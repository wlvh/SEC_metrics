"""Current B06 through existing source grammars and the ordinary record writer.

Sources remain at the requested data root. Installed rules and business
composition are the existing program's; there is no new debt selector or Run.
"""
from pathlib import Path

from .canonical import content_hash
from .normal_source_authority import ROOT
from .normal_governance_input import prepare_saved_original_financial_sources
from .normal_annual_input_v2 import prepare_saved_annual_input
from .b06_current_input import (prepare_current_debt_input, bind_current_debt_input,
                                withheld_current_debt_case)
from .ordinary_debt_guard import prepare_current_guarded_b06_result
from .ordinary_special_debt_scope import prepare_special_debt_case
from .normal_note_debt_results import prepare_note_debt_case
from .normal_bond_debt_results import prepare_bond_debt_case
from .normal_inclusive_debt_results import prepare_inclusive_debt_case
from .ordinary_b06_resolution import _b06_resolution
from .specs import compile_spec_file


PROCESSING_FILES=tuple('scripts/vnext/'+name+'.py' for name in (
    'current_b06_case','ordinary_b06_resolution','normal_governance_input',
    'b06_current_input','annual_amendment_scope','instant_balance_amendment',
    'normal_annual_input_v2','fiscal_year_labels','ordinary_debt_guard',
    'b06_guarded_result_v3','ordinary_special_debt_scope','normal_note_debt_results',
    'normal_bond_debt_results','normal_inclusive_debt_results','b06_note_carrying',
    'b06_bond_leases','b06_inclusive_table','b06_financing_inventory',
    'b06_combined_borrowings','b06_disclosure_v2','b06_disclosure','r5_b06_scope',
    'r5_b06_measurement','ordinary_source_authority',
)) + (
    'config/b06_current_input_v1.json','config/annual_amendment_scope_v1.json',
    'config/normal_fiscal_year_labels_v1.json','config/b06_special_scope_v1.json',
    'config/b06_note_carrying_v1.json','config/b06_bond_leases_v1.json',
    'config/b06_inclusive_table_v1.json','config/r5_b06_debt_sets_v3.json',
    'config/b06_bond_debt_set_v1.json','catalog/r5/B06_new_source_v2.md',
    'catalog/r5/B06_guarded_v3.md','catalog/r5/B06_note_carrying_v4.md',
    'catalog/r5/B06_bond_leases_v5.md','catalog/r5/B06_inclusive_table_v6.md',
)


class CurrentB06Error(ValueError):
    def __init__(self,reason):
        super().__init__(reason)
        self.category='IMPLEMENTATION_GAP'


def _need(condition,reason):
    if not condition:raise CurrentB06Error(reason)


def _case_from_resolution(*, preparation, annual, spec_path, resolution):
    records=preparation['records']
    proofs=list({content_hash(value=p):p for p in [
        *preparation['input_binding']['source_proofs'],*annual['source_proofs']]}.values())
    result,trace=resolution['result'],resolution['trace']
    observations=resolution.get('observations',())
    return {'kind':'STRUCTURED','primary_metric_id':'B06',
        'input_binding':{'original_source_input':preparation['input_binding'],
                         'annual_label_input':annual,'selection':resolution['selection']},
        'source_records':records,'references':[r for r in records if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':proofs,'spec_paths':{'B06':spec_path},
        'compiled_specs':{'B06':compile_spec_file(path=ROOT/spec_path,dependency_specs={})},
        'target_period':{'fiscal_year':annual['table_input']['target_period']['fiscal_year'],
                         'period_start':result['period_start'],'period_end':result['period_end']},
        'expected_records':[*records,*observations,trace,result],
        'results':{'B06':result},'traces':{'B06':trace},
        'observations':observations,'selection':resolution['selection']}


def _display_selection(selection):
    """Keep ordinary CSV small; complete source/audit details stay in assessments."""
    audit=selection.get('audit') or selection.get('measurement') or {}
    displayed={key:selection[key] for key in ('classification','reason','reason_code','debt_completeness')
               if key in selection}
    displayed['selection_detail_id']=content_hash(value=selection)
    if isinstance(audit,dict):
        displayed['calculation']={key:audit[key] for key in
            ('branch','debt','equity','nonpositive_equity','resolver','selection_id') if key in audit}
    return displayed


def prepare_current_b06_case(*, source_root, company_id):
    source=Path(source_root)
    packet=prepare_current_debt_input(repo_root=source,company_id=company_id,rules_root=ROOT)
    preparation=prepare_saved_original_financial_sources(repo_root=source,company_id=company_id)
    annual=prepare_saved_annual_input(repo_root=source,company_id=company_id,ordinary_registered=True)
    original=preparation['input_binding']['prepared_annual_input']
    _need(original['company_id']==annual['company_id']==company_id
          and original['entity']==annual['entity']
          and all(original['filing'][k]==annual['filing'][k] for k in
                  ('accessionNumber','reportDate','primaryDocument'))
          and packet['prepared_input']['filing']==original['filing'],
          'B06_CURRENT_SELECTED_SOURCE_CHANGED')
    if packet['decision']!='INPUT_PROPERTY_PROVEN':
        case=withheld_current_debt_case(repo_root=source,company_id=company_id,packet=packet,
            rules_root=ROOT,preparation=preparation,annual_input=annual)
    else:
        guard=prepare_current_guarded_b06_result(repo_root=source,company_id=company_id,
            rules_root=ROOT,preparation=preparation)
        if guard['status']=='NOT_MEANINGFUL':
            case=_case_from_resolution(preparation=preparation,annual=annual,
                spec_path=guard['spec_path'],resolution={
                    'result':guard['result'],'trace':guard['trace'],'observations':guard['observations'],
                    'selection':{'reason_code':guard['reason_code'],
                                 'debt_completeness':'NOT_EVALUATED','equity_proof':guard['equity_proof']}})
        elif guard['reason_code']=='EXISTING_SPECIAL_SCOPE_REQUIRED':
            case=prepare_special_debt_case(repo_root=source,company_id=company_id,
                rules_root=ROOT,preparation=preparation)
            _need(case is not None,'B06_SEPARATE_BANK_OR_INDUSTRIAL_SCOPE_NOT_IMPLEMENTED')
        else:
            case=None
            for producer in (prepare_note_debt_case,prepare_bond_debt_case,prepare_inclusive_debt_case):
                case=producer(repo_root=source,company_id=company_id,rules_root=ROOT,
                    preparation=preparation,annual_input=annual)
                if case is not None:break
            if case is None:
                spec_path,resolution=_b06_resolution(data_root=ROOT,preparation=preparation)
                case=_case_from_resolution(preparation=preparation,annual=annual,
                    spec_path=spec_path,resolution=resolution)
        case=bind_current_debt_input(case=case,packet=packet,repo_root=source)
    return {**case,'prepared_annual_input':annual,'rules_root':str(ROOT),
        'selection':_display_selection(case['selection']),
        'input_assessments':{'B06':{'selection_detail_id':content_hash(value=case['selection']),
            'current_input_decision':packet['decision'],
            'amendment_checks':packet['checks'],'source_route':case['spec_paths']['B06'],
            'selection':case['selection']}},
        'new_calls':{'provider':0,'paid':0,'sec':0}}
