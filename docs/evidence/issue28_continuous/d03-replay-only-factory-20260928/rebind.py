"""Rebind the current unfrozen V14 D03 factory delta, retaining old bytes."""
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

BASE = 'f6e9e8863f2f25f9955f512e035da1fe7db1618a'
HERE = Path(__file__).resolve().parent
MODULE = 'scripts/vnext/continuous_semantic_calls.py'
MANIFEST = ROOT / 'requirements/issue_28_v14/baseline_manifest.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


manifest = json.loads(MANIFEST.read_text())
assert MANIFEST.read_bytes() == previous('requirements/issue_28_v14/baseline_manifest.json')
old, new = identity(previous(MODULE)), identity((ROOT / MODULE).read_bytes())
assert old != new
assert manifest['execution_authority']['files'][MODULE] == old
assert manifest['new_rule_files'][MODULE] == old
old_authority = content_hash(value=manifest['execution_authority'])
old_closure = json.loads((ROOT / RECEIPTS[0]).read_text())['requirement_closure_hash']
for relative in RECEIPTS:
    path = ROOT / relative
    assert path.read_bytes() == previous(relative)
    value = json.loads(path.read_text())
    assert value['execution_authority_hash'] == old_authority
    assert value.get('requirement_closure_hash', old_closure) == old_closure
write(HERE / 'binding-before.json', {'base': BASE, 'module': old,
    'v14_closure': old_closure, 'execution_authority_hash': old_authority})
manifest['execution_authority']['files'][MODULE] = new
manifest['new_rule_files'][MODULE] = new
write(MANIFEST, manifest)
requirement = load_requirement_snapshot(snapshot_dir=MANIFEST.parent)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT / relative
    value = json.loads(path.read_text())
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(path, value)
validate_wiring_receipt(requirement=requirement)
write(HERE / 'binding-after.json', {'base': BASE, 'module': new,
    'v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipt_count': len(RECEIPTS),
    'new_calls': [0, 0, 0]})
print('PASS V14 execution and provider, SEC, ordinary refresh wiring')
print('requirement_closure_hash', requirement['requirement_closure_hash'])
