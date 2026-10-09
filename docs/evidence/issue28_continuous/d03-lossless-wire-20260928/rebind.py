"""Rebind the current V14 draft after D03's lossless wire repair."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = 'b5b2a91b410a10b2982ec6b469899123d9548ffc'
CHANGED = 'scripts/vnext/continuous_semantic_calls.py'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
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


manifest_path = ROOT / MANIFEST
old_manifest = json.loads(previous(MANIFEST))
manifest = json.loads(manifest_path.read_text())
old = identity(previous(CHANGED))
new = identity((ROOT / CHANGED).read_bytes())
assert old != new
for group in ('new_rule_files',):
    assert old_manifest[group][CHANGED] == old
    assert manifest[group][CHANGED] == new
assert old_manifest['execution_authority']['files'][CHANGED] == old
assert manifest['execution_authority']['files'][CHANGED] == new
expected = json.loads(previous(MANIFEST))
expected['new_rule_files'][CHANGED] = new
expected['execution_authority']['files'][CHANGED] = new
assert manifest == expected
old_authority = content_hash(value=old_manifest['execution_authority'])
for relative in RECEIPTS:
    path = ROOT / relative
    assert path.read_bytes() == previous(relative)
    value = json.loads(path.read_text())
    assert value['execution_authority_hash'] == old_authority
    if 'requirement_closure_hash' in value:
        assert value['requirement_closure_hash'] == (
            'sha256:9563d906e54e5f5cdd9e1dda138c5db49db204cb69de6f4eac680b6f5169a4f1')

requirement = load_requirement_snapshot(snapshot_dir=manifest_path.parent)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    path = ROOT / relative
    value = json.loads(path.read_text())
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(path, value)
validate_wiring_receipt(requirement=requirement)
write(Path(__file__).with_name('binding.json'), {
    'base': BASE, 'changed_module_before': old, 'changed_module_after': new,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipt_count': len(RECEIPTS),
    'real_calls': [0, 0, 0],
})
print('PASS current V14 execution, semantic rules and provider/SEC/refresh wiring')
print('requirement_closure_hash', requirement['requirement_closure_hash'])
