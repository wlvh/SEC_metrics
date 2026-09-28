"""Update only the current #28 V14 execution identity after B03 scope guard."""
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

BASE = 'f415bd3ef2a95c65b51a0464e1f66681a6c3aa1f'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = (
    'scripts/vnext/ordinary_release_preparation.py',
    'scripts/vnext/ordinary_isolated_publication.py',
    'scripts/vnext/ordinary_refresh_cycle.py',
)
ADDED = (
    'scripts/vnext/b03_depreciation_scope.py',
    'scripts/vnext/ordinary_b03_scope_update.py',
    'tools/vnext_normal_update.py',
)
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def previous(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + relative],
                                   cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(relative, value):
    (ROOT/relative).write_text(json.dumps(value, ensure_ascii=False,
                                   indent=2) + '\n')


old = json.loads(previous(MANIFEST))
assert json.loads((ROOT/MANIFEST).read_text()) == old
assert all(p not in old['execution_authority']['files'] for p in ADDED)
assert all(old['execution_authority']['files'][p] == identity(previous(p))
           for p in CHANGED)
updated = json.loads(previous(MANIFEST))
for relative in (*CHANGED, *ADDED):
    binding = identity((ROOT/relative).read_bytes())
    updated['execution_authority']['files'][relative] = binding
    if relative in updated['new_rule_files']:
        updated['new_rule_files'][relative] = binding
write(MANIFEST, updated)

requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
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
print(json.dumps({'status':'PASS_CURRENT_V14_B03_SCOPE_BINDING',
    'base':BASE, 'changed_execution_files':[*CHANGED, *ADDED],
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'execution_authority_hash':authority, 'receipts':len(RECEIPTS),
    'v13_unchanged':True, 'real_calls':[0,0,0]}, sort_keys=True))
