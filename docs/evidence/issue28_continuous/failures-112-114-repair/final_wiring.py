"""Shortest current factory/opener/controller checks for both changed representations."""
from pathlib import Path
from unittest.mock import patch
import json,io,os,socket,time
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,execute_capacity_assessment,execute_d04_assessment,build_plan,request_digest
from vnext.native_request_construction import request_construction_session
from vnext.native_unit_index import evidence_json_bytes
from vnext.capacity_reference_contract import restore_base_request
from tests.vnext.test_capacity_run_material import recorded_response as capacity_response
from tests.vnext.test_d04_run_material import recorded_response as d04_response
from vnext import ai_adapter as adapter,invocation_control as control
base=Path('/tmp/issue28_failure_contract_wiring_ad0b');base.mkdir(exist_ok=True);e=Path(__file__).resolve().parent;started=time.monotonic();r=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
try:validate_wiring_receipt(requirement=r);raise AssertionError('stale wiring accepted')
except (ValueError,FileNotFoundError) as error:prior_error=str(error)
ledger=recorded_ledger(root=base/'ledger');observed=[];outcomes=[];reused=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')),patch.object(control,'effective_invocation_policy',side_effect=AssertionError('NO_LEGACY_DEFAULT')),request_construction_session(r):
 for company,metric in [('enphase_energy','B13'),('paramount_skydance_paramount_global','D04')]:
  prepared=prepare_requests(company_id=company,metric_id=metric,native=metric=='D04',reference_context=True,complete_response_contract=metric=='D04',program_quantity_roles=metric=='B13')
  selected,variants=select_native_request_variants(prepared_requests=prepared,ledger=ledger,source_references=metric=='B13',compact_references=metric=='B13')
  for obj,variant in list(zip(selected,variants))[:2 if metric=='B13' else 1]:
   request=json.loads(obj.request_bytes)
   if variant['original_ordinal'] is not None:
    reused.append(variant['original_ordinal']);outcomes.append({'metric':metric,'ordinal':variant['original_ordinal'],'request_id':request['request_id']});print('REUSE_RECORDED',metric,variant['original_ordinal'],flush=True);continue
   if metric=='B13':
    original=restore_base_request(request);response=capacity_response(original);proof=original['program_quantity_contract'];owned={(x['unit_id'],x['source_kind'],x['source_index']) for x in proof['verified_quantity_roles']+proof['verified_nonphysical_references']};books=request['response_protocol']['classification_codebooks'];findings=[]
    for row in response['units']:
     for finding in row['findings']:
      if any((row['unit_id'],x['kind'],x['source_index']) in owned for x in finding['evidence']):continue
      refs=[{'VISIBLE_BLOCK':'B','NATIVE_FACT':'F'}[x['kind']]+str(x['source_index']) for x in finding['evidence']]
      findings.append([books[k].index(finding[k]) for k in ('kind','subject','timing')]+[refs,'Recorded source classification '+','.join(refs)])
    answer={'units':[{'unit_index':i,'reviewed':True,'unresolved':[],'calculation_limits':[]} for i in range(len(request['units']))],'findings':findings}
   else:
    answer=d04_response(request);assert b'\xcd\xbe' in obj.provider_request_body_bytes
    old=json.loads((Path(r['policy']['budget_root'])/'calls/0113/intent.json').read_text());assert request_digest(request,build_plan(obj)[0])==old['request_digest']
   wire=evidence_json_bytes({'id':'failure-contract-offline','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(answer,ensure_ascii=False)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
   policy,plan=build_plan(obj)
   class Reply(io.BytesIO):headers={'x-request-id':'failure-contract-offline'}
   def opener(*,fullurl,timeout):
    assert fullurl.data==obj.provider_request_body_bytes and timeout==120;observed.append(metric);return Reply(wire)
   with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=opener):
    adapter._build_repository_transport(policy=policy).complete(prepared_request=obj,egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
   execute=execute_capacity_assessment if metric=='B13' else execute_d04_assessment
   path,outcome=execute(prepared=obj,ledger=ledger,recorded_wire=wire);assert outcome['terminal']['status']=='SUCCEEDED',str(outcome);outcomes.append({'metric':metric,'ordinal':int(path.name),'request_id':request['request_id']})
   print('PASS_CURRENT_CONTROLLER',metric,path.name,flush=True)
 with ledger.locked():assert ledger.snapshot()['counts']==[3,3,0]
result={'status':'PASS_CURRENT_TYPED_COMPACT_AND_LOSSLESS_INDEXED_FACTORY_CONTROLLER','requirement_closure_hash':r['requirement_closure_hash'],'stale_wiring_rejected':prior_error,'mock_opener_calls_this_launch':observed,'prior_completed_recorded_calls_reused':reused,'recorded_native_calls':outcomes,'new_real_calls':[0,0,0],'original113_indexed_digest_unchanged':True,'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,'seconds':round(time.monotonic()-started,3)}
(e/'current-wiring-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
