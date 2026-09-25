"""Prototype: explicit host physical roles plus complete model source coverage.

This derivation creates no request execution, source admission, Run or credit.
Unsupported quantity shapes stay source obligations regardless of model labels.
"""
import re
from xml.sax.saxutils import quoteattr
from xml.etree import ElementTree
from .canonical import content_hash,sha256_bytes
from .capacity_quantity_roles import (physical_quantity_role_proofs,_fact_timing,
    unsupported_quantity_constructions,validate_quantity_role_findings,_industry_scope)
from .capacity_quantity_scope import quantity_qualification,local_context_blocks
from .capacity_utilization_source import _quantity_context_qualified,need

VERSION='B13_PROGRAM_QUANTITY_ROLES_V1'
RESERVED_QUANTITY_KINDS={'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY'}


def native_quantity_candidate_name(qualified_name):
    """Recognize a quantity-relation family, never infer its numeric role."""
    local=qualified_name.rsplit(':',1)[-1]
    tokens={token.lower() for token in re.findall(r'[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+',local)}
    return bool(tokens&{'capacity','utilization'} or (tokens&{'production','manufacturing','produced','manufactured','output'}
        and tokens&{'actual','volume','quantity','quantities','unit','units','output','count'}))


def _supplement_text(item):
    raw=item['raw_xml']
    need(sha256_bytes(content=raw.encode())==item['raw_xml_sha256'],'B13_PROGRAM_SUPPLEMENT_BYTES_CHANGED')
    attributes=' '.join(('xmlns:'+key if key else 'xmlns')+'='+quoteattr(value) for key,value in item['namespaces'].items())
    root=ElementTree.fromstring('<root '+attributes+'>'+raw+'</root>')
    return ' '.join(' '.join(root.itertext()).split())


def quantity_contract(*,units,period,scope):
    from .capacity_semantic_source import native_capacity_roles
    all_blocks=[(u,b) for u in units if u['kind']=='VISIBLE_TEXT' for b in u['payload']['blocks']]
    findings=[];proofs=[];constraints=[];native_nonphysical=[];unresolved=[]
    for unit,block in all_blocks:
        context=local_context_blocks(blocks=[b for u,b in all_blocks if u['document_id']==unit['document_id']],
            block=block,document_id=unit['document_id'],scope=scope)
        for fact in physical_quantity_role_proofs(block['text']):
            qualification=quantity_qualification(block=block,document_id=unit['document_id'],scope=scope,statement=fact)
            if qualification in {'HYPOTHETICAL_HTML_HEADING_SCOPE','EXPLICIT_PRECEDING_NONACTUAL_QUANTITIES'} or _quantity_context_qualified(
                quoted=block['html_quotation_context'],context=context):continue
            if qualification or _fact_timing(fact,period)=='UNRESOLVED':
                unresolved.append({'unit_id':unit['unit_id'],'source_index':block['block_index'],
                    'reason':qualification or 'B13_PROGRAM_QUANTITY_TIMING_UNSUPPORTED'})
                continue
            body={'unit_id':unit['unit_id'],'kind':'VISIBLE_BLOCK','source_index':block['block_index'],
                'raw_span_sha256':block['raw_span_sha256'],'fact':fact,
                'finding_kind':fact['basis'],'subject':'TARGET_REGISTRANT','timing':_fact_timing(fact,period),
                'annual_ratio_comparability_proven':False}
            proof={**body,'program_proof_id':content_hash(value=body)};proofs.append(proof)
            findings.append({'unit_id':unit['unit_id'],'kind':fact['basis'],'subject':'TARGET_REGISTRANT','timing':_fact_timing(fact,period),
                'reason':'Program-verified original physical role; the Calculator separately verifies period and scope comparability.',
                'resolved_evidence':[{'kind':'VISIBLE_BLOCK','source_index':block['block_index'],'text':block['text']}]})
        forbidden=[timing for timing in ['CURRENT_REPORT','HISTORICAL','CONDITIONAL']
                   if _industry_scope([block['text']],timing,period)=='OTHER_ENTITY']
        if forbidden:
            constraints.append({'unit_id':unit['unit_id'],'kind':'VISIBLE_BLOCK','source_index':block['block_index'],
                'forbidden_target_capacity_timings':forbidden,
                'reason':'Original industry assertion has no same-period target-capacity assertion; no other kind or timing inferred.'})
    findings=list({content_hash(value=f):f for f in findings}.values())
    unresolved.extend(validate_quantity_role_findings(units=units,findings=findings,period=period,quantity_scope=scope))
    native_roles={(r['unit_id'],r['source_index']):r for r in native_capacity_roles(units)}
    census=[]
    for unit in units:
        if unit['kind']=='VISIBLE_TEXT':
            census.append({'unit_id':unit['unit_id'],'kind':unit['kind'],'items':len(unit['payload']['blocks'])});continue
        if unit['kind']=='NATIVE_FACTS':
            census.append({'unit_id':unit['unit_id'],'kind':unit['kind'],'items':len(unit['payload']['facts'])})
            for row in unit['payload']['facts']:
                fact=row['fact'];key=(unit['unit_id'],fact['ordinal']);role=native_roles.get(key)
                if role and role['role']=='MONETARY_CREDIT_FACILITY_CAPACITY':
                    native_nonphysical.append(role);continue
                if role or native_quantity_candidate_name(fact['qualified_name']) or unsupported_quantity_constructions(fact['text']) or physical_quantity_role_proofs(fact['text']):
                    unresolved.append({'unit_id':unit['unit_id'],'kind':'NATIVE_FACT','source_index':fact['ordinal'],
                        'reason':'B13_PROGRAM_NATIVE_QUANTITY_ROLE_IMPLEMENTATION_UNSUPPORTED'})
        elif unit['kind']=='NATIVE_SUPPLEMENTS':
            census.append({'unit_id':unit['unit_id'],'kind':unit['kind'],'items':sum(1+len(o['nested_objects']) for o in unit['payload']['objects'])})
            for index,item in enumerate(unit['payload']['objects']):
                text=_supplement_text(item)
                if unsupported_quantity_constructions(text) or physical_quantity_role_proofs(text):
                    unresolved.append({'unit_id':unit['unit_id'],'kind':'NATIVE_SUPPLEMENT','source_index':index,
                        'reason':'B13_PROGRAM_SUPPLEMENT_QUANTITY_SCOPE_IMPLEMENTATION_UNSUPPORTED'})
        else:need(False,'B13_PROGRAM_SOURCE_KIND_UNSUPPORTED')
    body={'version':VERSION,'required_unit_ids':[u['unit_id'] for u in units],
        'source_unit_census':census,'program_quantity_proofs':proofs,'program_findings':findings,
        'source_constraints':constraints,'verified_nonphysical_native_roles':native_nonphysical,
        'implementation_unresolved':unresolved,'model_must_review_all_units':True,
        'model_reserved_quantity_kinds':sorted(RESERVED_QUANTITY_KINDS),'new_call_credit':False}
    return {**body,'program_contract_id':content_hash(value=body)}


