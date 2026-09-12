"""D04 interpretation request/response binding, not semantic certification.

This offline protocol gives a model every source unit and rejects omitted
reviews, missed known candidates, false quotations and inconsistent categories.
A structurally valid response remains a model proposal. No provider call,
qualification, native Run, approval or production credit is created here.
"""
from pathlib import Path
import json

from .canonical import content_hash,sha256_bytes,sha256_file,strict_json_file,strict_json_loads
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .r6_semantic_source import prepare_d04_semantic_source,_bytes
from .sources import resolve_repository_file

POLICY_PATH='catalog/r6/semantic_review_v1.json'
POLICY=strict_json_file(path=ROOT/POLICY_PATH)


class SemanticReviewError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise SemanticReviewError(reason)


def requests_from_source(source):
    """Pure serialization; a caller-created source object has no source credit."""
    _need(source['metric_id']=='D04' and source['source_serialization_complete'],
          'D04_COMPLETE_SOURCE_REQUIRED')
    _need(strict_json_file(path=ROOT/POLICY_PATH)==POLICY,'D04_REVIEW_POLICY_CHANGED_DURING_PROCESS')
    _need(source['semantic_source_id']==content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'}),
          'D04_SOURCE_ID_CHANGED')
    _need(source['required_unit_ids']==[u['unit_id'] for u in source['units']]
          and len(set(source['required_unit_ids']))==len(source['units']),'D04_UNIT_SET_CHANGED')
    documents={d['document_id']:d for d in source['documents']};groups=[];current=[];size=0
    for unit in source['units']:
        unit_size=len(_bytes(unit));_need(unit_size<=POLICY['max_request_source_bytes'],'D04_SINGLE_UNIT_TOO_LARGE')
        if current and (size+unit_size>POLICY['max_request_source_bytes'] or current[0]['document_id']!=unit['document_id']):
            groups.append(current);current=[];size=0
        current.append(unit);size+=unit_size
    if current:groups.append(current)
    requests=[]
    for group in groups:
        document=documents[group[0]['document_id']]
        context={k:document[k] for k in ('document_id','filing','registrant_name_binding',
                                       'language_candidate_block_indices','native_candidate_ordinals')}
        body=exact_json_value({'record_type':'D04_INTERPRETATION_REQUEST','source_id':source['semantic_source_id'],
            'company_id':source['company_id'],'target_cik':source['prepared_annual_input']['entity'],
            'target_period':source['prepared_annual_input']['table_input']['target_period'],
            'fiscal_label_context':{key:source['prepared_annual_input']['fiscal_year_label_resolution'][key]
                for key in ('selected_fiscal_year','basis','original_dei_fiscal_year',
                            'original_companyfacts_fiscal_year_values','metadata_conflict_retained')},
            'document_context':context,'system_prompt':POLICY['system_prompt'],'units':group,
            'response_protocol':{'root_fields':['request_id','units'],'unit_fields':['unit_id','reviewed','findings','unresolved'],
                'finding_fields':['kind','subject','timing','evidence','reason'],
                'evidence_fields':['kind','source_index','text'],
                'evidence_kinds':['VISIBLE_BLOCK','NATIVE_FACT','NATIVE_SUPPLEMENT'],
                'finding_kinds':POLICY['kinds'],'subjects':POLICY['subjects'],'timings':POLICY['timings']},
            'policy_sha256':sha256_file(path=ROOT/POLICY_PATH),'provider_request_sent':False,
            'provider_tokens_measured':False,'production_authorized':False})
        requests.append({**body,'request_id':content_hash(value=body)})
    return requests


def _source_items(unit):
    kind=unit['kind'];p=unit['payload']
    if kind=='VISIBLE_TEXT':return 'VISIBLE_BLOCK',{b['block_index']:b for b in p['blocks']}
    if kind=='NATIVE_FACTS':return 'NATIVE_FACT',{f['fact']['ordinal']:f['fact'] for f in p['facts']}
    if kind=='NATIVE_SUPPLEMENTS':return 'NATIVE_SUPPLEMENT',{i:f for i,f in enumerate(p['objects'])}
    raise SemanticReviewError('D04_UNKNOWN_SOURCE_UNIT_KIND')


