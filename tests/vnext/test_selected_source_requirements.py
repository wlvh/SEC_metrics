"""Small source originals/logs through the actual read-only public preflight."""
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_dei_release_selection import annual
from sec_urls import accession_directory_url, accession_document_url, companyfacts_url, submissions_url
from sec_http import parse_request_log_rows, request_log_csv_bytes, refresh_request_log_manifest
from vnext.recorded_sec_http import RecordedSecHttpClient
from vnext import selected_source_requirements as preflight
from tools.vnext_company import main

COMPANY='marriott_international';CIK=1048286


class SelectedSourceRequirementsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'sources';self.root.mkdir()
        (self.root/'config').mkdir()
        (self.root/'config/company_registry.csv').write_bytes((REPO_ROOT/'config/company_registry.csv').read_bytes())
        self.client=RecordedSecHttpClient(recorded_root=self.root, workdir=self.root,
            config_path=REPO_ROOT/'config/sec_config.json',log_path=self.root/'evidence/requests_log.csv')
        self.filings=[];self.urls={}
        for year in (2025,2024):
            filing={'form':'10-K','reportDate':f'{year}-12-31','filingDate':f'{year+1}-02-10',
                'accessionNumber':f'0001048286-{str(year+1)[2:]}-000007','primaryDocument':f'annual-{year}.htm'}
            self.filings.append(filing)
            raw=annual('http://xbrl.sec.gov/dei/2021q4').replace(b'19617',str(CIK).encode()).replace(b'2021',str(year).encode())
            # This is an intentionally constructed inline original plus a
            # separately named inline-native instance, not a company answer.
            url=accession_document_url(cik=CIK,accession=filing['accessionNumber'],document_name=filing['primaryDocument'])
            self.urls[year]=url;self.record(url,raw)
            index={'directory':{'name':'/Archives/edgar/data/'+str(CIK)+'/'+filing['accessionNumber'].replace('-',''),
                'item':[{'name':filing['primaryDocument']},{'name':f'annual-{year}_htm.xml'}]}}
            self.record(accession_directory_url(cik=CIK,accession=filing['accessionNumber']),json.dumps(index).encode())
            self.record(accession_document_url(cik=CIK,accession=filing['accessionNumber'],document_name=f'annual-{year}_htm.xml'),raw)
        self.metadata={'cik':CIK,'filings':{'recent':{k:[f[k] for f in self.filings] for k in self.filings[0]},'files':[]}}
        self.record(submissions_url(cik=CIK),json.dumps(self.metadata).encode())
        self.record(companyfacts_url(cik=CIK),json.dumps({'cik':CIK,'facts':{}}).encode())

    def record(self,url,raw,status=200,error=''):
        path=self.root/'evidence/raw'/hashlib.sha256(url.encode()).hexdigest()/url.split('/')[-1]
        with patch.object(self.client,'reply',return_value=(status,raw,{},error)):
            self.client._fetch_once(url=url,purpose='CONSTRUCTED_PREFLIGHT_TEST',local_path=path,attempt=0)

    def plan(self,metrics=('B01','B02'),**kwargs):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch('vnext.historical_annual_input.prepare_historical_annual_input',side_effect=AssertionError('No full annual preparation')), \
             patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No metric calculation')):
            return preflight.discover_selected_annual_requirements(repo_root=self.root,
                company_id=COMPANY,report_end='2025-12-31',metric_ids=list(metrics),**kwargs)

    def remove_get(self,url):
        log=self.root/'evidence/requests_log.csv'
        rows=[r for r in parse_request_log_rows(text=log.read_text()) if r['source_url']!=url]
        log.write_bytes(request_log_csv_bytes(rows=rows));refresh_request_log_manifest(workdir=self.root,log_path=log)

    def digest_tree(self):
        return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_selected_task_preserves_complete_groups_and_is_read_only_not_acceptance(self):
        before=self.digest_tree();value=self.plan()
        self.assertEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')
        self.assertEqual(value['original_annual_period'],{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'})
        self.assertEqual(value['unique_known_get_count'],8)
        self.assertEqual(len({r['source_url'] for r in value['requirements']}),8)
        self.assertFalse(value['metric_acceptance_proven']);self.assertFalse(value['fetch_authorized'])
        self.assertEqual(value['annual_period_label_source'],'RAW_ORIGINAL_DEI_CONTEXT')
        self.assertFalse(value['consumer_fiscal_year_resolution_performed'])
        self.assertEqual(value['calls'],{'provider':0,'paid':0,'sec':0})
        self.assertEqual(before,self.digest_tree())

    def test_b01_does_not_require_unused_prior_annual_sources(self):
        self.record(self.urls[2024],b'failed',503,'recorded unavailable')
        value=self.plan(('B01',));self.assertEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')
        self.assertNotIn(self.urls[2024],[r['source_url'] for r in value['requirements']])
        self.assertEqual(value['unique_known_get_count'],5)

    def test_missing_target_is_named_without_running_full_preparation(self):
        self.remove_get(self.urls[2025]);value=self.plan()
        self.assertEqual(value['status'],'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED')
        self.assertIn(self.urls[2025],value['unresolved_dependency_urls'])
        self.assertIsNone(value['original_annual_period'])
        self.assertEqual(value['filing_selection']['current_filing']['primaryDocument'],'annual-2025.htm')

    def test_absent_index_keeps_unknown_instance_frontier_and_does_not_claim_ready(self):
        index=accession_directory_url(cik=CIK,accession=self.filings[0]['accessionNumber'])
        self.remove_get(index);value=self.plan()
        self.assertIn(index,value['unresolved_dependency_urls'])
        self.assertFalse(value['complete_known_source_graph']);self.assertTrue(value['unknown_instance_frontier'])
        self.assertEqual(value['status'],'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED')

    def test_latest_failed_primary_cannot_use_old_success_or_instance_alternative(self):
        self.record(self.urls[2024],b'failure',503,'recorded failure')
        value=self.plan();item=next(r for r in value['requirements'] if r['source_url']==self.urls[2024])
        self.assertEqual(item['saved_status'],'SAVED_SOURCE_BLOCKED')
        self.assertIn('LATEST_SOURCE_REQUEST_FAILED',item['reason'])
        self.assertNotIn('alternative_dependency',item)
        self.assertIn(self.urls[2024],value['unresolved_dependency_urls'])

    def test_missing_prior_primary_accepts_complete_verified_native_context_not_a_failure(self):
        self.remove_get(self.urls[2024]);value=self.plan()
        item=next(r for r in value['requirements'] if r['source_url']==self.urls[2024])
        self.assertEqual(item['saved_status'],'MISSING_SAVED_SOURCE')
        self.assertEqual(item['alternative_dependency']['status'],'VERIFIED_PRIOR_NATIVE_INSTANCE')
        self.assertEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')
        self.assertFalse(item['alternative_dependency']['metric_executed'])

    def test_wrong_subject_period_or_facts_are_specific_limitations(self):
        original=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',b'2025')
        for raw in (original.replace(str(CIK).encode(),b'19617'),original.replace(b'2025-12-31',b'2025-09-30')):
            self.record(self.urls[2025],raw);value=self.plan()
            self.assertTrue(any(e['phase']=='ANNUAL_IDENTITY' for e in value['limitations']))
            self.assertNotEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')
        self.record(self.urls[2025],original)
        self.record(companyfacts_url(cik=CIK),b'{"cik":19617}')
        value=self.plan();self.assertTrue(any('COMPANYFACTS_ENTITY_CONFLICT' in e['reason'] for e in value['limitations']))

    def test_amendment_source_dependencies_remain_and_do_not_gain_semantic_acceptance(self):
        amendment={**self.filings[0],'form':'10-K/A','accessionNumber':'0001048286-26-000008','primaryDocument':'amendment.htm','filingDate':'2026-03-01'}
        for k in amendment:self.metadata['filings']['recent'][k].append(amendment[k])
        self.record(submissions_url(cik=CIK),json.dumps(self.metadata).encode())
        value=self.plan();url=accession_document_url(cik=CIK,accession=amendment['accessionNumber'],document_name=amendment['primaryDocument'])
        self.assertIn(url,value['unresolved_dependency_urls'])
        self.assertFalse(value['amendment_effect_on_metric_verified'])
        self.assertNotEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')

    def test_actual_public_command_returns_structured_missing_and_ready_without_writes(self):
        before=self.digest_tree()
        args=['sources','--company',COMPANY,'--source-root',str(self.root),'--report-end','2025-12-31','--metric','B01']
        with patch('sys.stdout',new_callable=io.StringIO) as output:
            code=main(args)
        value=json.loads(output.getvalue());self.assertEqual(code,0)
        self.assertEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE');self.assertEqual(before,self.digest_tree())
        self.remove_get(self.urls[2025])
        with patch('sys.stdout',new_callable=io.StringIO) as output:code=main(args)
        self.assertEqual(code,2);self.assertEqual(json.loads(output.getvalue())['status'],'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED')

    def test_non_calendar_label_is_read_from_dei_and_not_report_end_year(self):
        filing={**self.filings[0],'reportDate':'2026-01-31','filingDate':'2026-03-01'}
        rows={k:[filing[k],self.filings[1][k]] for k in filing}
        self.record(submissions_url(cik=CIK),json.dumps({'cik':CIK,'filings':{'recent':rows,'files':[]}}).encode())
        raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021-01-01',b'2025-02-01').replace(b'2021-12-31',b'2026-01-31').replace(b'>2021<',b'>2026<')
        # The issuer chooses FY2026 although its start falls in2025; this is
        # the permitted original fact, not a report-date inference.
        self.record(self.urls[2025],raw)
        value=preflight.discover_selected_annual_requirements(repo_root=self.root,company_id=COMPANY,
            report_end='2026-01-31',metric_ids=['B01'])
        self.assertEqual(value['original_annual_period'],{'fiscal_year':2026,'period_start':'2025-02-01','period_end':'2026-01-31'})
        self.assertFalse(value['fiscal_year_claimed_from_report_date'])
        raw=raw.replace(b'>2026<',b'>2025<');self.record(self.urls[2025],raw)
        value=preflight.discover_selected_annual_requirements(repo_root=self.root,company_id=COMPANY,
            report_end='2026-01-31',metric_ids=['B01'])
        self.assertEqual(value['original_annual_period']['fiscal_year'],2025)
        self.assertEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')

    def test_wrong_directory_and_metadata_subject_cannot_claim_an_available_graph(self):
        index=accession_directory_url(cik=CIK,accession=self.filings[0]['accessionNumber'])
        self.record(index,json.dumps({'directory':{'name':'/Archives/edgar/data/19617/other','item':[]}}).encode())
        value=self.plan();self.assertFalse(value['complete_known_source_graph'])
        self.assertTrue(any('DIRECTORY_IDENTITY_CHANGED' in e['reason'] for e in value['limitations']))
        self.record(submissions_url(cik=CIK),json.dumps({**self.metadata,'cik':19617}).encode())
        value=self.plan();self.assertNotEqual(value['status'],'SAVED_SOURCE_BYTES_AVAILABLE')
        self.assertIn('GOVERNANCE_SUBMISSIONS_CIK_CONFLICT',[e['reason'] for e in value['limitations'] if e['phase']=='PERIOD_METADATA'])

    def test_prior_amendment_missing_is_not_excused_by_a_valid_prior_instance(self):
        amendment={**self.filings[1],'form':'10-K/A','accessionNumber':'0001048286-25-000008','primaryDocument':'prior-amendment.htm','filingDate':'2025-03-01'}
        for k in amendment:self.metadata['filings']['recent'][k].append(amendment[k])
        self.record(submissions_url(cik=CIK),json.dumps(self.metadata).encode())
        self.remove_get(self.urls[2024]);value=self.plan()
        url=accession_document_url(cik=CIK,accession=amendment['accessionNumber'],document_name=amendment['primaryDocument'])
        self.assertIn(url,value['unresolved_dependency_urls'])
        self.assertEqual(value['status'],'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED')
        self.assertEqual(len(value['filing_selection']['prior_amendments']),1)

    def test_malformed_recorded_metadata_returns_json_exit2_and_never_a_complete_graph(self):
        args=['sources','--company',COMPANY,'--source-root',str(self.root),
              '--report-end','2025-12-31','--metric','B01']
        for payload,field in (({'cik':CIK},'filings'),
                ({'cik':CIK,'filings':{'recent':{},'files':[]}},'filingDate')):
            with self.subTest(payload=payload):
                self.record(submissions_url(cik=CIK),json.dumps(payload).encode())
                before=self.digest_tree()
                with patch('sys.stdout',new_callable=io.StringIO) as output:
                    code=main(args)
                value=json.loads(output.getvalue())
                self.assertEqual(code,2)
                self.assertEqual(value['status'],'SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED')
                self.assertFalse(value['complete_known_source_graph'])
                self.assertFalse(value['metric_acceptance_proven'])
                issue=next(e for e in value['limitations'] if e['phase']=='PERIOD_METADATA')
                self.assertEqual(issue['error_type'],'KeyError')
                self.assertEqual(issue['reason'],repr(field))
                self.assertEqual(issue['category'],'SOURCE_SCHEMA_OR_READER_ERROR')
                self.assertIn(submissions_url(cik=CIK),[r['source_url'] for r in value['requirements']])
                self.assertEqual(before,self.digest_tree())

    def test_unconnected_scope_and_invalid_date_refuse_before_discovery(self):
        with patch.object(preflight,'resolve_period_selection',side_effect=AssertionError('No discovery')):
            for metrics in ([],['D04'],['B01','B01']):
                with self.assertRaisesRegex(ValueError,'METRIC_SCOPE_NOT_CONNECTED'):
                    preflight.discover_selected_annual_requirements(repo_root=self.root,company_id=COMPANY,report_end='2025-12-31',metric_ids=metrics)
            with self.assertRaises(ValueError):
                preflight.discover_selected_annual_requirements(repo_root=self.root,company_id=COMPANY,report_end='not-a-date',metric_ids=['B01'])


if __name__=='__main__':unittest.main()
