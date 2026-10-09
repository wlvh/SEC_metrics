"""Refresh only mutable V14 bytes changed by the recorded coverage scan."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = '4ac3e1cc3cd5dfb8774d6292116a5f175f16d6eb'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CAPACITY = 'scripts/vnext/capacity_two_stage.py'
SEMANTIC = 'scripts/vnext/continuous_semantic_calls.py'
POLICY = 'config/ordinary_scalability_exemptions_v1.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def identity(relative):
    raw = (ROOT / relative).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(relative, value):
    (ROOT / relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


policy = json.loads((ROOT / POLICY).read_text())
capacity_identity = identity(CAPACITY)
updated = 0
for row in policy['entries']:
    if row['file'] == CAPACITY and row['literal'] == 'F':
        assert row['line'] in (147, 242, 254, 271)
        row['source_sha256'] = capacity_identity['sha256']
        row['source_size'] = capacity_identity['size']
        updated += 1
assert updated == 4
write(POLICY, policy)

manifest = json.loads((ROOT / MANIFEST).read_text())
assert manifest['new_rule_files'][CAPACITY]['sha256'] == \
       'a1552e5e369f4fa5881c40e20e61b5af8556f5b5c250fa0255d26a5f0422b7a8'
assert manifest['new_rule_files'][SEMANTIC]['sha256'] == \
       'db52f2c8e887564442687aa75fa1dcb18c4d7452610091d8ef471cae03502979'
old_authority = content_hash(value=manifest['execution_authority'])
for relative in (CAPACITY, SEMANTIC):
    for table in (manifest['new_rule_files'], manifest['execution_authority']['files']):
        table[relative] = identity(relative)
manifest['execution_authority']['files'][POLICY] = identity(POLICY)
write(MANIFEST, manifest)
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT / 'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
new_authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt = json.loads((ROOT / relative).read_text())
    assert receipt['execution_authority_hash'] == old_authority
    receipt['execution_authority_hash'] = new_authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, receipt)
validate_wiring_receipt(requirement=requirement)
assert (ROOT / 'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
       subprocess.check_output(['git', 'show', BASE + ':requirements/issue_28_v13/baseline_manifest.json'], cwd=ROOT)
print(json.dumps({'status': 'PASS_V14_RECORDED_COVERAGE_SCAN_BINDING',
    'base': BASE, 'capacity': capacity_identity, 'semantic': identity(SEMANTIC),
    'policy': identity(POLICY),
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': new_authority,
    'receipts': len(RECEIPTS), 'v13_unchanged': True,
    'new_real_calls': [0, 0, 0]}, sort_keys=True))
