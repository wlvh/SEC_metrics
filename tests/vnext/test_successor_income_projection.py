"""Successor short-period input is projected, without pretending it is annual."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext.ordinary_saved_result import _ordinary_case
from vnext.ordinary_projection import render_ordinary_records
from vnext.ordinary_income_input import visible_income_periods

COMPANY='paramount_skydance_paramount_global'


class SuccessorIncomeProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Constructed consistent-header control for projection only. The
        # real filing's 7th/8th conflict has a separate unmocked test below.
        def consistent_headers(raw,parsed,rows):
            return {row['ordinal']:{'status':'MATCH','native_period':[row['period_start'],row['period_end']],
                'visible_periods':[[row['period_start'],row['period_end']]],'headers':[],
                'test_control':'CONSTRUCTED_CONSISTENT_HEADERS'} for row in rows}
        with patch('vnext.ordinary_income_input.visible_income_periods',side_effect=consistent_headers):
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

    def test_actual_original_header_context_conflict_is_named_withheld(self):
        case=_ordinary_case(REPO_ROOT,COMPANY,'B01')
        result=case['results']['B01']
        self.assertEqual(result['publication'],'WITHHELD')
        self.assertEqual(result['reason_code'],'ORDINARY_INCOME_VISIBLE_PERIOD_CONFLICT')
        self.assertIsNone(result['value'])
        self.assertIn('2025-08-07',case['selection']['reason'])
        self.assertIn('2025-08-08',case['selection']['reason'])
        self.assertNotIn('prepared_income_input',case)
        self.assertEqual(case['input_assessments']['income_period']['status'],'CONFLICT')
        self.assertTrue(case['input_assessments']['income_period']['headers'])


class VisibleIncomePeriodTest(unittest.TestCase):
    raw=b'''<html><table>
    <tr><td></td><td>Period From August 7 - December 31,</td><td>Period From January 1 - August 6,</td></tr>
    <tr><td></td><td>2025</td><td>2025</td></tr>
    <tr><td>Revenues</td><td><ix:nonFraction contextRef="c-1">12</ix:nonFraction></td>
    <td><ix:nonFraction contextRef="c-2">16</ix:nonFraction></td></tr>
    </table></html>'''

    def inspect(self,start='2025-08-08',raw=None):
        rows=[{'ordinal':1,'period_start':start,'period_end':'2025-12-31','source_reference':{'test':'source'}}]
        parsed=SimpleNamespace(facts=[{'ordinal':1},{'ordinal':2}])
        return visible_income_periods(raw or self.raw,parsed,rows)[1]

    def test_conflict_and_consistent_short_period(self):
        self.assertEqual(self.inspect()['status'],'CONFLICT')
        self.assertEqual(self.inspect()['visible_periods'],[['2025-08-07','2025-12-31']])
        self.assertEqual(self.inspect(start='2025-08-07')['status'],'MATCH')
        self.assertEqual(self.inspect(raw=self.raw.replace(b'August 7',b'August 8'))['status'],'MATCH')

    def test_other_column_date_cannot_prove_this_fact(self):
        result=self.inspect(start='2025-01-01')
        self.assertEqual(result['status'],'CONFLICT')
        self.assertNotIn(['2025-01-01','2025-08-06'],result['visible_periods'])

    def test_missing_range_remains_unresolved(self):
        self.assertEqual(self.inspect(raw=self.raw.replace(b'Period From August 7 - December 31,',b'Unknown period'))['status'],
                         'UNRESOLVED')

if __name__=='__main__':unittest.main()
