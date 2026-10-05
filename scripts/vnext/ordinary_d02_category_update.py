"""Current #28 D02 update selects its pinned Item 8 category successor.

The old D02 journal and Result identities remain readable. This wrapper only
selects the explicit successor for new ordinary CLI attempts.
"""
from pathlib import Path

from . import normal_run_v3 as normal
from . import ordinary_update_cycle as current
from .ordinary_a05_formula_update import run_company as run_other_metrics


def run_company(*, state_root, source_root, company_id, metric_ids,
                native_assessment_mode='LIVE', native_assessment_ledger=None,
                source_identity_root=None):
    root = normal._external(Path(state_root))
    if 'D02' not in metric_ids:
        return run_other_metrics(state_root=root, source_root=source_root,
            company_id=company_id, metric_ids=metric_ids,
            native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger,
            source_identity_root=source_identity_root)
    current._need(type(metric_ids) is list and metric_ids and
                  len(metric_ids) == len(set(metric_ids)) and
                  set(metric_ids) <= set(normal.update_metric_ids()),
                  'UPDATE_METRIC_SCOPE_INVALID')
    current._need(not (root/'configuration.json').exists() and
                  not (root/'current.json').exists(),
                  'UPDATE_GROUP_HISTORY_REQUIRES_PINNED_RUNTIME')
    other_ids = [metric for metric in metric_ids if metric != 'D02']
    other_rows = (run_other_metrics(state_root=root, source_root=source_root,
        company_id=company_id, metric_ids=other_ids,
        native_assessment_mode=native_assessment_mode,
        native_assessment_ledger=native_assessment_ledger,
        source_identity_root=source_identity_root)['metrics'] if other_ids else [])
    try:
        d02 = current.run_once(state_root=root/'metrics/D02-item8-v1',
            source_root=source_root, company_id=company_id,
            metric_ids=['D02'], native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger,
            source_identity_root=source_identity_root, d02_category=True)
        d02 = {'metric_id': 'D02', **d02}
    except Exception as error:
        d02 = {'metric_id': 'D02', 'status': 'UPDATE_BLOCKED',
               'error_type': type(error).__name__, 'reason': str(error),
               'last_verified_candidate': None,
               'calls': {'provider': 0, 'paid': 0, 'sec': 0},
               'production_authorized': False}
    rows = {row['metric_id']: row for row in [*other_rows, d02]}
    ordered = [rows[metric] for metric in metric_ids]
    ready = sum(row['status'] in {'CANDIDATE_READY',
                                  'NO_SOURCE_CONTENT_CHANGE'} for row in ordered)
    return {'company_id': company_id,
        'status': 'UPDATES_READY' if ready == len(ordered) else
            'UPDATES_PARTIAL' if ready else 'UPDATES_INCOMPLETE',
        'metrics': ordered,
        'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'production_authorized': False}
