"""Bind the explicit #28 D02 Item 8 successor into mutable V13/V14 only."""
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
SHARED = (
    'catalog/r6/D02_item8_category_28_v1.json',
    'config/issue28_normal_results_v2.json',
    'scripts/vnext/d02_item8_category_28_v1.py',
    'scripts/vnext/d02_text_results_v3.py',
    'scripts/vnext/normal_run_v3.py',
    'scripts/vnext/ordinary_d02_item8_v1.py',
    'scripts/vnext/ordinary_remaining_cases.py',
    'scripts/vnext/ordinary_update_cycle.py',
)
CHILD_ONLY = (
    'scripts/vnext/ordinary_d02_category_update.py',
    'tools/vnext_normal_update.py',
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
assert set(SHARED) <= set(policy['rule_paths'])
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
    'shared_changed_paths': list(SHARED), 'child_only_paths': list(CHILD_ONLY),
    'old_parent_bindings': {relative: parent['execution_authority']['files'].get(relative)
                            for relative in SHARED},
    'peer_source_commit': '104876d6cfae7812d93fd5b8a4bb0e0f97959fff',
    'peer_wired_commit': '36c64ab65e84af5e3f37b8f4b47820516fcec97d',
})

register_path = PARENT/'decision_register.json'
register = json.loads(register_path.read_text())
register['policy'] = policy
write(register_path, register)
parent['new_rule_files'] = {
    relative: identity(ROOT/relative) for relative in policy['rule_paths']}
for relative in set(policy['rule_paths']) | set(SHARED):
    parent['execution_authority']['files'][relative] = identity(ROOT/relative)
write(parent_path, parent)
parent_requirement = load_requirement_snapshot(snapshot_dir=PARENT)
validate_execution_authority(repo_root=ROOT, requirement=parent_requirement)

child['parent']['requirement_closure_hash'] = parent_requirement['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name] = identity(PARENT/name)
for relative in (*SHARED, *CHILD_ONLY):
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
    'shared_changed_paths': list(SHARED), 'child_only_paths': list(CHILD_ONLY),
    'receipt_count': len(RECEIPTS), 'new_real_calls': [0, 0, 0],
    'peer_code_and_terms_are_versioned_own_paths': True,
})
print(json.dumps({'status': 'PASS_D02_VERSIONED_NORMAL_BINDING',
                  'parent': parent_requirement['requirement_closure_hash'],
                  'child': child_requirement['requirement_closure_hash'],
                  'receipts': len(RECEIPTS)}, sort_keys=True))
