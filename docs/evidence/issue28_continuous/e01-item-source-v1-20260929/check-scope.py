"""Confirm the opt-in source component did not alter frozen E01 defaults."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = '237c7cf4c949a9c58bf857cd406e41ad6ec237d0'
paths = ['scripts/vnext/deterministic_router.py',
    'scripts/vnext/normal_zero_ai_results.py',
    'catalog/event_routes.json',
    'requirements/issue_28_v13/baseline_manifest.json',
    'requirements/issue_28_v14/baseline_manifest.json']
checks = {}
for path in paths:
    current = (ROOT/path).read_bytes()
    saved = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)
    checks[path] = {'unchanged': current == saved,
        'sha256': hashlib.sha256(current).hexdigest()}
assert all(row['unchanged'] for row in checks.values())
assert 'scripts/vnext/e01_item_source.py' not in (
    ROOT/'requirements/issue_28_v14/baseline_manifest.json').read_text()
runner_diff = subprocess.check_output(
    ['git', 'diff', BASE, '--', 'tools/run_fast_tests_v2.py'], cwd=ROOT,
    text=True)
assert runner_diff.count('+FAST_TESTS += ("tests.vnext.test_e01_item_source.E01ItemSourceTest",)') == 1
assert not any(line.startswith('-') and not line.startswith('---')
               for line in runner_diff.splitlines())
body = {'record_type': 'ISSUE28_E01_801_OPT_IN_COMPONENT_SCOPE_CHECK',
    'base_commit': BASE,
    'existing_default_and_frozen_files': checks,
    'new_module_sha256': hashlib.sha256((ROOT/'scripts/vnext/e01_item_source.py').read_bytes()).hexdigest(),
    'current_V14_runtime_binding_includes_new_module': False,
    'fast_selector_appended_once_without_runner_body_change': True,
    'current_E01_result_or_route_changed': False,
    'new_real_calls': [0, 0, 0]}
(HERE/'scope.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'unchanged_existing_files': len(checks),
    'runtime_bound': False, 'selector_appended_once': True}, sort_keys=True))
