"""Compare pre-commit tested runtime bytes with the subsequent Git commit."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
COMMIT = 'df9feafac6f1a5ff88145e29b1785117ab067bd1'
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from vnext.requirements import load_requirement_snapshot


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def committed(relative):
    return subprocess.check_output(['git', 'show', f'{COMMIT}:{relative}'], cwd=ROOT)


binding = json.loads((HERE / 'binding-after.json').read_text())
run = json.loads((HERE / 'run.json').read_text())
installed = Path(run['installed_data_root'])
parent = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v13')
child = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
assert parent['requirement_closure_hash'] == binding['parent_closure']
assert child['requirement_closure_hash'] == binding['child_closure']
assert run['requirement_closure_hash'] == binding['parent_closure']
rows = []
for relative in binding['changed_sources']:
    raw = committed(relative)
    assert raw == (ROOT / relative).read_bytes(), relative
    assert raw == (installed / relative).read_bytes(), relative
    assert identity(raw) == parent['execution_authority']['files'][relative], relative
    rows.append({'path': relative, **identity(raw), 'installed_equal': True})
for relative in binding['child_only_paths']:
    raw = committed(relative)
    assert raw == (ROOT / relative).read_bytes(), relative
    assert identity(raw) == child['execution_authority']['files'][relative], relative
    rows.append({'path': relative, **identity(raw), 'installed_equal': None,
                 'reason': 'CLI is child-bound; normal Run installs the parent runtime'})
snapshot_names = ('CONTRACT.md', 'baseline_manifest.json', 'decision_register.json',
                  'invariant_profile.json', 'transfer_manifest.json')
for version in ('issue_28_v13', 'issue_28_v14'):
    for name in snapshot_names:
        relative = f'requirements/{version}/{name}'
        raw = committed(relative)
        assert raw == (ROOT / relative).read_bytes(), relative
        installed_equal = None
        if version == 'issue_28_v13':
            assert raw == (installed / relative).read_bytes(), relative
            installed_equal = True
        rows.append({'path': relative, **identity(raw), 'installed_equal': installed_equal})
for relative in ('tests/vnext/test_c02_auditor_successor.py',
                 'tests/vnext/test_normal_c02_composition.py',
                 'tools/run_fast_tests_v2.py'):
    raw = committed(relative)
    assert raw == (ROOT / relative).read_bytes(), relative
    rows.append({'path': relative, **identity(raw), 'installed_equal': None})
result = {'record_type': 'ISSUE28_TESTED_WORKTREE_COMMIT_BYTE_EQUIVALENCE',
          'status': 'PASS_BYTE_EQUIVALENCE', 'commit': COMMIT,
          'execution_at_commit_claimed': False,
          'original_execution': 'PRE_COMMIT_BOUND_WORKTREE',
          'code_root': str(ROOT), 'installed_data_root': str(installed),
          'parent_closure': binding['parent_closure'],
          'child_closure': binding['child_closure'], 'verified_files': rows,
          'whole_content_or_production_credit': False}
(HERE / 'tested-commit-equivalence.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'commit': COMMIT,
                  'verified_files': len(rows), 'execution_at_commit_claimed': False}))
