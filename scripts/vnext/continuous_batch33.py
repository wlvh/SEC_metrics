"""The one user-authorized Issue28 D04/B13 batch in the original call ledger.

The GitHub comment is an executor transcription of the user's conversation
approval. A local file, a new request digest, or this module alone grants no
calls. Only the exact 33-group manifest and its one bounded repair slot per
newly failed group can be represented by this record.
"""
from pathlib import Path

from .annual_repair_budget import validate_comment
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_file
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = 'config/issue28_batch33_v1.json'
_BOUND_PATHS = (
    POLICY_PATH, 'scripts/vnext/continuous_batch33.py', 'tools/vnext_batch33.py',
    'docs/evidence/issue28_continuous/batch33-authorization/server-comment.json',
    'docs/evidence/issue28_continuous/batch33-authorization/authorization-original-user-text.md',
    'docs/evidence/issue28_continuous/batch33-authorization/initial-group-set.json',
)


def _config():
    return strict_json_file(path=ROOT / POLICY_PATH)


def _manifest(config):
    path = resolve_repository_file(repo_root=ROOT, repo_relative_path=config['group_manifest_path'])
    need(sha256_file(path=path) == config['group_manifest_sha256'], 'BATCH33_MANIFEST_CHANGED')
    value = strict_json_file(path=path)
    groups = value['groups']
    need(value['record_type'] == 'ISSUE28_BATCH33_INITIAL_GROUP_MANIFEST'
         and value['group_count'] == config['group_count'] == len(groups) == 33
         and value['real_execution_authorized_by_this_file'] is False,
         'BATCH33_MANIFEST_SCOPE_CHANGED')
    counts = [(metric, company, count) for metric, company, count in (
        ('D04', 'enphase_energy', 6), ('D04', 'paramount_skydance_paramount_global', 10),
        ('B13', 'enphase_energy', 6), ('B13', 'ford_motor_company', 11))]
    expected = [(metric, company, index) for metric, company, count in counts for index in range(count)]
    observed = [(row['metric_id'], row['company_id'], row['group_index']) for row in groups]
    need(observed == expected and len({row['initial_request_digest'] for row in groups}) == 33
         and all(type(row['source_id']) is str and row['source_id'].startswith('sha256:')
                 and type(row['initial_request_digest']) is str and len(row['initial_request_digest']) == 64
                 for row in groups)
         and {index: row['historical_ordinal'] for index, row in enumerate(groups)
              if row['historical_ordinal'] is not None} == {0: 114, 6: 113, 16: 111, 17: 170, 22: 171},
         'BATCH33_GROUP_IDENTITY_CHANGED')
    return groups


def group_id(row):
    return row['metric_id'] + ':' + row['company_id'] + ':' + str(row['group_index'])


def groups_for(authorization):
    if authorization['execution_mode'] == 'RECORDED_TEST_ONLY':
        return authorization['test_groups']
    config = _config()
    need(authorization['group_manifest_sha256'] == config['group_manifest_sha256'],
         'BATCH33_AUTHORIZATION_MANIFEST_CHANGED')
    return _manifest(config)


def _originals(ledger, approved):
    for number in (110, 111, 113, 114, 170, 171):
        reference = approved['originals'][str(number)]
        path = ledger.root / 'calls' / ('%04d' % number)
        intent = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                                     repo_relative_path='calls/%04d/intent.json' % number))
        terminal = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                                       repo_relative_path='calls/%04d/terminal.json' % number))
        need(reference == {'ordinal': number, 'intent_id': intent['intent_id'],
             'terminal_id': terminal['terminal_id'], 'request_digest': intent['request_digest'],
             'terminal_status': terminal['status'], 'stop_reason': terminal['stop_reason']}
             and intent['binding_id'] == ledger.binding['binding_id']
             and terminal['counts'] == [1, 1, 0], 'BATCH33_ORIGINAL_HISTORY_CHANGED')
        if number == 171:
            wire = strict_json_file(path=path/'wire/journal.json')
            need(terminal['status'] == 'FAILED_TERMINAL' and terminal['stop_reason'] == 'HTTP_402'
                 and wire['error_class'] == 'HTTP_402' and not (path/'wire/assistant-output.bin').exists(),
                 'BATCH33_171_NOT_HTTP402_WITHOUT_OUTPUT')
    need(approved['originals']['111']['terminal_status'] == 'SUCCEEDED'
         and all(approved['originals'][str(n)]['terminal_status'] == 'FAILED_TERMINAL'
                 for n in (110, 113, 114, 170, 171)), 'BATCH33_HISTORICAL_STATUS_CHANGED')


