"""Bind only E01's source-only installer addition into mutable V13/V14."""
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
SOURCE='scripts/vnext/ordinary_e01_item_text_input.py'
PARENT_FILES=('CONTRACT.md','baseline_manifest.json','decision_register.json',
              'invariant_profile.json','transfer_manifest.json')
RECEIPTS=(
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json')


def identity(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


parent_path,child_path=PARENT/'baseline_manifest.json',CHILD/'baseline_manifest.json'
parent,child=json.loads(parent_path.read_text()),json.loads(child_path.read_text())
prior=json.loads((HERE/'binding-after-e01.json').read_text())
old_auth=content_hash(value=child['execution_authority'])
assert prior['child_execution_authority_hash']==old_auth
for relative in RECEIPTS:
    assert json.loads((ROOT/relative).read_text())['execution_authority_hash']==old_auth
write(HERE/'binding-before-install.json',{
    'prior_parent_requirement_closure_hash':prior['parent_requirement_closure_hash'],
    'prior_child_requirement_closure_hash':prior['child_requirement_closure_hash'],
    'prior_child_execution_authority_hash':old_auth,
    'prior_source_binding':parent['execution_authority']['files'][SOURCE],
    'changed_source':SOURCE})

value=identity(ROOT/SOURCE)
parent['execution_authority']['files'][SOURCE]=value
parent['new_rule_files'][SOURCE]=value
write(parent_path,parent)
parent_req=load_requirement_snapshot(snapshot_dir=PARENT)
validate_execution_authority(repo_root=ROOT,requirement=parent_req)
child['parent']['requirement_closure_hash']=parent_req['requirement_closure_hash']
for name in PARENT_FILES:
    child['parent']['snapshot_files'][name]=identity(PARENT/name)
child['execution_authority']['files'][SOURCE]=value
if SOURCE in child['new_rule_files']:
    child['new_rule_files'][SOURCE]=value
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
write(HERE/'binding-after-install.json',{
    'parent_requirement_closure_hash':parent_req['requirement_closure_hash'],
    'child_requirement_closure_hash':child_req['requirement_closure_hash'],
    'child_execution_authority_hash':new_auth,
    'changed_source':SOURCE,'receipt_count':len(RECEIPTS),
    'source_only_no_result_or_provider_authority':True,
    'new_real_calls':[0,0,0]})
print(json.dumps({'status':'PASS_E01_SOURCE_INSTALL_BINDING',
    'parent':parent_req['requirement_closure_hash'],
    'child':child_req['requirement_closure_hash'],
    'receipts':len(RECEIPTS)},sort_keys=True))
