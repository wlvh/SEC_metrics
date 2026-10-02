"""Bind the explicit D02 v2 ordinary path into mutable V13/V14 only."""
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
CHANGED=(
    'catalog/r6/D02_item8_category_28_v2.json',
    'config/issue28_normal_results_v2.json',
    'scripts/vnext/d02_item8_category_28_v2.py',
    'scripts/vnext/d02_text_results_v3.py',
    'scripts/vnext/normal_run_v3.py',
    'scripts/vnext/ordinary_d02_category_update.py',
    'scripts/vnext/ordinary_d02_category_update_v2.py',
    'scripts/vnext/ordinary_d02_item8_v2.py',
    'scripts/vnext/ordinary_remaining_cases.py',
    'scripts/vnext/ordinary_update_cycle.py',
)
CHILD_ONLY=('tools/vnext_normal_update.py',)
NEW={
    'catalog/r6/D02_item8_category_28_v2.json',
    'scripts/vnext/d02_item8_category_28_v2.py',
    'scripts/vnext/ordinary_d02_category_update_v2.py',
    'scripts/vnext/ordinary_d02_item8_v2.py',
}
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
before=HERE/'binding-before.json'
current_auth=content_hash(value=child['execution_authority'])
prior_file=HERE/'binding-before.json'
prior=json.loads(prior_file.read_text()) if prior_file.exists() else None
for relative in RECEIPTS:
    recorded=json.loads((ROOT/relative).read_text())['execution_authority_hash']
    assert recorded==current_auth or (prior is not None and
        recorded==prior['child_execution_authority_hash'])
if not before.exists():
    prior=json.loads((ROOT/'docs/evidence/issue28_continuous/collab-e01-item-text-feasibility-20261002/binding-after-install.json').read_text())
    assert prior['child_execution_authority_hash']==current_auth
    write(before,{'parent_closure':prior['parent_requirement_closure_hash'],
        'child_closure':prior['child_requirement_closure_hash'],
        'child_execution_authority_hash':current_auth,
        'source_bindings':{p:parent['execution_authority']['files'].get(p) for p in CHANGED},
        'changed_paths':list(CHANGED),'child_only_paths':list(CHILD_ONLY),
        'peer_source_commit':'147957c400c3361ab26ee0b04bbb89b2a692cadd',
        'peer_module_git_blob':'184327494290f413a97091a22613e4b968ab8d45',
        'peer_terms_git_blob':'e65ccafc00f569ac0adc0e3501c76a7d7dba463d'})
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
for relative in NEW:
    child['new_rule_files'].pop(relative,None)
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
write(HERE/'binding-after.json',{'parent_closure':parent_req['requirement_closure_hash'],
    'child_closure':child_req['requirement_closure_hash'],
    'child_execution_authority_hash':new_auth,'changed_paths':list(CHANGED),
    'child_only_paths':list(CHILD_ONLY),
    'new_paths':sorted(NEW),'receipt_count':len(RECEIPTS),
    'old_v1_path_still_suspended':True,'new_real_calls':[0,0,0]})
print(json.dumps({'status':'PASS_D02_V2_EXPLICIT_BINDING',
    'parent':parent_req['requirement_closure_hash'],
    'child':child_req['requirement_closure_hash'],
    'receipts':len(RECEIPTS)}))
