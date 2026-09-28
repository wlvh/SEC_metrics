"""Explicit current #28 B03 update using the frozen controller's records.

V13 owns the original update controller. This successor checks an installed
B03 Run after source replay and before a success pointer can be written. It
uses the existing intent, terminal, recovery and state format and leaves the
old controller's default path byte-identical.
"""
from pathlib import Path
from uuid import uuid4

from . import normal_run_v3 as normal
from . import ordinary_update_cycle as inherited
from .b03_depreciation_scope import assess_direct_depreciation_scope
from .canonical import atomic_write_json, sha256_file, strict_json_file
from .normal_annual_input import _registry_rows
from .ordinary_projection import render_ordinary_run
from .requirements import load_requirement_snapshot


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


class B03CurrentScopeConflict(ValueError):
    """A mechanically valid historical success lacks current B03 credit."""


def _verify_candidate(root, terminal, configuration):
    """Validate old-format records, then withhold a narrow B03 source."""
    result = inherited._verify_candidate(root, terminal, configuration)
    work = inherited._attempt(root, terminal['attempt_id'])
    data = work/'data'
    manifest = strict_json_file(path=work/'runs/B03/manifest.json')
    case = normal.replay_case(data_root=data, manifest=manifest)
    _need(case['primary_metric_id'] == 'B03'
          and manifest['company_id'] == configuration['company_id'],
          'B03_CURRENT_SUCCESS_METRIC_OR_COMPANY_CHANGED')
    scope = assess_direct_depreciation_scope(case=case, data_root=data)
    if scope['blocked']:
        raise B03CurrentScopeConflict(
            'B03_CURRENT_SUCCESS_SCOPE_UNRESOLVED:' + scope['status'])
    return result


def _verify_historical_candidate(root, terminal, configuration):
    """Recover an old terminal without restoring its current business credit."""
    try:
        return _verify_candidate(root, terminal, configuration)
    except B03CurrentScopeConflict:
        return inherited._verify_candidate(root, terminal, configuration)


