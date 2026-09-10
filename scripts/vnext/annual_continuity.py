"""One bounded annual update over existing native execution and publication cores.

A real stage comment fixes code, roots, expiry and one durable budget. Per-input
plans are machine-generated; neither a plan nor a local JSON grants authority.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from pathlib import Path
import fcntl
import json
import os
import re
from uuid import uuid4

from .annual_adoption import ROOT, need, read, record, check_id, git, _tree_files
from .annual_adoption_policy import V3, policy
from .canonical import canonical_json_bytes, content_hash, parse_utc_timestamp, sha256_file, strict_json_file, strict_json_loads
from . import annual_runtime as runtime, annual_update as update, annual_input
from .annual_continuity_sources import select_saved_input
from .requirement_profile_v9 import REQUIREMENT_ID, DECISION_ID
from .requirements import load_requirement_snapshot
from .requirement_profile import validate_execution_authority

DECISION = 'AUTHORIZE_ISOLATED_ANNUAL_CONTINUITY_STAGE'
_FACTORY = object()
_running_candidate = ContextVar('continuity_owned_candidate', default=None)


def now():
    return datetime.now(timezone.utc)


def _write_once(path, value):
    path = _external(Path(path))
    need(not path.is_symlink(), 'CONTINUITY_RECORD_ALIAS')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(canonical_json_bytes(value=value)); out.flush(); os.fsync(out.fileno())


def _json(path):
    need(not path.is_symlink() and path.is_file(), 'CONTINUITY_RECORD_MISSING_OR_ALIAS: ' + str(path))
    return strict_json_file(path=path)


def _external(path):
    return runtime._external(Path(path))


def _requirement(root=ROOT):
    value = load_requirement_snapshot(snapshot_dir=root / 'requirements' / REQUIREMENT_ID)
    validate_execution_authority(repo_root=root, requirement=value)
    return value


def code_identity():
    return {**runtime.code_identity(), 'test_tree': content_hash(value=git('ls-tree', '-r', 'HEAD', 'tests').decode())}


def _code_matches(identity):
    current = code_identity()
    need(current['runtime_tree'] == identity['runtime_tree'] and current['test_tree'] == identity['test_tree']
         and git('merge-base', identity['exact_head'], 'HEAD').decode().strip() == identity['exact_head'],
         'CONTINUITY_REVIEWED_CODE_CHANGED')


def initialize_data(*, data_root):
    """Copy only existing authority and saved full inputs, with no HTTP calls."""
    from sec_urls import submissions_url, accession_document_url, companyfacts_url
    from .sources import resolve_repository_file
    root = _external(data_root); need(not root.exists(), 'CONTINUITY_DATA_EXISTS')
    requirement = _requirement(); identity = code_identity()
    company = update.supported_company(repo_root=ROOT)
    inventory = update.saved_source(repo_root=ROOT, url=submissions_url(cik=int(company['primary_cik'])))
    need(inventory is not None, 'SUBMISSIONS_SOURCE_MISSING')
    payload = annual_input._json(raw=inventory['raw'])
    filings = annual_input.filing_rows_from_submission_payloads(company=company['display_name'],
        cik=int(company['primary_cik']), entity_role='primary', payloads=[payload])
    proofs = [inventory['proof']]
    urls = {companyfacts_url(cik=int(company['primary_cik'])): ''}
    urls.update({accession_document_url(cik=int(company['primary_cik']), accession=f['accessionNumber'],
        document_name=f['primaryDocument']): f['accessionNumber'] for f in filings if f['form'] == '10-K'})
    for url, accession in sorted(urls.items()):
        saved = update.saved_source(repo_root=ROOT, url=url, accession=accession)
        if saved is not None:
            proofs.append(saved['proof'])
    paths = set(runtime._authority_files(requirement)) | {'evidence/requests_log.csv', 'evidence/requests_log_manifest.json'}
    for proof in proofs:
        paths.update((proof['request_repo_relative_path'], proof['request_headers_repo_relative_path']))
    from .annual_continuity_sources import frozen_foundation_receipts
    receipts=frozen_foundation_receipts()
    for name in sorted(paths):
        source = resolve_repository_file(repo_root=ROOT, repo_relative_path=name)
        destination = root / name; destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as output:
            output.write(receipts[name]['bytes'] if name in receipts else source.read_bytes())
    runtime.verify_data_root(root, requirement)
    need(code_identity() == identity, 'CONTINUITY_CODE_CHANGED_DURING_COPY')
    return {'status': 'SAVED_COMPLETE_INPUTS_COPIED', 'data_root': str(root), 'source_proofs': proofs,
            'code': identity, 'new_provider_paid_sec_calls': [0, 0, 0]}


def _root_separation(root,data,budget):
    values=(root,data,budget)
    need(all(a!=b and a not in b.parents and b not in a.parents
             for i,a in enumerate(values) for b in values[i+1:]), 'CONTINUITY_ROOTS_OVERLAP')


def _period_scope(start,end):
    from datetime import date
    need(type(start) is str and type(end) is str and date.fromisoformat(start).isoformat()==start
         and date.fromisoformat(end).isoformat()==end and start<=end, 'CONTINUITY_PERIOD_SCOPE_INVALID')


def _register_unused_budget(root, data, budget, start):
    """Preserve an inert registration after proposal output failure; never reset it."""
    need(not root.exists(), 'CONTINUITY_STAGE_OR_BUDGET_ALREADY_REGISTERED')
    path=budget/'registration.json'
    fixed={'kind':'CONTINUITY_BUDGET_REGISTRATION','budget_root':str(budget),
        'stage_root':str(root),'data_root':str(data),'policy_id':V3,
        'sec_ledger_origin':{'row_count':len(update._rows(data)), 'rows_id':content_hash(value=update._rows(data))},
        'limits':{'normal_provider':2,'conditional_provider':1,'provider':3,'paid':3,'sec':6,'retry':0}}
    if budget.exists():
        need(set(budget.iterdir())=={path}, 'CONTINUITY_BUDGET_HAS_EXECUTION_STATE')
        value=_json(path);check_id(value,'registration_id')
        need({k:v for k,v in value.items() if k not in {'nonce','created_at_utc','registration_id'}}==fixed
             and re.fullmatch('[0-9a-f]{32}',value.get('nonce','')) is not None
             and parse_utc_timestamp(value=value['created_at_utc'])<=start,
             'CONTINUITY_BUDGET_REGISTRATION_CHANGED')
        return value
    value=record({**fixed,'nonce':uuid4().hex,'created_at_utc':start.isoformat()},'registration_id')
    _write_once(path,value)
    return value


def stage_proposal(*, stage_root, data_root, budget_root, review_file, seed_b01=None, seed_b10=None,
                   visibility_file=None, expires_at_utc, historical_period_start, historical_period_end):
    """Create one inert stage proposal. The review and original seed are explicit."""
    need((seed_b01 is None)==(seed_b10 is None),'CONTINUITY_SEED_PARAMETERS_MUST_BE_PAIRED')
    identity = code_identity(); requirement = _requirement(); chosen = policy(policy_id=V3)
    review = _json(Path(review_file))
    need(review['reviewer_kind'] == 'INDEPENDENT_MODEL_SUBTASK'
         and review['conclusion'] == 'NO_BLOCKING_FINDINGS'
         and review['reviewed_head'] == identity['exact_head'] and review['runtime_tree'] == identity['runtime_tree'],
         'CONTINUITY_INDEPENDENT_REVIEW_REQUIRED')
    root, data, budget = _external(stage_root), _external(data_root), _external(budget_root)
    _root_separation(root,data,budget)
    _period_scope(historical_period_start,historical_period_end)
    runtime.verify_data_root(data, requirement)
    expiry = parse_utc_timestamp(value=expires_at_utc); start = now()
    need(start < expiry <= start + timedelta(days=chosen['maximum_stage_lifetime_days']), 'CONTINUITY_EXPIRY_INVALID')
    from .annual_continuity_snapshot import seed_descriptor
    seed = None if seed_b01 is None else seed_descriptor(b01=Path(seed_b01), b10=Path(seed_b10), data_root=data)
    need(seed is None or (seed['period']['period_start'] >= historical_period_start
         and seed['period']['period_end'] <= historical_period_end), 'CONTINUITY_SEED_OUT_OF_SCOPE')
    registration = _register_unused_budget(root,data,budget,start)
    from .publication import PublicationView
    PublicationView.open(publication_root=ROOT)
    initial_pointer = read(ROOT, 'outputs/active_publication.json')
    body = {'schema_version': 1, 'decision': DECISION,
        'approval_kind': 'USER_DELEGATED_ISOLATED_STAGE_AFTER_INDEPENDENT_REVIEW',
        'delegation_source': 'codex-task:01a081bb-9220-7de3-a311-b481906b3146',
        'statement': 'Codex records this bounded isolated stage under explicit user delegation; this is not a new human code review or continuous production permission.',
        'repository': requirement['baseline']['repository']['identity'],
        'requirement_id': REQUIREMENT_ID, 'requirement_closure_hash': requirement['requirement_closure_hash'],
        'policy': chosen, 'reviewed_code': identity, 'review': review,
        'review_sha256': sha256_file(path=Path(review_file)), 'review_id': content_hash(value=review), 'stage_root': str(root), 'data_root': str(data),
        'budget_root': str(budget), 'budget_registration': registration,
        'publication_root': str(root / 'publication'), 'initial_publication_pointer': initial_pointer, 'seed': seed,
        'visibility_file': None if visibility_file is None else str(_external(visibility_file)),
        'historical_period_scope': {'start': historical_period_start, 'end': historical_period_end},
        'created_at_utc': start.isoformat(), 'expires_at_utc': expiry.isoformat(),
        'maximum_provider_paid_sec_calls': [3, 3, 6], 'normal_provider_calls': 2,
        'conditional_repair_calls': 1, 'automatic_retry_count': 0,
        'production_publication_authorized': False, 'long_running_schedule_authorized': False}
    return record(body, 'stage_id')


def validate_lifetime(stage, *, execution=False):
    start, end = (parse_utc_timestamp(value=stage[k]) for k in ('created_at_utc', 'expires_at_utc'))
    need(start < end <= start + timedelta(days=policy(policy_id=V3)['maximum_stage_lifetime_days']), 'CONTINUITY_EXPIRY_INVALID')
    if execution:
        need(start <= now() <= end, 'CONTINUITY_STAGE_EXPIRED')


def validate_stage(stage, *, execution=False):
    check_id(stage, 'stage_id'); chosen = policy(policy_id=V3)
    need(stage['decision'] == DECISION and content_hash(value=stage['policy']) == content_hash(value=chosen)
         and stage['maximum_provider_paid_sec_calls'] == [3, 3, 6]
         and stage['normal_provider_calls'] == 2 and stage['conditional_repair_calls'] == 1
         and stage['automatic_retry_count'] == 0 and stage['production_publication_authorized'] is False
         and stage['long_running_schedule_authorized'] is False, 'CONTINUITY_STAGE_SCOPE_CHANGED')
    review = stage['review']
    need(review['reviewer_kind'] == 'INDEPENDENT_MODEL_SUBTASK' and review['conclusion'] == 'NO_BLOCKING_FINDINGS'
         and review['reviewed_head'] == stage['reviewed_code']['exact_head']
         and review['runtime_tree'] == stage['reviewed_code']['runtime_tree']
         and stage['review_id'] == content_hash(value=review), 'CONTINUITY_REVIEW_BINDING_CHANGED')
    requirement = _requirement()
    need(stage['requirement_id'] == REQUIREMENT_ID
         and stage['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and stage['repository'] == requirement['baseline']['repository']['identity'], 'CONTINUITY_STAGE_REQUIREMENT_CHANGED')
    _code_matches(stage['reviewed_code'])
    root, budget, data = _external(stage['stage_root']), _external(stage['budget_root']), _external(stage['data_root'])
    _root_separation(root,data,budget)
    _period_scope(stage['historical_period_scope']['start'],stage['historical_period_scope']['end'])
    need(stage['seed'] is None or type(stage['seed']) is dict,'CONTINUITY_SEED_DESCRIPTOR_INVALID')
    if stage['visibility_file'] is not None:_external(Path(stage['visibility_file']))
    need(stage['publication_root'] == str(root / 'publication') and root != budget and root != data,
         'CONTINUITY_STAGE_ROOT_CHANGED')
    registration = _json(budget / 'registration.json'); check_id(registration, 'registration_id')
    need(registration == stage['budget_registration'] and registration['stage_root'] == str(root)
         and registration['budget_root'] == str(budget) and registration['data_root'] == str(data),
         'CONTINUITY_BUDGET_REGISTRATION_CHANGED')
    validate_lifetime(stage, execution=execution)
    if execution:
        need(not (budget / 'closed.json').exists(), 'CONTINUITY_STAGE_CLOSED')
    return requirement


def validate_owner(stage, comment):
    url = comment['html_url']; match = re.fullmatch(r'https://github\.com/' + re.escape(stage['repository'])
        + r'/(?:issues|pull)/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)', url)
    need(match is not None and str(comment['id']) == match[2]
         and comment['issue_url'] == 'https://api.github.com/repos/' + stage['repository'] + '/issues/' + match[1]
         and comment['user']['login'] == stage['repository'].split('/')[0]
         and comment['created_at'] == comment['updated_at']
         and strict_json_loads(text=comment['body']) == stage, 'CONTINUITY_OWNER_PROVENANCE_CHANGED')
    approved = parse_utc_timestamp(value=comment['created_at'])
    need(parse_utc_timestamp(value=stage['created_at_utc']).replace(microsecond=0) <= approved
         <= parse_utc_timestamp(value=stage['expires_at_utc']), 'CONTINUITY_APPROVAL_TIME_INVALID')


def verify_stage(*, approval_url, execution=True):
    from .annual_candidate import _github
    match = re.fullmatch(r'https://github\.com/([^/]+/[^/]+)/(?:issues|pull)/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)', approval_url)
    need(match is not None, 'CONTINUITY_APPROVAL_URL_INVALID')
    value = _github('repos/' + match[1] + '/issues/comments/' + match[3])
    stage = strict_json_loads(text=value['body'])
    need(value['html_url'] == approval_url, 'CONTINUITY_APPROVAL_LOCATION_CHANGED')
    validate_stage(stage, execution=execution)
    comment = {**{k: value[k] for k in ('id', 'html_url', 'issue_url', 'body', 'created_at', 'updated_at')},
               'user': {'login': value['user']['login']}}
    validate_owner(stage, comment)
    return {'stage': stage, 'owner_comment': comment}


@contextmanager
def stage_lock(stage):
    root = _external(stage['budget_root']); path = root / 'run.lock'
    need(not path.is_symlink(), 'CONTINUITY_LOCK_ALIAS')
    with path.open('a+b') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _plan(stage, prepared, selection, source_root, predecessor, ordinal, *, authority_root=ROOT):
    from .table_task_contracts import table_task_execution_plan
    requirement = _requirement(authority_root); task = table_task_execution_plan(repo_root=source_root, task_contract_id=stage['policy']['task_contract_id'])
    body = {'record_type': 'CONTINUOUS_ANNUAL_EXECUTION_PLAN', 'schema_version': 1,
        'stage_id': stage['stage_id'], 'stage_root': stage['stage_root'],
        'requirement_id': REQUIREMENT_ID, 'requirement_closure_hash': requirement['requirement_closure_hash'],
        'requirement_hashes': requirement['hashes'], 'reviewed_code': stage['reviewed_code'],
        'data_root': str(Path(stage['stage_root']) / 'inputs' / stage['reviewed_code']['runtime_tree'][7:] / prepared['input_id'][7:]),
        'prepared_input': prepared, 'selection': selection, 'ordinal': ordinal,
        'source_ledger': {n: {'sha256': sha256_file(path=source_root / 'evidence' / n),
            'size': (source_root / 'evidence' / n).stat().st_size} for n in ('requests_log.csv', 'requests_log_manifest.json')},
        'task_contract_id': stage['policy']['task_contract_id'], 'task_binding': task['run_binding'],
        'request': runtime._request(prepared, source_root, stage['policy']['task_contract_id'], code_root=source_root, requirement=requirement),
        'predecessor_pointer': predecessor, 'maximum_new_executions': 1, 'automatic_retry_count': 0,
        'actual_input_tokens_max': 200000, 'qualification_credit': 'NONE', 'publication_credit': 'NONE'}
    return record(body, 'plan_id')


def _provider_terminal(stage, slot, workspace, *, allow_pending_plan=None):
    """Read native WB-3 identities; outcome flags cannot grant another socket."""
    from . import invocation_control as controller
    from .annual_adoption import verify_saved_execution, _records
    pending = {'provider': 0, 'status': 'UNKNOWN'}
    plan_path = workspace / 'plan.json'
    if not plan_path.exists(): return pending
    plan = _json(plan_path); check_id(plan, 'plan_id')
    need(plan['plan_id'] == slot['plan_id'] and plan['stage_id'] == stage['stage_id']
         and plan['ordinal'] == slot['ordinal'] and plan['prepared_input']['input_id'] == slot['input_id'],
         'CONTINUITY_SLOT_PLAN_CHANGED')
    logroot = workspace / 'invocation_control'
    plans = list((logroot / 'plans').glob('*.json'))
    markers_on_disk = list((logroot / 'egress').glob('*/*.json'))
    executions = list((logroot / 'executions').glob('*.json'))
    need(len(plans) <= 1 and len(markers_on_disk) <= 1 and len(executions) <= 1, 'CONTINUITY_EXTRA_EGRESS')
    current = (plan['plan_id'] == allow_pending_plan and
               _running_candidate.get() == (stage['stage_id'], plan['plan_id'], os.getpid()))
    if not plans:
        need(not markers_on_disk and not executions, 'CONTINUITY_UNBOUND_EGRESS')
        return {'provider': 0, 'status': 'IN_FLIGHT' if current else 'UNKNOWN'}
    invocation = _json(plans[0]); data = Path(plan['data_root'])
    history = controller.prepare_historical_annual_invocation_view(repo_root=data, requirement_id=REQUIREMENT_ID)
    controller.validate_ai_invocation_plan(plan=invocation, _historical_view=history)
    request = plan['request']
    need(invocation['release_input_plan_id'] == plan['plan_id']
         and invocation['provider_request_body_sha256'] == request['provider_request_body_sha256']
         and invocation['source_identity_hash'] == request['reader_input_manifest_id']
         and invocation['selected_representation_hash'] == request['derived_asset_id'], 'CONTINUITY_INVOCATION_CHANGED')
    binding = _json(Path(stage['stage_root']) / 'stage-binding.json')
    need(binding['stage'] == stage, 'CONTINUITY_STAGE_BINDING_CHANGED')
    owner = binding['owner_comment']; validate_owner(stage, owner)
    execution_id = controller.execution_identity(ai_invocation_plan_id=invocation['ai_invocation_plan_id'],
        owner_token=stage['stage_id'], authorized_at_utc=owner['created_at'])
    markers = controller._egress_markers_for_execution(root=logroot, execution_id=execution_id)
    need(len(markers) == len(markers_on_disk), 'CONTINUITY_UNBOUND_EGRESS')
    counters = controller._counters_from_egress_markers(markers=markers, plan=invocation) if markers else controller._empty_counters()
    need(counters['mock_transport_invocation_count'] == 0
         and counters['real_model_provider_egress_count'] == counters['paid_model_provider_call_count'] == len(markers),
         'CONTINUITY_COUNT_UNCERTAIN')
    pending['provider'] = len(markers)
    if not executions:
        if current and not markers: return {**pending, 'status': 'IN_FLIGHT'}
        reservation_path = controller._reservation_path(root=logroot, request_identity=invocation['provider_request_identity'])
        if current and reservation_path.exists():
            reservation = controller._validate_active_reservation_for_plan(reservation=_json(reservation_path), plan=invocation)
            need(reservation['execution_id'] == execution_id and reservation['owner_process_id'] == os.getpid()
                 and reservation['owner_token_hash'] == content_hash(value=stage['stage_id'])
                 and reservation['attempt_ordinal'] == 1, 'CONTINUITY_RESERVATION_NOT_OWNED')
            return {**pending, 'status': 'IN_FLIGHT'}
        return pending
    execution = controller._load_execution_receipt(root=logroot, path=executions[0], execution_id=execution_id)
    need(executions[0] == controller._execution_path(root=logroot, execution_id=execution_id)
         and execution['ai_invocation_plan_id'] == invocation['ai_invocation_plan_id']
         and execution['provider_request_identity'] == invocation['provider_request_identity']
         and execution['counters'] == counters, 'CONTINUITY_EXECUTION_CHANGED')
    if execution['status'] == 'UNKNOWN_REMOTE_OUTCOME': return pending
    need(len(markers) == 1 and execution['attempts'] == controller._attempt_receipts_for_execution(
        root=logroot, execution_id=execution_id, plan=invocation, markers=markers), 'CONTINUITY_ATTEMPT_SET_CHANGED')
    if execution['status'] != 'SUCCEEDED': return {**pending, 'status': 'FAILED'}
    # A transport success alone is not an accepted annual result. Recheck saved
    # raw response/usage and both original native result records, never outcome.status.
    if current: return {**pending, 'status': 'IN_FLIGHT'}
    if not (workspace / 'b10/records.jsonl').exists(): return pending
    requirement = _requirement(data)
    verify_saved_execution(candidate=workspace, data_root=data, plan=plan, stage=stage,
        owner=owner, requirement=requirement, request=request)
    from .annual_continuity_snapshot import _selected
    for name, metric in (('b01', 'B01'), ('b10', 'B10')):
        try: _selected(_records(workspace / name), metric)
        except ValueError: return {**pending, 'status': 'FAILED'}
    return {**pending, 'status': 'SUCCEEDED'}


def budget_counts(stage, *, allow_pending_plan=None):
    """Reconcile permanent slots and native WB-3 terminals across all inputs."""
    root, budget = Path(stage['stage_root']), Path(stage['budget_root'])
    slots = sorted(budget.glob('provider-*.json'))
    ids = set(); observed = 0; failures = []; pending = []
    for index, path in enumerate(slots, 1):
        slot = _json(path); check_id(slot, 'slot_id')
        need(path.name == 'provider-' + str(index) + '.json'
             and slot['registration_id'] == stage['budget_registration']['registration_id']
             and slot['ordinal'] == index and index <= 3, 'CONTINUITY_BUDGET_SLOT_CHANGED')
        ids.add(slot['plan_id']); workspace = root / 'candidates' / slot['plan_id'][7:]
        state = _provider_terminal(stage, slot, workspace, allow_pending_plan=allow_pending_plan)
        observed += state['provider']
        if state['status'] == 'FAILED': failures.append(slot['plan_id'])
        if state['status'] == 'UNKNOWN': pending.append(slot['plan_id'])
    candidates = {p.parent.name for p in (root / 'candidates').glob('*/plan.json')}
    need(candidates <= {p[7:] for p in ids}, 'CONTINUITY_UNACCOUNTED_CANDIDATE')
    sec = sorted(budget.glob('sec-*.json')); sec_unknown = []; sec_failed = []
    if sec:
        data=Path(stage['data_root']);rows=update._rows(data)
        origin=stage['budget_registration']['sec_ledger_origin'];offset=origin['row_count']
        need(content_hash(value=rows[:offset])==origin['rows_id'] and len(rows)<=offset+len(sec),
             'CONTINUITY_SEC_LEDGER_PREFIX_CHANGED')
    for index, path in enumerate(sec, 1):
        record_value = _json(path); check_id(record_value, 'sec_slot_id')
        need(path.name == 'sec-' + str(index) + '.json' and index <= 6
             and record_value['registration_id'] == stage['budget_registration']['registration_id']
             and record_value['ordinal']==index and record_value['stage_id']==stage['stage_id']
             and record_value['ledger_before_count']==offset+index-1
             and record_value['ledger_before_rows_id']==content_hash(value=rows[:offset+index-1]), 'CONTINUITY_SEC_SLOT_CHANGED')
        terminal_path = budget / 'sec-terminals' / path.name
        if not terminal_path.exists() or len(rows)<offset+index:
            sec_unknown.append(path.name);continue
        terminal = _json(terminal_path);check_id(terminal,'sec_terminal_id')
        row=rows[offset+index-1];result=terminal['result']
        need(terminal['slot'] == record_value and terminal['ledger_row']==row
             and row['source_url']==record_value['item']['url']==result['url']
             and row['status_code']==str(result['status_code']) and row['error']==result['error']
             and row['retry_attempt']=='0' and row['method']=='GET'
             and row['content_sha256']==result['sha256'] and row['content_length']==str(result['content_length'])
             and row['purpose']=='annual_continuity_'+record_value['item']['kind'].lower(), 'CONTINUITY_SEC_TERMINAL_CHANGED')
        need(parse_utc_timestamp(value=row['timestamp_utc'])>=parse_utc_timestamp(value=record_value['reserved_at_utc']).replace(microsecond=0),
             'CONTINUITY_SEC_ATTEMPT_PREDATES_SLOT')
        if row['content_sha256']:
            from sec_http import read_request_snapshot_bytes, request_headers_bytes_match_identity
            from .sources import resolve_repository_file
            body=read_request_snapshot_bytes(workdir=data,path=resolve_repository_file(repo_root=data,repo_relative_path=row['repo_relative_path']))
            headers=read_request_snapshot_bytes(workdir=data,path=resolve_repository_file(repo_root=data,repo_relative_path=row['headers_repo_relative_path']))
            from .canonical import sha256_bytes
            need(sha256_bytes(content=body)==row['content_sha256'] and len(body)==int(row['content_length'])
                 and request_headers_bytes_match_identity(content=headers,source_url=row['source_url'],status_code=row['status_code'],
                    content_length=row['content_length'],content_sha256=row['content_sha256']), 'CONTINUITY_SEC_RESPONSE_CHANGED')
        accepted=row['status_code']=='200' and not row['error']
        need(terminal['status']==('SUCCEEDED' if accepted else 'FAILED'),'CONTINUITY_SEC_TERMINAL_CHANGED')
        if not accepted: sec_failed.append(path.name)
    need(observed <= len(slots) <= 3 and len(sec) <= 6, 'CONTINUITY_BUDGET_EXCEEDED')
    return {'provider': observed, 'paid': observed, 'sec_reserved': len(sec), 'provider_reserved': len(slots),
            'failed_plans': failures, 'uncertain_plans': pending, 'uncertain_sec': sec_unknown, 'failed_sec': sec_failed}


def authorization_fields(binding):
    stage, plan = binding['stage'], binding['plan']
    requirement = validate_stage(stage); validate_owner(stage, binding['owner_comment'])
    check_id(plan, 'plan_id')
    data = runtime.verify_data_root(Path(plan['data_root']), requirement)
    visibility = plan['selection']['visibility']
    prepared, selection = select_saved_input(data, None if visibility is None else visibility['visibility'])
    need(plan == _plan(stage, prepared, selection, data, plan['predecessor_pointer'], plan['ordinal']),
         'CONTINUITY_INPUT_OR_REQUEST_CHANGED')
    scope = stage['historical_period_scope']; period = prepared['table_input']['target_period']
    need(scope['start'] <= period['period_start'] <= period['period_end'] <= scope['end'], 'CONTINUITY_INPUT_OUT_OF_STAGE_SCOPE')
    slot = _json(Path(stage['budget_root']) / ('provider-' + str(plan['ordinal']) + '.json')); check_id(slot, 'slot_id')
    need(slot['stage_id'] == stage['stage_id'] and slot['plan_id'] == plan['plan_id']
         and slot['input_id'] == prepared['input_id'], 'CONTINUITY_SLOT_PLAN_CHANGED')
    counts = budget_counts(stage, allow_pending_plan=plan['plan_id'])
    need(not counts['uncertain_plans'] and not counts['uncertain_sec'], 'CONTINUITY_COUNT_UNKNOWN')
    workspace, run_dir, run_id = runtime._paths(plan)
    return {'binding': binding, 'plan': plan, 'requirement': requirement,
        'workspace_dir': workspace, 'run_dir': run_dir, 'run_id': run_id,
        'owner_token': stage['stage_id'], 'authorized_at_utc': binding['owner_comment']['created_at'], 'data_root': data}


def require_live_boundary(binding):
    if binding['stage'].get('decision') == DECISION:
        validate_stage(binding['stage'], execution=True)


def _visibility(stage):
    value=stage['visibility_file']
    return None if value is None else _json(_external(Path(value)))


def _reserve_provider(stage, plan):
    counts = budget_counts(stage)
    need(not counts['uncertain_plans'] and not counts['uncertain_sec'], 'CONTINUITY_COUNT_UNKNOWN')
    need(not counts['failed_plans'] and not counts['failed_sec'], 'CONTINUITY_REPAIRED_REBIND_REQUIRED')
    need(counts['provider_reserved'] < stage['normal_provider_calls'], 'CONTINUITY_NORMAL_BUDGET_EXHAUSTED')
    for p in Path(stage['budget_root']).glob('provider-*.json'):
        prior = _json(p)
        need(prior['input_id'] != plan['prepared_input']['input_id']
             and prior['filing']['period_end'] != plan['selection']['filing']['period_end'],
             'CONTINUITY_INPUT_ALREADY_RESERVED')
    need(plan['ordinal'] == counts['provider_reserved'] + 1, 'CONTINUITY_ORDINAL_CHANGED')
    slot = record({'registration_id': stage['budget_registration']['registration_id'],
        'stage_id': stage['stage_id'], 'ordinal': plan['ordinal'], 'kind': 'NORMAL',
        'plan_id': plan['plan_id'], 'input_id': plan['prepared_input']['input_id'],
        'filing': plan['selection']['filing'], 'reserved_at_utc': now().isoformat()}, 'slot_id')
    _write_once(Path(stage['budget_root']) / ('provider-' + str(plan['ordinal']) + '.json'), slot)


def close_stage(*, approval_url):
    binding = verify_stage(approval_url=approval_url, execution=False); stage = binding['stage']
    with stage_lock(stage):
        counts = budget_counts(stage)
        path = Path(stage['budget_root']) / 'closed.json'
        if not path.exists():
            _write_once(path, {'stage_id': stage['stage_id'], 'closed_at_utc': now().isoformat(),
                               'reason': 'WORK_PACKAGE_DELIVERY_NO_MORE_BUSINESS_CALLS', 'counts': counts})
    return {'status': 'STAGE_CLOSED', 'counts': counts}


def _successful_candidate(stage):
    from .run_store import _mechanically_replay_open_run
    from .canonical import atomic_write_json
    root=Path(stage['stage_root']);path=root/'successful-candidate.json'
    successes=[]
    for slot_path in sorted(Path(stage['budget_root']).glob('provider-*.json')):
        slot=_json(slot_path);candidate=root/'candidates'/slot['plan_id'][7:]
        if _provider_terminal(stage,slot,candidate)['status']=='SUCCEEDED': successes.append((slot,candidate))
    if not successes:
        need(not path.exists(),'CONTINUITY_SUCCESS_REFERENCE_WITHOUT_NATIVE_SUCCESS')
        return None
    slot,candidate=successes[-1];plan=_json(candidate/'plan.json')
    ref={'stage_id':stage['stage_id'],'plan_id':plan['plan_id'],'candidate_directory':str(candidate),'run_id':runtime._paths(plan)[2]}
    if path.exists():
        prior=_json(path)
        need(any(prior['plan_id']==s['plan_id'] and prior['candidate_directory']==str(c) for s,c in successes),
             'CONTINUITY_SUCCESS_REFERENCE_CHANGED')
    workspace,b10,run_id=runtime._paths(plan)
    need(candidate==workspace and plan['stage_id']==stage['stage_id'] and ref['plan_id']==plan['plan_id'],
         'CONTINUITY_SUCCESS_REFERENCE_CHANGED')
    for name in ('b01','b10'):
        manifest,records,_=_mechanically_replay_open_run(run_dir=candidate/name,repo_root=Path(plan['data_root']),require_complete_results=True)
        from .annual_continuity_snapshot import _selected
        _selected(records,'B01' if name=='b01' else 'B10')
    if not path.exists() or _json(path)!=ref: atomic_write_json(path=path,value=ref)
    baseline=update.candidate_baseline(company=update.supported_company(repo_root=ROOT),run_dir=b10)
    return {'reference':ref,'baseline':baseline,'plan':plan}


def _publish_candidate(binding, candidate, *, seed=False):
    from . import annual_publication as annual,annual_continuity_publication as publishing
    from . import annual_publication_authority as authority,publication as pub
    stage=binding['stage'];root=Path(stage['publication_root'])
    path=Path(stage['stage_root'])/('seed-publication-plan.json' if seed else 'publication-work/'+candidate.name+'/plan.json')
    if path.exists():
        planned=_json(path)
    else:
        prepared=annual.prepare(candidate_dir=candidate,publication_root=root,policy_id=V3)
        planned=publishing.plan(bundle_dir=root/'outputs/publications'/prepared['publication_id'],approval_url=binding['owner_comment']['html_url'])
        _write_once(path,planned)
    permission=publishing.verify_authorization(plan=planned,activation_url=binding['owner_comment']['html_url'],owner_url=binding['owner_comment']['html_url'])
    # Reuse the already fully validated exact manifest carried by the opaque
    # permission. Generic bundle verification still checks every file byte.
    pin=annual._Verified(annual._FACTORY,authority._permission(permission)['manifest'])
    with annual._verified(pin):
        current=pub.PublicationView.open(publication_root=root)
        if current.publication_id==planned['binding']['publication_id']:
            record_value=pub._switch_receipt_for_pointer(pointer_path=root/'outputs/active_publication.json',pointer=read(root,'outputs/active_publication.json'))
            need(record_value.get('annual_authority',{}).get('plan_id')==planned['plan_id'],'CONTINUITY_EXISTING_PUBLICATION_NOT_THIS_PLAN')
            return {'status':'ALREADY_COMMITTED_NO_NEW_PUBLICATION','publication_id':current.publication_id,'plan_id':planned['plan_id']}
        result=authority.execute(permission=permission,operation='publish')
        current=pub.PublicationView.open(publication_root=root)
        need(result['status']=='AUTHORIZED_PUBLISH_COMPLETED' and current.publication_id==planned['binding']['publication_id'],
             'CONTINUITY_PUBLICATION_NOT_COMMITTED')
        _write_once(path.parent/('seed-publication-result.json' if seed else 'publication-result.json'),result)
        return {**result,'plan_id':planned['plan_id']}


def _recover_pending(binding):
    from . import publication as pub,annual_continuity_publication as publishing,annual_publication_authority as authority
    stage=binding['stage'];root=Path(stage['publication_root'])
    if not (root/'outputs/active_publication.json').exists():return None
    intent=pub._load_switch_intent(pointer_path=root/'outputs/active_publication.json')
    if intent is None:return None
    plan_id=intent.get('annual_authority',{}).get('plan_id');plans=[]
    for path in [Path(stage['stage_root'])/'seed-publication-plan.json',*Path(stage['stage_root']).glob('publication-work/*/plan.json')]:
        if path.exists() and _json(path)['plan_id']==plan_id:plans.append(_json(path))
    need(len(plans)==1,'CONTINUITY_PENDING_TRANSACTION_UNBOUND')
    planned=plans[0]
    permission=publishing.verify_authorization(plan=planned,activation_url=binding['owner_comment']['html_url'],
        owner_url=binding['owner_comment']['html_url'],allow_expired_recovery=True)
    return authority.execute(permission=permission,operation='recover')


def _fetch_missing(stage, item):
    """One existing SEC client call, reserved in the same non-resetting budget."""
    from sec_http import SecHttpClient
    counts=budget_counts(stage)
    need(not counts['uncertain_plans'] and not counts['uncertain_sec'],'CONTINUITY_COUNT_UNKNOWN')
    need(not counts['failed_sec'], 'CONTINUITY_SEC_FAILURE_STOP')
    need(counts['sec_reserved']<stage['maximum_provider_paid_sec_calls'][2],'CONTINUITY_SEC_BUDGET_EXHAUSTED')
    data=Path(stage['data_root']);client=SecHttpClient(workdir=data,config_path=data/'config/sec_config.json',log_path=data/'evidence/requests_log.csv')
    client.config={**client.config,'max_retries':0}
    ordinal=counts['sec_reserved']+1;budget=Path(stage['budget_root'])
    before=update._rows(data)
    slot=record({'stage_id':stage['stage_id'],'registration_id':stage['budget_registration']['registration_id'],
        'ordinal':ordinal,'item':item,'reserved_at_utc':now().isoformat(),
        'ledger_before_count':len(before),'ledger_before_rows_id':content_hash(value=before)},'sec_slot_id')
    validate_stage(stage,execution=True)
    _write_once(budget/('sec-'+str(ordinal)+'.json'),slot)
    before=update._rows(data)
    result=client.fetch(url=item['url'],purpose='annual_continuity_'+item['kind'].lower(),
        local_path=data/'evidence/annual_continuity'/uuid4().hex/item['document_name'])
    after=update._rows(data)
    need(len(after)==len(before)+1 and after[:-1]==before,'CONTINUITY_SEC_COUNT_UNKNOWN')
    _write_once(budget/'sec-terminals'/('sec-'+str(ordinal)+'.json'),
        record({'slot':slot,'result':result.__dict__,'ledger_row':after[-1],'status':'SUCCEEDED' if result.status_code==200 and not result.error else 'FAILED'},'sec_terminal_id'))
    need(result.status_code==200 and not result.error,'CONTINUITY_SEC_FAILED')


@contextmanager
def _initial_version(stage):
    from . import publication as pub, annual_publication as annual
    view=pub.PublicationView.open(publication_root=ROOT)
    need(read(ROOT,'outputs/active_publication.json')==stage['initial_publication_pointer'],
         'CONTINUITY_FORMAL_BASELINE_CHANGED')
    with annual._verified(annual._Verified(annual._FACTORY,view.manifest)):
        yield


def _current_published(stage):
    company=update.supported_company(repo_root=ROOT)
    return update.published_baseline(company=company,publication_root=Path(stage['publication_root']))


def _inspect_input_for_run(**kwargs):
    """Scope inspector-only counters; execution describes this invocation's candidate step."""
    report = update.inspect_annual_update(**kwargs)
    report["inspection"] = {
        "execution": report.pop("execution"),
        "provider_paid_sec_calls": report.pop("provider_paid_sec_calls"),
    }
    report["execution"] = "NOT_EXECUTED"
    return report


