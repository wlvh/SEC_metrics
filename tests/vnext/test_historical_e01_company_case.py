"""Ordinary E01 consumer controls; constructed answers have no model credit."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from vnext import historical_e01_company_case as cases
from tests.vnext.test_historical_ma_confirmation import candidate,POINTER

class HistoricalE01CompanyCaseTest(TestCase):
    def prepare(self, *, dependency=None, successor=False, packet_error=None, amendment_checks=None):
        annual={'company_id':'paramount_skydance_paramount_global','entity':'813828',
            'filing':{'accessionNumber':'constructed'},'amendments':[],
            'subject_policy':{'mode':'SUCCESSOR_REGISTRANT_ONLY' if successor else 'CONTINUOUS_PRIMARY'},
            'table_input':{'target_period':{'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}},'source_proofs':[]}
        item=candidate(POINTER,accession='0000813828-24-000018',code='8.01',start=2224)
        packet={'claims':[],'source_records':[],'source_proofs':[],
                'filings':[],'source_set_manifests':[]}
        declaration={'company_id':annual['company_id'],'report_end':'2024-12-31',
            'parent_url':'https://www.sec.gov/Archives/edgar/data/813828/000081382824000018/para-20240429.htm',
            'accession':item['accession']}
        reader=SimpleNamespace(primary=Mock(),records={},proofs={})
        with ExitStack() as stack:
            for name,value in [('resolve_period_selection',{}),('prepare_historical_annual_input',annual),
                ('_Sources',reader),('_event_amendment_checks',amendment_checks or []),('verify_ordinary_source_proofs',{}),
                ('content_confirmation_candidates',{'candidates':[item]}),
                ('strict_json_file',{'items':[] if dependency is None else [declaration]})]:
                stack.enter_context(patch.object(cases,name,return_value=value))
            walk=stack.enter_context(patch.object(cases,'read_selected_event_sources',return_value=packet,
                side_effect=packet_error))
            deps=stack.enter_context(patch.object(cases,'attachment_dependencies',return_value=[dependency]))
            incorporated=stack.enter_context(patch.object(cases,'prepare_incorporated_e01_input',return_value={
                'request_id':'constructed-new-request','contract':'NEW_SUPPLIED_SOURCE_CONTRACT',
                'source_proofs':[],'added_source_records':[]}))
            case=cases.prepare_historical_e01_year_case(repo_root='/constructed',company_id=annual['company_id'],
                metric_id='E01',fiscal_year=2024)
        return case,walk,incorporated

    def test_no_matching_response_is_whole_window_withheld_not_old_item_count(self):
        case,_,_=self.prepare()
        self.assertIsNone(case['results']['E01']['value'])
        a=case['input_assessments']['e01_content']
        self.assertEqual('E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST',a['reason_code'])
        self.assertIsNone(a['complete_annual_count'])
        self.assertFalse(a['old_answer_reused']);self.assertFalse(a['partial_count_exported'])
        self.assertEqual(['0000813828-24-000018#8.01@2224'],a['candidate_item_ids'])

    def test_missing_declared_attachment_has_exact_dependency_and_no_answer_reuse(self):
        dep={'saved_status':'MISSING_SAVED_SOURCE','source_url':'https://www.sec.gov/Archives/edgar/data/813828/000081382824000018/ex-99.htm'}
        case,_,build=self.prepare(dependency=dep);build.assert_not_called()
        a=case['input_assessments']['e01_content'];self.assertEqual([dep],a['attachment_dependencies'])
        self.assertEqual('E01_REQUIRED_INCORPORATED_SOURCE_UNAVAILABLE',a['reason_code'])
        self.assertIsNone(case['results']['E01']['value'])

    def test_saved_attachment_changes_request_contract_but_not_into_model_success(self):
        dep={'saved_status':'VERIFIED_SAVED_SOURCE','source_url':'constructed-saved-attachment'}
        case,_,build=self.prepare(dependency=dep);build.assert_called_once()
        a=case['input_assessments']['e01_content'];self.assertEqual('constructed-new-request',a['request_id'])
        self.assertEqual('NEW_SUPPLIED_SOURCE_CONTRACT',a['request_contract'])
        self.assertFalse(a['matching_response_available']);self.assertFalse(a['target_model_execution_authorized'])
        self.assertIsNone(case['results']['E01']['value'])

    def test_successor_cannot_borrow_the_other_event_familys_wide_window(self):
        case,walk,build=self.prepare(successor=True);walk.assert_not_called();build.assert_not_called()
        self.assertEqual('E01_SUCCESSOR_EVENT_WINDOW_NOT_RECEIVED',case['results']['E01']['reason_code'])
        self.assertEqual('2024-01-01',case['target_period']['period_start'])

    def test_source_error_is_not_no_candidate_or_zero(self):
        with self.assertRaisesRegex(ValueError,'MISSING_EVENT_HEADER'):
            self.prepare(packet_error=ValueError('MISSING_EVENT_HEADER'))

    def test_display_summary_keeps_amendment_conclusion_and_full_evidence_separate(self):
        source={'filing':{'accessionNumber':'constructed'},'period':{'period_end':'2024-12-31'},
                'raw_sha256':'1'*64,'source_reference':{'source_reference_id':'constructed-reference'},
                'document':{'text':'constructed original text '*10000}}
        check={'scope_id':'constructed-scope','classification':'CONSTRUCTED_UNCHANGED_EVENT_WINDOW',
               'fiscal_window_unchanged':True,'unchanged_input_classes':['FISCAL_EVENT_WINDOW'],
               'issues':[],'original':source,'amendment':source}
        case,_,_=self.prepare(amendment_checks=[check])
        self.assertEqual(check,case['input_assessments']['e01_content']['annual_amendment_checks'][0])
        summary=case['selection']['e01_content']['annual_amendment_checks'][0]
        self.assertEqual(check['scope_id'],summary['scope_id'])
        self.assertTrue(summary['fiscal_window_unchanged'])
        self.assertEqual(['FISCAL_EVENT_WINDOW'],summary['unchanged_input_classes'])
        self.assertNotIn('document',summary['original'])
        self.assertEqual(source['source_reference'],summary['original']['source_reference'])

    def test_declared_dependencies_include_the_used_event_and_amendment_rules(self):
        from vnext.historical_event_cases import PROCESSING_FILES as event_files
        self.assertTrue(set(event_files) <= set(cases.PROCESSING_FILES))
        self.assertEqual(len(cases.PROCESSING_FILES),len(set(cases.PROCESSING_FILES)))
        self.assertTrue(all((cases.ROOT/path).is_file() for path in cases.PROCESSING_FILES))
        self.assertIn('config/annual_amendment_scope_v1.json',cases.PROCESSING_FILES)
        self.assertIn('scripts/vnext/normal_zero_ai_results.py',cases.PROCESSING_FILES)

    def test_wrong_family_refuses_before_source_selection(self):
        with patch.object(cases,'resolve_period_selection') as select:
            with self.assertRaisesRegex(ValueError,'FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_e01_year_case(repo_root='/constructed',company_id='example',
                    metric_id='E02',fiscal_year=2024)
        select.assert_not_called()

class HistoricalE01ZeroCandidateTest(TestCase):
    def test_zero_requires_the_successful_complete_candidate_walk(self):
        from vnext.observations import structured_observation,scope_key
        period={'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}
        annual={'company_id':'paramount_skydance_paramount_global','entity':'813828',
            'filing':{'accessionNumber':'constructed'},'amendments':[],
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},'table_input':{'target_period':period},'source_proofs':[]}
        scope={'coverage':'fiscal_year_source_set','fiscal_year':2024,'shared_claim_group_id':'merger_acquisition_items'}
        observation=structured_observation(metric_id='E01',semantic_role='event_count',
            company_id=annual['company_id'],period_start=period['period_start'],period_end=period['period_end'],
            scope=scope,value='0',unit='count',quality='EXACT',source_binding={
                'raw_asset_id':'sha256:'+'1'*64,'source_reference_id':'sha256:'+'2'*64,
                'accession':'constructed','document_name':'constructed.hdr','source_role':'fy_8k_header'})
        packet={'claims':[],'source_records':[],'source_proofs':[],'filings':[],
            'source_set_manifests':[{'source_role':'fy_8k_item_inventory'}],
            'inventory_source_reference':{'source_role':'sec_submissions_inventory'}}
        reader=SimpleNamespace(primary=Mock(),records={},proofs={})
        with ExitStack() as stack:
            for name,value in [('resolve_period_selection',{}),('prepare_historical_annual_input',annual),
                ('_Sources',reader),('_event_amendment_checks',[]),('verify_ordinary_source_proofs',{}),
                ('read_selected_event_sources',packet),('content_confirmation_candidates',{'candidates':[]}),
                ('project_event_result',{'observation':observation})]:
                stack.enter_context(patch.object(cases,name,return_value=value))
            request=stack.enter_context(patch.object(cases,'confirmation_request'))
            result=cases.prepare_historical_e01_year_case(repo_root='/constructed',
                company_id=annual['company_id'],metric_id='E01',fiscal_year=2024)
        request.assert_not_called()
        self.assertEqual('0',result['results']['E01']['value'])
        self.assertEqual('NO_CANDIDATE_ITEM',result['input_assessments']['e01_content']['status'])
        self.assertIsNone(result['input_assessments']['e01_request'])