def authorization(*, ledger, online=False):
    """Read a pinned server comment; never infer permission from local code."""
    config = _config()
    need(ledger.live and str(ledger.root) == config['budget_root']
         and ledger.binding['binding_id'] == config['binding_id']
         and ledger.binding['limits'] == config['maximum_cumulative_provider_paid_sec_calls']
         == [240, 240, 80], 'BATCH33_ORIGINAL_LEDGER_REQUIRED')
    if online:
        from .annual_candidate import _github
        comment = _github('repos/' + config['repository'] + '/issues/comments/'
                          + config['delegation_url'].rsplit('-', 1)[1])
    else:
        comment = strict_json_file(path=resolve_repository_file(repo_root=ROOT,
                                   repo_relative_path=config['delegation_record_path']))
    approved = validate_comment(comment, repository=config['repository'], url=config['delegation_url'])
    need(sha256_bytes(content=comment['body'].encode()) == config['delegation_body_sha256']
         and approved['record_type'] == 'ISSUE28_BATCH33_D04_B13_DELEGATION'
         and approved['approval_kind'] == 'USER_DELEGATED_BOUNDED_EXECUTION'
         and approved['registered_by'] == 'CODEX_ON_EXPLICIT_USER_INSTRUCTION'
         and approved['repository'] == config['repository']
         and approved['issue_number'] == config['issue_number'] == 28
         and approved['branch'] == 'task/b06-new-source' and approved['main_pr_number'] == 43
         and approved['transcription_id'] == content_hash(value={
             key: value for key, value in approved.items() if key != 'transcription_id'}),
         'BATCH33_SERVER_APPROVAL_CHANGED')
    source_path = resolve_repository_file(repo_root=ROOT, repo_relative_path=config['source_text_path'])
    source_text = source_path.read_text()
    need(approved['original_user_instruction'] == source_text
         and sha256_bytes(content=source_text.encode()) == config['source_text_sha256']
         and approved['delegation_source'] == {
             'kind': 'EXPLICIT_USER_CONVERSATION_APPROVAL',
             'user_instruction_date': '2026-09-23',
             'transcription_commit': config['transcription_commit'],
             'original_text_sha256': config['source_text_sha256']},
         'BATCH33_TRANSCRIBED_USER_TEXT_CHANGED')
    scope = approved['scope']
    need(scope['budget_root'] == config['budget_root']
         and scope['binding_id'] == config['binding_id']
         and scope['maximum_cumulative_provider_paid_sec_calls'] == [240, 240, 80]
         and scope['counts_before'] == config['counts_before'] == [122, 122, 49]
         and scope['maximum_new_provider_paid_sec_calls'] == config['maximum_new_provider_paid_sec_calls']
         == [66, 66, 0]
         and scope['initial_business_group_count'] == config['group_count'] == 33
         and scope['initial_group_set_path'] == config['group_manifest_path']
         and scope['initial_group_set_sha256'] == config['group_manifest_sha256']
         and scope['first_execution_per_group'] == scope['repair_execution_per_group_maximum'] == 1
         and scope['repair_requires_new_failed_group_root_cause_substantive_patch_tests_scoped_review'] is True
         and scope['consume_on'] == 'NEW_CLAIM_APPEND_NOT_SUCCESS'
         and scope['automatic_retry_count'] == config['automatic_retry_count'] == 0
         and scope['d04_first_order'] == ['enphase_energy:6', 'paramount_skydance_paramount_global:10']
         and scope['b13_following_order'] == ['enphase_energy:6', 'ford_motor_company:11']
         and scope['resume_171_without_replaying_old_ford_request'] is True
         and scope['original_110_recovery_may_be_reused'] is False
         and scope['old_113_114_same_digest_one_each'] is True
         and scope['old_111_170_171_v3_successor_one_each'] is True
         and scope['old_68_109_or_other_failed_requests_may_repeat'] is False
         and scope['new_stop_conditions_remain_effective'] is True
         and all(scope[key] is False for key in ('D03_calls_authorized',
             'account_operations_authorized', 'production_authorized',
             'ready_merge_active_or_deploy_authorized')),
         'BATCH33_SCOPE_CHANGED')
    _manifest(config)
    _originals(ledger, approved)
    value = {'record_type': 'CONTINUOUS_BATCH33_AUTHORIZATION',
             'execution_mode': 'LIVE', 'budget_root': config['budget_root'],
             'binding_id': config['binding_id'], 'delegation_url': config['delegation_url'],
             'delegation_body_sha256': config['delegation_body_sha256'],
             'transcription_id': config['transcription_id'],
             'group_manifest_sha256': config['group_manifest_sha256'],
             'original_stop_ordinal': 171, 'original_stop_intent_id': config['old_171_intent_id'],
             'original_stop_terminal_id': config['old_171_terminal_id'],
             'same_digest_original_ordinals': [113, 114],
             'maximum_new_provider_calls': 66, 'first_group_id': 'D04:enphase_energy:0'}
    need(value['transcription_id'] == approved['transcription_id']
         and value['original_stop_intent_id'] == approved['originals']['171']['intent_id']
         and value['original_stop_terminal_id'] == approved['originals']['171']['terminal_id'],
         'BATCH33_ORIGINAL_STOP_CHANGED')
    return {**value, 'authorization_id': content_hash(value=value)}


