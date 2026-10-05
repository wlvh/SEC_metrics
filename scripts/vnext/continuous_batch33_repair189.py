"""One concrete engineering-repair slot for failed B13 batch group at 189.

The existing user batch delegation grants a repair only after a new failure,
substantive patch, regression tests and scoped independent review. This
record binds those four items; a changed request digest alone grants nothing.
"""
from pathlib import Path
from types import SimpleNamespace

from .canonical import content_hash, sha256_file, strict_json_file
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = 'config/issue28_b13_repair_189_v1.json'
RECORD_PATH = 'batch33-repair-189.json'


def _config():
    return strict_json_file(path=ROOT/POLICY_PATH)


def validate_failed(*, ledger, policy):
    path = ledger.root/'calls'/('%04d' % policy['failed_ordinal'])
    intent = strict_json_file(path=path/'intent.json')
    terminal = strict_json_file(path=path/'terminal.json')
    wire = strict_json_file(path=path/'wire/journal.json')
    response = strict_json_file(path=path/'wire/raw-response.bin')
    request = strict_json_file(path=path/'semantic-request.json')
    from .capacity_reference_contract import (RELEVANCE_VERSION, ROLE_VERSION,
        restore_base_request, upgrade_request)
    from .continuous_semantic_calls import request_digest
    need(intent['ordinal'] == policy['failed_ordinal'] == 189
         and intent['intent_id'] == policy['failed_intent_id']
         and intent['channel'] == 'PROVIDER'
         and intent['batch_group_id'] == policy['group_id'] == 'B13:enphase_energy:0'
         and intent['batch_authorization_id'] == policy['batch_authorization_id']
         and intent['batch_attempt_index'] == 0
         and intent['request_digest'] == policy['failed_v3_request_digest']
         and terminal['terminal_id'] == policy['failed_terminal_id']
         and terminal['intent_id'] == intent['intent_id']
         and terminal['status'] == 'FAILED_TERMINAL' and not terminal['stop_reason']
         and terminal['counts'] == [1, 1, 0]
         and wire['error_class'] == 'DEEPSEEK_RESPONSE_INVALID'
         and wire['usage']['output_tokens'] == 4096
         and response['choices'][0]['finish_reason'] == 'length'
         and sha256_file(path=path/'wire/raw-response.bin') == policy['failed_raw_response_sha256']
         and sha256_file(path=path/'source.json') == policy['failed_source_sha256']
         and request['source_id'] == policy['source_id']
         and request['source_reference_contract']['version'] == ROLE_VERSION
         and not (path/'wire/assistant-output.bin').exists(),
         'BATCH33_REPAIR189_ORIGINAL_FAILURE_CHANGED')
    base = restore_base_request(request)
    updated = upgrade_request(base, compact=True, role_labels=True, relevance_scope=True)
    need(updated['source_reference_contract']['version'] == RELEVANCE_VERSION
         and updated['source_id'] == request['source_id']
         and updated['units'] == request['units']
         and updated['required_candidate_assessments'] == request['required_candidate_assessments']
         and request_digest(updated, SimpleNamespace(model='deepseek-flash')) ==
             policy['repaired_v4_request_digest']
         and request_digest(request, SimpleNamespace(model='deepseek-flash')) ==
             policy['failed_v3_request_digest'],
         'BATCH33_REPAIR189_REQUEST_SCOPE_CHANGED')
    return intent, terminal


