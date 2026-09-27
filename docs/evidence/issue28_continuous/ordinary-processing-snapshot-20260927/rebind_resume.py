"""Rebind the unfrozen V14 refresh verifier after bounded resume repair."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = '40bff4570776f04d2ee9b562d23ee33c05f8a429'
HERE = Path(__file__).resolve().parent
MODULE = 'scripts/vnext/ordinary_refresh_cycle.py'
MANIFEST = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)

def identity(path):
    raw = path.read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}

def original(relative):
    return subprocess.check_output(['git', 'show', BASE+':'+relative], cwd=ROOT)

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

manifest = json.loads(MANIFEST.read_text())
old = json.loads(original('requirements/issue_28_v14/baseline_manifest.json'))
old_module = {
    'sha256': hashlib.sha256(original(MODULE)).hexdigest(),
    'size': len(original(MODULE))}
restored = json.loads(json.dumps(manifest))
restored['execution_authority']['files'][MODULE] = old_module
assert restored == old
assert manifest['execution_authority']['files'][MODULE] in (
    old_module, identity(ROOT/MODULE))
old_authority = content_hash(value=manifest['execution_authority'])
for relative in RECEIPTS:
    receipt = json.loads((ROOT/relative).read_text())
    assert receipt['execution_authority_hash'] == old_authority
    old_receipt = json.loads(original(relative))
    for key in old_receipt:
        if key not in {'execution_authority_hash', 'requirement_closure_hash'}:
            assert receipt[key] == old_receipt[key]
manifest['execution_authority']['files'][MODULE] = identity(ROOT/MODULE)
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
write(HERE/'binding-resume-after.json', {
    'base': BASE,
    'module': MODULE,
    'module_identity': identity(ROOT/MODULE),
    'parent_v13_closure': requirement['parent_snapshot']['requirement_closure_hash'],
    'child_v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'receipts_validated': True,
    'calls': [0, 0, 0]})
print(json.dumps({'child_v14_closure': requirement['requirement_closure_hash'],
                  'execution_authority_hash': authority, 'calls': [0, 0, 0]},
                 sort_keys=True))
