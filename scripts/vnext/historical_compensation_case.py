"""Historical C03 source selection for the shared compensation resolver.

First-reported selection continues the existing historical policy. The public
resolver, ordinary writer and renderer own value/record handling; this module
does not provide a second compensation parser or result store.
"""
from pathlib import Path

from .canonical import content_hash, strict_json_loads
from .historical_annual_input import prepare_historical_annual_input
from .normal_governance_input import _Sources, _order
from .normal_history_catalog import load_history_for_period
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .governance_signals import C03_SPEC_PATH, resolve_c03
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .specs import compile_spec_file
from .deterministic_router import DeterministicRouterError
from .proxy_compensation_source import (SPEC_PATH as PROXY_SCT_SPEC_PATH,
    PROCESSING_FILES as PROXY_SCT_PROCESSING_FILES, resolve_proxy_compensation_table)


METRICS = ('C03',)
PROCESSING_FILES = tuple(dict.fromkeys((*tuple('scripts/vnext/'+name+'.py' for name in (
    'historical_compensation_case', 'historical_annual_input', 'historical_dei',
    'historical_fiscal_labels', 'normal_period_selection', 'normal_history_catalog',
    'normal_governance_input', 'governance_signals', 'xbrl_namespace_policy',
)) + ('config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
      C03_SPEC_PATH), *PROXY_SCT_PROCESSING_FILES)))


class HistoricalCompensationInputError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise HistoricalCompensationInputError(reason, category)


def select_first_reported_proxy(*, prepared, history):
    """Reuse the historical first-proxy rule and current same-day ordering."""
    _need(history['window_proven'] and not history['limitations'],
          'HISTORICAL_C03_PROXY_HISTORY_INCOMPLETE', 'SOURCE_UNAVAILABLE')
    _need(str(int(history['reporting_cik'])) == str(int(prepared['entity'])),
          'HISTORICAL_C03_PROXY_REPORTER_CHANGED')
    period = prepared['table_input']['target_period']
    rows = history['all_rows']
    annuals = [r for r in rows if r['form']=='10-K' and r['reportDate']==period['period_end']]
    _need(len(annuals)==1 and all(annuals[0][key]==prepared['filing'][key]
        for key in ('accessionNumber','primaryDocument','reportDate','form')),
        'HISTORICAL_C03_SELECTED_ANNUAL_CHANGED')
    # _order proves acceptance timestamps for same-day rows. Reversing its
    # newest-first result preserves the existing first-reported convention.
    proxies = list(reversed(_order([r for r in rows
        if r['form']=='DEF 14A' and r['filingDate']>period['period_end']])))
    _need(bool(proxies), 'HISTORICAL_C03_FIRST_PROXY_NOT_SAVED', 'SOURCE_UNAVAILABLE')
    proxy = proxies[0]
    sequence = list(reversed(_order([proxy, *[r for r in rows if r['form']=='DEF 14A/A'
        and r['filingDate']>=proxy['filingDate']], *proxies[1:]])))
    next_proxy = next((r for r in sequence if r['form']=='DEF 14A'
                       and r['accessionNumber']!=proxy['accessionNumber']), None)
    changes = []
    for r in sequence[sequence.index(proxy)+1:]:
        if next_proxy is not None and r['accessionNumber']==next_proxy['accessionNumber']:
            break
        if r['form']=='DEF 14A/A':changes.append(r)
    return {'record_type':'HISTORICAL_C03_FIRST_REPORTED_SELECTION',
        'reporting_cik':prepared['entity'], 'annual_filing':prepared['filing'],
        'target_period':period, 'selected_proxy':proxy, 'proxy_amendments':changes,
        'first_reported_convention':'OWNER_A_2026_09_30',
        'selection_rule':'EARLIEST_SAME_CIK_DEF14A_AFTER_SELECTED_PERIOD',
        'loaded_inventories':history['loaded_inventories'], 'value_selected':False}


