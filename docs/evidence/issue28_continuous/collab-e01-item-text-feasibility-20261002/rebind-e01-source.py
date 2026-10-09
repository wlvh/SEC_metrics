"""Bind the source-only E01 successor into mutable #28 V13/V14."""
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT),str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

PARENT = ROOT/'requirements/issue_28_v13'
CHILD = ROOT/'requirements/issue_28_v14'
CHANGED = ('config/issue28_normal_results_v2.json',
           'scripts/vnext/e01_item_text_28_v1.py',
           'scripts/vnext/ordinary_e01_item_text_input.py')
PARENT_FILES = ('CONTRACT.md','baseline_manifest.json','decision_register.json',
                'invariant_profile.json','transfer_manifest.json')
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json')


def identity(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


policy=json.loads((ROOT/'config/issue28_normal_results_v2.json').read_text())
assert policy['rule_paths']==sorted(set(policy['rule_paths']))
assert set(CHANGED)<=set(policy['rule_paths'])
parent_path,child_path=PARENT/'baseline_manifest.json',CHILD/'baseline_manifest.json'
parent,child=json.loads(parent_path.read_text()),json.loads(child_path.read_text())
old_child_auth=content_hash(value=child['execution_authority'])
prior=json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'collab-d02-versioned-20261002/binding-after-gate.json').read_text())
assert prior['child_execution_authority_hash']==old_child_auth
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash']==old_child_auth
write(HERE/'binding-before-e01.json',{
    'prior_child_requirement_closure_hash':prior['child_requirement_closure_hash'],
    'prior_child_execution_authority_hash':old_child_auth,
    'changed_paths':list(CHANGED),
    'old_parent_bindings':{key:parent['execution_authority']['files'].get(key)
                            for key in CHANGED}})

register_path=PARENT/'decision_register.json'
register=json.loads(register_path.read_text())
register['policy']=policy
write(register_path,register)
parent['new_rule_files']={relative:identity(ROOT/relative)
                          for relative in policy['rule_paths']}
for relative in policy['rule_paths']:
    parent['execution_authority']['files'][relative]=identity(ROOT/relative)
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
write(HERE/'binding-after-e01.json',{
    'parent_requirement_closure_hash':parent_req['requirement_closure_hash'],
    'child_requirement_closure_hash':child_req['requirement_closure_hash'],
    'child_execution_authority_hash':new_auth,
    'changed_paths':list(CHANGED),'receipt_count':len(RECEIPTS),
    'source_only_no_result_or_provider_authority':True,
    'new_real_calls':[0,0,0]})
print(json.dumps({'status':'PASS_E01_SOURCE_ONLY_BINDING',
    'parent':parent_req['requirement_closure_hash'],
    'child':child_req['requirement_closure_hash'],
    'receipts':len(RECEIPTS)},sort_keys=True))
