"""Small orchestration/retention checks; real-source CLI is separate evidence."""
import csv
import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import company_current_records as current
from vnext.csv_output import METRIC_FIELDS, EVIDENCE_FIELDS, _csv_bytes


class CurrentCompanyTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root/'source'; self.source.mkdir()
        self.work = self.root/'state'; self.outputs = self.root/'output'
        self.registry = self.root/'defects.json'; self.registry.write_text('{"defects":[]}')
        self.values = {}; self.updates = []
        def update(**kw):
            metric = kw['metric_id']; controller = kw['state_root']; controller.mkdir(parents=True, exist_ok=True)
            record = controller/'results'/'first'; record.mkdir(parents=True, exist_ok=True)
            result = {'company_id': 'marriott_international', 'metric_id': metric,
                      'period_end': '2025-12-31', 'result_id': metric+'-result'}
            row = {**{f: '' for f in METRIC_FIELDS}, 'company': 'Marriott International',
                   'metric_id': metric, 'value': '100', 'unit': 'USD', 'status': 'OK',
                   'period_start': '2025-01-01', 'period_end': '2025-12-31', 'fiscal_year': '2025'}
            self.values[str(record)] = {'result': result, 'files': {
                'metrics_matrix.csv': _csv_bytes(rows=[row],fieldnames=METRIC_FIELDS),
                'metric_evidence.csv': _csv_bytes(rows=[],fieldnames=EVIDENCE_FIELDS)}}
            (controller/'current-result.json').write_text('{"version":"first"}')
            self.updates.append(metric)
            return {'status': 'CANDIDATE_READY', 'result_root': str(record)}
        for name, kwargs in [('run_once', {'side_effect': update}),
                             ('read_saved_result', {'side_effect': lambda **k:self.values[str(k['output_root'])]})]:
            p = patch.object(current,name,**kwargs); p.start(); self.addCleanup(p.stop)

    def run_company(self, metrics=('B01','B02')):
        return current.run_saved_company(company_id='marriott_international',source_root=self.source,
            work_dir=self.work,output_dir=self.outputs,metric_ids=metrics,defects_file=self.registry)

    def rows(self, report):
        with (Path(report['output_root'])/'metrics_matrix.csv').open() as stream:
            return list(csv.DictReader(stream))

    def test_two_metrics_share_source_and_program_without_installer(self):
        from vnext.company_runtime_install import install_runtime
        with patch('vnext.company_runtime_install.install_runtime',side_effect=AssertionError('No installer')):
            r=self.run_company()
        self.assertEqual(r['status'],'FLOW_COMPLETED');self.assertEqual(self.updates,['B01','B02'])
        self.assertEqual(r['calls'],{'provider':0,'paid':0,'sec':0})
        self.assertFalse((self.work/'programs').exists());self.assertFalse((self.work/'source').exists())
        self.assertTrue(all(row['source_root']==str(self.source) for row in self.rows(r)))

    def test_existing_local_entry_selects_saved_branch_without_configure_task(self):
        from vnext.company_local import run_local
        with patch('vnext.company_local.configure_task',side_effect=AssertionError('No legacy installation')), \
             patch.object(current,'run_saved_company',return_value={'status':'FLOW_COMPLETED'}) as selected:
            run_local(company_id='marriott_international',source_root=self.source,
                work_dir=self.work,output_dir=self.outputs,metric_ids=['B01'])
        self.assertEqual(selected.call_args.kwargs['source_root'],self.source)

    def test_source_failure_preserves_old_period_and_other_metric_continues(self):
        self.run_company()
        def update(**kw):
            return {'status':'INPUT_OR_EXECUTION_FAILED','reason':'LATEST_SOURCE_REQUEST_FAILED'} if kw['metric_id']=='B01' else {'status':'NO_SOURCE_CONTENT_CHANGE'}
        with patch.object(current,'run_once',side_effect=update):r=self.run_company()
        rows={row['metric_id']:row for row in self.rows(r)}
        self.assertEqual(r['status'],'FLOW_COMPLETED_WITH_LIMITATIONS')
        self.assertEqual(rows['B01']['period_role'],'PREVIOUS_RESULT')
        self.assertEqual(rows['B01']['source_observation_status'],'FAILED_CURRENT_CHECK')
        self.assertEqual(rows['B01']['period_end'],'2025-12-31')
        self.assertEqual(rows['B02']['period_role'],'REQUESTED_RESULT')

    def test_known_bad_exact_result_is_removed_from_numeric_csv(self):
        self.registry.write_text(json.dumps({'defects':[{'defect_id':'test-known-defect',
            'company_id':'marriott_international','metric_id':'B01','period_end':'2025-12-31',
            'result_id':'B01-result','released':[]}]}))
        r=self.run_company(); rows={row['metric_id']:row for row in self.rows(r)}
        self.assertEqual(rows['B01']['value'],'');self.assertEqual(rows['B01']['status'],'WITHHELD_KNOWN_DEFECT')
        self.assertEqual(rows['B02']['value'],'100');self.assertEqual(r['status'],'FLOW_COMPLETED_WITH_LIMITATIONS')

    def test_wrong_metric_saved_record_is_not_exported(self):
        self.run_company()
        path=self.work/'updates/B01/results/first'
        self.values[str(path)]['result']['company_id']='wrong-company'
        with patch.object(current,'run_once',return_value={'status':'NO_SOURCE_CONTENT_CHANGE'}):r=self.run_company(['B01'])
        self.assertEqual(self.rows(r)[0]['value'],'')
        self.assertIn('WRONG_SAVED_COORDINATE',r['metrics'][0]['saved_read_error'])

    def test_metric_exception_is_local_not_batch_failure(self):
        with patch.object(current,'run_once',side_effect=ValueError('broken metric')):
            r=self.run_company()
        self.assertEqual(len(r['metrics']),2);self.assertEqual(r['status'],'FLOW_COMPLETED_WITH_LIMITATIONS')
        self.assertTrue(all(row['period_role']=='REQUESTED_WITHOUT_RESULT' for row in self.rows(r)))

    def test_missing_ai_and_deprecated_e01_do_not_manufacture_results(self):
        r=self.run_company(['D04','E01'])
        self.assertEqual(self.updates,[]);self.assertEqual(r['status'],'FLOW_COMPLETED_WITH_LIMITATIONS')
        self.assertTrue(all(row['value']=='' for row in self.rows(r)))

    def test_source_binding_and_old_task_are_not_reset(self):
        self.run_company()
        other=self.root/'other-source';other.mkdir()
        with self.assertRaisesRegex(ValueError,'TASK_IDENTITY_CHANGED'):
            current.run_saved_company(company_id='marriott_international',source_root=other,
                work_dir=self.work,output_dir=self.outputs,metric_ids=['B01'],defects_file=self.registry)
        (self.work/'local-company.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'OLD_TASK_REQUIRES_ORIGINAL_ENTRY'):self.run_company()

    def test_writable_state_cannot_overlap_source_or_code(self):
        with self.assertRaisesRegex(ValueError,'ROOTS_OVERLAP'):
            current.run_saved_company(company_id='marriott_international',source_root=self.source,
                work_dir=self.source/'state',output_dir=self.outputs,metric_ids=['B01'])

    def test_competing_writer_does_not_enter_calculation(self):
        self.work.mkdir()
        with (self.work/'company.lock').open('a+b') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.run_company()
        self.assertEqual(self.updates,[])

    def test_daily_read_does_not_select_sources_or_run_update(self):
        self.run_company()
        with patch.object(current,'run_once',side_effect=AssertionError('No update')):
            view=current.read_current_company(state_root=self.work,company_id='marriott_international')
        self.assertEqual(len(view['metrics']),2)
        self.assertEqual(view['source_freshness'],'NOT_CHECKED_BY_SAVED_READER')

    def test_unrelated_source_discovery_failure_still_shows_limitation(self):
        self.run_company()
        with patch.object(current,'run_once',return_value={'status':'NO_SOURCE_CONTENT_CHANGE',
             'source_observation_errors':[{'source_url':'metadata','status_code':'500'}]}):r=self.run_company()
        self.assertEqual(r['status'],'FLOW_COMPLETED_WITH_LIMITATIONS')
        self.assertTrue(all(row['source_observation_status']=='SAVED_SOURCE_CHECKED_WITH_DISCOVERY_ERRORS'
                            for row in self.rows(r)))

    def test_new_withheld_result_is_shown_instead_of_old_success(self):
        self.run_company(['B01'])
        record=self.work/'updates/B01/results/withheld';record.mkdir()
        old=self.values[str(self.work/'updates/B01/results/first')]
        row={**{f:'' for f in METRIC_FIELDS},'company':'Marriott International','metric_id':'B01',
             'status':'WITHHELD','period_start':'2026-01-01','period_end':'2026-12-31','fiscal_year':'2026'}
        self.values[str(record)]={'result':{**old['result'],'period_end':'2026-12-31','result_id':'new-withheld'},
            'files':{'metrics_matrix.csv':_csv_bytes(rows=[row],fieldnames=METRIC_FIELDS),
                     'metric_evidence.csv':old['files']['metric_evidence.csv']}}
        with patch.object(current,'run_once',return_value={'status':'CANDIDATE_WITHHELD','result_root':str(record)}):
            result=self.run_company(['B01'])
        self.assertEqual(self.rows(result)[0]['period_role'],'REQUESTED_RESULT')
        self.assertEqual(self.rows(result)[0]['period_end'],'2026-12-31')
        self.assertEqual(self.rows(result)[0]['value'],'')
        self.assertEqual(json.loads((self.work/'updates/B01/current-result.json').read_text())['version'],'first')

    def test_common_company_reader_keeps_other_metric_after_subset_run(self):
        from vnext.company_result_view import read_company_results
        self.run_company()
        for metric in ('B01','B02'):
            pointer=self.work/'updates'/metric/'current-result.json'
            pointer.write_text(json.dumps({'version':'first','company_id':'marriott_international',
                'metric_id':metric,'result_id':metric+'-result'}))
        self.run_company(['B02'])
        with patch('vnext.company_result_view.recover_for_read',side_effect=AssertionError('No old trust')):
            view=read_company_results(state_root=self.work,company_id='marriott_international',defects_file=self.registry)
        rows={m['metric_id']:m for m in view['metrics']}
        self.assertEqual(set(rows),{'B01','B02'})
        self.assertFalse(rows['B01']['requested_in_latest_execution'])
        self.assertTrue(rows['B02']['requested_in_latest_execution'])

    def test_common_read_exports_csv_and_honours_supplied_defects_without_update(self):
        from vnext.company_result_view import read_company_results
        self.run_company()
        self.registry.write_text(json.dumps({'defects':[{'defect_id':'held','company_id':'marriott_international',
            'metric_id':'B01','period_end':'2025-12-31','result_id':'B01-result','released':[]}]}))
        output=self.root/'daily'
        with patch.object(current,'run_once',side_effect=AssertionError('No update')):
            view=read_company_results(state_root=self.work,company_id='marriott_international',
                defects_file=self.registry,output_root=output)
        rows={r['metric_id']:r for r in self.rows({'output_root':str(output)})}
        self.assertEqual(rows['B01']['value'],'');self.assertEqual(rows['B02']['value'],'100')
        self.assertEqual(rows['B01']['status'],'WITHHELD_KNOWN_DEFECT')
        self.assertEqual(view['source_freshness'],'NOT_CHECKED_BY_SAVED_READER')
        self.assertTrue((output/'metric_evidence.csv').exists())


class SavedSourceCompanyEntryTest(unittest.TestCase):
    """One real source/Calculator preparation shared across read/reentry checks."""
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.work=cls.root/'state';cls.output=cls.root/'output'
        cls.report=current.run_saved_company(company_id='marriott_international',source_root=REPO_ROOT,
            work_dir=cls.work,output_dir=cls.output,metric_ids=['B01','B02'])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_marriott_values_periods_and_source_links_reach_company_csv(self):
        from decimal import Decimal
        with (Path(self.report['output_root'])/'metrics_matrix.csv').open() as f:
            rows={r['metric_id']:r for r in csv.DictReader(f)}
        self.assertEqual(self.report['status'],'FLOW_COMPLETED')
        self.assertEqual(Decimal(rows['B01']['value']),Decimal('26186000000'))
        self.assertEqual(Decimal(rows['B02']['value']),(Decimal('26186000000')-Decimal('25100000000'))/Decimal('25100000000'))
        self.assertEqual(rows['B01']['unit'],'USD');self.assertEqual(rows['B02']['unit'],'ratio')
        for row in rows.values():
            self.assertEqual((row['period_start'],row['period_end'],row['fiscal_year']),
                             ('2025-01-01','2025-12-31','2025'))
        with (Path(self.report['output_root'])/'metric_evidence.csv').open() as f:proofs=list(csv.DictReader(f))
        self.assertTrue(proofs);self.assertTrue(all(p['source_url'].startswith('https://') for p in proofs))
        self.assertFalse((self.work/'programs').exists());self.assertFalse((self.work/'source').exists())

    def test_real_reentry_never_invokes_calculation_factory(self):
        with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No calculation')):
            report=current.run_saved_company(company_id='marriott_international',source_root=REPO_ROOT,
                work_dir=self.work,output_dir=self.output,metric_ids=['B01','B02'])
        self.assertTrue(all(m['status']=='NO_SOURCE_CONTENT_CHANGE' for m in report['metrics']))

    def test_real_read_does_not_parse_or_update(self):
        with patch.object(current,'run_once',side_effect=AssertionError('No update')):
            view=current.read_current_company(state_root=self.work,company_id='marriott_international')
        self.assertEqual(len(view['metrics']),2)
        self.assertEqual(view['source_freshness'],'NOT_CHECKED_BY_SAVED_READER')


if __name__=='__main__':unittest.main()
