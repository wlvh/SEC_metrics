"""Bind only the unfrozen V14 D03 current-source replay increment."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

FILES = (
    'scripts/vnext/continuous_semantic_calls.py',
    'scripts/vnext/r6_regulatory_semantics.py',
    'scripts/vnext/d03_native_assessment.py',
)
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)

path = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
manifest = json.loads(path.read_text())
old_authority = content_hash(value=manifest['execution_authority'])
for relative in FILES:
    raw = (ROOT/relative).read_bytes()
    identity = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
    assert relative in manifest['execution_authority']['files']
    manifest['execution_authority']['files'][relative] = identity
    if relative in manifest['new_rule_files']:
        manifest['new_rule_files'][relative] = identity
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')

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
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
validate_wiring_receipt(requirement=requirement)
print(json.dumps({'status':'PASS_V14_D03_CURRENT_SOURCE_REPLAY_BINDING',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'files': list(FILES),
    'receipts': len(RECEIPTS), 'new_real_calls': [0,0,0]},sort_keys=True))
