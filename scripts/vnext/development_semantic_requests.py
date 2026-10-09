"""Explicit offline resource-aware semantic envelopes; never a send interface.

Reuse PR66 request construction/digest/response usage checks. The existing
live semantic module keeps its original file bytes and factory contract.
"""
import json
from .canonical import content_hash, sha256_bytes, strict_json_loads
from .continuous_semantic_calls import _json, usage_observation
from .request_limits import configured_limits

def request_body(request, policy, *, limits=None):
    limits = configured_limits(limits)
    payload = {k:v for k,v in request.items() if k not in
        {'system_prompt','provider_request_sent','provider_tokens_measured','production_authorized'}}
    from .native_unit_index import evidence_json_bytes
    encode = evidence_json_bytes if request.get('metric_id') in {'B13', 'D03', 'D04'} else _json
    return encode({'model':policy.model,'messages':[
        {'role':'system','content':request['system_prompt']},
        {'role':'user','content':json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))}],
        'response_format':{'type':'json_object'},'temperature':0,'max_tokens':limits.output_tokens,
        'stream':False,'thinking':{'type':'disabled'}})

def request_digest(request, policy, *, limits=None):
    """New code/provenance IDs alone do not authorize another extraction."""
    body = {'model':policy.model,'system_prompt':request['system_prompt'],
        'target_cik':request['target_cik'],'target_period':request['target_period'],
        'fiscal_label_context':request['fiscal_label_context'],
        'filing':request['document_context']['filing'],
        'units':[{'kind':u['kind'],'payload':u['payload']} for u in request['units']],
        'response_protocol':request['response_protocol'],
        'category_definitions':request['category_definitions'],
        'required_candidate_assessments':request['required_candidate_assessments'],
        # Semantic input IDs do not grant a redraw. Actual decoding settings
        # belong to the request, including the repaired thinking-mode setting.
        'provider_parameters':{k:v for k,v in strict_json_loads(
            text=request_body(request,policy,limits=limits).decode()).items() if k not in {'messages'}}}
    if request['record_type']=='D03_SEMANTIC_VERIFICATION_REQUEST':
        body['verification']={'proposals':request['proposals'],
            'prior_assistant_output_sha256':request['prior_assistant_output_sha256']}
    if request.get('source_statement_facts'):
        body['source_statement_facts'] = request['source_statement_facts']
    if 'source_fact_candidates' in request:
        body['source_fact_candidates'] = request['source_fact_candidates']
        body['source_fact_review_contract'] = request['source_fact_review_contract']
    if 'shared_source_dictionaries' in request:
        body['shared_source_dictionaries'] = request['shared_source_dictionaries']
    if request.get('metric_id') == 'B13':
        body['native_capacity_role_assessments'] = request['native_capacity_role_assessments']
    for field in ('program_quantity_role_contract_version','program_quantity_contract',
                  'quantity_scope_context', 'quantity_scope_instructions', 'response_contract_version',
                  'required_response_unit_ids', 'unit_response_requirements',
                  'unit_index_requirements', 'scan_contract', 'two_stage_contract',
                  'two_stage_scan'):
        if field in request:
            body[field] = request[field]
    if 'indexed_unit_contract' in request:
        # A source/request identity alone never permits a redraw. The complete
        # original ID remains bound in HTTP bytes, request, plan and receipt;
        # this digest compares semantic inputs and the response contract only.
        body['indexed_unit_contract'] = {k:v for k,v in request['indexed_unit_contract'].items()
                                         if k != 'base_request_id'}
    if 'source_reference_contract' in request:
        body['source_reference_contract'] = {k:v for k,v in request['source_reference_contract'].items()
                                              if k != 'base_request_id'}
    return sha256_bytes(content=_json(body))

def usage_error(raw, *, expected_prompt_tokens=None, enforce_total_context=False, limits=None):
    explicit_limits = limits is not None
    limits = configured_limits(limits)
    observed = usage_observation(raw)
    if observed['input_tokens'] is None or observed['output_tokens'] is None:return 'USAGE_UNKNOWN'
    usage = strict_json_loads(text=raw.decode())['usage']
    total = usage.get('total_tokens')
    if type(total) is not int or total != observed['input_tokens']+observed['output_tokens']:
        return 'USAGE_UNKNOWN'
    hit,miss = observed['cache_hit_input_tokens'],observed['cache_miss_input_tokens']
    for key,value in [('prompt_cache_hit_tokens',hit),('prompt_cache_miss_tokens',miss)]:
        if key in usage and value is None:return 'USAGE_UNKNOWN'
    if hit is not None and miss is not None and hit+miss!=observed['input_tokens']:return 'USAGE_UNKNOWN'
    if observed['input_tokens'] > limits.max_context_tokens or (enforce_total_context and total > limits.max_context_tokens):
        return 'CONTEXT_LIMIT'
    if explicit_limits and observed['output_tokens'] > limits.output_tokens:
        return 'OUTPUT_LIMIT'
    if expected_prompt_tokens is not None and observed['input_tokens'] != expected_prompt_tokens:
        return 'CONTEXT_REFERENCE_MISMATCH'
    return ''
