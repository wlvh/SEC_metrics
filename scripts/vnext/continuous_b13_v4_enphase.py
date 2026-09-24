"""One reviewed V4 correction for real Enphase B13 group1 and unopened groups2-5.

The group1 second claim consumes its sole engineering-repair opportunity.
Groups2-5 retain one base claim each. The original V3 group identities and
both failed terminals remain in the batch history.
"""
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = 'config/issue28_b13_v4_enphase_v1.json'
RECORD_PATH = 'batch33-b13-v4-enphase.json'


def _config():
    return strict_json_file(path=ROOT / POLICY_PATH)


def _originals(*, ledger, config):
    old190 = ledger.root / 'calls/0190'
    old191 = ledger.root / 'calls/0191'
    i190 = strict_json_file(path=old190 / 'intent.json')
    t190 = strict_json_file(path=old190 / 'terminal.json')
    i191 = strict_json_file(path=old191 / 'intent.json')
    t191 = strict_json_file(path=old191 / 'terminal.json')
    w191 = strict_json_file(path=old191 / 'wire/journal.json')
    r191 = strict_json_file(path=old191 / 'wire/raw-response.bin')
    from .continuous_batch33_repair189 import read_authorization as prior_repair
    prior = prior_repair(ledger)
    need(prior is not None and prior['authorization_id'] == config['prior_repair_189_id']
         and i190['ordinal'] == 190 and i190['batch_group_id'] == 'B13:enphase_energy:0'
         and i190['batch_repair_189_id'] == prior['authorization_id']
         and i190['intent_id'] == config['prior_success_190_intent_id']
         and t190['terminal_id'] == config['prior_success_190_terminal_id']
         and t190['status'] == 'SUCCEEDED' and t190['counts'] == [1, 1, 0]
         and i191['ordinal'] == config['failed_ordinal'] == 191
         and i191['batch_group_id'] == config['failed_group_id'] == 'B13:enphase_energy:1'
         and i191['batch_attempt_index'] == 0
         and i191['intent_id'] == config['failed_intent_id']
         and i191['request_digest'] == config['failed_v3_digest']
         and t191['terminal_id'] == config['failed_terminal_id']
         and t191['status'] == 'FAILED_TERMINAL' and not t191['stop_reason']
         and t191['counts'] == [1, 1, 0]
         and w191['error_class'] == 'DEEPSEEK_RESPONSE_INVALID'
         and w191['usage']['output_tokens'] == 4096
         and r191['choices'][0]['finish_reason'] == 'length'
         and sha256_file(path=old191 / 'wire/raw-response.bin') ==
             config['failed_raw_response_sha256']
         and sha256_file(path=old191 / 'source.json') ==
             config['failed_source_sha256']
         and not (old191 / 'wire/assistant-output.bin').exists(),
         'B13_V4_ENPHASE_ORIGINAL_TERMINALS_CHANGED')
    return i190, t190, i191, t191, w191


def authorization(*, ledger, check_ledger=True):
    config = _config()
    need(config['state'] == 'SUBSTANTIVE_PATCH_TESTS_SCOPED_REVIEW_BOUND'
         and type(config['patch_sha']) is str and len(config['patch_sha']) == 40
         and all(type(config[key]) is str for key in (
             'diagnosis_sha256', 'preflight_sha256', 'regression_log_sha256',
             'independent_review_sha256', 'regression_log_path',
             'independent_review_path')),
         'B13_V4_ENPHASE_PROOF_PENDING')
    need(ledger.live and str(ledger.root) == config['budget_root']
         and ledger.binding['binding_id'] == config['binding_id']
         and ledger.binding['limits'] == [240, 240, 80],
         'B13_V4_ENPHASE_ORIGINAL_LEDGER_REQUIRED')
    from .continuous_batch33 import read_authorization as read_batch, groups_for, group_id
    if check_ledger:
        batch = read_batch(ledger)
        need(batch is not None and batch['authorization_id'] == config['batch_authorization_id'],
             'B13_V4_ENPHASE_BATCH_CHANGED')
        _originals(ledger=ledger, config=config)
        expected = {group_id(row): row for row in groups_for(batch)}
        rows = config['successor_groups']
        need(type(rows) is list and [row['group_index'] for row in rows] == [1, 2, 3, 4, 5]
             and all(row['group_id'] in expected
                     and row['v3_digest'] == expected[row['group_id']]['initial_request_digest']
                     and row['source_id'] == expected[row['group_id']]['source_id']
                     and row['group_id'] == 'B13:enphase_energy:' + str(row['group_index'])
                     for row in rows)
             and rows[0]['v3_digest'] == config['failed_v3_digest']
             and config['base_groups_without_prior_attempt'] == [2, 3, 4, 5]
             and config['maximum_repair_executions_for_group1'] == 1
             and config['base_claims_for_unopened_groups'] == 4,
             'B13_V4_ENPHASE_GROUP_MAP_CHANGED')
    for field in ('diagnosis', 'preflight', 'regression_log', 'independent_review'):
        path = resolve_repository_file(repo_root=ROOT,
                                       repo_relative_path=config[field + '_path'])
        need(sha256_file(path=path) == config[field + '_sha256'],
             'B13_V4_ENPHASE_PROOF_CHANGED:' + field)
    diagnosis = strict_json_file(path=ROOT / config['diagnosis_path'])
    preflight = strict_json_file(path=ROOT / config['preflight_path'])
    review = (ROOT / config['independent_review_path']).read_text()
    need(diagnosis['record_type'] == 'ISSUE28_B13_191_OFFLINE_FAILURE_DIAGNOSIS'
         and diagnosis['original_ordinal'] == 191
         and diagnosis['raw_response_sha256'] == config['failed_raw_response_sha256']
         and diagnosis['provider_finish_reason'] == 'length'
         and diagnosis['required_candidate_count'] == 0
         and diagnosis['nonrequired_exclusion_findings'] == 162
         and preflight['record_type'] == 'ISSUE28_B13_191_ENPHASE_V4_NO_CALL_PREFLIGHT'
         and preflight['status'] == 'PASS_GROUPS_1_TO_5_SOURCE_REQUIRED_AND_CONTEXT_PRESERVED'
         and preflight['groups'] == config['successor_groups']
         and preflight['new_calls'] == [0, 0, 0]
         and 'verdict: PASS_SCOPED_ENPHASE_V4_ROLLOUT' in review
         and config['patch_sha'] in review,
         'B13_V4_ENPHASE_EVIDENCE_NOT_ESTABLISHED')
    body = {
        'record_type': 'CONTINUOUS_BATCH33_B13_ENPHASE_V4_AUTHORIZATION',
        'execution_mode': 'LIVE', 'budget_root': config['budget_root'],
        'binding_id': config['binding_id'],
        'batch_authorization_id': config['batch_authorization_id'],
        'prior_repair_189_id': config['prior_repair_189_id'],
        'prior_success_190_intent_id': config['prior_success_190_intent_id'],
        'prior_success_190_terminal_id': config['prior_success_190_terminal_id'],
        'failed_group_id': config['failed_group_id'],
        'failed_ordinal': 191, 'failed_intent_id': config['failed_intent_id'],
        'failed_terminal_id': config['failed_terminal_id'],
        'failed_v3_digest': config['failed_v3_digest'],
        'failed_raw_response_sha256': config['failed_raw_response_sha256'],
        'successor_groups': config['successor_groups'],
        'base_groups_without_prior_attempt': [2, 3, 4, 5],
        'maximum_repair_executions_for_group1': 1,
        'patch_sha': config['patch_sha'],
        'diagnosis_sha256': config['diagnosis_sha256'],
        'preflight_sha256': config['preflight_sha256'],
        'regression_log_sha256': config['regression_log_sha256'],
        'independent_review_sha256': config['independent_review_sha256'],
        'maximum_new_executions': 5,
    }
    return {**body, 'authorization_id': content_hash(value=body)}