def _run_once_b03(*, state_root, source_root, company_id,
                  native_assessment_mode='LIVE', native_assessment_ledger=None,
                  source_identity_root=None):
    """Keep B03's source decision inside the original durable write order."""
    root = normal._external(Path(state_root))
    source = (normal._external(Path(source_root))
              if source_identity_root is not None else Path(source_root).resolve())
    identity_source = (source if source_identity_root is None else
                       normal._external(Path(source_identity_root)))
    inherited._need(root != source and root not in source.parents
                    and source not in root.parents,
                    'UPDATE_SOURCE_STATE_ROOTS_OVERLAP')
    if source_identity_root is not None:
        from .ordinary_processing_source import verify_processing_source
        from .continuous_call_policy import REQUIREMENT_ID
        processing_requirement = load_requirement_snapshot(
            snapshot_dir=normal.ROOT/'requirements'/REQUIREMENT_ID)
        verify_processing_source(acquisition_root=identity_source,
            processing_root=source, requirement=processing_requirement)
    with inherited._locked(root):
        configuration = inherited._config(root, identity_source, company_id,
                                          ['B03'], native_assessment_mode)
        state = inherited._recover(root, inherited._state(root, configuration),
            configuration, verify_candidate=_verify_historical_candidate)
        previous = None
        previous_scope_conflict = False
        successful_results = {}
        if state['successful_attempt'] is not None:
            previous = inherited._terminal(root, state['successful_attempt'])
            try:
                successful_results = _verify_candidate(root, previous,
                                                       configuration)
            except B03CurrentScopeConflict:
                previous_scope_conflict = True
        identity = uuid4().hex
        work = inherited._attempt(root, identity)
        intent = inherited._record(work/'intent.json', {
            'record_type': 'ORDINARY_UPDATE_INTENT', 'attempt_id': identity,
            'configuration_id': configuration['record_id'],
            'started_at': inherited._now(),
            'previous_attempt': state['latest_attempt'],
            'previous_successful_attempt': state['successful_attempt']})
        descriptor = None
        metrics = {}
        status = 'INPUT_FAILED'
        error = None
        try:
            _, descriptor, ledger = inherited._inspect(
                source, configuration, native_assessment_ledger)
            if previous:
                inherited._need(descriptor['targets']['B03']['period_end'] >=
                    previous['input']['targets']['B03']['period_end'],
                    'UPDATE_SOURCE_PERIOD_REGRESSED')
            if previous and descriptor == previous['input']:
                status = ('PREVIOUS_INPUT_WITHHELD' if previous_scope_conflict
                          else 'NO_SOURCE_CONTENT_CHANGE')
            elif state['latest_attempt']:
                prior = inherited._terminal(root, state['latest_attempt'])
                if (prior['input'] == descriptor and
                        prior['status'] in {'CANDIDATE_WITHHELD',
                            'PREVIOUS_INPUT_WITHHELD'}):
                    status = 'PREVIOUS_INPUT_WITHHELD'
                elif (prior['input'] == descriptor and
                        prior['status'] == 'EXECUTION_FAILED' and
                        type(prior['error']) is dict and
                        str(prior['error'].get('reason', '')).startswith(
                            'B03_CURRENT_SOURCE_SCOPE_UNRESOLVED:')):
                    status = 'PREVIOUS_INPUT_WITHHELD'
            if status == 'INPUT_FAILED':
                normal.install_normal_inputs(data_root=work/'data',
                    source_root=None if source == normal.ROOT else source,
                    company_id=company_id, metric_id='B03')
                created = normal.create_normal_run(data_root=work/'data',
                    run_dir=work/'runs/B03', company_id=company_id,
                    metric_id='B03')
                rendered = render_ordinary_run(data_root=work/'data',
                                               run_dir=work/'runs/B03')
                hashes = {}
                for name, raw in rendered['files'].items():
                    path = work/'rows/B03'/name
                    normal._write(path, raw)
                    hashes[name] = sha256_file(path=path)
                metrics['B03'] = {
                    'result_id': created['result']['result_id'],
                    'publication': created['result']['publication'],
                    'source_credit': created['input_binding'][
                        'source_admission']['source_credit'],
                    'files': hashes}
                inherited._need(sha256_file(path=source/
                    'evidence/requests_log.csv') == ledger,
                    'UPDATE_SOURCE_CHANGED_DURING_EXECUTION')
                if created['result']['publication'] == 'PUBLISHED':
                    case = normal.replay_case(data_root=work/'data',
                                              manifest=created['manifest'])
                    scope = assess_direct_depreciation_scope(
                        case=case, data_root=work/'data')
                    _need(not scope['blocked'],
                          'B03_CURRENT_SOURCE_SCOPE_UNRESOLVED:' +
                          scope['status'])
                    status = 'CANDIDATE_READY'
                    successful_results = _verify_candidate(root, {
                        'status': status,
                        'configuration_id': configuration['record_id'],
                        'attempt_id': identity, 'input': descriptor,
                        'metrics': metrics}, configuration)
                    previous_scope_conflict = False
                else:
                    status = 'CANDIDATE_WITHHELD'
            if source_identity_root is not None:
                verify_processing_source(acquisition_root=identity_source,
                    processing_root=source, requirement=processing_requirement)
        except Exception as failure:
            error = {'error_type': type(failure).__name__,
                     'reason': str(failure)}
            status = 'EXECUTION_FAILED' if descriptor is not None else 'INPUT_FAILED'
        terminal = inherited._record(work/'terminal.json', {
            'record_type': 'ORDINARY_UPDATE_TERMINAL',
            'attempt_id': identity,
            'configuration_id': configuration['record_id'],
            'intent_id': intent['record_id'], 'status': status,
            'completed_at': inherited._now(), 'input': descriptor,
            'metrics': metrics, 'error': error,
            'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'production_authorized': False})
        if status == 'CANDIDATE_READY':
            state['successful_attempt'] = identity
            previous = terminal
        state['latest_attempt'] = identity
        atomic_write_json(path=root/'current.json', value=state)
        return {'status': status, 'attempt_id': identity,
            'latest_attempt': identity,
            'successful_attempt': state['successful_attempt'],
            'previous_successful_attempt': intent['previous_successful_attempt'],
            'last_verified_candidate': None if previous is None or
                previous_scope_conflict else {
                'attempt_id': previous['attempt_id'],
                'targets': previous['input']['targets'],
                'current_input_matches': descriptor == previous['input'],
                'results': successful_results,
                'rows_root': str(inherited._attempt(root,
                    previous['attempt_id'])/'rows')},
            'new_candidate_created': bool(metrics),
            'terminal': terminal,
            'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'production_authorized': False}


def _blocked(error):
    return {'metric_id': 'B03', 'status': 'UPDATE_BLOCKED',
        'error_type': type(error).__name__, 'reason': str(error),
        'last_verified_candidate': None,
        'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'production_authorized': False}


def run_company(*, state_root, source_root, company_id, metric_ids,
                native_assessment_mode='LIVE', native_assessment_ledger=None,
                source_identity_root=None):
    """Dispatch only B03 to the explicit successor; other metrics stay old."""
    root = normal._external(Path(state_root))
    source = Path(source_root).resolve()
    _need(type(metric_ids) is list and metric_ids and
          len(metric_ids) == len(set(metric_ids)) and
          set(metric_ids) <= set(normal.update_metric_ids()) and
          company_id in {row['company_id'] for row in
                         _registry_rows(repo_root=normal.ROOT)},
          'B03_CURRENT_UPDATE_SCOPE_INVALID')
    if 'B03' not in metric_ids:
        return inherited.run_company(state_root=root, source_root=source,
            company_id=company_id, metric_ids=metric_ids,
            native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger,
            source_identity_root=source_identity_root)
    _need(not (root/'configuration.json').exists() and
          not (root/'current.json').exists(),
          'UPDATE_GROUP_HISTORY_REQUIRES_PINNED_RUNTIME')
    others = [metric for metric in metric_ids if metric != 'B03']
    other_rows = (inherited.run_company(state_root=root,
        source_root=source, company_id=company_id, metric_ids=others,
        native_assessment_mode=native_assessment_mode,
        native_assessment_ledger=native_assessment_ledger,
        source_identity_root=source_identity_root)['metrics'] if others else [])
    try:
        b03 = _run_once_b03(state_root=root/'metrics/B03',
            source_root=source, company_id=company_id,
            native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger,
            source_identity_root=source_identity_root)
        b03 = {'metric_id': 'B03', **b03}
    except Exception as error:
        b03 = _blocked(error)
    by_metric = {row['metric_id']: row for row in [*other_rows, b03]}
    rows = [by_metric[metric] for metric in metric_ids]
    ready = sum(row['status'] in {'CANDIDATE_READY',
                                  'NO_SOURCE_CONTENT_CHANGE'} for row in rows)
    return {'company_id': company_id,
        'status': 'UPDATES_READY' if ready == len(rows)
            else 'UPDATES_PARTIAL' if ready else 'UPDATES_INCOMPLETE',
        'metrics': rows,
        'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'production_authorized': False}
