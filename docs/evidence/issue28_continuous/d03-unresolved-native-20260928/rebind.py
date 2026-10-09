"""Rebind only the unfrozen V14 D03 acceptance difference and current receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = 'db5a23fdcc54348ffce229afca282766e02f1930'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = ('scripts/vnext/capacity_native_assessment.py',
           'scripts/vnext/d03_native_assessment.py')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative],
                                   cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(relative, value):
    (ROOT / relative).write_text(json.dumps(value, ensure_ascii=False,
                                           indent=2) + '\n')


old = json.loads(previous(MANIFEST))
assert json.loads((ROOT / MANIFEST).read_text()) == old
old_files = old['execution_authority']['files']
assert all(old_files[p] == identity(previous(p)) for p in CHANGED)
updated = json.loads(previous(MANIFEST))
for relative in CHANGED:
    binding = identity((ROOT / relative).read_bytes())
    assert binding != old_files[relative]
    updated['execution_authority']['files'][relative] = binding
    if relative in updated['new_rule_files']:
        updated['new_rule_files'][relative] = binding
write(MANIFEST, updated)

requirement = load_requirement_snapshot(
    snapshot_dir=ROOT / 'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
old_authority = content_hash(value=old['execution_authority'])
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    value = json.loads(previous(relative))
    assert json.loads((ROOT / relative).read_text()) == value
    assert value['execution_authority_hash'] == old_authority
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, value)
validate_wiring_receipt(requirement=requirement)
assert (ROOT / 'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
    previous('requirements/issue_28_v13/baseline_manifest.json')
assert (ROOT / 'scripts/vnext/canonical.py').read_bytes() == \
    previous('scripts/vnext/canonical.py')
print(json.dumps({'status': 'PASS_UNFROZEN_V14_AND_CURRENT_WIRING',
    'base': BASE, 'changed_execution_files': list(CHANGED),
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipt_count': len(RECEIPTS),
    'v13_and_canonical_unchanged': True, 'real_calls': [0, 0, 0]},
    sort_keys=True))
