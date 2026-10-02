"""Bind the explicit C02 auditor-scope successor into mutable #28 roots."""
import hashlib
import json
from pathlib import Path
import sys


ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

PARENT=ROOT/'requirements/issue_28_v13'
CHILD=ROOT/'requirements/issue_28_v14'
CHANGED=(
    'catalog/r6/C02_board_disclosures_v5.md',
    'config/issue28_normal_results_v2.json',
    'scripts/vnext/c02_board_composition_28_v4.py',
    'scripts/vnext/c02_composition_text_results.py',
    'scripts/vnext/normal_run_v3.py',
    'scripts/vnext/ordinary_c02_member_update_v4.py',
    'scripts/vnext/ordinary_remaining_cases.py',
    'scripts/vnext/ordinary_update_cycle.py',
)
NEW={'catalog/r6/C02_board_disclosures_v5.md',
     'scripts/vnext/c02_board_composition_28_v4.py',
     'scripts/vnext/ordinary_c02_member_update_v4.py'}
CHILD_ONLY=('tools/vnext_normal_update.py',)
PARENT_FILES=('CONTRACT.md','baseline_manifest.json','decision_register.json',
              'invariant_profile.json','transfer_manifest.json')
RECEIPTS=(
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def identity(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


parent_path=PARENT/'baseline_manifest.json';child_path=CHILD/'baseline_manifest.json'
parent=json.loads(parent_path.read_text());child=json.loads(child_path.read_text())
prior=json.loads((ROOT/'docs/evidence/issue28_continuous/collab-e01-header-guard-20261002/binding-after-boundary.json').read_text())
old_auth=content_hash(value=child['execution_authority'])
if not (HERE/'binding-before.json').exists():
    assert old_auth==prior['child_execution_authority_hash']
    write(HERE/'binding-before.json',{'prior_parent_closure':prior['parent_closure'],
        'prior_child_closure':prior['child_closure'],
        'prior_child_execution_authority_hash':old_auth,
        'prior_source_bindings':{p:parent['execution_authority']['files'].get(p) for p in CHANGED},
        'changed_sources':list(CHANGED),'child_only_paths':list(CHILD_ONLY)})
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash']==old_auth
for relative in CHANGED:
    value=identity(ROOT/relative)
    parent['execution_authority']['files'][relative]=value
    if relative in parent['new_rule_files'] or relative in NEW:
        parent['new_rule_files'][relative]=value
write(parent_path,parent)
parent_req=load_requirement_snapshot(snapshot_dir=PARENT)
validate_execution_authority(repo_root=ROOT,requirement=parent_req)
child['parent']['requirement_closure_hash']=parent_req['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name]=identity(PARENT/name)
for relative in (*CHANGED,*CHILD_ONLY):
    value=identity(ROOT/relative)
    child['execution_authority']['files'][relative]=value
    if relative in child['new_rule_files']:
        child['new_rule_files'][relative]=value
write(child_path,child)
transfer_path=CHILD/'transfer_manifest.json';transfer=json.loads(transfer_path.read_text())
transfer['parent_requirement_closure_hash']=parent_req['requirement_closure_hash']
write(transfer_path,transfer)
child_req=load_requirement_snapshot(snapshot_dir=CHILD)
validate_execution_authority(repo_root=ROOT,requirement=child_req)
validate_semantic_rule_bindings(child_req)
new_auth=content_hash(value=child_req['execution_authority'])
for relative in RECEIPTS:
    path=ROOT/relative;receipt=json.loads(path.read_text())
    receipt['execution_authority_hash']=new_auth
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash']=child_req['requirement_closure_hash']
    write(path,receipt)
validate_wiring_receipt(requirement=child_req)
write(HERE/'binding-after.json',{'parent_closure':parent_req['requirement_closure_hash'],
    'child_closure':child_req['requirement_closure_hash'],
    'child_execution_authority_hash':new_auth,'changed_sources':list(CHANGED),
    'child_only_paths':list(CHILD_ONLY),'receipt_count':len(RECEIPTS),
    'new_explicit_C02_policy':'COMPOSITION_GROUPED_V4',
    'default_shared_flags_unchanged':True,'old_D02_credit_still_suspended':True,
    'new_real_calls':[0,0,0]})
print(json.dumps({'status':'PASS_C02_MEMBER_SUCCESSOR_BINDING',
    'parent':parent_req['requirement_closure_hash'],
    'child':child_req['requirement_closure_hash'],'receipts':len(RECEIPTS)}))
