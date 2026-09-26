"""One bounded source refresh followed by ordinary per-metric updates.

The existing acquisition session owns transport, provenance and the cumulative
ledger. The existing update cycle owns candidate history. No resident loop or
publication action is introduced here.
"""
from pathlib import Path

from sec_http import parse_request_log_rows, validate_request_log_manifest
from git_workspace import first_symlink_in_path
from .canonical import content_hash, sha256_file, strict_json_file
from .continuous_call_policy import need
from .continuous_sec_acquisition import SecAcquisitionSession, initialize_source_inputs
from .normal_source_authority import ROOT
from .normal_source_requirements import discover_saved_source_requirements, source_dependency_satisfied
from .normal_annual_input import _registry_rows
from .ordinary_update_cycle import run_company
from .normal_run_v3 import update_metric_ids
from .sources import resolve_repository_file

WIRING_PATH = 'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json'


def _check_session(session, *, c04_successor=False):
    need(isinstance(session, SecAcquisitionSession), 'ORDINARY_REFRESH_NATIVE_SESSION_REQUIRED')
    need(session.data_root == session.ledger.root / 'source-inputs', 'ORDINARY_REFRESH_SESSION_SOURCE_ROOT_CHANGED')
    if not session.ledger.live:
        session._check()
        return
    relative = Path(__file__).relative_to(ROOT).as_posix()
    need(session.requirement['execution_authority']['files'].get(relative) == {
        'sha256': sha256_file(path=Path(__file__)), 'size': Path(__file__).stat().st_size},
        'ORDINARY_REFRESH_IMPLEMENTATION_NOT_BOUND')
    if c04_successor:
        from . import c04_update_cycle
        path = Path(c04_update_cycle.__file__)
        name = path.relative_to(ROOT).as_posix()
        need(session.requirement['execution_authority']['files'].get(name) == {
            'sha256': sha256_file(path=path), 'size': path.stat().st_size},
            'ORDINARY_REFRESH_C04_SUCCESSOR_NOT_BOUND')
    session._check()
    evidence = strict_json_file(path=resolve_repository_file(repo_root=ROOT, repo_relative_path=WIRING_PATH))
    need(evidence['record_type'] == 'ORDINARY_REFRESH_OFFLINE_WIRING'
         and evidence['execution_authority_hash'] == content_hash(value=session.requirement['execution_authority'])
         and evidence['calls'] == [0, 0, 0]
         and evidence['normal_update_lifecycle_verified'] is True
         and evidence['failed_url_not_retried_verified'] is True
         and (not c04_successor or
              evidence.get('c04_successor_recorded_route_verified') is True and
              evidence.get('c04_controller_sha256') ==
              sha256_file(path=Path(__file__).with_name('c04_update_cycle.py'))),
         'ORDINARY_REFRESH_OFFLINE_WIRING_CHANGED')
    for path, digest in evidence['evidence'].items():
        need(sha256_file(path=resolve_repository_file(repo_root=ROOT, repo_relative_path=path)) == digest,
             'ORDINARY_REFRESH_OFFLINE_EVIDENCE_CHANGED')


def _failed_urls(data_root):
    path = data_root / 'evidence/requests_log.csv'
    validate_request_log_manifest(log_path=path)
    latest = {}
    for row in parse_request_log_rows(text=path.read_text()):
        latest[row['source_url']] = row
    return {url for url, row in latest.items() if row['status_code'] != '200' or row['error']}


def _pending(discovery, attempted, failed):
    return [r for r in discovery['requirements'] if r['source_url'] not in attempted | failed
            and (r['refresh_for_new_discovery'] or (r['saved_status'] == 'MISSING_SAVED_SOURCE'
                and not source_dependency_satisfied(r)))
            and r['saved_status'] != 'SAVED_SOURCE_BLOCKED']