def program_source(source):
    """Explicit successor identity; the old source object is never modified."""
    need(source['metric_id']=='B13' and source['source_serialization_complete'] is True
         and source['semantic_source_id']==content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'}),
         'B13_PROGRAM_COMPLETE_SOURCE_REQUIRED')
    need('program_quantity_role_contract_version' not in source,'B13_PROGRAM_SOURCE_ALREADY_SELECTED')
    body={k:v for k,v in source.items() if k!='semantic_source_id'}
    body['program_quantity_role_contract_version']=VERSION
    return {**body,'semantic_source_id':content_hash(value=body)}


def request_contract(*,units,period,scope,complete=None):
    """Readonly source annotations use a different shape from model findings."""
    complete=quantity_contract(units=units,period=period,scope=scope) if complete is None else complete
    ids={u['unit_id'] for u in units}
    complete={**complete,**{key:[row for row in complete[key] if row['unit_id'] in ids] for key in
        ['source_unit_census','program_quantity_proofs','program_findings','source_constraints','verified_nonphysical_native_roles','implementation_unresolved']},
        'required_unit_ids':[u['unit_id'] for u in units]}
    body={'version':VERSION,'required_unit_ids':complete['required_unit_ids'],
        'source_unit_census':complete['source_unit_census'],
        'verified_quantity_roles':[{'program_proof_id':p['program_proof_id'],'unit_id':p['unit_id'],
            'source_kind':p['kind'],'source_index':p['source_index'],'quantity_role':p['finding_kind'],
            'assertion_subject':p['subject'],'assertion_timing':p['timing'],'original_quantity':p['fact'],
            'annual_ratio_comparability_proven':False} for p in complete['program_quantity_proofs']],
        'verified_nonphysical_references':[{'unit_id':p['unit_id'],'source_kind':'NATIVE_FACT','source_index':p['source_index'],
            'role_assessment_id':p['role_assessment_id'],'quantity_disposition':'VERIFIED_MONETARY_NOT_PHYSICAL'}
            for p in complete['verified_nonphysical_native_roles']],
        'source_constraints':complete['source_constraints'],'implementation_unresolved':complete['implementation_unresolved'],
        'program_owned_roles_need_no_model_acknowledgement':True,'all_source_units_need_model_response':True}
    return {**body,'contract_id':content_hash(value=body)},complete


