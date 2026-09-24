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
    return {'attempts': {}, 'total': 0, 'resumed': False,
            'recovery172_consumed': False}


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
                 next_ordinal, repair_receipt=None, recovery172=None,
                 v4_enphase=None):
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
    recovering172 = (recovery172 is not None and not progress['recovery172_consumed']
                     and group == recovery172['batch_group_id']
                     and group == authorization['first_group_id']
                     and recovery172['batch_authorization_id'] == authorization['authorization_id']
                     and request_digest == recovery172['request_digest']
                     and len(prior) == 1
                     and prior[0] == {'ordinal': recovery172['original_ordinal'],
                                     'status': 'FAILED_TERMINAL', 'stop_reason': 'HTTP_402'}
                     and repair_receipt is None)
    repairing189 = (repair_receipt is not None
                    and repair_receipt['batch_authorization_id'] == authorization['authorization_id']
                    and repair_receipt['group_id'] == group == 'B13:enphase_energy:0'
                    and repair_receipt['repaired_request_digest'] == request_digest
                    and len(prior) == 1
                    and prior[0] == {'ordinal': repair_receipt['failed_ordinal'],
                                    'status':'FAILED_TERMINAL', 'stop_reason':''})
    v4_row = next((item for item in v4_enphase['successor_groups']
                   if item['group_id'] == group), None) if v4_enphase else None
    v4_target = (v4_row is not None and
                 request_digest == v4_row['v4_digest'] and
                 v4_enphase['batch_authorization_id'] == authorization['authorization_id'])
    repairing191 = (v4_target and group == v4_enphase['failed_group_id']
                    and len(prior) == 1
                    and prior[0] == {'ordinal': v4_enphase['failed_ordinal'],
                                    'status': 'FAILED_TERMINAL', 'stop_reason': ''})
    if first:
        need(stops == {('PROVIDER', authorization['original_stop_ordinal'])},
             'BATCH33_ORIGINAL_STOP_NOT_ISOLATED')
    else:
        need(progress['resumed'] and (not stops or
             (recovering172 and stops == {('PROVIDER', recovery172['original_ordinal'])})),
             'BATCH33_NEW_STOP_REMAINS')
    if not prior:
        old191 = (v4_row is not None and group == v4_enphase['failed_group_id']
                  and next_ordinal == v4_enphase['failed_ordinal']
                  and request_digest == row['initial_request_digest'])
        v4_base = (v4_target and v4_row['group_index'] in
                   v4_enphase['base_groups_without_prior_attempt'])
        need(repair_receipt is None and (v4_base or old191 or
             (v4_row is None and request_digest == row['initial_request_digest']))
             and _base_order_allowed(groups=groups, attempts=progress['attempts'], target=group),
             'BATCH33_BASE_GROUP_OR_ORDER_CHANGED')
        attempt = 0
    else:
        if recovering172:
            attempt = 1
        elif repairing189:
            attempt = 1
        elif repairing191:
            attempt = 1
        else:
            need(len(prior) == 1 and prior[0]['status'] == 'FAILED_TERMINAL'
                 and not prior[0]['stop_reason'] and repair_receipt is not None,
                 'BATCH33_REPAIR_NOT_ELIGIBLE')
            # No other group can convert a disappointing answer into a redraw.
            need(False, 'BATCH33_REPAIR_PROOF_NOT_YET_IMPLEMENTED')
    historical = row['historical_ordinal']
    duplicate = ('PROVIDER', request_digest) in requests
    need(not duplicate or (attempt == 0 and historical in authorization['same_digest_original_ordinals'])
         or (recovering172 and request_digest == recovery172['request_digest']),
         'BATCH33_UNAPPROVED_DUPLICATE_REQUEST')
    fields = {'batch_authorization_id': authorization['authorization_id'],
              'batch_group_id': group, 'batch_attempt_index': attempt,
              'batch_resume_171': first}
    if recovering172:
        fields['batch_recovery_172_id'] = recovery172['authorization_id']
        fields['batch_resume_172'] = True
    if repairing189:
        fields['batch_repair_189_id'] = repair_receipt['authorization_id']
    if v4_target:
        fields['batch_b13_v4_id'] = v4_enphase['authorization_id']
    if repairing191:
        fields['batch_repair_191_id'] = v4_enphase['authorization_id']
    return fields, duplicate


