import runpy,json
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from vnext.canonical import content_hash
from vnext.r6_semantic_source import _bytes
from vnext import continuous_semantic_calls as c
from vnext.d04_native_assessment import _response_contract,validate_response
from vnext.normal_source_authority import ROOT
from vnext.canonical import strict_json_file
x=runpy.run_path('/tmp/sec_metrics_issue28_continuous/d04-complete-contract-review/probe.py')
r,source,response=x['r'],x['source'],x['response']
source['source_proofs']=[]
source['semantic_source_id']=content_hash(value={k:v for k,v in source.items()if k!='semantic_source_id'})
r=c.source_requests(source)[0]
response={**response,'request_id':r['request_id']}
bad=deepcopy(r);bad['units']=bad['units'][:2]
protocol,checklist=_response_contract(strict_json_file(path=ROOT/'catalog/r6/semantic_review_v5.json'),bad['units'],bad['required_candidate_assessments'],True)
bad.update(response_protocol=protocol,**checklist);bad['request_id']=content_hash(value={k:v for k,v in bad.items()if k!='request_id'})
short={**response,'request_id':bad['request_id'],'units':response['units'][:2]}
# A stand-alone dictionary knows only its declared request scope.
assert validate_response(request=bad,raw_response=_bytes(short))['unresolved']==[]
policy=SimpleNamespace(model='deepseek-flash')
def prepared(req):
 return c.SemanticRequest(c._FACTORY,c._json(source),c._json(req),c.request_body(req,policy),c._json(req['response_protocol']),
   {'policy':{'budget_root':'/tmp/unused-review-budget'}},SimpleNamespace(_check=lambda:None),ROOT)
with patch.object(c,'verify_saved_source_proofs',return_value=None),patch.object(c,'configured_transport_policy',return_value=policy):
 assert prepared(r).validate(policy)==r
 try:prepared(bad).validate(policy)
 except ValueError as e:reason=str(e)
 else:raise AssertionError('Factory accepted shrunk rehashed request against complete source')
assert reason=='CONTINUOUS_REQUEST_NOT_IN_SOURCE'
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0069')
old=json.loads((base/'semantic-request.json').read_bytes());raw=(base/'wire/assistant-output.bin').read_bytes()
try:validate_response(request=old,raw_response=raw)
except ValueError as e:oldreason=str(e)
else:raise AssertionError('Original69 unexpectedly accepted')
assert oldreason=='D04_RESPONSE_UNIT_SET_INCOMPLETE'
result={'self_consistent_short_dictionary':'PER_REQUEST_VALID_ONLY_NOT_AUTHORITY','actual_SemanticRequest_validate':reason,
 'test_doubles':['source admission verifier','process authority check','transport policy loader'],
 'scope':'Actual factory membership check is not mocked; no live request, model response, source admission or result credit',
 'original69_old_v4_rejection':oldreason,'new_calls':[0,0,0]}
Path('/tmp/sec_metrics_issue28_continuous/d04-complete-contract-review/factory-boundary.json').write_text(json.dumps(result,indent=2)+'\n')
print(result)
