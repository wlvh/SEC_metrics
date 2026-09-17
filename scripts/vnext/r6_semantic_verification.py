"""Check one saved D03 model proposal against its original complete source unit.

This is a distinct bounded provider task. It is not independent code review,
acceptance, a replacement original response, or a retry of the extraction.
"""
from pathlib import Path
import copy
import json

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file, strict_json_loads
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .r6_regulatory_semantics import validate_response as validate_proposal, POLICY_PATH as PROPOSAL_POLICY
from .r6_semantic_review import _source_items
from .sources import resolve_repository_file

POLICY_PATH='catalog/r6/regulatory_semantic_verification_v2.json'


def _prior(ordinal):
    need(type(ordinal) is int and ordinal>0,'SEMANTIC_CHECK_PRIOR_SLOT_INVALID')
    config=strict_json_file(path=ROOT/'config/issue28_continuous_calls_v1.json')
    root=Path(config['budget_root'])/'calls'/f'{ordinal:04d}'
    return _read_prior_directory(root)


def _read_prior_directory(root):
    """Read-only replay helper; it cannot construct an execution capability."""
    def read(name):return strict_json_file(path=resolve_repository_file(repo_root=root,repo_relative_path=name))
    terminal=read('terminal.json');intent=read('intent.json');wire=read('wire/journal.json')
    need(terminal['terminal_id']==content_hash(value={k:v for k,v in terminal.items() if k!='terminal_id'})
         and intent['intent_id']==content_hash(value={k:v for k,v in intent.items() if k!='intent_id'})
         and terminal['intent_id']==intent['intent_id'] and intent['channel']=='PROVIDER'
         and intent['execution_mode']=='LIVE' and intent['requirement_id']=='issue_28_v14'
         and terminal['counts']==[1,1,0] and terminal['stop_reason']==''
         and wire['mode']=='LIVE' and wire['error_class']=='','SEMANTIC_CHECK_PRIOR_EXECUTION_INVALID')
    for relative,digest in terminal['evidence'].items():
        need(sha256_file(path=resolve_repository_file(repo_root=root,repo_relative_path=relative))==digest,
             'SEMANTIC_CHECK_PRIOR_BYTES_CHANGED')
    request=read('semantic-request.json');source=read('source.json')
    need(request.get('metric_id')=='D03' and request['record_type']=='D03_INTERPRETATION_REQUEST',
         'SEMANTIC_CHECK_ORIGINAL_D03_PROPOSAL_REQUIRED')
    raw=resolve_repository_file(repo_root=root,repo_relative_path='wire/assistant-output.bin').read_bytes()
    need(sha256_bytes(content=raw)==wire['assistant_output_sha256'],'SEMANTIC_CHECK_RESPONSE_CHANGED')
    checked=validate_proposal(request=request,raw_response=raw)
    return root,source,request,checked.get('source_selection_proposal',checked['provider_response']),terminal,sha256_bytes(content=raw)


def prepare_verification_source(*,company_id,prior_call_ordinal):
    _,source,request,proposal,terminal,response_sha=_prior(prior_call_ordinal)
    need(request['company_id']==company_id,'SEMANTIC_CHECK_COMPANY_CHANGED')
    body=copy.deepcopy(source);body.pop('semantic_source_id')
    body.update(record_type='D03_PROVIDER_PROPOSAL_VERIFICATION_SOURCE',
        prior_call_ordinal=prior_call_ordinal,prior_terminal_id=terminal['terminal_id'],
        prior_assistant_output_sha256=response_sha,prior_request_id=request['request_id'],
        verification_scope='ONLY_THE_SAVED_PROPOSAL_NOT_WHOLE_FILING_COMPLETENESS',
        verification_module_sha256=sha256_file(path=Path(__file__)))
    return {**body,'semantic_source_id':content_hash(value=body)}


