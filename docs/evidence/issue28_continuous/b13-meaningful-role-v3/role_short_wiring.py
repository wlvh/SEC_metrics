"""Current B13-only factory/controller bridge; no live calls or old success credit."""
from pathlib import Path
from unittest.mock import patch
import json,socket,time,io,os
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,build_plan,execute_capacity_assessment
from vnext.continuous_call_ledger import recorded_ledger
from vnext.native_unit_index import evidence_json_bytes
from vnext.native_request_construction import request_construction_session
from vnext import ai_adapter as adapter,invocation_control as control
out=Path('/tmp/issue28_meaningful_role_wiring_v3_final_20260923');out.mkdir(exist_ok=False);e=Path(__file__).resolve().parent;started=time.monotonic();r=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
try:validate_wiring_receipt(requirement=r);raise AssertionError('No current receipt should exist')
except (ValueError,FileNotFoundError) as error:prior_error=str(error)
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')),patch.object(control,'effective_invocation_policy',side_effect=AssertionError('NO_LEGACY')),request_construction_session(r):
 prepared=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)
 selected,_=select_native_request_variants(prepared_requests=prepared,ledger=recorded_ledger(root=out/'selection'),source_references=True)
 role_selected,_=select_native_request_variants(prepared_requests=prepared,ledger=recorded_ledger(root=out/'role_selection'),source_references=True,compact_references=True,semantic_role_labels=True)
 old=Path(r['policy']['budget_root'])/'calls/0111';assert selected[0].request_bytes==(old/'semantic-request.json').read_bytes()
 good=role_selected[1];request=json.loads(good.request_bytes);assert not request['required_candidate_assessments']
 answer={'units':[{'unit_index':i,'reviewed':True,'unresolved':[],'calculation_limits':[]} for i in range(len(request['units']))],'findings':[]}
 positive=evidence_json_bytes({'id':'source-role-recorded','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(answer)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
 observed=[];results=[]
 for name,obj,wire,expected in [('valid_empty_group_role_v3',good,positive,'SUCCEEDED'),('original111_current_semantic_rejection',selected[0],(old/'wire/raw-response.bin').read_bytes(),'FAILED_TERMINAL')]:
  policy,plan=build_plan(obj)
  class Reply(io.BytesIO):headers={'x-request-id':'source-role-recorded'}
  def opener(*,fullurl,timeout):
   assert fullurl.data==obj.provider_request_body_bytes and timeout==120;observed.append(name);return Reply(wire)
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=opener):
   adapter._build_repository_transport(policy=policy).complete(prepared_request=obj,egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
  ledger=recorded_ledger(root=out/name);path,result=execute_capacity_assessment(prepared=obj,ledger=ledger,recorded_wire=wire)
  assert result['terminal']['status']==expected,str(result)
  assert result['native_candidate_evidence_created']==(expected=='SUCCEEDED')
  with ledger.locked():assert ledger.snapshot()['counts']==[1,1,0]
  results.append({'name':name,'status':expected,'native_candidate_evidence_created':result['native_candidate_evidence_created']});print(name,expected,flush=True)
summary={'status':'PASS_RECORDED_ROLE_V3_FACTORY_OPENER_CONTROLLER_AND_ORIGINAL111_REJECTION','requirement_closure_hash':r['requirement_closure_hash'],'prior_receipt_error':prior_error,'opt_in_role_variant':True,'recorded_role_v3_only':True,'mock_opener_calls':observed,'results':results,'original111_request_identity_unchanged':True,'original111_current_reuse_credit':False,'old111_terminal_changed':False,'complete_company_result':False,'new_calls':[0,0,0],'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,'seconds':round(time.monotonic()-started,3)}
(e/'role-short-wiring-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
