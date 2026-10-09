"""Compatibility selection only; actual empty-task CLI pair is separate."""
import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from tests.vnext.common import REPO_ROOT
from vnext import company_local as local
from vnext.company_retained_local import RETAINED_MAIN


class RetainedLocalTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name).resolve()/'work';self.work.mkdir()

    def test_new_native_task_uses_fixed_main_installer_without_current_tree_install(self):
        def install(*,repo_root,output_root):
            self.assertEqual(REPO_ROOT,repo_root)
            (output_root/'requirements/issue_54_v4').mkdir(parents=True)
            return {'retained_main_commit':RETAINED_MAIN}
        with patch('vnext.company_retained_local.install_retained_local',side_effect=install) as retained, \
             patch('vnext.company_runtime_install.install_runtime',side_effect=AssertionError('current tree is not the retained native program')):
            program=local.prepare_program(self.work)
        self.assertEqual(retained.call_count,1)
        self.assertEqual(program.parent,self.work/'programs')
        self.assertTrue((program/'requirements/issue_54_v4').is_dir())

    def test_existing_task_keeps_its_original_program_without_reinstallation(self):
        program=self.work/'programs/original';(program/'requirements/issue_54_v4').mkdir(parents=True)
        (self.work/'local-company.json').write_text(json.dumps({'program_root':str(program)}))
        with patch('vnext.company_retained_local.install_retained_local',side_effect=AssertionError('do not replace old program')):
            self.assertEqual(local.prepare_program(self.work),program)

    def test_saved_source_route_does_not_enter_retained_installer(self):
        with patch('vnext.company_current_records.run_saved_company',return_value={'status':'FLOW_COMPLETED'}) as current, \
             patch('vnext.company_retained_local.install_retained_local',side_effect=AssertionError('saved source has no native install')):
            local.run_local(company_id='marriott_international',work_dir=self.work,output_dir=self.work.parent/'out',source_root=self.work.parent/'source',metric_ids=['B01'])
        self.assertEqual(current.call_count,1)
