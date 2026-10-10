"""Constructed controller state with actual main configuration; no business result."""
import hashlib,json,subprocess
from pathlib import Path
from unittest.mock import patch
from tests.vnext.test_selected_history_result_state import SelectedHistoryResultStateTest,update,ROOT
changed=['scripts/vnext/ordinary_current_update.py','scripts/vnext/ordinary_saved_result.py']
old={p:hashlib.sha256(subprocess.check_output(['git','show','145a464b:'+p])).hexdigest() for p in changed}
original_hash=update.sha256_file
control=SelectedHistoryResultStateTest();control.setUp()
try:
 control.outcomes[2025,'B11']='WITHHELD'
 def before_d04(*,path):return old.get(str(Path(path).relative_to(ROOT)),original_hash(path=path))
 with patch.object(update,'_configuration',side_effect=control.actual_configuration):
  with patch.object(update,'sha256_file',side_effect=before_d04):
   first=[control.run_control(2024),control.run_control(2025,'B11')]
  initial_calls=len(control.factory_calls)
  second=[control.run_control(2024),control.run_control(2025,'B11')]
  extra_calls=len(control.factory_calls)-initial_calls
  control.forbid_factory=True
  third=[control.run_control(2024),control.run_control(2025,'B11')]
 assert initial_calls==2 and extra_calls==2
 assert all(a['version']!=b['version'] for a,b in zip(first,second))
 assert [r['status'] for r in third]==['NO_SOURCE_CONTENT_CHANGE','PREVIOUS_INPUT_WITHHELD']
 r={'actual_main':'bdb27684','comparison_main':'145a464b','constructed_state_control':True,
    'real_annual_result_created':False,'actual_non_D04_configuration_changed_paths':old,
    'identical_mock_source_census_and_body_proofs':True,'unchanged_business_factory':True,
    'initial_factory_calls':initial_calls,'unrelated_D04_delta_factory_calls':extra_calls,
    'first_versions':[r['version'] for r in first],'second_versions':[r['version'] for r in second],
    'second_statuses':[r['status'] for r in second],'same_new_config_repeat_statuses':[r['status'] for r in third],
    'business_expectation':'D04-specific dispatcher/dependency additions should not recalculate unrelated historical success/withheld',
    'new_calls':[0,0,0]}
 Path('work/main-g3-consumer/unused-d04-repro.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r,indent=2))
finally:control.doCleanups()