def read_authorization(ledger):
    path = ledger.root / _config()['record_path']
    if not path.exists():
        return None
    value = strict_json_file(path=resolve_repository_file(repo_root=ledger.root,
                                  repo_relative_path=_config()['record_path']))
    need(value.get('authorization_id') == content_hash(value={k: v for k, v in value.items()
         if k != 'authorization_id'})
         and value.get('record_type') == 'CONTINUOUS_BATCH33_AUTHORIZATION'
         and value.get('budget_root') == str(ledger.root)
         and value.get('binding_id') == ledger.binding['binding_id']
         and value.get('execution_mode') == ('LIVE' if ledger.live else 'RECORDED_TEST_ONLY'),
         'BATCH33_SAVED_AUTHORIZATION_CHANGED')
    if ledger.live:
        need(value == authorization(ledger=ledger), 'BATCH33_SAVED_APPROVAL_DIFFERS')
    else:
        need(type(value.get('test_groups')) is list and value['maximum_new_provider_calls']
             == 2 * len(value['test_groups']), 'BATCH33_RECORDED_SCOPE_CHANGED')
    return value


def install_live_authorization(*, ledger, requirement):
    from .invocation_control import _exclusive_write_json
    config = _config()
    for relative in _BOUND_PATHS:
        path = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
        need(requirement['execution_authority']['files'].get(relative) ==
             {'sha256': sha256_file(path=path), 'size': path.stat().st_size},
             'BATCH33_RULE_OR_APPROVAL_NOT_BOUND:' + relative)
    approved = authorization(ledger=ledger, online=True)
    with ledger.locked():
        state = ledger.snapshot()
        path = ledger.root / config['record_path']
        if path.exists():
            need(read_authorization(ledger) == approved, 'BATCH33_AUTHORIZATION_ALREADY_DIFFERENT')
            # The batch grants no SEC calls of its own. Separate Issue28 SEC
            # acquisition remains governed by the original allowance.
            need(state['counts'][2] >= 49, 'BATCH33_PRIOR_SEC_COUNT_CHANGED')
        else:
            need(state['counts'] == [122, 122, 49] and len(state['rows']) == 171
                 and state['stopped_channels'] == ['PROVIDER'], 'BATCH33_INSTALL_LEDGER_DRIFT')
            _exclusive_write_json(path=path, value=approved)
            state = ledger.snapshot()
            need(state['counts'] == [122, 122, 49]
                 and state['stopped_channels'] == ['PROVIDER'], 'BATCH33_INSTALL_CHANGED_HISTORY')
    return approved


