"""Read a selected event window from source-only inputs and explicit rules.

Selection, amendment admission, metric matching and calculation remain with
the consumer. This interface reuses the ordinary source walk and verifies the
actual bodies/headers; it creates no Result/Run and does not confirm E01.
An optional history validator is consumer program code, whose file/config
dependencies must be declared in that consumer's processing identity.
"""
from datetime import date
from pathlib import Path

from sec_urls import submissions_url
from .canonical import sha256_file
from .normal_annual_input import _registry_rows
from .normal_governance_input import _Sources
from .normal_zero_ai_results import _event_sources, _registered_event_sources
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_ciks


class SelectedEventSourceError(ValueError):
    category = 'SELECTED_SOURCE_SCOPE_UNRESOLVED'


def _need(condition, reason):
    if not condition:
        raise SelectedEventSourceError('SELECTED_EVENT_' + reason)


def read_selected_event_sources(*, data_root, rules_root, prepared, period,
                                registered_union=False, history_validator=None, history_last_days=None):
    """Read exact SEC event inputs for an already selected issuer/window.

    ``registered_union`` must be selected from the approved event scope by the
    caller; false reads only the selected registrant. ``history_validator``
    receives the full saved block, declared shards, retained filing rows and
    window. A non-None conflict blocks the walk, never becomes an empty set.
    Without it, the original ordinary history check remains in use.
    """
    source, rules = Path(data_root), Path(rules_root)
    _need(type(registered_union) is bool, 'REGISTRANT_SCOPE_REQUIRED')
    _need(history_validator is None or callable(history_validator), 'HISTORY_VALIDATOR_INVALID')
    _need(history_last_days is None or callable(history_last_days), 'HISTORY_LAST_DAYS_INVALID')
    _need(history_last_days is None or callable(history_validator), 'HISTORY_VALIDATOR_REQUIRED')
    company = prepared['company_id']
    source_rows = [row for row in _registry_rows(repo_root=source) if row['company_id'] == company]
    rules_rows = [row for row in _registry_rows(repo_root=rules) if row['company_id'] == company]
    _need(len(source_rows) == len(rules_rows) == 1 and source_rows == rules_rows,
          'SOURCE_SUBJECT_REGISTRY_CHANGED')
    ciks = repository_company_ciks(repo_root=rules, company_id=company)
    _need(prepared['entity'] in ciks, 'SELECTED_REGISTRANT_NOT_REGISTERED')
    _need(type(period) is dict and {'period_start', 'period_end', 'fiscal_year'} <= set(period),
          'WINDOW_REQUIRED')
    try:
        start, end = (date.fromisoformat(period[key]) for key in ('period_start', 'period_end'))
    except (TypeError, ValueError):
        raise SelectedEventSourceError('SELECTED_EVENT_WINDOW_INVALID') from None
    _need(start <= end and start.isoformat() == period['period_start']
          and end.isoformat() == period['period_end']
          and type(period['fiscal_year']) is int, 'WINDOW_INVALID')
    ledger = source / 'evidence/requests_log.csv'
    before = sha256_file(path=ledger)
    reader = _Sources(source, company, prepared['entity'])
    inventory = reader.read(submissions_url(cik=int(prepared['entity'])),
                            role='sec_submissions_inventory', media_type='application/json')
    context = {'company_id': company, 'entity': prepared['entity'],
               'table_input': {'target_period': period}}
    registered_scope = None
    if registered_union:
        claims, manifests, filings, registered_scope = _registered_event_sources(
            repo_root=source, reader=reader, prepared=context, inventory=inventory,
            period=period, rules_root=rules, history_validator=history_validator,
            history_last_days=history_last_days)
    else:
        claims, manifests, filings = _event_sources(
            repo_root=source, reader=reader, prepared=context, inventory=inventory,
            installed_census_required=False, history_validator=history_validator,
            history_last_days=history_last_days)
    proofs = [entry['proof'] for entry in reader.proofs.values()]
    admission = verify_ordinary_source_proofs(data_root=source, proofs=proofs)
    _need(sha256_file(path=ledger) == before, 'LEDGER_CHANGED_DURING_READ')
    records = list(reader.records.values())
    return {'record_type': 'SELECTED_EVENT_SOURCE_INPUT', 'company_id': company,
            'selected_cik': prepared['entity'], 'event_window': dict(period),
            'registered_event_scope': registered_scope, 'claims': claims,
            'source_set_manifests': manifests, 'filings': filings,
            'inventory_source_reference': inventory['source_reference'],
            'source_records': records,
            'source_references': [row for row in records if row['record_type'] == 'SOURCE_REFERENCE'],
            'source_bindings': list(reader.proofs.values()), 'source_proofs': proofs,
            'source_admission': admission,
            'failed_source_attempts': list(reader.failed_attempts.values()),
            'new_calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'native_run_status': 'NOT_CREATED', 'production_authorized': False}
