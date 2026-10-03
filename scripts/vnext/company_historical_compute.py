"""Company boundary over #47's pinned period, installation and native Run APIs."""
from uuid import uuid4
from contextlib import contextmanager

from .canonical import content_hash, strict_json_file
from .company_handoff import _atomic_json
from .company_source_authority import need


@contextmanager
def historical_compute_scope():
    """Reuse #47's bounded, state-keyed batch mechanisms; keep inputs separate."""
    from .historical_run_replay import run_checks_replay_once
    from .historical_derivation_memo import derived_once_per_state
    from .historical_xbrl_parse import xbrl_parsed_once
    with run_checks_replay_once(), derived_once_per_state(), xbrl_parsed_once():
        yield


def compute_historical(*, root, source, company_id, metric_ids, report_end=None, fiscal_year=None):
    from .normal_period_selection import resolve_period_selection
    from .historical_run import install_historical_run_inputs, create_historical_run
    from .historical_projection import render_historical_run
    from .historical_results import prepare_historical_run_input
    from .historical_run_receipts import read_run_receipt
    need((report_end is None) != (fiscal_year is None),
         'COMPANY_HISTORY_EXACTLY_ONE_PERIOD_REQUIRED')
    try:
        selection = resolve_period_selection(repo_root=source, company_id=company_id,
                                             report_end=report_end, fiscal_year=fiscal_year)
    except Exception as error:
        return {'company_id': company_id, 'metrics': [
            {'metric_id': metric, 'status': 'INPUT_FAILED',
             'reason': str(error), 'error_type': type(error).__name__,
             'business_metric_completed': False} for metric in metric_ids]}
    outcomes = []
    for metric in metric_ids:
        target = root/'updates/historical'/selection['target_report_end']/metric
        previous = None
        try:
            pointer = target/'current.json'
            previous = strict_json_file(path=pointer) if pointer.is_file() else None
            prepared = prepare_historical_run_input(repo_root=source, company_id=company_id,
                                                    metric_id=metric, period_selection=selection)
            fingerprint = content_hash(value={
                'input_id': prepared['input_id'],
                'period_selection_id': selection['selection_id'],
                'spec_closures': {key: spec['spec_closure_hash']
                                  for key, spec in prepared['compiled_specs'].items()}})
            if previous and previous['input_fingerprint'] == fingerprint:
                work = target/'attempts'/previous['attempt_id']
                render_historical_run(data_root=work/'data', run_dir=work/'runs'/metric, frozen=True)
                outcomes.append({'metric_id': metric, 'status': 'NO_SOURCE_CONTENT_CHANGE',
                                 'new_candidate_created': False,
                                 'last_verified_candidate': previous['candidate']})
                continue
            attempt = uuid4().hex
            work = target/'attempts'/attempt
            installed = install_historical_run_inputs(data_root=work/'data', company_id=company_id,
                metric_id=metric, period_selection=selection, source_root=source)
            create_historical_run(data_root=work/'data', run_dir=work/'runs'/metric,
                company_id=company_id, metric_id=metric,
                binding_id=installed['binding']['binding_id'], freeze=True)
            rendered = render_historical_run(data_root=work/'data', run_dir=work/'runs'/metric,
                                             frozen=True, persist=True)
            # The existing receipt is a hash-read interface, separately from
            # the frozen replay performed above.
            receipt = read_run_receipt(run_dir=work/'runs'/metric)
            rows = work/'rows'; rows.mkdir()
            from .publication import _csv_bytes, METRIC_FIELDS, EVIDENCE_FIELDS
            (rows/'metrics_matrix.csv').write_bytes(_csv_bytes(rows=[rendered['row']], fieldnames=METRIC_FIELDS))
            (rows/'metric_evidence.csv').write_bytes(_csv_bytes(rows=rendered['evidence'], fieldnames=EVIDENCE_FIELDS))
            candidate = {'attempt_id': attempt, 'rows_root': str(rows), 'receipt': receipt,
                         'current_input_matches': True, 'period_selection': selection}
            _atomic_json(pointer, {'attempt_id': attempt, 'input_fingerprint': fingerprint,
                                   'candidate': candidate})
            outcomes.append({'metric_id': metric, 'status': 'CANDIDATE_READY',
                             'new_candidate_created': True, 'last_verified_candidate': candidate})
        except Exception as error:
            target.mkdir(parents=True, exist_ok=True)
            failure = {'metric_id': metric, 'status': 'UPDATE_BLOCKED',
                       'reason': str(error), 'error_type': type(error).__name__,
                       'business_metric_completed': False}
            if previous:
                failure['last_verified_candidate'] = {
                    **previous['candidate'], 'current_input_matches': False}
            _atomic_json(target/'latest_failure.json', failure)
            outcomes.append(failure)
    return {'company_id': company_id, 'metrics': outcomes}
