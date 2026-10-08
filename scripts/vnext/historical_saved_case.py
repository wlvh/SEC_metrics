"""Thin B01/B03 component-to-case adapter for the public ordinary writer.

The existing historical source producer selects and calculates. This adapter
checks its record set and retains its source, Spec, period and result IDs; the
public writer/controller owns persistence, recovery and unchanged-input reuse.
"""
from pathlib import Path


def prepare_historical_income_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Select the saved issuer year once and adapt the existing calculation."""
    from .normal_source_authority import ROOT
    from .normal_period_selection import resolve_period_selection
    from .historical_zero_ai_results import resolve_historical_zero_ai_metric
    selected = resolve_period_selection(repo_root=Path(repo_root), company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    component = resolve_historical_zero_ai_metric(repo_root=Path(repo_root),
        company_id=company_id, metric_id=metric_id, period_selection=selected, rules_root=ROOT)
    return case_from_historical_component(component=component, rules_root=ROOT)


def case_from_historical_component(*, component, rules_root):
    metric = component['metric_id']
    if metric not in {'B01', 'B03'}:
        raise ValueError('HISTORICAL_SAVED_CASE_FAMILY_NOT_RECEIVED')
    records = component['records']
    specs = {metric: component['compiled_spec'], **component['dependency_specs']}
    expected = {metric, *component['compiled_spec']['compiled']['dependencies']}
    results, traces = {}, {}
    for record in records:
        if record['record_type'] not in {'METRIC_RESULT', 'EXECUTION_TRACE'}:
            continue
        target = results if record['record_type'] == 'METRIC_RESULT' else traces
        key = record['metric_id']
        if key in target:
            raise ValueError('HISTORICAL_SAVED_CASE_DUPLICATE_RESULT_OR_TRACE')
        target[key] = record
    if set(specs) != expected or set(results) != expected or set(traces) != expected:
        raise ValueError('HISTORICAL_SAVED_CASE_DEPENDENCY_SET_INCOMPLETE')
    if results[metric] != component['result'] or traces[metric] != component['trace']:
        raise ValueError('HISTORICAL_SAVED_CASE_PRIMARY_RECORD_CHANGED')
    for key, result in results.items():
        if (result['company_id'] != component['company_id']
                or result['trace_id'] != traces[key]['trace_id']
                or result['spec_closure_hash'] != specs[key]['spec_closure_hash']
                or any(result[p] != component['target_period'][p] for p in ('period_start', 'period_end'))):
            raise ValueError('HISTORICAL_SAVED_CASE_COORDINATE_OR_SPEC_CHANGED')
    from .normal_zero_ai_results import B01_SPEC_PATH, B03_SPEC_PATH
    paths = {'B01': B01_SPEC_PATH, 'B03': B03_SPEC_PATH}
    assessments = {}
    selection = component['selection']
    if selection.get('income_period_evidence') is not None:
        assessments['income_period'] = {'reason_code': selection['reason_code'],
            'category': selection['category'], 'evidence': selection['income_period_evidence']}
    if selection.get('depreciation_scope') is not None:
        assessments['depreciation_scope'] = selection['depreciation_scope']
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric,
        'input_binding': component['input_binding'],
        'compiled_specs': specs, 'spec_paths': {key: paths[key] for key in expected},
        'target_period': component['target_period'], 'prepared_annual_input': component['prepared_input'],
        'expected_records': records, 'results': results, 'traces': traces,
        'references': component['source_references'], 'source_proofs': component['source_proofs'],
        'admission': component['source_admission'], 'selection': selection,
        'rules_root': str(Path(rules_root)),
        **({'prepared_income_input': component['prepared_income_input'],
            'income_observation_checks': component['income_observation_checks']}
           if component.get('prepared_income_input') is not None else {}),
        **({'input_assessments': assessments} if assessments else {})}
