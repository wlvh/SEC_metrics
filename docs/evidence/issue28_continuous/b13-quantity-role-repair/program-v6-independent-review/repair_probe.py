"""Independent bounded V6 review: synthetic references, no network or live credit."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib,json,socket,tempfile
from tests.vnext.test_capacity_utilization_source import quantity_source
from tests.vnext.test_capacity_program_roles import answer,acceptance
from vnext.capacity_program_roles import program_source,original_program_records
from vnext.capacity_semantic_review import requests_from_source,validate_response
from vnext.capacity_utilization_source import calculate_source_comparable_pair
from vnext.canonical import content_hash,canonical_json_bytes
from vnext import capacity_update_input as update,ordinary_update_cycle as cycle
rows=[]
def capture(label,fn,expected=None):
 try:
  value=fn()
 except ValueError as exc:
  assert expected and expected in str(exc),(label,str(exc));rows.append({'case':label,'outcome':'REJECTED','reason':str(exc)});return
 assert expected is None,(label,'UNEXPECTED_ACCEPT');rows.append({'case':label,'outcome':'PASS','value':value})
def check(source,req,res):return acceptance(source,req,res)['evidence_status']
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')):
 s,raw=quantity_source('<p>For fiscal year 2025, we produced 80 widgets worldwide.</p><p>For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.</p>');s=program_source(s);q=requests_from_source(s)[0];a=answer(q)
 capture('program_pair_candidate_evidence',lambda:check(s,q,a))
 capture('original_source_calculator_pair',lambda:calculate_source_comparable_pair(source=s,raw_bytes_by_id=raw)['result']['value'])
 for name,change in [('omit_unit',lambda z:z['units'].clear()),('duplicate_unit',lambda z:z['units'].append(deepcopy(z['units'][0]))),('false_review',lambda z:z['units'][0].update(reviewed=False))]:
  bad=deepcopy(a);change(bad)
  try:check(s,q,bad)
  except ValueError as exc:rows.append({'case':name,'outcome':'REJECTED','reason':str(exc)})
  else:raise AssertionError(name)
 for kind in ['OTHER_CONTEXT','HISTORICAL_STATEMENT','ACTUAL_PRODUCTION','AVAILABLE_CAPACITY']:
  bad=deepcopy(a);b=next(b for b in s['units'][0]['payload']['blocks']if '80 widgets'in b['text'])
  bad['units'][0]['findings']=[{'kind':kind,'subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT','reason':'Independent source-role contradiction probe','evidence':[{'kind':'VISIBLE_BLOCK','source_index':b['block_index']}]}]
  try:check(s,q,bad)
  except ValueError as exc:rows.append({'case':'model_kind_'+kind,'outcome':'REJECTED','reason':str(exc)})
  else:
   assert kind in {'OTHER_CONTEXT','HISTORICAL_STATEMENT'}
   checked=validate_response(request=q,raw_response=canonical_json_bytes(value=bad),source=s)
   assert {'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY'}<={f['kind']for f in checked['findings']}
   rows.append({'case':'redundant_model_'+kind,'outcome':'PROGRAM_ROLE_RETAINED','calculator_value':calculate_source_comparable_pair(source=s,raw_bytes_by_id=raw)['result']['value']})
 bad=deepcopy(s);bad['units'][0]['payload']['blocks'][-1]['text']='Changed source text';bad['semantic_source_id']=content_hash(value={k:v for k,v in bad.items()if k!='semantic_source_id'})
 capture('original_raw_vs_resigned_source',lambda:original_program_records(source=bad,raw_bytes_by_id=raw),'SOURCE_BLOCK_CHANGED')
 for field in ['program_quantity_contract','program_quantity_role_contract_version']:
  bad=deepcopy(q);bad.pop(field);bad['request_id']=content_hash(value={k:v for k,v in bad.items()if k!='request_id'})
  try:check(s,bad,answer(bad))
  except ValueError as exc:rows.append({'case':'resigned_request_remove_'+field,'outcome':'REJECTED','reason':str(exc)})
  else:raise AssertionError(field)
 observed=[]
 def prepare(**kwargs):
  observed.append(deepcopy(kwargs['options']))
  return {'registered_input':{'input_record_id':'synthetic-old-default-input'}}
 with patch.object(update,'prepare_registered_update',side_effect=prepare):
  returned=update.ensure_native_update(source_root=Path('/tmp/synthetic-source'),company_id='enphase_energy',metric_id='B13',ledger=SimpleNamespace(live=False),max_provider_requests=1)
 with tempfile.TemporaryDirectory()as temporary,patch.object(cycle,'load_requirement_snapshot',return_value={'requirement_closure_hash':'synthetic-review'}):
  p=Path(temporary);configuration=cycle._config(p/'history',p/'source','enphase_energy',['B13'],'RECORDED_TEST_ONLY')
 mismatch=observed[0]!=configuration['registered_update_options'];assert not mismatch
 rows.append({'case':'finite_native_preparation_vs_current_run_contract','outcome':'CONFIRMED_MATCH_AFTER_FIX','prepare_options':observed[0],'ordinary_run_options':configuration['registered_update_options'],'ensure_return':returned['status'],'boundary_double':'Only prepare_registered_update; real ensure_native_update and _config. No actual source execution or model call.'})
result={'patch_sha256':hashlib.sha256(Path('/tmp/sec_metrics_issue28_continuous/b13-program-v6.patch').read_bytes()).hexdigest(),'rows':rows,'new_calls':[0,0,0],'evidence_type':'SYNTHETIC_SOURCE_NATIVE_ACCEPTOR_AND_CALCULATOR_PLUS_COORDINATOR_BOUNDARY_PROBE','real_company_credit':False}
Path(__file__).with_name('repair-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
