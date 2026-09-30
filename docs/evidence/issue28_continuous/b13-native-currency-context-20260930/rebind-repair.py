"""Bind the inline-measure-namespace repair against the exact 5f8d372 base."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.ordinary_scalability_audit import successor_scalability_snapshot
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = '5f8d372a36936646fa5ae2732a920ee98aa12118'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
RULE = 'scripts/vnext/capacity_reference_contract.py'
EXEMPTIONS = 'config/ordinary_scalability_exemptions_v1.json'
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
    (ROOT / relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


old = json.loads(previous(MANIFEST))
assert json.loads((ROOT / MANIFEST).read_text()) == old
assert old['new_rule_files'][RULE] == old['execution_authority']['files'][RULE] == identity(previous(RULE))
assert old['execution_authority']['files'][EXEMPTIONS] == identity(previous(EXEMPTIONS))
policy = json.loads((ROOT / EXEMPTIONS).read_text())
old_policy = json.loads(previous(EXEMPTIONS))
assert len(policy['entries']) == len(old_policy['entries'])
assert [row for row in policy['entries'] if row['file'] != RULE] == [
    row for row in old_policy['entries'] if row['file'] != RULE]
assert [row['line'] for row in policy['entries'] if row['file'] == RULE] == [190, 310]
assert all(row['source_sha256'] == identity((ROOT / RULE).read_bytes())['sha256']
           and row['source_size'] == identity((ROOT / RULE).read_bytes())['size']
           for row in policy['entries'] if row['file'] == RULE)
assert successor_scalability_snapshot(ROOT) == []
updated = json.loads(previous(MANIFEST))
updated['new_rule_files'][RULE] = identity((ROOT / RULE).read_bytes())
updated['execution_authority']['files'][RULE] = updated['new_rule_files'][RULE]
updated['execution_authority']['files'][EXEMPTIONS] = identity((ROOT / EXEMPTIONS).read_bytes())
write(MANIFEST, updated)
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
old_authority = content_hash(value=old['execution_authority'])
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    value = json.loads(previous(relative))
    assert json.loads((ROOT / relative).read_text()) == value
    assert value['execution_authority_hash'] == old_authority
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, value)
validate_wiring_receipt(requirement=requirement)
assert (ROOT / 'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
       previous('requirements/issue_28_v13/baseline_manifest.json')
print(json.dumps({'status': 'PASS_V14_INLINE_CURRENCY_UNIT_REPAIR_BINDING',
    'base': BASE, 'changed_rule': RULE, 'changed_exemption_policy': EXEMPTIONS,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipts': len(RECEIPTS),
    'v13_manifest_unchanged': True, 'new_real_calls': [0, 0, 0]}, sort_keys=True))
