"""The approved nine-sample R4 development purpose, using existing invocation control.

Source Requirement/proof bytes remain immutable. A short-lived implementation
binding separates diagnostic code from those historical source semantics; it
cannot enable formal qualification or publication. Live permission still comes
from the existing exact-head owner-comment capability.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import json

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from .sources import resolve_repository_file

REQUEST_SET_ID = "sha256:c8608d448f3591c56d79057159e143aaf2506f8d550d9ae2101c98ae6408c42d"
SCOPE_PATH = "docs/evidence/r4_development_diagnostic_scope.json"
TASK_APPROVAL_PATH = "docs/evidence/r4_development_task_approval.json"
SELECTION_REQUEST_SET_ID = "sha256:670d566388cd68843a97eaef3858eee74b75586fcb323951e82aeaf0c88a95c0"
SELECTION_SCOPE_PATH = "docs/evidence/r4_cell_selection_diagnostic_scope.json"
PLAN_TYPE = "R4_DEVELOPMENT_DIAGNOSTIC_PLAN"
PURPOSE = "R4_DEVELOPMENT_DIAGNOSTIC_NO_CREDIT"
RUNTIME_ROOT = "artifacts/vnext/qualification/r4_scoped/development"
_CURRENT = ContextVar("r4_development_implementation", default=None)
_FACTORY = object()
# Only interface, execution wiring and their capability descriptions can differ
# from frozen v3. Source/proof/Spec/engine/business configuration cannot differ.
_CHANGED_BINDINGS = frozenset({
    "scripts/vnext/ai_adapter.py", "scripts/vnext/scoped_reader.py",
    "scripts/vnext/requirement_profile.py", "scripts/vnext/evidence.py",
    "scripts/vnext/live_scoped_reader.py", "scripts/vnext/r4_live_authority.py",
    "scripts/vnext/r4_live_qualification.py", "tools/vnext_r4_qualification.py",
    "architecture.md", "capability_contract.json", "interact.md", "TESTING.md",
})


def is_diagnostic(plan):
    return plan.get("record_type") == PLAN_TYPE


def approved_scope(root, request_set_id=REQUEST_SET_ID):
    # The new scope is an execution proposal, not a captured owner approval.
    # Only the real exact-head comment preflight can authorize its calls.
    if request_set_id == SELECTION_REQUEST_SET_ID:
        from .cell_selection import REVISION
        scope = strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=SELECTION_SCOPE_PATH))
        historical = approved_scope(root)
        if (scope.get('request_set_id') != SELECTION_REQUEST_SET_ID
                or content_hash(value=scope.get('entries')) != SELECTION_REQUEST_SET_ID
                or scope.get('interface_revision') != REVISION
                or scope.get('authorization_state') != 'NOT_ISSUED'
                or scope.get('authorization_source') != 'EXACT_HEAD_GITHUB_OWNER_COMMENT_REQUIRED'
                or any(scope.get(k) != historical[k] for k in (
                    'source_requirement_id', 'source_requirement_closure_hash', 'provider', 'model',
                    'maximum_provider_calls', 'maximum_paid_model_calls', 'execution_order',
                    'automatic_retry_count', 'response_reuse_authorized', 'sec_calls_authorized',
                    'publication_authorized', 'qualification_credit', 'publication_credit',
                    'context_ceiling_tokens', 'stability_repeats', 'continue_only_if', 'stop_on'))
                or len(scope['entries']) != len(historical['entries'])):
            raise ValueError('Cell-selection diagnostic scope differs from its bound proposal')
        for row, old in zip(scope['entries'], historical['entries']):
            if any(row.get(k) != old[old_key] for k, old_key in (
                    ('fixture_id','fixture_id'), ('period','task_period'),
                    ('source_sha256','source_sha256'), ('source_scope_manifest_id','source_scope_manifest_id'))):
                raise ValueError('Cell-selection source/order differs from the nine base requests')
        return scope
    if request_set_id != REQUEST_SET_ID:
        raise ValueError('Unknown diagnostic request set')
    scope = strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=SCOPE_PATH))
    if (scope.get("request_set_id") != REQUEST_SET_ID
            or content_hash(value=scope.get("entries")) != REQUEST_SET_ID
            or len(scope["entries"]) != 9
            or scope["source_requirement_id"] != "issue_28_v3"
            or scope["maximum_provider_calls"] != 9
            or scope["maximum_paid_model_calls"] != 9
            or scope["automatic_retry_count"] != 0
            or scope["response_reuse_authorized"] is not False
            or scope["sec_calls_authorized"] is not False
            or scope["publication_authorized"] is not False
            or scope["qualification_credit"] != "NONE"
            or scope["context_ceiling_tokens"] != 200000):
        raise ValueError("Diagnostic scope differs from the approved nine requests")
    approval = strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=TASK_APPROVAL_PATH))
    if (approval["source_kind"] != "CURRENT_CODEX_USER_INSTRUCTION"
            or approval["approval_text"] != "批准" or approval["approved_scope_path"] != SCOPE_PATH
            or approval["approved_scope_sha256"] != sha256_bytes(content=(root / SCOPE_PATH).read_bytes())):
        raise ValueError("Diagnostic task-scope approval differs")
    return scope


class _Implementation:
    def __init__(self, root, requirement, factory, offline_interface_revision=None, request_set_id=REQUEST_SET_ID):
        if factory is not _FACTORY:
            raise ValueError("Diagnostic implementation requires its factory")
        from .r4_live_authority import _git_state
        self.root, self.requirement_id = root, requirement["requirement_id"]
        self.scope = approved_scope(root, request_set_id)
        from .cell_selection import REVISION
        if offline_interface_revision not in (None, REVISION):
            raise ValueError('Unknown offline selection interface')
        if offline_interface_revision is not None and request_set_id != REQUEST_SET_ID:
            raise ValueError('Offline interface experiments cannot select a live diagnostic scope')
        self.offline_only = offline_interface_revision is not None
        self.interface_revision = offline_interface_revision or self.scope['interface_revision']
        if requirement["requirement_closure_hash"] != self.scope["source_requirement_closure_hash"]:
            raise ValueError("Diagnostic source Requirement changed")
        self.state = _git_state(repo_root=root, clean=False) if (root / '.git').exists() else {"head": None, "tree": None}
        self.files = {}
        for relative, frozen in requirement["execution_authority"]["files"].items():
            data = resolve_repository_file(repo_root=root, repo_relative_path=relative).read_bytes()
            binding = {"sha256": sha256_bytes(content=data), "size": len(data)}
            if binding != frozen and relative not in _CHANGED_BINDINGS:
                raise ValueError("Diagnostic scope cannot change source/semantic authority: " + relative)
            self.files[relative] = binding
        # Include newly added production code, not just old snapshot file names.
        for parent in (root / 'scripts', root / 'tools'):
            for path in parent.rglob('*.py'):
                relative = path.relative_to(root).as_posix()
                data = resolve_repository_file(repo_root=root, repo_relative_path=relative).read_bytes()
                self.files[relative] = {"sha256": sha256_bytes(content=data), "size": len(data)}
        scope_files = (SCOPE_PATH, TASK_APPROVAL_PATH)
        if request_set_id == SELECTION_REQUEST_SET_ID:
            scope_files += (SELECTION_SCOPE_PATH,)
        for relative in scope_files:
            data = (root / relative).read_bytes()
            self.files[relative] = {"sha256": sha256_bytes(content=data), "size": len(data)}
        body = {"purpose": PURPOSE, "request_set_id": request_set_id,
            "source_requirement_id": self.requirement_id,
            "source_requirement_closure_hash": requirement["requirement_closure_hash"],
            "files": self.files, "semantic_runtime_versions_hash": requirement["execution_authority"]["semantic_runtime_versions_hash"]}
        if self.offline_only:
            body.update(offline_interface_revision=self.interface_revision,
                live_authorization_eligible=False, source_request_set_role='HISTORICAL_SOURCE_SET_ONLY')
        elif request_set_id == SELECTION_REQUEST_SET_ID:
            body.update(interface_revision=self.interface_revision, scope_path=SELECTION_SCOPE_PATH,
                scope_sha256=self.files[SELECTION_SCOPE_PATH]['sha256'])
        self.record = {**body, "development_execution_binding_id": content_hash(value=body)}

    def check(self):
        if _CURRENT.get() is not self:
            raise ValueError("Diagnostic implementation used outside its scoped purpose")
        from .live_scoped_reader import _check_files
        _check_files(repo_root=self.root, bindings=self.files)


def current_implementation(root, requirement):
    bound = _CURRENT.get()
    if bound is None:
        return None
    if root.resolve() != bound.root or requirement["requirement_id"] != bound.requirement_id:
        raise ValueError("Diagnostic implementation/source context differs")
    bound.check()
    return bound


@contextmanager
def diagnostic_implementation(root, *, offline_interface_revision=None, request_set_id=REQUEST_SET_ID):
    from .requirements import load_requirement_snapshot
    if _CURRENT.get() is not None:
        raise ValueError("Diagnostic implementation contexts cannot be nested")
    root = root.resolve(strict=True)
    requirement = load_requirement_snapshot(snapshot_dir=root / "requirements/issue_28_v3")
    bound = _Implementation(root, requirement, _FACTORY, offline_interface_revision, request_set_id)
    token = _CURRENT.set(bound)
    try:
        bound.check()
        yield bound
    finally:
        _CURRENT.reset(token)


@contextmanager
def diagnostic_implementation_for_plan(root, plan):
    """Restore the finite interface/scope binding from a saved plan, then revalidate.

    A caller cannot supply an interface override or turn an offline experiment
    into a live plan. Full plan/request/file rebuilding still precedes replay
    or owner preflight; this loader does not issue any execution capability.
    """
    if (not is_diagnostic(plan) or plan.get('pending_plan_id') != content_hash(
            value={k:v for k,v in plan.items() if k != 'pending_plan_id'})):
        raise ValueError('Diagnostic saved plan identity differs')
    binding = plan['implementation_authority']
    if 'offline_interface_revision' in binding:
        raise ValueError('Offline experimental plans are not diagnostic CLI execution plans')
    with diagnostic_implementation(root, request_set_id=binding['request_set_id']) as implementation:
        if binding != implementation.record:
            raise ValueError('Saved diagnostic implementation/interface binding differs')
        yield implementation


def verify_request_set(context):
    rows = context._session._development.scope['entries']
    if set(context._requests) != {r['fixture_id'] for r in rows}:
        raise ValueError("Diagnostic base request exact set changed")
    for row in rows:
        request = context._requests[row['fixture_id']]
        capture = request.identity
        for field, expected in (("source_scope_manifest_id", row["source_scope_manifest_id"]),
                ("source_sha256", row["source_sha256"]),
                ("task_period", row['period'] if context._session._development.scope['request_set_id'] == SELECTION_REQUEST_SET_ID else row['task_period']),
                ("provider_request_body_sha256", row["request_sha256"]),
                ("provider_request_body_size", row["request_bytes"]),
                ("provider_output_schema_sha256", row["output_schema_sha256"])):
            if context._session._development.offline_only and field in {
                    'provider_request_body_sha256','provider_request_body_size','provider_output_schema_sha256'}:
                # New bytes are bound by their new request/plan identity; old
                # paid-request hashes remain historical, never a new grant.
                continue
            if capture[field] != expected:
                raise ValueError("Approved diagnostic request changed: " + row['fixture_id'] + ':' + field)


def prepare_diagnostic_context(root):
    from .r4_live_authority import prepare_r4_execution_context
    context = prepare_r4_execution_context(repo_root=root, requirement_id='issue_28_v3')
    if context._session._development is None:
        raise ValueError("Diagnostic context requires explicit diagnostic implementation")
    verify_request_set(context)
    return context


def build_diagnostic_plan(context, *, mode="LIVE"):
    from .r4_live_authority import _build_plan, _git_state
    if context._session._development is None:
        raise ValueError("Diagnostic plan requires its explicit purpose")
    if mode == 'LIVE' and context._session._development.offline_only:
        raise ValueError('New cell-selection requests have no live authorization')
    state = _git_state(repo_root=context._root, clean=True) if mode == "LIVE" else context._state
    return _build_plan(context, mode=mode, state=state)


def _entry_root(context, plan, entry):
    from .r4_live_authority import invocation_namespace
    from .r4_live_qualification import _runtime_path
    return _runtime_path(context, invocation_namespace(plan, entry['entry_id']))


def _tree(root):
    from .r4_live_qualification import _tree_files
    if (root / 'qualification_terminal.json').exists():
        raise ValueError('Formal qualification terminal is forbidden in a diagnostic entry')
    return {p: v for p, v in _tree_files(root).items() if p != 'diagnostic_terminal.json'}


def _read_payloads(root, fields):
    required = {'request_body','reader_payload','task_contract','output_schema'}
    if (type(fields) is not list or any(type(f) is not str for f in fields)
            or fields != sorted(set(fields)) or not required.issubset(fields)
            or set(fields) - required - {'assistant_output','raw_response'}):
        raise ValueError('Diagnostic payload exact field set differs')
    return {k:(root / 'payloads' / (k+'.bin')).read_bytes() for k in fields}


def _check_response(acceptance, response, execution_id):
    """Only known response-validation rejections qualify as sample failures.

    Unknown exceptions, source checks and persistence failures are not folded
    into content failures. Normal controller validators are re-run unchanged.
    """
    from .live_scoped_reader import parse_scoped_invocation_candidate, validate_scoped_invocation_acceptance
    from .live_scoped_reader import LiveScopedReaderError
    from .invocation_control import SchemaViolationError, EvidenceFailureError
    from .reader import ReaderError
    from .scoped_reader import ScopedReaderError
    from .composite_scope import CompositeScopeError
    from .cell_selection import CellSelectionError
    try:
        parse_scoped_invocation_candidate(response_body=response, execution_id=execution_id, context=acceptance)
        draft = validate_scoped_invocation_acceptance(response_body=response, execution_id=execution_id, context=acceptance)
        return {'status': 'ACCEPTED', 'error_class': '',
                'candidate': draft['candidate_record'], 'evidence': draft['evidence_record']}
    except (SchemaViolationError, EvidenceFailureError) as error:
        cause = error.__cause__
        known = isinstance(cause, (ReaderError, UnicodeDecodeError, CellSelectionError))
        known = known or (isinstance(cause, ScopedReaderError) and str(cause).startswith((
            'SCOPED_CERTIFIED_TARGET_MISMATCH:', 'SCOPED_REFERENCE_RECONCILIATION_FAILED:',
            'MODEL_SCOPE_RESPONSIBILITY_MISMATCH:')))
        known = known or (isinstance(cause, CompositeScopeError) and str(cause) in {
            'Native table scope conflicts with source-bound narrative',
            'Combined source/table scope differs from the owner-required scope',
            'Source-bound scope remains incomplete'})
        known = known or (isinstance(cause, LiveScopedReaderError)
                           and str(cause) == 'Native scoped Evidence did not certify the response')
        if not known:
            raise ValueError('Diagnostic rejection is not proven to be response content: ' + str(cause)) from error
        return {'status': 'REJECTED_CONTENT',
            'error_class': 'SCHEMA_VIOLATION' if isinstance(error, SchemaViolationError) else 'EVIDENCE_FAILURE',
            'reason': str(cause)}


def _assess(context, plan, entry, record, payloads):
    from .live_scoped_reader import build_scoped_invocation_acceptance_context, replay_scoped_attempt
    from .ai_adapter import _qualification_usage_error, approved_scoped_transport_policy
    from .invocation_control import capture_successor_execution_bundle
    context._check()
    request = context._requests[entry['fixture_id']]
    acceptance = build_scoped_invocation_acceptance_context(request=request, execution_context=context)
    execution = record['execution_receipt']
    # Read and validate the actual WB-3 archive/ledger/journal, not just copies
    # embedded in the diagnostic JSON. An incomplete archive cannot continue.
    bundle = capture_successor_execution_bundle(repo_root=context._root,
        workspace_dir=_entry_root(context, plan, entry), plan=record['invocation_plan'],
        execution_receipt=execution, authority=request._session._invocation_authority)
    if bundle != record['terminal_bundle']:
        raise ValueError('Diagnostic WB-3 durable terminal differs from its saved capture')
    rebuilt = replay_scoped_attempt(repo_root=context._root, request_record=record['request_identity'],
        payloads=payloads, invocation_plan=record['invocation_plan'], execution_receipt=execution,
        acceptance_receipt=record['acceptance_receipt'], authorization_binding=record['authorization_binding'],
        terminal_bundle=bundle, acceptance_context=acceptance, execution_context=context)
    if rebuilt['native_attempt_record'] != record['attempt_record']:
        raise ValueError('Diagnostic native Attempt differs from independent replay')
    raw, assistant = payloads.get('raw_response'), payloads.get('assistant_output')
    attempts = execution['attempts']
    base = {'execution_status': execution['status'], 'counters': execution['counters'],
        'usage': attempts[0]['usage'] if len(attempts) == 1 else None,
        'qualification_credit': 'NONE', 'publication_credit': 'NONE'}
    if (raw is None or assistant is None or len(attempts) != 1
            or attempts[0]['status_code'] != 200
            or bundle['wire_journal'].get('error_class')
            or _qualification_usage_error(raw_response_bytes=raw,
                policy={'actual_prompt_tokens_max':200000,'terminal_error_class':'CONTEXT_LIMIT'})):
        return {**base, 'status': 'STOP', 'reason': 'HTTP/transport/usage/unknown outcome prevents independent sample continuation'}
    verdict = _check_response(acceptance, assistant, execution['execution_id'])
    context._check()
    if execution['status'] == 'SUCCEEDED' and verdict['status'] == 'ACCEPTED':
        return {**base, 'status': 'ACCEPTED', 'response_validation': verdict}
    if (execution['status'] == 'FAILED_TERMINAL' and verdict['status'] == 'REJECTED_CONTENT'
            and attempts[0]['error_class'] == verdict['error_class']):
        return {**base, 'status': 'CONTENT_FAILED', 'response_validation': verdict}
    return {**base, 'status': 'STOP', 'reason': 'Controller outcome differs from independent content validation; possible persistence/internal failure',
            'response_validation': verdict}


def _record_payloads(root, attempt):
    from .invocation_control import _exclusive_write_bytes, _exclusive_write_json
    payloads = {}
    for key, attribute in (('request_body','request_body_bytes'), ('reader_payload','reader_payload_bytes'),
            ('task_contract','task_contract_bytes'), ('output_schema','output_schema_bytes'),
            ('assistant_output','assistant_output_bytes'), ('raw_response','raw_response_bytes')):
        data = getattr(attempt.payloads, attribute)
        if data is not None:
            _exclusive_write_bytes(path=root / 'payloads' / (key + '.bin'), content=data)
            payloads[key] = data
    record = {key: getattr(attempt, key) for key in ('attempt_record','request_identity','invocation_plan',
        'execution_receipt','terminal_bundle','acceptance_receipt','authorization_binding')}
    record['payload_fields'] = sorted(payloads)
    _exclusive_write_json(path=root / 'diagnostic_attempt.json', value=record)
    return record, payloads


def validated_terminal(context, plan, entry):
    root = _entry_root(context, plan, entry)
    terminal = strict_json_file(path=root / 'diagnostic_terminal.json')
    if (terminal.get('terminal_id') != content_hash(value={k:v for k,v in terminal.items() if k != 'terminal_id'})
            or terminal.get('pending_plan_id') != plan['pending_plan_id']
            or terminal.get('entry_id') != entry['entry_id']
            or terminal.get('purpose') != PURPOSE or terminal.get('files') != _tree(root)):
        raise ValueError('Diagnostic terminal identity or sealed file set differs')
    cached = context._terminal_pins.get(('diagnostic', entry['entry_id']))
    if cached == terminal['terminal_id']:
        return terminal
    record = strict_json_file(path=root / 'diagnostic_attempt.json')
    payloads = _read_payloads(root, record['payload_fields'])
    result = _assess(context, plan, entry, record, payloads)
    if result != terminal['result']:
        raise ValueError('Diagnostic terminal differs from fresh native validation')
    context._terminal_pins[('diagnostic', entry['entry_id'])] = terminal['terminal_id']
    return terminal


def validate_diagnostic_prefix(*, context, plan, entry_id, for_socket=False):
    if not is_diagnostic(plan) or context._session._development is None:
        raise ValueError('Diagnostic prefix requires its separate plan purpose')
    context._check()
    matches = [e for e in plan['entries'] if e['entry_id'] == entry_id]
    if len(matches) != 1:
        raise ValueError('Diagnostic entry is absent or ambiguous')
    current = matches[0]
    parent = _entry_root(context, plan, current).parent
    start = strict_json_file(path=parent.parent / 'execution_started' / 'owner.json')
    if start['pending_plan_id'] != plan['pending_plan_id']:
        raise ValueError('Diagnostic execution owner differs')
    expected = {e['entry_id'][7:] for e in plan['entries']}
    if parent.exists() and any(p.name not in expected or p.is_symlink() or not p.is_dir() for p in parent.iterdir()):
        raise ValueError('Unknown diagnostic entry namespace')
    for entry in plan['entries']:
        path = _entry_root(context, plan, entry)
        if entry['ordinal'] < current['ordinal']:
            terminal = validated_terminal(context, plan, entry)
            if terminal['result']['status'] not in {'ACCEPTED', 'CONTENT_FAILED'}:
                raise ValueError('Previous diagnostic integrity failure stops later samples')
        elif entry['ordinal'] > current['ordinal'] and path.exists() and any(path.iterdir()):
            raise ValueError('Later diagnostic sample started out of order')
    if for_socket:
        path = _entry_root(context, plan, current)
        if (path / 'diagnostic_terminal.json').exists() or list((path/'invocation_control/executions').glob('*.json')):
            raise ValueError('Diagnostic entry is already terminal; another socket is forbidden')
        if len(list((path/'invocation_control/egress').rglob('*.json'))) != 1:
            raise ValueError('Diagnostic socket requires its sole reservation-owned marker')


def execute_diagnostic(*, context, plan, owner=None, recorded_transports=None):
    from .r4_live_authority import validate_r4_execution_plan, authorize_r4_live_entry, authorize_r4_recorded_test_entry
    from .live_scoped_reader import build_scoped_invocation_acceptance_context
    from .ai_adapter import build_scoped_qualification_transport_adapter, run_scoped_ai_attempt
    from .invocation_control import _exclusive_write_json
    if not is_diagnostic(plan):
        raise ValueError('A formal qualification plan cannot execute as a diagnostic')
    validate_r4_execution_plan(plan=plan, context=context, expected_plan_id=plan['pending_plan_id'], mode=plan['execution_mode'])
    if plan['execution_mode'] == 'LIVE' and (owner is None or recorded_transports is not None):
        raise ValueError('Diagnostic live execution requires owner preflight and forbids recorded transport')
    if plan['execution_mode'] == 'RECORDED_TEST' and (owner is not None or not isinstance(recorded_transports, dict)
            or set(recorded_transports) != {e['entry_id'] for e in plan['entries']}):
        raise ValueError('Recorded diagnostic transport exact set differs')
    if plan['execution_mode'] == 'LIVE':
        import os
        from .ai_adapter import approved_scoped_transport_policy, api_key_environment_name, api_key_required_error_code
        policy = approved_scoped_transport_policy(requirement=context._session._requirement)
        if not os.environ.get(api_key_environment_name(policy=policy), '').strip():
            raise ValueError(api_key_required_error_code(policy=policy))
    root = _entry_root(context, plan, plan['entries'][0]).parent.parent
    root.mkdir(parents=True, exist_ok=True)
    # Atomic batch start exclusion, retained forever. No cleanup/retry route.
    (root / 'execution_started').mkdir()
    _exclusive_write_json(path=root / 'execution_started/owner.json', value={
        'pending_plan_id':plan['pending_plan_id'], 'purpose':PURPOSE})
    terminals = []
    for entry in plan['entries']:
        try:
            validate_diagnostic_prefix(context=context, plan=plan, entry_id=entry['entry_id'])
            authorization = (authorize_r4_live_entry(context=context, plan=plan, entry_id=entry['entry_id'], owner_receipt=owner)
                if plan['execution_mode'] == 'LIVE' else authorize_r4_recorded_test_entry(context=context, plan=plan, entry_id=entry['entry_id']))
            request = context._requests[entry['fixture_id']]
            acceptance = build_scoped_invocation_acceptance_context(request=request, execution_context=context)
            adapter = build_scoped_qualification_transport_adapter(authorization=authorization,
                recorded_transport=None if recorded_transports is None else recorded_transports[entry['entry_id']])
            attempt = run_scoped_ai_attempt(adapter=adapter, prepared_request=request, acceptance_context=acceptance)
            path = _entry_root(context, plan, entry)
            record, payloads = _record_payloads(path, attempt)
            result = _assess(context, plan, entry, record, payloads)
            body = {'purpose':PURPOSE, 'pending_plan_id':plan['pending_plan_id'], 'entry_id':entry['entry_id'],
                'fixture_id':entry['fixture_id'], 'ordinal':entry['ordinal'], 'result':result, 'files':_tree(path)}
            terminal = {**body, 'terminal_id':content_hash(value=body)}
            _exclusive_write_json(path=path/'diagnostic_terminal.json', value=terminal)
            terminals.append(validated_terminal(context, plan, entry))
            print(json.dumps({'ordinal':entry['ordinal'],'fixture_id':entry['fixture_id'],
                'status':result['status'],'usage':result['usage'],'counters':result['counters']},ensure_ascii=False),flush=True)
            if result['status'] == 'STOP':
                break
        except Exception as error:
            # WB-3 already retains every occurred egress/response/terminal. A
            # broken postflight is never converted into sample-content failure.
            _exclusive_write_json(path=root/'diagnostic_stop.json', value={
                'pending_plan_id':plan['pending_plan_id'], 'entry_id':entry['entry_id'],
                'status':'STOP', 'error_type':type(error).__name__, 'reason':str(error),
                'qualification_credit':'NONE','publication_credit':'NONE'})
            raise
    result = diagnostic_summary(plan, terminals)
    _exclusive_write_json(path=root/'diagnostic_summary.json', value=result)
    return result


def diagnostic_summary(plan, terminals):
    counters = {k:sum(t['result']['counters'][k] for t in terminals) for k in
        ('real_model_provider_egress_count','paid_model_provider_call_count','mock_transport_invocation_count')}
    return {'record_type':'R4_DEVELOPMENT_DIAGNOSTIC_SUMMARY','pending_plan_id':plan['pending_plan_id'],
        'status':'COMPLETED_DIAGNOSTIC' if len(terminals)==9 and all(t['result']['status'] != 'STOP' for t in terminals) else 'STOPPED',
        'observed_samples':len(terminals),'unstarted_samples':9-len(terminals),'counters':counters,
        'qualification_credit':'NONE','publication_credit':'NONE','sec_calls':0,
        'entries':[{'ordinal':t['ordinal'],'fixture_id':t['fixture_id'],'terminal_id':t['terminal_id'],
                    **t['result']} for t in terminals]}


def replay_diagnostic(context, plan):
    from .r4_live_authority import validate_r4_execution_plan
    if not is_diagnostic(plan):
        raise ValueError('Diagnostic replay requires its distinct plan purpose')
    validate_r4_execution_plan(plan=plan, context=context, expected_plan_id=plan['pending_plan_id'], mode=plan['execution_mode'])
    context._check()
    terminals = []
    for entry in plan['entries']:
        path = _entry_root(context, plan, entry)
        if not path.exists():
            break
        terminals.append(validated_terminal(context, plan, entry))
        if terminals[-1]['result']['status'] == 'STOP':
            break
    summary = diagnostic_summary(plan, terminals)
    root = _entry_root(context, plan, plan['entries'][0]).parent.parent
    saved = root / 'diagnostic_summary.json'
    if saved.exists() and strict_json_file(path=saved) != summary:
        raise ValueError('Saved diagnostic aggregate differs from independent replay')
    context._check()
    return summary
