"""Ordinary B10/B11 records from rebuilt reported lodging table cells."""
from pathlib import Path

from sec_urls import submissions_url,companyfacts_url
from .calculator import calculate_observation_metric,metric_is_applicable,withheld_metric_result
from .canonical import content_hash,sha256_file
from .lodging_table_source import prepare_saved_lodging_source,LodgingSourceError,POLICY_PATH
from .normal_annual_input_v2 import prepare_saved_annual_input,exact_json_value
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .observations import structured_observation,scope_key
from .sources import resolve_repository_file
from .specs import compile_spec_file
from .traits import repository_company_traits
from .zero_ai_r2 import _manual_result_trace


SPEC_PATHS={m:'catalog/ordinary_lodging/'+m+'.md' for m in ['B10','B11']}


def _need(condition,reason):
    if not condition:raise ValueError(reason)


def _spec(root,metric):
    path=SPEC_PATHS[metric]
    _need(sha256_file(path=resolve_repository_file(repo_root=root,repo_relative_path=path))==sha256_file(path=ROOT/path),
          'ORDINARY_LODGING_INSTALLED_SPEC_CHANGED')
    spec=compile_spec_file(path=root/path,dependency_specs={});semantic=spec['compiled'];rule=semantic['quality_rule']
    _need(rule['resolver']=='ordinary_lodging_table_v1' and rule['source_policy']==POLICY_PATH
          and rule['source_policy_sha256']==sha256_file(path=ROOT/POLICY_PATH),'ORDINARY_LODGING_SOURCE_POLICY_CHANGED')
    original=compile_spec_file(path=ROOT/rule['original_metric_spec'],dependency_specs={})
    _need(rule['original_metric_spec_sha256']==sha256_file(path=ROOT/rule['original_metric_spec']),
          'ORDINARY_LODGING_ORIGINAL_SPEC_CHANGED')
    fields=['metric_id','kind','canonical_unit','reported_unit','applicability','required_claims',
            'scope_contract','forbidden_confusions','inputs','formula','top_level_guards','dependencies']
    _need(all(semantic[k]==original['compiled'][k] for k in fields),'ORDINARY_LODGING_ECONOMIC_DEFINITION_CHANGED')
    return spec


def prepare_ordinary_lodging_case(*,repo_root:Path,company_id:str,metric_id:str):
    _need(metric_id in SPEC_PATHS,'ORDINARY_LODGING_METRIC_UNSUPPORTED')
    spec=_spec(repo_root,metric_id)
    prepared=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    period=prepared['table_input']['target_period'];traits=repository_company_traits(repo_root=repo_root,company_id=company_id)
    reader=_Sources(repo_root,company_id,prepared['entity'])
    reader.read(submissions_url(cik=int(prepared['entity'])),role='sec_submissions_inventory',media_type='application/json')
    primary=reader.primary(prepared['filing'])
    reader.read(companyfacts_url(cik=int(prepared['entity'])),accession=prepared['filing']['accessionNumber'],role='companyfacts',media_type='application/json')
    scope={k:v for k,v in spec['compiled']['required_claims'].items() if k!='period_role'}
    target={'company_id':company_id,'period_start':period['period_start'],'period_end':period['period_end'],
            'scope':scope,'scope_key':scope_key(scope=scope)}
    observations=[];assets=[];source_component=None;selection=None
    if not metric_is_applicable(applicability=spec['compiled']['applicability'],traits=traits):
        result,trace=_manual_result_trace(metric_id=metric_id,company_id=company_id,
            period_start=period['period_start'],period_end=period['period_end'],scope=scope,spec_closure_hash=spec['spec_closure_hash'],
            applicability='N_A_STRUCTURAL',quality='NONE',reason_code='TRAIT_NOT_APPLICABLE',input_observation_ids=[],
            steps=[{'event':'N_A_STRUCTURAL'}],accession=None,entity=None,unit=None)
        selection={'classification':'STRUCTURAL','reason_code':'TRAIT_NOT_APPLICABLE'}
    else:
        try:
            source_component=prepare_saved_lodging_source(repo_root=repo_root,company_id=company_id)
            component=source_component['component'];fact=component['selection']['facts'][metric_id]
            _need(source_component['prepared_input']==prepared and component['source_reference']==primary['source_reference'],
                  'ORDINARY_LODGING_SOURCE_SELECTION_CHANGED')
            _need(fact['scope']==scope and fact['period']==period,'ORDINARY_LODGING_SCOPE_OR_PERIOD_CHANGED')
            reference=primary['source_reference'];witnesses=fact['source_witnesses'];amount=witnesses['amount']
            binding={'raw_asset_id':reference['raw_asset_id'],'source_reference_id':reference['source_reference_id'],
                'source_role':reference['source_role'],'document_name':reference['document_name'],'accession':reference['accession'],
                'entity':prepared['entity'],'form':prepared['filing']['form'],'filed':prepared['filing']['filingDate'],
                'derived_asset_id':component['derived_asset']['derived_asset_id'],'table_locator':amount['locator'],
                'reported_raw_text':amount['raw_text'],'reported_value':fact['reported_value'],'reported_unit':fact['reported_unit'],
                'source_witnesses':witnesses,'source_component_id':component['component_id'],
                'period_basis':fact['period_basis'],'ordinary_source_policy_hash':component['policy_hash']}
            observation=structured_observation(metric_id=metric_id,semantic_role=fact['semantic_role'],
                company_id=company_id,period_start=period['period_start'],period_end=period['period_end'],scope=scope,
                value=fact['value'],unit=fact['unit'],quality='EXACT',source_binding=binding)
            result,trace=calculate_observation_metric(compiled_spec=spec,target=target,company_traits=traits,observation=observation)
            observations=[observation];assets=[component['derived_asset']]
            selection={'classification':'DETERMINISTIC_REPORTED_TABLE','reason_code':result['reason_code'],
                'table_id':component['selection']['table_id'],'source_component_id':component['component_id'],
                'source_witnesses':witnesses,'period_basis':fact['period_basis'],'ai_response_used':False,
                'qualification_credit':False}
        except LodgingSourceError as error:
            result,trace=withheld_metric_result(compiled_spec=spec,target=target,reason_code='ORDINARY_LODGING_SOURCE_UNRESOLVED')
            selection={'classification':'SOURCE_OR_IMPLEMENTATION_UNRESOLVED','reason':str(error),'reason_code':result['reason_code']}
    proofs=list({content_hash(value=p):p for p in [*prepared['source_proofs'],*[x['proof'] for x in reader.proofs.values()]]}.values())
    admission=verify_ordinary_source_proofs(data_root=repo_root,proofs=proofs);records=list(reader.records.values())
    binding=exact_json_value({'record_type':'ORDINARY_LODGING_INPUT','prepared_input':prepared,'source_component':source_component,
        'source_proofs':proofs,'source_admission':admission,'selection':selection,'module_sha256':sha256_file(path=Path(__file__))})
    return {'kind':'STRUCTURED','primary_metric_id':metric_id,'input_binding':binding,
        'source_records':records,'references':[r for r in records if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':proofs,'admission':admission,'spec_paths':{metric_id:SPEC_PATHS[metric_id]},
        'compiled_specs':{metric_id:spec},'target_period':period,'expected_records':[*records,*assets,*observations,trace,result],
        'results':{metric_id:result},'traces':{metric_id:trace},'observations':observations,'selection':selection}
