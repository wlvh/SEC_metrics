"""Formal sources dispatch, source states and retained financial preflight behavior."""
from contextlib import redirect_stdout
import io,json
from pathlib import Path
import unittest
import socket,hashlib
from unittest.mock import patch
from tools.vnext_company import main
from vnext import selected_source_requirements as preflight
from tests.vnext import test_selected_source_requirements as source_fixture
from sec_urls import companyfacts_url

class CompanyEventSourceDispatchTest(unittest.TestCase):
    def test_formal_sources_accepts_e01_and_preserves_unresolved_source_status(self):
        # Only dispatch is isolated here; this is not a successful source read.
        result={'status':'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED','metric_ids':['E01'],
                'complete_known_source_graph':False,'limitations':[{'reason':'MISSING_ORIGINAL'}]}
        stream=io.StringIO()
        with patch.object(preflight,'discover_selected_source_requirements',return_value=result,create=True) as discover, \
             patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No calculation')),redirect_stdout(stream):
            rc=main(['sources','--company','southwest_airlines','--source-root','/explicit/saved-sources',
                     '--report-end','2024-12-31','--metric','E01'])
        self.assertEqual(rc,2)
        emitted=json.loads(stream.getvalue());emitted.pop('elapsed_seconds')
        self.assertEqual(emitted,result)
        discover.assert_called_once_with(repo_root=Path('/explicit/saved-sources'),company_id='southwest_airlines',
            report_end='2024-12-31',metric_ids=['E01'])

    def test_unselected_event_metric_keeps_exact_annual_result(self):
        source={'status':'SAVED_SOURCE_BYTES_AVAILABLE','requirements_id':'unchanged'}
        with patch.object(preflight,'discover_selected_annual_requirements',return_value=source) as annual:
            observed=preflight.discover_selected_source_requirements(repo_root=Path('/saved'),
                company_id='marriott_international',report_end='2025-12-31',metric_ids=['B01','B02'])
        self.assertIs(observed,source)
        annual.assert_called_once_with(repo_root=Path('/saved'),company_id='marriott_international',
            report_end='2025-12-31',metric_ids=['B01','B02'])