def _call_accounting(captures, before, after, live, capture_error):
    delta = [end - start for start, end in zip(before, after)]
    need(len(delta) == 3 and all(value >= 0 for value in delta), 'ORDINARY_REFRESH_LEDGER_COUNT_REGRESSED')
    own_sec = sum(item['result']['calls'][2] for item in captures)
    unknown = live and capture_error and delta[2] > own_sec
    return {'status': 'UNKNOWN' if unknown else 'KNOWN', 'cumulative_ledger_delta': delta,
        'calls': {'provider': 0, 'paid': 0, 'sec': None if unknown else own_sec if live else 0}}


def refresh_and_process(*, session, state_root, company_ids=None, metric_ids=None, max_sec_requests, max_provider_requests=0, recorded_native_wire_factory=None, c04_successor=False):
    """Discover inputs automatically, capture each URL at most once, then update."""
    need(type(max_sec_requests) is int and 0 <= max_sec_requests <= 80, 'ORDINARY_REFRESH_FINITE_REQUEST_LIMIT_REQUIRED')
    need(type(max_provider_requests) is int and 0<=max_provider_requests<=240,
         'ORDINARY_REFRESH_FINITE_PROVIDER_LIMIT_REQUIRED')
    need(type(c04_successor) is bool, 'ORDINARY_REFRESH_C04_ROUTE_FLAG_INVALID')
    need(isinstance(session, SecAcquisitionSession), 'ORDINARY_REFRESH_NATIVE_SESSION_REQUIRED')
    need(not session.ledger.live or recorded_native_wire_factory is None,'ORDINARY_REFRESH_RECORDED_PROVIDER_WIRE_FORBIDDEN')
    companies = [row['company_id'] for row in _registry_rows(repo_root=ROOT)]
    selected = companies if company_ids is None else company_ids
    strategy = strict_json_file(path=ROOT / 'config/source_strategy_registry.json')
    metrics = sorted(strategy['metrics']) if metric_ids is None else metric_ids
    need(type(selected) is list and selected and len(selected) == len(set(selected))
         and set(selected) <= set(companies), 'ORDINARY_REFRESH_COMPANY_SCOPE_INVALID')
    need(type(metrics) is list and metrics and len(metrics) == len(set(metrics))
         and set(metrics) <= set(strategy['metrics']), 'ORDINARY_REFRESH_METRIC_SCOPE_INVALID')
    need(not c04_successor or 'C04' in metrics,
         'ORDINARY_REFRESH_C04_ROUTE_REQUIRES_C04')
    state_root = Path(state_root)
    need(state_root.is_absolute() and first_symlink_in_path(path=state_root) is None,
         'ORDINARY_REFRESH_ABSOLUTE_UNALIASED_STATE_REQUIRED')
    state_root = state_root.resolve()
    need(state_root != ROOT and state_root not in ROOT.parents and ROOT not in state_root.parents
         and state_root != session.data_root and state_root not in session.data_root.parents
         and session.data_root not in state_root.parents
         and not any((p / 'outputs/active_publication.json').exists() for p in (state_root, *state_root.parents)),
         'ORDINARY_REFRESH_STATE_ROOT_UNSAFE')
    _check_session(session, c04_successor=c04_successor)
    with session.ledger.locked():
        initialize_source_inputs(root=session.data_root, requirement=session.requirement,
                                 c04_source_only=c04_successor)
        before = session.ledger.snapshot()['counts']
    failed = _failed_urls(session.data_root)
    attempted, captures, discoveries, errors = set(), [], {}, {}
    capture_error = False
    # One request per company per pass keeps an unrelated company progressing
    # when another company's metadata or original source is unavailable.
    for _ in range(max_sec_requests):
        progressed = False
        for company in selected:
            try:
                discovery = discover_saved_source_requirements(repo_root=session.data_root, company_id=company)
                discoveries[company] = discovery
                pending = _pending(discovery, attempted, failed)
            except Exception as error:
                errors.setdefault(company, []).append({'stage': 'DISCOVERY', 'error_type': type(error).__name__, 'reason': str(error)})
                continue
            if not pending:
                continue
            if len(captures) >= max_sec_requests:
                break
            request = pending[0]; url = request['source_url']; attempted.add(url)
            try:
                result = session.capture(company_id=company, url=url,
                    refresh_metadata=request['refresh_for_new_discovery'],
                    **({'source_only_c04': True} if c04_successor else {}))
                captures.append({'company_id': company, 'source_url': url, 'result': result})
                if result['status'] not in {'SUCCEEDED', 'EXISTING_VERIFIED_SOURCE_REUSED'}:
                    failed.add(url)
                progressed = True
            except Exception as error:
                capture_error = True
                errors.setdefault(company, []).append({'stage': 'CAPTURE', 'error_type': type(error).__name__, 'reason': str(error)})
                # An interrupted or unaccounted capture must stop new requests;
                # the original ledger decides which channel is still usable.
                break
        else:
            if progressed and len(captures) < max_sec_requests:
                continue
        break
    with session.ledger.locked():
        after = session.ledger.snapshot()['counts']
    accounting = _call_accounting(captures, before, after, session.ledger.live, capture_error)
    supported = set(update_metric_ids())
    results = [];native_attempts=[];provider_attempts=0;provider_stopped=False
    for company in selected:
        try:
            discovery = discover_saved_source_requirements(repo_root=session.data_root, company_id=company)
            discoveries[company] = discovery
            pending = _pending(discovery, attempted, failed)
            failed_for_company = sorted({r['source_url'] for r in discovery['requirements']} & failed)
            complete = (not pending and not failed_for_company and not errors.get(company)
                        and discovery['status'] == 'SAVED_SOURCE_DEPENDENCIES_AVAILABLE')
            source_check = {'status': 'REFRESH_CHECK_COMPLETED' if complete else 'REFRESH_INCOMPLETE',
                'requirements_id': discovery['requirements_id'], 'source_discovery_status': discovery['status'],
                'deferred_source_urls': [r['source_url'] for r in pending], 'failed_source_urls_not_retried': failed_for_company,
                'limitations': discovery['limitations'], 'all_39_metric_source_acceptance_proven': False}
        except Exception as error:
            complete = False
            source_check = {'status': 'REFRESH_CHECK_FAILED', 'error_type': type(error).__name__, 'reason': str(error)}
        requested = [metric for metric in metrics if metric in supported]
        if max_provider_requests and complete:
            from .capacity_update_input import ensure_native_update
            from .capacity_utilization_source import policy as capacity_policy
            for metric in requested:
                if metric not in {'B13','D04'}:continue
                if metric=='B13' and company not in capacity_policy()[1]['applicable_company_ids']:continue
                if provider_stopped or provider_attempts>=max_provider_requests:break
                try:
                    native=ensure_native_update(source_root=session.data_root,company_id=company,metric_id=metric,
                        ledger=session.ledger,max_provider_requests=max_provider_requests-provider_attempts,
                        recorded_wire_factory=recorded_native_wire_factory)
                    provider_attempts+=native['attempted_executions'];provider_stopped |= native['stop_provider']
                except Exception as error:
                    native={'company_id':company,'metric_id':metric,'status':'NATIVE_PREPARATION_FAILED',
                            'attempted_executions':0,'counts':[0,0,0],'call_accounting':'KNOWN',
                            'error_type':type(error).__name__,'reason':str(error)}
                native_attempts.append(native)
        ordinary = [metric for metric in requested if not (c04_successor and metric == 'C04')]
        try:
            updates = run_company(state_root=Path(state_root) / company, source_root=session.data_root,
                company_id=company, metric_ids=ordinary,
                native_assessment_mode='LIVE' if session.ledger.live else 'RECORDED_TEST_ONLY',native_assessment_ledger=session.ledger) if ordinary else {'metrics': [], 'status': 'UPDATES_INCOMPLETE'}
        except Exception as error:
            updates = {'status': 'UPDATE_BLOCKED', 'metrics': [], 'error_type': type(error).__name__, 'reason': str(error)}
        if c04_successor and 'C04' in requested:
            if ordinary and updates['status'] == 'UPDATE_BLOCKED':
                updates['metrics'] = [{'metric_id': metric, 'status': 'UPDATE_BLOCKED',
                    'error_type': updates['error_type'], 'reason': updates['reason'],
                    'last_verified_candidate': None, 'production_authorized': False}
                    for metric in ordinary]
            from .c04_update_cycle import run_company as run_c04_company
            try:
                c04 = run_c04_company(state_root=Path(state_root) / company / 'metrics/C04-registration-v3',
                    source_root=session.data_root, company_id=company)
                updates['metrics'].extend(c04['metrics'])
            except Exception as error:
                updates['metrics'].append({'metric_id': 'C04', 'status': 'UPDATE_BLOCKED',
                    'error_type': type(error).__name__, 'reason': str(error),
                    'last_verified_candidate': None, 'production_authorized': False})
            ready = sum(row['status'] in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'}
                        for row in updates['metrics'])
            updates['status'] = ('UPDATES_READY' if ready == len(updates['metrics']) else
                'UPDATES_PARTIAL' if ready else 'UPDATES_INCOMPLETE')
        unsupported = sorted(set(metrics) - supported)
        updates['metrics'].extend({'metric_id': metric, 'status': 'UPDATE_NOT_IMPLEMENTED',
            'reason': 'ORDINARY_UPDATE_ROUTE_NOT_WIRED', 'last_verified_candidate': None,
            'production_authorized': False} for metric in unsupported)
        if unsupported:
            updates['status'] = 'UPDATES_PARTIAL' if requested else 'UPDATES_INCOMPLETE'
        results.append({'company_id': company,
            'status': 'REFRESHED_UPDATES_READY' if complete and updates['status'] == 'UPDATES_READY' else 'REFRESHED_UPDATES_INCOMPLETE',
            'source_refresh': source_check, 'updates': updates, 'acquisition_errors': errors.get(company, [])})
    if max_provider_requests:
        with session.ledger.locked():after=session.ledger.snapshot()['counts']
        accounting['cumulative_ledger_delta']=[b-a for a,b in zip(before,after)]
        unknown=any(r['call_accounting']=='UNKNOWN' for r in native_attempts)
        accounting['status']='UNKNOWN' if unknown else accounting['status']
        for i,key in enumerate(('provider','paid')):
            accounting['calls'][key]=(None if unknown else sum(r['counts'][i] for r in native_attempts)) if session.ledger.live else 0
    return {'record_type': 'ORDINARY_BOUNDED_REFRESH_AND_UPDATE', 'schema_version': 1,
        **({'max_provider_requests':max_provider_requests,'native_preparations':native_attempts} if max_provider_requests else {}),
        'status': 'CALL_ACCOUNTING_UNRESOLVED' if accounting['status'] == 'UNKNOWN' else
                  'UPDATES_READY' if all(r['status'] == 'REFRESHED_UPDATES_READY' for r in results) else 'UPDATES_INCOMPLETE',
        'execution_mode': 'LIVE' if session.ledger.live else 'RECORDED_TEST_ONLY',
        'max_sec_requests': max_sec_requests, 'captures': captures, 'companies': results,
        'ledger_counts_before': before, 'ledger_counts_after': after,
        'calls': accounting['calls'], 'call_accounting': accounting['status'],
        'cumulative_ledger_delta': accounting['cumulative_ledger_delta'],
        'source_discovery_scope': 'EXISTING_COMPLETE_39_METRIC_DEPENDENCY_DISCOVERY',
        'ordinary_update_metric_routes_not_wired': sorted(set(strategy['metrics']) - supported),
        'all390_acceptance': False, 'production_authorized': False, 'resident_schedule_enabled': False}
