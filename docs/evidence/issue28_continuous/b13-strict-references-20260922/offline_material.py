from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import io,json,os,socket,time
from vnext.canonical import canonical_json_bytes,content_hash,strict_json_loads,sha256_file
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,build_plan,execute_capacity_assessment,execute_feasibility
from vnext.continuous_call_ledger import recorded_ledger
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.capacity_reference_contract import VERSION,restore_base_request
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
from vnext import invocation_control as control,ai_adapter as adapter
from tests.vnext.test_capacity_run_material import recorded_response
base=Path('/tmp/sec_metrics_reference_20260922');base.mkdir(exist_ok=False)
evidence=Path(__file__).resolve().parent
started=time.monotonic();requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
def response(request):
 old=restore_base_request(request);value=recorded_response(old);proof=old['program_quantity_contract']
 owned={(r['unit_id'],r['source_kind'],r['source_index']) for r in proof['verified_quantity_roles']+proof['verified_nonphysical_references']}
 return {'units':[{'unit_index':i,'reviewed':True,'unresolved':[],'calculation_limits':[]} for i,u in enumerate(value['units'])],
  'findings':[f for u in value['units'] for f in u['findings'] if not any((u['unit_id'],e['kind'],e['source_index']) in owned for e in f['evidence'])]}
def wire(value):
 return canonical_json_bytes(value={'id':'b13-reference-recorded','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(value)},'finish_reason':'stop'}],
  'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')),patch.object(control,'effective_invocation_policy',side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')),request_construction_session(requirement):
 for company,count in [('enphase_energy',6),('ford_motor_company',11)]:
  ledger=recorded_ledger(root=base/company/'ledger')
  originals=prepare_requests(company_id=company,metric_id='B13',reference_context=True,program_quantity_roles=True)
  selected,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger,source_references=True)
  assert len(selected)==count and all(r['variant']==VERSION for r in variants)
  plans=[build_plan(p)[1] for p in selected]
  print(company,'prepared',count,'seconds',time.monotonic()-started,flush=True)
  p=selected[0];r=json.loads(p.request_bytes);raw=wire(response(r));policy,_=build_plan(p);observed=[]
  class FakeResponse(io.BytesIO):headers={'x-request-id':'b13-reference-offline'}
  def fake_open(*,fullurl,timeout):
   assert fullurl.full_url=='https://api.deepseek.com/chat/completions' and fullurl.data==p.provider_request_body_bytes and timeout==120
   observed.append(fullurl.data);return FakeResponse(raw)
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-test-not-a-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=fake_open):
   transport=adapter._build_repository_transport(policy=policy)
   try:transport.complete(prepared_request=p)
   except adapter.AIAdapterError as e:assert 'RESERVATION_OWNER_EGRESS_REQUIRED' in str(e)
   else:raise AssertionError('unowned egress accepted')
   assert transport.complete(prepared_request=p,egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY).raw_response_bytes==raw
  assert len(observed)==1
  try:replace(p,provider_request_body_bytes=b'{}').validate(policy)
  except ValueError as e:assert 'PAYLOAD_CHANGED' in str(e)
  else:raise AssertionError('altered body accepted')
  try:execute_feasibility(prepared=p,ledger=ledger,recorded_wire=raw)
  except ValueError as e:assert 'B13_REQUIRES_NATIVE_ASSESSMENT_ENTRY' in str(e)
  else:raise AssertionError('legacy diagnostic accepted')
  execute_set=selected if company=='enphase_energy' else selected[:1]
  for item in execute_set:
   path,outcome=execute_capacity_assessment(prepared=item,ledger=ledger,recorded_wire=wire(response(json.loads(item.request_bytes))))
   assert outcome['terminal']['status']=='SUCCEEDED',outcome
  partial=collect_native_assessments(prepared_requests=selected,ledger=ledger)
  assert partial['native_request_variants']==[VERSION]*count
  badledger=recorded_ledger(root=base/company/'missing-unit')
  bad=response(r);bad['units'].pop()
  _,outcome=execute_capacity_assessment(prepared=p,ledger=badledger,recorded_wire=wire(bad))
  assert outcome['terminal']['status']=='FAILED_TERMINAL' and not outcome['native_candidate_evidence_created']
  row={'company_id':company,'request_count':count,'plans':[{'request_id':json.loads(p.request_bytes)['request_id'],'estimated_context_tokens':plan['observability']['estimated_context_tokens']} for p,plan in zip(selected,plans)],'opener_and_controller':'PASS','missing_unit':'REJECTED'}
  if company=='enphase_energy':
   assert partial['all_source_requests_accepted']
   # Ordinary default selection must consume existing exact successor successes without buying calls.
   retained,report=select_native_request_variants(prepared_requests=originals,ledger=ledger)
   assert [p.request_bytes for p in retained]==[p.request_bytes for p in selected] and all(x['original_ordinal'] is not None for x in report)
   registered=register_assessment_input(prepared_requests=selected,ledger=ledger)
   data=base/company/'data';run=base/company/'run'
   install_inputs(data_root=data,company_id=company,assessment_mode='RECORDED_TEST_ONLY',assessment_input_id=registered['input_record_id'],request_context_format=json.loads(selected[0].source_bytes)['request_context_format'],program_quantity_roles=True)
   created=create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='B13')
   rendered=render_ordinary_run(data_root=data,run_dir=run)
   assert created['manifest']['status']=='OPEN' and rendered['receipt']['semantic_assessment_mode']=='RECORDED_TEST_ONLY'
   row.update(run_id=created['manifest']['run_id'],result_id=created['result']['result_id'],full_native_run='PASS',default_exact_success_reuse='PASS')
  else:assert not partial['all_source_requests_accepted'] and partial['proposed_branch']=='INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE'
  rows.append(row);print(company,'finished','seconds',time.monotonic()-started,flush=True)
summary={'status':'PASS_REFERENCE_CONTRACT_FACTORY_NATIVE_RUN_AND_WIRING','requirement_closure_hash':requirement['requirement_closure_hash'],'execution_authority_hash':content_hash(value=requirement['execution_authority']),'companies':rows,'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,'calls':{'provider':0,'paid':0,'sec':0},'seconds':round(time.monotonic()-started,3),'production_authorized':False,'real_semantic_credit':False,'external_material_root':str(base)}
(evidence/'offline-material-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)
