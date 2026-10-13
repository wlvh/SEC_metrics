"""Selected-year RPO substitute through the existing native instant case.

RPO is a reported stock at the selected fiscal-year end, not ARR or churn.
No current/latest filing is substituted; source checks and ordinary storage
retain their existing implementations.
"""
from .historical_capital_cases import (
    _prepare_selected_native_year_case, PROCESSING_FILES as NATIVE_FILES)

METRICS = frozenset({'B12'})
PROCESSING_FILES = (*NATIVE_FILES, 'scripts/vnext/historical_rpo_cases.py')


def prepare_historical_rpo_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id not in METRICS:
        raise ValueError('HISTORICAL_RPO_FAMILY_NOT_RECEIVED')
    case = _prepare_selected_native_year_case(repo_root=repo_root,
        company_id=company_id, metric_id=metric_id, fiscal_year=fiscal_year)
    case['input_binding']['record_type'] = 'HISTORICAL_RPO_SOURCE_INPUT'
    if case['results'][metric_id]['publication'] == 'WITHHELD':
        # Keep the shared source failure; name the consumer's actual family.
        case['input_assessments'] = {'rpo_source': case['selection']}
    return case
