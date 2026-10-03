"""Refresh only the current processing-copy and SEC initializer bindings."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

HERE = Path(__file__).resolve().parent
BASE = 'b686814f586bc4ba7471e00218a54773645cc48e'
PARENT = ROOT/'requirements/issue_28_v13/baseline_manifest.json'
CHILD = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
TRANSFER = ROOT/'requirements/issue_28_v14/transfer_manifest.json'
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')
CURRENT = ('scripts/vnext/ordinary_processing_source.py',
           'scripts/vnext/continuous_sec_acquisition.py')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def ident(path):
    raw = path.read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def base(relative):
    return json.loads(subprocess.check_output(
        ['git', 'show', BASE + ':' + relative], cwd=ROOT))


parent = json.loads(PARENT.read_text())
child = json.loads(CHILD.read_text())
original_parent = base('requirements/issue_28_v13/baseline_manifest.json')
original_child = base('requirements/issue_28_v14/baseline_manifest.json')
for path, value in original_parent['execution_authority']['files'].items():
    if path != 'scripts/vnext/ordinary_update_cycle.py':
        assert parent['execution_authority']['files'][path] == value
for path, value in original_child['execution_authority']['files'].items():
    if path not in {'scripts/vnext/ordinary_update_cycle.py',
                    'scripts/vnext/ordinary_refresh_cycle.py'}:
        assert child['execution_authority']['files'][path] == value
for path in CURRENT:
    assert path in parent['execution_authority']['files']
    assert path in child['execution_authority']['files']
assert child['new_rule_files']['scripts/vnext/continuous_sec_acquisition.py'] == \
       original_child['new_rule_files']['scripts/vnext/continuous_sec_acquisition.py']
old_authority = content_hash(value=child['execution_authority'])
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash'] == old_authority
write(HERE/'binding-delta-before.json', {'parent_closure': child['parent']['requirement_closure_hash'],
    'execution_authority_hash': old_authority,
    'files': {path: parent['execution_authority']['files'][path] for path in CURRENT}})

for path in CURRENT:
    parent['execution_authority']['files'][path] = ident(ROOT/path)
write(PARENT, parent)
parent_requirement = load_requirement_snapshot(snapshot_dir=PARENT.parent)
validate_execution_authority(repo_root=ROOT, requirement=parent_requirement)
child['parent']['requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name] = ident(PARENT.parent/name)
for path in CURRENT:
    child['execution_authority']['files'][path] = ident(ROOT/path)
child['new_rule_files']['scripts/vnext/continuous_sec_acquisition.py'] = \
    ident(ROOT/'scripts/vnext/continuous_sec_acquisition.py')
write(CHILD, child)
transfer = json.loads(TRANSFER.read_text())
transfer['parent_requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
write(TRANSFER, transfer)
child_requirement = load_requirement_snapshot(snapshot_dir=CHILD.parent)
validate_execution_authority(repo_root=ROOT, requirement=child_requirement)
authority = content_hash(value=child_requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT/relative
    receipt = json.loads(path.read_text())
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = child_requirement['requirement_closure_hash']
    write(path, receipt)
validate_wiring_receipt(requirement=child_requirement)
write(HERE/'binding-delta-after.json', {
    'parent_closure': parent_requirement['requirement_closure_hash'],
    'child_closure': child_requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'files': {path: ident(ROOT/path) for path in CURRENT},
    'default_behavior_changed': False, 'frozen_v12_modified': False,
    'calls': [0, 0, 0]})
print(json.dumps({'parent_closure': parent_requirement['requirement_closure_hash'],
    'child_closure': child_requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'calls': [0, 0, 0]}, sort_keys=True))