def run_once(*, approval_url, refresh_submissions=False):
    """Continue an unfinished input before selecting another; never update the actual root."""
    from . import publication as pub,annual_continuity_publication as publishing
    from .annual_continuity_snapshot import create_seed_candidate
    from .canonical import atomic_write_json
    binding=verify_stage(approval_url=approval_url,execution=False);stage=binding['stage'];root=Path(stage['stage_root'])
    with stage_lock(stage), _initial_version(stage):
        recovery=_recover_pending(binding)
        if recovery is not None:
            return {'status':'RECOVERED_PRIOR_TRANSACTION','execution':'NOT_EXECUTED','recovery':recovery,'counts':budget_counts(stage),
                'current_published':_current_published(stage),'discovery_status':'NOT_RECHECKED_RECOVERY_FIRST'}
        validate_stage(stage,execution=True)
        if not (root/'stage-binding.json').exists():
            need(not root.exists(),'CONTINUITY_UNBOUND_STAGE_RESIDUE')
            _write_once(root/'stage-binding.json',binding)
        need(_json(root/'stage-binding.json')==binding,'CONTINUITY_STAGE_APPROVAL_CHANGED')
        publishing.initialize(publication_root=Path(stage['publication_root']),approval_url=approval_url)
        if stage['seed'] is not None and not (root/'seed-publication-result.json').exists():
            candidate=root/'seed-candidate'
            if not candidate.exists():candidate=create_seed_candidate(stage,binding['owner_comment'])
            seeded=_publish_candidate(binding,candidate,seed=True)
            # The actual original statuses and mixed-period inheritance stay in the seed package.
            if stage['seed'] is not None and not (root/'seed-publication-result.json').exists():_write_once(root/'seed-publication-result.json',seeded)
        counts=budget_counts(stage)
        need(not counts['uncertain_plans'] and not counts['uncertain_sec'],'CONTINUITY_COUNT_UNKNOWN')
        company=update.supported_company(repo_root=ROOT)
        published=update.published_baseline(company=company,publication_root=Path(stage['publication_root']))
        success=_successful_candidate(stage)
        if success is not None and success['baseline']['run_id']!=published['run_id']:
            pending=_publish_candidate(binding,Path(success['reference']['candidate_directory']))
            return {'status':'PENDING_CANDIDATE_PUBLISHED','execution':'NOT_EXECUTED','publication':pending,'counts':budget_counts(stage),
                'discovery_status':'NOT_RECHECKED_PENDING_CANDIDATE','discovered_filing':success['plan']['selection']['filing'],
                'latest_successful_candidate':success['baseline'],'published_before':published,
                'current_published':_current_published(stage),'candidate_work':'NONE','publication_work':'COMPLETE'}
        need(not counts['failed_plans'],'CONTINUITY_FAILED_INPUT_REQUIRES_REVIEWED_REPAIR')
        if refresh_submissions:
            from sec_urls import submissions_url
            need(not any(_json(p)['item']['kind']=='SUBMISSIONS' for p in Path(stage['budget_root']).glob('sec-*.json')),'CONTINUITY_SUBMISSIONS_REFRESH_ALREADY_USED')
            url=submissions_url(cik=int(company['primary_cik']))
            _fetch_missing(stage,{'kind':'SUBMISSIONS','url':url,'document_name':url.rsplit('/',1)[-1]})
            _write_once(Path(stage['budget_root'])/'submissions-refreshed.json',{'stage_id':stage['stage_id'],'completed_at_utc':now().isoformat()})
        if refresh_submissions:
            refreshed=_inspect_input_for_run(repo_root=Path(stage['data_root']),company=company,successful_candidate=None,published=published)
            newest=refreshed.get('discovered_filing');scope=stage['historical_period_scope']
            if newest and not(scope['start']<=newest['period_start']<=newest['period_end']<=scope['end']):
                return {**refreshed,'status':'DISCOVERED_OUTSIDE_STAGE_SCOPE_NOT_EXECUTED','counts':budget_counts(stage)}
        visibility=_visibility(stage)
        report=_inspect_input_for_run(repo_root=Path(stage['data_root']),company=company,
            successful_candidate=None if success is None else success['baseline'],published=published,visibility=visibility)
        report.update(stage_id=stage['stage_id'],publication_root=stage['publication_root'],recovery=None,
            start_mode='CURRENT_ACTIVE' if stage['seed'] is None else 'EXPLICIT_HISTORICAL_SEED')
        if report.get('discovered_filing'):
            filing=report['discovered_filing'];scope=stage['historical_period_scope']
            if not (scope['start']<=filing['period_start']<=filing['period_end']<=scope['end']):
                return {**report,'status':'DISCOVERED_OUTSIDE_STAGE_SCOPE_NOT_EXECUTED','counts':budget_counts(stage)}
        attempted=set()
        while report['status']=='INPUTS_MISSING':
            item=report['missing_sources'][0];need(item['url'] not in attempted,'CONTINUITY_NO_AUTOMATIC_RETRY');attempted.add(item['url'])
            _fetch_missing(stage,item)
            report=_inspect_input_for_run(repo_root=Path(stage['data_root']),company=company,
                successful_candidate=None if success is None else success['baseline'],published=published,visibility=visibility)
        if report['status']=='NO_NEW_ANNUAL_FILING':
            return {**report,'status':'NO_CHANGE','counts':budget_counts(stage)}
        if report['status']!='INPUT_READY':
            return {**report,'counts':budget_counts(stage)}
        prepared,selection=select_saved_input(Path(stage['data_root']),visibility)
        need(prepared==report['prepared_input'],'CONTINUITY_INPUT_CHANGED_DURING_CHECK')
        from .ai_adapter import configured_annual_transport_policy,api_key_environment_name,api_key_required_error_code
        requirement=_requirement()
        data=runtime.verify_data_root(Path(stage['data_root']),requirement)
        transport=configured_annual_transport_policy(requirement=requirement,repo_root=data)
        credential='' if os.environ.get(api_key_environment_name(policy=transport),'').strip() else api_key_required_error_code(policy=transport)
        if credential:return {**report,'status':'CREDENTIAL_REQUIRED','error':credential,'counts':budget_counts(stage)}
        predecessor=read(Path(stage['publication_root']),'outputs/active_publication.json')
        planned=_plan(stage,prepared,selection,Path(stage['data_root']),predecessor,counts['provider_reserved']+1)
        _reserve_provider(stage,planned)
        candidate,b10,run_id=runtime._paths(planned)
        runtime._copy_inputs(source_root=Path(stage['data_root']),data_root=Path(planned['data_root']),
            prepared=prepared,requirement=_requirement())
        candidate.mkdir(parents=True,exist_ok=True);_write_once(candidate/'plan.json',planned)
        active_binding={**binding,'plan':planned}
        token=_running_candidate.set((stage['stage_id'],planned['plan_id'],os.getpid()))
        try:
            outcome=runtime.execute_native_candidate(authorization=runtime.RuntimeAuthorization(factory=runtime._FACTORY,binding=active_binding))
        except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
            outcome={'status':'CANDIDATE_UPDATE_FAILED','error':str(error),'error_type':type(error).__name__,
                'execution':'INSPECT_NATIVE_CONTROLLER','original_partial_runs_retained':True}
        finally:
            _running_candidate.reset(token)
        _write_once(candidate/'outcome.json',outcome)
        if outcome['status']!='CANDIDATE_UPDATE_SUCCEEDED':
            return {**report,**outcome,'counts':budget_counts(stage),'current_published':published}
        # Both complete native results are required before this mutable pointer advances.
        ref={'stage_id':stage['stage_id'],'plan_id':planned['plan_id'],'candidate_directory':str(candidate),'run_id':run_id}
        atomic_write_json(path=root/'successful-candidate.json',value=ref)
        published_result=_publish_candidate(binding,candidate)
        return {**report,'status':'COMPLETE_UPDATE_COMMITTED','execution':'EXECUTED','candidate':ref,'publication':published_result,
            'counts':budget_counts(stage),'execution_code':code_identity(),
            'published_before':published,'current_published':_current_published(stage),
            'latest_successful_candidate':update.candidate_baseline(company=company,run_dir=b10),
            'candidate_work':'COMPLETE','publication_work':'COMPLETE'}
