"""D03 semantic proposals from the existing full annual-source assembler.

Every visible block/native fact/supplement is retained. Keyword candidates only
require explicit assessment; they neither select the corpus nor prove absence.
The shared quote checker does not endorse a model's investigation conclusion.
"""
import re
import copy
from datetime import datetime
from pathlib import Path

from .canonical import content_hash, strict_json_file, sha256_file, strict_json_loads, canonical_json_bytes
from .normal_source_authority import ROOT
from .r6_semantic_source import prepare_d04_semantic_source
from .r6_semantic_review import _source_items, _validate_source_response, SemanticReviewError

POLICY_PATH='catalog/r6/regulatory_semantic_review_v6.json'
POLICY_HISTORY=tuple('catalog/r6/regulatory_semantic_review_v%d.json' % i for i in range(1,7))


def _need(condition,reason):
    if not condition:raise ValueError(reason)


def _response_schema(policy):
    def obj(fields):
        return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
    def array(item):return {'type':'array','items':item}
    text={'type':'string','minLength':1}
    evidence=obj({'kind':{'enum':['VISIBLE_BLOCK','NATIVE_FACT','NATIVE_SUPPLEMENT']},
                  'source_index':{'type':'integer'}})
    finding=obj({'kind':{'enum':policy['kinds']},'subject':{'enum':policy['subjects']},
                 'event_dates':array(text),'reported_status':{'enum':policy['reported_status_values']},
                 'evidence':array(evidence),'reason':text})
    unit=obj({'unit_id':text,'reviewed':{'const':True},'findings':array(finding),
              'context_only_source_indices':array({'type':'integer'}),'unresolved':array(text)})
    return obj({'request_id':text,'units':array(unit)})


def prepare_regulatory_semantic_source(*,repo_root:Path,company_id:str):
    # The inherited assembler makes no D04 conclusion; reuse its complete
    # original annual/amendment text and native-object reconstruction.
    original=prepare_d04_semantic_source(repo_root=repo_root,company_id=company_id)
    policy=strict_json_file(path=ROOT/POLICY_PATH)
    _need(strict_json_file(path=repo_root/POLICY_PATH)==policy,'D03_INSTALLED_POLICY_CHANGED')
    pattern=re.compile(policy['candidate_pattern'],re.I)
    documents=[]
    for doc in original['documents']:
        visible=[];native=[]
        for unit in original['units']:
            if unit['document_id']!=doc['document_id']:continue
            kind,items=_source_items(unit)
            if kind=='VISIBLE_BLOCK':visible.extend(i for i,item in items.items() if pattern.search(item['text']))
            elif kind=='NATIVE_FACT':native.extend(i for i,item in items.items() if pattern.search(item['qualified_name']))
        documents.append({**doc,'language_candidate_block_indices':visible,'native_candidate_ordinals':native})
    body={k:v for k,v in original.items() if k!='semantic_source_id'}
    body.update(record_type='D03_COMPLETE_SEMANTIC_SOURCE',metric_id='D03',documents=documents,
        inherited_complete_source_id=original['semantic_source_id'],
        regulatory_policy_sha256=sha256_file(path=ROOT/POLICY_PATH),
        regulatory_module_sha256=sha256_file(path=Path(__file__)))
    return {**body,'semantic_source_id':content_hash(value=body)}


def requests_from_source(source):
    policy=strict_json_file(path=ROOT/POLICY_PATH)
    _need(source['metric_id']=='D03' and source['source_serialization_complete']
          and source['semantic_source_id']==content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'}),
          'D03_COMPLETE_SOURCE_REQUIRED')
    documents={d['document_id']:d for d in source['documents']};rows=[]
    for unit in source['units']:
        doc=documents[unit['document_id']];kind,items=_source_items(unit)
        required=(doc['language_candidate_block_indices'] if kind=='VISIBLE_BLOCK' else
                  doc['native_candidate_ordinals'] if kind=='NATIVE_FACT' else [])
        body={'record_type':'D03_INTERPRETATION_REQUEST','metric_id':'D03',
            'source_id':source['semantic_source_id'],'company_id':source['company_id'],
            'target_cik':source['prepared_annual_input']['entity'],
            'target_period':source['prepared_annual_input']['table_input']['target_period'],
            'fiscal_label_context':{k:source['prepared_annual_input']['fiscal_year_label_resolution'][k] for k in
                ('selected_fiscal_year','basis','original_dei_fiscal_year','original_companyfacts_fiscal_year_values','metadata_conflict_retained')},
            'document_context':{k:doc[k] for k in ('document_id','filing','registrant_name_binding','language_candidate_block_indices','native_candidate_ordinals')},
            'units':[unit],'system_prompt':policy['system_prompt'],'category_definitions':policy['category_definitions'],
            'required_candidate_assessments':[{'unit_id':unit['unit_id'],'kind':kind,'source_index':i} for i in required if i in items],
            'response_protocol':{'root_fields':['request_id','units'],'unit_fields':['unit_id','reviewed','findings','context_only_source_indices','unresolved'],
                'finding_fields':['kind','subject','event_dates','reported_status','evidence','reason'],'evidence_fields':['kind','source_index'],
                'evidence_kinds':['VISIBLE_BLOCK','NATIVE_FACT','NATIVE_SUPPLEMENT'],'finding_kinds':policy['kinds'],
                'subjects':policy['subjects'],'reported_status_values':policy['reported_status_values'],'json_schema':_response_schema(policy)},
            'policy_sha256':sha256_file(path=ROOT/POLICY_PATH),'provider_request_sent':False,
            'provider_tokens_measured':False,'production_authorized':False}
        rows.append({**body,'request_id':content_hash(value=body)})
    _need([r['units'][0]['unit_id'] for r in rows]==source['required_unit_ids'],'D03_SOURCE_UNIT_COVERAGE_CHANGED')
    return rows


