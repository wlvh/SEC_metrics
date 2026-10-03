"""Historical balance attribution, share counts and asset-table boundaries."""
import re
import unittest

from vnext.b06_note_carrying import NoteCarryingError
from vnext.historical_note_carrying import (narrative_inventory, prior_principal_balance,
    related_tables_inventory, inspect_note_carrying)


class HistoricalNoteCarryingTest(unittest.TestCase):
    prior = ('Following the repurchase combined with repurchase in previous years, '
             'as of December 31, 2023, $102.2 million aggregate principal amount of '
             'the Notes due 2025 remained outstanding.')
    shares = ('As of December 31, 2024, options to purchase approximately 1.3 million '
              'shares of common stock remained outstanding under the Notes due 2025 '
              'Hedge, and 2025 Warrants exercisable to purchase approximately 1.3 million '
              'shares remained outstanding.')

    def narrative(self, sentence):
        return narrative_inventory([{'qualified_name':'us-gaap:DebtDisclosureTextBlock',
                                      'text':'<p>' + sentence + '</p>'}],
                                    {'members':[], 'balances':{}}, '2024-12-31')

    def test_wholly_prior_principal_balance_is_not_current_debt(self):
        rows = self.narrative(self.prior)
        self.assertEqual(['EXPLICIT_PRIOR_PERIOD_PRINCIPAL_BALANCE'],
                         [row['disposition'] for row in rows])
        self.assertEqual(self.prior, rows[0]['sentence'])
        self.assertTrue(prior_principal_balance(
            'As of ' + self.prior.split(', as of ', 1)[1], '2024-12-31'))

    def test_current_future_mixed_or_additional_balances_keep_refusal(self):
        for sentence in [self.prior.replace('2023,', '2024,'),
                         self.prior.replace('2023,', '2025,'),
                         self.prior.replace('December 31, 2023', 'February 31, 2023'),
                         self.prior.replace('Following the repurchase', 'On June 30, 2024, following the repurchase'),
                         self.prior.replace('Following the repurchase', 'Currently $5 million and following the repurchase'),
                         self.prior.replace('remained outstanding.', 'remained outstanding, plus $17 million additional borrowings.')]:
            with self.subTest(sentence=sentence):
                with self.assertRaisesRegex(NoteCarryingError, 'NARRATIVE_PERIOD_UNPROVEN|UNRESOLVED_NARRATIVE_BALANCE'):
                    self.narrative(sentence)

    def test_every_quantity_is_a_count_of_equity_shares(self):
        self.assertEqual('EQUITY_INSTRUMENT_SHARE_COUNTS', self.narrative(self.shares)[0]['disposition'])

    def test_mixed_cash_or_nonshare_quantities_are_not_excluded(self):
        for sentence in [self.shares.replace('approximately 1.3 million', '$1.3 million', 1),
                         self.shares.replace('1.3 million shares remained', '1.3 million notes remained'),
                         self.shares.replace('options', 'borrowings').replace('Warrants', 'notes')]:
            with self.subTest(sentence=sentence):
                with self.assertRaisesRegex(NoteCarryingError, 'UNRESOLVED_NARRATIVE_BALANCE'):
                    self.narrative(sentence)

    def inventory(self, prefix, concept='us-gaap:DebtSecuritiesAvailableForSaleTableTextBlock', label='Commercial paper'):
        return related_tables_inventory([{'qualified_name':concept, 'text': '<p>' + prefix + '</p>'
            + '<table><tr><td>' + label + '</td><td>30,713</td></tr></table>'}])

    def test_reported_asset_table_with_or_without_article(self):
        for prefix in ['Cash equivalents, restricted cash and marketable securities consist of the following:',
                       'The cash equivalents, restricted cash and marketable securities consist of the following:']:
            self.assertEqual('REPORTED_CASH_OR_MARKETABLE_SECURITY_ASSET', self.inventory(prefix)[0]['disposition'])

    def test_commercial_paper_liability_or_wrong_table_is_unresolved(self):
        asset = 'The cash equivalents, restricted cash and marketable securities consist of the following:'
        for args in [(asset, 'us-gaap:DebtDisclosureTextBlock'),
                     ('The Company issued commercial paper as follows:',),
                     (asset, 'us-gaap:DebtSecuritiesAvailableForSaleTableTextBlock', 'Borrowings')]:
            with self.subTest(args=args):
                with self.assertRaisesRegex(NoteCarryingError, 'UNRESOLVED_RELATED_TABLE_ROW'):
                    self.inventory(*args)