def recorded_authorization(*, ledger, groups, original_stop_ordinal):
    """A test-only grant; it can never authenticate as a live comment."""
    from .invocation_control import _exclusive_write_json
    need(not ledger.live and ledger._locked and type(groups) is list and groups,
         'BATCH33_RECORDED_ONLY')
    path = ledger.root / ('calls/%04d' % original_stop_ordinal)
    intent = strict_json_file(path=path/'intent.json')
    terminal = strict_json_file(path=path/'terminal.json')
    need(terminal['stop_reason'] == 'HTTP_402' and terminal['status'] == 'FAILED_TERMINAL'
         and not (path/'wire/assistant-output.bin').exists(), 'BATCH33_RECORDED_ORIGINAL_REQUIRED')
    body = {'record_type': 'CONTINUOUS_BATCH33_AUTHORIZATION',
            'execution_mode': 'RECORDED_TEST_ONLY', 'budget_root': str(ledger.root),
            'binding_id': ledger.binding['binding_id'],
            'original_stop_ordinal': original_stop_ordinal,
            'original_stop_intent_id': intent['intent_id'],
            'original_stop_terminal_id': terminal['terminal_id'],
            'same_digest_original_ordinals': sorted({row['historical_ordinal'] for row in groups
                if row['historical_ordinal'] is not None and row['historical_ordinal'] != original_stop_ordinal}),
            'maximum_new_provider_calls': 2 * len(groups),
            'first_group_id': group_id(groups[0]), 'test_groups': groups}
    value = {**body, 'authorization_id': content_hash(value=body)}
    _exclusive_write_json(path=ledger.root/_config()['record_path'], value=value)
    return value


def empty_progress():
    return {'attempts': {}, 'total': 0, 'resumed': False}


def _stage(row):
    return row['metric_id'], row['company_id']


def _base_order_allowed(*, groups, attempts, target):
    """Complete or explicitly blocked earlier companies before advancing."""
    index = next(i for i, row in enumerate(groups) if group_id(row) == target)
    for group in groups[:index]:
        gid = group_id(group)
        history = attempts.get(gid, [])
        if _stage(group) == _stage(groups[index]):
            # Never skip a source group within the company. A failure may be
            # repaired once, but it cannot be labelled a completed group.
            if not history or history[-1]['status'] != 'SUCCEEDED':
                return False
        elif history and history[-1]['status'] == 'SUCCEEDED':
            continue
        else:
            stage = _stage(group)
            failed = any(attempts.get(group_id(prior), []) and
                         attempts[group_id(prior)][-1]['status'] == 'FAILED_TERMINAL'
                         for prior in groups[:index] if _stage(prior) == stage)
            if not failed:
                return False
    return True


