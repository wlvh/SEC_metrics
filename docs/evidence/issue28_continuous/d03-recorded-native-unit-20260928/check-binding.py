"""Verify the unfrozen V14 binding diff and current offline wiring."""
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

BASE = '29b401d73937c0b9014098274568dfae3748d5bd'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = (
    'scripts/vnext/continuous_semantic_calls.py',
    'scripts/vnext/capacity_native_assessment.py',
    'scripts/vnext/native_assessment_replay.py',
    'scripts/vnext/native_request_construction.py',
    'scripts/vnext/regulatory_fact_review.py',
)
ADDED = (
    'scripts/vnext/d03_native_assessment.py',
    'catalog/r6/D03_regulatory_investigations_assessment_v1.md',
)
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


original = json.loads(previous(MANIFEST))
actual = json.loads((ROOT / MANIFEST).read_text())
expected = json.loads(previous(MANIFEST))
changed_identities = {}
for relative in (*CHANGED, *ADDED):
    binding = identity((ROOT / relative).read_bytes())
    expected['execution_authority']['files'][relative] = binding
    if relative in expected['new_rule_files']:
        expected['new_rule_files'][relative] = binding
    changed_identities[relative] = binding
assert actual == expected
assert all(relative not in original['new_rule_files'] for relative in ADDED)
for relative in ('requirements/issue_28_v13/baseline_manifest.json',
                 'scripts/vnext/canonical.py',
                 'config/issue28_continuous_calls_v1.json'):
    assert (ROOT / relative).read_bytes() == previous(relative)

requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
previous_authority = content_hash(value=original['execution_authority'])
for relative in RECEIPTS:
    old = json.loads(previous(relative))
    current = json.loads((ROOT / relative).read_text())
    assert old['execution_authority_hash'] == previous_authority
    expected_receipt = dict(old)
    expected_receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in expected_receipt:
        expected_receipt['requirement_closure_hash'] = (
            requirement['requirement_closure_hash'])
    assert current == expected_receipt
validate_wiring_receipt(requirement=requirement)

summary = {
    'status': 'PASS_V14_EXECUTION_AND_OFFLINE_WIRING',
    'base': BASE,
    'changed_or_added_file_identities': changed_identities,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'receipt_count': len(RECEIPTS),
    'approved_rule_paths_changed': False,
    'v13_or_canonical_changed': False,
    'real_calls': [0, 0, 0],
}
Path(__file__).with_name('binding.json').write_text(
    json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, sort_keys=True))
