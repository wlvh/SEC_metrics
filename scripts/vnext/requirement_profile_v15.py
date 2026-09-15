"""Explicit continuous-call/B13 successor; historical runtime rules are retained."""
from pathlib import Path

from . import requirement_profile_v1 as v1
from .canonical import content_hash, sha256_file, strict_json_file
from .sources import resolve_repository_file
from .continuous_call_policy import REQUIREMENT_ID, POLICY_PATH, DECISION_ID, delegation_fields

PROFILE_REQUIREMENT_GENERATION = 'PROFILE_DRIVEN_V15'
PARENT_ID = 'issue_28_v13'


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    def need(condition, reason):
        if not condition:raise v1.RequirementProfileError(reason)
    root = snapshot_dir.parent.parent
    installed = Path(__file__).resolve().parents[2]
    need(snapshot_dir.name == REQUIREMENT_ID and snapshot_dir.parent.name == 'requirements'
         and not snapshot_dir.is_symlink()
         and {p.name for p in snapshot_dir.iterdir()} == v1.PROFILE_SNAPSHOT_FILES,
         'Continuous successor snapshot files differ')
    for name in v1.PROFILE_SNAPSHOT_FILES:
        relative = 'requirements/' + REQUIREMENT_ID + '/' + name
        need(resolve_repository_file(repo_root=root,repo_relative_path=relative).read_bytes()
             == resolve_repository_file(repo_root=installed,repo_relative_path=relative).read_bytes(),
             'Continuous successor installed snapshot differs: ' + name)
    baseline = strict_json_file(path=snapshot_dir/'baseline_manifest.json')
    policy = strict_json_file(path=root/POLICY_PATH)
    need(policy == strict_json_file(path=installed/POLICY_PATH), 'Continuous installed policy differs')
    parent = parent_loader(snapshot_dir=root/'requirements'/PARENT_ID)
    need(baseline['requirement_id'] == REQUIREMENT_ID
         and baseline['requirement_generation'] == PROFILE_REQUIREMENT_GENERATION
         and baseline['parent']['requirement_id'] == PARENT_ID
         and baseline['parent']['requirement_closure_hash'] == parent['requirement_closure_hash'],
         'Continuous successor parent differs')
    for name,binding in baseline['parent']['snapshot_files'].items():
        path = root/'requirements'/PARENT_ID/name
        need({'sha256':sha256_file(path=path),'size':path.stat().st_size} == binding,
             'Continuous parent bytes differ: ' + name)
    need(set(baseline['parent']['snapshot_files']) == v1.PROFILE_SNAPSHOT_FILES,
         'Continuous parent snapshot set differs')
    validator = baseline['validator'];relative = 'scripts/vnext/requirement_profile_v15.py'
    need(validator['path'] == relative and sha256_file(path=root/relative)
         == validator['sha256'] == sha256_file(path=installed/relative), 'Continuous validator differs')
    need(set(baseline['new_rule_files']) == set(policy['rule_paths']), 'Continuous rule set differs')
    for relative,binding in baseline['new_rule_files'].items():
        path = resolve_repository_file(repo_root=root,repo_relative_path=relative)
        need({'sha256':sha256_file(path=path),'size':path.stat().st_size} == binding
             and sha256_file(path=installed/relative) == binding['sha256'], 'Continuous rule bytes differ: ' + relative)
    approval = strict_json_file(path=root/policy['delegation_record_path'])
    approved = delegation_fields(approval,policy=policy)
    need(policy['production_authorized'] is False and policy['automatic_retry_count'] == 0
         and policy['maximum_additional_provider_paid_sec_calls'] == [240,240,80]
         and policy['repository_monetary_budget_enforcement'] == 'DISABLED', 'Continuous safety boundary differs')
    decisions = strict_json_file(path=snapshot_dir/'decision_register.json')
    need(decisions['delegation_url'] == policy['delegation_url'] and decisions['policy'] == policy,
         'Continuous decision binding differs')
    need(decisions['field_resolutions'] == {'S-R5-B06-B13-MEANING':{'b13_economic_meaning':{
        'status':'APPROVED','choice':approved['b13'],'evidence':policy['delegation_url']}}},
        'Continuous B13 resolution differs')
    effective = dict(parent['effective_decisions'])
    for key,decision in decisions['successor_decisions'].items():
        need(decision['decision_id'] == key and decision['status'] == 'APPROVED'
             and decision['evidence'] == policy['delegation_url'], 'Continuous decision authority differs')
        effective[key] = decision
    need(effective[DECISION_ID]['choice'] == {'kind':'CONTINUOUS_CALL_ALLOWANCE',
         'maximum_additional_provider_paid_sec_calls':[240,240,80],'automatic_retry_count':0,
         'response_reuse':'NOT_AUTHORIZED','budget_root':policy['budget_root']}, 'Continuous allowance differs')
    for key in ('timeout_seconds','retry_count','maximum_payload_bytes','endpoint_host','provider','api'):
        need(effective['S-PROVIDER-TRANSPORT']['choice'][key] == parent['effective_decisions']['S-PROVIDER-TRANSPORT']['choice'][key],
             'Continuous transport boundary expanded: ' + key)
    need(effective['S-PROVIDER-TRANSPORT']['choice']['model'] == 'deepseek-flash'
         and effective['S-TRANSPORT-RETRY']['choice'] == parent['effective_decisions']['S-TRANSPORT-RETRY']['choice'],
         'Continuous model or retry/resource boundary differs')
    d36=effective['D-36']['choice']
    need(d36['repository_monetary_budget_enforcement']=='DISABLED' and d36['monetary_budget_preflight'] is False
         and d36['estimated_or_actual_cost_may_block_provider_call'] is False,'Continuous D36 differs')
    hashes={key:sha256_file(path=snapshot_dir/name) for key,name in (
        ('baseline_sha256','baseline_manifest.json'),('contract_sha256','CONTRACT.md'),
        ('decision_register_sha256','decision_register.json'),('invariant_profile_sha256','invariant_profile.json'),
        ('transfer_manifest_sha256','transfer_manifest.json'))}
    hashes.update(parent_requirement_closure_hash=parent['requirement_closure_hash'],validator_sha256=validator['sha256'])
    return {'artifact_requirement_generation':'EXPLICIT_REQUIREMENT_V1','baseline':baseline,
        'requirement_generation':PROFILE_REQUIREMENT_GENERATION,'requirement_id':REQUIREMENT_ID,
        'requirement_closure_hash':content_hash(value=hashes),'hashes':hashes,
        'execution_authority':baseline['execution_authority'],'activation_state':'LIMITED_CALLS_APPROVED_WIRING_REQUIRED',
        'effective_decisions':effective,'decision_chains':{**parent['decision_chains'],
            **{k:[*parent['decision_chains'].get(k,[]),v] for k,v in decisions['successor_decisions'].items()}},
        'pending_decision_ids':parent['pending_decision_ids'],'resolved_decision_fields':decisions['field_resolutions'],
        'parent_snapshot':parent,'parent_requirement_id':PARENT_ID,'parent_requirement_closure_hash':parent['requirement_closure_hash'],
        'transfer':strict_json_file(path=snapshot_dir/'transfer_manifest.json'),
        'evaluated_invariants':strict_json_file(path=snapshot_dir/'invariant_profile.json'),
        'issue_contract_revision':'continuous-calls-and-b13-v1','policy':policy}