def observe_claim(*, authorization, progress, intent, stops, requests,
                  recovery172=None, repair189=None, v4_enphase=None):
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
        next_ordinal=intent['ordinal'], recovery172=recovery172,
        repair_receipt=repair189 if 'batch_repair_189_id' in intent else None,
        v4_enphase=v4_enphase)
    need(all(intent.get(key) == value for key, value in expected.items()),
         'BATCH33_CLAIM_MARKER_CHANGED')
    need(('batch_recovery_172_id' in intent) == ('batch_recovery_172_id' in expected)
         and ('batch_resume_172' in intent) == ('batch_resume_172' in expected),
         'BATCH33_RECOVERY172_MARKER_CHANGED')
    need(('batch_repair_189_id' in intent) == ('batch_repair_189_id' in expected),
         'BATCH33_REPAIR189_MARKER_CHANGED')
    need(('batch_b13_v4_id' in intent) == ('batch_b13_v4_id' in expected)
         and ('batch_repair_191_id' in intent) == ('batch_repair_191_id' in expected),
         'BATCH33_B13_V4_MARKER_CHANGED')
    progress['attempts'].setdefault(intent['batch_group_id'], []).append({
        'ordinal': intent['ordinal'], 'status': 'PENDING', 'stop_reason': ''})
    progress['total'] += 1
    if expected['batch_resume_171']:
        stops.remove(('PROVIDER', authorization['original_stop_ordinal']))
        progress['resumed'] = True
    if expected.get('batch_resume_172'):
        stops.remove(('PROVIDER', recovery172['original_ordinal']))
        progress['recovery172_consumed'] = True
    return duplicate


def observe_terminal(*, progress, intent, status, stop_reason):
    if 'batch_authorization_id' in intent:
        row = progress['attempts'][intent['batch_group_id']][-1]
        need(row['ordinal'] == intent['ordinal'] and row['status'] == 'PENDING',
             'BATCH33_TERMINAL_PREDECESSOR_CHANGED')
        row.update(status=status, stop_reason=stop_reason)


def group_for_request(*, authorization, request, request_digest, repair189=None,
                      v4_enphase=None):
    matches = [row for row in groups_for(authorization)
               if row['initial_request_digest'] == request_digest]
    if v4_enphase is not None:
        from .capacity_reference_contract import RELEVANCE_VERSION
        successor = [row for row in v4_enphase['successor_groups']
                     if row['v4_digest'] == request_digest]
        if successor:
            need(len(successor) == 1
                 and request.get('source_reference_contract', {}).get('version') == RELEVANCE_VERSION
                 and request['source_id'] == successor[0]['source_id']
                 and request['metric_id'] == 'B13'
                 and request['company_id'] == 'enphase_energy',
                 'BATCH33_B13_V4_REQUEST_CHANGED')
            return successor[0]['group_id']
        need(not any(row['group_id'] == group_id(match)
                     for row in v4_enphase['successor_groups'] for match in matches),
             'BATCH33_B13_V3_SUPERSEDED_BEFORE_NEW_CLAIM')
    if not matches and repair189 is not None and \
            repair189['repaired_request_digest'] == request_digest:
        from .capacity_reference_contract import RELEVANCE_VERSION
        need(request.get('source_reference_contract', {}).get('version') == RELEVANCE_VERSION
             and repair189['group_id'] == 'B13:enphase_energy:0'
             and request['source_id'] == repair189['source_id']
             and request['metric_id'] == 'B13'
             and request['company_id'] == 'enphase_energy',
             'BATCH33_REPAIR189_REQUEST_CHANGED')
        return repair189['group_id']
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
    if (ledger.root/'recovery-172.json').exists():
        from .continuous_recovery_172 import read_authorization as read_recovery172
        recovery172 = read_recovery172(ledger)
        body['recovery_172'] = recovery172
        body['recovery_172_original_wire'] = strict_json_file(
            path=ledger.root/'calls'/('%04d' % recovery172['original_ordinal'])/'wire/journal.json')
    if (ledger.root/'batch33-repair-189.json').exists():
        from .continuous_batch33_repair189 import read_authorization as read_repair189
        repair189 = read_repair189(ledger)
        body['repair_189'] = repair189
        body['repair_189_original_wire'] = strict_json_file(
            path=ledger.root/'calls'/('%04d' % repair189['failed_ordinal'])/'wire/journal.json')
    if (ledger.root/'batch33-b13-v4-enphase.json').exists():
        from .continuous_b13_v4_enphase import read_authorization as read_v4
        v4 = read_v4(ledger)
        body['b13_v4_enphase'] = v4
        body['b13_v4_enphase_original_wire'] = strict_json_file(
            path=ledger.root/'calls'/('%04d' % v4['failed_ordinal'])/'wire/journal.json')
    return {**body, 'history_id': content_hash(value=body)}


