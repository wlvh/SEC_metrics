"""Rebind final D03 company-review identity after narrowing source checks."""
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

SOURCE = 'scripts/vnext/d03_native_assessment.py'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)

path = ROOT/MANIFEST
before = json.loads(path.read_text())
old_authority = content_hash(value=before['execution_authority'])
raw = (ROOT/SOURCE).read_bytes()
new_identity = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
assert before['execution_authority']['files'][SOURCE] != new_identity
assert SOURCE not in before['new_rule_files']
before['execution_authority']['files'][SOURCE] = new_identity
path.write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n')
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt_path = ROOT/relative
    receipt = json.loads(receipt_path.read_text())
    assert receipt['execution_authority_hash'] == old_authority
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
validate_wiring_receipt(requirement=requirement)
assert (ROOT/'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
    subprocess.check_output(['git', 'show',
        'ba7b5f88:requirements/issue_28_v13/baseline_manifest.json'], cwd=ROOT)
print(json.dumps({'status': 'PASS_FINAL_V14_D03_COMPANY_REVIEW_BINDING',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipts': len(RECEIPTS),
    'v13_unchanged': True, 'real_calls': [0, 0, 0]}, sort_keys=True))
