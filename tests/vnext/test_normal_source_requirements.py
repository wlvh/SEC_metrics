"""Source discovery uses original requests, including real failure and drift."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from sec_urls import accession_document_url
from vnext.normal_annual_input import _registry_rows
from vnext.normal_source_requirements import (
    discover_saved_source_requirements,inspect_source_requirements,_instance_names,
    _declared_selection,SourceRequirementsError)


class OrdinarySourceRequirementsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.cases={c:discover_saved_source_requirements(repo_root=ROOT,company_id=c)
                       for c in ('marriott_international','salesforce','jpmorgan_chase')}
        cls.marriott=cls.cases['marriott_international']
        cls.company=next(c for c in _registry_rows(repo_root=ROOT) if c['company_id']=='marriott_international')

    def copied_sources(self,root):
        paths={'config/company_registry.csv','config/normal_fiscal_year_labels_v1.json',
               'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for r in self.marriott['requirements']:
            if 'proof' in r:
                paths.update(r['proof'][k] for k in ('request_repo_relative_path','request_headers_repo_relative_path'))
        for relative in paths:
            target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,target)

    def test_actual_sources_keep_requests_unique_and_do_not_claim_freshness_or_execution(self):
        self.assertEqual('SAVED_SOURCE_DEPENDENCIES_AVAILABLE',self.marriott['status'])
        self.assertEqual(29,self.marriott['unique_known_get_count'])
        self.assertTrue(self.marriott['complete_new_source_graph_known'])
        for case in self.cases.values():
            urls=[r['source_url'] for r in case['requirements']]
            self.assertEqual(len(urls),len(set(urls)))
            self.assertEqual({'provider':0,'paid':0,'sec':0},case['calls'])
            for field in ('current_sec_freshness_proven','fetch_authorized','source_acquisition_credit',
                          'metric_executed','production_authorized','all_39_metric_source_acceptance_proven'):
                self.assertFalse(case[field])

    def test_real_snapshot_conflict_requires_refresh_without_inventing_a_complete_inventory(self):
        case=self.cases['jpmorgan_chase']
        self.assertEqual('METADATA_REFRESH_REQUIRED',case['status'])
        self.assertTrue(case['metadata']['history_conflicts'])
        self.assertIsNone(case['filing_selection'])
        self.assertFalse(case['complete_new_source_graph_known'])
        self.assertEqual(9,len(case['new_discovery_dataset_urls']))

    def test_real_final_failed_get_is_not_replaced_by_an_older_success(self):
        case=self.cases['salesforce']
        failed=[r for r in case['requirements'] if r['saved_status']=='SAVED_SOURCE_BLOCKED']
        self.assertEqual(1,len(failed))
        self.assertTrue(failed[0]['source_url'].endswith('/0001108524-25-000083.hdr.sgml'))
        self.assertIn('LATEST_SOURCE_REQUEST_FAILED',failed[0]['reason'])
        self.assertIn(failed[0]['source_url'],case['missing_or_failed_source_urls'])
        self.assertTrue(case['complete_new_source_graph_known'])
        self.assertEqual('SOURCE_DEPENDENCIES_UNRESOLVED',case['status'])

    def test_missing_primary_is_still_discovered_before_annual_preparation(self):
        primary=next(r for r in self.marriott['requirements'] if 'current_annual_primary' in r['roles'])
        with tempfile.TemporaryDirectory(prefix='ordinary-discovery-primary-') as tmp:
            root=Path(tmp);self.copied_sources(root)
            (root/primary['proof']['request_repo_relative_path']).unlink()
            with original_sources_only():case=discover_saved_source_requirements(repo_root=root,company_id=self.company['company_id'])
            self.assertEqual(self.marriott['metadata_declared_annual_selection'],case['metadata_declared_annual_selection'])
            self.assertIn(primary['source_url'],case['missing_or_failed_source_urls'])
            self.assertIsNone(case['prepared_annual_input'])
            self.assertFalse(case['annual_source_identity_verified'])
            self.assertFalse(case['complete_new_source_graph_known'])

    def test_missing_index_preserves_an_unknown_instance_frontier(self):
        index=next(r for r in self.marriott['requirements'] if 'annual_accession_index' in r['roles'])
        with tempfile.TemporaryDirectory(prefix='ordinary-discovery-index-') as tmp:
            root=Path(tmp);self.copied_sources(root)
            (root/index['proof']['request_repo_relative_path']).unlink()
            with original_sources_only():case=discover_saved_source_requirements(repo_root=root,company_id=self.company['company_id'])
            self.assertTrue(case['metadata']['complete_filing_inventory_proven'])
            self.assertFalse(case['complete_new_source_graph_known'])
            self.assertIn(index['source_url'],case['missing_or_failed_source_urls'])
            self.assertTrue(any(r['reason']=='INSTANCE_DOCUMENT_NAMES_NOT_YET_DISCOVERED' for r in case['limitations']))

    def test_new_metadata_names_new_primary_without_a_saved_answer_or_body(self):
        # This is a pure metadata parser counterexample, not trusted acquisition.
        source=next(r for r in self.marriott['requirements'] if 'sec_submissions_inventory' in r['roles'])
        payload=json.loads((ROOT/source['proof']['request_repo_relative_path']).read_text())
        block=payload['filings']['recent'];i=next(i for i,f in enumerate(block['form']) if f=='10-K')
        block['reportDate'][i]='2026-12-31';block['filingDate'][i]='2027-02-10'
        block['accessionNumber'][i]='0001048286-27-000010';block['primaryDocument'][i]='future-20261231.htm'
        filing=_declared_selection(payload,self.company)['filing']
        self.assertEqual('future-20261231.htm',filing['primaryDocument'])
        self.assertTrue(accession_document_url(cik=int(self.company['primary_cik']),accession=filing['accessionNumber'],
            document_name=filing['primaryDocument']).endswith('/000104828627000010/future-20261231.htm'))

    def test_malformed_directory_wrong_identity_and_unsafe_names_cannot_hide_the_frontier(self):
        filing=self.marriott['filing_selection']['ordinary']
        index=next(r for r in self.marriott['requirements'] if 'annual_accession_index' in r['roles'] and r['accession']==filing['accessionNumber'])
        payload=json.loads((ROOT/index['proof']['request_repo_relative_path']).read_text())
        self.assertTrue(_instance_names(payload,self.company,filing))
        wrong=copy.deepcopy(payload);wrong['directory']['name']='/Archives/edgar/data/1/wrong'
        unsafe=copy.deepcopy(payload);unsafe['directory']['item'].append({'name':'../outside.xml'})
        duplicate=copy.deepcopy(payload);duplicate['directory']['item'].append(duplicate['directory']['item'][0])
        for value in ({},[],{'directory':None},{'directory':{}},wrong,unsafe,duplicate):
            with self.subTest(value=str(value)[:50]),self.assertRaises(SourceRequirementsError):
                _instance_names(value,self.company,filing)

    def test_changed_saved_body_has_no_import_or_complete_graph_credit(self):
        index=next(r for r in self.marriott['requirements'] if 'annual_accession_index' in r['roles'])
        with tempfile.TemporaryDirectory(prefix='ordinary-discovery-tamper-') as tmp:
            root=Path(tmp);self.copied_sources(root)
            path=root/index['proof']['request_repo_relative_path'];path.write_bytes(path.read_bytes()+b' ')
            with original_sources_only():case=discover_saved_source_requirements(repo_root=root,company_id=self.company['company_id'])
            row=next(r for r in case['requirements'] if r['source_url']==index['source_url'])
            self.assertEqual('SAVED_SOURCE_BLOCKED',row['saved_status'])
            self.assertFalse(case['complete_new_source_graph_known'])


if __name__=='__main__':unittest.main()