def authorization(*, ledger, check_ledger=True):
    config = _config()
    need(config['state'] == 'SUBSTANTIVE_PATCH_TESTS_SCOPED_REVIEW_BOUND'
         and type(config['patch_sha']) is str and len(config['patch_sha']) == 40
         and type(config['independent_review_path']) is str
         and type(config['independent_review_sha256']) is str
         and type(config['regression_log_path']) is str
         and type(config['regression_log_sha256']) is str
         and type(config['diagnosis_sha256']) is str,
         'BATCH33_REPAIR189_PROOF_PENDING')
    need(ledger.live and str(ledger.root) == config['budget_root']
         and ledger.binding['binding_id'] == config['binding_id']
         and ledger.binding['limits'] == [240, 240, 80],
         'BATCH33_REPAIR189_ORIGINAL_LEDGER_REQUIRED')
    from .continuous_batch33 import read_authorization as read_batch
    if check_ledger:
        batch = read_batch(ledger)
        need(batch is not None and batch['authorization_id'] == config['batch_authorization_id'],
             'BATCH33_REPAIR189_BATCH_CHANGED')
        validate_failed(ledger=ledger, policy=config)
    for path_field, sha_field in (
        ('diagnosis_path','diagnosis_sha256'),
        ('regression_log_path','regression_log_sha256'),
        ('independent_review_path','independent_review_sha256')):
        path = resolve_repository_file(repo_root=ROOT,
                                       repo_relative_path=config[path_field])
        need(sha256_file(path=path) == config[sha_field],
             'BATCH33_REPAIR189_PROOF_CHANGED:' + path_field)
    diagnosis = strict_json_file(path=ROOT/config['diagnosis_path'])
    review = (ROOT/config['independent_review_path']).read_text()
    need(diagnosis['record_type'] == 'ISSUE28_B13_189_OFFLINE_FAILURE_DIAGNOSIS'
         and diagnosis['original_ordinal'] == 189
         and diagnosis['raw_response_sha256'] == config['failed_raw_response_sha256']
         and diagnosis['provider_finish_reason'] == 'length'
         and diagnosis['nonrequired_monetary_credit_findings'] == 115
         and 'verdict: PASS_SCOPED_REPAIR189' in review
         and config['patch_sha'] in review,
         'BATCH33_REPAIR189_EVIDENCE_NOT_ESTABLISHED')
    body = {'record_type':'CONTINUOUS_BATCH33_ENGINEERING_REPAIR_AUTHORIZATION',
            'execution_mode':'LIVE', 'budget_root':config['budget_root'],
            'binding_id':config['binding_id'],
            'batch_authorization_id':config['batch_authorization_id'],
            'group_id':config['group_id'], 'source_id':config['source_id'],
            'failed_ordinal':189, 'failed_intent_id':config['failed_intent_id'],
            'failed_terminal_id':config['failed_terminal_id'],
            'failed_request_digest':config['failed_v3_request_digest'],
            'failed_raw_response_sha256':config['failed_raw_response_sha256'],
            'repaired_request_digest':config['repaired_v4_request_digest'],
            'patch_sha':config['patch_sha'],
            'diagnosis_sha256':config['diagnosis_sha256'],
            'regression_log_sha256':config['regression_log_sha256'],
            'independent_review_sha256':config['independent_review_sha256'],
            'maximum_new_executions':1}
    return {**body, 'authorization_id':content_hash(value=body)}


def read_authorization(ledger):
    path = ledger.root/RECORD_PATH
    if not path.exists():
        return None
    value = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                                  repo_relative_path=RECORD_PATH))
    need(value.get('authorization_id') == content_hash(value={k:v for k,v in value.items()
         if k != 'authorization_id'})
         and value.get('record_type') == 'CONTINUOUS_BATCH33_ENGINEERING_REPAIR_AUTHORIZATION'
         and value.get('budget_root') == str(ledger.root)
         and value.get('binding_id') == ledger.binding['binding_id']
         and value.get('execution_mode') == ('LIVE' if ledger.live else 'RECORDED_TEST_ONLY')
         and value.get('maximum_new_executions') == 1,
         'BATCH33_REPAIR189_SAVED_AUTHORIZATION_CHANGED')
    if ledger.live:
        need(value == authorization(ledger=ledger),
             'BATCH33_REPAIR189_SAVED_PROOF_CHANGED')
    return value