def verify_request_contract(request,units,source):
    need(source is not None and source.get('program_quantity_role_contract_version')==VERSION
         and source.get('record_type')=='B13_COMPLETE_SEMANTIC_SOURCE' and source.get('metric_id')=='B13'
         and source.get('source_serialization_complete') is True
         and source.get('required_unit_ids')==[u['unit_id'] for u in source['units']]
         and len(set(source['required_unit_ids']))==len(source['units'])
         and source['semantic_source_id']==request['source_id']
         and source['semantic_source_id']==content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
         and source['company_id']==request['company_id']
         and source['prepared_annual_input']['table_input']['target_period']==request['target_period'],
         'B13_PROGRAM_COMPLETE_SOURCE_REQUIRED')
    ids={u['unit_id'] for u in units}
    need([u for u in source['units'] if u['unit_id'] in ids]==units,'B13_PROGRAM_REQUEST_UNIT_SET_CHANGED')
    whole=quantity_contract(units=source['units'],period=request['target_period'],scope=source.get('quantity_scope_context'))
    expected,complete=request_contract(units=units,period=request['target_period'],scope=request.get('quantity_scope_context'),complete=whole)
    need(request.get('program_quantity_role_contract_version')==VERSION and request.get('program_quantity_contract')==expected,
         'B13_PROGRAM_SOURCE_PROOFS_CHANGED')
    return complete,whole


def original_program_records(*,source,raw_bytes_by_id):
    """Rebuild programme-owned roles after verifying the original HTML bytes."""
    from .capacity_quantity_scope import verified_scope
    scope=verified_scope(source=source,raw_bytes_by_id=raw_bytes_by_id)
    return quantity_contract(units=source['units'],period=source['prepared_annual_input']['table_input']['target_period'],scope=scope)


def verify_original_program_assessment(*,source,assessment,raw_bytes_by_id,actual_requests=None):
    """The same original-source proof check serves text and numeric Runs."""
    from .native_unit_index import reconstruct_requests,restore_base_request
    from .capacity_semantic_review import _restore_units
    original=original_program_records(source=source,raw_bytes_by_id=raw_bytes_by_id)
    need(not original['implementation_unresolved'],'B13_PROGRAM_ORIGINAL_SOURCE_IMPLEMENTATION_UNRESOLVED')
    if actual_requests is None:
        requests=reconstruct_requests(source,assessment.get('native_request_variants'))
    else:
        from .native_unit_index import validate_request_partition
        requests=actual_requests
        need(validate_request_partition(source, requests)==assessment.get('native_request_variants'),
             'B13_PROGRAM_ORIGINAL_REQUEST_PARTITION_CHANGED')
    need([r['request_id'] for r in requests]==assessment['required_request_ids']
         and [r['request_id'] for r in requests]==[r['request_id'] for r in assessment['completed']],
         'B13_PROGRAM_ORIGINAL_REQUEST_SET_CHANGED')
    proofs=[];native=[]
    for request,row in zip(requests,assessment['completed']):
        base=restore_base_request(request) if 'indexed_unit_contract' in request else request
        from .capacity_reference_contract import SCANNED_VERSION
        if base.get('source_reference_contract', {}).get('version') == SCANNED_VERSION:
            from .capacity_two_stage import restore_prior_interpretation_request
            base=restore_prior_interpretation_request(base)
        contract,program=request_contract(units=_restore_units(base['units'],base['shared_source_dictionaries']),
            period=base['target_period'],scope=base.get('quantity_scope_context'),complete=original)
        need(base['program_quantity_contract']==contract,'B13_PROGRAM_REQUEST_ORIGINAL_PROOFS_CHANGED')
        expected={'contract_id':contract['contract_id'],'program_quantity_proofs':program['program_quantity_proofs'],
            'verified_nonphysical_native_roles':program['verified_nonphysical_native_roles']}
        need(row['candidate']['selected']['source_assessment'].get('program_quantity_contract')==expected,
             'B13_NATIVE_PROGRAM_ORIGINAL_PROOFS_CHANGED')
        proofs.extend(program['program_quantity_proofs']);native.extend(program['verified_nonphysical_native_roles'])
    need(proofs==original['program_quantity_proofs'] and native==original['verified_nonphysical_native_roles'],
         'B13_PROGRAM_ORIGINAL_ROLE_CENSUS_CHANGED')
