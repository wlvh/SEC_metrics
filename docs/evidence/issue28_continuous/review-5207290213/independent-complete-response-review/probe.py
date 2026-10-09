import json,hashlib
from copy import deepcopy
from pathlib import Path
from tests.vnext.test_capacity_semantic_review import source_packet
from tests.vnext.test_d04_native_assessment import response_for
from vnext.canonical import content_hash
from vnext.r6_semantic_source import _seal_unit,_bytes
from vnext.d04_native_assessment import native_source,requests_from_source,validate_response,COMPLETE_RESPONSE_VERSION
s=source_packet();s.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE',metric_id='D04')
u=s['units'][0];payload=deepcopy(u['payload']);payload['blocks'][0]['text']='There is substantial doubt about our ability to continue as a going concern.'
first=_seal_unit(u['document_id'],'VISIBLE_TEXT',payload,0)
units=[first]+[_seal_unit(first['document_id'],'VISIBLE_TEXT',{'blocks':[{**payload['blocks'][0],'block_index':i,'text':'Revenue is recognized when services are delivered.'}]},i)for i in (8,9)]
s.update(units=units,required_unit_ids=[u['unit_id']for u in units]);s['documents'][0].update(language_candidate_block_indices=[7],native_candidate_ordinals=[])
s['prepared_annual_input']['table_input']['target_period']={'period_start':'2025-01-01','period_end':'2025-12-31','fiscal_year':2025}
s['semantic_source_id']=content_hash(value={k:v for k,v in s.items()if k!='semantic_source_id'})
source=native_source(s,complete_response_contract=True);r=requests_from_source(source)[0]
response=response_for(r);response['units'] += [{'unit_id':u['unit_id'],'reviewed':True,'unresolved':[],'findings':[]}for u in units[1:]]
rows=[]
def check(name,request,res):
 try:
  c=validate_response(request=request,raw_response=_bytes(res));out={'case':name,'outcome':'ACCEPTED','unresolved':c['unresolved']}
 except Exception as e:out={'case':name,'outcome':'REJECTED','error_type':type(e).__name__,'reason':str(e)}
 rows.append(out);print(out,flush=True)
check('complete_positive',r,response)
check('reversed_complete_units',r,{**response,'units':list(reversed(response['units']))})
check('missing_unit',r,{**response,'units':response['units'][:2]})
check('duplicate_unit',r,{**response,'units':[response['units'][0]]*3})
for name,fn in [
 ('shrink_schema_count',lambda x:x['response_protocol']['json_schema']['properties']['units'].update(minItems=1,maxItems=1)),
 ('shrink_schema_enum',lambda x:x['response_protocol']['json_schema']['properties']['units']['items']['properties']['unit_id'].update(enum=[units[0]['unit_id']])),
 ('shrink_required_ids',lambda x:x.update(required_response_unit_ids=[units[0]['unit_id']])),
 ('shrink_checklist',lambda x:x.update(unit_response_requirements=[])),
 ('wrong_version',lambda x:x.update(response_contract_version='other')),
 ('downgrade_version_only',lambda x:x.pop('response_contract_version')),
 ('remove_required_candidates_and_update_checklist',lambda x:(x.update(required_candidate_assessments=[]),[u.update(required_evidence_references=[])for u in x['unit_response_requirements']]))]:
 bad=deepcopy(r);fn(bad);bad['request_id']=content_hash(value={k:v for k,v in bad.items()if k!='request_id'})
 res={**response,'request_id':bad['request_id']}
 if name=='remove_required_candidates_and_update_checklist':res=deepcopy(res);res['units'][0]['findings']=[]
 check(name,bad,res)
 assert bad not in requests_from_source(source)
root=Path('/tmp/sec_metrics_issue28_continuous/d04-complete-contract-review')
(root/'results.json').write_text(json.dumps({'scope':'complete response contract independent review','rows':rows,'new_calls':[0,0,0]},indent=2)+'\n')
