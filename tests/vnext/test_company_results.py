"""Orchestration regressions. Financial computation/replay are explicitly mocked."""
from contextlib import contextmanager
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext import company_compute, company_result_export as export
from scripts.vnext.company_result_view import build_company_view, save_execution
from scripts.vnext.company_handoff import _atomic_json
from scripts.vnext.ordinary_update_cycle import _record
from scripts.vnext.publication import _csv_bytes, METRIC_FIELDS, EVIDENCE_FIELDS
from scripts.vnext.canonical import sha256_file


class CompanyResultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'state'; self.root.mkdir()
        self.current = {'company_id': 'test_company', 'checkpoint_id': 'source-v1'}
        self.serial = 0

    def journal(self, metric, end='2025-12-31', fail=False, closure='old-runtime'):
        target = self.root/'updates/metrics'/metric
        target.mkdir(parents=True, exist_ok=True)
        config = target/'configuration.json'
        configuration = json.loads(config.read_text()) if config.exists() else _record(config, {
            'company_id': 'test_company', 'metric_ids': [metric], 'source_root': str(self.root/'source'),
            'requirement_closure_hash': closure})
        p = target/'current.json'
        previous = json.loads(p.read_text()) if p.exists() else {'latest_attempt': None, 'successful_attempt': None}
        self.serial += 1; identity = format(self.serial, '032x')
        work = target/'attempts'/identity
        intent = _record(work/'intent.json', {'attempt_id': identity, 'configuration_id': configuration['record_id'],
            'previous_attempt': previous['latest_attempt'], 'previous_successful_attempt': previous['successful_attempt']})
        terminal = _record(work/'terminal.json', {'attempt_id': identity, 'configuration_id': configuration['record_id'],
            'intent_id': intent['record_id'], 'status': 'INPUT_FAILED' if fail else 'CANDIDATE_READY',
            'error': {'reason': 'bad input'} if fail else None,
            'metrics': {} if fail else {metric: {'result_id': 'result-'+metric+'-'+end}}})
        if not fail:
            self.manifest(work, metric, end, closure)
        successful = previous['successful_attempt'] if fail else identity
        _atomic_json(p, {'configuration_id': configuration['record_id'], 'latest_attempt': identity,
                         'successful_attempt': successful})
        return {'metric_id': metric, 'status': terminal['status'], 'last_verified_candidate': None if successful is None else {
            'attempt_id': successful, 'rows_root': str(target/'attempts'/successful/'rows'),
            'current_input_matches': not fail}}

    def manifest(self, work, metric, end, closure):
        (work/'runs'/metric).mkdir(parents=True)
        _atomic_json(work/'runs'/metric/'manifest.json', {'company_id': 'test_company',
            'target_period': {'period_start': end[:4]+'-01-01', 'period_end': end, 'fiscal_year': int(end[:4])},
            'run_id': 'run:'+work.name, 'requirement_id': 'issue_54_v3' if 'historical' in work.parts else 'issue_28_v13',
            'requirement_closure_hash': closure, 'status': 'FROZEN' if 'historical' in work.parts else 'OPEN'})
        row = {**dict.fromkeys(METRIC_FIELDS, ''), 'metric_id': metric, 'period_end': end, 'value': '10', 'status': 'EXACT'}
        rows = work/'rows' if 'historical' in work.parts else work/'rows'/metric
        rows.mkdir(parents=True)
        (rows/'metrics_matrix.csv').write_bytes(_csv_bytes(rows=[row], fieldnames=METRIC_FIELDS))
        (rows/'metric_evidence.csv').write_bytes(_csv_bytes(rows=[{**dict.fromkeys(EVIDENCE_FIELDS, ''), 'metric_id': metric,'period_end': end}], fieldnames=EVIDENCE_FIELDS))

    def observe(self, rows, source='source-v1', period=None):
        return save_execution(root=self.root, report={'record_type': 'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id': 'test_company', 'source_checkpoint_id': source,
            'period_request': period, 'metrics': rows, 'runtime_root': '/fixed/runtime'})

    def view(self, registry=None):
        return build_company_view(root=self.root, company_id='test_company', current=self.current, defect_registry=registry)

    def replay(self, entry, roots):
        directory = Path(entry['rows_root']) if entry['row_layout']=='historical' else Path(entry['rows_root'])/entry['metric_id']
        return {p.name: p.read_bytes() for p in directory.iterdir()}, '/fixed/runtime'

    def exported(self, suffix='export', registry=None):
        @contextmanager
        def locked(root): yield Path(root)
        with patch.object(export, 'locked_company', locked), patch.object(export, 'recover_for_read', return_value=self.current), \
             patch.object(export, 'replay_candidate', side_effect=self.replay):
            output = self.root.parent/suffix
            defects = self.root.parent/'defects.json'
            if registry: defects.write_text(json.dumps(registry))
            result = export.export_results(state_root=self.root, output_root=output, company_id='test_company',
                                            defects_file=defects if registry else None)
            rows = list(csv.DictReader(io.StringIO((output/'metrics_matrix.csv').read_text())))
            return result, rows, output

    def test_compute_partial_request_preserves_native_D01_and_exports_both(self):
        @contextmanager
        def locked(root): yield Path(root)
        def run(**kw): return {'metrics': [self.journal(m) for m in kw['metric_ids']]}
        with patch.object(company_compute,'locked_company',locked), \
             patch.object(company_compute,'recover_import',return_value=self.current), \
             patch.object(company_compute,'require_company',return_value={'checkpoint_id':'source-v1','metric_ids':['B01','D01']}), \
             patch('scripts.vnext.ordinary_d02_category_update_v2.run_company',side_effect=run):
            company_compute.compute_company(state_root=self.root,company_id='test_company',metric_ids=['B01','D01'])
            _, first, _ = self.exported('first-export')
            self.assertEqual({'B01','D01'}, {r['metric_id'] for r in first})
            report = company_compute.compute_company(state_root=self.root,company_id='test_company',metric_ids=['B01'])
        self.assertEqual(['B01'], [m['metric_id'] for m in report['metrics']])
        self.assertEqual({'B01','D01'}, {m['metric_id'] for m in self.view()['metrics']})
        result, rows, output = self.exported()
        self.assertEqual({'B01','D01'}, {r['metric_id'] for r in rows})
        self.assertEqual(2,len(result['native_candidates']))
        self.assertTrue((output/'metric_evidence.csv').is_file())
        self.assertFalse(next(r for r in rows if r['metric_id']=='D01')['requested_in_latest_execution']=='True')

    def test_processing_arguments_cannot_be_silently_ignored(self):
        @contextmanager
        def locked(root): yield Path(root)
        program=self.root.parent/'program'; program.mkdir()
        with patch.object(company_compute,'locked_company',locked), \
             patch.object(company_compute,'recover_import',return_value=self.current), \
             patch.object(company_compute,'require_company',return_value={
                 'checkpoint_id':'source-v1','metric_ids':['B01','D04']}), \
             patch('scripts.vnext.normal_source_authority.ROOT',program), \
             patch('scripts.vnext.ordinary_d02_category_update_v2.run_company') as financial:
            with self.assertRaisesRegex(ValueError,'PACKAGE_AND_ORIGINAL_RUNTIME_REQUIRED'):
                company_compute.compute_company(state_root=self.root,company_id='test_company',
                    metric_ids=['D04'],processing_package='/separate/processing')
            with self.assertRaisesRegex(ValueError,'INPUT_REQUIRES_D04'):
                company_compute.compute_company(state_root=self.root,company_id='test_company',
                    metric_ids=['B01'],processing_package='/separate/processing',
                    processing_runtime='/original/runtime')
            (program/'requirements/issue_54_v3').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,'HISTORY_ADAPTER_NOT_IMPLEMENTED'):
                company_compute.compute_company(state_root=self.root,company_id='test_company',
                    metric_ids=['D04'],report_end='2023-12-31',processing_package='/separate/processing',
                    processing_runtime='/original/runtime')
            financial.assert_not_called()

    def test_failed_metric_keeps_old_result_without_claiming_current_success(self):
        self.observe([self.journal('B01'),self.journal('D01')])
        self.observe([self.journal('B01',fail=True)])
        _, rows, _ = self.exported()
        b = next(r for r in rows if r['metric_id']=='B01')
        self.assertEqual('INPUT_FAILED', b['latest_attempt_status'])
        self.assertEqual('False', b['current_input_matches'])
        self.assertEqual({'B01','D01'}, {r['metric_id'] for r in rows})

    def test_source_switch_does_not_claim_untouched_results_match(self):
        self.observe([self.journal('B01'),self.journal('D01')])
        self.current['checkpoint_id']='source-v2'
        self.observe([self.journal('B01')],source='source-v2')
        d = next(e for e in self.view()['metrics'] if e['metric_id']=='D01')
        self.assertIsNone(d['current_input_matches']); self.assertEqual('NOT_RECHECKED', d['current_input_status'])

    def test_historical_two_periods_and_partial_third_request(self):
        for year in [2023,2024]:
            target = self.root/'updates/historical'/f'{year}-12-31'/'A08'
            work = target/'attempts'/format(year,'032x')
            self.manifest(work,'A08',f'{year}-12-31','historical-closure')
            candidate = {'attempt_id':work.name,'rows_root':str(work/'rows'),'current_input_matches':True}
            _atomic_json(target/'current.json', {'attempt_id':work.name,'candidate':candidate})
            self.observe([{'metric_id':'A08','status':'CANDIDATE_READY','last_verified_candidate':candidate}])
        self.observe([self.journal('B01')])
        _, rows, _ = self.exported()
        self.assertEqual({'2023-12-31','2024-12-31'}, {r['period_end'] for r in rows if r['metric_id']=='A08'})
        self.assertEqual({'historical-closure','old-runtime'}, {r['requirement_closure_hash'] for r in rows})

    def test_ordinary_prior_year_remains_in_view(self):
        self.observe([self.journal('B01',end='2024-12-31')])
        self.observe([self.journal('B01',end='2025-12-31')])
        self.assertEqual(2,len(self.view()['metrics']))

    def test_confirmed_defect_keeps_native_but_withholds_company_value(self):
        self.observe([self.journal('B01')])
        registry = {'defects':[{'defect_id':'known-bad','company_id':'test_company','metric_id':'B01',
                               'period_end':'2025-12-31','result_id':'result-B01-2025-12-31'}]}
        result, rows, _ = self.exported(registry=registry)
        self.assertEqual('CONFIRMED_INVALID',rows[0]['result_validity'])
        self.assertEqual('',rows[0]['value']); self.assertEqual('WITHHELD',rows[0]['status'])
        self.assertEqual(1,len(result['native_candidates']))

    def test_archive_coordinate_and_wider_measurement_window_stay_distinct(self):
        outcome = self.journal('C01')
        work = Path(outcome['last_verified_candidate']['rows_root']).parent
        records = work/'runs/C01/records.jsonl'
        records.write_text(json.dumps({'record_type':'METRIC_RESULT','metric_id':'C01',
            'result_id':'result-C01-2025-12-31','period_start':'2024-01-01','period_end':'2025-12-31'})+'\n')
        path = records.parent/'manifest.json'; manifest=json.loads(path.read_text())
        manifest['records_file_hash']=sha256_file(path=records); _atomic_json(path,manifest)
        rows=work/'rows/C01/metrics_matrix.csv'
        row=list(csv.DictReader(io.StringIO(rows.read_text())))[0]
        row['period_start']='2024-01-01'; rows.write_bytes(_csv_bytes(rows=[row],fieldnames=METRIC_FIELDS))
        self.observe([outcome]); entry=self.view()['metrics'][0]
        self.assertEqual('2025-01-01',entry['period']['period_start'])
        self.assertEqual('RUN_ARCHIVE_COORDINATE',entry['period_role'])
        self.assertEqual('2024-01-01',entry['measurement_period']['period_start'])
        _, exported, _ = self.exported()
        self.assertEqual('2025-01-01',exported[0]['archive_period_start'])
        self.assertEqual('2024-01-01',exported[0]['measurement_period_start'])
        self.assertEqual('NATIVE_REPLAY_VERIFIED',exported[0]['measurement_period_status'])
        records.write_text(records.read_text().replace('2024-01-01','2023-01-01'))
        entry=self.view()['metrics'][0]
        self.assertIsNone(entry['measurement_period'])
        self.assertEqual('NATIVE_RECORD_INVALID',entry['measurement_period_status'])

    def test_other_runtime_release_explains_hold_without_releasing_current_result(self):
        self.observe([self.journal('D02',closure='current-runtime')])
        release={'result_id':'result-D02-2025-12-31','requirement_closure_hash':'accepted-runtime',
                 'accepted_by':'existing/reading.json','run_id':'original-run'}
        defect={'defect_id':'coordinate-defect','company_id':'test_company','metric_id':'D02',
                'period_end':'2025-12-31','result_id':None,'released':[release]}
        registry={'defects':[defect]}; entry=self.view(registry)['metrics'][0]
        self.assertEqual('CURRENT_RUNTIME_RELEASE_REQUIRED',entry['result_validity'])
        self.assertEqual(release,entry['defect_holds'][0]['releases_in_other_runtimes'][0])
        _, rows, _ = self.exported(registry=registry)
        self.assertEqual('WITHHELD',rows[0]['status']); self.assertEqual('',rows[0]['value'])
        self.assertIn('CURRENT_RUNTIME_RELEASE_REQUIRED',rows[0]['notes'])
        release['result_id']='different-result'
        self.assertEqual('CONFIRMED_INVALID',self.view(registry)['metrics'][0]['result_validity'])
        release.update(result_id='result-D02-2025-12-31',requirement_closure_hash='current-runtime')
        self.assertEqual([],self.view(registry)['metrics'][0]['confirmed_defects'])

    def test_one_replay_failure_does_not_hide_other_metrics(self):
        self.observe([self.journal('B01'),self.journal('D01')])
        original = self.replay
        def read(entry, roots):
            if entry['metric_id']=='B01': raise ValueError('BOUND_HEADER_CHANGED')
            return original(entry,roots)
        self.replay = read
        result, rows, _ = self.exported()
        self.assertEqual('EXPORTED_PARTIAL', result['status'])
        self.assertEqual({'B01','D01'}, {r['metric_id'] for r in rows})
        self.assertEqual('REPLAY_FAILED',next(r for r in rows if r['metric_id']=='B01')['result_validity'])

    def test_wrong_company_run_rejected(self):
        self.observe([self.journal('B01')])
        p = next(self.root.glob('updates/**/manifest.json')); v=json.loads(p.read_text());v['company_id']='other'
        p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError,'WRONG_COMPANY'):self.view()

    def test_failed_other_historical_period_remains_visible(self):
        self.observe([self.journal('A08',end='2023-12-31')])
        self.observe([{'metric_id':'A08','status':'INPUT_FAILED'}],period={'fiscal_year':2021})
        view=self.view(); self.assertEqual(2,len(view['metrics']))
        self.assertFalse(view['metrics'][0]['requested_in_latest_execution'])
        self.assertEqual({'fiscal_year':2021},view['metrics'][1]['period_request'])

    def test_legacy_report_subset_does_not_limit_journal_view(self):
        first=self.journal('B01');self.journal('D01')
        _atomic_json(self.root/'company-results.json',{'record_type':'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id':'test_company','source_checkpoint_id':'source-v1','metrics':[first]})
        self.assertEqual({'B01','D01'}, {e['metric_id'] for e in self.view()['metrics']})

    def test_successful_pointer_cannot_be_changed_to_an_earlier_candidate(self):
        one=self.journal('B01');self.journal('B01')
        p=self.root/'updates/metrics/B01/current.json';v=json.loads(p.read_text());v['successful_attempt']=one['last_verified_candidate']['attempt_id']
        p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError,'SUCCESSFUL_POINTER_CHANGED'):self.view()

    def test_processing_result_exposes_original_mode_and_runtime(self):
        target=self.root/'updates/processing/D04'/'original-closure'
        work=target/'attempts'/('a'*32)
        self.manifest(work,'D04','2025-12-31','original-closure')
        manifest=work/'runs/D04/manifest.json';value=json.loads(manifest.read_text())
        value['requirement_id']='issue_28_v14';manifest.write_text(json.dumps(value))
        _atomic_json(work/'processing-receipt.json',{'result_id':'original-result','mode':'LIVE'})
        (work/'processing').mkdir()
        _atomic_json(work/'processing/processing.json',{'mode':'RECORDED_TEST_ONLY'})
        _atomic_json(work/'processing/processing-source.json',{'source_admission':{
            'source_credit':'PREEXISTING_SAVED_ACQUISITIONS_ONLY'}})
        candidate={'attempt_id':work.name,'rows_root':str(work/'rows'),'current_input_matches':True,
                   'runtime_root':'/original/v14'}
        _atomic_json(target/'current.json',{'attempt_id':work.name,'candidate':candidate})
        self.observe([{'metric_id':'D04','status':'CANDIDATE_READY','last_verified_candidate':candidate}])
        view=self.view();self.assertEqual('processing',view['metrics'][0]['row_layout'])
        self.assertFalse(view['metrics'][0]['business_metric_completed'])
        _,rows,_=self.exported()
        self.assertEqual('RECORDED_TEST_ONLY',rows[0]['saved_processing_mode'])
        self.assertEqual('issue_28_v14',rows[0]['requirement_id'])
        self.assertEqual('PREEXISTING_SAVED_ACQUISITIONS_ONLY',rows[0]['source_credit'])
