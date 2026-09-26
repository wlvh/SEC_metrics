"""Explicit C04 four-form successor over the existing ordinary update journal.

The older ordinary controller stays byte-identical. This route reuses its
locked journal, prior-candidate verification and interruption recovery, while
selecting the registered four-form C04 source family at each Run boundary.
"""
from pathlib import Path
from uuid import uuid4

from . import normal_run_v3 as normal
from . import ordinary_update_cycle as cycle
from .c04_registration_successor import EVENT_FORMS
from .canonical import atomic_write_json, sha256_file
from .normal_annual_input import _registry_rows
from .ordinary_projection import render_ordinary_run
from .requirements import load_requirement_snapshot


ROUTE = 'C04_REGISTRATION_FOUR_FORM_UPDATE_V1'


def _configuration(root, source_root, company_id):
    policy = normal._policy(normal.ROOT)
    cycle._need(not policy['provider_enabled'] and not policy['sec_fetch_enabled']
                and not policy['freeze_enabled'], 'UPDATE_ZERO_EGRESS_RUNTIME_REQUIRED')
    cycle._need(company_id in {row['company_id'] for row in
                _registry_rows(repo_root=normal.ROOT)}, 'UPDATE_COMPANY_NOT_CONFIGURED')
    requirement = load_requirement_snapshot(
        snapshot_dir=normal.ROOT/'requirements'/normal.REQUIREMENT_ID)
    body = {'record_type': 'ORDINARY_UPDATE_CONFIGURATION', 'schema_version': 2,
        'company_id': company_id, 'metric_ids': ['C04'],
        'source_root': str(source_root),
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'route': ROUTE, 'c04_event_forms': EVENT_FORMS,
        'controller_sha256': sha256_file(path=Path(__file__)),
        'provider_enabled': False, 'sec_fetch_enabled': False,
        'production_authorized': False}
    path = root/'configuration.json'
    if path.exists():
        saved = cycle._read(path)
        cycle._need({key: value for key, value in saved.items()
                     if key != 'record_id'} == body,
                    'C04_UPDATE_CONFIGURATION_OR_RUNTIME_CHANGED')
        return saved
    return cycle._record(path, body)


def _inspect(source_root, configuration):
    original_ledger = sha256_file(path=source_root/'evidence/requests_log.csv')
    case = normal.prepare_case(data_root=source_root,
        company_id=configuration['company_id'], metric_id='C04',
        c04_event_forms=EVENT_FORMS)
    cycle._need(sha256_file(path=source_root/'evidence/requests_log.csv')
                == original_ledger, 'UPDATE_SOURCE_CHANGED_DURING_INSPECTION')
    return case, cycle._descriptor({'C04': case}, configuration), original_ledger


def run_once(*, state_root, source_root, company_id):
    """Advance one C04 history; source and old successes are checked each run."""
    root = normal._external(Path(state_root))
    source = Path(source_root).resolve()
    cycle._need(root != source and root not in source.parents
                and source not in root.parents, 'UPDATE_SOURCE_STATE_ROOTS_OVERLAP')
    with cycle._locked(root):
        configuration = _configuration(root, source, company_id)
        state = cycle._recover(root, cycle._state(root, configuration), configuration)
        previous = None
        successful_results = {}
        if state['successful_attempt'] is not None:
            previous = cycle._terminal(root, state['successful_attempt'])
            successful_results = cycle._verify_candidate(root, previous, configuration)
        identity = uuid4().hex
        work = cycle._attempt(root, identity)
        intent = cycle._record(work/'intent.json', {
            'record_type': 'ORDINARY_UPDATE_INTENT', 'attempt_id': identity,
            'configuration_id': configuration['record_id'],
            'started_at': cycle._now(), 'previous_attempt': state['latest_attempt'],
            'previous_successful_attempt': state['successful_attempt']})
        descriptor = None
        metrics = {}
        status = 'INPUT_FAILED'
        error = None
        try:
            _, descriptor, ledger_digest = _inspect(source, configuration)
            if previous:
                cycle._need(descriptor['targets']['C04']['period_end'] >=
                    previous['input']['targets']['C04']['period_end'],
                    'UPDATE_SOURCE_PERIOD_REGRESSED')
            if previous and descriptor == previous['input']:
                status = 'NO_SOURCE_CONTENT_CHANGE'
            elif (state['latest_attempt'] and
                  (prior := cycle._terminal(root, state['latest_attempt']))['status']
                  in {'CANDIDATE_WITHHELD', 'PREVIOUS_INPUT_WITHHELD'}
                  and prior['input'] == descriptor):
                status = 'PREVIOUS_INPUT_WITHHELD'
            else:
                normal.install_normal_inputs(data_root=work/'data',
                    source_root=None if source == normal.ROOT else source,
                    company_id=company_id, metric_id='C04',
                    c04_event_forms=EVENT_FORMS)
                created = normal.create_normal_run(data_root=work/'data',
                    run_dir=work/'runs/C04', company_id=company_id,
                    metric_id='C04', c04_event_forms=EVENT_FORMS)
                rendered = render_ordinary_run(data_root=work/'data',
                    run_dir=work/'runs/C04')
                hashes = {}
                for name, raw in rendered['files'].items():
                    path = work/'rows/C04'/name
                    normal._write(path, raw)
                    hashes[name] = sha256_file(path=path)
                result = created['result']
                metrics['C04'] = {'result_id': result['result_id'],
                    'publication': result['publication'],
                    'source_credit': created['input_binding']['source_admission']['source_credit'],
                    'files': hashes}
                cycle._need(sha256_file(path=source/'evidence/requests_log.csv')
                            == ledger_digest, 'UPDATE_SOURCE_CHANGED_DURING_EXECUTION')
                status = ('CANDIDATE_READY' if result['publication'] == 'PUBLISHED'
                          else 'CANDIDATE_WITHHELD')
                if status == 'CANDIDATE_READY':
                    successful_results = cycle._verify_candidate(root, {
                        'status': status,
                        'configuration_id': configuration['record_id'],
                        'attempt_id': identity, 'input': descriptor,
                        'metrics': metrics}, configuration)
        except Exception as failure:
            error = {'error_type': type(failure).__name__, 'reason': str(failure)}
            status = 'EXECUTION_FAILED' if descriptor is not None else 'INPUT_FAILED'
        terminal = cycle._record(work/'terminal.json', {
            'record_type': 'ORDINARY_UPDATE_TERMINAL', 'attempt_id': identity,
            'configuration_id': configuration['record_id'],
            'intent_id': intent['record_id'], 'status': status,
            'completed_at': cycle._now(), 'input': descriptor,
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
            'last_verified_candidate': None if previous is None else {
                'attempt_id': previous['attempt_id'],
                'targets': previous['input']['targets'],
                'current_input_matches': descriptor == previous['input'],
                'results': successful_results,
                'rows_root': str(cycle._attempt(root, previous['attempt_id'])/'rows')},
            'new_candidate_created': bool(metrics), 'terminal': terminal,
            'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'production_authorized': False}


def run_company(*, state_root, source_root, company_id):
    """Expose the same one-company result shape as the frozen controller."""
    outcome = run_once(state_root=state_root, source_root=source_root,
                       company_id=company_id)
    ready = outcome['status'] in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'}
    return {'company_id': company_id,
        'status': 'UPDATES_READY' if ready else 'UPDATES_INCOMPLETE',
        'metrics': [{'metric_id': 'C04', **outcome}],
        'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'production_authorized': False}
