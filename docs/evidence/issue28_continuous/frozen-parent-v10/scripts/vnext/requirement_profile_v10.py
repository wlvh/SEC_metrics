"""Draft-only R5 structured primary Requirement over unchanged parent obligations."""
from pathlib import Path
from . import requirement_profile_v1 as v1
from .canonical import strict_json_file, sha256_file, content_hash

PROFILE_REQUIREMENT_GENERATION='PROFILE_DRIVEN_V10'
REQUIREMENT_ID='issue_28_v9'
PARENT_ID='issue_28_v8'


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    need=lambda ok, msg: _require(ok,msg)
    need(not snapshot_dir.is_symlink() and {p.name for p in snapshot_dir.iterdir()}==v1.PROFILE_SNAPSHOT_FILES,'R5 snapshot file set differs')
    root=snapshot_dir.parent.parent
    baseline=strict_json_file(path=snapshot_dir/'baseline_manifest.json')
    need(baseline['requirement_id']==REQUIREMENT_ID and baseline['requirement_generation']==PROFILE_REQUIREMENT_GENERATION,'R5 identity differs')
    parent=parent_loader(snapshot_dir=root/'requirements'/PARENT_ID)
    need(baseline['parent']['requirement_id']==PARENT_ID and baseline['parent']['requirement_closure_hash']==parent['requirement_closure_hash'],'R5 parent differs')
    for name,proof in baseline['parent']['snapshot_files'].items():
        p=root/'requirements'/PARENT_ID/name
        need(sha256_file(path=p)==proof['sha256'] and p.stat().st_size==proof['size'],'R5 parent bytes differ')
    validator=root/baseline['validator']['path']
    need(baseline['validator']['path']=='scripts/vnext/requirement_profile_v10.py' and sha256_file(path=validator)==baseline['validator']['sha256'],'R5 engine identity differs')
    register=strict_json_file(path=snapshot_dir/'decision_register.json')
    transfer=strict_json_file(path=snapshot_dir/'transfer_manifest.json')
    invariants=strict_json_file(path=snapshot_dir/'invariant_profile.json')
    rule=strict_json_file(path=root/'config/r5_b06_structured_v1.json')
    need(register['requirement_id']==REQUIREMENT_ID and register['decision']=='PROPOSE_R5_B06_STRUCTURED_PRIMARY' and register['status']=='PENDING_FINAL_REVIEW' and register['policy']==rule,'R5 proposal or policy differs')
    need(rule['metric_ids']==['B06'] and rule['source_strategy']=='structured_first_ai_fallback' and rule['primary_only'] is True and rule['production_authorized'] is False and rule['business_calls']==[0,0,0],'R5 scope expanded')
    need(transfer=={'parent_requirement_id':PARENT_ID,'parent_requirement_closure_hash':parent['requirement_closure_hash'],'disposition':'CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION','pending_decision_ids':parent['pending_decision_ids']},'R5 dropped or activated inherited responsibility')
    need(invariants=={'requirement_id':REQUIREMENT_ID,'policy_id':rule['policy_id'],'business_calls':[0,0,0],'production_authorized':False,'historical_plans_unchanged':True},'R5 invariant scope differs')
    hashes={k:sha256_file(path=snapshot_dir/n) for k,n in [('baseline_sha256','baseline_manifest.json'),('contract_sha256','CONTRACT.md'),('decision_register_sha256','decision_register.json'),('invariant_profile_sha256','invariant_profile.json'),('transfer_manifest_sha256','transfer_manifest.json')]}
    hashes.update(parent_requirement_closure_hash=parent['requirement_closure_hash'],validator_sha256=baseline['validator']['sha256'])
    return {'artifact_requirement_generation':'EXPLICIT_REQUIREMENT_V1','baseline':baseline,'requirement_generation':PROFILE_REQUIREMENT_GENERATION,'requirement_id':REQUIREMENT_ID,'requirement_closure_hash':content_hash(value=hashes),'hashes':hashes,'execution_authority':baseline['execution_authority'],'activation_state':'NOT_ACTIVATED','effective_decisions':parent['effective_decisions'],'decision_chains':parent['decision_chains'],'pending_decision_ids':parent['pending_decision_ids'],'parent_snapshot':parent,'parent_requirement_id':PARENT_ID,'parent_requirement_closure_hash':parent['requirement_closure_hash'],'transfer':transfer,'evaluated_invariants':invariants,'issue_contract_revision':'r5-b06-structured-primary-draft','policy':rule}


def _require(ok,msg):
    if not ok:
        raise v1.RequirementProfileError(msg)
