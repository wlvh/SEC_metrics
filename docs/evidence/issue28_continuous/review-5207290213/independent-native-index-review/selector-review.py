import json,tempfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.vnext.test_native_request_variants import synthetic_source
from vnext import continuous_semantic_calls as c
from vnext.continuous_call_ledger import recorded_ledger
from vnext.native_unit_index import reconstruct_requests,upgrade_request
from vnext.canonical import content_hash
rows=[]
source,_=synthetic_source();source['source_proofs']=[];source['semantic_source_id']=content_hash(value={k:v for k,v in source.items()if k!='semantic_source_id'})
base=reconstruct_requests(source);indexed=[upgrade_request(r)for r in base];policy=SimpleNamespace(model='deepseek-flash')
req={'policy':{'budget_root':'/tmp/unused-synthetic-budget'}}
prepared=[c.SemanticRequest(c._FACTORY,c._json(source),c._json(r),c.request_body(r,policy),c._json(r['response_protocol']),req,SimpleNamespace(_check=lambda:None))for r in base]

def scenario(name,saved,statuses,fail_replay=False):
 with tempfile.TemporaryDirectory() as temporary:
  root=Path(temporary).resolve();ledger=recorded_ledger(root=root/'ledger')
  with ledger.locked():pass
  snapshots=[]
  for ordinal,(r,status) in enumerate(zip(saved,statuses),1):
   p=ledger.root/'calls'/f'{ordinal:04d}';p.mkdir(parents=True);(p/'semantic-request.json').write_bytes(c._json(r))
   snapshots.append({'channel':'PROVIDER','ordinal':ordinal,'status':status})
  before={p:p.read_bytes()for p in ledger.root.rglob('*')if p.is_file()}
  def replay(*,prepared,path):
   if fail_replay:raise ValueError('NATIVE_ORIGINAL_ACCEPTANCE_SEMANTICS_CHANGED')
   return {'revalidation':{'request_id':json.loads(prepared.request_bytes)['request_id'],'actual_credit':'SYNTHETIC_REPLAY_DOUBLE_ONLY'}}
  with patch.object(ledger,'snapshot',return_value={'rows':snapshots}),patch.object(c,'configured_transport_policy',return_value=policy),patch('vnext.native_assessment_replay.replay_native_response',side_effect=replay) as reader:
   try:
    chosen,report=c.select_native_request_variants(prepared_requests=prepared,ledger=ledger)
    outcome='ACCEPTED';reason=None
   except ValueError as e:outcome='REJECTED';reason=str(e);report=[];chosen=[]
  assert before=={p:p.read_bytes()for p in before}
  result={'case':name,'outcome':outcome,'reason':reason,'variants':[r['variant']for r in report],'original_ordinals':[r['original_ordinal']for r in report],'replay_calls':reader.call_count}
  rows.append(result)
  return chosen,result

chosen,r=scenario('no success',[],[]);assert r['variants']==['INDEXED_UNITS_V1']*3 and r['replay_calls']==0
chosen,r=scenario('BASE and INDEXED successes plus old failed BASE',[base[0],indexed[1],base[2]],['SUCCEEDED','SUCCEEDED','FAILED'])
assert r['variants']==['BASE','INDEXED_UNITS_V1','INDEXED_UNITS_V1'] and r['original_ordinals']==[1,2,None]
assert chosen[0].request_bytes==prepared[0].request_bytes and chosen[0].provider_request_body_bytes==prepared[0].provider_request_body_bytes
_,r=scenario('two successful variants for one original group',[base[0],indexed[0]],['SUCCEEDED','SUCCEEDED']);assert r['reason']=='NATIVE_VARIANT_MULTIPLE_SUCCESSFUL_VERSIONS'
_,r=scenario('current replay rejects original success',[base[0]],['SUCCEEDED'],True);assert r['reason']=='NATIVE_ORIGINAL_ACCEPTANCE_SEMANTICS_CHANGED'
foreign=deepcopy(base[0]);foreign['source_id']=content_hash(value='foreign source');foreign['request_id']=content_hash(value={k:v for k,v in foreign.items()if k!='request_id'})
_,r=scenario('foreign source success',[foreign],['SUCCEEDED']);assert r['original_ordinals']==[None]*3 and r['replay_calls']==0
for name,request in [('valid_indexed',indexed[0]),('cross_source_indexed',upgrade_request(foreign))]:
 item=c.SemanticRequest(c._FACTORY,c._json(source),c._json(request),c.request_body(request,policy),c._json(request['response_protocol']),req,SimpleNamespace(_check=lambda:None))
 with patch.object(c,'verify_saved_source_proofs',return_value=None),patch.object(c,'configured_transport_policy',return_value=policy):
  try:item.validate(policy);outcome='ACCEPTED';reason=None
  except ValueError as e:outcome='REJECTED';reason=str(e)
 assert outcome==('ACCEPTED'if name=='valid_indexed'else'REJECTED')
 rows.append({'case':'SemanticRequest.validate '+name,'outcome':outcome,'reason':reason})
Path('/tmp/sec_metrics_issue28_continuous/native-index-independent-review/selector-results.json').write_text(json.dumps({'cases':rows,'test_doubles':['ledger snapshot','native archived-runtime replay','process authority check and source admission for membership probes','transport policy loader'],'actual_new_calls':[0,0,0],'original_fixture_request_files_unchanged':True},indent=2)+'\n')
print(json.dumps(rows,indent=2))
