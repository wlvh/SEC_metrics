"""Latest A13 uses the existing original-source geographic revenue calculation."""
from .ordinary_financial_results import resolve_current_financial_metric
from .normal_source_authority import ROOT

METRICS=frozenset({'A13'})
PROCESSING_FILES=tuple('scripts/vnext/'+name+'.py' for name in (
    'current_geography_case','ordinary_financial_results','financial_results','financial_structured',
    'financial_duration','financial_relationships','financial_candidates','financial_balance_scope',
    'normal_annual_input_v2','normal_annual_input','fiscal_year_labels','normal_governance_input',
    'composite_scope','constraints','specs','traits','r4_task_contracts','table_task_contracts','table_grid')) + (
    'catalog/r4_normal/A13_geographic_exposure.md','catalog/r4_v2/A13_geographic_exposure.md',
    'catalog/table_task_contracts.json','config/r4_task_contracts_v2.json',
    'docs/evidence/issue_28_prb_policy_revision.json','config/normal_fiscal_year_labels_v1.json')


def prepare_current_geography_case(*,source_root,company_id):
    resolved=resolve_current_financial_metric(repo_root=source_root,company_id=company_id,
        metric_id='A13',rules_root=ROOT)
    period=resolved['target_period'];result=resolved['result'];spec=resolved['compiled_spec']
    fact=resolved['source_fact']
    selection=dict(resolved['selection'])
    if fact is not None:
        selection['source_summary']={'outcome':fact['outcome'],'regional_sum_used':fact['regional_sum_used'],
            'selected':[{ 'locator':item['claim']['locator'],
                'source_reference_id':item['claim']['source_reference_id'],
                'geography':item['source_witness']['geography_label']['text'],
                'revenue_meaning':item['source_witness']['revenue_measure']['interpretation']}
                for item in fact['selected']]}
    return {'kind':'STRUCTURED','primary_metric_id':'A13','input_binding':resolved['input_binding'],
        'compiled_specs':{'A13':spec},'spec_paths':{'A13':resolved['spec_path']},'target_period':period,
        'references':resolved['source_references'],'source_proofs':resolved['source_proofs'],
        'admission':resolved['source_admission'],'expected_records':resolved['records'],
        'results':{'A13':result},'traces':{'A13':resolved['trace']},
        'prepared_annual_input':resolved['prepared_input'],'rules_root':str(ROOT),
        'selection':selection,
        'input_assessments':{'current_geography':{'input_binding':resolved['input_binding'],
            'source_fact':resolved['source_fact'],'selection':resolved['selection']}}}
