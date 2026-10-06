"""Thin company references derived from existing update journals and Runs.

This is a query, not a publication/selection authority. Each native controller
still owns its successful pointer. Execution observations describe source
checks; they cannot manufacture a candidate or clear a registered defect.
"""
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from .canonical import content_hash, sha256_bytes, strict_json_file, strict_json_loads
from .company_handoff import _atomic_json
from .company_source_authority import need


def recover_for_read(root, runtime_roots=()):
    """Check source rules in the explicitly supplied fixed consumer tree.

The selected tree supplies rule bytes only; native code is replayed separately
in its own process. This permits an ordinary reader to export historical Runs
without installing the historical registration patch in the ordinary tree.
"""
    from . import company_handoff as handoff
    from .company_source_authority import EXPORT_PATH
    pointer = root/'current_source.json'
    if not pointer.is_file(): return handoff.recover_import(root)
    current = strict_json_file(path=pointer)
    import re
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', current['checkpoint_id']) is not None,
         'COMPANY_RESULT_SOURCE_POINTER_CHANGED')
    package = root/'versions'/current['checkpoint_id'][7:]
    handoff.external(package)
    admission = strict_json_file(path=package/EXPORT_PATH)
    identity = admission.get('rule_requirement_id', 'issue_28_v13')
    need(identity in {'issue_28_v13','issue_47_v1'}, 'COMPANY_RESULT_SOURCE_RULE_ID_INVALID')
    original = handoff.ROOT
    candidates = [original, *map(Path, runtime_roots)]
    try:
        for program in candidates:
            if not (program/'requirements'/identity/'baseline_manifest.json').is_file(): continue
            from git_workspace import first_symlink_in_path
            need(program.is_absolute() and first_symlink_in_path(path=program) is None,
                 'COMPANY_RESULT_SOURCE_RUNTIME_ALIAS')
            handoff.ROOT = program
            if handoff.rule_bindings(identity) == admission['rules']:
                return handoff.recover_import(root)
        raise ValueError('COMPANY_RESULT_EXACT_SOURCE_RULE_RUNTIME_REQUIRED')
    finally:
        handoff.ROOT = original


def save_execution(*, root, report):
    previous = root/'company-results.json'
    directory = root/'company-executions'
    directory.mkdir(exist_ok=True)
    # Migrate the old single-request report without assigning it new success.
    if previous.is_file():
        old = strict_json_file(path=previous)
        if old.get('record_type') == 'COMPANY_COMPUTATION_REFERENCES_V1':
            _atomic_json(directory/'inherited-report.json', old)
    identity = uuid4().hex
    report = {**report, 'execution_id': identity, 'recorded_at': datetime.now(timezone.utc).isoformat()}
    _atomic_json(directory/(identity+'.json'), report)
    _atomic_json(root/'latest-execution.json', report)
    return report


def _manifest(root, work, metric, company):
    need(root in work.parents and not any(p.is_symlink() for p in [work, *work.parents]),
         'COMPANY_RESULT_CANDIDATE_PATH_CHANGED')
    need(not any(p.is_symlink() for p in work.rglob('*')), 'COMPANY_RESULT_NATIVE_INPUT_ALIAS')
    paths = list((work/'runs').glob('*/manifest.json'))
    need(len(paths) == 1 and paths[0].parent.name == metric,
         'COMPANY_RESULT_NATIVE_RUN_SET_CHANGED')
    manifest = strict_json_file(path=paths[0])
    need(manifest['company_id'] == company, 'COMPANY_RESULT_NATIVE_RUN_WRONG_COMPANY')
    return manifest


