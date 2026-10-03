"""Rebind only the unfrozen #28 V14 B03 source-scope implementation."""
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

BASE = '9e0e607595bb193687a8f4554789004f85e7b98a'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = 'scripts/vnext/b03_depreciation_scope.py'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(relative, value):
    (ROOT/relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


old = json.loads(previous(MANIFEST))
assert json.loads((ROOT/MANIFEST).read_text()) == old
assert old['execution_authority']['files'][CHANGED] == identity(previous(CHANGED))
updated = json.loads(previous(MANIFEST))
binding = identity((ROOT/CHANGED).read_bytes())
updated['execution_authority']['files'][CHANGED] = binding
if CHANGED in updated['new_rule_files']:
    updated['new_rule_files'][CHANGED] = binding
write(MANIFEST, updated)
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
old_authority = content_hash(value=old['execution_authority'])
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    value = json.loads(previous(relative))
    assert json.loads((ROOT/relative).read_text()) == value
    assert value['execution_authority_hash'] == old_authority
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, value)
validate_wiring_receipt(requirement=requirement)
assert (ROOT/'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
    previous('requirements/issue_28_v13/baseline_manifest.json')
print(json.dumps({'status':'PASS_CURRENT_V14_FORD_B03_SCOPE_BINDING',
    'base':BASE, 'changed_execution_file':CHANGED,
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'execution_authority_hash':authority, 'receipts':len(RECEIPTS),
    'v13_unchanged':True, 'real_calls':[0,0,0]}, sort_keys=True))
