"""New actual-source recorded chain, never a retry or upgrade of original113."""
from pathlib import Path
from unittest.mock import patch
import json,socket,time,io,os
from vnext.canonical import strict_json_loads,sha256_bytes
from vnext.r6_semantic_source import _bytes
from vnext.native_unit_index import evidence_json_bytes as _record_bytes
from vnext.continuous_semantic_calls import prepare_requests,execute_d04_assessment,build_plan
from vnext.continuous_call_ledger import recorded_ledger
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from tests.vnext.test_d04_run_material import recorded_response
from vnext import ai_adapter as adapter
from vnext import invocation_control as control
base=Path('/tmp/issue28_paramount_lossless_recorded_v3');base.mkdir(exist_ok=False);evidence=Path(__file__).resolve().parent;started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')):
 prepared=prepare_requests(company_id='paramount_skydance_paramount_global',metric_id='D04',native=True,reference_context=True,complete_response_contract=True)
 ledger=recorded_ledger(root=base/'ledger');observed=[];greek=[]
 for item in prepared:
  request=strict_json_loads(text=item.request_bytes.decode());wire=_record_bytes({'id':'new-lossless-recorded','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(recorded_response(request),ensure_ascii=False)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
  policy,plan=build_plan(item)
  if '\u037e' in item.request_bytes.decode():
   greek.append(request['request_id'])
   assert b'\xcd\xbe' in item.provider_request_body_bytes and '\u037e' in json.loads(item.provider_request_body_bytes)['messages'][1]['content']
   class Reply(io.BytesIO):headers={}
   def opener(*,fullurl,timeout):
    assert fullurl.data==item.provider_request_body_bytes;observed.append(sha256_bytes(content=fullurl.data));return Reply(wire)
   with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-a-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=opener):
    adapter._build_repository_transport(policy=policy).complete(prepared_request=item,egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
  path,outcome=execute_d04_assessment(prepared=item,ledger=ledger,recorded_wire=wire)
  assert outcome['terminal']['status']=='SUCCEEDED',str(path)+str(outcome)
  print('RECORDED',path.name,flush=True)
 assert greek and observed
 registered=register_assessment_input(prepared_requests=prepared,ledger=ledger)
 source=strict_json_loads(text=prepared[0].source_bytes.decode())
 install_inputs(data_root=base/'data',company_id='paramount_skydance_paramount_global',metric_id='D04',assessment_mode='RECORDED_TEST_ONLY',assessment_input_id=registered['input_record_id'],request_context_format=source['request_context_format'],complete_response_contract=True)
 created=create_normal_run(data_root=base/'data',run_dir=base/'run',company_id='paramount_skydance_paramount_global',metric_id='D04');rendered=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
 for name,raw in rendered['files'].items():
  p=base/'rows'/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(raw)
 report={'status':'PASS_NEW_PARAMOUNT_LOSSLESS_RECORDED_NATIVE_CHAIN','groups':len(prepared),'greek_request_ids':greek,'observed_wire_hashes':observed,'run_id':created['manifest']['run_id'],'result_id':created['result']['result_id'],'new_real_calls':[0,0,0],'old113_changed':False,'root':str(base),'seconds':round(time.monotonic()-started,3)}
 (base/'summary.json').write_text(json.dumps(report,indent=2)+'\n');(evidence/'paramount-lossless-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
