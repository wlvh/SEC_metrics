"""Bind the explicit B03 repair only in mutable V14, preserving V13 bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

V13 = Path('requirements/issue_28_v13')
V14 = Path('requirements/issue_28_v14')
POLICY = 'config/issue28_continuous_calls_v1.json'
PRESERVED = [*(str(V13/name) for name in (
    'CONTRACT.md', 'decision_register.json', 'invariant_profile.json',
    'baseline_manifest.json', 'transfer_manifest.json')),
    'config/issue28_normal_results_v2.json',
    'scripts/vnext/normal_run_v3.py',
    'scripts/vnext/run_store.py',
    'scripts/vnext/ordinary_projection.py']
NEW = (
    'catalog/r6/B03_impairment_excluded_v1.md',
    'scripts/vnext/b03_exact_impairment_relation.py',
    'scripts/vnext/b03_impairment_adjusted_run.py',
)
CHANGED = (POLICY, 'scripts/vnext/ordinary_b03_scope_update.py')
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


for relative in PRESERVED:
    before = subprocess.check_output(['git', 'show', 'HEAD:' + relative],
                                      cwd=ROOT)
    assert (ROOT/relative).read_bytes() == before, relative
path = ROOT/V14/'baseline_manifest.json'
manifest = json.loads(path.read_text())
assert manifest['parent']['snapshot_files']['baseline_manifest.json'] == \
    identity(ROOT/V13/'baseline_manifest.json')
old_authority = content_hash(value=manifest['execution_authority'])
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash'] == old_authority
write(HERE/'binding-v14-before.json', {
    'v13_parent_closure': manifest['parent']['requirement_closure_hash'],
    'v14_execution_authority_hash': old_authority,
    'new_files': list(NEW), 'changed_files': list(CHANGED),
    'v13_and_shared_defaults_byte_identical_to_head': True})
policy_path = ROOT/POLICY
policy = json.loads(policy_path.read_text())
for relative in (*NEW, *CHANGED):
    if relative not in policy['rule_paths']:
        policy['rule_paths'].append(relative)
write(policy_path, policy)
register_path = ROOT/V14/'decision_register.json'
register = json.loads(register_path.read_text())
register['policy'] = policy
write(register_path, register)
for relative in (*NEW, *CHANGED):
    manifest['execution_authority']['files'][relative] = identity(ROOT/relative)
    manifest['new_rule_files'][relative] = identity(ROOT/relative)
write(path, manifest)
requirement = load_requirement_snapshot(snapshot_dir=ROOT/V14)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt = ROOT/relative
    value = json.loads(receipt.read_text())
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(receipt, value)
validate_wiring_receipt(requirement=requirement)
write(HERE/'binding-v14-after.json', {
    'v13_parent_closure': requirement['parent_snapshot']['requirement_closure_hash'],
    'v14_requirement_closure_hash': requirement['requirement_closure_hash'],
    'v14_execution_authority_hash': authority,
    'new_files': list(NEW), 'changed_files': list(CHANGED),
    'v13_and_shared_defaults_byte_identical_to_head': True,
    'receipt_count': len(RECEIPTS), 'new_real_calls': [0, 0, 0]})
print(json.dumps({'status': 'PASS_EXPLICIT_B03_V14_ONLY',
    'v14_closure': requirement['requirement_closure_hash'],
    'v13_unchanged': True, 'receipts': len(RECEIPTS)}, sort_keys=True))
