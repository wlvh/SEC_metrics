"""Current B06 through existing source grammars and the ordinary record writer.

Sources remain at the requested data root. Installed rules and business
composition are the existing program's; there is no new debt selector or Run.
"""
from pathlib import Path
from decimal import Decimal
import re

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
from .calculator import withheld_metric_result


PROCESSING_FILES=tuple('scripts/vnext/'+name+'.py' for name in (
    'current_b06_case','ordinary_b06_resolution','normal_governance_input',
    'b06_current_input','annual_amendment_scope','instant_balance_amendment',
    'normal_annual_input_v2','fiscal_year_labels','ordinary_debt_guard',
    'b06_guarded_result_v3','ordinary_special_debt_scope','normal_note_debt_results',
    'normal_bond_debt_results','normal_inclusive_debt_results','b06_note_carrying',
    'b06_bond_leases','b06_inclusive_table','b06_financing_inventory',
    'b06_combined_borrowings','ordinary_reported_lease_scope','industrial_lease_relation','b06_disclosure_v2','b06_disclosure','r5_b06_scope',
    'r5_b06_measurement','ordinary_source_authority','text_results_v2',
)) + (
    'config/b06_current_input_v1.json','config/annual_amendment_scope_v1.json',
    'config/instant_balance_amendment_v1.json',
    'config/normal_fiscal_year_labels_v1.json','config/b06_special_scope_v1.json',
    'config/b06_note_carrying_v1.json','config/b06_bond_leases_v1.json',
    'config/b06_inclusive_table_v1.json','config/r5_b06_debt_sets_v3.json',
    'config/b06_bond_debt_set_v1.json','catalog/r5/B06_new_source_v2.md',
    'catalog/r5/B06_guarded_v3.md','catalog/r5/B06_note_carrying_v4.md',
    'catalog/r5/B06_bond_leases_v5.md','catalog/r5/B06_inclusive_table_v6.md',
)

# Explicit consumers using the existing inline paragraph readers must name
# their dependencies. Current default consumers do not load those readers.
INLINE_NOTE_PROCESSING_FILES=PROCESSING_FILES+tuple('scripts/vnext/'+name+'.py' for name in (
    'annual_amendment_scope_v2','instant_balance_amendment_v2','amendment_note_layout'))


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
    if selection.get('scope_class') is not None:
        displayed.update({k:selection[k] for k in ('scope_class','reasons','reported_subtotal') if k in selection})
        relationship=selection.get('scope_source',{}).get('lease_inclusion',{})
        if relationship:
            displayed['lease_inclusion']={k:relationship[k] for k in
                ('status','additional_debt_amount','component_total') if k in relationship}
    displayed['selection_detail_id']=content_hash(value=selection)
    if isinstance(audit,dict):
        displayed['calculation']={key:audit[key] for key in
            ('branch','debt','equity','nonpositive_equity','resolver','selection_id') if key in audit}
    return displayed


