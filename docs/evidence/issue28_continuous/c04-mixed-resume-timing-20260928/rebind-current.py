"""Rebind current unfrozen V13/V14 after one-operation replay reuse."""
import hashlib
import json
from pathlib import Path
import subprocess

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
BASE = 'ea6ac14e8afc8464eeeca6f004b2016d1678ce40'
CHANGED = ('scripts/vnext/ordinary_projection.py',
           'scripts/vnext/ordinary_update_cycle.py')
PARENT = Path('requirements/issue_28_v13')
CHILD = Path('requirements/issue_28_v14')
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')
RECEIPTS = (
    Path('docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json'),
    Path('docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json'),
    Path('docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json'),
)


def old(relative):
    return subprocess.check_output(['git', 'show', BASE + ':' + str(relative)], cwd=ROOT)


def binding(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(relative, value):
    (ROOT/relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


parent_path = PARENT/'baseline_manifest.json'
child_path = CHILD/'baseline_manifest.json'
transfer_path = CHILD/'transfer_manifest.json'
assert all((ROOT/path).read_bytes() == old(path) for path in
           (parent_path, child_path, transfer_path))
parent = json.loads((ROOT/parent_path).read_text())
child = json.loads((ROOT/child_path).read_text())
prior_authority = content_hash(value=child['execution_authority'])
before = {path: binding(old(path)) for path in CHANGED}
after = {path: binding((ROOT/path).read_bytes()) for path in CHANGED}
assert all(before[path] != after[path] for path in CHANGED)
assert all(parent['execution_authority']['files'][path] == before[path]
           and child['execution_authority']['files'][path] == before[path]
           for path in CHANGED)
assert parent['new_rule_files'][CHANGED[1]] == before[CHANGED[1]]
assert all(json.loads((ROOT/path).read_text())['execution_authority_hash'] ==
           prior_authority for path in RECEIPTS)
(HERE/'binding-before.json').write_text(json.dumps({
    'base': BASE, 'old_authority': prior_authority,
    'parent_closure': child['parent']['requirement_closure_hash'],
    'files': before}, indent=2) + '\n')

for path in CHANGED:
    parent['execution_authority']['files'][path] = after[path]
parent['new_rule_files'][CHANGED[1]] = after[CHANGED[1]]
write(parent_path, parent)
ordinary = load_requirement_snapshot(snapshot_dir=ROOT/PARENT)
validate_execution_authority(repo_root=ROOT, requirement=ordinary)

child['parent']['requirement_closure_hash'] = ordinary['requirement_closure_hash']
for name in PARENT_FILES:
    relative = PARENT/name
    child['parent']['snapshot_files'][name] = binding((ROOT/relative).read_bytes())
for path in CHANGED:
    child['execution_authority']['files'][path] = after[path]
write(child_path, child)
transfer = json.loads((ROOT/transfer_path).read_text())
transfer['parent_requirement_closure_hash'] = ordinary['requirement_closure_hash']
write(transfer_path, transfer)
continuous = load_requirement_snapshot(snapshot_dir=ROOT/CHILD)
validate_execution_authority(repo_root=ROOT, requirement=continuous)

authority = content_hash(value=continuous['execution_authority'])
for path in RECEIPTS:
    receipt = json.loads((ROOT/path).read_text())
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = continuous['requirement_closure_hash']
    write(path, receipt)
validate_wiring_receipt(requirement=continuous)
(HERE/'binding-after.json').write_text(json.dumps({
    'ordinary_closure': ordinary['requirement_closure_hash'],
    'continuous_closure': continuous['requirement_closure_hash'],
    'execution_authority_hash': authority, 'files': after,
    'receipts': [str(path) for path in RECEIPTS],
    'frozen_snapshots_changed': False}, indent=2) + '\n')
print(json.dumps({'ordinary_closure': ordinary['requirement_closure_hash'],
                  'continuous_closure': continuous['requirement_closure_hash'],
                  'execution_authority_hash': authority}, sort_keys=True))