def _ordinary_candidates(root, pointer, company):
    from .ordinary_update_cycle import _read
    target = pointer.parent
    configuration = _read(target/'configuration.json')
    need(configuration['company_id'] == company, 'COMPANY_RESULT_JOURNAL_WRONG_COMPANY')
    state = strict_json_file(path=pointer)
    need(state['configuration_id'] == configuration['record_id'], 'COMPANY_RESULT_JOURNAL_CONFIGURATION_CHANGED')
    identity = state['latest_attempt']; seen = set(); periods = set(); latest = None
    successful_seen = state['successful_attempt'] is None; newest_success = None
    while identity:
        need(identity not in seen and len(identity) == 32 and all(c in '0123456789abcdef' for c in identity),
             'COMPANY_RESULT_JOURNAL_CHAIN_CHANGED')
        seen.add(identity)
        work = target/'attempts'/identity
        intent = _read(work/'intent.json'); terminal = _read(work/'terminal.json')
        need(intent['attempt_id'] == terminal['attempt_id'] == identity
             and terminal['intent_id'] == intent['record_id']
             and terminal['configuration_id'] == intent['configuration_id'] == configuration['record_id'],
             'COMPANY_RESULT_JOURNAL_BINDING_CHANGED')
        if latest is None:
            latest = terminal
        if identity == state['successful_attempt']:
            need(terminal['status'] == 'CANDIDATE_READY', 'COMPANY_RESULT_SUCCESSFUL_POINTER_CHANGED')
            successful_seen = True
        if terminal['status'] == 'CANDIDATE_READY':
            if newest_success is None:
                newest_success = identity
                need(newest_success == state['successful_attempt'], 'COMPANY_RESULT_SUCCESSFUL_POINTER_CHANGED')
            for metric in configuration['metric_ids']:
                manifest = _manifest(root, work, metric, company)
                key = (metric, manifest['target_period']['period_end'])
                if key not in periods:
                    periods.add(key)
                    yield {'metric_id': metric, 'attempt_id': identity, 'rows_root': str(work/'rows'),
                           'manifest': manifest, 'journal': str(target.relative_to(root)),
                           'result_id': terminal['metrics'][metric]['result_id'],
                           'source_credit': terminal['metrics'][metric].get('source_credit'),
                           'journal_latest_status': latest['status'],
                           'journal_latest_error': latest.get('error'), 'row_layout': 'ordinary'}
        identity = intent['previous_attempt']
    need(successful_seen, 'COMPANY_RESULT_SUCCESSFUL_POINTER_DISCONNECTED')


def _historical_candidate(root, pointer, company):
    state = strict_json_file(path=pointer); candidate = state['candidate']
    need(state['attempt_id'] == candidate['attempt_id'], 'COMPANY_RESULT_HISTORY_POINTER_CHANGED')
    work = Path(candidate['rows_root']).parent
    metric = 'D04' if 'processing' in pointer.relative_to(root).parts else pointer.parent.name
    manifest = _manifest(root, work, metric, company)
    need(work == pointer.parent/'attempts'/state['attempt_id'], 'COMPANY_RESULT_HISTORY_PATH_CHANGED')
    return {'metric_id': metric, 'attempt_id': state['attempt_id'], 'rows_root': candidate['rows_root'],
            'manifest': manifest, 'journal': str(pointer.parent.relative_to(root)),
            'result_id': candidate.get('receipt', {}).get('public_row', {}).get('result_id'), 'row_layout': 'historical',
            'journal_latest_status': 'CANDIDATE_READY'}


def _measurement_period(entry, manifest):
    """Read the result's window, without inferring it from the Run coordinate.

    This is a manifest hash read, not native replay or content acceptance.
    Older records without a sealed records hash leave the window unavailable.
    """
    records = Path(entry['rows_root']).parent/'runs'/entry['metric_id']/'records.jsonl'
    expected = manifest.get('records_file_hash')
    # Ordinary SUCCESSOR_RUN manifests retain the initial empty-stream hash;
    # their append-only records are authenticated by native replay instead.
    if not expected or (manifest.get('record_type') == 'SUCCESSOR_RUN'
                        and expected == sha256_bytes(content=b'')):
        return {'measurement_period': None, 'measurement_period_status': 'NOT_AVAILABLE'}
    try:
        raw = records.read_bytes()
        need(sha256_bytes(content=raw) == expected, 'COMPANY_RESULT_RECORDS_CHANGED')
        found = [record for line in raw.decode('utf-8').splitlines()
                 if (record := strict_json_loads(text=line)).get('record_type') == 'METRIC_RESULT'
                 and record.get('metric_id') == entry['metric_id']
                 and record.get('result_id') == entry['result_id']]
        need(len(found) == 1, 'COMPANY_RESULT_MEASUREMENT_RECORD_AMBIGUOUS')
        return {'measurement_period': {k: found[0][k] for k in ('period_start', 'period_end')},
                'measurement_period_status': 'NATIVE_RECORD_HASH_VERIFIED_NOT_REPLAYED'}
    except Exception as error:
        return {'measurement_period': None, 'measurement_period_status': 'NATIVE_RECORD_INVALID',
                'measurement_period_reason': str(error)}


