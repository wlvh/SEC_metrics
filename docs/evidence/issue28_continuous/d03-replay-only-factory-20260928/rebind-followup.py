"""Bind D03's candidate-review code without changing approved rule_paths."""
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

BASE = '23243375ddf9143eb2f25405b16527ead330a0cb'
HERE = Path(__file__).resolve().parent
CHANGED = 'scripts/vnext/continuous_semantic_calls.py'
ADDED = 'scripts/vnext/regulatory_fact_review.py'
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
old = identity(previous(CHANGED))
new = identity((ROOT / CHANGED).read_bytes())
added = identity((ROOT / ADDED).read_bytes())
assert old != new and (ROOT / ADDED).read_bytes() == previous(ADDED)
assert manifest['execution_authority']['files'][CHANGED] == old
assert manifest['new_rule_files'][CHANGED] == old
assert ADDED not in manifest['execution_authority']['files']
assert ADDED not in manifest['new_rule_files']
old_authority = content_hash(value=manifest['execution_authority'])
old_closure = json.loads((ROOT / RECEIPTS[0]).read_text())['requirement_closure_hash']
for relative in RECEIPTS:
    path = ROOT / relative
    assert path.read_bytes() == previous(relative)
    value = json.loads(path.read_text())
    assert value['execution_authority_hash'] == old_authority
    assert value.get('requirement_closure_hash', old_closure) == old_closure
write(HERE / 'followup-binding-before.json', {'base': BASE,
    'changed_module': old, 'previously_unbound_dependency': ADDED,
    'v14_closure': old_closure, 'execution_authority_hash': old_authority})
manifest['execution_authority']['files'][CHANGED] = new
manifest['execution_authority']['files'][ADDED] = added
manifest['new_rule_files'][CHANGED] = new
write(MANIFEST, manifest)
requirement = load_requirement_snapshot(snapshot_dir=MANIFEST.parent)
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
write(HERE / 'followup-binding-after.json', {'base': BASE,
    'changed_module': new, 'added_dependency': {ADDED: added},
    'v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipt_count': len(RECEIPTS),
    'new_calls': [0, 0, 0]})
print('PASS D03 candidate dependency, V14 execution, provider/SEC/refresh wiring')
print('requirement_closure_hash', requirement['requirement_closure_hash'])
