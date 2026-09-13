"""B13 approved source scope and Calculator inputs, before native integration.

Candidate excerpts never prove absence of a numeric pair. This module keeps
the two required quantity roles and rejects substitution/scope drift; actual
numeric extraction, semantic coverage, Review and native Run credit remain
separate from this source-preparation result.
"""
from datetime import date
from pathlib import Path
import re

from .canonical import content_hash, strict_json_file, sha256_file
from .continuous_call_policy import delegation_fields
from .normal_annual_input import prepare_saved_annual_input
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .specs import compile_spec_file
from .text_coverage import build_text_document
from .text_results import text_claim_from_block
from .deterministic_router import parse_accession_xbrl_source
from .calculator import calculate_metric

POLICY_PATH='config/b13_production_capacity_v1.json'


def need(value,reason):
    if not value:raise ValueError(reason)


def policy():
    rules=strict_json_file(path=ROOT/POLICY_PATH)
    approved=strict_json_file(path=ROOT/rules['approval_policy'])
    comment=strict_json_file(path=ROOT/approved['delegation_record_path'])
    delegation_fields(comment,policy=approved)
    return rules,approved['b13']


def prepare_capacity_sources(*, repo_root:Path, company_id:str):
    rules,approved=policy()
    need(strict_json_file(path=repo_root/POLICY_PATH)==rules,'B13_INSTALLED_RULES_CHANGED')
    need(company_id in approved['applicable_company_ids'],'B13_OUTSIDE_APPROVED_APPLICABILITY')
    annual=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    reader=_Sources(repo_root,company_id,annual['entity']);original=reader.primary(annual['filing'])
    admission=verify_ordinary_source_proofs(data_root=repo_root,proofs=annual['source_proofs'])
    document=build_text_document(raw_bytes=original['raw_bytes'],raw_blob=original['raw_blob'],
        source_reference=original['source_reference'],expected_company_id=company_id,
        expected_cik=annual['entity'],expected_period_end=annual['filing']['reportDate'])
    need(document['source_state']=='COMPLETE_LOCAL_DOCUMENT','B13_SOURCE_DOCUMENT_INCOMPLETE')
    parsed=parse_accession_xbrl_source(raw_bytes=original['raw_bytes'])
    related=re.compile(rules['related_production_capacity_pattern'],re.I)
    possible=re.compile(rules['possible_actual_production_pattern'],re.I)
    disclosures=[];potential=[]
    for block in document['blocks']:
        if related.search(block['text']):
            disclosures.append(text_claim_from_block(document=document,section_id='CAPACITY_DISCLOSURES',
                block_index=block['block_index'],order=len(disclosures),extent='FULL_BLOCK'))
        if possible.search(block['text']):
            potential.append(text_claim_from_block(document=document,section_id='POSSIBLE_ACTUAL_PRODUCTION',
                block_index=block['block_index'],order=len(potential),extent='FULL_BLOCK'))
    native=[dict(f) for f in parsed.facts if re.search(r'capacity|utilization|actualproduction|productionvolume',
                                                    f['qualified_name'],re.I)]
    body={'record_type':'B13_SOURCE_CANDIDATES','company_id':company_id,'metric_id':'B13',
        'annual':annual,'source_reference':original['source_reference'],'raw_blob':original['raw_blob'],
        'source_proofs':annual['source_proofs'],'source_admission':admission,
        'document_id':document['text_document_id'],'complete_document_block_count':len(document['blocks']),
        'related_disclosures':disclosures,'possible_actual_production':potential,'native_quantity_candidates':native,
        'amendment_scope_proven':not annual['amendments'],
        'source_status':'RELATED_DISCLOSURES_FOUND' if disclosures else 'SOURCE_INTERPRETATION_REQUIRED',
        'numeric_pair_completeness_verified':False,'absence_established':False,
        'candidate_text_status':'TEXT_QUAL' if disclosures else None,
        'native_result_created':False,'review_complete':False,'production_authorized':False,
        'rule_sha256':sha256_file(path=ROOT/POLICY_PATH),'calls':{'provider':0,'paid':0,'sec':0}}
    return {**body,'source_candidate_id':content_hash(value=body)}


def calculate_comparable_pair(*, target, production, capacity):
    """Development calculation for already source-verified quantity roles.

    This is not a public source-admission API. Its return carries no native Run
    or source credit; the future extractor must independently establish the
    role assignments and source evidence before feeding the shared Calculator.
    """
    rules,approved=policy()
    need(target['company_id'] in approved['applicable_company_ids'],'B13_OUTSIDE_APPROVED_APPLICABILITY')
    need(target['scope'].get('capacity_basis')=='actual_production_over_available_capacity',
         'B13_TARGET_MEANING_CHANGED')
    required={'basis','value','unit','entity','period_start','period_end','product_or_facility_scope','source_binding'}
    need(set(production)==required and set(capacity)==required,'B13_QUANTITY_FIELDS_CHANGED')
    need(production['basis']=='ACTUAL_PRODUCTION' and capacity['basis']=='AVAILABLE_CAPACITY',
         'B13_REQUIRED_QUANTITY_ROLE_MISSING')
    for field in ['unit','entity','period_start','period_end','product_or_facility_scope']:
        need(production[field]==capacity[field] and bool(production[field]),'B13_INCOMPARABLE_'+field.upper())
    need(all(production[k]==target[k] for k in ['entity','period_start','period_end'])
         and target['scope']['product_or_facility_scope']==production['product_or_facility_scope'],
         'B13_TARGET_SCOPE_CHANGED')
    from .canonical import parse_decimal
    need(parse_decimal(value=production['value'])>=0 and parse_decimal(value=capacity['value'])>0,
         'B13_QUANTITY_OR_CAPACITY_NOT_POSITIVE')
    facts=[]
    for role,quantity in [('ActualProduction',production),('AvailableCapacity',capacity)]:
        binding=quantity['source_binding']
        need(binding.get('entity')==target['entity'] and binding.get('accession')==target['accession'],
             'B13_SOURCE_BINDING_CHANGED')
        fact={'concept':'b13:'+role,'value':quantity['value'],'unit':quantity['unit'],
            'entity':quantity['entity'],'period_start':quantity['period_start'],'period_end':quantity['period_end'],
            'accession':target['accession'],'filed':binding['filing_date'],'form':'10-K','fiscal_period':'FY',
            'duration_days':(date.fromisoformat(quantity['period_end'])-date.fromisoformat(quantity['period_start'])).days+1,
            'source_binding':binding}
        facts.append({**fact,'fact_id':content_hash(value=fact)})
    spec=compile_spec_file(path=ROOT/rules['numeric_spec'],dependency_specs={})
    result,trace,observations=calculate_metric(compiled_spec=spec,target=target,company_traits=[],
        structured_facts=facts,verified_observations=[])
    return {'result':result,'trace':trace,'observations':observations,'source_assignments_independently_verified':False,
            'native_result_created':False,'production_authorized':False}
