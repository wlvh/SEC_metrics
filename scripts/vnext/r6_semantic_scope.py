"""Scope D04 statement kinds without rewriting the original provider response."""
import copy
from .canonical import strict_json_loads,canonical_json_bytes,sha256_file
from .normal_source_authority import ROOT
from .r6_semantic_review import validate_response as validate_original,SemanticReviewError,POLICY

POLICY_PATH='catalog/r6/semantic_review_v3.json'
CURRENT_KINDS={'DOUBT_DISCLOSED','DOUBT_ALLEVIATED','NO_DOUBT_DECLARATION'}


def validate_response(*,request,raw_response):
    if request['policy_sha256']!=sha256_file(path=ROOT/POLICY_PATH):
        return validate_original(request=request,raw_response=raw_response)
    if type(raw_response) is not bytes or len(raw_response)>POLICY['max_response_bytes']:
        raise SemanticReviewError('D04_RESPONSE_SIZE_OR_TYPE')
    original=strict_json_loads(text=raw_response.decode('utf-8'))
    scoped=copy.deepcopy(original);changes=[]
    if type(scoped) is dict and type(scoped.get('units')) is list:
        for unit in scoped['units']:
            if type(unit) is not dict or type(unit.get('findings')) is not list:continue
            for i,finding in enumerate(unit['findings']):
                if type(finding) is not dict or finding.get('kind') not in CURRENT_KINDS:continue
                if finding.get('subject')=='TARGET_REGISTRANT' and finding.get('timing')=='CURRENT_REPORT':continue
                new_kind=('OTHER_ENTITY' if finding.get('subject')=='OTHER_ENTITY' else
                          'HISTORICAL_STATEMENT' if finding.get('timing')=='HISTORICAL' else
                          'CONDITIONAL_OR_BOILERPLATE' if finding.get('timing')=='CONDITIONAL' else 'UNRESOLVED')
                changes.append({'unit_id':unit.get('unit_id'),'finding_index':i,'statement_kind':finding['kind'],
                                'scoped_kind':new_kind,'subject':finding.get('subject'),'timing':finding.get('timing')})
                finding['kind']=new_kind
    checked=validate_original(request=request,raw_response=canonical_json_bytes(value=scoped))
    current=[f for f in checked['findings'] if f['kind'] in CURRENT_KINDS]
    return {**checked,'provider_response':original,'response_origin':'HOST_EXPLICIT_SUBJECT_AND_TIME_PROJECTION',
            'scope_projection':changes,'current_target_findings':current,
            'semantic_correctness_verified':False,'native_result_created':False,'production_authorized':False}
