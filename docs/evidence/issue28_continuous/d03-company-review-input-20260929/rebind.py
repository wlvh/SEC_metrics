"""Rebind only the changed unfrozen D03 execution module and current receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = 'ba7b5f88e4067c4d4c0c774127c8e71887b9ba29'
SOURCE = 'scripts/vnext/d03_native_assessment.py'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)


def write(relative, value):
    (ROOT/relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


before = json.loads(previous(MANIFEST))
assert json.loads((ROOT/MANIFEST).read_text()) == before
assert SOURCE not in before['new_rule_files']
assert before['execution_authority']['files'][SOURCE] == {
    'sha256': hashlib.sha256(previous(SOURCE)).hexdigest(),
    'size': len(previous(SOURCE))}
raw = (ROOT/SOURCE).read_bytes()
updated = json.loads(previous(MANIFEST))
updated['execution_authority']['files'][SOURCE] = {
    'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
write(MANIFEST, updated)
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
old_authority = content_hash(value=before['execution_authority'])
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt = json.loads(previous(relative))
    assert json.loads((ROOT/relative).read_text()) == receipt
    assert receipt['execution_authority_hash'] == old_authority
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, receipt)
validate_wiring_receipt(requirement=requirement)
assert (ROOT/'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
    previous('requirements/issue_28_v13/baseline_manifest.json')
print(json.dumps({'status': 'PASS_CURRENT_V14_D03_COMPANY_REVIEW_BINDING',
    'base': BASE, 'changed_execution_file': SOURCE,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'receipts': len(RECEIPTS), 'v13_unchanged': True,
    'real_calls': [0, 0, 0]}, sort_keys=True))
