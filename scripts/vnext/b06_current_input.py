"""Check current debt/equity input effects before any ordinary B06 result.

This adds a debt-specific use of the existing full amendment mechanics. The
B08/B09 policy and its result are not enlarged or relabelled. Every current
amendment stays in the Run source graph; debt composition remains independent.
"""
from pathlib import Path
import re

from .annual_amendment_scope import inspect_annual_amendment_scope, prepare_saved_amendment_scopes
from .instant_balance_amendment import _part_iii_details, POLICY as BALANCE_POLICY
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import resolve_repository_file


POLICY_PATH = 'config/b06_current_input_v1.json'
POLICY = strict_json_file(path=ROOT/POLICY_PATH)


def _need(condition, reason):
    if not condition: raise ValueError('B06_CURRENT_INPUT_'+reason)


def inspect_current_debt_amendment(*, original, amendment, company_id, cik):
    scope = inspect_annual_amendment_scope(original=original,amendment=amendment,company_id=company_id,cik=cik)
    decision = 'WITHHELD'; details = {}; issues = []
    try:
        _need(scope['fiscal_window_unchanged'] and not scope['issues'],'AMENDMENT_SCOPE_UNRESOLVED')
        if 'ORIGINAL_STATEMENT_VALUES' in scope['unchanged_input_classes']:
            details = {'unchanged_original_statement_scope':scope['scope_id']}
        else:
            _need(scope['classification']=='PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',
                  'AMENDMENT_KIND_UNSUPPORTED')
            details = _part_iii_details(scope,amendment['raw'])
            conflicts = []
            for block in scope['amendment']['document']['blocks']:
                text = block['text']
                correction = re.search(POLICY['financial_subject_pattern'],text,re.I) and re.search(BALANCE_POLICY['revision_pattern'],text,re.I)
                amount = re.search(POLICY['current_amount_pattern'],text,re.I)
                if correction or amount: conflicts.append(block)
            _need(not conflicts,'DEBT_EQUITY_CHANGE_UNRESOLVED:'+','.join(str(b['block_index']) for b in conflicts))
            details['debt_equity_conflicts'] = conflicts
        decision = 'INPUT_PROPERTY_PROVEN'
    except ValueError as error:
        issues.append({'reason':str(error),'error_type':type(error).__name__})
    body = exact_json_value({'record_type':'B06_CURRENT_AMENDMENT_EFFECT','input_class':POLICY['input_class'],
        'metric_ids':['B06'],'decision':decision,'scope_id':scope['scope_id'],'details':details,'issues':issues,
        'policy_sha256':sha256_file(path=ROOT/POLICY_PATH),'original_accession':original['filing']['accessionNumber'],
        'amendment_accession':amendment['filing']['accessionNumber'],'source_acquisition_credit':False,
        'annual_continuity_proven':False,'debt_completeness_proven':False,'production_authorized':False})
    return {**body,'effect_id':content_hash(value=body)}


def prepare_current_debt_input(*, repo_root:Path, company_id:str):
    path = resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(path.read_bytes()==(ROOT/POLICY_PATH).read_bytes() and strict_json_file(path=path)==POLICY,'INSTALLED_POLICY_CHANGED')
    packet = prepare_saved_amendment_scopes(repo_root=repo_root,company_id=company_id)
    blobs = {r['raw_asset_id']:r for r in packet['source_records'] if r['record_type']=='RAW_BLOB'}
    checks = []
    for scope in packet['scopes']:
        args = {}
        for role in ['original','amendment']:
            source = scope[role]; blob = blobs[source['source_reference']['raw_asset_id']]
            args[role] = {'raw':resolve_repository_file(repo_root=repo_root,repo_relative_path=blob['storage_uri']).read_bytes(),
                          'blob':blob,'reference':source['source_reference'],'filing':source['filing']}
        checks.append(inspect_current_debt_amendment(**args,company_id=company_id,cik=packet['prepared_input']['entity']))
    body = exact_json_value({**packet,'record_type':'B06_CURRENT_INPUT','input_class':POLICY['input_class'],
        'metric_ids':['B06'],'checks':checks,'decision':'INPUT_PROPERTY_PROVEN' if all(c['decision']=='INPUT_PROPERTY_PROVEN' for c in checks) else 'WITHHELD',
        'current_primary_only':True,'per_metric_statement_scope_required':True,
        'annual_continuity_proven':False,'debt_completeness_proven':False,'policy_sha256':sha256_file(path=path)})
    return {**body,'current_input_id':content_hash(value=body)}


