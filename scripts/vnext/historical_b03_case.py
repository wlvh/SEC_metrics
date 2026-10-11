"""Select saved historical income originals for the shared B03 computation.

The public income core owns revenue admission, D&A scope and calculation.
This module owns only issuer-year/source selection and ordinary-case dispatch.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url
from .canonical import content_hash
from .historical_annual_input import prepare_historical_annual_input
from .historical_filing_inventory import filing_inventory
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs


METRICS = frozenset({'B03'})
SOURCE_PROCESSING_FILES = (
    'scripts/vnext/historical_b03_case.py',
    'scripts/vnext/historical_annual_input.py',
    'scripts/vnext/historical_dei.py',
    'scripts/vnext/historical_fiscal_labels.py',
    'scripts/vnext/historical_filing_inventory.py',
    'scripts/vnext/normal_period_selection.py',
    'scripts/vnext/normal_history_catalog.py',
    'scripts/vnext/normal_governance_input.py',
    'scripts/vnext/ordinary_source_authority.py',
    'scripts/sec_urls.py', 'scripts/sec_http.py',
    'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json',
)


class HistoricalIncomeSourceError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__('HISTORICAL_B03_' + reason)
        self.category = category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise HistoricalIncomeSourceError(reason, category)


def prepare_selected_income_sources(*, repo_root, company_id, fiscal_year):
    """Revalidate the requested issuer year and read both complete originals."""
    source = Path(repo_root).resolve()
    selection = resolve_period_selection(repo_root=source, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    annual = prepare_historical_annual_input(repo_root=source, company_id=company_id,
        period_selection=selection, rules_root=ROOT)
    _need(annual['table_input']['target_period']['fiscal_year'] == fiscal_year,
          'REQUESTED_YEAR_CHANGED')
    _need(annual['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY'
          and not annual['amendments'], 'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED',
          'IMPLEMENTATION_GAP')
    original = annual.get('original_input', annual)
    _need(all(original['table_input']['target_period'][key] ==
              annual['table_input']['target_period'][key]
              for key in ('period_start', 'period_end')), 'ORIGINAL_PERIOD_CHANGED')
    reader = _Sources(source, company_id, original['entity'])
    inventory = reader.read(submissions_url(cik=int(original['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    target_inventory = filing_inventory(reader=reader, inventory=inventory,
        period_selection=selection, cik=original['entity'],
        accession=original['filing']['accessionNumber'])
    facts = reader.read(companyfacts_url(cik=int(original['entity'])),
        accession=original['filing']['accessionNumber'], role='companyfacts',
        media_type='application/json')
    originals = reader.auditor_filing(original['filing'])
    primary = [s for s in originals if s['raw_blob']['media_type'] == 'text/html']
    xml = [s for s in originals if s['raw_blob']['media_type'] == 'application/xml']
    _need(len(primary) == len(xml) == 1, 'ORIGINAL_MEDIA_SET_AMBIGUOUS')
    proofs = list({content_hash(value=p): p for p in [
        *annual['source_proofs'], *[entry['proof'] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source, proofs=proofs)
    body = {'record_type': 'HISTORICAL_SELECTED_INCOME_SOURCE_INPUT',
        'prepared_annual_input': original, 'period_selection': selection,
        'source_sets': reader.file_sets, 'source_proofs': proofs}
    preparation = {'input_binding': {**body, 'input_binding_id': content_hash(value=body)},
            'records': list(reader.records.values()), 'inventory': inventory,
            'facts': facts, 'primary': primary[0], 'xml': xml[0]}
    # Recent filings keep the original object and unchanged calculation input.
    # Older filings use the verified loaded block that actually lists the row.
    if target_inventory is not inventory:
        preparation['filing_inventory_source'] = target_inventory
    return {'annual': annual, 'original_annual': original, 'selection': selection,
        'preparation': preparation,
        'source_proofs': proofs, 'admission': admission}


# The producer names actual shared business dependencies; it does not import
# the retained historical Run/authorization installer.
PROCESSING_FILES = tuple(dict.fromkeys((*SOURCE_PROCESSING_FILES, *(
    'scripts/vnext/'+name+'.py' for name in (
        'normal_annual_input', 'normal_annual_input_v2', 'selected_income_calculation', 'ordinary_income_input',
        'normal_zero_ai_results', 'selected_income_source_v1', 'selected_revenue_scope_v1',
        'selected_reported_revenue_v2', 'selected_fiscal_definition_scope_v1',
        'ordinary_b03_input_scope', 'ordinary_da_scope_v1', 'b03_depreciation_scope',
        'b03_contract_amortization_scope', 'financial_duration', 'financial_structured',
        'text_results_v2', 'reported_monetary_literal', 'xbrl_namespace_policy',
        'composite_scope', 'normal_run_specs', 'batch_workflow', 'deterministic_router',
        'zero_ai_r2', 'annual_sources', 'request_bindings', 'saved_source_checks',
        'fiscal_year_labels', 'traits')), 'catalog/metrics/B01_revenue.md',
    'catalog/metrics/B03_ebitda_margin.md', 'catalog/r6/text_results_v2_policy.json')))


def prepare_historical_income_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Use the common income computation and ordinary record writer shape."""
    from .calculator import withheld_metric_result
    from .historical_dei import annual_period
    from .normal_run_specs import installed_ordinary_spec_documents
    from .normal_zero_ai_results import NormalZeroAiError
    from .observations import scope_key
    from .selected_income_calculation import calculate_selected_income
    from .selected_income_source_v1 import IncomeSourceError
    from .traits import repository_company_traits
    from .xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
    _need(metric_id in METRICS, 'FAMILY_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    selected = prepare_selected_income_sources(repo_root=repo_root,
        company_id=company_id, fiscal_year=fiscal_year)
    annual, preparation = selected['annual'], selected['preparation']
    period = annual['table_input']['target_period']
    scope = {'entity_scope':'registrant', 'period_basis':'source_annual_duration'}
    target = {'company_id':company_id, 'period_start':period['period_start'],
        'period_end':period['period_end'], 'scope':scope, 'scope_key':scope_key(scope=scope)}
    docs = installed_ordinary_spec_documents()
    spec = docs['B03']['compiled_spec']
    dependencies = {'B01':docs['B01']['compiled_spec']}
    prepared = {**annual, 'source_proofs':selected['source_proofs']}
    try:
        computed = calculate_selected_income(repo_root=Path(repo_root), prepared=prepared,
            inventory=preparation['inventory'], primary_source=preparation['primary'],
            facts_source=preparation['facts'], xml_source=preparation['xml'],
            metric_id='B03', spec=spec, dependency_specs=dependencies, target=target,
            period=period, traits=repository_company_traits(repo_root=ROOT, company_id=company_id),
            validate_revenue_scope=True, revenue_scope_contract='reported-total-v2',
            allow_single_revenue_line=True, validate_depreciation_scope=True,
            namespace_policy=YEAR_OR_DATE_RELEASE, annual_period_reader=annual_period,
            filing_inventory_source=preparation.get('filing_inventory_source'))
    except (IncomeSourceError, NormalZeroAiError) as error:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
            reason_code='NORMAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED')
        computed = {'dependency_records':[], 'observations':[], 'trace':trace, 'result':result,
            'source_sets':[], 'selection':{'reason':str(error),
                'category':getattr(error,'category','SOURCE_SCOPE_UNRESOLVED')},
            'revenue_scope':None, 'depreciation_scope':None, 'original_checks':[]}
    results = {'B03':computed['result']}
    traces = {'B03':computed['trace']}
    for record in computed['dependency_records']:
        if record['record_type']=='METRIC_RESULT':results[record['metric_id']]=record
        if record['record_type']=='EXECUTION_TRACE':traces[record['metric_id']]=record
    records = list({content_hash(value=r):r for r in [*preparation['records'],
        *computed['dependency_records'], *computed['observations'],
        computed['trace'], computed['result']]}.values())
    assessments = {k:computed[k] for k in ('revenue_scope','depreciation_scope')
                   if computed[k] is not None}
    assessments['original_income_checks'] = computed['original_checks']
    body = {'record_type':'HISTORICAL_SELECTED_INCOME_CASE_INPUT',
        'selected_sources':preparation['input_binding'], 'target':target,
        'spec_closure_hashes':{m:docs[m]['compiled_spec']['spec_closure_hash'] for m in ('B01','B03')},
        'source_set_manifests':computed['source_sets'], 'selection':computed['selection'],
        'input_assessments':assessments}
    return {'kind':'STRUCTURED', 'primary_metric_id':'B03', 'input_binding':body,
        'compiled_specs':{'B03':spec, **dependencies},
        'spec_paths':{m:docs[m]['path'] for m in ('B01','B03')},
        'target_period':period, 'prepared_annual_input':annual, 'expected_records':records,
        'results':results, 'traces':traces, 'observations':computed['observations'],
        'references':[r for r in preparation['records'] if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':selected['source_proofs'], 'admission':selected['admission'],
        'selection':computed['selection'], 'input_assessments':assessments, 'rules_root':str(ROOT)}