def requests_from_source(source):
    _,prior_source,prior_request,proposal,terminal,response_sha=_prior(source['prior_call_ordinal'])
    need(source['prior_terminal_id']==terminal['terminal_id'] and source['prior_assistant_output_sha256']==response_sha
         and source['prior_request_id']==prior_request['request_id']
         and source['units']==prior_source['units'] and source['source_proofs']==prior_source['source_proofs'],
         'SEMANTIC_CHECK_SOURCE_BINDING_CHANGED')
    policy=strict_json_file(path=ROOT/POLICY_PATH);definitions=prior_request['category_definitions']
    proposals=[]
    for row in proposal['units']:
        for finding in row['findings']:
            item={'unit_id':row['unit_id'],'finding':finding}
            proposals.append({**item,'proposal_id':content_hash(value=item)})
    body={k:v for k,v in prior_request.items() if k not in {'request_id','system_prompt','response_protocol','policy_sha256','source_id'}}
    body.update(record_type='D03_SEMANTIC_VERIFICATION_REQUEST',source_id=source['semantic_source_id'],
        system_prompt=policy['system_prompt'],category_definitions=definitions,proposals=proposals,
        prior_request_id=prior_request['request_id'],prior_terminal_id=terminal['terminal_id'],
        prior_assistant_output_sha256=response_sha,policy_sha256=sha256_file(path=ROOT/POLICY_PATH),
        response_protocol={'root_fields':['request_id','assessments'],
            'assessment_fields':['proposal_id','judgment','reason','evidence'],
            'judgments':['SUPPORTED','UNSUPPORTED','UNRESOLVED'],
            'evidence_fields':['unit_id','kind','source_index'],
            'field_types':{'request_id':'string','assessments':'array of objects','proposal_id':'string',
                           'judgment':'enum','reason':'nonempty string','evidence':'nonempty array of source references'}})
    return [{**body,'request_id':content_hash(value=body)}]


def validate_response(*,request,raw_response):
    policy=strict_json_file(path=ROOT/POLICY_PATH)
    need(type(raw_response) is bytes and len(raw_response)<=262144,'SEMANTIC_CHECK_RESPONSE_SIZE')
    value=strict_json_loads(text=raw_response.decode())
    need(type(value) is dict and set(value)=={'request_id','assessments'} and value['request_id']==request['request_id']
         and type(value['assessments']) is list,'SEMANTIC_CHECK_RESPONSE_BINDING')
    expected={p['proposal_id']:p for p in request['proposals']};seen=set();units={u['unit_id']:u for u in request['units']};rows=[]
    for item in value['assessments']:
        need(type(item) is dict and set(item)=={'proposal_id','judgment','reason','evidence'}
             and type(item['proposal_id']) is str and item['proposal_id'] in expected and item['proposal_id'] not in seen
             and item['judgment'] in ['SUPPORTED','UNSUPPORTED','UNRESOLVED']
             and type(item['reason']) is str and 0<len(item['reason'])<=2000
             and type(item['evidence']) is list and bool(item['evidence']),'SEMANTIC_CHECK_ASSESSMENT_FIELDS')
        seen.add(item['proposal_id']);refs=[]
        for evidence in item['evidence']:
            need(type(evidence) is dict and set(evidence)=={'unit_id','kind','source_index'}
                 and type(evidence['unit_id']) is str and evidence['unit_id'] in units,'SEMANTIC_CHECK_REFERENCE_UNIT')
            kind,items=_source_items(units[evidence['unit_id']])
            need(evidence['kind']==kind and type(evidence['source_index']) is int and evidence['source_index'] in items,
                 'SEMANTIC_CHECK_REFERENCE_RANGE')
            obj=items[evidence['source_index']];refs.append({**evidence,'text':obj['raw_xml'] if kind=='NATIVE_SUPPLEMENT' else obj['text']})
        rows.append({**item,'resolved_source_evidence':refs})
    need(seen==set(expected),'SEMANTIC_CHECK_PROPOSALS_INCOMPLETE')
    return {'request_id':request['request_id'],'provider_response':value,'assessments':rows,
        'all_proposals_assessed':True,'all_proposals_supported':all(r['judgment']=='SUPPORTED' for r in rows),
        'source_references_valid':True,'semantic_correctness_verified':False,'independent_code_review':False,
        'native_result_created':False,'production_authorized':False}
