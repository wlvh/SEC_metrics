"""Small issuer display checks; all numbers/periods stay in original records."""
from copy import deepcopy
from pathlib import Path
import unittest
from scripts.vnext import ordinary_projection as projection

ROOT=Path(__file__).resolve().parents[2]
COMPANY='paramount_skydance_paramount_global'

class ReportingCompanyProjectionTest(unittest.TestCase):
    def setUp(self):
        self.company=next(c for c in projection.projector._load_registry(repo_root=ROOT) if c['company_id']==COMPANY)
        self.annual={'company_id':COMPANY,'entity':'813828','filing':{'accessionNumber':'0000813828-22-000005'},
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY','selected_cik':'813828','cross_entity_combination_authorized':False}}
        self.target={'company_id':COMPANY,'entity':'813828','accession':'0000813828-22-000005'}

    def view(self):
        return projection._reporting_company_view(data_root=ROOT,company=self.company,
            annual=self.annual,calculation_target=self.target)

    def test_predecessor_reporting_cik_changes_only_presentation_view(self):
        before=deepcopy(self.company);actual=self.view()
        self.assertEqual(actual['primary_cik'],'813828')
        self.assertEqual(actual['company_id'],COMPANY)
        self.assertEqual({k:v for k,v in actual.items() if k!='primary_cik'},
                         {k:v for k,v in before.items() if k!='primary_cik'})
        self.assertEqual(self.company,before)

    def test_current_reporter_preserves_current_view(self):
        self.annual['entity']=self.target['entity']='2041610'
        self.assertEqual(self.view(),self.company)

    def test_unregistered_reporter_or_cross_subject_trace_is_rejected(self):
        self.annual['entity']=self.target['entity']='12345'
        with self.assertRaisesRegex(ValueError,'REPORTER_NOT_REGISTERED'):self.view()
        self.annual['entity']='813828';self.target['entity']='2041610'
        with self.assertRaisesRegex(ValueError,'TRACE_SUBJECT_CHANGED'):self.view()
        self.target['entity']='813828';self.target['company_id']='other-company'
        with self.assertRaisesRegex(ValueError,'TRACE_SUBJECT_CHANGED'):self.view()

    def test_different_filing_or_bad_entity_does_not_gain_display_identity(self):
        self.target['accession']='different-filing'
        with self.assertRaisesRegex(ValueError,'TRACE_FILING_CHANGED'):self.view()
        self.annual['entity']='not-a-cik'
        with self.assertRaisesRegex(ValueError,'REPORTER_NOT_REGISTERED'):self.view()

    def test_combined_or_unproven_subject_policy_does_not_get_single_reporter_view(self):
        self.annual['subject_policy']['cross_entity_combination_authorized']=True
        with self.assertRaisesRegex(ValueError,'REPORTER_SCOPE_NOT_PROVEN'):self.view()
        self.annual.pop('subject_policy')
        with self.assertRaisesRegex(ValueError,'REPORTER_SCOPE_NOT_PROVEN'):self.view()

if __name__=='__main__':unittest.main()
