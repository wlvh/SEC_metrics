"""A single, separately approved recovery of batch33's new HTTP402 at 172.

This module is fail-closed until an exact user decision is transcribed and
verified against the real Issue comment. It cannot reuse the consumed 110
recovery or the batch's development-error repair opportunity.
"""
from pathlib import Path

from .annual_repair_budget import validate_comment
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = 'config/issue28_recovery_172_v1.json'
RECORD_PATH = 'recovery-172.json'


def _config():
    return strict_json_file(path=ROOT / POLICY_PATH)


def validate_original(*, ledger, approval):
    """The no-output 402 and exact batch request remain the only target."""
    path = ledger.root / 'calls' / ('%04d' % approval['original_ordinal'])
    intent = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                              repo_relative_path='calls/%04d/intent.json' % approval['original_ordinal']))
    terminal = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                                repo_relative_path='calls/%04d/terminal.json' % approval['original_ordinal']))
    wire = strict_json_file(path=path/'wire/journal.json')
    need(intent['intent_id'] == approval['original_intent_id']
         and terminal['terminal_id'] == approval['original_terminal_id']
         and terminal['intent_id'] == intent['intent_id']
         and intent['ordinal'] == approval['original_ordinal']
         and intent['channel'] == 'PROVIDER'
         and intent['request_digest'] == approval['request_digest']
         and intent['batch_group_id'] == approval['batch_group_id']
         and intent['batch_authorization_id'] == approval['batch_authorization_id']
         and intent['batch_attempt_index'] == 0
         and intent['batch_resume_171'] is True
         and terminal['status'] == 'FAILED_TERMINAL'
         and terminal['stop_reason'] == wire['error_class'] == 'HTTP_402'
         and terminal['counts'] == [1, 1, 0]
         and not (path/'wire/assistant-output.bin').exists()
         and sha256_file(path=path/'semantic-request.json') == approval['request_sha256']
         and sha256_file(path=path/'source.json') == approval['source_sha256'],
         'RECOVERY172_ORIGINAL_FAILED_REQUEST_CHANGED')
    return intent, terminal


def authorization(*, ledger, online=False, check_ledger=True):
    """Only a pinned server comment can become a live one-shot authority."""
    config = _config()
    need(config['authorization_state'] == 'EXPLICIT_USER_DECISION_SERVER_VERIFIED'
         and type(config['delegation_url']) is str
         and type(config['delegation_record_path']) is str
         and type(config['delegation_body_sha256']) is str,
         'RECOVERY172_EXPLICIT_APPROVAL_PENDING')
    if online:
        from .annual_candidate import _github
        comment = _github('repos/' + config['repository'] + '/issues/comments/'
                          + config['delegation_url'].rsplit('-', 1)[1])
    else:
        comment = strict_json_file(path=resolve_repository_file(repo_root=ROOT,
                                   repo_relative_path=config['delegation_record_path']))
    body = validate_comment(comment, repository=config['repository'],
                            url=config['delegation_url'])
    need(sha256_bytes(content=comment['body'].encode()) == config['delegation_body_sha256']
         and body['record_type'] == 'ISSUE28_HTTP402_RECOVERY_172_DELEGATION'
         and body['approval_kind'] == 'USER_DELEGATED_SINGLE_172_RECOVERY_ONLY'
         and body['registered_by'] == 'CODEX_ON_EXPLICIT_USER_INSTRUCTION'
         and body['repository'] == config['repository']
         and body['issue_number'] == config['issue_number'] == 28
         and body['original_ordinal'] == config['original_ordinal'] == 172
         and body['original_intent_id'] == config['original_intent_id']
         and body['original_terminal_id'] == config['original_terminal_id']
         and body['original_request_digest'] == config['request_digest']
         and body['original_request_sha256'] == config['request_sha256']
         and body['original_source_sha256'] == config['source_sha256']
         and body['batch_group_id'] == config['batch_group_id'] == 'D04:enphase_energy:0'
         and body['batch_authorization_id'] == config['batch_authorization_id']
         and body['eligible_original_failure'] == 'HTTP_402_WITHOUT_USABLE_MODEL_OUTPUT'
         and body['maximum_new_executions_of_original_request'] == config['maximum_new_executions'] == 1
         and body['consume_on'] == 'NEW_CLAIM_APPEND_NOT_SUCCESS'
         and body['maximum_cumulative_provider_paid_sec_calls'] == [240, 240, 80]
         and body['automatic_retry_count'] == 0
         and body['new_stop_conditions_remain_effective'] is True
         and all(body[field] is False for field in (
             'other_failed_requests_may_repeat', 'original_ledger_history_may_change',
             'request_digest_or_source_may_change', 'new_budget_granted',
             'account_operations_authorized', 'production_authorized')),
         'RECOVERY172_APPROVAL_SCOPE_CHANGED')
    need(ledger.live and str(ledger.root) == config['budget_root'] == body['budget_root']
         and ledger.binding['binding_id'] == config['binding_id'] == body['binding_id']
         and ledger.binding['limits'] == [240, 240, 80],
         'RECOVERY172_ORIGINAL_LEDGER_REQUIRED')
    if check_ledger:
        from .continuous_batch33 import read_authorization as read_batch
        batch = read_batch(ledger)
        need(batch is not None and batch['authorization_id'] == config['batch_authorization_id'],
             'RECOVERY172_BATCH_AUTHORIZATION_CHANGED')
        validate_original(ledger=ledger, approval=config)
    value = {'record_type': 'CONTINUOUS_BATCH33_HTTP402_RECOVERY_AUTHORIZATION',
             'execution_mode': 'LIVE', 'budget_root': config['budget_root'],
             'binding_id': config['binding_id'], 'original_ordinal': 172,
             'original_intent_id': config['original_intent_id'],
             'original_terminal_id': config['original_terminal_id'],
             'request_digest': config['request_digest'],
             'request_sha256': config['request_sha256'],
             'source_sha256': config['source_sha256'],
             'batch_group_id': config['batch_group_id'],
             'batch_authorization_id': config['batch_authorization_id'],
             'delegation_url': config['delegation_url'],
             'delegation_body_sha256': config['delegation_body_sha256'],
             'maximum_new_executions': 1}
    return {**value, 'authorization_id': content_hash(value=value)}