def install_live_authorization(*, ledger, requirement):
    from .invocation_control import _exclusive_write_json
    config = _config()
    path = ledger.root/RECORD_PATH
    if config['state'] == 'PENDING_PATCH_TEST_AND_SCOPED_REVIEW':
        need(not path.exists(), 'BATCH33_REPAIR189_UNAPPROVED_RECORD_PRESENT')
        return None
    need(config['state'] == 'SUBSTANTIVE_PATCH_TESTS_SCOPED_REVIEW_BOUND',
         'BATCH33_REPAIR189_POLICY_STATE_CHANGED')
    for relative in (POLICY_PATH, 'scripts/vnext/continuous_batch33_repair189.py',
                     config['diagnosis_path'], config['regression_log_path'],
                     config['independent_review_path']):
        file = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
        need(requirement['execution_authority']['files'].get(relative) ==
             {'sha256':sha256_file(path=file), 'size':file.stat().st_size},
             'BATCH33_REPAIR189_RULE_OR_PROOF_NOT_BOUND:' + relative)
    approved = authorization(ledger=ledger)
    with ledger.locked():
        state = ledger.snapshot()
        if path.exists():
            need(read_authorization(ledger) == approved,
                 'BATCH33_REPAIR189_ALREADY_DIFFERENT')
        else:
            batch, progress = ledger._batch_observation
            need(batch is not None and batch['authorization_id'] == approved['batch_authorization_id']
                 and progress['attempts'].get(approved['group_id']) == [{
                     'ordinal':189, 'status':'FAILED_TERMINAL', 'stop_reason':''}]
                 and state['counts'][:2] == [140, 140]
                 and len(state['rows']) >= 189
                 and 'PROVIDER' not in state['stopped_channels'],
                 'BATCH33_REPAIR189_INSTALL_LEDGER_DRIFT')
            _exclusive_write_json(path=path, value=approved)
        ledger.snapshot()
    return approved


def recorded_authorization(*, ledger, failed_ordinal, repaired_digest, source_id=None):
    """Only recorded tests can manufacture this local proof-shaped object."""
    from .invocation_control import _exclusive_write_json
    from .continuous_batch33 import read_authorization as read_batch
    need(not ledger.live and ledger._locked, 'BATCH33_REPAIR189_RECORDED_ONLY')
    batch = read_batch(ledger)
    path = ledger.root/'calls'/('%04d' % failed_ordinal)
    intent = strict_json_file(path=path/'intent.json')
    terminal = strict_json_file(path=path/'terminal.json')
    need(batch is not None and terminal['status'] == 'FAILED_TERMINAL'
         and not terminal['stop_reason'] and intent['batch_attempt_index'] == 0,
         'BATCH33_REPAIR189_RECORDED_FAILURE_REQUIRED')
    body = {'record_type':'CONTINUOUS_BATCH33_ENGINEERING_REPAIR_AUTHORIZATION',
            'execution_mode':'RECORDED_TEST_ONLY', 'budget_root':str(ledger.root),
            'binding_id':ledger.binding['binding_id'],
            'batch_authorization_id':batch['authorization_id'],
            'group_id':intent['batch_group_id'],
            'source_id':source_id or content_hash(value='recorded source'),
            'failed_ordinal':failed_ordinal, 'failed_intent_id':intent['intent_id'],
            'failed_terminal_id':terminal['terminal_id'],
            'failed_request_digest':intent['request_digest'],
            'failed_raw_response_sha256':sha256_file(path=path/'wire/raw-response.bin'),
            'repaired_request_digest':repaired_digest,
            'patch_sha':'RECORDED_TEST_ONLY',
            'diagnosis_sha256':'RECORDED_TEST_ONLY',
            'regression_log_sha256':'RECORDED_TEST_ONLY',
            'independent_review_sha256':'RECORDED_TEST_ONLY',
            'maximum_new_executions':1}
    value = {**body,'authorization_id':content_hash(value=body)}
    _exclusive_write_json(path=ledger.root/RECORD_PATH,value=value)
    return value
