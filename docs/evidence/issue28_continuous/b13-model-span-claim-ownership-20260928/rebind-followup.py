"""Rebind the unfrozen V14 execution set for the reviewed B13 follow-up."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = '7676f49d37c02e6bfe597d44ba333cfc4222daab'
HERE = Path(__file__).resolve().parent
MODULE = 'scripts/vnext/capacity_two_stage.py'
MANIFEST = ROOT / 'requirements/issue_28_v14/baseline_manifest.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(path):
    return subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT)


def file_id(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


manifest = json.loads(MANIFEST.read_text())
assert MANIFEST.read_bytes() == previous('requirements/issue_28_v14/baseline_manifest.json')
old = file_id(previous(MODULE))
new = file_id((ROOT / MODULE).read_bytes())
assert old != new
assert manifest['execution_authority']['files'][MODULE] == old
assert manifest['new_rule_files'][MODULE] == old
old_authority = content_hash(value=manifest['execution_authority'])
old_closure = json.loads((ROOT / RECEIPTS[0]).read_text())['requirement_closure_hash']
for relative in RECEIPTS:
    path = ROOT / relative
    assert path.read_bytes() == previous(relative)
    receipt = json.loads(path.read_text())
    assert receipt['execution_authority_hash'] == old_authority
    assert receipt.get('requirement_closure_hash', old_closure) == old_closure
write(HERE / 'followup-binding-before.json', {'base': BASE, 'module': old,
    'v14_closure': old_closure, 'execution_authority_hash': old_authority})
manifest['execution_authority']['files'][MODULE] = new
manifest['new_rule_files'][MODULE] = new
write(MANIFEST, manifest)
requirement = load_requirement_snapshot(snapshot_dir=MANIFEST.parent)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT / relative
    receipt = json.loads(path.read_text())
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(path, receipt)
validate_wiring_receipt(requirement=requirement)
write(HERE / 'followup-binding-after.json', {'base': BASE, 'module': new,
    'v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipt_count': len(RECEIPTS),
    'new_calls': [0, 0, 0]})
print('PASS V14 execution and provider, SEC, ordinary refresh wiring')
print('requirement_closure_hash', requirement['requirement_closure_hash'])
