"""Small issuer display checks; all numbers/periods stay in original records."""
from copy import deepcopy
from pathlib import Path
import unittest
from sec_urls import accession_document_url, submissions_url
from scripts.vnext import ordinary_projection as projection

ROOT=Path(__file__).resolve().parents[2]
COMPANY='paramount_skydance_paramount_global'

class ReportingCompanyProjectionTest(unittest.TestCase):
    def setUp(self):
        self.company=next(c for c in projection.projector._load_registry(repo_root=ROOT) if c['company_id']==COMPANY)
        self.annual={'company_id':COMPANY,'entity':'813828','filing':{'accessionNumber':'0000813828-22-000005','primaryDocument':'viac-20211231.htm'},
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY','selected_cik':'813828','cross_entity_combination_authorized':False}}
        self.target={'company_id':COMPANY,'entity':'813828','accession':'0000813828-22-000005'}
        self.references=[{'company_id':COMPANY,'accession':'0000813828-22-000005',
            'source_url':accession_document_url(cik=813828,accession='0000813828-22-000005',document_name='viac-20211231.htm')}]
        self.metadata_only=False

    def view(self):
        return projection._reporting_company_view(data_root=ROOT,company=self.company,
            annual=self.annual,calculation_target=self.target,source_references=self.references,
            allow_metadata_only=self.metadata_only)

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

    def test_explicit_null_issuer_fields_use_verified_annual_without_modifying_trace(self):
        self.target['entity']=self.target['accession']=None
        before=deepcopy(self.target)
        self.assertEqual(self.view()['primary_cik'],'813828')
        self.assertEqual(self.target,before)

    def test_nullable_contract_does_not_hide_filled_conflicts_or_missing_fields(self):
        self.target['entity']=None;self.target['accession']='wrong-filing'
        with self.assertRaisesRegex(ValueError,'TRACE_FILING_CHANGED'):self.view()
        self.target['accession']=None;self.target['entity']='2041610'
        with self.assertRaisesRegex(ValueError,'TRACE_SUBJECT_CHANGED'):self.view()
        self.target.pop('entity')
        with self.assertRaisesRegex(ValueError,'TRACE_SUBJECT_CHANGED'):self.view()

    def test_null_target_requires_matching_source_not_another_registered_issuer(self):
        self.target['entity']=self.target['accession']=None
        self.references[0]['source_url']=accession_document_url(cik=2041610,accession='0000813828-22-000005',document_name='viac-20211231.htm')
        with self.assertRaisesRegex(ValueError,'REPORTER_SOURCE_NOT_PROVEN'):self.view()
        self.references=[]
        with self.assertRaisesRegex(ValueError,'REPORTER_SOURCE_NOT_PROVEN'):self.view()

    def test_metadata_only_outcome_can_keep_inventory_issuer_without_claiming_amount(self):
        self.target['entity']=self.target['accession']=None
        self.references=[{'company_id':COMPANY,'source_url':submissions_url(cik=813828)}]
        with self.assertRaisesRegex(ValueError,'REPORTER_SOURCE_NOT_PROVEN'):self.view()
        self.metadata_only=True
        self.assertEqual(self.view()['primary_cik'],'813828')

    def test_valued_historical_event_uses_selected_inventory_and_source_set(self):
        self.target['entity']=self.target['accession']=None
        inventory={'record_type':'SOURCE_REFERENCE','source_reference_id':'inventory',
            'company_id':COMPANY,'source_url':submissions_url(cik=813828),
            'source_role':'sec_submissions_inventory','raw_asset_id':'sha256:inventory'}
        event={'record_type':'SOURCE_REFERENCE','source_reference_id':'event',
            'company_id':COMPANY,'accession':'0000813828-21-000001','document_name':'event.htm',
            'source_url':accession_document_url(cik=813828,accession='0000813828-21-000001',document_name='event.htm')}
        window={'period_start':'2021-01-01','period_end':'2021-12-31','fiscal_year':2021}
        self.annual['table_input']={'target_period':window}
        binding={'record_type':'HISTORICAL_EVENT_SOURCE_INPUT','prepared_input':deepcopy(self.annual),
            'metric_id':'C01','event_window':window,'financial_cross_entity_combination_authorized':False,
            'registered_event_scope':None,'source_set_manifests':[{
                'record_type':'SOURCE_SET_MANIFEST','company_id':COMPANY,'source_role':'fy_8k_item_inventory',
                'form_types':['8-K','8-K/A'],'discovery_policy':'PINNED_SUBMISSIONS',
                'inventory_source_reference_id':'inventory','sec_submissions_inventory_hash':'sha256:inventory',
                'fiscal_or_date_window':{k:window[k] for k in ('period_start','period_end')},
                'ordered_source_reference_ids':['event']}]}
        def view(refs,b= binding,metric='C01'):
            return projection._reporting_company_view(data_root=ROOT,company=self.company,
                annual=self.annual,calculation_target=self.target,source_references=refs,
                event_input_binding=b,event_metric_id=metric)
        before=deepcopy(self.target)
        self.assertEqual(view([inventory,event])['primary_cik'],'813828')
        self.assertEqual(self.target,before)
        union=deepcopy(binding)
        union['source_set_manifests'].append({**union['source_set_manifests'][0],
            'discovery_policy':'PINNED_SUBMISSIONS_SHARD_UNION_V1'})
        self.assertEqual(view([inventory,event],union)['primary_cik'],'813828')
        foreign=deepcopy(inventory);foreign['source_url']=submissions_url(cik=2041610)
        with self.assertRaisesRegex(ValueError,'REPORTER_EVENT_SOURCE_NOT_PROVEN'):view([foreign,event])
        foreign_event=deepcopy(event);foreign_event['source_url']=accession_document_url(cik=2041610,
            accession=event['accession'],document_name=event['document_name'])
        with self.assertRaisesRegex(ValueError,'REPORTER_EVENT_SOURCE_NOT_PROVEN'):view([inventory,foreign_event])
        for field,value in [('metric_id','B01'),('event_window',{**window,'period_end':'2022-12-31'}),
                            ('financial_cross_entity_combination_authorized',True)]:
            changed=deepcopy(binding);changed[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'REPORTER_EVENT_SOURCE_NOT_PROVEN'):
                view([inventory,event],changed)
        with self.assertRaisesRegex(ValueError,'REPORTER_SOURCE_NOT_PROVEN'):
            view([inventory,event],metric='B01')
        # A failed/missing event set can still display a metadata-only withheld
        # outcome; it gains no amount or completed event-set credit.
        missing=deepcopy(binding);missing['source_set_manifests']=[]
        with self.assertRaisesRegex(ValueError,'REPORTER_EVENT_SOURCE_NOT_PROVEN'):
            view([inventory],missing)
        metadata=projection._reporting_company_view(data_root=ROOT,company=self.company,
            annual=self.annual,calculation_target=self.target,source_references=[inventory],
            allow_metadata_only=True,event_input_binding=missing,event_metric_id='C01')
        self.assertEqual(metadata['primary_cik'],'813828')

    def test_registered_union_still_requires_its_existing_period_proof(self):
        from tests.vnext.test_registered_event_projection import RegisteredEventProjectionTest
        fixture=RegisteredEventProjectionTest();fixture.setUp()
        annual=fixture.annual
        annual['filing'].update(accessionNumber='0002041610-26-000001',primaryDocument='annual.htm')
        annual['subject_policy']['cross_entity_combination_authorized']=False
        binding=fixture.case['input_binding']
        binding.update(record_type='HISTORICAL_EVENT_SOURCE_INPUT',metric_id='C01',
            prepared_input=deepcopy(annual),financial_cross_entity_combination_authorized=False)
        for item in binding['source_set_manifests']:
            item.update(record_type='SOURCE_SET_MANIFEST',source_role='fy_8k_item_inventory',
                form_types=['8-K','8-K/A'],discovery_policy='PINNED_SUBMISSIONS_SHARD_UNION_V1',
                sec_submissions_inventory_hash='sha256:inventory',ordered_source_reference_ids=[])
        for ref in fixture.case['references']:ref['raw_asset_id']='sha256:inventory'
        target={'company_id':COMPANY,'entity':None,'accession':None}
        def view(proven=False):
            return projection._reporting_company_view(data_root=ROOT,company=self.company,
                annual=annual,calculation_target=target,source_references=fixture.case['references'],
                event_input_binding=binding,event_metric_id='C01',registered_event_period_proven=proven)
        with self.assertRaisesRegex(ValueError,'REPORTER_EVENT_SOURCE_NOT_PROVEN'):view()
        self.assertTrue(fixture.proven())
        self.assertEqual(view(fixture.proven())['primary_cik'],'2041610')
        fixture.case['references'][0]['source_url']=submissions_url(cik=813828)
        with self.assertRaisesRegex(ValueError,'EVENT_SCOPE_CHANGED'):fixture.proven()
        with self.assertRaisesRegex(ValueError,'REPORTER_EVENT_SOURCE_NOT_PROVEN'):view(True)



class CurrentNullableTraceProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.vnext.common import REPO_ROOT
        from vnext.ordinary_saved_result import _ordinary_case
        from vnext.normal_lodging_results import prepare_ordinary_lodging_case
        cls.root=REPO_ROOT
        cls.cases={'B12':_ordinary_case(REPO_ROOT,'marriott_international','B12')}
        for metric in ('B10','B11'):
            cls.cases[metric]=prepare_ordinary_lodging_case(repo_root=REPO_ROOT,
                company_id='marriott_international',metric_id=metric,rules_root=REPO_ROOT)

    def test_current_structural_and_both_hotel_numbers_save_with_nullable_trace(self):
        import tempfile,csv,io
        from vnext.ordinary_saved_result import save_calculated_case,read_saved_result
        with tempfile.TemporaryDirectory() as directory:
            for metric,case in self.cases.items():
                with self.subTest(metric=metric):
                    result=case['results'][metric]
                    trace=next(r for r in case['expected_records'] if r['record_type']=='EXECUTION_TRACE'
                               and r['trace_id']==result['trace_id'])
                    self.assertIsNone(trace['calculation_target']['entity'])
                    self.assertIsNone(trace['calculation_target']['accession'])
                    saved=save_calculated_case(source_root=self.root,output_root=Path(directory)/metric,
                        company_id='marriott_international',metric_id=metric,case=case)
                    row=list(csv.DictReader(io.StringIO(saved['files']['metrics_matrix.csv'].decode())))[0]
                    self.assertEqual(row['cik'],'1048286')
                    self.assertEqual(saved['result'],result)
                    self.assertEqual(read_saved_result(output_root=Path(directory)/metric)['result'],result)
                    if metric=='B12':self.assertEqual(row['status'],'N_A_STRUCTURAL')
                    else:self.assertIsNotNone(result['value'])

    def test_current_reported_rpo_with_nullable_trace_keeps_value_and_issuer(self):
        import tempfile,csv,io
        from vnext.ordinary_saved_result import _ordinary_case,save_calculated_case,read_saved_result
        case=_ordinary_case(self.root,'salesforce','B12')
        result=case['results']['B12']
        trace=next(r for r in case['expected_records'] if r['record_type']=='EXECUTION_TRACE'
                   and r['trace_id']==result['trace_id'])
        self.assertIsNone(trace['calculation_target']['entity'])
        self.assertIsNone(trace['calculation_target']['accession'])
        with tempfile.TemporaryDirectory() as directory:
            written=save_calculated_case(source_root=self.root,output_root=Path(directory)/'result',
                company_id='salesforce',metric_id='B12',case=case)
            reread=read_saved_result(output_root=Path(directory)/'result')
        row=list(csv.DictReader(io.StringIO(written['files']['metrics_matrix.csv'].decode())))[0]
        self.assertEqual((row['cik'],row['value'],row['unit']),('1108524','72400000000','USD'))
        self.assertEqual(row['period_start'],row['period_end'])
        self.assertEqual(row['period_end'],'2026-01-31')
        self.assertEqual(written['result'],result)
        self.assertEqual(reread['result'],result)

    def test_constructed_withheld_native_trace_keeps_state_without_filled_issuer(self):
        import csv,io
        from vnext.calculator import withheld_metric_result
        from vnext import ordinary_projection as renderer
        case=deepcopy(self.cases['B12']);old=case['results']['B12']
        target=next(r['calculation_target'] for r in case['expected_records']
            if r['record_type']=='EXECUTION_TRACE' and r['trace_id']==old['trace_id'])
        fields={k:target[k] for k in ('company_id','period_start','period_end','scope','scope_key')}
        result,trace=withheld_metric_result(compiled_spec=case['compiled_specs']['B12'],
            target=fields,reason_code='CONSTRUCTED_MISSING_INPUT_TEST')
        records=[r for r in case['expected_records'] if r['record_type'] not in {'METRIC_RESULT','EXECUTION_TRACE'}]+[trace,result]
        manifest={'company_id':'marriott_international','source_references':case['references'],
            'target_period':case['target_period'],'run_id':'constructed-null-trace-test','status':'CALCULATED'}
        output=renderer.render_ordinary_records(data_root=self.root,manifest=manifest,records=records,
            case=case,receipt_status='CONSTRUCTED_TEST',source_validation='SAVED_SOURCE_CONTROL',
            prepared_annual_input=case['prepared_annual_input'])
        row=list(csv.DictReader(io.StringIO(output['files']['metrics_matrix.csv'].decode())))[0]
        self.assertEqual(row['status'],'WITHHELD')
        self.assertEqual(row['cik'],'1048286')
        self.assertEqual(row['value'],'')
        self.assertIn('CONSTRUCTED_MISSING_INPUT_TEST',row['notes'])


if __name__=='__main__':unittest.main()
