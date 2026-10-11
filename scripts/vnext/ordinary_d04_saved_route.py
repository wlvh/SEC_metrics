"""D04-only saved model dispatch and consumed dependencies.

Other metrics do not load this producer or include its bytes in their input
configuration. This adapter never creates a new provider execution.
"""

METRIC_IDS = frozenset({'D04'})


def prepare_case(*, source_root, company_id, metric_id):
    if metric_id != 'D04':
        raise ValueError('SAVED_MODEL_ROUTE_NOT_IMPLEMENTED')
    from .current_d04_result import prepare_current_d04_case
    return prepare_current_d04_case(source_root=source_root, company_id=company_id)


def processing_paths():
    paths = {'scripts/vnext/ordinary_d04_saved_route.py'}
    # This route rebuilds annual text/native units and rechecks original
    # responses. Name the consumed rules, not a recursive authority tree:
    # unchanged SEC bytes cannot preserve credit after these rules change.
    paths.update('scripts/vnext/'+name+'.py' for name in (
        'current_d04_result','current_request_configuration','continuous_semantic_calls',
        'continuous_request_context','request_limits','continuous_call_ledger',
        'native_assessment_replay','capacity_native_assessment','capacity_update_input',
        'd04_native_assessment','r6_semantic_source','r6_semantic_review',
        'native_unit_index','capacity_text_results','text_results','text_review','review',
        'going_concern_source','text_business_candidates','text_coverage',
        'regulatory_investigation_candidates','normal_annual_input_v2','fiscal_year_labels',
        'ordinary_source_authority','text_results_v2','capacity_semantic_review',
        'capacity_utilization_source','invocation_control','continuous_call_policy'))
    paths.update({'config/issue28_current_request_runtime_v1.json',
        'config/issue28_continuous_calls_v1.json','config/normal_fiscal_year_labels_v1.json',
        'catalog/r6/going_concern_source_rules_v1.json','catalog/r6/semantic_source_v1.json',
        'catalog/r6/semantic_review_v1.json','catalog/r6/text_business_candidates_v1.json',
        'catalog/r6/regulatory_investigation_candidates_v1.json',
        'catalog/r6/text_results_v2_policy.json',
        'catalog/r6/D04_going_concern_assessment_v1.md',
        'catalog/r6/semantic_review_v4.json','catalog/r6/semantic_review_v5.json'})
    return paths