def prepare_historical_compensation_sources(*, repo_root, company_id, fiscal_year):
    """Prepare one existing proxy using shared annual/history/source readers."""
    root = Path(repo_root)
    selected = resolve_period_selection(repo_root=root, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    annual = prepare_historical_annual_input(repo_root=root, company_id=company_id,
        period_selection=selected, rules_root=ROOT)
    reader = _Sources(root, company_id, annual['entity'])
    # The shared reporter projection uses the annual container's original
    # primary reference when the Calculator target has null entity/accession.
    # Retain that real source alongside the distinct compensation proxy.
    reader.primary(annual['filing'])
    history = load_history_for_period(repo_root=root, company_id=company_id,
        report_end=annual['table_input']['target_period']['period_end'],
        cik=annual['entity'], reader=reader)
    proxy = select_first_reported_proxy(prepared=annual, history=history)
    _need(not proxy['proxy_amendments'], 'HISTORICAL_C03_PROXY_AMENDMENT_NOT_RECEIVED',
          'IMPLEMENTATION_GAP')
    source = reader.primary(proxy['selected_proxy'])
    proofs = {content_hash(value=p):p for p in annual['source_proofs']}
    proofs.update({content_hash(value=s['proof']):s['proof'] for s in reader.proofs.values()})
    return {'prepared_annual_input':annual, 'selection':proxy, 'proxy_source':source,
        'records':list(reader.records.values()), 'source_proofs':list(proofs.values()),
        'source_selection':selected,
        'proxy_inventory':strict_json_loads(text=history['inventory']['raw_bytes'].decode('utf-8'))}


def prepare_historical_compensation_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Use ECD, then the shared SCT only for a truly untagged proxy."""
    _need(metric_id=='C03', 'HISTORICAL_C03_METRIC_REQUIRED', 'IMPLEMENTATION_GAP')
    source = prepare_historical_compensation_sources(repo_root=repo_root,
        company_id=company_id, fiscal_year=fiscal_year)
    annual, proxy = source['prepared_annual_input'], source['proxy_source']
    period = annual['table_input']['target_period']
    scope = {'entity_scope':'registrant'}
    target = {'company_id':company_id, 'period_start':period['period_start'],
        'period_end':period['period_end'], 'scope':scope, 'scope_key':scope_key(scope=scope)}
    spec = compile_spec_file(path=ROOT/C03_SPEC_PATH, dependency_specs={})
    args = {key:proxy[key] for key in ('raw_bytes','raw_blob','source_reference')}
    spec_path, source_kind = C03_SPEC_PATH, 'FIRST_REPORTED_PROXY_ECD'
    try:
        resolution = resolve_c03(**args, target=target, expected_cik=annual['entity'],
            compiled_spec=spec, sec_namespace_release='YEAR_QUARTER_OR_DATE')
    except DeterministicRouterError as error:
        # This is the existing historical route's narrow no-context rule.
        # Any broken inline document, wrong unit/person/period or other error
        # retains its original outcome rather than escaping into another table.
        if str(error) != 'XBRL source contains no contexts' or b'<ix:' in args['raw_bytes'].lower():
            raise
        spec_path, source_kind = PROXY_SCT_SPEC_PATH, 'FIRST_REPORTED_PROXY_SCT'
        spec = compile_spec_file(path=ROOT/spec_path, dependency_specs={})
        resolution = resolve_proxy_compensation_table(**args,
            filing=source['selection']['selected_proxy'], inventory=source['proxy_inventory'],
            company_id=company_id, cik=annual['entity'], target=target,
            fiscal_year=period['fiscal_year'], compiled_spec=spec)
    observation = resolution['observation']
    records = [*source['records'], *resolution.get('derived_assets',()),
               *([observation] if observation is not None else []),
               resolution['trace'], resolution['result']]
    # ECD's absent/ambiguous/person/period outcomes remain the shared core's
    # exact outcomes. No arbitrary fallback to another proxy or annual year.
    assessment = {'selection':source['selection'], 'resolution':resolution['selection'],
        'source_kind':source_kind,
        'proxy_sct_consumer_complete':False,
        'proxy_sct_route_used':source_kind=='FIRST_REPORTED_PROXY_SCT'}
    return {'kind':'STRUCTURED', 'primary_metric_id':'C03',
        'compiled_specs':{'C03':spec}, 'spec_paths':{'C03':spec_path},
        'target_period':period, 'prepared_annual_input':annual,
        'selected_proxy':source['selection']['selected_proxy'],
        'expected_records':records, 'results':{'C03':resolution['result']},
        'traces':{'C03':resolution['trace']},
        'references':[r for r in source['records'] if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':source['source_proofs'],
        'admission':verify_ordinary_source_proofs(data_root=Path(repo_root),proofs=source['source_proofs']),
        'input_binding':{'record_type':'HISTORICAL_C03_SELECTED_INPUT',
            'prepared_input':annual, 'proxy_selection':source['selection'],
            'selected_proxy':source['selection']['selected_proxy'],
            'resolution':resolution, 'source_proofs':source['source_proofs']},
        'input_assessments':{'C03':assessment},
        'selection':{'source_kind':assessment['source_kind'],
            'selected_proxy_accession':source['selection']['selected_proxy']['accessionNumber'],
            'reason_code':resolution['selection']['reason_code']}, 'rules_root':str(ROOT)}
