"""Original successor debt tables and counterexamples that alter their meaning."""
import copy
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext import test_b06_bond_leases as bond_tests
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b06_inclusive_table import inspect_inclusive_debt_scope
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_candidates import _prepare_b06
from vnext.normal_source_authority import verify_saved_source_proofs


class InclusiveDebtSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            p=_prepare_b06(repo_root=ROOT,company_id='paramount_skydance_paramount_global')
            verify_saved_source_proofs(data_root=ROOT,proofs=p['input_binding']['source_proofs'])
            cls.args={'primary':p['primary'],'xml':p['xml'],'prepared':p['input_binding']['prepared_annual_input']}
            cls.actual=inspect_inclusive_debt_scope(**cls.args)

    changed=bond_tests.SeparateLeaseSourceTest.changed

    def inspect(self,args):
        with original_sources_only():return inspect_inclusive_debt_scope(**args)

    def both(self,before,after):
        args=copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args=self.changed(kind,lambda raw:raw.replace(before,after),args)
        return args

    def test_actual_inclusive_total_subject_and_other_measurements(self):
        p=self.actual
        self.assertEqual('13658000000',p['carrying_amount'])
        self.assertTrue(p['complete_b06_proven'])
        self.assertEqual(25,len(p['members']))
        self.assertEqual('3000000',p['roles']['finance_lease']['value'])
        self.assertTrue(p['finance_lease_already_included'])
        self.assertEqual('2041610',p['balance_scope']['entity'])
        self.assertFalse(p['balance_scope']['predecessor_combined'])
        self.assertEqual('11693000000',p['reports']['equity']['chosen']['value'])
        m=p['measurements']
        self.assertEqual('2025-08-07',m['acquisition_date'])
        self.assertEqual('14976000000',m['maturity_face_total'])
        self.assertEqual('14980000000',m['face']['value'])
        self.assertEqual('13655000000',m['exact_notes_carrying'])
        self.assertEqual('13650000000',m['rounded_notes_carrying']['value'])
        self.assertTrue(m['coarse_measurements_are_not_calculation_operands'])
        self.assertEqual(147,len(p['independent_financing_inventory']['xml']))
        typed=[r for r in p['independent_financing_inventory']['xml'] if r['typed_dimensions']]
        self.assertEqual(['2026-01-01','2027-01-01','2028-01-01'],sorted(r['typed_dimensions'][0]['value'] for r in typed))
        self.assertFalse(p['source_acquisition_credit']);self.assertFalse(p['production_authorized'])

    def test_predecessor_column_cannot_be_renamed_current(self):
        args=self.both(b'Successor',b'Predecessor')
        with self.assertRaisesRegex(ValueError,'CURRENT_SUCCESSOR_COLUMN_UNPROVEN'):self.inspect(args)

    def test_missing_finance_lease_row_does_not_mean_zero(self):
        args=self.both(b'Obligations under finance leases',b'Other liabilities')
        with self.assertRaisesRegex(ValueError,'UNRECONCILED_DEBT_ROW'):self.inspect(args)

    def test_native_current_total_disagreement_is_not_overwritten(self):
        args=self.changed('xml',lambda raw:raw.replace(b'>13658000000<',b'>13678000000<'))
        with self.assertRaisesRegex(ValueError,'PRECISION_CONFLICT'):self.inspect(args)

    def test_extra_native_senior_note_or_borrowing_cannot_escape_inventory(self):
        parsed=parse_accession_xbrl_source(raw_bytes=self.args['xml']['raw_bytes'])
        current=next(f for f in parsed.facts if f['qualified_name'].casefold()=='us-gaap:debtandcapitalleaseobligations'
                     and parsed.contexts[f['context_ref']]['period_end']=='2025-12-31')
        for concept,reason in [('SeniorNotes','NATIVE_MEMBER_DOCUMENT_SETS_DIFFER'),('ShortTermBorrowings','UNRESOLVED_ADDITIONAL_FINANCING_FACT')]:
            with self.subTest(concept=concept):
                added=('<us-gaap:'+concept+' contextRef="'+current['context_ref']+'" unitRef="'+current['unit_ref']+'" decimals="-6">17000000</us-gaap:'+concept+'>').encode()
                args=self.changed('xml',lambda raw:raw.replace(b'</xbrl>',added+b'</xbrl>'))
                with self.assertRaisesRegex(ValueError,reason):self.inspect(args)

    def test_unknown_or_unquantified_narrative_borrowing_rejects(self):
        for sentence in [b'Other borrowings are not included above. ',
                         b'At December 31, 2025, additional borrowings of $17 million were outstanding. ',
                         b'We have additional finance leases. ']:
            with self.subTest(sentence=sentence):
                args=self.both(b'The table below details our debt',sentence+b'The table below details our debt')
                with self.assertRaisesRegex(ValueError,'UNRESOLVED_ADDITIONAL_BORROWING'):self.inspect(args)

    def test_parent_equity_scope_cannot_be_replaced_by_other_equity(self):
        args=self.changed('primary',lambda raw:raw.replace(b'Total Parent stockholders',b'Total minority stockholders'))
        with self.assertRaisesRegex(ValueError,'PARENT_EQUITY_SCOPE_UNPROVEN'):self.inspect(args)

    def test_acquisition_amount_is_bound_to_the_earlier_source_table(self):
        args=self.changed('xml',lambda raw:raw.replace(b'>13619000000<',b'>14619000000<'))
        with self.assertRaisesRegex(ValueError,'ACQUISITION_MEASUREMENT_SCOPE_MISSING'):self.inspect(args)

    def test_maturity_table_cannot_relabel_face_amount_as_carrying(self):
        args=self.both(b'debt at face value',b'debt at carrying value')
        with self.assertRaisesRegex(ValueError,'MATURITY_FACE_EXCLUDES_LEASE_SCOPE_UNPROVEN'):self.inspect(args)

    def test_future_typed_revenue_bucket_cannot_be_reused_as_a_borrowing(self):
        parsed=parse_accession_xbrl_source(raw_bytes=self.args['xml']['raw_bytes'])
        current=next(f for f in parsed.facts if f['qualified_name'].casefold()=='us-gaap:revenueremainingperformanceobligation'
                     and parsed.contexts[f['context_ref']]['typed_dimension_count'])
        added=('<us-gaap:ShortTermBorrowings contextRef="'+current['context_ref']+'" unitRef="'+current['unit_ref']+'" decimals="-6">17000000</us-gaap:ShortTermBorrowings>').encode()
        args=self.changed('xml',lambda raw:raw.replace(b'</xbrl>',added+b'</xbrl>'))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_TYPED_FINANCING_CONTEXT'):self.inspect(args)

    def test_extra_financing_note_cannot_hide_outside_the_debt_note(self):
        parsed=parse_accession_xbrl_source(raw_bytes=self.args['xml']['raw_bytes'])
        note=next(f for f in parsed.facts if f['qualified_name'].casefold()=='us-gaap:debtdisclosuretextblock')
        added=('<us-gaap:LoansDisclosureTextBlock contextRef="'+note['context_ref']+'">Additional loans are outstanding.</us-gaap:LoansDisclosureTextBlock>').encode()
        args=self.changed('xml',lambda raw:raw.replace(b'</xbrl>',added+b'</xbrl>'))
        with self.assertRaisesRegex(ValueError,'ADDITIONAL_FINANCING_NOTE_OUTSIDE_PROVEN_SCOPE'):self.inspect(args)
