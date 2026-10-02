"""Bind only the explicit A05 explanation successor into mutable #28 V13/V14."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

PARENT = ROOT/'requirements/issue_28_v13'
CHILD = ROOT/'requirements/issue_28_v14'
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')
SHARED_CHANGED = (
    'scripts/vnext/normal_run_v3.py',
    'scripts/vnext/ordinary_projection.py',
    'scripts/vnext/ordinary_update_cycle.py')
CHILD_ONLY = (
    'scripts/vnext/ordinary_a05_formula_update.py',
    'tools/vnext_normal_update.py')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json')


def identity(path):
    raw = path.read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


policy = json.loads((ROOT/'config/issue28_normal_results_v2.json').read_text())
assert set(SHARED_CHANGED) <= set(policy['rule_paths'] + policy['presentation_paths'])
assert not set(CHILD_ONLY) & set(policy['rule_paths'] + policy['presentation_paths'])
parent_path, child_path = PARENT/'baseline_manifest.json', CHILD/'baseline_manifest.json'
parent, child = json.loads(parent_path.read_text()), json.loads(child_path.read_text())
old_parent = content_hash(value=parent['execution_authority'])
old_child = content_hash(value=child['execution_authority'])
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash'] == old_child
write(HERE/'binding-before.json', {
    'parent_execution_authority_hash': old_parent,
    'child_execution_authority_hash': old_child,
    'parent_requirement_closure_hash': child['parent']['requirement_closure_hash'],
    'shared_changed_paths': list(SHARED_CHANGED),
    'child_only_paths': list(CHILD_ONLY),
    'old_shared_bindings': {relative: parent['execution_authority']['files'].get(relative)
                            for relative in SHARED_CHANGED}})

for relative in SHARED_CHANGED:
    value = identity(ROOT/relative)
    parent['execution_authority']['files'][relative] = value
    if relative in parent['new_rule_files']:
        parent['new_rule_files'][relative] = value
write(parent_path, parent)
parent_requirement = load_requirement_snapshot(snapshot_dir=PARENT)
validate_execution_authority(repo_root=ROOT, requirement=parent_requirement)

child['parent']['requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name] = identity(PARENT/name)
for relative in (*SHARED_CHANGED, *CHILD_ONLY):
    value = identity(ROOT/relative)
    child['execution_authority']['files'][relative] = value
    if relative in child['new_rule_files']:
        child['new_rule_files'][relative] = value
write(child_path, child)
transfer_path = CHILD/'transfer_manifest.json'
transfer = json.loads(transfer_path.read_text())
transfer['parent_requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
write(transfer_path, transfer)
child_requirement = load_requirement_snapshot(snapshot_dir=CHILD)
validate_execution_authority(repo_root=ROOT, requirement=child_requirement)
validate_semantic_rule_bindings(child_requirement)

new_authority = content_hash(value=child_requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT/relative
    receipt = json.loads(path.read_text())
    receipt['execution_authority_hash'] = new_authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = child_requirement['requirement_closure_hash']
    write(path, receipt)
validate_wiring_receipt(requirement=child_requirement)
write(HERE/'binding-after.json', {
    'parent_requirement_closure_hash': parent_requirement['requirement_closure_hash'],
    'child_requirement_closure_hash': child_requirement['requirement_closure_hash'],
    'child_execution_authority_hash': new_authority,
    'shared_changed_paths': list(SHARED_CHANGED),
    'child_only_paths': list(CHILD_ONLY),
    'receipt_count': len(RECEIPTS),
    'new_real_calls': [0, 0, 0]})
print(json.dumps({'status': 'PASS_EXPLICIT_A05_FORMULA_BINDING',
    'parent': parent_requirement['requirement_closure_hash'],
    'child': child_requirement['requirement_closure_hash'],
    'receipts': len(RECEIPTS)}, sort_keys=True))
