"""Ordinary current request configuration, without Requirement ancestry.

Configuration is not a new call permission. Existing allowance, group limits,
stop conditions and request digests remain in the original CallLedger.
"""
from pathlib import Path
from dataclasses import replace
from .canonical import content_hash, strict_json_file
from .continuous_call_policy import POLICY_PATH, need
from .request_limits import configured_limits

PATH = 'config/issue28_current_request_runtime_v1.json'
KIND = 'CURRENT_REQUEST_CONFIGURATION_V1'


def load_current_configuration(*, repo_root):
    runtime = strict_json_file(path=Path(repo_root)/PATH)
    saved_allowance = strict_json_file(path=Path(repo_root)/POLICY_PATH)
    # Retain only the allowance fields actually consumed by this route.
    # Old rule lists/wiring paths/Requirement IDs are historical metadata,
    # not processing configuration or a new reason to invalidate a request.
    fields = ('maximum_additional_provider_paid_sec_calls','provider','model','api',
              'automatic_retry_count','budget_root','scope','delegation_url',
              'delegation_body_sha256','delegation_record_path')
    allowance = {key:saved_allowance[key] for key in fields}
    need(runtime['schema_version'] == 1 and runtime['configuration_id'] ==
         'issue28_current_request_runtime_v1' and runtime['automatic_retry_count'] == 0
         and runtime['unknown_usage_may_be_zero'] is False
         and runtime['response_redraw_authorized'] is False,
         'CURRENT_REQUEST_CONFIGURATION_INVALID')
    need(runtime['allowed_metrics'] == ['B13','D03','D04']
         and runtime['live_metrics'] == ['B13','D04']
         and runtime['allowed_live_request_limits'] == configured_limits().as_dict(),
         'CURRENT_REQUEST_SCOPE_CHANGED')
    need(allowance['maximum_additional_provider_paid_sec_calls'] == [240,240,80]
         and (allowance['provider'], allowance['model'], allowance['api']) ==
         ('deepseek','deepseek-flash','chat_completions')
         and allowance['automatic_retry_count'] == 0,
         'CURRENT_CALL_ALLOWANCE_CHANGED')
    body = {'record_type': KIND, 'runtime': runtime, 'policy': allowance}
    identity = content_hash(value=body)
    # These existing WB-3 record fields identify configuration only. They do
    # not point to a recursively loaded Requirement or a new approval object.
    return {**body, 'requirement_id': runtime['configuration_id'],
            'requirement_closure_hash': identity, 'configuration_hash': identity}


def transport_policy(*, configuration, repo_root, limits=None):
    from .ai_adapter import TransportPolicy, _DEEPSEEK_ENDPOINT_HOST
    from .provider_runtime import load_provider_runtime_authority
    limits = configured_limits(limits)
    current = load_current_configuration(repo_root=repo_root)
    need(configuration == current, 'CURRENT_REQUEST_CONFIGURATION_CHANGED')
    selected = TransportPolicy.from_mapping(value=current['runtime']['transport'])
    need((selected.provider, selected.model, selected.api, selected.endpoint_host,
          selected.retry_count) == ('deepseek','deepseek-flash','chat_completions',
                                   _DEEPSEEK_ENDPOINT_HOST,0), 'CURRENT_TRANSPORT_CHANGED')
    load_provider_runtime_authority(repo_root=repo_root, provider=selected.provider,
                                   model=selected.model, api=selected.api)
    return replace(selected, maximum_payload_bytes=limits.max_payload_bytes)


def live_scope(*, configuration, metric_id, limits):
    need(metric_id in configuration['runtime']['live_metrics'],
         'CURRENT_METRIC_LIVE_EXECUTION_NOT_AUTHORIZED')
    need(configured_limits(limits).as_dict() ==
         configuration['runtime']['allowed_live_request_limits'],
         'CURRENT_NONDEFAULT_LIVE_LIMITS_NOT_AUTHORIZED')
