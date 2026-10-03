from pathlib import Path
import hashlib,json,socket
from unittest.mock import patch
from vnext.continuous_semantic_calls import prepare_requests
base=Path('/tmp/sec_metrics_issue28_continuous/b13-v6');counts=json.loads((base/'final-request-counts.json').read_text());rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for company in counts['companies']:
  prepared=prepare_requests(company_id=company['company_id'],metric_id='B13',reference_context=True,program_quantity_roles=True)
  groups=[]
  for index,(p,m) in enumerate(zip(prepared,company['measurements']),1):
   request=json.loads(p.request_bytes);contract=request['program_quantity_contract']
   # Counting evidence binds the exact provider body, not this summary.
   digest=hashlib.sha256(p.provider_request_body_bytes).hexdigest()
   assert digest==m['request_sha256'],(digest,m['request_sha256'])
   refs=request['required_candidate_assessments']
   groups.append({'group':index,'request_id':request['request_id'],'provider_body_sha256':digest,
    'input_tokens':m['input_tokens'],'context_tokens':m['context_tokens'],'unit_ids':[u['unit_id'] for u in request['units']],
    'required_candidate_count':len(refs),'candidate_kind_counts':{kind:sum(r['kind']==kind for r in refs) for kind in sorted({r['kind'] for r in refs})},
    'program_quantity_roles':contract['verified_quantity_roles'],'source_constraints':contract['source_constraints'],
    'implementation_unresolved':contract['implementation_unresolved']})
  rows.append({'company_id':company['company_id'],'metric_id':'B13','groups':groups})
(base/'company-task-request-plan.json').write_text(json.dumps({'new_calls':[0,0,0],'execution_authorized_by_this_artifact':False,
 'requires_current_binding_and_wiring':True,'companies':rows,'request_count':sum(len(r['groups']) for r in rows)},indent=2)+'\n')
print([(r['company_id'],[(g['group'],len(g['unit_ids']),g['required_candidate_count'],g['input_tokens'],len(g['program_quantity_roles'])) for g in r['groups']]) for r in rows])
