"""Bind the explicit private release scanner in the unfrozen V14 draft."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

HERE = Path(__file__).resolve().parent
BASE = '070f1c4e'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
CHANGED = 'scripts/vnext/ordinary_isolated_publication.py'
ADDED = 'scripts/vnext/ordinary_scalability_audit.py'
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


old_manifest = json.loads(previous(MANIFEST))
path = ROOT / MANIFEST
assert json.loads(path.read_text()) == old_manifest
old_files = old_manifest['execution_authority']['files']
assert ADDED not in old_files and old_files[CHANGED] == identity(previous(CHANGED))
new_files = {}
for relative, binding in old_files.items():
    new_files[relative] = identity((ROOT / relative).read_bytes()) if relative == CHANGED else binding
    if relative == CHANGED:
        new_files[ADDED] = identity((ROOT / ADDED).read_bytes())
assert new_files[CHANGED] != old_files[CHANGED]
manifest = json.loads(path.read_text())
manifest['execution_authority']['files'] = new_files
write(path, manifest)

old_authority = content_hash(value=old_manifest['execution_authority'])
before = {'base': BASE, 'manifest_sha256': identity(previous(MANIFEST)),
          'execution_authority_hash': old_authority,
          'changed_files': {CHANGED: {'before': old_files[CHANGED],
                                     'after': new_files[CHANGED]},
                            ADDED: {'before': None, 'after': new_files[ADDED]}}}
write(HERE / 'binding-before.json', before)

requirement = load_requirement_snapshot(snapshot_dir=path.parent)
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt = ROOT / relative
    assert receipt.read_bytes() == previous(relative)
    value = json.loads(receipt.read_text())
    assert value['execution_authority_hash'] == old_authority
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(receipt, value)
validate_wiring_receipt(requirement=requirement)

after = {'base': BASE,
         'manifest_sha256': identity(path.read_bytes()),
         'requirement_closure_hash': requirement['requirement_closure_hash'],
         'execution_authority_hash': authority,
         'changed_execution_files': [CHANGED, ADDED],
         'v13_manifest_unchanged': (ROOT / 'requirements/issue_28_v13/baseline_manifest.json').read_bytes()
             == previous('requirements/issue_28_v13/baseline_manifest.json'),
         'receipt_count': len(RECEIPTS),
         'real_calls': [0, 0, 0]}
assert after['v13_manifest_unchanged']
write(HERE / 'binding-after.json', after)
print('PASS V14 explicit private release execution, rule and three wiring receipts')
print(requirement['requirement_closure_hash'])