class MixedEventSourceStateTest(unittest.TestCase):
    setUp = source_fixture.SelectedSourceRequirementsTest.setUp
    record = source_fixture.SelectedSourceRequirementsTest.record

    def event_plan(self,*,metrics,graph,errors=(),reporting_entity='1048286',source_hook=None):
        # Source-shape dispatch only: no claim of successful historical input.
        annual={'company_id':'marriott_international','entity':reporting_entity,
            'filing':self.filings[0],'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},
            'table_input':{'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}}}
        event={'source_graph_known':graph,'errors':list(errors),'event_window':annual['table_input']['target_period'],
               'matching_response_available':False,'complete_annual_count':None,'metric_executed':False}
        def collect_sources(plan,**kwargs):
            if source_hook is not None:
                source_hook(plan)
            return event
        with patch('vnext.historical_annual_input.prepare_historical_annual_input',return_value=annual), \
             patch('vnext.historical_e01_company_case.collect_historical_e01_requirements',side_effect=collect_sources,create=True) as collect, \
             patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No calculation')):
            result=preflight.discover_selected_source_requirements(repo_root=self.root,
                company_id='marriott_international',report_end='2025-12-31',metric_ids=metrics)
            self.assertEqual(collect.call_args.args[0].company['primary_cik'],'1048286')
            return result

    def test_selected_predecessor_does_not_replace_the_registered_primary_catalog(self):
        self.event_plan(metrics=['E01'],graph=False,reporting_entity='813828')

    def test_same_companyfacts_bytes_with_different_filing_context_can_be_shared(self):
        url=companyfacts_url(cik=source_fixture.CIK)
        def event_source(plan):
            plan.require(url,'selected_event_fiscal_label','application/json',self.filings[0]['accessionNumber'])
        result=self.event_plan(metrics=['B01','E01'],graph=True,source_hook=event_source)
        self.assertEqual(result['status'],'SAVED_SOURCE_BYTES_AVAILABLE')
        shared=next(r for r in result['requirements'] if r['source_url']==url)
        annual=next(r for r in result['component_source_plans'][0]['requirements'] if r['source_url']==url)
        self.assertEqual(shared['proof']['accession'],self.filings[0]['accessionNumber'])
        self.assertEqual(annual['proof']['accession'],'')
        self.assertEqual(shared['proof']['content_sha256'],annual['proof']['content_sha256'])

    def test_companyfacts_context_exception_does_not_hide_different_source_bytes(self):
        url=companyfacts_url(cik=source_fixture.CIK)
        def changed_source(plan):
            plan.require(url,'selected_event_fiscal_label','application/json',self.filings[0]['accessionNumber'])
            plan.requests[url]['proof']['content_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'COMPONENT_SOURCE_OBSERVATION_CHANGED'):
            self.event_plan(metrics=['B01','E01'],graph=True,source_hook=changed_source)

    def test_filing_documents_do_not_gain_the_aggregate_context_exception(self):
        common={'source_url':self.urls[2025],'content_sha256':'1'*64,
                'accession':self.filings[0]['accessionNumber']}
        self.assertFalse(preflight._component_source_observation_matches(common,
            {**common,'accession':''},facts_url=companyfacts_url(cik=source_fixture.CIK)))

    def test_unknown_event_graph_preserves_the_ready_annual_component(self):
        result=self.event_plan(metrics=['B01','E01'],graph=False,
            errors=[{'phase':'EVENT_WINDOW','reason':'MISSING_HISTORY_ORIGINAL','source_url':'https://example.invalid/known-missing'}])
        self.assertEqual('SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED',result['status'])
        self.assertFalse(result['complete_known_source_graph'])
        self.assertEqual('SAVED_SOURCE_BYTES_AVAILABLE',result['component_source_plans'][0]['status'])
        self.assertIn('MISSING_HISTORY_ORIGINAL',[e['reason'] for e in result['limitations']])
        self.assertIn('https://example.invalid/known-missing',result['unresolved_dependency_urls'])
        self.assertFalse(result['metric_executed']);self.assertFalse(result['fetch_authorized'])
        self.assertIsNone(result['event_source_context']['complete_annual_count'])

    def test_event_only_does_not_run_the_financial_preflight(self):
        with patch.object(preflight,'discover_selected_annual_requirements',side_effect=AssertionError('Not a financial task')):
            result=self.event_plan(metrics=['E01'],graph=False)
        self.assertEqual([],result['component_source_plans'])
        self.assertFalse(result['complete_known_source_graph'])

    def test_unregistered_failed_event_keeps_its_actual_attempt_without_fake_proof(self):
        from sec_urls import accession_document_url
        accession='0001048286-26-000011'
        url=accession_document_url(cik=source_fixture.CIK,accession=accession,document_name='event.htm')
        self.record(url,b'<html><body>Earlier recorded event</body></html>')
        self.record(url,b'recorded event failure',503,'recorded event failure')
        def direct_read(plan):
            plan.reader.read(url,accession=accession,role='event_original',media_type='text/html')
        result=self.event_plan(metrics=['E01'],graph=True,source_hook=direct_read)
        self.assertIn(url,result['unresolved_dependency_urls'])
        problem=next(p for p in result['limitations'] if p.get('source_url')==url)
        self.assertEqual(problem['failed_request']['status_code'],'503')
        self.assertEqual(problem['failed_request']['error'],'recorded event failure')
        self.assertFalse(result['complete_known_source_graph'])
        self.assertFalse(any(r['source_url']==url for r in result['requirements']))

    def test_a_source_graph_does_not_claim_model_or_metric_acceptance(self):
        result=self.event_plan(metrics=['E01'],graph=True)
        self.assertEqual('SAVED_SOURCE_BYTES_AVAILABLE',result['status'])
        self.assertFalse(result['metric_acceptance_proven']);self.assertFalse(result['metric_executed'])
        self.assertIsNone(result['event_source_context']['complete_annual_count'])


class FailedEventSourceObservationTest(unittest.TestCase):
    setUp=source_fixture.SelectedSourceRequirementsTest.setUp
    record=source_fixture.SelectedSourceRequirementsTest.record

    def formal(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}
        stream=io.StringIO()
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No calculation')), \
             redirect_stdout(stream):
            rc=main(['sources','--company',source_fixture.COMPANY,'--source-root',str(self.root),
                '--report-end','2025-12-31','--metric','E01'])
        self.assertEqual(rc,2)
        self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.root.rglob('*') if p.is_file()})
        return json.loads(stream.getvalue())

    def test_latest_failed_companyfacts_before_plan_registration_keeps_exact_url(self):
        url=companyfacts_url(cik=source_fixture.CIK)
        self.record(url,b'recorded failure',503,'recorded CF failure')
        result=self.formal()
        self.assertIn(url,result['unresolved_dependency_urls'])
        problem=next(p for p in result['limitations'] if p.get('source_url')==url)
        self.assertEqual(problem['category'],'SOURCE_ACCESS_FAILED')
        self.assertEqual(problem['failed_request']['status_code'],'503')
        self.assertEqual(problem['failed_request']['error'],'recorded CF failure')
        self.assertTrue(problem['failed_request']['request_attempt_id'])
        self.assertFalse(result['complete_known_source_graph'])
        self.assertFalse(result['metric_executed']);self.assertFalse(result['fetch_authorized'])
        self.assertNotIn('results',result)

    def test_failed_observation_uses_the_actual_latest_get(self):
        url=companyfacts_url(cik=source_fixture.CIK)
        self.record(url,b'older failure',503,'older CF failure')
        self.record(url,b'latest failure',404,'latest CF failure')
        result=self.formal()
        problem=next(p for p in result['limitations'] if p.get('source_url')==url)
        self.assertEqual(problem['failed_request']['status_code'],'404')
        self.assertEqual(problem['failed_request']['error'],'latest CF failure')

    def test_unrelated_reader_error_does_not_invent_a_source_url(self):
        with patch('vnext.historical_annual_input.prepare_historical_annual_input',
                   side_effect=ValueError('CONSTRUCTED_READER_CONFLICT:no source url')):
            result=self.formal()
        problem=next(p for p in result['limitations'] if p['phase']=='E01_SELECTED_SOURCE')
        self.assertNotIn('source_url',problem)
        self.assertNotIn('failed_request',problem)
