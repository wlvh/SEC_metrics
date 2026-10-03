import json,hashlib
from pathlib import Path
from vnext.canonical import content_hash
from vnext.d04_native_assessment import native_source,requests_from_source,validate_response
from vnext.continuous_request_context import FORMAT_VERSION
from vnext.r6_semantic_source import _bytes
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0069')
names=['source.json','semantic-request.json','wire/assistant-output.bin','wire/raw-response.bin','terminal.json']
before={name:hashlib.sha256((base/name).read_bytes()).hexdigest()for name in names}
s=json.loads((base/'source.json').read_bytes());r=json.loads((base/'semantic-request.json').read_bytes());response=json.loads((base/'wire/assistant-output.bin').read_bytes())
original={k:v for k,v in s.items()if k not in {'semantic_source_id','original_complete_source_id','source_check_scope','request_context_format','response_contract_version'}}
original['record_type']='D04_COMPLETE_SEMANTIC_SOURCE'
original['semantic_source_id']=content_hash(value=original)
assert original['semantic_source_id']==s['original_complete_source_id']
newsource=native_source(original,request_context_format=FORMAT_VERSION,complete_response_contract=True)
requests=requests_from_source(newsource)
selected=next(q for q in requests if [u['unit_id']for u in q['units']]==[u['unit_id']for u in r['units']])
changed={**response,'request_id':selected['request_id']}
try:validate_response(request=selected,raw_response=_bytes(changed))
except ValueError as e: reason=str(e)
else:raise AssertionError('Original incomplete response accepted under new complete contract')
assert before=={name:hashlib.sha256((base/name).read_bytes()).hexdigest()for name in names}
result={'case':'Original69_response_with_only_new_request_id_substituted_OFFLINE_REJECTION_ONLY','original_request_id':r['request_id'],
 'new_request_id':selected['request_id'],'original_response_sha256':before['wire/assistant-output.bin'],
 'original_requested_units':len(r['units']),'original_responded_units':len(response['units']),'new_requested_units':len(selected['units']),
 'outcome':'REJECTED','reason':reason,'all_original_artifact_hashes_unchanged':before,'execution_credit_reused':False,'calls':[0,0,0]}
Path('/tmp/sec_metrics_issue28_continuous/d04-complete-contract-review/original69-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
