"""Rebind current #28 V13/V14 after atomic C04 resume predecessor repair."""

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
BASE = '45cdbacaa4c3b617194807b04d3dbd540650282c'
PARENT_CHANGED = 'scripts/vnext/continuous_sec_acquisition.py'
CHILD_CHANGED = 'scripts/vnext/ordinary_refresh_cycle.py'
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def base(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


parent_dir = ROOT/'requirements/issue_28_v13'
child_dir = ROOT/'requirements/issue_28_v14'
parent_path = parent_dir/'baseline_manifest.json'
child_path = child_dir/'baseline_manifest.json'
transfer_path = child_dir/'transfer_manifest.json'
parent = json.loads(parent_path.read_text())
child = json.loads(child_path.read_text())
assert parent_path.read_bytes() == base('requirements/issue_28_v13/baseline_manifest.json')
assert child_path.read_bytes() == base('requirements/issue_28_v14/baseline_manifest.json')
assert transfer_path.read_bytes() == base('requirements/issue_28_v14/transfer_manifest.json')
old_authority = content_hash(value=child['execution_authority'])
before = {relative: identity(base(relative)) for relative in
          (PARENT_CHANGED, CHILD_CHANGED)}
after = {relative: identity((ROOT/relative).read_bytes()) for relative in before}
assert all(before[relative] != after[relative] for relative in before)
assert parent['execution_authority']['files'][PARENT_CHANGED] == before[PARENT_CHANGED]
assert child['execution_authority']['files'][PARENT_CHANGED] == before[PARENT_CHANGED]
assert child['execution_authority']['files'][CHILD_CHANGED] == before[CHILD_CHANGED]
assert child['new_rule_files'][PARENT_CHANGED] == before[PARENT_CHANGED]
for name in PARENT_FILES:
    relative = 'requirements/issue_28_v13/' + name
    assert identity((ROOT/relative).read_bytes()) == identity(base(relative))
    assert child['parent']['snapshot_files'][name] == identity(base(relative))
for relative in RECEIPTS:
    path = ROOT/relative
    assert path.read_bytes() == base(relative)
    assert json.loads(path.read_text())['execution_authority_hash'] == old_authority
write(HERE/'atomic-binding-before.json', {'base': BASE,
    'parent_closure': child['parent']['requirement_closure_hash'],
    'execution_authority_hash': old_authority, 'files': before})

parent['execution_authority']['files'][PARENT_CHANGED] = after[PARENT_CHANGED]
write(parent_path, parent)
parent_requirement = load_requirement_snapshot(snapshot_dir=parent_dir)
validate_execution_authority(repo_root=ROOT, requirement=parent_requirement)

child['parent']['requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name] = identity((parent_dir/name).read_bytes())
for relative in (PARENT_CHANGED, CHILD_CHANGED):
    child['execution_authority']['files'][relative] = after[relative]
child['new_rule_files'][PARENT_CHANGED] = after[PARENT_CHANGED]
write(child_path, child)
transfer = json.loads(transfer_path.read_text())
transfer['parent_requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
write(transfer_path, transfer)

requirement = load_requirement_snapshot(snapshot_dir=child_dir)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT/relative
    receipt = json.loads(path.read_text())
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(path, receipt)
validate_wiring_receipt(requirement=requirement)
write(HERE/'atomic-binding-after.json', {'base': BASE,
    'parent_closure': parent_requirement['requirement_closure_hash'],
    'child_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'files': after,
    'default_capture_parameters_unchanged': True,
    'resume_predecessor_only_in_explicit_c04_mixed_resume': True,
    'provider_sec_refresh_receipts_validated': True,
    'new_real_calls': [0, 0, 0]})
print(json.dumps({'parent_closure': parent_requirement['requirement_closure_hash'],
    'child_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority}, sort_keys=True))