def claim_fields(*, authorization, progress, group, request_digest, stops, requests,
                 next_ordinal, repair_receipt=None):
    """Return the exact marker for one allowed claim; never write the ledger."""
    groups = groups_for(authorization)
    by_id = {group_id(row): row for row in groups}
    need(group in by_id, 'BATCH33_GROUP_OUTSIDE_APPROVAL')
    row = by_id[group]
    prior = progress['attempts'].get(group, [])
    need(progress['total'] < authorization['maximum_new_provider_calls'],
         'BATCH33_SUBCAP_EXHAUSTED')
    first = progress['total'] == 0
    need(first == (group == authorization['first_group_id'] and next_ordinal ==
                  authorization['original_stop_ordinal'] + 1),
         'BATCH33_FIRST_CLAIM_CHANGED')
    if first:
        need(stops == {('PROVIDER', authorization['original_stop_ordinal'])},
             'BATCH33_ORIGINAL_STOP_NOT_ISOLATED')
    else:
        need(not stops and progress['resumed'], 'BATCH33_NEW_STOP_REMAINS')
    if not prior:
        need(repair_receipt is None and request_digest == row['initial_request_digest']
             and _base_order_allowed(groups=groups, attempts=progress['attempts'], target=group),
             'BATCH33_BASE_GROUP_OR_ORDER_CHANGED')
        attempt = 0
    else:
        need(len(prior) == 1 and prior[0]['status'] == 'FAILED_TERMINAL'
             and not prior[0]['stop_reason'] and repair_receipt is not None,
             'BATCH33_REPAIR_NOT_ELIGIBLE')
        # A specific failed group may acquire a repair record only after its
        # actual diagnosis, code patch, regressions and scoped review exist.
        # The initial authorization alone never grants a second draw.
        need(False, 'BATCH33_REPAIR_PROOF_NOT_YET_IMPLEMENTED')
    historical = row['historical_ordinal']
    duplicate = ('PROVIDER', request_digest) in requests
    need(not duplicate or (attempt == 0 and historical in authorization['same_digest_original_ordinals']),
         'BATCH33_UNAPPROVED_DUPLICATE_REQUEST')
    return {'batch_authorization_id': authorization['authorization_id'],
            'batch_group_id': group, 'batch_attempt_index': attempt,
            'batch_resume_171': first}, duplicate


def observe_claim(*, authorization, progress, intent, stops, requests):
    """Independently revalidate each marked claim during every cold ledger read."""
    if 'batch_authorization_id' not in intent:
        need(not (intent['channel'] == 'SEC' and
                  intent['ordinal'] > authorization['original_stop_ordinal']
                  and not progress['resumed']), 'BATCH33_FIRST_D04_CLAIM_REQUIRED')
        need(not (intent['channel'] == 'PROVIDER' and
                  intent['ordinal'] > authorization['original_stop_ordinal']),
             'BATCH33_UNMARKED_PROVIDER_CLAIM')
        return False
    need(intent['channel'] == 'PROVIDER'
         and intent['batch_authorization_id'] == authorization['authorization_id']
         and type(intent.get('batch_group_id')) is str
         and type(intent.get('batch_attempt_index')) is int
         and type(intent.get('batch_resume_171')) is bool,
         'BATCH33_CLAIM_MARKER_CHANGED')
    expected, duplicate = claim_fields(authorization=authorization,
        progress=progress, group=intent['batch_group_id'],
        request_digest=intent['request_digest'],
        stops={stop for stop in stops if stop[0] == 'PROVIDER'}, requests=requests,
        next_ordinal=intent['ordinal'])
    need(all(intent.get(key) == value for key, value in expected.items()),
         'BATCH33_CLAIM_MARKER_CHANGED')
    progress['attempts'].setdefault(intent['batch_group_id'], []).append({
        'ordinal': intent['ordinal'], 'status': 'PENDING', 'stop_reason': ''})
    progress['total'] += 1
    if expected['batch_resume_171']:
        stops.remove(('PROVIDER', authorization['original_stop_ordinal']))
        progress['resumed'] = True
    return duplicate


def observe_terminal(*, progress, intent, status, stop_reason):
    if 'batch_authorization_id' in intent:
        row = progress['attempts'][intent['batch_group_id']][-1]
        need(row['ordinal'] == intent['ordinal'] and row['status'] == 'PENDING',
             'BATCH33_TERMINAL_PREDECESSOR_CHANGED')
        row.update(status=status, stop_reason=stop_reason)


