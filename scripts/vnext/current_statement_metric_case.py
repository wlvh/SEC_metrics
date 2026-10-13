"""Current B04/B07 select the actual latest saved period and reuse one core."""
from pathlib import Path

from .normal_annual_input_v2 import prepare_saved_annual_input
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .canonical import strict_json_file
from .historical_statement_cases import (_prepare_historical_statement_case,
    processing_files_for_statement_metric)

METRICS=frozenset({'B04','B07'})
PROCESSING_FILES=tuple(dict.fromkeys((*processing_files_for_statement_metric('B04'),
    'scripts/vnext/current_statement_metric_case.py',
    'scripts/vnext/normal_annual_input.py','scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/fiscal_year_labels.py','config/normal_fiscal_year_labels_v1.json')))


def prepare_current_statement_metric_case(*,source_root,company_id,metric_id):
    if metric_id not in METRICS:raise ValueError('CURRENT_STATEMENT_METRIC_NOT_SUPPORTED')
    route=strict_json_file(path=ROOT/'catalog/deterministic_metrics.json')['metrics'][metric_id]
    if (route['adapter_id']!='companyfacts' or route['result_period_role']!='current_annual'
            or not all(c['accession_role']=='current' and c['period_role']=='current_annual'
                for branch in route['branches'] for c in branch['components'])):
        raise ValueError('CURRENT_STATEMENT_SOURCE_ROLE_CHANGED')
    source=Path(source_root)
    current=prepare_saved_annual_input(repo_root=source,company_id=company_id,ordinary_registered=True)
    period=current['table_input']['target_period']
    selection=resolve_period_selection(repo_root=source,company_id=company_id,
        report_end=period['period_end'],rules_root=ROOT)
    case=_prepare_historical_statement_case(repo_root=source,company_id=company_id,
        metric_id=metric_id,fiscal_year=period['fiscal_year'],period_selection=selection,
        withhold_known_source_errors=True)
    filing_fields=('accessionNumber','form','reportDate','filingDate','primaryDocument')
    if (case['primary_metric_id']!=metric_id or case['target_period']!=period
            or {k:case['prepared_annual_input']['filing'][k] for k in filing_fields}
                !={k:current['filing'][k] for k in filing_fields}
            or case['prepared_annual_input']['entity']!=current['entity']):
        raise ValueError('CURRENT_STATEMENT_SELECTED_SOURCE_CHANGED')
    # Existing selected-case records and input identity remain intact. This
    # additional assessment records the current selection, not an online
    # freshness claim or permission to use a previous/foreign filing.
    case={**case,'input_assessments':{**case.get('input_assessments',{}),
        'current_statement_selection':{'company_id':company_id,'metric_id':metric_id,
            'selection_rule':current['selection_rule'],'filing':current['filing'],
            'entity':current['entity'],'target_period':period,'ordinary_annual_input_id':current['input_id'],
            'current_sec_freshness_verified':False}}}
    return case
