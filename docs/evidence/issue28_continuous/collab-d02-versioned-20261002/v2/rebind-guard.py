"""Bind the exact v2 native-credit stop after its limited review found P2."""
import hashlib
import json
from pathlib import Path
import sys


ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


PARENT=ROOT/'requirements/issue_28_v13'
CHILD=ROOT/'requirements/issue_28_v14'
CHANGED=('scripts/vnext/normal_run_v3.py','scripts/vnext/ordinary_update_cycle.py')
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


parent_path=PARENT/'baseline_manifest.json'
child_path=CHILD/'baseline_manifest.json'
parent=json.loads(parent_path.read_text())
child=json.loads(child_path.read_text())
prior=json.loads((HERE/'binding-after.json').read_text())
old_auth=content_hash(value=child['execution_authority'])
assert old_auth==prior['child_execution_authority_hash']
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash']==old_auth
write(HERE/'binding-before-guard.json',{
    'review_patch_sha':'79677ed2c8519a952698ee2a0b05e24deb91702a',
    'review_verdict':'NEEDS_FIX_P2_OUR_COMPANY_MATTER_FALSE_EXCLUSION',
    'prior_parent_closure':prior['parent_closure'],
    'prior_child_closure':prior['child_closure'],
    'prior_child_execution_authority_hash':old_auth,
    'prior_source_bindings':{p:parent['execution_authority']['files'][p] for p in CHANGED},
    'changed_sources':list(CHANGED)})
for relative in CHANGED:
    value=identity(ROOT/relative)
    parent['execution_authority']['files'][relative]=value
    if relative in parent['new_rule_files']:
        parent['new_rule_files'][relative]=value
write(parent_path,parent)
parent_req=load_requirement_snapshot(snapshot_dir=PARENT)
validate_execution_authority(repo_root=ROOT,requirement=parent_req)

child['parent']['requirement_closure_hash']=parent_req['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name]=identity(PARENT/name)
for relative in CHANGED:
    value=identity(ROOT/relative)
    child['execution_authority']['files'][relative]=value
    if relative in child['new_rule_files']:
        child['new_rule_files'][relative]=value
write(child_path,child)
transfer_path=CHILD/'transfer_manifest.json'
transfer=json.loads(transfer_path.read_text())
transfer['parent_requirement_closure_hash']=parent_req['requirement_closure_hash']
write(transfer_path,transfer)
child_req=load_requirement_snapshot(snapshot_dir=CHILD)
validate_execution_authority(repo_root=ROOT,requirement=child_req)
validate_semantic_rule_bindings(child_req)
new_auth=content_hash(value=child_req['execution_authority'])
for relative in RECEIPTS:
    path=ROOT/relative
    receipt=json.loads(path.read_text())
    receipt['execution_authority_hash']=new_auth
    if 'requirement_closure_hash' in receipt:
        receipt['requirement_closure_hash']=child_req['requirement_closure_hash']
    write(path,receipt)
validate_wiring_receipt(requirement=child_req)
write(HERE/'binding-after-guard.json',{
    'parent_closure':parent_req['requirement_closure_hash'],
    'child_closure':child_req['requirement_closure_hash'],
    'child_execution_authority_hash':new_auth,
    'changed_sources':list(CHANGED),'receipt_count':len(RECEIPTS),
    'v1_and_v2_new_native_credit_suspended':True,
    'old_private_runs_untouched':True,'new_real_calls':[0,0,0]})
print(json.dumps({'status':'PASS_D02_V2_POST_REVIEW_NATIVE_STOP_BINDING',
    'parent':parent_req['requirement_closure_hash'],
    'child':child_req['requirement_closure_hash'],
    'receipts':len(RECEIPTS)}))
