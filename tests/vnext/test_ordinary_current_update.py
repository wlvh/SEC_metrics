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
        self.root=Path(self.temp.name)/'state'
        self.config={'processing_version':'one'}
        self.census=[{'source_url':'source-a','content_sha256':'a','status_code':'200','error':''}]
        self.proof={'source_url':'source-a','accession':'filing-a','document_name':'a.json','content_sha256':'a'}
        self.records={};self.calculations=0
        def create(**kwargs):
            self.calculations+=1; path=kwargs['output_root'];path.mkdir(parents=True)
            result={'company_id':'marriott_international','metric_id':'B01','publication':'PUBLISHED',
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


class CurrentProcessingConfigurationTest(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
