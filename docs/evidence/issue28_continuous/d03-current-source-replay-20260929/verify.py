"""Bind final D03 replay evidence to actual current files and test exits."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirements import load_requirement_snapshot

FILES = (
    'scripts/vnext/continuous_semantic_calls.py',
    'scripts/vnext/r6_regulatory_semantics.py',
    'scripts/vnext/d03_native_assessment.py',
    'requirements/issue_28_v14/baseline_manifest.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
    'tests/vnext/test_d03_current_source_replay.py',
    'tools/run_fast_tests_v2.py',
)
for name in ('test', 'compat', 'fast', 'material-compat'):
    assert (HERE/(name+'.exit')).read_text().strip() == '0'
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_wiring_receipt(requirement=requirement)
v13 = 'requirements/issue_28_v13/baseline_manifest.json'
assert (ROOT/v13).read_bytes() == subprocess.check_output(
    ['git', 'show', 'HEAD:'+v13], cwd=ROOT)
paths = subprocess.check_output(['git', 'diff', '--name-only'],
    cwd=ROOT, text=True).splitlines()
body = {'record_type': 'D03_CURRENT_SOURCE_REPLAY_FINAL_TREE',
    'code_root': str(ROOT),
    'tested_tree_base_commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'uncommitted_tracked_paths': paths,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'file_sha256': {relative: hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
                    for relative in FILES},
    'v13_manifest_unchanged': True,
    'test_exits': {name: 0 for name in ('test', 'compat', 'fast',
                                      'material-compat')},
    'recorded_test_only': True,
    'new_real_calls': [0, 0, 0],
    'native_company_result_created': False,
    'production_authorized': False}
(HERE/'verification.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'status': 'PASS',
    'requirement_closure_hash': body['requirement_closure_hash'],
    'tracked_diff_count': len(paths), 'file_count': len(FILES)},
    sort_keys=True))
