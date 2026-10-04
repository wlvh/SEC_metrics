"""Current #28 A05 update with a bound explanation of its approved formula.

The old A05 update journal and its rows retain their exact identity. New A05
attempts use a separate versioned journal; other metrics keep their current
routes, including the explicit B03 successor.
"""
from pathlib import Path

from . import normal_run_v3 as normal
from . import ordinary_update_cycle as current
from .ordinary_b03_scope_update import run_company as run_other_metrics


def _blocked(error):
    return {'metric_id': 'A05', 'status': 'UPDATE_BLOCKED',
            'error_type': type(error).__name__, 'reason': str(error),
            'last_verified_candidate': None,
            'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'production_authorized': False}


def run_company(*, state_root, source_root, company_id, metric_ids,
                native_assessment_mode='LIVE', native_assessment_ledger=None,
                source_identity_root=None):
    """Automatically select the explained A05 successor on this #28 CLI."""
    root = normal._external(Path(state_root))
    if 'A05' not in metric_ids:
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
    other_ids = [metric for metric in metric_ids if metric != 'A05']
    other_rows = (run_other_metrics(state_root=root,
        source_root=source_root, company_id=company_id, metric_ids=other_ids,
        native_assessment_mode=native_assessment_mode,
        native_assessment_ledger=native_assessment_ledger,
        source_identity_root=source_identity_root)['metrics'] if other_ids else [])
    try:
        a05 = current.run_once(state_root=root/'metrics/A05-formula-v1',
            source_root=source_root, company_id=company_id,
            metric_ids=['A05'], native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger,
            source_identity_root=source_identity_root, a05_formula=True)
        a05 = {'metric_id': 'A05', **a05}
    except Exception as error:
        a05 = _blocked(error)
    rows = {row['metric_id']: row for row in [*other_rows, a05]}
    ordered = [rows[metric] for metric in metric_ids]
    ready = sum(row['status'] in {'CANDIDATE_READY',
                                  'NO_SOURCE_CONTENT_CHANGE'} for row in ordered)
    return {'company_id': company_id,
        'status': 'UPDATES_READY' if ready == len(ordered) else
            'UPDATES_PARTIAL' if ready else 'UPDATES_INCOMPLETE',
        'metrics': ordered,
        'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'production_authorized': False}