def _unresolved_current_interest(preparation, annual):
    """Retain reported current interest whose debt-set relation is unproved.

    The existing bond inventory does not select InterestPayableCurrent.
    Its positive amount cannot silently disappear from a completeness claim;
    neither adding it nor excluding it is authorized by this check.
    """
    from .deterministic_router import parse_accession_xbrl_source
    from .text_results_v2 import _ReportedFactMetadata
    from .governance_signals import _source_value
    rows=[]
    end=annual['filing']['reportDate']
    for kind in ('primary','xml'):
        source=preparation[kind];raw=source['raw_bytes']
        parsed=parse_accession_xbrl_source(raw_bytes=raw)
        metadata=_ReportedFactMetadata();metadata.feed(raw.decode('utf-8-sig'));metadata.close()
        for fact in parsed.facts:
            item=metadata.facts[fact['ordinal']];namespace,name=item['concept']
            if name.casefold()!='interestpayablecurrent' or not re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',namespace):
                continue
            context=parsed.contexts[fact['context_ref']]
            if (context['period_start']!=end or context['period_end']!=end
                    or str(int(context['entity_identifier']))!=annual['entity']
                    or context['dimensions'] or context['typed_dimension_count']):
                continue
            _need(metadata.units.get(fact['unit_ref'])=={
                'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
                'B06_CURRENT_INTEREST_UNIT_UNRESOLVED')
            value=_source_value(fact,item)
            if Decimal(value)!=0:
                rows.append({'source_kind':kind,'source_reference':source['source_reference'],
                    'ordinal':fact['ordinal'],'context_ref':fact['context_ref'],
                    'concept':name,'period_end':end,'value':value,'unit':'USD'})
    return rows


def prepare_current_b06_case(*, source_root, company_id):
    source=Path(source_root)
    packet=prepare_current_debt_input(repo_root=source,company_id=company_id,rules_root=ROOT)
    preparation=prepare_saved_original_financial_sources(repo_root=source,company_id=company_id)
    annual=prepare_saved_annual_input(repo_root=source,company_id=company_id,ordinary_registered=True)
    return prepare_selected_b06_case(source_root=source,company_id=company_id,
        preparation=preparation,annual=annual,packet=packet)


def prepare_selected_b06_case(*, source_root, company_id, preparation, annual, packet):
    """Compose the existing B06 route for an already source-selected period.

    The consumer prepares original sources, issuer year and amendment effects;
    this shared route keeps source identity checks and the current cascade.
    It does not discover another year or accept a supplied numerical answer.
    """
    source=Path(source_root)
    original=preparation['input_binding']['prepared_annual_input']
    _need(original['company_id']==annual['company_id']==company_id
          and packet['prepared_input']['company_id']==company_id
          and original['entity']==annual['entity']
          and packet['prepared_input']['entity']==original['entity']
          and all(original['filing'][k]==annual['filing'][k] for k in
                  ('accessionNumber','reportDate','primaryDocument'))
          and all(original['table_input']['target_period'][k]==annual['table_input']['target_period'][k]
                  ==packet['prepared_input']['table_input']['target_period'][k]
                  for k in ('period_start','period_end'))
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
            from .ordinary_reported_lease_scope import prepare_reported_lease_case
            case=prepare_reported_lease_case(repo_root=source,company_id=company_id,
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
        if (case['results']['B06']['publication']=='PUBLISHED'
                and case['results']['B06']['quality']!='NOT_MEANINGFUL'
                and case['traces']['B06']['calculation_target']['scope'].get('entity_scope')=='consolidated'):
            unresolved=_unresolved_current_interest(preparation,annual)
            if unresolved:
                original_target=case['traces']['B06']['calculation_target']
                target={k:original_target[k] for k in
                    ('company_id','period_start','period_end','scope','scope_key')}
                result,trace=withheld_metric_result(compiled_spec=case['compiled_specs']['B06'],
                    target=target,reason_code='B06_SOURCE_RELATIONSHIP_UNRESOLVED')
                case=_case_from_resolution(preparation=preparation,annual=annual,
                    spec_path=case['spec_paths']['B06'],resolution={
                        'result':result,'trace':trace,'observations':[],
                        'selection':{'classification':'SOURCE_OR_RELATIONSHIP_UNRESOLVED',
                            'reason':'B06_REPORTED_INTEREST_DEBT_SCOPE_UNRESOLVED',
                            'reported_interest':unresolved,'component_selection':case['selection']}})
        case=bind_current_debt_input(case=case,packet=packet,repo_root=source)
    return {**case,'prepared_annual_input':annual,'rules_root':str(ROOT),
        'selection':_display_selection(case['selection']),
        'input_assessments':{'B06':{'selection_detail_id':content_hash(value=case['selection']),
            'current_input_decision':packet['decision'],
            'amendment_checks':packet['checks'],'source_route':case['spec_paths']['B06'],
            'selection':case['selection']}},
        'new_calls':{'provider':0,'paid':0,'sec':0}}
