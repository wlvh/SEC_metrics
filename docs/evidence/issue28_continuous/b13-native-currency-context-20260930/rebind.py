"""Bind one unfrozen V14 B13 checker change; preserve V13 and old packets."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot
from vnext.ordinary_scalability_audit import successor_scalability_snapshot

BASE = 'e646f9cdac3fa2b57096892eb7f4fbd1deebb805'
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
intermediate_receipt = json.loads((Path(__file__).with_name(
    'binding-intermediate.log')).read_text())
intermediate = json.loads((ROOT / MANIFEST).read_text())
expected_intermediate = deepcopy(old)
intermediate_rule = intermediate['new_rule_files'][RULE]
expected_intermediate['new_rule_files'][RULE] = intermediate_rule
expected_intermediate['execution_authority']['files'][RULE] = intermediate_rule
assert intermediate == expected_intermediate
assert content_hash(value=intermediate['execution_authority']) == \
       intermediate_receipt['execution_authority_hash']
assert old['new_rule_files'][RULE] == old['execution_authority']['files'][RULE]
assert old['new_rule_files'][RULE] == identity(previous(RULE))
assert old['execution_authority']['files'][EXEMPTIONS] == identity(previous(EXEMPTIONS))
old_policy = json.loads(previous(EXEMPTIONS))
expected_policy = deepcopy(old_policy)
for row in expected_policy['entries']:
    if row['file'] == RULE:
        row['line'] = {147: 181, 257: 301}[row['line']]
        row['source_sha256'] = identity((ROOT / RULE).read_bytes())['sha256']
        row['source_size'] = identity((ROOT / RULE).read_bytes())['size']
assert json.loads((ROOT / EXEMPTIONS).read_text()) == expected_policy
assert successor_scalability_snapshot(ROOT) == []
updated = json.loads(previous(MANIFEST))
updated['new_rule_files'][RULE] = identity((ROOT / RULE).read_bytes())
updated['execution_authority']['files'][RULE] = updated['new_rule_files'][RULE]
updated['execution_authority']['files'][EXEMPTIONS] = identity(
    (ROOT / EXEMPTIONS).read_bytes())
write(MANIFEST, updated)

requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
old_authority = content_hash(value=old['execution_authority'])
authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    value = json.loads(previous(relative))
    assert value['execution_authority_hash'] == old_authority
    expected_receipt = deepcopy(value)
    expected_receipt['execution_authority_hash'] = intermediate_receipt[
        'execution_authority_hash']
    if 'requirement_closure_hash' in expected_receipt:
        expected_receipt['requirement_closure_hash'] = intermediate_receipt[
            'requirement_closure_hash']
    assert json.loads((ROOT / relative).read_text()) == expected_receipt
    value['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in value:
        value['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, value)
validate_wiring_receipt(requirement=requirement)
assert (ROOT / 'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
       previous('requirements/issue_28_v13/baseline_manifest.json')
print(json.dumps({'status': 'PASS_CURRENT_V14_B13_CURRENCY_CONTEXT_BINDING',
    'base': BASE, 'changed_rule': RULE, 'changed_exemption_policy': EXEMPTIONS,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority, 'receipts': len(RECEIPTS),
    'v13_manifest_unchanged': True, 'new_real_calls': [0, 0, 0]}, sort_keys=True))