class HistoricalNoteRateMaterialTest(unittest.TestCase):
    """Alter a complete current filing without changing its note or balances."""
    @classmethod
    def setUpClass(cls):
        from tests.vnext import test_b06_note_carrying as ordinary
        ordinary.NoteCarryingTest.setUpClass()
        cls.fixture = ordinary.NoteCarryingTest()

    def arguments(self, *, unit='pure', prefix='us-gaap', concept='DebtInstrumentInterestRateEffectivePercentage'):
        from vnext.deterministic_router import parse_accession_xbrl_source
        args = self.fixture.arguments()
        for kind in ['xml', 'primary']:
            parsed = parse_accession_xbrl_source(raw_bytes=args[kind]['raw_bytes'])
            fact = next(f for f in parsed.facts if f['qualified_name'].split(':')[-1].casefold() == 'debtinstrumentcarryingamount'
                        and parsed.contexts[f['context_ref']]['dimensions']
                        and parsed.contexts[f['context_ref']]['period_end'] == '2025-12-31'
                        and parsed.contexts[f['context_ref']]['period_start'] == '2025-12-31')
            name = prefix + ':' + concept
            unit_id = 'historical-note-rate-test'
            unit_xml = ('<xbrli:unit xmlns:xbrli="http://www.xbrl.org/2003/instance" '
                        'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" id="' + unit_id + '"><xbrli:measure>') + (
                'xbrli:pure' if unit == 'pure' else 'iso4217:USD') + '</xbrli:measure></xbrli:unit>'
            if kind == 'xml':
                addition = (unit_xml + '<' + name + ' contextRef="' + fact['context_ref']
                    + '" unitRef="' + unit_id + '" decimals="3">0.035</' + name + '>').encode()
                self.fixture.change(args,kind,lambda raw:re.sub(
                    rb'(</(?:[A-Za-z0-9_-]+:)?xbrl>\s*)$',lambda m:addition+m[1],raw))
            else:
                addition = (unit_xml + '<ix:nonFraction name="' + name + '" contextRef="' + fact['context_ref']
                    + '" unitRef="' + unit_id + '" decimals="3">0.035</ix:nonFraction>').encode()
                self.fixture.change(args,kind,lambda raw:raw.replace(b'</body>',addition+b'</body>'))
        return args

    def inspect(self, args):
        from tests.vnext.test_normal_zero_ai_results import original_sources_only
        with original_sources_only():
            return inspect_note_carrying(**args)

    def test_standard_pure_rate_leaves_complete_debt_and_equity_unchanged(self):
        proof = self.inspect(self.arguments())
        self.assertEqual(self.fixture.actual['composition'], proof['composition'])
        self.assertEqual(self.fixture.actual['reports'], proof['reports'])
        for inventory in proof['native_inventory'].values():
            self.assertTrue(any(row['disposition'] == 'DIMENSIONED_DEBT_EFFECTIVE_INTEREST_RATE'
                                for row in inventory))

    def test_rate_caption_with_currency_is_not_a_nonmonetary_rate(self):
        with self.assertRaisesRegex(NoteCarryingError,'UNRESOLVED_FINANCING_FACT'):
            self.inspect(self.arguments(unit='USD'))

    def test_article_in_actual_asset_note_does_not_move_debt(self):
        args = self.fixture.arguments()
        phrase = b'Cash equivalents, restricted cash and marketable securities consist of the following:'
        for kind in ['xml', 'primary']:
            self.fixture.change(args,kind,lambda raw:raw.replace(phrase,b'The cash' + phrase[4:]))
        proof = self.inspect(args)
        self.assertEqual(self.fixture.actual['composition'], proof['composition'])
        self.assertEqual(self.fixture.actual['reports'], proof['reports'])
        self.assertTrue(any(row['disposition'] == 'REPORTED_CASH_OR_MARKETABLE_SECURITY_ASSET'
                            for row in proof['related_table_inventory']))

    def test_custom_rate_or_another_pure_financing_fact_remains_unresolved(self):
        for args in [self.arguments(prefix='enph'), self.arguments(concept='ShortTermBorrowings')]:
            with self.subTest(prefix=args['xml']['source_reference']['raw_asset_id']):
                with self.assertRaisesRegex(NoteCarryingError,'UNRESOLVED_FINANCING_FACT'):
                    self.inspect(args)


if __name__ == '__main__':
    unittest.main()
