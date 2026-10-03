"""One explicitly approved HTTP402 recovery in the original Issue28 ledger.

No new allowance, changed digest, account operation or automatic retry. The
new claim carries the consumption record; original failure bytes stay intact.
"""
from pathlib import Path

from .annual_repair_budget import validate_comment
from .canonical import content_hash, sha256_file, sha256_bytes, strict_json_file, canonical_json_bytes
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .sources import resolve_repository_file

POLICY_PATH = 'config/issue28_recovery_110_v1.json'
RECORD_PATH = 'recovery-110.json'


def authorization(*, ledger, online=False):
    """Derive permission from the pinned real owner comment, never a local flag."""
    config = strict_json_file(path=ROOT / POLICY_PATH)
    if online:
        from .annual_candidate import _github
        comment = _github('repos/' + config['repository'] + '/issues/comments/'
                          + config['delegation_url'].rsplit('-', 1)[1])
    else:
        comment = strict_json_file(path=resolve_repository_file(repo_root=ROOT,
                                   repo_relative_path=config['delegation_record_path']))
    body = validate_comment(comment, repository=config['repository'], url=config['delegation_url'])
    need(sha256_bytes(content=comment['body'].encode()) == config['delegation_body_sha256'],
         'RECOVERY110_APPROVAL_CHANGED')
    need(body['record_type'] == 'ISSUE28_HTTP402_RECOVERY_110_DELEGATION'
         and body['approval_kind'] == 'USER_DELEGATED_SINGLE_RECOVERY_ONLY'
         and body['repository'] == config['repository'] and body['issue_number'] == 28
         and body['original_ordinal'] == 110
         and body['eligible_original_failure'] == 'HTTP_402_WITHOUT_USABLE_MODEL_OUTPUT'
         and body['maximum_new_executions_of_original_request'] == 1
         and body['consume_on'] == 'NEW_CLAIM_APPEND_NOT_SUCCESS'
         and body['maximum_cumulative_provider_paid_sec_calls'] == [240, 240, 80]
         and body['automatic_retry_count'] == 0
         and body['following_provider_metric_ids'] == ['B13', 'D04']
         and body['new_stop_conditions_remain_effective'] is True
         and all(body[field] is False for field in (
             'other_failed_requests_may_repeat', 'request_digest_algorithm_may_change',
             'business_source_grouping_prompt_output_contract_model_parameters_may_change_for_recovery',
             'original_ledger_binding_anchor_history_may_change', 'new_budget_granted',
             'D03_calls_authorized', 'account_operations_authorized', 'production_authorized')),
         'RECOVERY110_APPROVAL_SCOPE_CHANGED')
    need(str(ledger.root) == body['budget_root']
         and ledger.binding['binding_id'] == body['original_binding_id']
         and ledger.binding['limits'] == [240, 240, 80] and ledger.live,
         'RECOVERY110_ORIGINAL_LEDGER_REQUIRED')
    value = {'record_type': 'CONTINUOUS_HTTP402_RECOVERY_AUTHORIZATION',
             'execution_mode': 'LIVE', 'budget_root': body['budget_root'],
             'binding_id': body['original_binding_id'], 'original_ordinal': 110,
             'original_intent_id': body['original_intent_id'],
             'original_terminal_id': body['original_terminal_id'],
             'request_digest': body['original_request_digest'],
             'original_request_sha256': body['original_request_sha256'],
             'original_source_sha256': body['original_source_sha256'],
             'delegation_url': config['delegation_url'],
             'delegation_body_sha256': config['delegation_body_sha256'],
             'maximum_new_executions': 1}
    return {**value, 'authorization_id': content_hash(value=value)}


