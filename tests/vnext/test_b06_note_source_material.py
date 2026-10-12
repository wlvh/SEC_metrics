"""Complete saved debt notes and in-memory source mutations; no acquisition."""
import copy
import hashlib
import re
import unittest
from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b06_note_carrying import inspect_note_carrying, POLICY, NoteCarryingError
from vnext.normal_governance_input import prepare_saved_original_financial_sources as _prepare_b06
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.ordinary_source_authority import verify_ordinary_source_proofs
from vnext.sources import source_reference_record


class NoteSourceMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hasattr(NoteSourceMaterialTest, 'preparation'):
            return
        with original_sources_only():
            cls.preparation = _prepare_b06(repo_root=ROOT,company_id='enphase_energy')
            verify_ordinary_source_proofs(data_root=ROOT,proofs=cls.preparation['input_binding']['source_proofs'])
            cls.args = {'primary':cls.preparation['primary'],'xml':cls.preparation['xml'],
                        'prepared':cls.preparation['input_binding']['prepared_annual_input']}
            cls.actual = inspect_note_carrying(**cls.args)

    def arguments(self): return copy.deepcopy(self.args)

    def change(self,args,kind,transform):
        item = args[kind]; raw = transform(item['raw_bytes'])
        self.assertNotEqual(raw,item['raw_bytes'],'Mutation must change actual source bytes')
        blob = {**item['raw_blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old = item['source_reference']
        reference = source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        args[kind] = {**item,'raw_bytes':raw,'raw_blob':blob,'source_reference':reference}

    def inspect(self,args):
        with original_sources_only(): return inspect_note_carrying(**args)

    def test_actual_complete_member_reconciliation_and_explicit_lease_absence(self):
        proof = self.actual; c = proof['composition']
        self.assertEqual({'total':'1204377000','current':'632183000','noncurrent':'572194000'},c['balances'])
        self.assertEqual(2,c['table_count_in_note'])
        self.assertEqual(['2028','2026','2025'],[m['year'] for m in c['members']])
        self.assertEqual(['572194000','632183000','0'],[m['carrying']['value'] for m in c['members']])
        self.assertEqual('1087023000',proof['reports']['equity']['chosen']['value'])
        self.assertEqual('EXPLICIT_CURRENT_ISSUER_POLICY',proof['finance_lease_absence']['basis'])
        rounded = [r for r in proof['narrative_inventory'] if r['disposition'].startswith('RECONCILED_')]
        self.assertEqual(4,len(rounded))
        self.assertFalse(proof['source_acquisition_credit']); self.assertFalse(proof['production_authorized'])

    def test_missing_or_historical_lease_statement_never_means_zero(self):
        statement = POLICY['no_finance_lease_statement'].encode()
        for replacement in [b'',b'The Company did not have any finance leases in the prior year.']:
            with self.subTest(replacement=replacement):
                args = self.arguments()
                for kind in ['primary','xml']: self.change(args,kind,lambda raw:raw.replace(statement,replacement))
                with self.assertRaisesRegex(ValueError,'EXPLICIT_NO_FINANCE_LEASE_REQUIRED'): self.inspect(args)

    def test_quoted_or_contradicted_lease_statement_is_not_current_issuer_evidence(self):
        statement = POLICY['no_finance_lease_statement'].encode()
        for transform in [lambda raw:raw.replace(statement,b'<blockquote>'+statement+b'</blockquote>'),
                          lambda raw:raw.replace(b'</body>',b'<p>We also have finance leases.</p></body>')]:
            args = self.arguments(); self.change(args,'primary',transform)
            with self.assertRaisesRegex(ValueError,'NO_FINANCE_LEASE_ATTRIBUTION_OR_CONTRADICTION'): self.inspect(args)

    def test_each_note_principal_and_adjustment_must_reconcile(self):
        args = self.arguments()
        for kind in ['primary','xml']: self.change(args,kind,lambda raw:raw.replace(b'575,000',b'675,000'))
        with self.assertRaisesRegex(ValueError,'MEMBER_RECONCILIATION_FAILED'): self.inspect(args)

    def test_an_unknown_table_row_cannot_hide_in_a_supported_schedule(self):
        args = self.arguments()
        for kind in ['primary','xml']:
            self.change(args,kind,lambda raw:raw.replace(b'Less: unamortized debt issuance costs',b'Additional credit facility'))
        with self.assertRaisesRegex(ValueError,'UNKNOWN_COMPOSITION_ROW'): self.inspect(args)

    def test_additional_current_borrowing_in_full_note_is_not_a_table_total(self):
        args = self.arguments(); date = 'December 31, 2025'
        addition = ('As of '+date+', additional borrowings of $17 million were outstanding outside the debt schedule. ').encode()
        for kind in ['primary','xml']:
            self.change(args,kind,lambda raw:raw.replace(b'The following table provides information',addition+b'The following table provides information'))
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_NARRATIVE_BALANCE|UNRESOLVED_ADDITIONAL_BORROWING'): self.inspect(args)

    def test_independent_native_inventory_catches_other_debt_and_finance_leases(self):
        for concept,reason in [('FinanceLeaseLiability','FINANCE_LEASE_FACT_CONFLICT'),('ShortTermBorrowings','UNRESOLVED_FINANCING_FACT'),('SeniorNotes','UNRESOLVED_FINANCING_FACT')]:
            args = self.arguments(); parsed = parse_accession_xbrl_source(raw_bytes=args['xml']['raw_bytes'])
            fact = next(f for f in parsed.facts if f['qualified_name'].casefold() == 'us-gaap:longtermdebt'
                        and parsed.contexts[f['context_ref']]['period_end'] == '2025-12-31')
            added = ('<us-gaap:'+concept+' contextRef="'+fact['context_ref']+'" unitRef="'+fact['unit_ref']+'" decimals="-3">17000000</us-gaap:'+concept+'>').encode()
            self.change(args,'xml',lambda raw:re.sub(rb'(</(?:[A-Za-z0-9_-]+:)?xbrl>\s*)$',lambda m:added+m[1],raw))
            with self.assertRaisesRegex(ValueError,reason): self.inspect(args)

    def test_cross_document_disagreement_and_wrong_currency_namespace_reject(self):
        args = self.arguments()
        self.change(args,'xml',lambda raw:raw.replace(b'The Company does not have any finance leases.',b'The Company has finance leases.'))
        with self.assertRaisesRegex(ValueError,'FULL_PRIMARY_XML_NOTE_CONFLICT'): self.inspect(args)
        args = self.arguments()
        for kind in ['primary','xml']:
            self.change(args,kind,lambda raw:raw.replace(b'http://www.xbrl.org/2003/iso4217',b'urn:untrusted-currency'))
        with self.assertRaisesRegex(ValueError,'UNIT_CONFLICT'): self.inspect(args)


class NoteRateMaterialTest(unittest.TestCase):
    """Alter a complete current filing without changing its note or balances."""
    @classmethod
    def setUpClass(cls):
        NoteSourceMaterialTest.setUpClass()
        cls.fixture = NoteSourceMaterialTest()

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

