"""Selected historical D04 through the shared saved-response producer."""
from pathlib import Path

from .historical_d04_selection import prepare_historical_d04_selection
from .saved_d04_replay import prepare_selected_saved_d04_case


METRICS = ('D04',)
PROCESSING_FILES = tuple('scripts/vnext/' + name + '.py' for name in (
    'historical_d04_case', 'historical_d04_selection', 'historical_annual_input',
    'historical_dei', 'historical_fiscal_labels', 'normal_period_selection',
    'saved_d04_replay', 'current_d04_result', 'd04_native_assessment',
    'capacity_native_assessment', 'native_unit_index', 'continuous_semantic_calls',
    'continuous_request_context', 'native_request_construction', 'invocation_control',
)) + ('config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json')


def historical_d04_factory(*, saved_call_package):
    """Bind a read-only package; the controller separately tracks its bytes."""
    package = Path(saved_call_package).expanduser().resolve()

    def prepare(*, repo_root, company_id, metric_id, fiscal_year):
        if metric_id != 'D04':
            raise ValueError('HISTORICAL_D04_METRIC_REQUIRED')
        selection = prepare_historical_d04_selection(source_root=repo_root,
            company_id=company_id, fiscal_year=fiscal_year, saved_call_package=package)
        return prepare_selected_saved_d04_case(source_root=repo_root, selection=selection)

    return prepare
