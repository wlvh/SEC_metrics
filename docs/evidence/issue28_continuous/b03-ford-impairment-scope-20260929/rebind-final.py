"""Bind the final B03 source docstring bytes without changing the rule."""
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

manifest_path = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
preceding_log = ROOT/'docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/binding-followup.log'
source = 'scripts/vnext/b03_depreciation_scope.py'
receipts = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)

manifest = json.loads(manifest_path.read_text())
prior_authority = json.loads(preceding_log.read_text())['execution_authority_hash']
raw = (ROOT/source).read_bytes()
identity = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
manifest['execution_authority']['files'][source] = identity
if source in manifest['new_rule_files']:
    manifest['new_rule_files'][source] = identity
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in receipts:
    path = ROOT/relative
    receipt = json.loads(path.read_text())
    assert receipt['execution_authority_hash'] == prior_authority
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
validate_wiring_receipt(requirement=requirement)
print(json.dumps({'status': 'PASS_FINAL_V14_B03_BINDING',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipts': len(receipts)},
    sort_keys=True))