def validate_response(*,request,raw_response):
    """Check response shape and source references; do not endorse its meaning."""
    _need(request['request_id']==content_hash(value={k:v for k,v in request.items() if k!='request_id'}),
          'D04_HOST_REQUEST_CHANGED')
    for unit in request['units']:
        raw=_bytes(unit['payload'])
        _need(unit['payload_sha256']==sha256_bytes(content=raw) and unit['payload_bytes']==len(raw)
              and unit['unit_id']==content_hash(value={k:v for k,v in unit.items() if k!='unit_id'})
              and unit['document_id']==request['document_context']['document_id'],'D04_HOST_SOURCE_UNIT_CHANGED')
    _need(type(raw_response) is bytes and len(raw_response)<=POLICY['max_response_bytes'],'D04_RESPONSE_SIZE_OR_TYPE')
    response=strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(response) is dict and set(response)=={'request_id','units'}
          and response['request_id']==request['request_id'],'D04_RESPONSE_REQUEST_BINDING')
    expected={u['unit_id']:u for u in request['units']}
    _need(type(response['units']) is list and len(response['units'])==len(expected),'D04_RESPONSE_UNIT_SET_INCOMPLETE')
    seen=set();findings=[];unresolved=[]
    for result in response['units']:
        _need(type(result) is dict and set(result)=={'unit_id','reviewed','findings','unresolved'},'D04_UNIT_RESPONSE_FIELDS')
        uid=result['unit_id'];_need(type(uid) is str and uid in expected and uid not in seen
                                  and result['reviewed'] is True,'D04_UNIT_REVIEW_MISSING_OR_DUPLICATE')
        seen.add(uid);unit=expected[uid];evidence_kind,items=_source_items(unit)
        _need(type(result['findings']) is list and len(result['findings'])<=POLICY['max_findings_per_unit'],'D04_FINDING_COUNT')
        _need(type(result['unresolved']) is list and all(type(s) is str and 0<len(s.strip())<=POLICY['max_reason_characters']
              for s in result['unresolved']),'D04_UNRESOLVED_FIELDS')
        accounted=set()
        for finding in result['findings']:
            _need(type(finding) is dict and set(finding)=={'kind','subject','timing','evidence','reason'},'D04_FINDING_FIELDS')
            kind=finding['kind'];_need(kind in POLICY['kinds'] and finding['subject'] in POLICY['subjects']
                                      and finding['timing'] in POLICY['timings'],'D04_FINDING_ENUM')
            if kind in POLICY['current_target_kinds']:
                _need(finding['subject']=='TARGET_REGISTRANT' and finding['timing']=='CURRENT_REPORT','D04_CURRENT_TARGET_CATEGORY_CONFLICT')
            for chosen,field,value in [('OTHER_ENTITY','subject','OTHER_ENTITY'),('HISTORICAL_STATEMENT','timing','HISTORICAL'),
                                       ('CONDITIONAL_OR_BOILERPLATE','timing','CONDITIONAL')]:
                if kind==chosen:_need(finding[field]==value,'D04_CATEGORY_SCOPE_CONFLICT')
            _need(type(finding['reason']) is str and 0<len(finding['reason'].strip())<=POLICY['max_reason_characters'],
                  'D04_REASON_MISSING_OR_TOO_LARGE')
            _need(type(finding['evidence']) is list and bool(finding['evidence']),'D04_SOURCE_EVIDENCE_REQUIRED')
            resolved=[]
            for evidence in finding['evidence']:
                _need(type(evidence) is dict and set(evidence)=={'kind','source_index','text'}
                      and evidence['kind']==evidence_kind and type(evidence['source_index']) is int
                      and evidence['source_index'] in items,'D04_EVIDENCE_OUTSIDE_SUPPLIED_UNIT')
                item=items[evidence['source_index']];text=item['raw_xml'] if evidence_kind=='NATIVE_SUPPLEMENT' else item['text']
                quote=evidence['text']
                _need(type(quote) is str and bool(quote.strip()) and len(quote)<=POLICY['max_quote_characters'],'D04_SOURCE_QUOTE_RANGE_INVALID')
                start=text.find(quote)
                _need(start>=0,'D04_EXACT_SOURCE_TEXT_CHANGED')
                _need(text.find(quote,start+1)<0,'D04_SOURCE_QUOTE_NOT_UNIQUE')
                end=start+len(quote)
                resolved.append({**evidence,'start_character':start,'end_character':end})
                if evidence_kind=='VISIBLE_BLOCK' and item['html_quotation_context'] and kind in POLICY['current_target_kinds']:
                    raise SemanticReviewError('D04_QUOTED_TEXT_CANNOT_ALONE_ESTABLISH_CURRENT_ASSERTION')
                accounted.add(evidence['source_index'])
            findings.append({**finding,'unit_id':uid,'resolved_evidence':resolved})
        context=request['document_context']
        required=(set(context['language_candidate_block_indices']) if evidence_kind=='VISIBLE_BLOCK' else
                  set(context['native_candidate_ordinals']) if evidence_kind=='NATIVE_FACT' else set()) & set(items)
        _need(required<=accounted,'D04_KNOWN_SOURCE_CANDIDATE_NOT_ASSESSED')
        unresolved.extend({'unit_id':uid,'reason':s} for s in result['unresolved'])
    _need(seen==set(expected),'D04_RESPONSE_UNIT_SET_INCOMPLETE')
    return {'request_id':request['request_id'],'response':exact_json_value(response),'findings':findings,
            'unresolved':unresolved,'status':'SOURCE_REFERENCES_AND_RESPONSE_SHAPE_VALID',
            'semantic_correctness_verified':False,'native_result_created':False,'production_authorized':False}


