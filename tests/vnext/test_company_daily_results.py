"""Small isolated saved-record fixtures; real source reading is separate evidence."""
from contextlib import contextmanager, redirect_stdout
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext import company_daily_results as daily
from scripts.vnext.calculator import calculate_metric
from scripts.vnext.canonical import content_hash, sha256_file
from scripts.vnext.csv_output import METRIC_FIELDS, EVIDENCE_FIELDS, _csv_bytes
from scripts.vnext.company_result_view import save_execution
from scripts.vnext.ordinary_update_cycle import _record
from scripts.vnext.sources import raw_blob_record, source_reference_record
from scripts.vnext.specs import compile_spec_file
from tests.vnext.test_b03_calculator import fact

ROOT = Path(__file__).resolve().parents[2]


class CompanyDailyResultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'state'; self.root.mkdir()
        self.company = 'marriott_international'
        self.current = {'company_id': self.company, 'checkpoint_id': 'source-fixture-v1'}
        self.serial = 0

    def saved(self, *, row_changes=None, fail=False, closure='fixture-contract', applicable=True):
        self.serial += 1; identity = format(self.serial,'032x')
        target = self.root/'updates/metrics/B01'; target.mkdir(parents=True,exist_ok=True)
        config = target/'configuration.json'
        configuration = (json.loads(config.read_text()) if config.exists() else _record(config,
            {'company_id':self.company, 'metric_ids':['B01'], 'source_root':str(self.root/'source'),
             'requirement_closure_hash':closure}))
        previous = (json.loads((target/'current.json').read_text()) if (target/'current.json').exists()
                    else {'latest_attempt':None,'successful_attempt':None})
        work = target/'attempts'/identity
        intent = _record(work/'intent.json', {'attempt_id':identity, 'configuration_id':configuration['record_id'],
            'previous_attempt':previous['latest_attempt'], 'previous_successful_attempt':previous['successful_attempt']})
        metrics = {}
        if not fail:
            data = work/'data'; data.mkdir()
            body = data/'evidence/fixture.json'; body.parent.mkdir(); body.write_text('{"fixture_revenue":120}')
            blob = raw_blob_record(repo_root=data,repo_relative_path='evidence/fixture.json',media_type='application/json')
            ref = source_reference_record(raw_blob=blob,company_id=self.company,
                source_url='https://www.sec.gov/Archives/edgar/data/1048286/000104828626000007/fixture.json',
                accession='0001048286-26-000007',document_name='fixture.json',source_role='companyfacts',
                request_attempt_id='isolated-test-request')
            path = data/'catalog/metrics/B01_revenue.md'; path.parent.mkdir(parents=True)
            path.write_bytes((ROOT/'catalog/metrics/B01_revenue.md').read_bytes())
            spec = compile_spec_file(path=path,dependency_specs={})
            f = fact(concept='us-gaap:Revenues',value='120',entity='1048286')
            f['source_binding'].update(raw_asset_id=blob['raw_asset_id'],source_reference_id=ref['source_reference_id'])
            from scripts.vnext.observations import scope_key
            scope = {'consolidation':'entity'}
            result,trace,obs = calculate_metric(compiled_spec=spec,
                target={'company_id':self.company,'period_start':'2025-01-01','period_end':'2025-12-31',
                    'accession':f['accession'],'entity':'1048286','scope':scope,'scope_key':scope_key(scope=scope)},
                company_traits=['non_financial'] if applicable else [],structured_facts=[f],verified_observations=[])
            records = [blob,ref,*obs,trace,result]
            run = work/'runs/B01'; run.mkdir(parents=True)
            (run/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            manifest = {'record_type':'ISOLATED_TEST_SAVED_MANIFEST','company_id':self.company,
                'run_id':'test-saved:'+identity,'status':'OPEN',
                'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'},
                'requirement_id':'issue_28_v13','requirement_closure_hash':closure,
                'spec_file_hashes':{'catalog/metrics/B01_revenue.md':sha256_file(path=path)},
                'records_file_hash':sha256_file(path=run/'records.jsonl')}
            (run/'manifest.json').write_text(json.dumps(manifest))
            rows = work/'rows/B01'; rows.mkdir(parents=True)
            row = {**dict.fromkeys(METRIC_FIELDS,''),'company':'Test Marriott','cik':'1048286','metric_id':'B01',
                'value':'120' if applicable else '', 'unit':'USD',
                'status':'OK' if applicable else 'N_A_STRUCTURAL','fiscal_year':'2025',
                'period_start':'2025-01-01','period_end':'2025-12-31',**(row_changes or {})}
            evidence = {**dict.fromkeys(EVIDENCE_FIELDS,''),'metric_id':'B01','source_url':ref['source_url'],
                'content_sha256':blob['raw_asset_id'][7:],'repo_relative_path':blob['storage_uri'],
                'accession':ref['accession'],'document_name':ref['document_name'],'evidence_quote':'fixture revenue 120'}
            for name, values, fields in [('metrics_matrix.csv',[row],METRIC_FIELDS),('metric_evidence.csv',[evidence],EVIDENCE_FIELDS)]:
                (rows/name).write_bytes(_csv_bytes(rows=values,fieldnames=fields))
            metrics['B01'] = {'result_id':result['result_id'],'files':{name:sha256_file(path=rows/name)
                for name in ('metrics_matrix.csv','metric_evidence.csv')}}
            self.result_id = result['result_id']; self.body_path = body
        terminal = _record(work/'terminal.json',{'attempt_id':identity,'configuration_id':configuration['record_id'],
            'intent_id':intent['record_id'],'status':'INPUT_FAILED' if fail else 'CANDIDATE_READY',
            'error':{'reason':'source failed'} if fail else None,'metrics':metrics})
        successful = previous['successful_attempt'] if fail else identity
        (target/'current.json').write_text(json.dumps({'configuration_id':configuration['record_id'],
            'latest_attempt':identity,'successful_attempt':successful}))
        outcome = {'metric_id':'B01','status':terminal['status'],
            'last_verified_candidate':{'attempt_id':successful,'rows_root':str(target/'attempts'/successful/'rows'),
                                     'current_input_matches':not fail} if successful else None}
        save_execution(root=self.root, report={'record_type':'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id':self.company,'source_checkpoint_id':self.current['checkpoint_id'],
            'period_request':None,'metrics':[outcome]})
        return work

    def read(self, *, defects=None, suffix='daily', row_year=None):
        @contextmanager
        def locked(root): yield Path(root)
        registry = self.root.parent/'defects.json'
        if defects: registry.write_text(json.dumps(defects))
        with (patch.object(daily,'locked_company',locked), patch.object(daily,'recover_for_read',return_value=self.current),
             patch('scripts.vnext.company_result_export.replay_candidate',side_effect=AssertionError('No replay')),
             patch('shutil.copytree',side_effect=AssertionError('No attempt copy'))):
            result = daily.write_daily_results(state_root=self.root,output_root=self.root.parent/suffix,
                company_id=self.company, defects_file=registry if defects else None)
        output = self.root.parent/suffix
        rows=list(csv.DictReader(io.StringIO((output/'metrics_matrix.csv').read_text())))
        row, = [r for r in rows if row_year is None or r['fiscal_year']==str(row_year)]
        return result,row,output

    def test_calculated_value_and_source_links_without_replay_or_copy(self):
        work = self.saved(); result,row,out = self.read()
        self.assertEqual((row['value'],row['unit'],row['period_start'],row['period_end']),('120','USD','2025-01-01','2025-12-31'))
        self.assertEqual(row['result_validity'],'SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED')
        self.assertEqual(row['source_root'],str(work/'data'))
        self.assertEqual(row['requested_in_latest_execution'],'True')
        self.assertEqual(row['period_role'],'RUN_ARCHIVE_COORDINATE')
        self.assertFalse((out/'native').exists()); self.assertFalse(result['replay_performed'])

    def test_wrong_value_unit_or_measurement_is_withheld(self):
        for update,reason in [({'value':'999'},'VALUE_CHANGED'),({'unit':'shares'},'UNIT_CHANGED'),
                              ({'period_start':'2024-01-01'},'MEASUREMENT_CHANGED'),
                              ({'fiscal_year':'2024'},'FISCAL_LABEL_CHANGED')]:
            with self.subTest(update=update):
                self.saved(row_changes=update); result,row,_ = self.read(suffix='daily'+str(self.serial))
                self.assertEqual(result['status'],'READ_PARTIAL'); self.assertEqual(row['value'],'')
                self.assertIn(reason,row['notes'])

    def test_previous_period_outside_latest_request_stays_visible_but_is_not_requested(self):
        self.saved()
        save_execution(root=self.root,report={'record_type':'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id':self.company,'source_checkpoint_id':self.current['checkpoint_id'],
            'period_request':{'fiscal_year':2024},'metrics':[{'metric_id':'B01','status':'INPUT_FAILED'}]})
        _,row,out=self.read(row_year=2025)
        self.assertEqual(row['requested_in_latest_execution'],'False')
        self.assertEqual(row['period_role'],'RUN_ARCHIVE_COORDINATE')
        self.assertEqual(row['fiscal_year'],'2025')
        rows=list(csv.DictReader(io.StringIO((out/'metrics_matrix.csv').read_text())))
        pending=next(r for r in rows if r['fiscal_year']=='2024')
        self.assertEqual((pending['status'],pending['period_role'],pending['requested_in_latest_execution']),
                         ('INPUT_FAILED','REQUESTED_WITHOUT_RESULT','True'))

    def test_missing_range_years_match_actual_latest_outcomes_not_range_header(self):
        pending=[{'metric_id':'B01','period_request':{'fiscal_year':y},'latest_attempt_status':'SOURCE_INPUT_REQUIRED',
                  'run_id':None,'result_validity':'NO_RESULT'} for y in (2022,2023,2024)]
        latest={'period_request':{'fiscal_year_start':2023,'fiscal_year_end':2024},
            'metrics':[{'metric_id':'B01','period_request':{'fiscal_year':y}} for y in (2023,2024)]}
        view={'metrics':pending,'latest_execution':latest,'company_id':self.company}
        with patch.object(daily,'build_company_view',return_value=view):
            _,_,out=self.read(row_year=2022)
        rows=list(csv.DictReader(io.StringIO((out/'metrics_matrix.csv').read_text())))
        self.assertEqual([(r['fiscal_year'],r['requested_in_latest_execution']) for r in rows],
                         [('2022','False'),('2023','True'),('2024','True')])

    def test_real_save_view_csv_preserves_each_missing_range_year(self):
        save_execution(root=self.root,report={'record_type':'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id':self.company,'source_checkpoint_id':self.current['checkpoint_id'],
            'period_request':{'fiscal_year':2022},'metrics':[{'metric_id':'B01','status':'INPUT_FAILED'}]})
        save_execution(root=self.root,report={'record_type':'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id':self.company,'source_checkpoint_id':self.current['checkpoint_id'],
            'period_request':{'fiscal_year_start':2023,'fiscal_year_end':2024},
            'metrics':[{'metric_id':'B01','status':'SOURCE_INPUT_REQUIRED','period_request':{'fiscal_year':y}}
                       for y in (2023,2024)]})
        _,_,out=self.read(row_year=2022)
        rows=list(csv.DictReader(io.StringIO((out/'metrics_matrix.csv').read_text())))
        self.assertEqual([(r['fiscal_year'],r['requested_in_latest_execution']) for r in rows],
                         [('2022','False'),('2023','True'),('2024','True')])
        self.assertTrue(all(r['value']=='' for r in rows))

    def test_known_defect_release_of_another_result_does_not_release_this_result(self):
        self.saved()
        defect={'defect_id':'known-fixture-error','company_id':self.company,'metric_id':'B01','period_end':'2025-12-31',
                'result_id':self.result_id,'released':[{'result_id':'different-fixed-result','requirement_closure_hash':'other-runtime'}]}
        _,row,_=self.read(defects={'defects':[defect]})
        self.assertEqual((row['value'],row['status']),('','WITHHELD'))
        self.assertEqual(row['result_validity'],'CONFIRMED_INVALID')

    def test_same_result_release_does_not_need_another_package_proof(self):
        self.saved()
        defect={'defect_id':'same-result-old-package','company_id':self.company,'metric_id':'B01','period_end':'2025-12-31',
                'released':[{'result_id':self.result_id,'requirement_closure_hash':'other-runtime'}]}
        _,row,out=self.read(defects={'defects':[defect]})
        self.assertEqual(row['value'],'120')
        self.assertEqual(row['result_validity'],'SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED')
        entry=json.loads((out/'company-results.json').read_text())['metrics'][0]
        self.assertTrue(entry['prior_same_result_releases'])

    def test_latest_failed_input_keeps_previous_period_but_does_not_look_current(self):
        self.saved(); self.saved(fail=True); _,row,_=self.read()
        self.assertEqual((row['value'],row['status']),('120','PREVIOUS_RESULT'))
        self.assertEqual(row['latest_attempt_status'],'INPUT_FAILED')
        self.assertEqual(row['current_input_status'],'MISMATCH_OR_FAILED')

    def test_source_damage_is_rejected(self):
        self.saved(); self.body_path.write_text('unexpected damage'); result,row,_=self.read()
        self.assertEqual(result['status'],'READ_PARTIAL'); self.assertIn('SOURCE_BYTES_CHANGED',row['notes'])

    def test_structural_absence_has_no_invented_value(self):
        self.saved(applicable=False); result,row,_=self.read()
        self.assertEqual(result['status'],'READ')
        self.assertEqual((row['value'],row['unit'],row['status']),('','USD','N_A_STRUCTURAL'))

    def test_failed_import_is_visible_without_hiding_previous_value(self):
        self.saved(); (self.root/'latest_import.json').write_text(json.dumps({'status':'FAILED','error':'new source missing'}))
        _,row,_=self.read(); self.assertEqual(row['status'],'PREVIOUS_RESULT')
        self.assertEqual(row['source_import_status'],'FAILED')

    def test_failed_export_has_no_complete_output_and_does_not_change_saved_state(self):
        self.saved(); before = (self.root/'updates/metrics/B01/current.json').read_bytes()
        with patch.object(daily.os,'rename',side_effect=OSError('ordinary write interruption')):
            with self.assertRaisesRegex(OSError,'write interruption'):
                self.read()
        self.assertFalse((self.root.parent/'daily').exists())
        self.assertEqual((self.root/'updates/metrics/B01/current.json').read_bytes(),before)
        self.assertFalse(list(self.root.parent.glob('.daily-*')))

    def test_existing_output_is_not_overwritten(self):
        self.saved(); _,_,out=self.read(); before=(out/'metrics_matrix.csv').read_bytes()
        with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):
            self.read()
        self.assertEqual((out/'metrics_matrix.csv').read_bytes(),before)

    def test_cli_partial_read_is_nonzero(self):
        from tools import vnext_company
        with patch('vnext.company_daily_results.write_daily_results',return_value={'status':'READ_PARTIAL'}), \
             redirect_stdout(io.StringIO()):
            code = vnext_company.main(['results','--state-root',str(self.root),
                '--trust-root',str(self.root.parent/'trust'),'--company',self.company,
                '--output-root',str(self.root.parent/'daily')])
        self.assertEqual(code,2)


if __name__ == '__main__': unittest.main()