def validate_history(*, history, mode, native_rows, request_digests,
                     recovered_failed_ordinals, recovered_402_ordinals=(),
                     recovered_engineering_ordinals=()):
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
    recovery172 = history.get('recovery_172')
    need((recovery172 is None) == ('recovery_172_original_wire' not in history),
         'BATCH33_HISTORY_RECOVERY172_FIELDS_CHANGED')
    if recovery172 is not None:
        need(recovery172['authorization_id'] == content_hash(value={k: v for k, v in recovery172.items()
             if k != 'authorization_id'})
             and recovery172['execution_mode'] == mode
             and recovery172['original_ordinal'] == auth['original_stop_ordinal'] + 1
             and recovery172['batch_authorization_id'] == auth['authorization_id']
             and recovery172['batch_group_id'] == auth['first_group_id']
             and recovery172['maximum_new_executions'] == 1
             and recovery172['request_digest'] == groups_for(auth)[0]['initial_request_digest']
             and history['recovery_172_original_wire']['error_class'] == 'HTTP_402',
             'BATCH33_HISTORY_RECOVERY172_AUTH_CHANGED')
        if mode == 'LIVE':
            from types import SimpleNamespace
            from .continuous_recovery_172 import authorization as recovery_authorization
            view = SimpleNamespace(root=Path(recovery172['budget_root']), live=True,
                                   binding={'binding_id': recovery172['binding_id'],
                                            'limits': [240, 240, 80]})
            need(recovery172 == recovery_authorization(ledger=view, check_ledger=False),
                 'BATCH33_HISTORY_RECOVERY172_APPROVAL_CHANGED')
    repair189 = history.get('repair_189')
    need((repair189 is None) == ('repair_189_original_wire' not in history),
         'BATCH33_HISTORY_REPAIR189_FIELDS_CHANGED')
    if repair189 is not None:
        repair_groups = [row for row in groups_for(auth)
                         if group_id(row) == repair189['group_id']]
        need(repair189['authorization_id'] == content_hash(value={k:v for k,v in repair189.items()
             if k != 'authorization_id'})
             and repair189['execution_mode'] == mode
             and repair189['batch_authorization_id'] == auth['authorization_id']
             and repair189['group_id'] == 'B13:enphase_energy:0'
             and (mode != 'LIVE' or repair189['failed_ordinal'] == 189)
             and repair189['maximum_new_executions'] == 1
             and len(repair_groups) == 1
             and repair189['failed_request_digest'] == repair_groups[0]['initial_request_digest']
             and history['repair_189_original_wire']['error_class'] == 'DEEPSEEK_RESPONSE_INVALID',
             'BATCH33_HISTORY_REPAIR189_AUTH_CHANGED')
        if mode == 'LIVE':
            from types import SimpleNamespace
            from .continuous_batch33_repair189 import authorization as repair_authorization
            view = SimpleNamespace(root=Path(repair189['budget_root']), live=True,
                                   binding={'binding_id':repair189['binding_id'],
                                            'limits':[240,240,80]})
            need(repair189 == repair_authorization(ledger=view, check_ledger=False),
                 'BATCH33_HISTORY_REPAIR189_PROOF_CHANGED')
    v4_enphase = history.get('b13_v4_enphase')
    need((v4_enphase is None) == ('b13_v4_enphase_original_wire' not in history),
         'BATCH33_HISTORY_B13_V4_FIELDS_CHANGED')
    if v4_enphase is not None:
        need(v4_enphase['authorization_id'] == content_hash(value={k: v for k, v in
             v4_enphase.items() if k != 'authorization_id'})
             and v4_enphase['execution_mode'] == mode
             and v4_enphase['batch_authorization_id'] == auth['authorization_id']
             and (mode != 'LIVE' or v4_enphase['failed_ordinal'] == 191)
             and [row['group_index'] for row in v4_enphase['successor_groups']] == [1, 2, 3, 4, 5]
             and v4_enphase['maximum_new_executions'] == 5
             and history['b13_v4_enphase_original_wire']['error_class'] ==
                 'DEEPSEEK_RESPONSE_INVALID',
             'BATCH33_HISTORY_B13_V4_AUTH_CHANGED')
        if mode == 'LIVE':
            from types import SimpleNamespace
            from .continuous_b13_v4_enphase import authorization as v4_authorization
            view = SimpleNamespace(root=Path(v4_enphase['budget_root']), live=True,
                                   binding={'binding_id':v4_enphase['binding_id'],
                                            'limits':[240, 240, 80]})
            need(v4_enphase == v4_authorization(ledger=view, check_ledger=False),
                 'BATCH33_HISTORY_B13_V4_PROOF_CHANGED')
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
        if recovery172 is not None and intent['ordinal'] == recovery172['original_ordinal']:
            old_wire = history['recovery_172_original_wire']
            need(intent['intent_id'] == recovery172['original_intent_id']
                 and intent['request_digest'] == recovery172['request_digest']
                 and intent['batch_group_id'] == recovery172['batch_group_id']
                 and intent['batch_authorization_id'] == recovery172['batch_authorization_id']
                 and intent['batch_attempt_index'] == 0
                 and terminal is not None
                 and terminal['terminal_id'] == recovery172['original_terminal_id']
                 and terminal['status'] == 'FAILED_TERMINAL'
                 and terminal['stop_reason'] == old_wire['error_class'] == 'HTTP_402'
                 and terminal['counts'] == [1, 1, 0]
                 and terminal['evidence']['wire/journal.json'] == sha256_bytes(
                     content=canonical_json_bytes(value=old_wire))
                 and terminal['evidence']['semantic-request.json'] == recovery172['request_sha256']
                 and terminal['evidence']['source.json'] == recovery172['source_sha256']
                 and 'wire/assistant-output.bin' not in terminal['evidence'],
                 'BATCH33_HISTORY_RECOVERY172_ORIGINAL_CHANGED')
        if repair189 is not None and intent['ordinal'] == repair189['failed_ordinal']:
            old_wire = history['repair_189_original_wire']
            need(intent['intent_id'] == repair189['failed_intent_id']
                 and intent['request_digest'] == repair189['failed_request_digest']
                 and intent['batch_group_id'] == repair189['group_id']
                 and intent['batch_authorization_id'] == repair189['batch_authorization_id']
                 and intent['batch_attempt_index'] == 0
                 and terminal is not None
                 and terminal['terminal_id'] == repair189['failed_terminal_id']
                 and terminal['status'] == 'FAILED_TERMINAL'
                 and not terminal['stop_reason']
                 and terminal['counts'] == [1,1,0]
                 and terminal['evidence']['wire/journal.json'] == sha256_bytes(
                     content=canonical_json_bytes(value=old_wire))
                 and terminal['evidence']['wire/raw-response.bin'] ==
                     repair189['failed_raw_response_sha256']
                 and old_wire['usage']['output_tokens'] == 4096,
                 'BATCH33_HISTORY_REPAIR189_ORIGINAL_CHANGED')
        if v4_enphase is not None and intent['ordinal'] == v4_enphase['failed_ordinal']:
            original_wire = history['b13_v4_enphase_original_wire']
            need(intent['intent_id'] == v4_enphase['failed_intent_id']
                 and intent['request_digest'] == v4_enphase['failed_v3_digest']
                 and intent['batch_group_id'] == v4_enphase['failed_group_id']
                 and intent['batch_attempt_index'] == 0
                 and terminal is not None
                 and terminal['terminal_id'] == v4_enphase['failed_terminal_id']
                 and terminal['status'] == 'FAILED_TERMINAL'
                 and not terminal['stop_reason']
                 and terminal['counts'] == [1, 1, 0]
                 and terminal['evidence']['wire/journal.json'] == sha256_bytes(
                     content=canonical_json_bytes(value=original_wire))
                 and terminal['evidence']['wire/raw-response.bin'] ==
                     v4_enphase['failed_raw_response_sha256']
                 and original_wire['usage']['output_tokens'] == 4096,
                 'BATCH33_HISTORY_B13_V4_ORIGINAL_CHANGED')
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
            intent=intent, stops=stops, requests=requests,
            recovery172=recovery172, repair189=repair189,
            v4_enphase=v4_enphase)
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
    expected_recovered_402 = ({recovery172['original_ordinal']}
        if recovery172 is not None and any(
            native['intent'].get('batch_recovery_172_id') == recovery172['authorization_id']
            for native in native_rows) else set())
    need(set(recovered_402_ordinals) == expected_recovered_402,
         'BATCH33_HISTORY_HTTP402_LINK_CHANGED')
    expected_recovered_engineering = ({repair189['failed_ordinal']}
        if repair189 is not None and any(
            native['intent'].get('batch_repair_189_id') == repair189['authorization_id']
            for native in native_rows) else set())
    if v4_enphase is not None and any(
            native['intent'].get('batch_repair_191_id') == v4_enphase['authorization_id']
            for native in native_rows):
        expected_recovered_engineering.add(v4_enphase['failed_ordinal'])
    need(set(recovered_engineering_ordinals) == expected_recovered_engineering,
         'BATCH33_HISTORY_ENGINEERING_LINK_CHANGED')
    return True
