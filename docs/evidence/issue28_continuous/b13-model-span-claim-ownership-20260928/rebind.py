"""Rebind only the current unfrozen V14 B13 model-span validator increment."""

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


BASE = 'ba56a51fb069ff53c4b9a831b901c4323c06d534'
HERE = Path(__file__).resolve().parent
MANIFEST = ROOT / 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = ('scripts/vnext/capacity_two_stage.py',)
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def from_base(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


manifest = json.loads(MANIFEST.read_text())
assert MANIFEST.read_bytes() == from_base('requirements/issue_28_v14/baseline_manifest.json')
old_authority = content_hash(value=manifest['execution_authority'])
old_closure = json.loads((ROOT / RECEIPTS[0]).read_text())['requirement_closure_hash']
before = {}
after = {}
for relative in CHANGED:
    old = identity(from_base(relative))
    new = identity((ROOT / relative).read_bytes())
    assert new != old
    assert manifest['execution_authority']['files'][relative] == old
    if relative in manifest['new_rule_files']:
        assert manifest['new_rule_files'][relative] == old
    before[relative], after[relative] = old, new
for relative in RECEIPTS:
    path = ROOT / relative
    assert path.read_bytes() == from_base(relative)
    receipt = json.loads(path.read_text())
    assert receipt['execution_authority_hash'] == old_authority
    assert receipt.get('requirement_closure_hash', old_closure) == old_closure

write(HERE / 'binding-before.json', {'base': BASE, 'files': before,
    'v14_closure': old_closure, 'execution_authority_hash': old_authority})
for relative, new in after.items():
    manifest['execution_authority']['files'][relative] = new
    if relative in manifest['new_rule_files']:
        manifest['new_rule_files'][relative] = new
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
write(HERE / 'binding-after.json', {'base': BASE, 'files': after,
    'v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'provider_paid_sec_calls': [0, 0, 0],
    'current_provider_sec_refresh_receipts_validated': True,
    'v13_default_modified': False})
print(json.dumps({'changed_files': list(CHANGED),
    'v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority}, sort_keys=True))
