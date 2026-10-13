"""Ordinary E01 consumer controls; constructed answers have no model credit."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from vnext import historical_e01_company_case as cases
from tests.vnext.test_historical_ma_confirmation import candidate,POINTER
from vnext import historical_event_items as items


class EventItemEndSubsectionTest(TestCase):
    """Constructed layout controls, with no model or financial conclusion."""

    @staticmethod
    def source(*blocks):
        return ('<html><body>' + ''.join('<p>'+block+'</p>' for block in blocks)
                + '</body></html>').encode()

    def test_caption_and_distinct_lettered_parts_end_at_the_base_heading(self):
        for code in ('5.02', '9.01'):
            with self.subTest(code=code):
                raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body A.',
                    'Item '+code+' '+items._END_CAPTIONS[code]+'.',
                    'Item '+code+'(b) Body B.', 'Item '+code+'(d) Body D.', 'SIGNATURES')
                result = items.item_text(raw_bytes=raw, item_code='1.01')
                view = items._visible_text(raw_bytes=raw)
                self.assertEqual(view.index('Item '+code), result['end'])
                self.assertEqual(view[result['start']:result['end']], result['text'])
                self.assertEqual('NEXT_ITEM_HEADING', result['end_marker'])
                self.assertNotIn('Body B', result['text'])

    def test_unqualified_repeat_cannot_cut_off_the_acquisition_paragraph(self):
        raw = self.source('Item 8.01 Other Events. See the exhibit discussion below:',
            'Item 9.01 Exhibits are listed below.',
            'We signed an acquisition agreement with Acme.',
            'Item 9.01 Financial Statements and Exhibits.', 'SIGNATURES')
        with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE:8.01:9.01'):
            items.item_text(raw_bytes=raw, item_code='8.01')

    def test_repeated_base_or_letter_stays_ambiguous(self):
        for repeated in ('Item 5.02 Another body.', 'Item 5.02(b) Another body.'):
            with self.subTest(repeated=repeated):
                raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body.',
                    'Item 5.02 '+items._END_CAPTIONS['5.02']+'.',
                    'Item 5.02(b) First body.', repeated, 'SIGNATURES')
                with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE'):
                    items.item_text(raw_bytes=raw, item_code='1.01')

    def test_another_item_between_parts_stays_ambiguous(self):
        raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body.',
            'Item 5.02 '+items._END_CAPTIONS['5.02']+'.', 'Item 5.02(b) First body.',
            'Item 7.01 Regulation FD Disclosure. Another item.', 'Item 5.02(d) Second body.')
        with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE'):
            items.item_text(raw_bytes=raw, item_code='1.01')

    def test_text_before_a_part_is_not_just_the_known_caption(self):
        raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body.',
            'Item 5.02 '+items._END_CAPTIONS['5.02']+'. The acquisition paragraph continues.',
            'Item 5.02(b) Other body.')
        with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE'):
            items.item_text(raw_bytes=raw, item_code='1.01')

    def test_linked_or_hidden_subsections_do_not_clear_the_end(self):
        for part in ('<a href="#part">Item 5.02(b) Body.</a>',
                     '<span hidden>Item 5.02(b) Body.</span>'):
            with self.subTest(part=part):
                raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body.',
                    'Item 5.02 '+items._END_CAPTIONS['5.02']+'.', part)
                with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE'):
                    items.item_text(raw_bytes=raw, item_code='1.01')

    def test_shared_body_caption_rules_are_unchanged(self):
        self.assertNotIn('5.02', items._CAPTIONS)
        self.assertIn('5.02', items._END_CAPTIONS)

    def test_an_invisible_caption_cannot_qualify_a_repeated_end(self):
        raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body.',
            'Item 5.02 <span hidden>'+items._END_CAPTIONS['5.02']+'</span>.',
            'Item 5.02(b) Other body.')
        with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE'):
            items.item_text(raw_bytes=raw, item_code='1.01')

    def test_parts_on_opposite_sides_of_signatures_are_not_one_end(self):
        raw = self.source('Item 1.01 Entry into a Material Definitive Agreement. Body.',
            'Item 5.02 '+items._END_CAPTIONS['5.02']+'.', 'Item 5.02(b) First body.',
            'SIGNATURES', 'Item 5.02(d) An attached document.')
        with self.assertRaisesRegex(items.EventItemTextError, 'END_HEADING_NOT_UNIQUE'):
            items.item_text(raw_bytes=raw, item_code='1.01')

    def test_a_second_own_section_is_still_refused(self):
        raw = self.source('Item 8.01 Other Events. First body.',
            'Item 7.01 Regulation FD Disclosure. Other body.', 'Item 8.01 Other Events. Second body.')
        with self.assertRaisesRegex(items.EventItemTextError, 'HEADED_MORE_THAN_ONCE:8.01'):
            items.item_text(raw_bytes=raw, item_code='8.01')

    def test_hidden_selected_text_and_ambiguous_signatures_stay_refused(self):
        samples = [
            (self.source('Item 8.01 Other Events.', '<span hidden>Acquired Acme.</span>',
                         'SIGNATURES'), 'TEXT_A_READER_CANNOT_SEE'),
            (self.source('Item 8.01 Other Events. The SIGNATURE page follows.',
                         'We agreed to acquire Acme.', 'SIGNATURES'), 'END_SIGNATURES_NOT_UNIQUE')]
        for raw,reason in samples:
            with self.subTest(reason=reason), self.assertRaisesRegex(items.EventItemTextError, reason):
                items.item_text(raw_bytes=raw, item_code='8.01')

class HistoricalE01CompanyCaseTest(TestCase):
    def test_shared_dependency_check_uses_the_content_consumer_for_unresolved_windows(self):
        from tests.vnext.processing_dependency_checks import (
            processing_calls, assert_processing_calls)
        from vnext.ordinary_current_update import _configuration
        root=Path(__file__).resolve().parents[2]
        configuration=_configuration(root,'paramount_skydance_paramount_global','E01')
        scenarios=(
            ({},'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST'),
            ({'successor':True},'E01_SUCCESSOR_EVENT_WINDOW_NOT_RECEIVED'),
            ({'dependency':{'saved_status':'MISSING_SAVED_SOURCE','source_url':'constructed'}},
                'E01_REQUIRED_INCORPORATED_SOURCE_UNAVAILABLE'))
        for arguments,reason in scenarios:
            with self.subTest(reason=reason), processing_calls(root) as observed:
                case,_,_=self.prepare(**arguments)
            self.assertIsNone(case['results']['E01']['value'])
            self.assertEqual(reason,case['results']['E01']['reason_code'])
            self.assertIn('scripts/vnext/historical_e01_company_case.py',observed)
            assert_processing_calls(observed,configuration,cases.PROCESSING_FILES)
            if not arguments:
                path='scripts/vnext/historical_ma_confirmation.py'
                self.assertIn(path,observed)
                reduced=tuple(p for p in cases.PROCESSING_FILES if p!=path)
                with self.assertRaisesRegex(AssertionError,'historical_ma_confirmation.py'):
                    assert_processing_calls(observed,configuration,reduced)
        # The existing complete-walk zero fixture still uses the E01 content
        # adapter and Calculator, not the ordinary keyword-count factory.
        with processing_calls(root) as observed:
            HistoricalE01ZeroCandidateTest().test_zero_requires_the_successful_complete_candidate_walk()
        self.assertIn('scripts/vnext/historical_e01_company_case.py',observed)
        self.assertIn('calculate_observation_metric',observed['scripts/vnext/calculator.py'])
        assert_processing_calls(observed,configuration,cases.PROCESSING_FILES)

    def prepare(self, *, dependency=None, successor=False, packet_error=None, amendment_checks=None,
                source_only=False, no_candidates=False, confirmation_error=None):
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
                ('content_confirmation_candidates',{'candidates':[] if no_candidates else [item]}),
                ('strict_json_file',{'items':[] if dependency is None else [declaration]})]:
                stack.enter_context(patch.object(cases,name,return_value=value))
            walk=stack.enter_context(patch.object(cases,'read_selected_event_sources',return_value=packet,
                side_effect=packet_error))
            if confirmation_error is not None:
                stack.enter_context(patch.object(cases,'content_confirmation_candidates',
                    side_effect=confirmation_error))
            deps=stack.enter_context(patch.object(cases,'attachment_dependencies',return_value=[dependency]))
            incorporated=stack.enter_context(patch.object(cases,'prepare_incorporated_e01_input',return_value={
                'request_id':'constructed-new-request','contract':'NEW_SUPPLIED_SOURCE_CONTRACT',
                'source_proofs':[],'added_source_records':[]}))
            if source_only:
                case=cases.prepare_historical_e01_source_context(repo_root='/constructed',
                    company_id=annual['company_id'],fiscal_year=2024)
            else:
                case=cases.prepare_historical_e01_year_case(repo_root='/constructed',company_id=annual['company_id'],
                    metric_id='E01',fiscal_year=2024)
        return case,walk,incorporated

    def test_source_context_never_creates_result_or_calculates(self):
        with patch.object(cases,'calculate_observation_metric',side_effect=AssertionError('NO_CALC')), \
                patch.object(cases,'withheld_metric_result',side_effect=AssertionError('NO_RESULT')):
            context,_,_=self.prepare(source_only=True)
        self.assertTrue(context['source_graph_known'])
        self.assertFalse(context['metric_executed'])
        self.assertFalse(context['metric_result_created'])
        self.assertIsNone(context['assessment']['complete_annual_count'])
        self.assertNotIn('results',context)
        case,_,_=self.prepare()
        self.assertEqual(case['input_assessments']['e01_request'],context['request'])
        self.assertEqual(case['results']['E01']['reason_code'],context['assessment']['reason_code'])

    def test_source_context_missing_attachment_or_successor_stays_incomplete(self):
        for options in ({'successor':True}, {'dependency':{
                'saved_status':'MISSING_SAVED_SOURCE','source_url':'constructed'}}):
            with self.subTest(options=options):
                context,_,_=self.prepare(source_only=True,**options)
                self.assertFalse(context['source_graph_known'])
                self.assertIsNone(context['assessment']['complete_annual_count'])

    def test_source_context_retains_original_missing_source_error(self):
        error=ValueError('SAVED_SOURCE_MISSING:https://www.sec.gov/Archives/edgar/data/1/1/missing.htm')
        with self.assertRaisesRegex(ValueError,'SAVED_SOURCE_MISSING:.*missing.htm'):
            self.prepare(source_only=True,packet_error=error)

    def test_empty_source_candidate_walk_is_not_a_calculated_zero(self):
        with patch.object(cases,'project_event_result',side_effect=AssertionError('NO_RESULT')), \
                patch.object(cases,'calculate_observation_metric',side_effect=AssertionError('NO_CALC')):
            context,_,_=self.prepare(source_only=True,no_candidates=True)
        self.assertTrue(context['source_graph_known'])
        self.assertIsNone(context['assessment']['complete_annual_count'])
        self.assertFalse(context['metric_executed'])

    def test_collector_registers_the_same_sources_without_a_second_selector(self):
        context,_,_=self.prepare(source_only=True)
        url='https://www.sec.gov/Archives/edgar/data/813828/1/original.htm'
        context['source_records']=[{'record_type':'RAW_BLOB','raw_asset_id':'constructed',
            'media_type':'text/html'}, {'record_type':'SOURCE_REFERENCE','raw_asset_id':'constructed',
            'source_url':url,'source_role':'fy_8k_primary'}]
        context['source_proofs']=[{'source_url':url,'document_name':'original.htm','accession':'constructed'}]
        plan=SimpleNamespace(root=Path('/constructed'),company={'company_id':context['company_id']},requests={})
        def require(source_url,role,media_type,accession=''):
            plan.requests[source_url]={'source_url':source_url,'saved_status':'VERIFIED_SAVED_SOURCE',
                'roles':[role],'media_type':media_type,'accession':accession}
        plan.require=Mock(side_effect=require)
        with patch.object(cases,'prepare_historical_e01_source_context',return_value=context) as source:
            result=cases.collect_historical_e01_requirements(plan,
                prepared=context['prepared_annual_input'],period_selection={})
        self.assertTrue(result['source_graph_known'])
        self.assertIsNone(result['complete_annual_count'])
        self.assertFalse(result['metric_executed'])
        source.assert_called_once_with(repo_root=plan.root,company_id=context['company_id'],
            fiscal_year=2024,period_selection={})
        plan.require.assert_called_once_with(url,role='fy_8k_primary',media_type='text/html',accession='constructed')

    def test_collector_rejects_mismatched_selection(self):
        context,_,_=self.prepare(source_only=True)
        plan=SimpleNamespace(root=Path('/constructed'),company={'company_id':context['company_id']},requests={})
        wrong={**context['prepared_annual_input'],'entity':'999'}
        with patch.object(cases,'prepare_historical_e01_source_context',return_value=context), \
                self.assertRaisesRegex(ValueError,'SOURCE_PLAN_SELECTION_CHANGED'):
            cases.collect_historical_e01_requirements(plan,prepared=wrong)

    def test_collector_recheck_failure_keeps_the_source_url_and_is_not_ready(self):
        context,_,_=self.prepare(source_only=True)
        url='https://data.sec.gov/api/xbrl/companyfacts/CIK0000813828.json'
        context['prepared_annual_input']['companyfacts_input']={'source_url':url}
        context['source_proofs']=[{'source_url':url,'document_name':'CIK0000813828.json','accession':''}]
        plan=SimpleNamespace(root=Path('/constructed'),company={'company_id':context['company_id']},requests={})
        def fail(source_url,**kwargs):
            plan.requests[source_url]={'source_url':source_url,'saved_status':'SAVED_SOURCE_BLOCKED',
                'reason':'LATEST_SOURCE_REQUEST_FAILED'}
        plan.require=Mock(side_effect=fail)
        with patch.object(cases,'prepare_historical_e01_source_context',return_value=context):
            result=cases.collect_historical_e01_requirements(plan,prepared=context['prepared_annual_input'])
        self.assertFalse(result['source_graph_known'])
        self.assertEqual(url,result['errors'][0]['source_url'])
        self.assertEqual('LATEST_SOURCE_REQUEST_FAILED',result['errors'][0]['reason'])

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

    def test_completed_item_metadata_body_conflict_is_saved_as_withheld_not_zero(self):
        # Constructed control of the existing real Pfizer conflict. No model
        # classification or replacement of either original item number.
        reason='EVENT_ITEM_HEADED_BUT_NOT_LISTED:0001193125-23-294930:2.01'
        error=items.EventItemTextError(reason)
        with patch.object(cases,'project_event_result',side_effect=AssertionError('NO_COUNT')):
            context,_,_=self.prepare(source_only=True,confirmation_error=error)
            case,_,build=self.prepare(confirmation_error=error)
        self.assertFalse(context['source_graph_known'])
        self.assertIsNone(context['request'])
        self.assertIsNone(context['assessment']['complete_annual_count'])
        self.assertEqual(reason,context['assessment']['item_source_conflict']['reason'])
        self.assertIsNone(case['results']['E01']['value'])
        self.assertEqual('E01_ITEM_METADATA_BODY_CONFLICT',case['results']['E01']['reason_code'])
        self.assertEqual(reason,case['selection']['e01_content']['item_source_conflict']['reason'])
        build.assert_not_called()

    def test_other_item_parser_and_integrity_errors_keep_their_original_failure(self):
        for error in (items.EventItemTextError('EVENT_ITEM_HEADED_MORE_THAN_ONCE:2.01'),
                      items.EventItemTextError('EVENT_ITEM_PRIMARY_IS_ANOTHER_FILING','SOURCE_INTEGRITY_ERROR'),
                      ValueError('EVENT_ITEM_HEADED_BUT_NOT_LISTED:untyped')):
            with self.subTest(error=str(error)),self.assertRaises(type(error)) as raised:
                self.prepare(confirmation_error=error)
            self.assertIs(error,raised.exception)

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
