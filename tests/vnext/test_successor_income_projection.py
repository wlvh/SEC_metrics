"""Successor short-period input is projected, without pretending it is annual."""
import copy
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.ordinary_saved_result import _ordinary_case
from vnext.ordinary_projection import render_ordinary_records

COMPANY='paramount_skydance_paramount_global'


class SuccessorIncomeProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=_ordinary_case(REPO_ROOT,COMPANY,'B01')
        cls.manifest={'company_id':COMPANY,'target_period':cls.case['target_period'],
            'source_references':cls.case['references'],'run_id':'ordinary:source-test','status':'CALCULATED'}

    def render(self,case=None):
        c=case or self.case
        return render_ordinary_records(data_root=REPO_ROOT,manifest=self.manifest,
            records=c['expected_records'],case=c,receipt_status='RECORDED_SOURCE_TEST',
            source_validation='EXISTING_SOURCE_AND_STATEMENT_CHECKS',prepared_annual_input=c['prepared_annual_input'])

    def test_short_period_state_has_actual_dates_and_preserves_annual_guard(self):
        output=self.render();result=self.case['results']['B01']
        self.assertEqual(result['period_start'],'2025-08-08')
        self.assertEqual(result['period_end'],'2025-12-31')
        self.assertEqual(result['reason_code'],'ANNUAL_DURATION_OUT_OF_RANGE')
        self.assertIsNone(result['value'])
        self.assertIn(b'2025-08-08',output['files']['metrics_matrix.csv'])
        self.assertFalse(self.case['prepared_income_input']['financial_cross_entity_combination_authorized'])

    def test_missing_proof_does_not_allow_an_arbitrary_shorter_period(self):
        c=copy.deepcopy(self.case);c.pop('prepared_income_input');c.pop('income_observation_checks')
        with self.assertRaisesRegex(ValueError,'PREPARED_PERIOD_CHANGED'):self.render(c)

    def test_wrong_subject_or_statement_period_still_rejected(self):
        for change in ('company','period','combination'):
            c=copy.deepcopy(self.case);income=c['prepared_income_input']
            if change=='company':income['company_id']='other_company'
            elif change=='period':income['statement_period']['period_start']='2025-08-09'
            else:income['financial_cross_entity_combination_authorized']=True
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'INCOME_PERIOD_PROOF_CHANGED'):
                self.render(c)

    def test_result_cannot_claim_a_different_short_period(self):
        c=copy.deepcopy(self.case)
        result=next(r for r in c['expected_records'] if r['record_type']=='METRIC_RESULT')
        result['period_start']='2025-08-09'
        with self.assertRaisesRegex(ValueError,'INCOME_PERIOD_PROOF_CHANGED'):
            self.render(c)

    def test_numeric_result_requires_checked_source_observations(self):
        c=copy.deepcopy(self.case)
        result=next(r for r in c['expected_records'] if r['record_type']=='METRIC_RESULT')
        result['value']='1'
        c['income_observation_checks']=[]
        with self.assertRaisesRegex(ValueError,'INCOME_OBSERVATION_PROOF_MISSING'):
            self.render(c)

if __name__=='__main__':unittest.main()