def read_authorization(ledger):
    path = ledger.root / RECORD_PATH
    if not path.exists():
        return None
    value = strict_json_file(path=resolve_repository_file(repo_root=ledger.root, repo_relative_path=RECORD_PATH))
    need(value.get('authorization_id') == content_hash(value={k:v for k,v in value.items() if k != 'authorization_id'})
         and value.get('record_type') == 'CONTINUOUS_HTTP402_RECOVERY_AUTHORIZATION'
         and value.get('budget_root') == str(ledger.root)
         and value.get('binding_id') == ledger.binding['binding_id']
         and type(value.get('original_ordinal')) is int and value['original_ordinal'] > 0
         and value.get('maximum_new_executions') == 1,
         'RECOVERY110_SAVED_AUTHORIZATION_CHANGED')
    if ledger.live:
        need(value == authorization(ledger=ledger), 'RECOVERY110_SAVED_APPROVAL_DIFFERS')
    else:
        need(value.get('execution_mode') == 'RECORDED_TEST_ONLY', 'RECOVERY110_TEST_MODE_REQUIRED')
    return value


def validate_original(*, ledger, authorization, intent, terminal, path):
    need(intent['ordinal'] == authorization['original_ordinal']
         and intent['intent_id'] == authorization['original_intent_id']
         and intent['channel'] == 'PROVIDER'
         and intent['request_digest'] == authorization['request_digest']
         and terminal['terminal_id'] == authorization['original_terminal_id']
         and terminal['status'] == 'FAILED_TERMINAL' and terminal['stop_reason'] == 'HTTP_402'
         and terminal['counts'] == [1, 1, 0], 'RECOVERY110_ORIGINAL_FAILURE_CHANGED')
    wire = strict_json_file(path=resolve_repository_file(repo_root=path, repo_relative_path='wire/journal.json'))
    need(wire['error_class'] == 'HTTP_402' and not (path / 'wire/assistant-output.bin').exists(),
         'RECOVERY110_USABLE_OUTPUT_OR_OTHER_FAILURE')
    for name, field in [('semantic-request.json', 'original_request_sha256'), ('source.json', 'original_source_sha256')]:
        need(sha256_file(path=resolve_repository_file(repo_root=path, repo_relative_path=name)) == authorization[field],
             'RECOVERY110_ORIGINAL_INPUT_CHANGED')


def install_live_authorization(*, ledger, requirement):
    from .invocation_control import _exclusive_write_json
    for relative in (POLICY_PATH, 'scripts/vnext/continuous_recovery_110.py'):
        path = ROOT / relative
        need(requirement['execution_authority']['files'].get(relative) ==
             {'sha256': sha256_file(path=path), 'size': path.stat().st_size},
             'RECOVERY110_RULE_NOT_BOUND')
    config = strict_json_file(path=ROOT / POLICY_PATH)
    path = ROOT / config['delegation_record_path']
    need(requirement['execution_authority']['files'].get(config['delegation_record_path']) ==
         {'sha256': sha256_file(path=path), 'size': path.stat().st_size}, 'RECOVERY110_APPROVAL_NOT_BOUND')
    value = authorization(ledger=ledger, online=True)
    with ledger.locked():
        # Validate the unchanged original and all prior counting before append.
        ledger.snapshot()
        original = ledger.root / 'calls/0110'
        validate_original(ledger=ledger, authorization=value,
                          intent=strict_json_file(path=original/'intent.json'),
                          terminal=strict_json_file(path=original/'terminal.json'), path=original)
        if (ledger.root / RECORD_PATH).exists():
            need(read_authorization(ledger) == value, 'RECOVERY110_AUTHORIZATION_ALREADY_DIFFERENT')
        else:
            _exclusive_write_json(path=ledger.root/RECORD_PATH, value=value)
        ledger.snapshot()


def recorded_authorization(*, ledger, original_ordinal):
    """Explicit test-only registration in an isolated recorded ledger."""
    from .invocation_control import _exclusive_write_json
    need(not ledger.live and ledger._locked, 'RECOVERY110_RECORDED_ONLY')
    path = ledger.root / 'calls' / ('%04d' % original_ordinal)
    intent = strict_json_file(path=path/'intent.json'); terminal = strict_json_file(path=path/'terminal.json')
    value = {'record_type': 'CONTINUOUS_HTTP402_RECOVERY_AUTHORIZATION', 'execution_mode': 'RECORDED_TEST_ONLY',
             'budget_root': str(ledger.root), 'binding_id': ledger.binding['binding_id'],
             'original_ordinal': original_ordinal, 'original_intent_id': intent['intent_id'],
             'original_terminal_id': terminal['terminal_id'], 'request_digest': intent['request_digest'],
             'original_request_sha256': sha256_file(path=path/'semantic-request.json'),
             'original_source_sha256': sha256_file(path=path/'source.json'), 'maximum_new_executions': 1}
    value['authorization_id'] = content_hash(value=value)
    validate_original(ledger=ledger, authorization=value, intent=intent, terminal=terminal, path=path)
    _exclusive_write_json(path=ledger.root/RECORD_PATH, value=value)
    return value


