"""#28 CLI explicitly selects the pinned running-header successor for D01."""
from pathlib import Path
from . import normal_run_v3 as normal
from . import ordinary_update_cycle as current
from .ordinary_c02_member_update_v4 import run_company as run_other_metrics


def run_company(*, state_root, source_root, company_id, metric_ids,
                native_assessment_mode='LIVE', native_assessment_ledger=None,
                source_identity_root=None):
    root = normal._external(Path(state_root))
    if 'D01' not in metric_ids:
        return run_other_metrics(state_root=root, source_root=source_root, company_id=company_id,
            metric_ids=metric_ids, native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger, source_identity_root=source_identity_root)
    current._need(type(metric_ids) is list and metric_ids
                  and len(metric_ids) == len(set(metric_ids))
                  and set(metric_ids) <= set(normal.update_metric_ids()), 'UPDATE_METRIC_SCOPE_INVALID')
    current._need(not (root/'configuration.json').exists() and not (root/'current.json').exists(),
                  'UPDATE_GROUP_HISTORY_REQUIRES_PINNED_RUNTIME')
    others = [m for m in metric_ids if m != 'D01']
    rows = (run_other_metrics(state_root=root, source_root=source_root, company_id=company_id,
        metric_ids=others, native_assessment_mode=native_assessment_mode,
        native_assessment_ledger=native_assessment_ledger,
        source_identity_root=source_identity_root)['metrics'] if others else [])
    try:
        outcome = current.run_once(state_root=root/'metrics/D01-header-v3', source_root=source_root,
            company_id=company_id, metric_ids=['D01'], native_assessment_mode=native_assessment_mode,
            native_assessment_ledger=native_assessment_ledger, source_identity_root=source_identity_root,
            d01_header_revision=True)
        rows.append({'metric_id': 'D01', **outcome})
    except Exception as error:
        rows.append({'metric_id':'D01', 'status':'UPDATE_BLOCKED', 'error_type':type(error).__name__,
            'reason':str(error), 'last_verified_candidate':None,
            'calls':{'provider':0,'paid':0,'sec':0}, 'production_authorized':False})
    by_metric = {row['metric_id']: row for row in rows}
    ordered = [by_metric[m] for m in metric_ids]
    ready = sum(row['status'] in {'CANDIDATE_READY','NO_SOURCE_CONTENT_CHANGE'} for row in ordered)
    return {'company_id':company_id, 'status':'UPDATES_READY' if ready == len(ordered) else
        'UPDATES_PARTIAL' if ready else 'UPDATES_INCOMPLETE', 'metrics':ordered,
        'calls':{'provider':0,'paid':0,'sec':0}, 'production_authorized':False}
