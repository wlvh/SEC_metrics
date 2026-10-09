"""Finish current V14 bindings after the exact scalability exception update."""
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

BASE = '4ac3e1cc3cd5dfb8774d6292116a5f175f16d6eb'
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
MODULE = 'scripts/vnext/capacity_two_stage.py'
POLICY = 'config/ordinary_scalability_exemptions_v1.json'
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def prior(relative):
    return subprocess.check_output(['git', 'show', BASE+':'+relative], cwd=ROOT)


def identity(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(relative, value):
    (ROOT/relative).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


current = json.loads((ROOT/MANIFEST).read_text())
assert current['new_rule_files'][MODULE] == \
       current['execution_authority']['files'][MODULE]
assert current['new_rule_files'][MODULE]['sha256'] == \
       '6bc847f86ccc8b687c226ad68b29862db16f74825c35bc704c65ad151dd399b5'
assert current['execution_authority']['files'][POLICY] == identity(prior(POLICY))
before_authority = content_hash(value=current['execution_authority'])
for target in (current['new_rule_files'], current['execution_authority']['files']):
    target[MODULE] = identity((ROOT/MODULE).read_bytes())
current['execution_authority']['files'][POLICY] = identity((ROOT/POLICY).read_bytes())
write(MANIFEST, current)
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
current_authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt = json.loads((ROOT/relative).read_text())
    assert receipt['execution_authority_hash'] == before_authority
    receipt['execution_authority_hash'] = current_authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, receipt)
validate_wiring_receipt(requirement=requirement)
assert (ROOT/'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
       prior('requirements/issue_28_v13/baseline_manifest.json')
print(json.dumps({'status': 'PASS_V14_COVERAGE_AND_SCALABILITY_BINDING',
    'base': BASE, 'module': MODULE, 'scalability_policy': POLICY,
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': current_authority,
    'receipts': len(RECEIPTS), 'v13_unchanged': True,
    'new_real_calls': [0, 0, 0]}, sort_keys=True))