def history_for_success(*, ledger, intent, terminal):
    """Retain the failed record separately; only its new successor is usable."""
    value = read_authorization(ledger)
    need(value is not None and intent.get('recovery_authorization_id') == value['authorization_id'],
         'RECOVERY110_SUCCESS_AUTHORIZATION_MISSING')
    path = ledger.root/'calls'/('%04d' % value['original_ordinal'])
    history = {'authorization': value, 'original_intent': strict_json_file(path=path/'intent.json'),
               'original_terminal': strict_json_file(path=path/'terminal.json'),
               'original_wire': strict_json_file(path=path/'wire/journal.json'),
               'recovered_ordinal': intent['ordinal']}
    validate_history(history=history, intent=intent, terminal=terminal,
                     mode='LIVE' if ledger.live else 'RECORDED_TEST_ONLY')
    return history


def validate_history(*, history, intent, terminal, mode):
    """Cold readers verify the narrowly approved failure and its new success."""
    from types import SimpleNamespace
    need(type(history) is dict and set(history) == {
        'authorization', 'original_intent', 'original_terminal', 'original_wire', 'recovered_ordinal'},
        'RECOVERY110_HISTORY_FIELDS_CHANGED')
    auth = history['authorization']; old = history['original_intent']; failed = history['original_terminal']
    for value, key in [(auth, 'authorization_id'), (old, 'intent_id'), (failed, 'terminal_id')]:
        need(value[key] == content_hash(value={k:v for k,v in value.items() if k != key}),
             'RECOVERY110_HISTORY_ID_CHANGED')
    need(mode in {'LIVE', 'RECORDED_TEST_ONLY'} and auth['execution_mode'] == mode
         and auth['maximum_new_executions'] == 1
         and old['execution_mode'] == mode and intent['execution_mode'] == mode
         and old['binding_id'] == intent['binding_id'] == auth['binding_id']
         and old['intent_id'] == auth['original_intent_id'] == failed['intent_id']
         and old['ordinal'] == auth['original_ordinal'] < history['recovered_ordinal'] == intent['ordinal']
         and old['channel'] == intent['channel'] == 'PROVIDER'
         and old['request_digest'] == intent['request_digest'] == auth['request_digest']
         and intent.get('recovery_authorization_id') == auth['authorization_id']
         and failed['terminal_id'] == auth['original_terminal_id']
         and failed['status'] == 'FAILED_TERMINAL' and failed['stop_reason'] == 'HTTP_402'
         and failed['counts'] == [1,1,0]
         and history['original_wire']['error_class'] == 'HTTP_402'
         and failed['evidence']['wire/journal.json'] == sha256_bytes(content=canonical_json_bytes(value=history['original_wire']))
         and 'wire/assistant-output.bin' not in failed['evidence']
         and failed['evidence']['semantic-request.json'] == auth['original_request_sha256']
         and failed['evidence']['source.json'] == auth['original_source_sha256']
         and terminal['intent_id'] == intent['intent_id'] and terminal['status'] == 'SUCCEEDED'
         and not terminal['stop_reason'], 'RECOVERY110_HISTORY_LINK_CHANGED')
    if mode == 'LIVE':
        view = SimpleNamespace(root=Path(auth['budget_root']), live=True,
                               binding={'binding_id':auth['binding_id'], 'limits':[240,240,80]})
        need(auth == authorization(ledger=view), 'RECOVERY110_HISTORY_APPROVAL_CHANGED')
