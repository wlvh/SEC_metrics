"""Historical balance attribution, share counts and asset-table boundaries."""
import re
import unittest

from vnext.b06_note_carrying import NoteCarryingError
from vnext.b06_note_carrying import (_narrative as narrative_inventory,
    _prior_principal_balance as prior_principal_balance,
    _related_tables_inventory as related_tables_inventory)


class NoteSourceFormsTest(unittest.TestCase):
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

