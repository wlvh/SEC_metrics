"""Rebind current V14 after failed preclaim admission stops later updates."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
RELATIVE = 'scripts/vnext/ordinary_refresh_cycle.py'
MANIFEST = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
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


prior = json.loads((HERE/'resume-lock-binding-failed.json').read_text())
manifest = json.loads(MANIFEST.read_text())
assert manifest['execution_authority']['files'][RELATIVE] == prior['after']
assert content_hash(value=manifest['execution_authority']) == prior['execution_authority_hash']
assert load_requirement_snapshot(snapshot_dir=MANIFEST.parent)[
    'requirement_closure_hash'] == prior['child_closure']
after = identity(ROOT/RELATIVE)
assert after != prior['after']
for relative in RECEIPTS:
    receipt = json.loads((ROOT/relative).read_text())
    assert receipt['execution_authority_hash'] == prior['execution_authority_hash']
manifest['execution_authority']['files'][RELATIVE] = after
write(MANIFEST, manifest)
requirement = load_requirement_snapshot(snapshot_dir=MANIFEST.parent)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT/relative
    receipt = json.loads(path.read_text())
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(path, receipt)
validate_wiring_receipt(requirement=requirement)
write(HERE/'resume-lock-binding.json', {
    'file': RELATIVE, 'before': prior['after'], 'after': after,
    'parent_closure_unchanged': prior['parent_closure_unchanged'],
    'child_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'provider_sec_refresh_receipts_validated': True,
    'new_real_calls': [0, 0, 0],
})
print(json.dumps({'child_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority}, sort_keys=True))
