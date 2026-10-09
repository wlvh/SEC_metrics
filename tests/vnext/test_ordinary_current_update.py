"""Small controller regressions; source/calculation mocks are explicit.

Real saved-source initial/repeated CLI is recorded separately.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext import ordinary_current_update as update

ROOT = Path(__file__).resolve().parents[2]


class CurrentUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=(Path(self.temp.name)/'state').resolve()
        self.config={'processing_version':'one'}
        self.census=[{'source_url':'source-a','content_sha256':'a','status_code':'200','error':''}]
        self.proof={'source_url':'source-a','accession':'filing-a','document_name':'a.json','content_sha256':'a'}
        self.records={};self.calculations=0
        def create(**kwargs):
            self.calculations+=1; path=kwargs['output_root'];path.mkdir(parents=True)
            result={'company_id':'marriott_international','metric_id':'B01','publication':getattr(self,'publication','PUBLISHED'),
                    'period_end':'2025-12-31','result_id':'result-'+str(self.calculations)}
            value={'manifest':{'company_id':'marriott_international','metric_id':'B01','source_proofs':[self.proof]},
                   'result':result}
            self.records[str(path)]=value
            return value
        for target,kwargs in [('_configuration',{'side_effect':lambda *args:dict(self.config)}),
            ('_source_census',{'side_effect':lambda *args:list(self.census)}),
            ('_current_sources',{'side_effect':lambda *args:[dict(self.proof)]}),
            ('create_saved_result',{'side_effect':create}),
            ('read_saved_result',{'side_effect':lambda **kwargs:self.records[str(kwargs['output_root'])]})]:
            p=patch.object(update,target,**kwargs);p.start();self.addCleanup(p.stop)

    def run_update(self):
        return update.run_once(state_root=self.root,source_root=ROOT,
                               company_id='marriott_international',metric_id='B01')

    def test_identical_raw_and_config_never_enters_calculation(self):
        first=self.run_update()
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No calculation')):
            again=self.run_update()
        self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
        self.assertEqual(again['result_id'],first['result_id']);self.assertEqual(self.calculations,1)

    def test_existing_update_entry_selects_current_record_storage_explicitly(self):
        from scripts.vnext.ordinary_update_cycle import run_once
        with patch('scripts.vnext.ordinary_update_cycle._config',side_effect=AssertionError('No old Requirement')):
            result=run_once(state_root=self.root,source_root=ROOT,company_id='marriott_international',
                            metric_ids=['B01'],current_records=True)
        self.assertEqual(result['status'],'CANDIDATE_READY')

    def test_new_company_file_or_processing_change_makes_new_version(self):
        first=self.run_update();self.census.append({'source_url':'new-source','content_sha256':'b','status_code':'200','error':''})
        second=self.run_update();self.assertNotEqual(second['version'],first['version'])
        self.config['processing_version']='two';third=self.run_update()
        self.assertNotEqual(third['version'],second['version'])
        self.assertTrue((self.root/'results'/first['version']).is_dir())

    def test_latest_get_failure_does_not_claim_no_change_or_overwrite_success(self):
        first=self.run_update();old=(self.root/'current-result.json').read_bytes()
        with patch.object(update,'_current_sources',side_effect=ValueError('LATEST_SOURCE_REQUEST_FAILED')):
            failed=self.run_update()
        self.assertEqual(failed['status'],'INPUT_OR_EXECUTION_FAILED')
        self.assertIn('LATEST_SOURCE_REQUEST_FAILED',failed['reason'])
        self.assertEqual((self.root/'current-result.json').read_bytes(),old)
        self.assertEqual(self.calculations,1)

    def test_configuration_failure_is_persisted(self):
        self.run_update()
        with patch.object(update,'_configuration',side_effect=ValueError('missing processing file')):
            result=self.run_update()
        self.assertEqual(result['status'],'INPUT_OR_EXECUTION_FAILED')
        self.assertEqual(json.loads((self.root/'latest-check.json').read_text()),result)

    def test_unfinished_intent_is_interrupted_not_success(self):
        first=self.run_update();path=self.root/'checks/incomplete/intent.json'
        update._write(path,{'attempt_id':'incomplete','previous_result':None})
        again=self.run_update()
        self.assertEqual(json.loads(path.with_name('terminal.json').read_text())['status'],'INTERRUPTED')
        self.assertEqual(again['result_id'],first['result_id'])

    def test_saved_completion_recovers_pointer_before_next_check(self):
        first=self.run_update();(self.root/'current-result.json').unlink()
        again=self.run_update()
        self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
        self.assertEqual(again['result_id'],first['result_id']);self.assertEqual(self.calculations,1)

    def test_old_native_history_requires_its_old_controller(self):
        self.root.mkdir();(self.root/'configuration.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'OLD_NATIVE_HISTORY'):
            self.run_update()

    def test_census_uses_company_latest_bodies_not_request_identity_or_other_company(self):
        rows=[{'method':'GET','source_url':'https://data.sec.gov/submissions/CIK0001048286.json',
               'status_code':'200','error':'','content_sha256':'same','document_name':'CIK0001048286.json'},
              {'method':'GET','source_url':'https://data.sec.gov/submissions/CIK0000789019.json',
               'status_code':'200','error':'','content_sha256':'other','document_name':'CIK0000789019.json'}]
        # Restore the actual function for this small metadata boundary.
        with patch('scripts.vnext.annual_sources._rows',return_value=rows):
            result=CurrentUpdateTest.original_census(ROOT,'marriott_international')
        self.assertEqual(len(result),1);self.assertEqual(result[0]['content_sha256'],'same')


CurrentUpdateTest.original_census = staticmethod(update._source_census)


class CompletedWithheldUpdateTest(unittest.TestCase):
    setUp=CurrentUpdateTest.setUp
    run_update=CurrentUpdateTest.run_update
    def test_first_withheld_repeats_without_factory_or_another_result(self):
        self.publication='WITHHELD';first=self.run_update()
        self.assertEqual(first['status'],'CANDIDATE_WITHHELD')
        before=set((self.root/'results').iterdir())
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated withheld calculation')):
            again=self.run_update()
        self.assertEqual(again['status'],'PREVIOUS_INPUT_WITHHELD')
        self.assertFalse(again['calculation_performed']);self.assertEqual(again['result_id'],first['result_id'])
        self.assertEqual(set((self.root/'results').iterdir()),before)
        self.assertFalse((self.root/'current-result.json').exists())

    def test_withheld_replaces_current_conclusion_but_preserves_success_history(self):
        success=self.run_update();old=(self.root/'current-result.json').read_bytes()
        self.config['processing_version']='changed';self.publication='WITHHELD';held=self.run_update()
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated calculation')):
            again=self.run_update()
        self.assertEqual(again['status'],'PREVIOUS_INPUT_WITHHELD');self.assertEqual(again['result_id'],held['result_id'])
        self.assertNotEqual(again['result_id'],success['result_id'])
        self.assertEqual((self.root/'current-result.json').read_bytes(),old)
        self.assertEqual(self.records[success['result_root']]['result']['publication'],'PUBLISHED')

    def test_source_and_configuration_changes_reprocess_stable_withheld(self):
        self.publication='WITHHELD';first=self.run_update()
        self.proof['content_sha256']='new';self.census[0]['content_sha256']='new'
        second=self.run_update();self.assertNotEqual(second['version'],first['version'])
        self.config['processing_version']='new-calculation-or-prompt';third=self.run_update()
        self.assertNotEqual(third['version'],second['version']);self.assertEqual(self.calculations,3)

    def test_completed_withheld_recovers_interrupted_pointer_write(self):
        self.publication='WITHHELD';write=update._write
        def interrupted(path,value):
            if path.name=='completed-check.json':raise KeyboardInterrupt('Crash after terminal commit')
            write(path,value)
        with patch.object(update,'_write',side_effect=interrupted),self.assertRaises(KeyboardInterrupt):self.run_update()
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated calculation')):
            again=self.run_update()
        self.assertEqual(again['status'],'PREVIOUS_INPUT_WITHHELD');self.assertEqual(self.calculations,1)

    def test_program_exception_does_not_become_reusable_withheld(self):
        with patch.object(update,'create_saved_result',side_effect=RuntimeError('Program error')):
            failed=self.run_update()
        self.assertEqual(failed['status'],'INPUT_OR_EXECUTION_FAILED')
        self.assertEqual(self.run_update()['status'],'CANDIDATE_READY');self.assertEqual(self.calculations,1)


class CurrentProcessingConfigurationTest(unittest.TestCase):
    def test_b02_paired_scope_changes_invalidate_only_its_processing_identity(self):
        original=update.sha256_file
        before=update._configuration(ROOT,'pfizer','B02')
        unrelated=update._configuration(ROOT,'pfizer','B01')
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
                'changed-paired-measure-rule' if path.name=='paired_measure_v1.py' else original(path=path)):
            after=update._configuration(ROOT,'pfizer','B02')
            unchanged=update._configuration(ROOT,'pfizer','B01')
        self.assertIn('scripts/vnext/paired_measure_v1.py',before['processing_files'])
        self.assertNotEqual(before,after)
        self.assertEqual(unrelated,unchanged)

    def test_changed_paired_scope_rechecks_then_reuses_a_withheld_conclusion(self):
        original=update.sha256_file
        before=update._configuration(ROOT,'pfizer','B02')
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
                'changed-paired-measure-rule' if path.name=='paired_measure_v1.py' else original(path=path)):
            after=update._configuration(ROOT,'pfizer','B02')
        records={};calls=[]
        def create(**kw):
            calls.append(kw);kw['output_root'].mkdir(parents=True)
            record={'manifest':{'company_id':'pfizer','metric_id':'B02','source_proofs':[]},
                'result':{'company_id':'pfizer','metric_id':'B02',
                    'publication':'PUBLISHED' if len(calls)==1 else 'WITHHELD',
                    'period_end':'2025-12-31','result_id':'synthetic-paired-'+str(len(calls)),
                    'reason_code':None if len(calls)==1 else 'SYNTHETIC_PAIRED_SCOPE_UNPROVEN'}}
            records[str(kw['output_root'])]=record;return record
        with tempfile.TemporaryDirectory() as folder,patch.object(update,'_source_census',return_value=[]), \
             patch.object(update,'_current_sources',return_value=[]),patch.object(update,'create_saved_result',side_effect=create), \
             patch.object(update,'read_saved_result',side_effect=lambda **kw:records[str(kw['output_root'])]):
            args=dict(state_root=Path(folder)/'state',source_root=ROOT,company_id='pfizer',metric_id='B02')
            with patch.object(update,'_configuration',return_value=before):first=update.run_once(**args)
            old_success=(args['state_root']/'current-result.json').read_bytes()
            with patch.object(update,'_configuration',return_value=after):second=update.run_once(**args)
            with patch.object(update,'_configuration',return_value=after), \
                 patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated paired-scope calculation')):
                repeated=update.run_once(**args)
            self.assertEqual(second['status'],'CANDIDATE_WITHHELD')
            self.assertNotEqual(first['version'],second['version'])
            self.assertEqual(repeated['status'],'PREVIOUS_INPUT_WITHHELD')
            self.assertEqual(repeated['result_id'],second['result_id'])
            self.assertEqual((args['state_root']/'current-result.json').read_bytes(),old_success)
            self.assertEqual(len(calls),2)

    def test_consumed_deterministic_graph_is_part_of_processing_identity(self):
        original=update.sha256_file
        for metric in ('B02','B04','B05'):
            before=update._configuration(ROOT,'marriott_international',metric)
            self.assertIn('scripts/vnext/zero_ai_r2.py',before['processing_files'])
            def changed(*,path):
                return 'changed-consumed-formula' if path.name=='zero_ai_r2.py' else original(path=path)
            with patch.object(update,'sha256_file',side_effect=changed):
                after=update._configuration(ROOT,'marriott_international',metric)
            self.assertNotEqual(before,after)

    def test_changed_graph_reprocesses_same_input_instead_of_reusing_old_result(self):
        original=update.sha256_file
        before=update._configuration(ROOT,'marriott_international','B04')
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
                'changed-formula' if path.name=='zero_ai_r2.py' else original(path=path)):
            after=update._configuration(ROOT,'marriott_international','B04')
        records={};calls=[]
        def create(**kw):
            calls.append(kw);path=kw['output_root'];path.mkdir(parents=True)
            record={'manifest':{'company_id':'marriott_international','metric_id':'B04','source_proofs':[]},
                'result':{'company_id':'marriott_international','metric_id':'B04','publication':'PUBLISHED',
                          'period_end':'2025-12-31','result_id':'synthetic-'+str(len(calls))}}
            records[str(path)]=record;return record
        with tempfile.TemporaryDirectory() as folder,patch.object(update,'_source_census',return_value=[]), \
             patch.object(update,'_current_sources',return_value=[]),patch.object(update,'create_saved_result',side_effect=create), \
             patch.object(update,'read_saved_result',side_effect=lambda **kw:records[str(kw['output_root'])]):
            args=dict(state_root=Path(folder)/'state',source_root=ROOT,company_id='marriott_international',metric_id='B04')
            with patch.object(update,'_configuration',return_value=before):first=update.run_once(**args)
            with patch.object(update,'_configuration',return_value=after):second=update.run_once(**args)
            with patch.object(update,'_configuration',return_value=after), \
                 patch.object(update,'create_saved_result',side_effect=AssertionError('No third calculation')):
                repeated=update.run_once(**args)
            self.assertEqual(second['status'],'CANDIDATE_READY')
            self.assertNotEqual(first['version'],second['version'])
            self.assertEqual(repeated['status'],'NO_SOURCE_CONTENT_CHANGE')
            self.assertEqual(len(calls),2)

    def test_lodging_only_changes_do_not_change_b01_processing_identity(self):
        original=update.sha256_file
        before=update._configuration(ROOT,'marriott_international','B01')
        def changed(*,path):
            return 'unrelated-lodging-version' if path.name=='normal_lodging_results.py' else original(path=path)
        with patch.object(update,'sha256_file',side_effect=changed):
            after=update._configuration(ROOT,'marriott_international','B01')
        self.assertEqual(before,after)
        self.assertNotIn('scripts/vnext/normal_lodging_results.py',before['processing_files'])

    def test_consumed_parser_changes_still_change_processing_identity(self):
        original=update.sha256_file
        before=update._configuration(ROOT,'marriott_international','B01')
        def changed(*,path):
            return 'new-consumed-parser-version' if path.name=='deterministic_router.py' else original(path=path)
        with patch.object(update,'sha256_file',side_effect=changed):
            after=update._configuration(ROOT,'marriott_international','B01')
        self.assertNotEqual(before['processing_files'].get('scripts/vnext/deterministic_router.py'),
                            after['processing_files'].get('scripts/vnext/deterministic_router.py'))


class SelectedPeriodUpdateTest(unittest.TestCase):
    setUp = CurrentUpdateTest.setUp

    def factory(self, *,repo_root,company_id,metric_id,fiscal_year):
        self.factory_calls=getattr(self,'factory_calls',0)+1
        return {'target_period':{'fiscal_year':fiscal_year}}

    def selected(self,year,factory=None,processing_files=()):
        def save(**kwargs):
            y=kwargs['case']['target_period']['fiscal_year'];path=kwargs['output_root'];path.mkdir(parents=True)
            value={'manifest':{'company_id':'marriott_international','metric_id':'B01','source_proofs':[self.proof]},
                'result':{'company_id':'marriott_international','metric_id':'B01','publication':getattr(self,'publication','PUBLISHED'),
                          'period_end':str(y)+'-12-31','result_id':'result-'+str(y)}}
            self.records[str(path)]=value
            return value
        with patch.object(update,'save_calculated_case',side_effect=save):
            return update.run_once(state_root=self.root,source_root=ROOT,company_id='marriott_international',
                metric_id='B01',fiscal_year=year,case_factory=factory or self.factory,processing_files=processing_files)

    def test_two_selected_periods_have_separate_pointers_and_current_layout_stays(self):
        first=self.selected(2024);second=self.selected(2025)
        self.assertEqual(first['status'],'CANDIDATE_READY');self.assertEqual(second['status'],'CANDIDATE_READY')
        for year in (2024,2025):
            self.assertEqual(json.loads((self.root/'periods'/('FY'+str(year))/'current-result.json').read_text())['requested_fiscal_year'],year)
        self.assertFalse((self.root/'current-result.json').exists())

    def test_unchanged_selected_period_does_not_invoke_case_factory(self):
        self.selected(2024)
        before=self.factory_calls
        with patch.object(update,'save_calculated_case',side_effect=AssertionError('No recalc')):
            again=update.run_once(state_root=self.root,source_root=ROOT,company_id='marriott_international',
                metric_id='B01',fiscal_year=2024,case_factory=self.factory)
        self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
        self.assertEqual(again['requested_fiscal_year'],2024)
        self.assertEqual(self.factory_calls,before)

    def test_wrong_selected_year_preserves_previous_pointer(self):
        self.selected(2024);pointer=self.root/'periods/FY2024/current-result.json';old=pointer.read_bytes()
        def wrong(**kwargs):return {'target_period':{'fiscal_year':2023}}
        result=self.selected(2024,factory=wrong)
        self.assertEqual(result['status'],'INPUT_OR_EXECUTION_FAILED')
        self.assertIn('CASE_FISCAL_YEAR_CHANGED',result['reason']);self.assertEqual(pointer.read_bytes(),old)

    def test_selected_period_without_factory_never_selects_latest(self):
        with self.assertRaisesRegex(ValueError,'REQUIRES_CASE_FACTORY'):
            update.run_once(state_root=self.root,source_root=ROOT,company_id='marriott_international',
                            metric_id='B01',fiscal_year=2024)

    def test_declared_dependency_change_recalculates_but_unrelated_change_does_not(self):
        paths=['scripts/vnext/normal_run_inputs.py'];first=self.selected(2024,processing_files=paths)
        original=update.sha256_file
        def unrelated(*,path):
            return 'irrelevant-change' if path.name=='normal_governance_input.py' else original(path=path)
        with patch.object(update,'sha256_file',side_effect=unrelated):again=self.selected(2024,processing_files=paths)
        self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
        def changed(*,path):
            return 'changed-producer-dependency' if path.name=='normal_run_inputs.py' else original(path=path)
        with patch.object(update,'sha256_file',side_effect=changed):new=self.selected(2024,processing_files=paths)
        self.assertEqual(new['status'],'CANDIDATE_READY');self.assertNotEqual(new['version'],first['version'])

    def test_processing_dependency_path_error_preserves_previous_result(self):
        self.selected(2024);pointer=self.root/'periods/FY2024/current-result.json';old=pointer.read_bytes()
        result=self.selected(2024,processing_files=['../wrong.py'])
        self.assertEqual(result['status'],'INPUT_OR_EXECUTION_FAILED')
        self.assertIn('PROCESSING_FILE_PATH_INVALID',result['reason']);self.assertEqual(pointer.read_bytes(),old)

    def test_period_selection_failure_retains_year_and_category(self):
        class MissingPeriod(ValueError):category='SOURCE_UNAVAILABLE'
        def missing(**kwargs):raise MissingPeriod('selected year missing')
        result=self.selected(2026,factory=missing)
        self.assertEqual(result['requested_fiscal_year'],2026)
        self.assertEqual(result['error_type'],'MissingPeriod')
        self.assertEqual(result['error_category'],'SOURCE_UNAVAILABLE')

    def test_completed_withheld_periods_do_not_override_current_or_each_other(self):
        CurrentUpdateTest.run_update(self)
        old=(self.root/'current-result.json').read_bytes()
        self.publication='WITHHELD';first=self.selected(2024);second=self.selected(2025)
        before=self.factory_calls
        again=self.selected(2024)
        self.assertEqual(again['status'],'PREVIOUS_INPUT_WITHHELD')
        self.assertEqual(again['result_id'],first['result_id'])
        self.assertNotEqual(again['result_id'],second['result_id'])
        self.assertEqual(self.factory_calls,before)
        self.assertEqual((self.root/'current-result.json').read_bytes(),old)
        self.assertFalse((self.root/'periods/FY2024/current-result.json').exists())

if __name__=='__main__':unittest.main()
