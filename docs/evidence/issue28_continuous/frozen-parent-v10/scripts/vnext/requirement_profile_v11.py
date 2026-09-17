"""B06 bounded new-source candidate policy; no production activation."""
from . import requirement_profile_v1 as v1
from .canonical import strict_json_file,sha256_file,content_hash

PROFILE_REQUIREMENT_GENERATION='PROFILE_DRIVEN_V11'
REQUIREMENT_ID='issue_28_v10'
PARENT_ID='issue_28_v9'


def load_profile_requirement_snapshot(*,snapshot_dir,parent_loader):
    def need(ok,message):
        if not ok:raise v1.RequirementProfileError(message)
    root=snapshot_dir.parent.parent
    need(not snapshot_dir.is_symlink() and {p.name for p in snapshot_dir.iterdir()}==v1.PROFILE_SNAPSHOT_FILES,'B06 source snapshot file set differs')
    b=strict_json_file(path=snapshot_dir/'baseline_manifest.json');parent=parent_loader(snapshot_dir=root/'requirements'/PARENT_ID)
    need(b['requirement_id']==REQUIREMENT_ID and b['requirement_generation']==PROFILE_REQUIREMENT_GENERATION and b['parent']['requirement_id']==PARENT_ID and b['parent']['requirement_closure_hash']==parent['requirement_closure_hash'],'B06 source parent/identity differs')
    for n,p in b['parent']['snapshot_files'].items():
        f=root/'requirements'/PARENT_ID/n;need(sha256_file(path=f)==p['sha256'] and f.stat().st_size==p['size'],'B06 source parent bytes differ')
    need(b['validator']['path']=='scripts/vnext/requirement_profile_v11.py' and sha256_file(path=root/b['validator']['path'])==b['validator']['sha256'],'B06 source validator differs')
    register=strict_json_file(path=snapshot_dir/'decision_register.json');policy=strict_json_file(path=root/'config/b06_new_source_v1.json')
    need(register['policy']==policy and register['status']=='DELEGATED_CANDIDATE_ONLY' and policy['production_authorized'] is False and policy['provider_enabled'] is False and policy['budget']=={'provider':2,'paid':2,'sec':4},'B06 source delegated boundary differs')
    transfer=strict_json_file(path=snapshot_dir/'transfer_manifest.json');inv=strict_json_file(path=snapshot_dir/'invariant_profile.json')
    need(transfer=={'parent_requirement_id':PARENT_ID,'parent_requirement_closure_hash':parent['requirement_closure_hash'],'disposition':'CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION','pending_decision_ids':parent['pending_decision_ids']},'B06 source parent responsibility changed')
    need(inv=={'production_authorized':False,'historical_bytes_unchanged':True,'coverage_requires_source_relationships':True,'input_allowlist_does_not_define_disclosure_scope':True,'native_run_admission_required':True},'B06 source invariant differs')
    for rel,p in b['new_rule_files'].items():need(sha256_file(path=root/rel)==p['sha256'],'B06 new source rule changed:'+rel)
    hashes={k:sha256_file(path=snapshot_dir/n) for k,n in [('baseline_sha256','baseline_manifest.json'),('contract_sha256','CONTRACT.md'),('decision_register_sha256','decision_register.json'),('invariant_profile_sha256','invariant_profile.json'),('transfer_manifest_sha256','transfer_manifest.json')]}
    hashes.update(parent_requirement_closure_hash=parent['requirement_closure_hash'],validator_sha256=b['validator']['sha256'])
    return {'artifact_requirement_generation':'EXPLICIT_REQUIREMENT_V1','baseline':b,'requirement_generation':PROFILE_REQUIREMENT_GENERATION,'requirement_id':REQUIREMENT_ID,'requirement_closure_hash':content_hash(value=hashes),'hashes':hashes,'execution_authority':b['execution_authority'],'activation_state':'NOT_ACTIVATED','effective_decisions':parent['effective_decisions'],'decision_chains':parent['decision_chains'],'pending_decision_ids':parent['pending_decision_ids'],'parent_snapshot':parent,'parent_requirement_id':PARENT_ID,'parent_requirement_closure_hash':parent['requirement_closure_hash'],'transfer':transfer,'evaluated_invariants':inv,'issue_contract_revision':'b06-new-source-candidate','policy':policy}