def _defects(entry, registry):
    matched = []
    for defect in registry.get('defects', []):
        if (defect.get('company_id'), defect.get('metric_id'), defect.get('period_end')) != (
                entry['company_id'], entry['metric_id'], entry['period']['period_end']):
            continue
        if defect.get('result_id'):
            if defect['result_id'] != entry.get('result_id'):
                continue
        else:
            released = defect.get('released', [])
            if isinstance(released, dict): released = [released]
            if any(r.get('result_id') == entry.get('result_id') and
                   r.get('requirement_closure_hash') == entry['requirement_closure_hash'] for r in released):
                continue
        other = defect.get('released', [])
        if isinstance(other, dict): other = [other]
        other = [r for r in other if r.get('result_id') == entry.get('result_id')
                 and r.get('requirement_closure_hash') != entry['requirement_closure_hash']]
        matched.append({'defect_id': defect['defect_id'],
            'reason': 'CURRENT_RUNTIME_RELEASE_REQUIRED' if other else 'REGISTERED_DEFECT_UNRELEASED',
            'releases_in_other_runtimes': other})
    return matched


def requested_period(report, outcome):
    return outcome.get('period_request', report.get('period_request')) or {}


def matches_period(request, period):
    """Issuer fiscal labels and archive dates keep their original meanings."""
    year = period['fiscal_year']
    return ((not request.get('report_end') or request['report_end'] == period['period_end'])
            and (not request.get('fiscal_year') or request['fiscal_year'] == year)
            and (not request.get('fiscal_year_start') or request['fiscal_year_start'] <= year)
            and (not request.get('fiscal_year_end') or year <= request['fiscal_year_end']))