def read_authorization(ledger):
    path = ledger.root / RECORD_PATH
    if not path.exists():
        return None
    value = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                                  repo_relative_path=RECORD_PATH))
    need(value.get('authorization_id') == content_hash(value={k: v for k, v in value.items()
         if k != 'authorization_id'})
         and value.get('record_type') == 'CONTINUOUS_BATCH33_HTTP402_RECOVERY_AUTHORIZATION'
         and value.get('budget_root') == str(ledger.root)
         and value.get('binding_id') == ledger.binding['binding_id']
         and value.get('execution_mode') == ('LIVE' if ledger.live else 'RECORDED_TEST_ONLY')
         and value.get('maximum_new_executions') == 1,
         'RECOVERY172_SAVED_AUTHORIZATION_CHANGED')
    if ledger.live:
        need(value == authorization(ledger=ledger), 'RECOVERY172_SAVED_APPROVAL_DIFFERS')
    else:
        validate_original(ledger=ledger, approval=value)
    return value


def install_live_authorization(*, ledger, requirement):
    """Pending policy never installs; approved policy requires final bound bytes."""
    from .invocation_control import _exclusive_write_json
    config = _config()
    if config['authorization_state'] == 'PENDING_EXPLICIT_USER_DECISION':
        need(not (ledger.root/RECORD_PATH).exists(), 'RECOVERY172_UNAPPROVED_RECORD_PRESENT')
        return None
    need(config['authorization_state'] == 'EXPLICIT_USER_DECISION_SERVER_VERIFIED',
         'RECOVERY172_POLICY_STATE_CHANGED')
    for relative in (POLICY_PATH, 'scripts/vnext/continuous_recovery_172.py',
                     config['delegation_record_path']):
        path = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
        need(requirement['execution_authority']['files'].get(relative) ==
             {'sha256': sha256_file(path=path), 'size': path.stat().st_size},
             'RECOVERY172_RULE_OR_COMMENT_NOT_BOUND:' + relative)
    approved = authorization(ledger=ledger, online=True)
    with ledger.locked():
        state = ledger.snapshot()
        if (ledger.root/RECORD_PATH).exists():
            need(read_authorization(ledger) == approved,
                 'RECOVERY172_AUTHORIZATION_ALREADY_DIFFERENT')
        else:
            from .continuous_batch33 import group_id, groups_for
            batch, progress = ledger._batch_observation
            need(batch is not None and progress['total'] == 1
                 and state['counts'][:2] == [123, 123] and state['counts'][2] >= 49
                 and len(state['rows']) >= 172
                 and [row for row in groups_for(batch) if group_id(row) == approved['batch_group_id']]
                 and progress['attempts'][approved['batch_group_id']] == [{
                     'ordinal': 172, 'status': 'FAILED_TERMINAL', 'stop_reason': 'HTTP_402'}]
                 and {stop for stop in ledger._recovery_observation[2]
                      if stop[0] == 'PROVIDER'} == {('PROVIDER', 172)},
                 'RECOVERY172_INSTALL_LEDGER_DRIFT')
            _exclusive_write_json(path=ledger.root/RECORD_PATH, value=approved)
        ledger.snapshot()
    return approved


def recorded_authorization(*, ledger, original_ordinal):
    """Offline-only authority for tests; never convertible to LIVE."""
    from .invocation_control import _exclusive_write_json
    from .continuous_batch33 import read_authorization as read_batch
    need(not ledger.live and ledger._locked, 'RECOVERY172_RECORDED_ONLY')
    batch = read_batch(ledger)
    need(batch is not None, 'RECOVERY172_BATCH_AUTHORIZATION_REQUIRED')
    path = ledger.root/'calls'/('%04d' % original_ordinal)
    intent = strict_json_file(path=path/'intent.json')
    terminal = strict_json_file(path=path/'terminal.json')
    body = {'record_type': 'CONTINUOUS_BATCH33_HTTP402_RECOVERY_AUTHORIZATION',
            'execution_mode': 'RECORDED_TEST_ONLY', 'budget_root': str(ledger.root),
            'binding_id': ledger.binding['binding_id'],
            'original_ordinal': original_ordinal,
            'original_intent_id': intent['intent_id'],
            'original_terminal_id': terminal['terminal_id'],
            'request_digest': intent['request_digest'],
            'request_sha256': sha256_file(path=path/'semantic-request.json'),
            'source_sha256': sha256_file(path=path/'source.json'),
            'batch_group_id': intent['batch_group_id'],
            'batch_authorization_id': batch['authorization_id'],
            'maximum_new_executions': 1}
    value = {**body, 'authorization_id': content_hash(value=body)}
    validate_original(ledger=ledger, approval=value)
    _exclusive_write_json(path=ledger.root/RECORD_PATH, value=value)
    return value