def group_for_request(*, authorization, request, request_digest):
    matches = [row for row in groups_for(authorization)
               if row['initial_request_digest'] == request_digest]
    need(len(matches) == 1 and matches[0]['metric_id'] == request['metric_id']
         and matches[0]['company_id'] == request['company_id']
         and matches[0]['source_id'] == request['source_id'],
         'BATCH33_REQUEST_OUTSIDE_APPROVED_GROUP')
    return group_id(matches[0])


def historical_successor_allowed(*, authorization, ledger, ordinal, saved_request,
                                 replacement_request, replacement_digest):
    """Only the original111 group may bypass historical success reuse."""
    if ordinal != 111:
        return False
    saved = strict_json_file(path=ledger.root/'calls/0111/semantic-request.json')
    need(saved == saved_request and saved['source_id'] == replacement_request['source_id']
         and saved['metric_id'] == replacement_request['metric_id'] == 'B13'
         and saved['company_id'] == replacement_request['company_id'] == 'enphase_energy'
         and group_for_request(authorization=authorization, request=replacement_request,
                               request_digest=replacement_digest) == 'B13:enphase_energy:0',
         'BATCH33_111_SOURCE_GROUP_CHANGED')
    return True


def history_for_current(*, ledger):
    """Copy a verified claim prefix for installed native-input cold readers."""
    need(ledger._locked, 'BATCH33_HISTORY_LEDGER_LOCK_REQUIRED')
    authorization_record = read_authorization(ledger)
    need(authorization_record is not None, 'BATCH33_HISTORY_AUTHORIZATION_MISSING')
    state = ledger.snapshot()
    old = authorization_record['original_stop_ordinal']
    def record(number):
        path = ledger.root / ('calls/%04d' % number)
        return {'intent': strict_json_file(path=path/'intent.json'),
                'terminal': strict_json_file(path=path/'terminal.json'),
                'wire': strict_json_file(path=path/'wire/journal.json')}
    prefix = []
    for row in state['rows'][old:]:
        path = ledger.root / ('calls/%04d' % row['ordinal'])
        prefix.append({'intent': strict_json_file(path=path/'intent.json'),
                       'terminal': strict_json_file(path=path/'terminal.json')
                       if (path/'terminal.json').exists() else None})
    related = {str(number): record(number) for number in
               authorization_record['same_digest_original_ordinals']
               if (ledger.root/'calls'/('%04d' % number)/'intent.json').exists()}
    body = {'record_type': 'CONTINUOUS_BATCH33_CLAIM_PREFIX',
            'execution_mode': 'LIVE' if ledger.live else 'RECORDED_TEST_ONLY',
            'authorization': authorization_record,
            'original_stop': record(old),
            'original_same_digest_failures': related,
            'claims': prefix,
            'new_call_authority': False}
    return {**body, 'history_id': content_hash(value=body)}