def _canonical_date(value):
    clean=' '.join(value.replace(',','').split())
    formats=[('%B %d %Y','%Y-%m-%d'),('%B %Y','%Y-%m'),('%Y-%m-%d','%Y-%m-%d'),
             ('%Y-%m','%Y-%m'),('%Y','%Y')]
    for fmt,out in formats:
        try:return datetime.strptime(clean,fmt).strftime(out)
        except ValueError:pass
    raise ValueError('D03_EVENT_DATE_FORMAT')


def _source_dates(text):
    from .regulatory_investigation_candidates import _PATTERNS
    matches=list(_PATTERNS['date_literal'].finditer(text))
    matches.extend(m for m in re.finditer(r'\b[12][0-9]{3}\b',text)
                   if not any(a.start()<=m.start()<a.end() for a in matches))
    return [(m,_canonical_date(m.group())) for m in matches]


def validate_response(*,request,raw_response):
    _need(request.get('metric_id')=='D03','D03_REQUEST_METRIC_CHANGED')
    policies=[p for p in POLICY_HISTORY if sha256_file(path=ROOT/p)==request['policy_sha256']]
    _need(len(policies)==1,'D03_RESPONSE_POLICY_NOT_BOUND')
    policy=strict_json_file(path=ROOT/policies[0])
    _need(type(raw_response) is bytes and len(raw_response)<=policy['max_response_bytes'],'D03_RESPONSE_SIZE_OR_TYPE')
    original=strict_json_loads(text=raw_response.decode('utf-8'))
    if policy['schema_version']<3:
        try:
            checked=_validate_source_response(request=request,raw_response=raw_response,policy=policy)
        except SemanticReviewError as error:
            raise ValueError(str(error).replace('D04_','D03_')) from error
        return {**checked,'provider_response':original,'response_origin':'ORIGINAL_PROVIDER_QUOTATIONS'}
    _need(type(original) is dict and set(original)=={'request_id','units'}
          and original['request_id']==request['request_id'] and type(original['units']) is list,
          'D03_RESPONSE_REQUEST_BINDING')
    resolved=copy.deepcopy(original)
    units={u['unit_id']:u for u in request['units']}
    temporal=[]
    selected_rows=[]
    for row in resolved['units']:
        _need(type(row) is dict and type(row.get('unit_id')) is str and row['unit_id'] in units
              and type(row.get('findings')) is list,'D03_REFERENCE_UNIT_CHANGED')
        kind,items=_source_items(units[row['unit_id']])
        if policy['schema_version']>=5:
            contexts=row.pop('context_only_source_indices' if policy['schema_version']>=6 else 'context_source_indices',None)
            _need(type(contexts) is list and all(type(i) is int and i in items for i in contexts)
                  and len(set(contexts))==len(contexts),'D03_CONTEXT_SOURCE_INDICES')
            if policy['schema_version']>=6:
                explicit={e.get('source_index') for f in row['findings'] if type(f) is dict
                          for e in f.get('evidence',[]) if type(e) is dict and type(e.get('source_index')) is int}
                _need(not set(contexts)&explicit,'D03_CONTEXT_AND_FINDING_OVERLAP')
            for index in contexts:
                row['findings'].append({'kind':'OTHER_MEANING','subject':'UNRESOLVED','event_dates':[],
                    'reported_status':'NOT_AN_ACTION_STATEMENT','evidence':[{'kind':kind,'source_index':index}],
                    'reason':'The provider explicitly selected this item as context only; the host retains its complete source text.'})
        selected_rows.append(copy.deepcopy(row))
        for finding in row['findings']:
            _need(type(finding) is dict and type(finding.get('evidence')) is list,'D03_REFERENCE_FIELDS')
            dates=None;status=None
            if policy['schema_version']>=4:
                _need(set(finding)=={'kind','subject','event_dates','reported_status','evidence','reason'}
                      and type(finding['event_dates']) is list and all(type(d) is str and bool(d) for d in finding['event_dates'])
                      and len(set(finding['event_dates']))==len(finding['event_dates'])
                      and finding['reported_status'] in policy['reported_status_values'],'D03_EVENT_AND_STATUS_FIELDS')
                dates=finding.pop('event_dates');status=finding.pop('reported_status')
                if finding['kind']=='CURRENT_REGULATORY_ACTION':
                    _need(status=='ONGOING_AS_REPORTED','D03_CURRENT_ACTION_STATUS_CONFLICT')
                if finding['kind']=='NO_ACTION_DECLARATION':
                    _need(status=='EXPLICIT_NEGATIVE_AS_REPORTED','D03_NEGATIVE_ACTION_STATUS_CONFLICT')
                finding['timing']=({'ONGOING_AS_REPORTED':'CURRENT_REPORT','EXPLICIT_NEGATIVE_AS_REPORTED':'CURRENT_REPORT',
                    'SPECIFIC_RESOLUTION_REPORTED':'HISTORICAL','CONDITIONAL':'CONDITIONAL'}.get(status,'UNRESOLVED'))
                if finding['kind']=='HISTORICAL_STATEMENT':
                    _need(status not in {'ONGOING_AS_REPORTED','EXPLICIT_NEGATIVE_AS_REPORTED'},'D03_HISTORICAL_CURRENT_STATUS_CONFLICT')
                    finding['timing']='HISTORICAL'
            for evidence in finding['evidence']:
                _need(type(evidence) is dict and set(evidence)=={'kind','source_index'}
                      and evidence['kind']==kind and type(evidence['source_index']) is int
                      and evidence['source_index'] in items,'D03_REFERENCE_OUTSIDE_SUPPLIED_SOURCE')
                item=items[evidence['source_index']]
                evidence['text']=item['raw_xml'] if kind=='NATIVE_SUPPLEMENT' else item['text']
            if dates is not None:
                from .regulatory_investigation_candidates import _PATTERNS
                matches=[]
                for date in dates:
                    if policy['schema_version']>=5:
                        canonical=_canonical_date(date)
                        refs=[{'source_index':e['source_index'],'date_text':date,'source_literal':m.group(),
                               'canonical_date':canonical,'start_character':m.start(),'end_character':m.end()}
                              for e in finding['evidence'] for m,normalized in _source_dates(e['text']) if normalized==canonical]
                        _need(bool(refs),'D03_EVENT_DATE_NOT_IN_SELECTED_SOURCE');matches.extend(refs)
                        continue
                    _need(_PATTERNS['date_literal'].fullmatch(date) is not None or re.fullmatch(r'[12][0-9]{3}',date),
                          'D03_EVENT_DATE_FORMAT')
                    refs=[{'source_index':e['source_index'],'date_text':date,'start_character':m.start(),'end_character':m.end()}
                          for e in finding['evidence'] for m in re.finditer(re.escape(date),e['text'])
                          if (m.start()==0 or not e['text'][m.start()-1].isalnum())
                          and (m.end()==len(e['text']) or not e['text'][m.end()].isalnum())]
                    _need(bool(refs),'D03_EVENT_DATE_NOT_IN_SELECTED_SOURCE');matches.extend(refs)
                temporal.append({'event_dates':dates,'reported_status':status,'resolved_date_evidence':matches,
                    'timing_origin':'HOST_COMPATIBILITY_FIELD_FROM_REPORTED_STATUS',
                    'date_to_action_relationship_semantically_verified':False})
    try:
        checked=_validate_source_response(request=request,raw_response=canonical_json_bytes(value=resolved),policy=policy)
    except SemanticReviewError as error:
        raise ValueError(str(error).replace('D04_','D03_')) from error
    if policy['schema_version']>=4:
        _need(len(temporal)==len(checked['findings']),'D03_EVENT_STATUS_COUNT_CHANGED')
        checked['findings']=[{**finding,**fields} for finding,fields in zip(checked['findings'],temporal)]
    return {**checked,'provider_response':original,
            'source_selection_proposal':{'request_id':original['request_id'],'units':selected_rows},
            'response_origin':'HOST_MATERIALIZED_COMPLETE_SOURCE_ITEMS',
            'raw_provider_response_preserved_separately':True,
            'reference_selection_is_semantic_approval':False}
