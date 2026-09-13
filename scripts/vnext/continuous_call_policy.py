"""User-approved successor call scope; reading a record never opens a socket."""
from pathlib import Path

from .annual_repair_budget import validate_comment
from .canonical import content_hash, sha256_bytes, strict_json_file
from .sources import resolve_repository_file

REQUIREMENT_ID = 'issue_28_v14'
POLICY_PATH = 'config/issue28_continuous_calls_v1.json'
DECISION_ID = 'S-ISSUE28-CONTINUOUS-CALLS'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def delegation_fields(comment, *, policy):
    body = validate_comment(comment, repository=policy['repository'], url=policy['delegation_url'])
    need(sha256_bytes(content=comment['body'].encode()) == policy['delegation_body_sha256'],
         'CONTINUOUS_DELEGATION_BODY_CHANGED')
    need(body['record_type'] == 'ISSUE_28_CONTINUOUS_CALL_AND_B13_DELEGATION'
         and body['approval_kind'] == 'USER_DELEGATED_POLICY_AND_BUDGET_ONLY'
         and body['maximum_additional_provider_paid_sec_calls'] == policy['maximum_additional_provider_paid_sec_calls']
         and body['scope'] == policy['scope'] and body['budget_root'] == policy['budget_root']
         and body['provider'] == 'deepseek' and body['model'] == 'deepseek-flash'
         and body['api'] == 'chat_completions' and body['automatic_retry_count'] == 0
         and body['unchanged_request_redraw_authorized'] is False
         and body['closed_stage_credit_reuse_authorized'] is False
         and body['unknown_usage_may_be_zero'] is False
         and body['repository_monetary_budget_enforcement'] == 'DISABLED'
         and body['monetary_budget_preflight'] is False
         and body['estimated_or_actual_cost_may_block_provider_call'] is False,
         'CONTINUOUS_DELEGATION_SCOPE_CHANGED')
    need(all(body[k] is False for k in ['ready_authorized','merge_authorized','formal_adoption_authorized',
         'deployment_authorized','active_switch_authorized','long_running_schedule_authorized',
         'account_inspection_authorized','account_recharge_authorized','account_settings_change_authorized']),
         'CONTINUOUS_PRODUCTION_OR_ACCOUNT_PERMISSION_FORBIDDEN')
    need(sha256_bytes(content=body['user_approved_sections_verbatim'].encode()) == body['verbatim_sections_sha256']
         and body['b13'] == policy['b13'], 'CONTINUOUS_APPROVED_TEXT_OR_B13_CHANGED')
    return body


def load_delegation(*, requirement, online=False):
    policy = requirement['policy']
    need(requirement['requirement_id'] == REQUIREMENT_ID, 'CONTINUOUS_REQUIREMENT_REQUIRED')
    if online:
        from .annual_candidate import _github
        comment = _github('repos/' + policy['repository'] + '/issues/comments/' + policy['delegation_url'].rsplit('-',1)[1])
    else:
        root = Path(__file__).resolve().parents[2]
        comment = strict_json_file(path=resolve_repository_file(repo_root=root,
            repo_relative_path=policy['delegation_record_path']))
    delegation_fields(comment, policy=policy)
    return comment


def invocation_policy(*, requirement):
    """Same WB-3 successor policy shape, bound to this new allowance only."""
    need(requirement['requirement_id'] == REQUIREMENT_ID, 'CONTINUOUS_REQUIREMENT_REQUIRED')
    decisions = requirement['effective_decisions']
    call = decisions[DECISION_ID]
    need(call['status'] == 'APPROVED' and call['choice']['automatic_retry_count'] == 0,
         'CONTINUOUS_CALL_POLICY_NOT_APPROVED')
    return {'provider_transport_decision_hash':content_hash(value=decisions['S-PROVIDER-TRANSPORT']),
        'transport_retry_decision_hash':content_hash(value=decisions['S-TRANSPORT-RETRY']),
        'live_call_bound_decision_hash':content_hash(value=call),'automatic_retry_count':0,
        'response_reuse_authorized':False,'requirement_closure_hash':requirement['requirement_closure_hash']}


def configured_transport_policy(*, requirement, repo_root):
    """Select this successor's bound configuration, never a legacy default."""
    from .ai_adapter import TransportPolicy
    from .provider_runtime import load_provider_runtime_authority
    need(requirement['requirement_id'] == REQUIREMENT_ID, 'CONTINUOUS_REQUIREMENT_REQUIRED')
    path = resolve_repository_file(repo_root=repo_root,repo_relative_path='config/provider_model_runtime.json')
    raw = path.read_bytes()
    need(requirement['execution_authority']['files']['config/provider_model_runtime.json']
         == {'sha256':sha256_bytes(content=raw),'size':len(raw)}, 'CONTINUOUS_MODEL_CONFIGURATION_CHANGED')
    choice = dict(requirement['effective_decisions']['S-PROVIDER-TRANSPORT']['choice'])
    choice.pop('kind')
    selected = TransportPolicy.from_mapping(value=choice)
    need((selected.provider,selected.model,selected.api) == ('deepseek','deepseek-flash','chat_completions')
         and selected.retry_count == 0, 'CONTINUOUS_TRANSPORT_CHANGED')
    load_provider_runtime_authority(repo_root=repo_root,provider=selected.provider,model=selected.model,api=selected.api)
    return selected