def validate_history(*, history, mode, native_rows, request_digests, recovered_failed_ordinals):
    """Replay grant, once-only claims and original stop from installed bytes."""
    from .continuous_call_ledger import _STOP
    need(mode in {'LIVE', 'RECORDED_TEST_ONLY'}
         and history.get('record_type') == 'CONTINUOUS_BATCH33_CLAIM_PREFIX'
         and history.get('execution_mode') == mode
         and history.get('new_call_authority') is False
         and history.get('history_id') == content_hash(value={k: v for k, v in history.items()
             if k != 'history_id'}), 'BATCH33_HISTORY_ID_CHANGED')
    auth = history['authorization']
    need(auth['execution_mode'] == mode and auth['authorization_id'] == content_hash(value={
        k: v for k, v in auth.items() if k != 'authorization_id'}),
        'BATCH33_HISTORY_AUTHORIZATION_CHANGED')
    if mode == 'LIVE':
        config = _config()
        comment = strict_json_file(path=ROOT/config['delegation_record_path'])
        approved = validate_comment(comment, repository=config['repository'],
                                    url=config['delegation_url'])
        need(sha256_bytes(content=comment['body'].encode()) == config['delegation_body_sha256']
             and approved['transcription_id'] == auth['transcription_id']
             and auth['delegation_url'] == config['delegation_url']
             and auth['delegation_body_sha256'] == config['delegation_body_sha256']
             and auth['group_manifest_sha256'] == config['group_manifest_sha256']
             and auth['budget_root'] == config['budget_root']
             and auth['binding_id'] == config['binding_id']
             and auth['original_stop_ordinal'] == 171
             and auth['original_stop_intent_id'] == config['old_171_intent_id']
             and auth['original_stop_terminal_id'] == config['old_171_terminal_id']
             and auth['same_digest_original_ordinals'] == [113, 114]
             and auth['first_group_id'] == 'D04:enphase_energy:0'
             and auth['maximum_new_provider_calls'] == 66,
             'BATCH33_HISTORY_APPROVAL_CHANGED')
    stop = history['original_stop']
    old_intent, old_terminal, old_wire = stop['intent'], stop['terminal'], stop['wire']
    need(old_intent['ordinal'] == auth['original_stop_ordinal']
         and old_intent['intent_id'] == auth['original_stop_intent_id']
         and old_terminal['terminal_id'] == auth['original_stop_terminal_id']
         and old_terminal['intent_id'] == old_intent['intent_id']
         and old_terminal['status'] == 'FAILED_TERMINAL'
         and old_terminal['stop_reason'] == old_wire['error_class'] == 'HTTP_402'
         and old_terminal['counts'] == [1, 1, 0]
         and old_terminal['evidence']['wire/journal.json'] ==
             sha256_bytes(content=canonical_json_bytes(value=old_wire))
         and old_intent['intent_id'] == content_hash(value={k: v for k, v in old_intent.items()
             if k != 'intent_id'})
         and old_terminal['terminal_id'] == content_hash(value={k: v for k, v in old_terminal.items()
             if k != 'terminal_id'})
         and (mode != 'LIVE' or approved['originals']['171']['request_digest'] ==
              old_intent['request_digest']), 'BATCH33_HISTORY_ORIGINAL_STOP_CHANGED')
    related = history['original_same_digest_failures']
    if mode == 'LIVE':
        need(set(related) == {'113', '114'}, 'BATCH33_HISTORY_OLD_FAILURES_MISSING')
    for number, old in related.items():
        intent, terminal = old['intent'], old['terminal']
        need(int(number) == intent['ordinal']
             and terminal['intent_id'] == intent['intent_id']
             and terminal['status'] == 'FAILED_TERMINAL' and not terminal['stop_reason']
             and terminal['counts'] == [1, 1, 0]
             and terminal['evidence']['wire/journal.json'] ==
                 sha256_bytes(content=canonical_json_bytes(value=old['wire']))
             and intent['intent_id'] == content_hash(value={k: v for k, v in intent.items()
                 if k != 'intent_id'})
             and terminal['terminal_id'] == content_hash(value={k: v for k, v in terminal.items()
                 if k != 'terminal_id'})
             and (mode != 'LIVE' or (approved['originals'][str(number)]['intent_id'] == intent['intent_id']
                  and approved['originals'][str(number)]['terminal_id'] == terminal['terminal_id']
                  and approved['originals'][str(number)]['request_digest'] == intent['request_digest'])),
             'BATCH33_HISTORY_OLD_FAILURE_CHANGED')
    progress = empty_progress()
    stops = {('PROVIDER', auth['original_stop_ordinal'])}
    requests = {('PROVIDER', old_intent['request_digest'])}
    requests.update(('PROVIDER', item['intent']['request_digest']) for item in related.values())
    previous = old_intent['intent_id']
    indexed = {}
    need(type(history['claims']) is list and
         sum(claim['intent']['channel'] == 'PROVIDER' for claim in history['claims'])
         <= auth['maximum_new_provider_calls'],
         'BATCH33_HISTORY_CLAIM_COUNT_CHANGED')
    for position, claim in enumerate(history['claims'], start=1):
        intent, terminal = claim['intent'], claim['terminal']
        need(intent['ordinal'] == auth['original_stop_ordinal'] + position
             and intent['previous_intent_id'] == previous
             and intent['intent_id'] == content_hash(value={k: v for k, v in intent.items()
                 if k != 'intent_id'}), 'BATCH33_HISTORY_CHAIN_CHANGED')
        if intent['channel'] == 'SEC':
            need(progress['resumed'] and not any(key.startswith('batch_') for key in intent)
                 and ('SEC', intent['request_digest']) not in requests,
                 'BATCH33_HISTORY_SEPARATE_SEC_SCOPE_CHANGED')
            need(not any(stop[0] == 'SEC' for stop in stops),
                 'BATCH33_HISTORY_SEPARATE_SEC_CHANNEL_STOPPED')
            requests.add(('SEC', intent['request_digest']))
            if terminal is not None:
                need(terminal['intent_id'] == intent['intent_id']
                     and terminal['counts'] == [0, 0, 1]
                     and terminal['terminal_id'] == content_hash(value={k: v for k, v in terminal.items()
                         if k != 'terminal_id'}), 'BATCH33_HISTORY_SEPARATE_SEC_TERMINAL_CHANGED')
                if terminal['stop_reason'] in _STOP:
                    stops.add(('SEC', intent['ordinal']))
            else:
                stops.add(('SEC', intent['ordinal']))
            previous = intent['intent_id']
            continue
        need(intent['channel'] == 'PROVIDER', 'BATCH33_HISTORY_CHANNEL_CHANGED')
        duplicate = observe_claim(authorization=auth, progress=progress,
            intent=intent, stops=stops, requests=requests)
        need(('PROVIDER', intent['request_digest']) not in requests or duplicate,
             'BATCH33_HISTORY_DUPLICATE_CHANGED')
        requests.add(('PROVIDER', intent['request_digest']))
        if terminal is None:
            status, stop_reason = 'UNKNOWN_PENDING_RECONCILIATION', 'UNKNOWN_REMOTE_OUTCOME'
            stops.add(('PROVIDER', intent['ordinal']))
        else:
            need(terminal['intent_id'] == intent['intent_id']
                 and terminal['counts'] == [1, 1, 0]
                 and terminal['terminal_id'] == content_hash(value={k: v for k, v in terminal.items()
                     if k != 'terminal_id'}), 'BATCH33_HISTORY_TERMINAL_CHANGED')
            status, stop_reason = terminal['status'], terminal['stop_reason']
            if stop_reason in _STOP:
                stops.add(('PROVIDER', intent['ordinal']))
        observe_terminal(progress=progress, intent=intent,
                         status=status, stop_reason=stop_reason)
        indexed[intent['ordinal']] = claim
        previous = intent['intent_id']
    need(type(request_digests) is dict and len(native_rows) == len(request_digests),
         'BATCH33_HISTORY_NATIVE_SET_CHANGED')
    used = set()
    for row in native_rows:
        number = row['ordinal']
        claim = indexed.get(number)
        need(claim is not None and claim['intent'] == row['intent']
             and claim['terminal'] == row['terminal']
             and claim['terminal']['status'] == 'SUCCEEDED'
             and request_digests[number] == row['intent']['request_digest']
             and number not in used, 'BATCH33_HISTORY_NATIVE_CLAIM_CHANGED')
        used.add(number)
    expected_recovered = {int(row['historical_ordinal']) for row in groups_for(auth)
        if row['historical_ordinal'] in auth['same_digest_original_ordinals']
        and any(native['intent']['batch_group_id'] == group_id(row) for native in native_rows)}
    need(set(recovered_failed_ordinals) == expected_recovered,
         'BATCH33_HISTORY_FAILED_LINK_CHANGED')
    return True
