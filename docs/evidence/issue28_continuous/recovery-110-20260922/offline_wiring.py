from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
import io,json,os,socket,time,hashlib
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.native_request_construction import request_construction_session
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,request_digest,build_plan,execute_capacity_assessment
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_recovery_110 import recorded_authorization
from vnext.canonical import canonical_json_bytes,content_hash
from vnext.capacity_reference_contract import restore_base_request
from vnext import ai_adapter as adapter,invocation_control as control
from tests.vnext.test_capacity_run_material import recorded_response
base=Path('/tmp/sec_metrics_recovery110_wiring_20260922_v2');base.mkdir(exist_ok=False)
evidence=Path(__file__).resolve().parent
req=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')),patch.object(control,'effective_invocation_policy',side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')),request_construction_session(req):
 ledger=recorded_ledger(root=base/'ledger')
 originals=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)
 selected,_=select_native_request_variants(prepared_requests=originals,ledger=ledger,source_references=True);p=selected[0]
 policy,plan=build_plan(p);request=json.loads(p.request_bytes)
 actual110=ROOT/'docs/evidence/issue28_continuous/b13-strict-references-20260922/real-110'
 original_intent=json.loads((actual110/'intent.json').read_text());original_request=json.loads((actual110/'semantic-request.json').read_text())
 assert request_digest(request,policy)==request_digest(original_request,policy)==original_intent['request_digest']
 raw402=(actual110/'wire/raw-response.bin').read_bytes()
 error=adapter.TransportAttemptError('Synthetic HTTP402 for offline wiring',observation=adapter._no_egress_policy_observation(policy=policy,request_bytes=p.provider_request_body_bytes),provider_request_id='',raw_response_bytes=raw402,error_class='HTTP_402')
 with patch.object(adapter,'_deepseek_chat_output_text',side_effect=error):
  old_path,old=execute_capacity_assessment(prepared=p,ledger=ledger,recorded_wire=raw402)
 assert old['terminal']['stop_reason']=='HTTP_402' and not old['native_candidate_evidence_created']
 original_bytes={q:q.read_bytes() for q in old_path.rglob('*') if q.is_file()}
 try:execute_capacity_assessment(prepared=p,ledger=ledger,recorded_wire=raw402)
 except ValueError as e:assert 'CHANNEL_STOPPED' in str(e)
 else:raise AssertionError('No authorization accepted')
 with ledger.locked():
  auth=recorded_authorization(ledger=ledger,original_ordinal=1)
  assert ledger.snapshot()['stopped_channels']==['PROVIDER']
 prior=restore_base_request(request);answer=recorded_response(prior);proof=prior['program_quantity_contract']
 owned={(r['unit_id'],r['source_kind'],r['source_index']) for r in proof['verified_quantity_roles']+proof['verified_nonphysical_references']}
 response={'units':[{'unit_index':i,'reviewed':True,'unresolved':[],'calculation_limits':[]} for i,u in enumerate(answer['units'])],
  'findings':[f for u in answer['units'] for f in u['findings'] if not any((u['unit_id'],e['kind'],e['source_index']) in owned for e in f['evidence'])]}
 wire=canonical_json_bytes(value={'id':'recovery110-offline','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(response)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
 observed=[]
 class FakeResponse(io.BytesIO):headers={'x-request-id':'recovery110-mock-opener'}
 def fake_open(*,fullurl,timeout):
  assert fullurl.full_url=='https://api.deepseek.com/chat/completions' and fullurl.data==p.provider_request_body_bytes and timeout==120
  observed.append(fullurl.data);return FakeResponse(wire)
 with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-a-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=fake_open):
  transport=adapter._build_repository_transport(policy=policy)
  try:transport.complete(prepared_request=p)
  except adapter.AIAdapterError as e:assert 'RESERVATION_OWNER_EGRESS_REQUIRED' in str(e)
  else:raise AssertionError('Unowned egress accepted')
  assert transport.complete(prepared_request=p,egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY).raw_response_bytes==wire
 assert len(observed)==1
 new_path,new=execute_capacity_assessment(prepared=p,ledger=ledger,recorded_wire=wire)
 assert new['terminal']['status']=='SUCCEEDED' and new['native_candidate_evidence_created']
 intent=json.loads((new_path/'intent.json').read_text());assert intent['recovery_authorization_id']==auth['authorization_id']
 with recorded_ledger(root=ledger.root).locked() as reopened:
  state=reopened.snapshot();assert state['counts']==[2,2,0] and state['stopped_channels']==[]
 try:execute_capacity_assessment(prepared=p,ledger=ledger,recorded_wire=wire)
 except ValueError as e:assert 'REDRAW_FORBIDDEN' in str(e)
 else:raise AssertionError('Recovery used twice')
 retained,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger,source_references=True)
 assert variants[0]['original_ordinal']==2 and retained[0].request_bytes==p.request_bytes
 from vnext.capacity_native_assessment import collect_native_assessments
 from vnext.capacity_assessment_input import register_assessment_input,load_registered_input
 partial=collect_native_assessments(prepared_requests=retained,ledger=ledger)
 assert not partial['failed_requests'] and len(partial['recovered_http402_failures'])==1
 assert not partial['all_source_requests_accepted']
 # Complete only the registration boundary affected by recovery; do not rerun the unchanged large Run rehearsal.
 for remaining in selected[1:]:
  old_request=restore_base_request(json.loads(remaining.request_bytes));value=recorded_response(old_request);proof=old_request['program_quantity_contract']
  owned={(r['unit_id'],r['source_kind'],r['source_index']) for r in proof['verified_quantity_roles']+proof['verified_nonphysical_references']}
  response={'units':[{'unit_index':i,'reviewed':True,'unresolved':[],'calculation_limits':[]} for i,u in enumerate(value['units'])],
   'findings':[f for u in value['units'] for f in u['findings'] if not any((u['unit_id'],e['kind'],e['source_index']) in owned for e in f['evidence'])]}
  more=canonical_json_bytes(value={'id':'recovery110-registration-recorded','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(response)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
  _,result=execute_capacity_assessment(prepared=remaining,ledger=ledger,recorded_wire=more)
  assert result['terminal']['status']=='SUCCEEDED'
 registered=register_assessment_input(prepared_requests=selected,ledger=ledger)
 loaded=load_registered_input(data_root=ROOT,source=json.loads(p.source_bytes),requirement=req,mode='RECORDED_TEST_ONLY',input_record_id=registered['input_record_id'],check_export=False)
 assert loaded==registered and not loaded['assessment']['failed_requests']
 assert len(loaded['assessment']['recovered_http402_failures'])==1
 assert original_bytes=={q:q.read_bytes() for q in original_bytes}
 summary={'status':'PASS_ACTUAL_ENTRY_HTTP402_SINGLE_RECOVERY_NATIVE_SUCCESS_AND_REUSE','original110_business_digest_unchanged':True,'request_digest':original_intent['request_digest'],'source_request_count':len(selected),'selected_index':0,'mock_official_opener_calls':len(observed),'failed_ordinal':1,'recovered_ordinal':2,'recorded_counts':[7,7,0],'full_registration_and_reader_pass':True,'large_run_rehearsal_repeated':False,'original_failure_bytes_unchanged':True,'success_reused':True,'restart_replay_pass':True,'one_opportunity_consumed_on_claim':True,'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,'calls':{'provider':0,'paid':0,'sec':0},'requirement_closure_hash':req['requirement_closure_hash'],'execution_authority_hash':content_hash(value=req['execution_authority']),'seconds':round(time.monotonic()-started,3),'complete_company_result':False,'material_root':str(base)}
 (evidence/'offline-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
