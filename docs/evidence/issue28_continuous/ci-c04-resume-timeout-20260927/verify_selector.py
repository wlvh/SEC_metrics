"""Check the scoped source-material timeout without rerunning the long case."""
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts'), str(ROOT / 'tools')]
from tools import run_fast_tests_v2 as runner

NAME = 'tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest'
assert runner.SOURCE_TIMEOUT_SECONDS == 240
assert runner.SOURCE_TIMEOUT_OVERRIDES[NAME] == 360
assert runner.SOURCE_TIMEOUT_OVERRIDES[
    'tests.vnext.test_d03_recorded_response_store.D03RecordedResponseStoreTest'] == 300
assert runner.SOURCE_TESTS.count(NAME) == 1
assert NAME in runner._selected_tests('source-material', 1, 2)
with patch.object(runner.subprocess, 'run', return_value=
                  subprocess.CompletedProcess([sys.executable], 0, '', '')) as call:
    checked = runner._run_source_case(NAME)
assert checked['return_code'] == 0 and checked['timeout_seconds'] == 360
assert call.call_args.kwargs['timeout'] == 360
print('PASS_C04_RESUME_SCOPED_360_SECOND_SELECTOR; '
      'global_240_D03_300_other_overrides_unchanged; long_material_not_rerun')
