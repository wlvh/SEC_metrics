import json,hashlib
from pathlib import Path
from copy import deepcopy
from tests.vnext.test_capacity_semantic_review import source_packet
from vnext import d04_native_assessment as d04, capacity_semantic_review as b13
from vnext.native_unit_index import upgrade_request,restore_base_request,restore_response
from vnext.canonical import content_hash,canonical_json_bytes
from vnext.r6_semantic_source import _seal_unit
rows=[]
def fixture(metric):
 s=source_packet();old=s['units'][0];units=[]
 texts=(['There is substantial doubt about our ability to continue as a going concern.','Revenue is recognized when services are delivered.'] if metric=='D04' else
        ['Our plant can manufacture 100 widgets per quarter.','An advanced manufacturing production tax credit applies to widgets manufactured and sold.'])
 for j,text in enumerate(texts):
  p=deepcopy(old['payload']);p['blocks'][0].update(block_index=7+j,text=text)
  units.append(_seal_unit(old['document_id'],'VISIBLE_TEXT',p,j))
 s.update(units=units,required_unit_ids=[u['unit_id']for u in units],capacity_navigation=[{'unit_id':u['unit_id'],'kind':'VISIBLE_BLOCK','source_index':7+i}for i,u in enumerate(units)])
 s['documents'][0].update(language_candidate_block_indices=[7],native_candidate_ordinals=[])
 s['prepared_annual_input']['table_input']['target_period']={'period_start':'2025-01-01','period_end':'2025-12-31','fiscal_year':2025}
 s.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE' if metric=='D04' else 'B13_COMPLETE_SEMANTIC_SOURCE',metric_id=metric)
 s['semantic_source_id']=content_hash(value={k:v for k,v in s.items()if k!='semantic_source_id'})
 base=(d04.requests_from_source(d04.native_source(s,complete_response_contract=True))[0] if metric=='D04' else b13.requests_from_source(s)[0])
 request=upgrade_request(base)
 response={'units':[{'unit_index':0,'reviewed':True,'findings':[{'kind':'DOUBT_DISCLOSED' if metric=='D04' else 'AVAILABLE_CAPACITY',
    'subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT','evidence':[{'kind':'VISIBLE_BLOCK','source_index':7}],'reason':'Classify the supplied source statement.'}],'unresolved':[]},
   {'unit_index':1,'reviewed':True,'findings':([]if metric=='D04'else[{'kind':'OTHER_CONTEXT','subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT','evidence':[{'kind':'VISIBLE_BLOCK','source_index':8}],'reason':'Tax credit is not a production quantity.'}]),'unresolved':[]}]}
 if metric=='B13':
  for item in response['units']:item['calculation_limits']=[]
 return base,request,response

def check(metric,name,request,response,expected):
 fn=d04.validate_response if metric=='D04'else b13.validate_response
 raw=json.dumps(response,ensure_ascii=False,separators=(',',':')).encode()
 try:
  got=fn(request=request,raw_response=raw)
  outcome='ACCEPTED';reason=None
  assert got['response']==response and got['request_id']==request['request_id']
 except ValueError as e:outcome='REJECTED';reason=str(e)
 assert outcome==expected,(metric,name,outcome,reason)
 rows.append({'metric':metric,'case':name,'outcome':outcome,'reason':reason})

for metric in ['D04','B13']:
 base,r,response=fixture(metric);before=canonical_json_bytes(value=base)
 assert restore_base_request(r)==base
 restored_base,normalized,original=restore_response(request=r,raw_response=canonical_json_bytes(value=response))
 assert restored_base==base and original==response and json.loads(normalized)['request_id']==base['request_id']
 assert [u['unit_id']for u in json.loads(normalized)['units']]==[u['unit_id']for u in base['units']]
 check(metric,'correct_indexed',r,response,'ACCEPTED')
 check(metric,'reordered_indexed_array',r,{**response,'units':list(reversed(response['units']))},'ACCEPTED')
 for label,value in [('boolean',True),('string','0'),('float',0.0),('negative',-1),('out_of_range',2),('duplicate',1)]:
  bad=deepcopy(response);bad['units'][0]['unit_index']=value;check(metric,label,r,bad,'REJECTED')
 bad=deepcopy(response);bad['units'].pop();check(metric,'omitted_unit',r,bad,'REJECTED')
 bad=deepcopy(response);bad['request_id']=r['request_id'];check(metric,'model_echoed_request_hash',r,bad,'REJECTED')
 bad=deepcopy(response);bad['units'][0]['unit_id']=base['units'][0]['unit_id'];check(metric,'model_echoed_unit_hash',r,bad,'REJECTED')
 bad=deepcopy(response);bad['units'][0]['findings'][0]['evidence'][0]['source_index']=8;check(metric,'cross_unit_reference',r,bad,'REJECTED')
 bad=deepcopy(response)
 if metric=='D04':bad['units'][0]['findings'][0].update(kind='CONDITIONAL_OR_BOILERPLATE',timing='CONDITIONAL')
 else:bad['units'][1]['findings'][0]['kind']='AVAILABLE_CAPACITY'
 check(metric,'wrong_original_business_classification',r,bad,'REJECTED')
 for field,mutate in [
  ('index_version',lambda q:q['indexed_unit_contract'].update(version='UNAPPROVED')),
  ('base_id',lambda q:q['indexed_unit_contract'].update(base_request_id=content_hash(value='other'))),
  ('requirements',lambda q:q['unit_index_requirements'].pop()),
  ('index_schema',lambda q:q['response_protocol']['json_schema']['properties']['units']['items']['properties']['unit_index'].update(maximum=999)),
  ('schema_count',lambda q:q['response_protocol']['json_schema']['properties']['units'].update(minItems=1,maxItems=1)),
  ('unit_order',lambda q:q.update(units=list(reversed(q['units']))))]:
  bad=deepcopy(r);mutate(bad);bad['request_id']=content_hash(value={k:v for k,v in bad.items()if k!='request_id'})
  check(metric,'resigned_'+field,bad,response,'REJECTED')
 assert canonical_json_bytes(value=base)==before
out={'scope':'Root-authored native_unit_index and recursive D04/B13 source validators only','cases':rows,
 'synthetic_source_units':True,'actual_new_calls':[0,0,0],'base_requests_unchanged':True}
Path('/tmp/sec_metrics_issue28_continuous/native-index-independent-review/helper-results.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS',len(rows),'cases')