def read_authorization(ledger):
    path = ledger.root / RECORD_PATH
    if not path.exists():
        return None
    value = strict_json_file(path=resolve_repository_file(
        repo_root=ledger.root, repo_relative_path=RECORD_PATH))
    need(value.get('authorization_id') == content_hash(value={
        key: item for key, item in value.items() if key != 'authorization_id'}),
         'B13_V4_ENPHASE_SAVED_ID_CHANGED')
    need(value.get('record_type') == 'CONTINUOUS_BATCH33_B13_ENPHASE_V4_AUTHORIZATION'
         and value.get('execution_mode') == ('LIVE' if ledger.live else 'RECORDED_TEST_ONLY')
         and value.get('budget_root') == str(ledger.root)
         and value.get('binding_id') == ledger.binding['binding_id']
         and value.get('maximum_new_executions') == 5,
         'B13_V4_ENPHASE_SAVED_AUTHORIZATION_CHANGED')
    if ledger.live:
        need(value == authorization(ledger=ledger),
             'B13_V4_ENPHASE_SAVED_PROOF_CHANGED')
    return value


def install_live_authorization(*, ledger, requirement):
    from .invocation_control import _exclusive_write_json
    config = _config()
    path = ledger.root / RECORD_PATH
    if config['state'] == 'PENDING_PATCH_TEST_AND_SCOPED_REVIEW':
        need(not path.exists(), 'B13_V4_ENPHASE_UNAPPROVED_RECORD_PRESENT')
        return None
    need(config['state'] == 'SUBSTANTIVE_PATCH_TESTS_SCOPED_REVIEW_BOUND',
         'B13_V4_ENPHASE_POLICY_STATE_CHANGED')
    for relative in (POLICY_PATH, 'scripts/vnext/continuous_b13_v4_enphase.py',
                     config['diagnosis_path'], config['preflight_path'],
                     config['regression_log_path'], config['independent_review_path']):
        file = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
        need(requirement['execution_authority']['files'].get(relative) == {
            'sha256': sha256_file(path=file), 'size': file.stat().st_size},
            'B13_V4_ENPHASE_RULE_OR_PROOF_NOT_BOUND:' + relative)
    approved = authorization(ledger=ledger)
    with ledger.locked():
        state = ledger.snapshot()
        if path.exists():
            need(read_authorization(ledger) == approved,
                 'B13_V4_ENPHASE_ALREADY_DIFFERENT')
        else:
            batch, progress = ledger._batch_observation
            need(batch is not None and batch['authorization_id'] == approved['batch_authorization_id']
                 and progress['attempts'].get('B13:enphase_energy:0') == [
                     {'ordinal': 189, 'status': 'FAILED_TERMINAL', 'stop_reason': ''},
                     {'ordinal': 190, 'status': 'SUCCEEDED', 'stop_reason': ''}]
                 and progress['attempts'].get('B13:enphase_energy:1') == [
                     {'ordinal': 191, 'status': 'FAILED_TERMINAL', 'stop_reason': ''}]
                 and all(not progress['attempts'].get('B13:enphase_energy:' + str(index))
                         for index in range(2, 6))
                 and state['counts'] == [142, 142, 49]
                 and len(state['rows']) == 191
                 and 'PROVIDER' not in state['stopped_channels'],
                 'B13_V4_ENPHASE_INSTALL_LEDGER_DRIFT')
            _exclusive_write_json(path=path, value=approved)
        ledger.snapshot()
    return approved
