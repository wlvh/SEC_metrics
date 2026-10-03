"""Refresh only mutable #28 V13/V14 authority for explicit C02 composition."""
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
CHANGED = (
    'catalog/r6/C02_board_composition_terms_v1.json',
    'catalog/r6/C02_board_disclosures_v2.md',
    'config/issue28_normal_results_v2.json',
    'scripts/vnext/c02_composition_text_results.py',
    'scripts/vnext/historical_board_composition.py',
    'scripts/vnext/normal_run_v3.py',
    'scripts/vnext/ordinary_remaining_cases.py',
    'scripts/vnext/ordinary_update_cycle.py',
)
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


policy = json.loads((ROOT/'config/issue28_normal_results_v2.json').read_text())
assert policy['rule_paths'] == sorted(set(policy['rule_paths']))
assert policy['metric_spec_paths']['C02'] == [
    'catalog/r6/C02_board_disclosures_v1.md',
    'catalog/r6/C02_board_disclosures_v2.md']
assert set(CHANGED) <= set(policy['rule_paths'])

parent_path = PARENT/'baseline_manifest.json'
child_path = CHILD/'baseline_manifest.json'
parent = json.loads(parent_path.read_text())
child = json.loads(child_path.read_text())
old_parent = content_hash(value=parent['execution_authority'])
old_child = content_hash(value=child['execution_authority'])
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash'] == old_child
write(HERE/'binding-before-peer60aa.json', {
    'parent_execution_authority_hash': old_parent,
    'child_execution_authority_hash': old_child,
    'parent_requirement_closure_hash': child['parent']['requirement_closure_hash'],
    'changed_paths': list(CHANGED),
    'old_bindings': {relative: parent['execution_authority']['files'].get(relative)
                     for relative in CHANGED}})

register_path = PARENT/'decision_register.json'
register = json.loads(register_path.read_text())
register['policy'] = policy
write(register_path, register)
parent['new_rule_files'] = {
    relative: identity(ROOT/relative) for relative in policy['rule_paths']}
for relative in policy['rule_paths']:
    parent['execution_authority']['files'][relative] = identity(ROOT/relative)
write(parent_path, parent)
parent_requirement = load_requirement_snapshot(snapshot_dir=PARENT)
validate_execution_authority(repo_root=ROOT, requirement=parent_requirement)

child['parent']['requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name] = identity(PARENT/name)
for relative in CHANGED:
    child['execution_authority']['files'][relative] = identity(ROOT/relative)
    if relative in child['new_rule_files']:
        child['new_rule_files'][relative] = identity(ROOT/relative)
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
write(HERE/'binding-after-peer60aa.json', {
    'parent_requirement_closure_hash': parent_requirement['requirement_closure_hash'],
    'child_requirement_closure_hash': child_requirement['requirement_closure_hash'],
    'child_execution_authority_hash': new_authority,
    'changed_paths': list(CHANGED),
    'receipt_count': len(RECEIPTS),
    'new_real_calls': [0, 0, 0],
    'default_binding_compatibility_test_pending': True})
print(json.dumps({'status': 'PASS_C02_COMPOSITION_CURRENT_BINDING',
    'parent': parent_requirement['requirement_closure_hash'],
    'child': child_requirement['requirement_closure_hash'],
    'receipts': len(RECEIPTS)}, sort_keys=True))