def bind_current_debt_input(*, case, packet, repo_root):
    """Retain every amendment before native graph comparison and persistence."""
    _need(packet['decision']=='INPUT_PROPERTY_PROVEN','UNPROVEN_INPUT_CANNOT_BIND_RESULT')
    annual = packet['prepared_input']; end = annual['filing']['reportDate']
    _need(case['target_period']['period_start']==case['target_period']['period_end']==end,
          'RESULT_MUST_BE_CURRENT_INSTANT')
    trace = case['traces']['B06']; target = trace['calculation_target']
    if case['results']['B06']['publication']=='PUBLISHED':
        _need(target.get('entity')==annual['entity'] and target.get('accession')==annual['filing']['accessionNumber'],
              'RESULT_CURRENT_REGISTRANT_SCOPE_UNPROVEN')
    source_records = list({content_hash(value=r):r for r in [*case['source_records'],*packet['source_records']]}.values())
    proofs = list({content_hash(value=p):p for p in [*case['source_proofs'],*packet['source_proofs']]}.values())
    records = [r for r in case['expected_records'] if r['record_type'] not in {'RAW_BLOB','SOURCE_REFERENCE'}]
    return {**case,'source_records':source_records,'references':[r for r in source_records if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':proofs,'admission':verify_ordinary_source_proofs(data_root=repo_root,proofs=proofs),
        'expected_records':[*source_records,*records],
        'input_binding':{**case['input_binding'],'current_debt_input':packet}}


def withheld_current_debt_case(*, repo_root, company_id, packet):
    from .normal_candidates import _prepare_b06
    from .normal_annual_input_v2 import prepare_saved_annual_input
    from .specs import compile_spec_file
    from .calculator import withheld_metric_result
    preparation = _prepare_b06(repo_root=repo_root,company_id=company_id)
    annual = prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    end = annual['filing']['reportDate']; scope = {'entity_scope':'consolidated'}
    target = {'company_id':company_id,'entity':annual['entity'],'accession':annual['filing']['accessionNumber'],
              'period_start':end,'period_end':end,'scope':scope,'scope_key':content_hash(value=scope)}
    path = 'catalog/r5/B06_new_source_v2.md'; spec = compile_spec_file(path=repo_root/path,dependency_specs={})
    simple_target = {k:target[k] for k in ['company_id','period_start','period_end','scope','scope_key']}
    result,trace = withheld_metric_result(compiled_spec=spec,target=simple_target,reason_code='B06_CURRENT_INPUT_UNRESOLVED')
    records = list({content_hash(value=r):r for r in [*preparation['records'],*packet['source_records']]}.values())
    proofs = list({content_hash(value=p):p for p in [*preparation['input_binding']['source_proofs'],*annual['source_proofs'],*packet['source_proofs']]}.values())
    selection = {'classification':'CURRENT_INPUT_SCOPE_UNRESOLVED','reason':'B06_CURRENT_INPUT_UNRESOLVED',
                 'amendment_checks':packet['checks'],'equity_guard_evaluated':False,'debt_evaluated':False}
    return {'kind':'STRUCTURED','primary_metric_id':'B06','input_binding':{'original_source_input':preparation['input_binding'],
        'annual_label_input':annual,'current_debt_input':packet},'source_records':records,
        'references':[r for r in records if r['record_type']=='SOURCE_REFERENCE'],'source_proofs':proofs,
        'admission':verify_ordinary_source_proofs(data_root=repo_root,proofs=proofs),'spec_paths':{'B06':path},'compiled_specs':{'B06':spec},
        'target_period':{'fiscal_year':annual['table_input']['target_period']['fiscal_year'],'period_start':end,'period_end':end},
        'expected_records':[*records,trace,result],'results':{'B06':result},'traces':{'B06':trace},'observations':[],'selection':selection}