def assemble_recorded_responses(*,source,response_bytes_by_request_id):
    """Pure response composition; this API cannot confer source authenticity."""
    requests=requests_from_source(source)
    _need(set(response_bytes_by_request_id)=={r['request_id'] for r in requests},'D04_RESPONSE_REQUEST_SET_INCOMPLETE')
    checked=[validate_response(request=r,raw_response=response_bytes_by_request_id[r['request_id']]) for r in requests]
    findings=[f for c in checked for f in c['findings']];kinds={f['kind'] for f in findings}
    unresolved=[u for c in checked for u in c['unresolved']]
    current=kinds & set(POLICY['current_target_kinds'])
    if len(current)>1:
        unresolved.append({'unit_id':None,'reason':'MULTIPLE_CURRENT_CLASSIFICATIONS_REQUIRE_JOINT_INTERPRETATION'})
    # This is a proposed interpretation, never a mechanically proved absence.
    if unresolved or 'UNRESOLVED' in kinds:proposal='UNRESOLVED'
    elif 'DOUBT_DISCLOSED' in kinds:proposal='DOUBT_DISCLOSED'
    elif 'DOUBT_ALLEVIATED' in kinds:proposal='DOUBT_ALLEVIATED'
    else:proposal='NO_DOUBT_DISCLOSED'
    body=exact_json_value({'record_type':'D04_RECORDED_INTERPRETATION_CANDIDATE','source_id':source['semantic_source_id'],
        'company_id':source['company_id'],'request_ids':[r['request_id'] for r in requests],'responses':checked,
        'model_proposed_interpretation':proposal,'all_source_units_responded':True,'unresolved':unresolved,
        'response_origin':'CALLER_SUPPLIED_RECORDED_BYTES_NOT_PROVIDER_ATTESTED',
        'semantic_correctness_verified':False,'semantic_qualification_passed':False,
        'provider_execution_proven':False,'native_result_created':False,'production_authorized':False,
        'calls':{'provider':0,'paid':0,'sec':0},'module_sha256':sha256_file(path=Path(__file__))})
    return {**body,'candidate_id':content_hash(value=body)}


def inspect_recorded_responses(*,repo_root:Path,company_id:str,response_bytes_by_request_id:dict):
    """Rebuild actual source inputs before interpreting a recorded response set."""
    path=resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(strict_json_file(path=path)==POLICY==strict_json_file(path=ROOT/POLICY_PATH),'D04_INSTALLED_REVIEW_POLICY_CHANGED')
    source=prepare_d04_semantic_source(repo_root=repo_root,company_id=company_id)
    return assemble_recorded_responses(source=source,response_bytes_by_request_id=response_bytes_by_request_id)
