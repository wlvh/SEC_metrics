"""Selected C04 annual roles consume the single public four-form core."""
from .historical_governance_input import prepare_selected_auditor_base
from .c04_registration_successor import prepare_c04_registration_case, EVENT_FORMS, SPEC_PATH

METRICS = frozenset({'C04'})
DEI_RELEASE = 'YEAR_QUARTER_OR_DATE'
PROCESSING_FILES = tuple('scripts/vnext/'+name+'.py' for name in (
    'historical_auditor_case', 'historical_governance_input',
    'historical_annual_input', 'historical_dei', 'historical_fiscal_labels',
    'normal_period_selection', 'normal_history_catalog', 'normal_annual_input',
    'normal_annual_input_v2', 'normal_governance_input',
    'c04_registration_successor', 'c04_verified_document_alias',
    'governance_signals', 'deterministic_router', 'calculator', 'specs',
    'records', 'sources', 'canonical', 'ordinary_source_authority')) + (
    SPEC_PATH, 'catalog/r5/C04_auditor_changes_v2.md',
    'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json')


def prepare_historical_auditor_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Select sources, then use public annual comparison/census/calculation."""
    if metric_id != 'C04':
        raise ValueError('HISTORICAL_AUDITOR_FAMILY_NOT_RECEIVED')
    prepared = prepare_selected_auditor_base(repo_root=repo_root,
        company_id=company_id, fiscal_year=fiscal_year)
    case = prepare_c04_registration_case(repo_root=repo_root, company_id=company_id,
        event_forms=EVENT_FORMS, selected_base=prepared['base'],
        labelled_annual=prepared['labelled_annual'], dei_release=DEI_RELEASE)
    annual = prepared['labelled_annual']
    expected = annual['table_input']['target_period']
    if any(case['target_period'][key] != expected[key]
           for key in ('fiscal_year', 'period_start', 'period_end')):
        raise ValueError('HISTORICAL_AUDITOR_SELECTED_PERIOD_CHANGED')
    case['prepared_annual_input'] = annual
    complete = case['selection']
    case['input_assessments'] = {'historical_auditor': complete}
    # Complete facts, source sets and item claims remain in ordinary evidence;
    # daily output names the scope rather than embedding the full event pool.
    case['selection'] = {key: complete[key] for key in (
        'selection_id', 'resolver', 'selected_current_accession',
        'names_differ', 'reason_code', 'same_cik_prior_status') if key in complete}
    case['selection']['event_forms'] = list(EVENT_FORMS)
    case['selection']['matched_item_4_01_claim_ids'] = complete.get('matched_item_4_01_claim_ids', [])
    case['selection']['event_source_set_ids'] = [entry['manifest']['source_set_manifest_id']
        for entry in complete.get('event_source_sets', [])]
    return case
