"""Actual amendment effects must precede ordinary B06 calculation and guards."""
import copy
import hashlib
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext import test_annual_amendment_scope as parent_tests
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b06_current_input import inspect_current_debt_amendment,prepare_current_debt_input
from vnext.instant_balance_amendment import inspect_instant_balance_amendment
from vnext.normal_run_v3 import prepare_case
from vnext.sources import source_reference_record


class CurrentDebtInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent_tests.AnnualAmendmentScopeTest.setUpClass()
        cls.helper = parent_tests.AnnualAmendmentScopeTest()
        cls.company = 'paramount_skydance_paramount_global'
        cls.args = cls.helper.arguments(cls.company)
        with original_sources_only():
            cls.actual = inspect_current_debt_amendment(**cls.args)
            cls.packet = prepare_current_debt_input(repo_root=ROOT,company_id=cls.company)

    def changed(self,transform):
        args = copy.deepcopy(self.args); item = args['amendment']; raw = transform(item['raw'])
        self.assertTrue(raw != item['raw'],'Mutation must change actual source bytes')
        blob = {**item['blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old = item['reference']
        ref = source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        args['amendment'] = {**item,'raw':raw,'blob':blob,'reference':ref}
        with original_sources_only():return inspect_current_debt_amendment(**args)

    def test_real_effect_is_separate_from_debt_completeness_and_the_old_balance_policy(self):
        self.assertEqual('INPUT_PROPERTY_PROVEN',self.actual['decision'],self.actual['issues'])
        self.assertEqual(['B06'],self.actual['metric_ids'])
        self.assertEqual('ORIGINAL_CURRENT_DEBT_AND_EQUITY',self.actual['input_class'])
        for flag in ['annual_continuity_proven','debt_completeness_proven','production_authorized','source_acquisition_credit']:
            self.assertFalse(self.actual[flag])
        with original_sources_only():old = inspect_instant_balance_amendment(**self.args)
        self.assertEqual(['B08','B09'],old['metric_ids'])
        self.assertEqual('INPUT_PROPERTY_PROVEN',self.packet['decision'])
        self.assertEqual(1,len(self.packet['checks']))
        self.assertEqual('SUCCESSOR_REGISTRANT_ONLY',self.packet['prepared_input']['subject_policy']['mode'])

    def test_changed_debt_or_equity_outside_the_purpose_note_is_rejected(self):
        for text in [b'We corrected our total debt balance.',b'We revised our stockholders equity.',
                     b'Total debt was $99 billion at December 31, 2025.',
                     b'Shareholders equity was $99 billion at December 31, 2025.']:
            with self.subTest(text=text):
                result = self.changed(lambda raw:raw.replace(b'</body>',b'<p>'+text+b'</p></body>',1))
                self.assertEqual('WITHHELD',result['decision'])
                self.assertTrue(result['issues'])

    def test_changed_declared_amendment_purpose_and_new_native_debt_cannot_pass(self):
        result = self.changed(lambda raw:raw.replace(b'to amend Part III',b'to restate our debt and to amend Part III',1))
        self.assertEqual('WITHHELD',result['decision'])
        extra = b'<ix:nonFraction xmlns:new="http://fasb.org/us-gaap/2025" name="new:DebtAndCapitalLeaseObligations" contextRef="c20250101to20251231" unitRef="usd">900</ix:nonFraction>'
        result = self.changed(lambda raw:raw.replace(b'</body>',extra+b'</body>',1))
        self.assertEqual('WITHHELD',result['decision'])

    def test_current_run_input_retains_the_actual_amendment_without_creating_debt(self):
        with original_sources_only():case = prepare_case(data_root=ROOT,company_id=self.company,metric_id='B06')
        packet = case['input_binding']['current_debt_input']
        self.assertEqual(self.packet,packet)
        accession = self.packet['prepared_input']['amendments'][0]['accessionNumber']
        self.assertTrue(any(r['accession']==accession for r in case['references']))
        self.assertFalse(packet['debt_completeness_proven'])
        self.assertTrue(case['input_binding']['source_proof']['complete_b06_proven'])
        self.assertEqual(('PUBLISHED','1.168049260241169930727785855'),
                         (case['results']['B06']['publication'],case['results']['B06']['value']))
        from vnext.b06_inclusive_table import InclusiveDebtError
        with original_sources_only(), patch('vnext.normal_inclusive_debt_results.inspect_inclusive_debt_scope',
                side_effect=InclusiveDebtError('INCLUSIVE_DEBT_SOURCE_RELATIONSHIP_UNPROVEN')):
            unresolved=prepare_case(data_root=ROOT,company_id=self.company,metric_id='B06')
        self.assertEqual(packet,unresolved['input_binding']['current_debt_input'])
        self.assertEqual('WITHHELD',unresolved['results']['B06']['publication'])
        self.assertIn('SOURCE_RELATIONSHIP_UNPROVEN',unresolved['selection']['reason'])

    def test_unproven_amendment_does_not_enter_even_the_equity_guard(self):
        negative = self.changed(lambda raw:raw.replace(b'</body>',b'<p>We corrected our total debt balance.</p></body>',1))
        packet = copy.deepcopy(self.packet); packet.update(decision='WITHHELD',checks=[negative])
        with original_sources_only(), patch('vnext.b06_current_input.prepare_current_debt_input',return_value=packet), \
             patch('vnext.ordinary_debt_guard.prepare_current_guarded_b06_result',side_effect=AssertionError('Guard must wait for amendment input')):
            case = prepare_case(data_root=ROOT,company_id=self.company,metric_id='B06')
        self.assertEqual('WITHHELD',case['results']['B06']['publication'])
        self.assertEqual('B06_CURRENT_INPUT_UNRESOLVED',case['results']['B06']['reason_code'])
        self.assertFalse(case['selection']['equity_guard_evaluated'])
        self.assertFalse(case['selection']['debt_evaluated'])

    def test_source_relationship_failure_remains_a_withheld_result(self):
        from vnext.b06_note_carrying import NoteCarryingError
        from vnext.b06_bond_leases import BondLeaseError
        for company,name,error in [
            ('enphase_energy','vnext.normal_note_debt_results.inspect_note_carrying',NoteCarryingError('UNPROVEN_SOURCE_RELATIONSHIP')),
            ('macys','vnext.normal_bond_debt_results.inspect_bond_debt_scope',BondLeaseError('UNPROVEN_SOURCE_RELATIONSHIP'))]:
            with self.subTest(company=company), original_sources_only(), patch(name,side_effect=error):
                case = prepare_case(data_root=ROOT,company_id=company,metric_id='B06')
            self.assertEqual('WITHHELD',case['results']['B06']['publication'])
            self.assertEqual('B06_SOURCE_RELATIONSHIP_UNRESOLVED',case['results']['B06']['reason_code'])
            self.assertEqual('INPUT_PROPERTY_PROVEN',case['input_binding']['current_debt_input']['decision'])


if __name__ == '__main__':unittest.main()
