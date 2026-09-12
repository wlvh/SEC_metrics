"""Ordinary catalog formulas return to actual source values and periods."""
import copy
from decimal import Decimal, localcontext
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.batch_workflow import BatchWorkflowError
from vnext.canonical import content_hash
from vnext.normal_annual_input import _registry_rows
from vnext.normal_companyfacts_results import (
    resolve_ordinary_companyfacts_metrics, verify_ordinary_companyfacts_metrics, NormalCompanyfactsError)
from vnext.records import validate_record


def copy_sources(candidate, target):
    paths = set(candidate['authority_file_hashes']) | {'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
    for proof in candidate['source_proofs']:
        paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
    for path in paths:
        destination = target/path
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/path,destination)


class OrdinaryCompanyfactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.cases = {company['company_id']:resolve_ordinary_companyfacts_metrics(
                repo_root=ROOT,company_id=company['company_id']) for company in _registry_rows(repo_root=ROOT)}

    def test_ten_companies_keep_all_eleven_coordinates_with_valid_native_records(self):
        self.assertEqual(10,len(self.cases))
        metrics = {'A05','A06','A07','A08','A10','B02','B04','B05','B07','B08','B09'}
        for company,case in self.cases.items():
            with self.subTest(company=company):
                self.assertEqual(metrics,set(case['metrics']))
                self.assertEqual('NOT_CREATED',case['native_run_status'])
                self.assertEqual({'provider':0,'paid':0,'sec':0},case['calls'])
                self.assertFalse(case['production_authorized'])
                self.assertFalse(case['current_latest_verified'])
                for row in case['metrics'].values():
                    for record in row['records']:validate_record(record=record)
                    self.assertEqual(row['trace']['trace_id'],row['result']['trace_id'])
                    if row['result']['publication']=='WITHHELD':
                        self.assertIsNone(row['result']['value'])
                        self.assertTrue(row['selection']['reason'])
                    if row['result']['applicability']=='N_A_STRUCTURAL':
                        self.assertEqual([],row['claims'])
                        self.assertEqual([],row['observations'])

    def test_every_selected_claim_returns_to_its_original_accession_value_unit_and_period(self):
        for company,case in self.cases.items():
            raw=json.loads((ROOT/case['prepared_input']['companyfacts_input']['source_repo_relative_path']).read_text())
            for metric,row in case['metrics'].items():
                for claim in row['claims']:
                    name=claim['locator']['concept']
                    candidates=raw['facts']['us-gaap'][name]['units'][claim['unit']]
                    matches=[f for f in candidates if f['accn']==claim['attributes']['accession']
                        and f.get('start',f['end'])==claim['locator']['period_start']
                        and f['end']==claim['locator']['period_end'] and f['form']=='10-K' and f.get('fp')=='FY']
                    with self.subTest(company=company,metric=metric,concept=name):
                        self.assertTrue(matches)
                        self.assertEqual({Decimal(claim['value'])},{Decimal(str(f['val'])) for f in matches})

    def test_current_and_prior_math_is_independent_of_old_matrix_answers(self):
        case=self.cases['marriott_international']
        self.assertEqual('2024-01-01',case['periods']['prior']['period_start'])
        self.assertEqual('2024-12-31',case['periods']['prior']['period_end'])
        with localcontext() as context:
            context.prec=28
            expected={'B02':(Decimal(26186000000)-Decimal(25100000000))/Decimal(25100000000),
                'B04':Decimal(2601000000),'B05':Decimal(3212000000)-Decimal(604000000),
                'B07':Decimal(4141000000)/Decimal(809000000),
                'B08':Decimal(3584000000)/Decimal(8398000000),'B09':Decimal(358000000)}
        for metric,value in expected.items():
            self.assertEqual(value,Decimal(case['metrics'][metric]['result']['value']))
        self.assertNotEqual(case['metrics']['B02']['claims'][0]['attributes']['accession'],
                            case['metrics']['B02']['claims'][1]['attributes']['accession'])

    def test_native_prior_instances_and_actual_noncalendar_periods_are_used(self):
        for company,prior_start,prior_end in [('macys','2024-02-04','2025-02-01'),
                                             ('salesforce','2024-02-01','2025-01-31')]:
            case=self.cases[company]
            self.assertIsNone(case['prior_error'])
            self.assertEqual(prior_start,case['periods']['prior']['period_start'])
            self.assertEqual(prior_end,case['periods']['prior']['period_end'])
            self.assertTrue(any(r['record_type']=='SOURCE_REFERENCE' and r['accession']==case['filings']['prior']['accessionNumber']
                and r['document_name'].endswith('.xml') for r in case['source_records']))
            self.assertEqual('PUBLISHED',case['metrics']['B02']['result']['publication'])
            for metric in ('B08','B09'):
                self.assertEqual('2026-01-31',case['metrics'][metric]['result']['period_start'])
                self.assertEqual('2026-01-31',case['metrics'][metric]['result']['period_end'])

    def test_prior_conflict_is_not_spread_to_current_only_metrics_or_silently_ignored(self):
        case=self.cases['jpmorgan_chase']
        self.assertIn('HISTORY_SNAPSHOT_CONFLICT',case['prior_error']['reason'])
        for metric in ('A05','A06','A07'):
            self.assertEqual('WITHHELD',case['metrics'][metric]['result']['publication'])
        for metric in ('A08','A10'):
            self.assertEqual('PUBLISHED',case['metrics'][metric]['result']['publication'])
        southwest=self.cases['southwest_airlines']
        self.assertEqual('PUBLISHED',southwest['metrics']['B02']['result']['publication'])
        self.assertEqual('INPUT_PROPERTY_PROVEN',southwest['amendment_input']['decision'])
        self.assertIsNone(southwest['prior_error'])
        for company in ('paramount_skydance_paramount_global',):
            self.assertEqual('WITHHELD',self.cases[company]['metrics']['B02']['result']['publication'])
            self.assertEqual('N_A_STRUCTURAL',self.cases[company]['metrics']['A05']['result']['applicability'])

    def test_real_json_no_git_rebuild_rejects_resigned_answer_period_and_source_changes(self):
        case=self.cases['marriott_international']
        with tempfile.TemporaryDirectory(prefix='normal-catalog-source-') as tmp:
            data=Path(tmp);copy_sources(case,data)
            self.assertFalse((data/'.git').exists())
            with original_sources_only():
                self.assertEqual(case,verify_ordinary_companyfacts_metrics(candidate=json.loads(json.dumps(case)),
                    repo_root=data,company_id='marriott_international'))
            for field in ('value','period_start'):
                changed=copy.deepcopy(case)
                changed['metrics']['B02']['result'][field]='999' if field=='value' else '2025-02-01'
                changed['component_id']=content_hash(value={k:v for k,v in changed.items() if k!='component_id'})
                with original_sources_only(),self.assertRaisesRegex(NormalCompanyfactsError,'SOURCE_REPLAY_CHANGED'):
                    verify_ordinary_companyfacts_metrics(candidate=changed,repo_root=data,company_id='marriott_international')
            original=data/case['prepared_input']['companyfacts_input']['source_repo_relative_path']
            original.write_bytes(original.read_bytes()+b' ')
            with original_sources_only(),self.assertRaisesRegex(BatchWorkflowError,'Request-ledger locator evidence is invalid'):
                resolve_ordinary_companyfacts_metrics(repo_root=data,company_id='marriott_international')

    def test_caller_cannot_supply_prior_period_filing_claim_or_answer(self):
        for key in ('prior_period','filing','claims','answer','source_proofs'):
            with self.subTest(key=key),self.assertRaises(TypeError):
                resolve_ordinary_companyfacts_metrics(repo_root=ROOT,company_id='marriott_international',**{key:{}})


if __name__=='__main__':
    unittest.main()
