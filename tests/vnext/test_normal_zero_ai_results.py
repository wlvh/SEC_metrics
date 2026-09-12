"""Current saved inputs reach native zero-AI records without legacy answers."""
import builtins
from contextlib import contextmanager
import copy
import io
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.batch_workflow import BatchWorkflowError
from vnext.canonical import content_hash
from vnext.deterministic_router import validate_verified_claim
from vnext.normal_annual_input import _registry_rows
from vnext.normal_zero_ai_results import resolve_ordinary_zero_ai_metric, verify_ordinary_zero_ai_metric, NormalZeroAiError, EVENT_METRICS
from vnext.records import validate_record


@contextmanager
def original_sources_only():
    original_open, original_io = builtins.open, io.open
    def checked(opener):
        def call(path, *args, **kwargs):
            if isinstance(path, (str, Path)) and any(x in str(path) for x in
                ('/outputs/', '/fixtures/', 'REPORT_', 'metrics_matrix.csv', 'metric_evidence.csv', 'latest_filings_inventory.csv')):
                raise AssertionError('Legacy answer or derived input read: ' + str(path))
            return opener(path, *args, **kwargs)
        return call
    with patch('builtins.open', checked(original_open)), patch('io.open', checked(original_io)), \
         patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')):
        yield


def copy_input(candidate, target, *, event_census=True):
    paths = set(candidate['authority_file_hashes']) | {'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
    for proof in candidate['source_proofs']:
        paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
    if candidate['metric_id'] in EVENT_METRICS and event_census:
        cik = candidate['prepared_input']['entity']
        for directory in (ROOT/'evidence/accession_materials').iterdir():
            parts = directory.name.rsplit('_',2)
            if directory.is_dir() and len(parts)==3 and parts[1].isdigit() and int(parts[1])==int(cik):
                paths.update(str(p.relative_to(ROOT)) for p in directory.glob('*.hdr.sgml'))
    for relative in paths:
        destination = target/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,destination)
    return paths


class OrdinaryZeroAiPrototypeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases={}
        with original_sources_only():
            for company in _registry_rows(repo_root=ROOT):
                for metric in ('B01','C01'):
                    cls.cases[(company['company_id'],metric)] = resolve_ordinary_zero_ai_metric(
                        repo_root=ROOT,company_id=company['company_id'],metric_id=metric)

    def test_twenty_actual_coordinates_use_native_records_and_never_create_a_run(self):
        self.assertEqual(20,len(self.cases))
        counts={'number':0,'structural':0,'withheld':0}
        for key,case in self.cases.items():
            with self.subTest(key=key):
                self.assertEqual('NOT_CREATED',case['native_run_status'])
                self.assertEqual({'provider':0,'paid':0,'sec':0},case['calls'])
                self.assertFalse(case['production_authorized'])
                self.assertFalse(case['current_latest_verified'])
                self.assertEqual('PREEXISTING_SAVED_ACQUISITIONS_ONLY',case['source_admission']['source_credit'])
                for record in case['records']: validate_record(record=record)
                for claim in case['claims']: validate_verified_claim(claim=claim)
                result=case['result']
                self.assertEqual(case['trace']['trace_id'],result['trace_id'])
                self.assertEqual(case['target_period']['period_start'],result['period_start'])
                self.assertEqual(case['target_period']['period_end'],result['period_end'])
                if result['publication']=='WITHHELD': counts['withheld']+=1
                elif result['applicability']=='N_A_STRUCTURAL': counts['structural']+=1
                else: counts['number']+=1
        self.assertEqual({'number':13,'structural':1,'withheld':6},counts)

    def test_revenue_is_recovered_from_real_same_accession_companyfacts(self):
        case=self.cases[('marriott_international','B01')]
        observation=case['observations'][0]
        binding=observation['source_binding']
        source=next(r for r in case['source_records'] if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==binding['raw_asset_id'])
        raw=json.loads((ROOT/source['storage_uri']).read_text())
        taxonomy,concept=binding['concept'].split(':',1)
        candidates=raw['facts'][taxonomy][concept]['units'][observation['unit']]
        selected=[f for f in candidates if f['accn']==binding['accession'] and f.get('start')==observation['period_start'] and f['end']==observation['period_end']]
        self.assertEqual({'26186000000'},{str(f['val']) for f in selected})
        self.assertEqual('26186000000',case['result']['value'])
        self.assertEqual('USD',case['result']['unit'])
        self.assertIn(['2024-01-01','2024-12-31'],case['selection']['source_reported_periods'])
        self.assertEqual('2025-01-01',case['result']['period_start'])

    def test_events_need_complete_additional_sources_and_preserve_a_real_zero(self):
        case=self.cases[('marriott_international','C01')]
        self.assertEqual('3',case['result']['value'])
        self.assertEqual('count',case['result']['unit'])
        self.assertEqual(10,len(case['selection']['source_event_accessions']))
        self.assertTrue(any(s['source_role']=='fy_8k_header' for s in case['source_references']))
        self.assertEqual(3,len(case['selection']['matched_verified_claim_ids']))
        chosen={c['verified_claim_id']:c for c in case['claims']}
        self.assertEqual({'5.02'},{chosen[k]['attributes']['item_code'] for k in case['selection']['matched_verified_claim_ids']})
        zero=self.cases[('pfizer','C01')]
        self.assertEqual('0',zero['result']['value'])
        self.assertEqual(9,len(zero['selection']['source_event_accessions']))
        self.assertEqual([],zero['selection']['matched_verified_claim_ids'])
        self.assertTrue(zero['source_set_manifests'])

    def test_noncalendar_periods_structural_and_source_failures_are_not_relabelled(self):
        salesforce=self.cases[('salesforce','B01')]
        self.assertEqual(('2025-02-01','2026-01-31'),tuple(salesforce['target_period'][k] for k in ('period_start','period_end')))
        macys=self.cases[('macys','B01')]
        self.assertEqual(('2025-02-02','2026-01-31'),tuple(macys['target_period'][k] for k in ('period_start','period_end')))
        bank=self.cases[('jpmorgan_chase','B01')]
        self.assertEqual('N_A_STRUCTURAL',bank['result']['applicability'])
        self.assertEqual([],bank['observations'])
        for company,reason in [('southwest_airlines','AMENDMENT_REPLAY_NOT_IMPLEMENTED'),
                               ('paramount_skydance_paramount_global','SUCCESSOR_SCOPE_NOT_IMPLEMENTED')]:
            for metric in ('B01','C01'):
                row=self.cases[(company,metric)]
                self.assertEqual('WITHHELD',row['result']['publication'])
                self.assertEqual('IMPLEMENTATION_GAP',row['selection']['category'])
                self.assertIn(reason,row['selection']['reason'])
        failed=self.cases[('salesforce','C01')]
        self.assertEqual('SOURCE_ACCESS_FAILED',failed['selection']['category'])
        self.assertTrue(failed['failed_source_attempts'])
        self.assertIsNone(failed['result']['value'])
        self.assertEqual('SOURCE_COVERAGE_CONFLICT',self.cases[('jpmorgan_chase','C01')]['selection']['category'])

    def test_native_json_replay_rejects_self_consistent_changed_answer_and_source_omission(self):
        for metric in ('B01','C01'):
            case=json.loads(json.dumps(self.cases[('marriott_international',metric)]))
            with original_sources_only():
                self.assertEqual(case,verify_ordinary_zero_ai_metric(candidate=case,repo_root=ROOT,
                    company_id='marriott_international',metric_id=metric))
            changed=copy.deepcopy(case)
            changed['result']['value']='999'
            changed['component_id']=content_hash(value={k:v for k,v in changed.items() if k not in {'component_id','input_binding_id'}})
            with original_sources_only(), self.assertRaisesRegex(NormalZeroAiError,'SOURCE_REPLAY_CHANGED'):
                verify_ordinary_zero_ai_metric(candidate=changed,repo_root=ROOT,company_id='marriott_international',metric_id=metric)
            changed=copy.deepcopy(case);changed['source_references'].pop()
            with original_sources_only(), self.assertRaisesRegex(NormalZeroAiError,'SOURCE_REPLAY_CHANGED'):
                verify_ordinary_zero_ai_metric(candidate=changed,repo_root=ROOT,company_id='marriott_international',metric_id=metric)

    def test_portable_source_copy_needs_no_git_or_old_results_and_tampered_source_fails(self):
        for metric in ('B01','C01'):
            case=self.cases[('marriott_international',metric)]
            with tempfile.TemporaryDirectory(prefix='normal-zero-ai-source-') as tmp:
                target=Path(tmp)
                copy_input(case,target)
                self.assertFalse((target/'.git').exists())
                with original_sources_only():
                    self.assertEqual(case,resolve_ordinary_zero_ai_metric(repo_root=target,company_id='marriott_international',metric_id=metric))
                proof=next(p for p in case['source_proofs'] if '/companyfacts/' in p['source_url'])
                source=target/proof['request_repo_relative_path']
                source.write_bytes(source.read_bytes()+b' ')
                with original_sources_only(), self.assertRaisesRegex(BatchWorkflowError,'Request-ledger locator evidence is invalid'):
                    resolve_ordinary_zero_ai_metric(repo_root=target,company_id='marriott_international',metric_id=metric)

    def test_callers_cannot_supply_spec_period_fact_or_answer(self):
        for key in ('compiled_spec','target_period','source_fact','answer','source_proofs'):
            with self.subTest(key=key), self.assertRaises(TypeError):
                resolve_ordinary_zero_ai_metric(repo_root=ROOT,company_id='marriott_international',metric_id='B01',**{key:{}})
        with self.assertRaisesRegex(NormalZeroAiError,'METRIC_NOT_IN_PROTOTYPE'):
            resolve_ordinary_zero_ai_metric(repo_root=ROOT,company_id='marriott_international',metric_id='B10')


class OrdinaryZeroAiAdditionalRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.cases = {metric:resolve_ordinary_zero_ai_metric(repo_root=ROOT,
                company_id='marriott_international', metric_id=metric) for metric in ('B03', *EVENT_METRICS)}

    def test_ebitda_uses_current_revenue_dependency_and_exact_component_arithmetic(self):
        from decimal import Decimal, localcontext
        case = self.cases['B03']
        self.assertEqual({'B01'}, set(case['dependency_specs']))
        dependency = next(r for r in case['dependency_records'] if r['record_type'] == 'METRIC_RESULT')
        self.assertEqual('26186000000', dependency['value'])
        self.assertEqual('B01', dependency['metric_id'])
        # Independently check the source values and formula, not an old answer.
        facts = json.loads((ROOT/case['prepared_input']['companyfacts_input']['source_repo_relative_path']).read_text())
        def original(concept):
            return {Decimal(str(f['val'])) for f in facts['facts']['us-gaap'][concept]['units']['USD']
                if f['accn'] == case['prepared_input']['filing']['accessionNumber']
                and f.get('start') == '2025-01-01' and f['end'] == '2025-12-31'}
        revenue, income, depreciation, amortization = (original(c) for c in (
            'Revenues','OperatingIncomeLoss','Depreciation','AmortizationOfIntangibleAssets'))
        self.assertTrue(all(len(values) == 1 for values in (revenue,income,depreciation,amortization)))
        with localcontext() as context:
            context.prec = 28
            expected = (next(iter(income)) + next(iter(depreciation)) + next(iter(amortization))) / next(iter(revenue))
        self.assertEqual(expected, Decimal(case['result']['value']))
        self.assertTrue(any(s['event'] == 'REUSED_OBSERVATION' for s in case['trace']['steps']))
        ids = [content_hash(value=r) for r in case['records']]
        self.assertEqual(len(ids), len(set(ids)))
        for record in case['records']: validate_record(record=record)

    def test_six_events_share_source_coverage_but_keep_their_catalog_meanings(self):
        canonical = self.cases['C01']
        for metric in EVENT_METRICS:
            case = self.cases[metric]
            self.assertEqual(canonical['claims'],case['claims'])
            self.assertEqual(canonical['source_set_manifests'],case['source_set_manifests'])
            self.assertEqual('count',case['result']['unit'])
            self.assertEqual(metric,case['result']['metric_id'])
            self.assertEqual(10,len(case['selection']['source_event_accessions']))
        self.assertEqual('3',self.cases['E03']['result']['value'])
        self.assertEqual(canonical['selection']['matched_verified_claim_ids'],self.cases['E03']['selection']['matched_verified_claim_ids'])
        for metric in ('E01','E02','E04','E05'):
            self.assertEqual('0',self.cases[metric]['result']['value'])
            self.assertEqual([],self.cases[metric]['selection']['matched_verified_claim_ids'])

    def test_additional_routes_rebuild_json_and_cannot_omit_the_dependency_or_coverage(self):
        for metric in ('B03','E03'):
            original = self.cases[metric]
            with original_sources_only():
                self.assertEqual(original,verify_ordinary_zero_ai_metric(candidate=json.loads(json.dumps(original)),
                    repo_root=ROOT,company_id='marriott_international',metric_id=metric))
            changed = copy.deepcopy(original)
            if metric == 'B03': changed['dependency_records'] = []
            else: changed['source_set_manifests'].pop()
            changed['component_id'] = content_hash(value={k:v for k,v in changed.items() if k not in {'component_id','input_binding_id'}})
            with original_sources_only(), self.assertRaisesRegex(NormalZeroAiError,'SOURCE_REPLAY_CHANGED'):
                verify_ordinary_zero_ai_metric(candidate=changed,repo_root=ROOT,company_id='marriott_international',metric_id=metric)


if __name__=='__main__':
    unittest.main()
