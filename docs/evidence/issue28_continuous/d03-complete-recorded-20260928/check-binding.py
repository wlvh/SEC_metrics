"""Verify only the current D03 collector and controller are rebound in V14."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = '5425d51a7356653e1b9e96e5ee78b48d80306925'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = ('scripts/vnext/d03_native_assessment.py',
           'scripts/vnext/continuous_semantic_calls.py')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative],
                                   cwd=ROOT)


old = json.loads(previous(MANIFEST))
expected = json.loads(previous(MANIFEST))
identities = {}
for relative in CHANGED:
    raw = (ROOT/relative).read_bytes()
    binding = {'sha256': hashlib.sha256(raw).hexdigest(),
               'size': len(raw)}
    expected['execution_authority']['files'][relative] = binding
    if relative in expected['new_rule_files']:
        expected['new_rule_files'][relative] = binding
    identities[relative] = binding
assert json.loads((ROOT/MANIFEST).read_text()) == expected
for relative in ('requirements/issue_28_v13/baseline_manifest.json',
                 'scripts/vnext/canonical.py',
                 'config/issue28_continuous_calls_v1.json'):
    assert (ROOT/relative).read_bytes() == previous(relative)

requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
old_authority = content_hash(value=old['execution_authority'])
for relative in RECEIPTS:
    original = json.loads(previous(relative))
    current = json.loads((ROOT/relative).read_text())
    assert original['execution_authority_hash'] == old_authority
    expected_receipt = dict(original)
    expected_receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in expected_receipt:
        expected_receipt['requirement_closure_hash'] = (
            requirement['requirement_closure_hash'])
    assert current == expected_receipt
validate_wiring_receipt(requirement=requirement)

summary = {'status': 'PASS_CURRENT_V14_EXECUTION_AND_WIRING',
    'base': BASE, 'changed_identities': identities,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'receipt_count': len(RECEIPTS),
    'approved_rule_paths_changed': False,
    'v13_or_canonical_changed': False,
    'real_calls': [0, 0, 0]}
Path(__file__).with_name('binding.json').write_text(
    json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, sort_keys=True))