def build_company_view(*, root, company_id, current, defect_registry=None):
    """Recover every metric/period from native records, even pre-V2 states."""
    reports = []
    legacy = root/'company-results.json'
    if legacy.is_file():
        value = strict_json_file(path=legacy)
        if value.get('record_type') == 'COMPANY_COMPUTATION_REFERENCES_V1': reports.append(value)
    for path in (root/'company-executions').glob('*.json'):
        reports.append(strict_json_file(path=path))
    reports.sort(key=lambda r: r.get('recorded_at', ''))
    for report in reports:
        need(report['company_id'] == company_id, 'COMPANY_RESULT_EXECUTION_WRONG_COMPANY')
    observations = {}; creations = {}; latest_requests = {}
    for report in reports:
        for metric in report['metrics']:
            latest_requests.setdefault(metric['metric_id'], []).append((report, metric))
            candidate = metric.get('last_verified_candidate')
            if candidate:
                key = (metric['metric_id'], candidate['rows_root'], candidate['attempt_id'])
                observations[key] = (report, metric)
                if metric['status'] == 'CANDIDATE_READY': creations.setdefault(key, report)
    entries = []
    for pointer in sorted((root/'updates').glob('**/current.json')):
        need(not pointer.is_symlink(), 'COMPANY_RESULT_JOURNAL_ALIAS')
        if (pointer.parent/'configuration.json').is_file():
            candidates = _ordinary_candidates(root, pointer, company_id)
        elif 'historical' in pointer.relative_to(root).parts:
            candidates = [_historical_candidate(root, pointer, company_id)]
        elif 'processing' in pointer.relative_to(root).parts:
            candidates = [_historical_candidate(root, pointer, company_id)]
        else:
            continue
        for candidate in candidates:
            manifest = candidate.pop('manifest')
            if 'processing' in pointer.relative_to(root).parts:
                processing_work = Path(candidate['rows_root']).parent
                receipt = strict_json_file(path=processing_work/'processing-receipt.json')
                original_source = strict_json_file(path=processing_work/'processing/processing-source.json')
                processing_metadata = strict_json_file(path=processing_work/'processing/processing.json')
                candidate.update(row_layout='processing', result_id=receipt['result_id'],
                                 saved_processing_mode=processing_metadata['mode'],
                                 source_credit=original_source['source_admission']['source_credit'],
                                 original_source_checkpoint_id=receipt.get('original_source_checkpoint_id'),
                                 current_source_equivalence_id=receipt.get('current_source_equivalence', {}).get('equivalence_id'),
                                 business_metric_completed=False)
            key = (candidate['metric_id'], candidate['rows_root'], candidate['attempt_id'])
            report, outcome = observations.get(key, ({}, {}))
            creation = creations.get(key, {})
            installed_checkpoint = Path(candidate['rows_root']).parent/'data/config/ordinary_source_checkpoint.json'
            bound_source_id = creation.get('source_checkpoint_id')
            if bound_source_id is None and installed_checkpoint.is_file():
                bound_source_id = strict_json_file(path=installed_checkpoint).get('checkpoint_id')
            saved = outcome.get('last_verified_candidate', {})
            same = report.get('source_checkpoint_id') == current['checkpoint_id']
            matches = saved.get('current_input_matches') if same else None
            # A later failed journal cannot be cleared by an older report.
            latest_status = candidate['journal_latest_status']
            if latest_status not in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'}:
                matches = False
            entry = {**candidate, 'company_id': company_id, 'period': manifest['target_period'],
                     'run_id': manifest['run_id'], 'run_status': manifest['status'],
                     'requirement_id': manifest['requirement_id'],
                     'requirement_closure_hash': manifest['requirement_closure_hash'],
                     'runtime_root': saved.get('runtime_root', report.get('runtime_root')),
                     'source_checkpoint_id': bound_source_id,
                     'last_checked_source_checkpoint_id': report.get('source_checkpoint_id'),
                     'current_source_checkpoint_id': current['checkpoint_id'],
                     'current_input_matches': matches,
                     'current_input_status': 'MATCHED' if matches is True else 'MISMATCH_OR_FAILED' if matches is False else 'NOT_RECHECKED',
                     'latest_attempt_status': latest_status if latest_status not in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'} else outcome.get('status', latest_status),
                     'latest_request_status': next((outcome.get('status') for request_report, outcome in
                         reversed(latest_requests.get(candidate['metric_id'], []))
                         if matches_period(requested_period(request_report, outcome), manifest['target_period'])), None),
                     'result_validity': 'NOT_ASSESSED', 'replay_status': 'NOT_REPLAYED'}
            latest_report = reports[-1] if reports else {}
            entry['requested_in_latest_execution'] = any(
                outcome['metric_id'] == candidate['metric_id'] and
                matches_period(requested_period(latest_report, outcome), entry['period'])
                for outcome in latest_report.get('metrics', []))
            entry['period_role'] = 'RUN_ARCHIVE_COORDINATE'
            entry.update(_measurement_period(entry, manifest))
            entry['defect_holds'] = _defects(entry, defect_registry or {})
            entry['confirmed_defects'] = [d['defect_id'] for d in entry['defect_holds']]
            if entry['defect_holds']:
                entry['result_validity'] = ('CURRENT_RUNTIME_RELEASE_REQUIRED'
                    if all(d['reason'] == 'CURRENT_RUNTIME_RELEASE_REQUIRED' for d in entry['defect_holds'])
                    else 'CONFIRMED_INVALID')
            entry['view_key'] = content_hash(value={k: entry[k] for k in ('journal', 'metric_id', 'period', 'run_id')})
            entries.append(entry)
    # Failed/pending requests with no native record are still visible.
    pending = {}
    for report in reports:
        for outcome in report['metrics']:
            if not outcome.get('last_verified_candidate'):
                period = requested_period(report, outcome)
                pending[(outcome['metric_id'], str(period))] = {
                    'metric_id': outcome['metric_id'], 'period_request': period,
                    'latest_attempt_status': outcome['status'], 'reason': outcome.get('reason'),
                    'source_checkpoint_id': report['source_checkpoint_id'], 'run_id': None,
                    'result_validity': 'NO_RESULT', 'current_input_matches': False}
    existing = list(entries)
    for value in pending.values():
        requested = value.get('period_request') or {}
        matched = any(e['metric_id'] == value['metric_id'] and
            (not requested.get('report_end') or e['period']['period_end'] == requested['report_end']) and
            (not requested.get('fiscal_year') or e['period']['fiscal_year'] == requested['fiscal_year']) for e in existing)
        if not matched: entries.append(value)
    return {'record_type': 'COMPANY_RESULT_VIEW_V2', 'company_id': company_id,
            'source_checkpoint_id': current['checkpoint_id'], 'metrics': entries,
            'latest_execution': reports[-1] if reports else None,
            'defect_registry_supplied': defect_registry is not None,
            'production_authorized': False, 'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0}}


def read_company_results(*, state_root, company_id, defects_file=None, runtime_roots=()):
    from .company_handoff import locked_company, recover_import
    with locked_company(state_root) as root:
        current = recover_for_read(root, runtime_roots)
        need(current and current['company_id'] == company_id, 'COMPANY_RESULT_VIEW_WRONG_COMPANY')
        registry = strict_json_file(path=Path(defects_file)) if defects_file else None
        legacy = root/'company-results.json'
        if legacy.is_file():
            old = strict_json_file(path=legacy)
            if old.get('record_type') == 'COMPANY_COMPUTATION_REFERENCES_V1':
                (root/'company-executions').mkdir(exist_ok=True)
                _atomic_json(root/'company-executions/inherited-report.json', old)
        view = build_company_view(root=root, company_id=company_id, current=current, defect_registry=registry)
        _atomic_json(root/'company-results.json', view)
        return view
