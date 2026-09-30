"""Bind only the current V14 B03 source relation; keep V13 unchanged."""
import hashlib
import json
import os
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

BASE = os.environ.get('ISSUE28_REBIND_BASE',
    '430097dd212bfe097caaa5d1d4b5b3f5dcc7a14e')
MANIFEST = 'requirements/issue_28_v14/baseline_manifest.json'
MODULE = 'scripts/vnext/b03_contract_amortization_scope.py'
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


old = json.loads(prior(MANIFEST))
assert json.loads((ROOT/MANIFEST).read_text()) == old
assert old['execution_authority']['files'][MODULE] == identity(prior(MODULE))
assert MODULE not in old['new_rule_files']
updated = json.loads(prior(MANIFEST))
updated['execution_authority']['files'][MODULE] = identity((ROOT/MODULE).read_bytes())
write(MANIFEST, updated)
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
old_authority = content_hash(value=old['execution_authority'])
current_authority = content_hash(value=requirement['execution_authority'])
for relative in RECEIPTS:
    receipt = json.loads(prior(relative))
    assert json.loads((ROOT/relative).read_text()) == receipt
    assert receipt['execution_authority_hash'] == old_authority
    receipt['execution_authority_hash'] = current_authority
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
    write(relative, receipt)
validate_wiring_receipt(requirement=requirement)
assert (ROOT/'requirements/issue_28_v13/baseline_manifest.json').read_bytes() == \
       prior('requirements/issue_28_v13/baseline_manifest.json')
print(json.dumps({'status':'PASS_V14_B03_CONTRACT_EXCLUSION_BINDING',
    'base':BASE,'module':MODULE,
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'execution_authority_hash':current_authority,
    'receipts':len(RECEIPTS),'v13_unchanged':True,
    'new_real_calls':[0,0,0]},sort_keys=True))
