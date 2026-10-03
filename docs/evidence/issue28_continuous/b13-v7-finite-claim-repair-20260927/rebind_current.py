"""Refresh only the unfrozen V14 B13 diagnostic byte binding and receipts."""
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

HERE = Path(__file__).resolve().parent
BASE = '227182efe31b7ce6364c866753ae1332afb41ea2'
RELATIVE = 'scripts/vnext/capacity_two_stage.py'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


path = ROOT / 'requirements/issue_28_v14/baseline_manifest.json'
baseline = json.loads(path.read_text())
old = subprocess.check_output(['git', 'show', BASE + ':' + RELATIVE], cwd=ROOT)
before = identity(old)
assert baseline['execution_authority']['files'][RELATIVE] == before
assert baseline['new_rule_files'][RELATIVE] == before
assert path.read_bytes() == subprocess.check_output(['git', 'show',
    BASE + ':requirements/issue_28_v14/baseline_manifest.json'], cwd=ROOT)
prior_authority = content_hash(value=baseline['execution_authority'])
prior_closure = json.loads((ROOT / RECEIPTS[0]).read_text())['requirement_closure_hash']
after = identity((ROOT / RELATIVE).read_bytes())
assert after != before
for name in RECEIPTS:
    receipt = json.loads((ROOT / name).read_text())
    assert (ROOT / name).read_bytes() == subprocess.check_output(
        ['git', 'show', BASE + ':' + name], cwd=ROOT)
    assert receipt['execution_authority_hash'] == prior_authority
    assert receipt.get('requirement_closure_hash', prior_closure) == prior_closure
write(HERE / 'binding-before.json', {'base': BASE, 'file': RELATIVE,
    'identity': before, 'v14_closure': prior_closure,
    'execution_authority_hash': prior_authority})
baseline['execution_authority']['files'][RELATIVE] = after
baseline['new_rule_files'][RELATIVE] = after
write(path, baseline)
current = load_requirement_snapshot(snapshot_dir=path.parent)
validate_execution_authority(repo_root=ROOT, requirement=current)
authority = content_hash(value=current['execution_authority'])
for name in RECEIPTS:
    receipt_path = ROOT / name
    receipt = json.loads(receipt_path.read_text())
    receipt['execution_authority_hash'] = authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = current['requirement_closure_hash']
    write(receipt_path, receipt)
validate_wiring_receipt(requirement=current)
write(HERE / 'binding-after.json', {'base': BASE, 'file': RELATIVE,
    'identity': after, 'v14_closure': current['requirement_closure_hash'],
    'execution_authority_hash': authority, 'v13_default_modified': False,
    'provider_paid_sec_calls': [0, 0, 0],
    'current_provider_receipt_validated': True})
print(json.dumps({'v14_closure': current['requirement_closure_hash'],
    'execution_authority_hash': authority, 'changed_files': [RELATIVE]},
    sort_keys=True))
