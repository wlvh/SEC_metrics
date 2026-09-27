"""Rebind only current unfrozen #28 source-processing successor bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.canonical import content_hash, sha256_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

HERE = Path(__file__).resolve().parent
BASE = 'b686814f586bc4ba7471e00218a54773645cc48e'
PARENT_CHANGED = ('scripts/vnext/ordinary_update_cycle.py',)
CHILD_CHANGED = (*PARENT_CHANGED, 'scripts/vnext/ordinary_refresh_cycle.py')
NEW = 'scripts/vnext/ordinary_processing_source.py'
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def identity(path):
    raw = path.read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def base_identity(relative):
    raw = subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


parent_dir = ROOT/'requirements/issue_28_v13'
child_dir = ROOT/'requirements/issue_28_v14'
parent_path = parent_dir/'baseline_manifest.json'
child_path = child_dir/'baseline_manifest.json'
parent = json.loads(parent_path.read_text())
child = json.loads(child_path.read_text())
old_authority = content_hash(value=child['execution_authority'])
before = {}
for relative in CHILD_CHANGED:
    old = base_identity(relative)
    if relative in PARENT_CHANGED:
        assert parent['execution_authority']['files'][relative] == old
        assert parent['new_rule_files'][relative] == old
    assert child['execution_authority']['files'][relative] == old
    before[relative] = old
assert NEW not in parent['execution_authority']['files']
assert NEW not in parent['new_rule_files']
assert NEW not in child['execution_authority']['files']
for name in PARENT_FILES:
    relative = 'requirements/issue_28_v13/' + name
    assert identity(ROOT/relative) == base_identity(relative)
    assert child['parent']['snapshot_files'][name] == identity(ROOT/relative)
for relative in RECEIPTS:
    path = ROOT/relative
    assert identity(path) == base_identity(relative)
    assert json.loads(path.read_text())['execution_authority_hash'] == old_authority
write(HERE/'binding-before.json', {'base': BASE,
    'parent_closure': child['parent']['requirement_closure_hash'],
    'execution_authority_hash': old_authority, 'files': before})

for relative in PARENT_CHANGED:
    new = identity(ROOT/relative)
    assert new != before[relative]
    parent['execution_authority']['files'][relative] = new
    parent['new_rule_files'][relative] = new
parent['execution_authority']['files'][NEW] = identity(ROOT/NEW)
write(parent_path, parent)
parent_requirement = load_requirement_snapshot(snapshot_dir=parent_dir)
validate_execution_authority(repo_root=ROOT, requirement=parent_requirement)

child['parent']['requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name] = identity(parent_dir/name)
for relative in CHILD_CHANGED:
    child['execution_authority']['files'][relative] = identity(ROOT/relative)
child['execution_authority']['files'][NEW] = identity(ROOT/NEW)
write(child_path, child)
transfer_path = child_dir/'transfer_manifest.json'
transfer = json.loads(transfer_path.read_text())
transfer['parent_requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
write(transfer_path, transfer)
child_requirement = load_requirement_snapshot(snapshot_dir=child_dir)
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
after = {'base': BASE,
    'parent_closure': parent_requirement['requirement_closure_hash'],
    'child_closure': child_requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'files': {relative: identity(ROOT/relative)
              for relative in (*CHILD_CHANGED, NEW)},
    'frozen_v12_modified': False, 'old_default_arguments_changed': False,
    'provider_sec_refresh_receipts_validated': True, 'calls': [0, 0, 0]}
write(HERE/'binding-after.json', after)
print(json.dumps({key: after[key] for key in
    ('parent_closure', 'child_closure', 'execution_authority_hash', 'calls')},
    sort_keys=True))
