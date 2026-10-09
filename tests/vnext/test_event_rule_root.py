"""Current event calculation from source-only originals and installed rules."""
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch
from sec_http import parse_request_log_rows,request_log_csv_bytes,refresh_request_log_manifest

from tests.vnext.common import REPO_ROOT
from vnext.normal_zero_ai_results import resolve_ordinary_zero_ai_metric
from vnext.ordinary_saved_result import create_saved_result,read_saved_result
from vnext.company_current_records import run_saved_company


class EventRuleRootTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.sources={};cls.records={};cls.candidates={}
        for company in ('marriott_international','pfizer'):
            candidate=resolve_ordinary_zero_ai_metric(repo_root=REPO_ROOT,company_id=company,metric_id='C01')
            cls.candidates[company]=candidate
            source=cls.root/company;source.mkdir();cls.sources[company]=source
            paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
            for proof in candidate['source_proofs']:
                paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
            # Keep the company's existing captured header census, including
            # out-of-window headers; never populate source with old results.
            cik=candidate['prepared_input']['entity']
            for directory in (REPO_ROOT/'evidence/accession_materials').iterdir():
                parts=directory.name.rsplit('_',2)
                if len(parts)==3 and parts[1].isdigit() and int(parts[1])==int(cik):
                    paths.update(str(p.relative_to(REPO_ROOT)) for p in directory.glob('*.hdr.sgml'))
            for relative in paths:
                target=source/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(REPO_ROOT/relative,target)
            cls.records[company]=create_saved_result(source_root=source,output_root=cls.root/(company+'-record'),
                company_id=company,metric_id='C01')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_existing_item_contract_counts_match_independent_original_headers(self):
        for company,expected in (('marriott_international',3),('pfizer',0)):
            candidate=self.candidates[company]
            headers=[p for p in candidate['source_proofs'] if p['document_name'].endswith('.hdr.sgml')
                     and p['accession'] in candidate['selection']['source_event_accessions']]
            count=sum(bool(re.search(r'(?m)^<ITEMS>\s*5\.02\s*$',
                (REPO_ROOT/p['request_repo_relative_path']).read_text())) for p in headers)
            self.assertEqual(count,expected)
            saved=self.records[company]
            self.assertEqual(saved['result']['value'],str(count))
            self.assertEqual(saved['result']['unit'],'count')
            self.assertEqual(saved['manifest']['target_period']['fiscal_year'],2025)
            self.assertEqual(saved['result']['period_start'],'2025-01-01')
            self.assertEqual(saved['result']['period_end'],'2025-12-31')
            self.assertFalse((self.sources[company]/'catalog').exists())
            self.assertFalse((self.sources[company]/'scripts').exists())

    def test_normal_company_entry_and_reentry_use_saved_source_without_install(self):
        work=self.root/'state';outputs=self.root/'outputs';company='marriott_international'
        report=run_saved_company(company_id=company,source_root=self.sources[company],work_dir=work,
            output_dir=outputs,metric_ids=['C01','E01'])
        rows={m['metric_id']:m for m in report['metrics']}
        self.assertEqual(rows['C01']['status'],'CANDIDATE_READY')
        self.assertEqual(rows['E01']['status'],'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED')
        with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No calculation')):
            repeat=run_saved_company(company_id=company,source_root=self.sources[company],work_dir=work,
                output_dir=outputs,metric_ids=['C01'])
        self.assertEqual(repeat['metrics'][0]['status'],'NO_SOURCE_CONTENT_CHANGE',repeat['metrics'])
        self.assertFalse((work/'programs').exists())
        source=self.sources[company];log=source/'evidence/requests_log.csv'
        manifest=source/'evidence/requests_log_manifest.json';old_log=log.read_bytes();old_manifest=manifest.read_bytes()
        pointer=work/'updates/C01/current-result.json';old_pointer=pointer.read_bytes()
        url=next(p['source_url'] for p in self.candidates[company]['source_proofs']
                 if p['document_name'].endswith('.hdr.sgml'))
        rows=parse_request_log_rows(text=old_log.decode())
        failed={**next(r for r in rows if r['source_url']==url),'status_code':'503',
                'error':'recorded current-check failure','timestamp_utc':'2026-10-07T01:00:00Z'}
        log.write_bytes(request_log_csv_bytes(rows=[*rows,failed]))
        refresh_request_log_manifest(log_path=log,workdir=source)
        try:
            with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No fallback calculation')):
                failed_report=run_saved_company(company_id=company,source_root=source,work_dir=work,
                    output_dir=outputs,metric_ids=['C01'])
            self.assertEqual(failed_report['metrics'][0]['status'],'INPUT_OR_EXECUTION_FAILED')
            self.assertIn('LATEST_SOURCE_REQUEST_FAILED',failed_report['metrics'][0]['reason'])
            self.assertEqual(pointer.read_bytes(),old_pointer)
        finally:log.write_bytes(old_log);manifest.write_bytes(old_manifest)

    def test_missing_event_body_cannot_turn_into_smaller_complete_count(self):
        candidate=self.candidates['marriott_international'];source=self.sources['marriott_international']
        proof=next(p for p in candidate['source_proofs'] if p['source_url'].endswith('.hdr.sgml')
            and p['accession'] in candidate['selection']['source_event_accessions'])
        path=source/proof['request_repo_relative_path'];raw=path.read_bytes();path.unlink()
        try:
            saved=create_saved_result(source_root=source,output_root=self.root/'missing',
                company_id='marriott_international',metric_id='C01')
            self.assertEqual(saved['result']['publication'],'WITHHELD')
            self.assertIsNone(saved['result']['value'])
        finally:path.write_bytes(raw)

    def test_independent_read_has_no_selection_or_calculation(self):
        with patch('vnext.ordinary_saved_result.prepare_ordinary_zero_ai_run_input',side_effect=AssertionError('No prepare')):
            for company in self.sources:
                saved=read_saved_result(output_root=self.root/(company+'-record'))
                self.assertEqual(saved['result']['result_id'],self.records[company]['result']['result_id'])

    def test_explicit_current_rules_cannot_grant_old_e01_item_count_new_credit(self):
        with self.assertRaisesRegex(ValueError,'E01_CONTENT_CONFIRMED_ROUTE_REQUIRED'):
            resolve_ordinary_zero_ai_metric(repo_root=self.sources['marriott_international'],
                company_id='marriott_international',metric_id='E01',rules_root=REPO_ROOT)

if __name__=='__main__':unittest.main()
