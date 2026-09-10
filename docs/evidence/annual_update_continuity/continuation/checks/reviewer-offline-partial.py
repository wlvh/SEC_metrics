from pathlib import Path
import sys,json,copy,hashlib,datetime
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');W=O/'continuation';D=W/'offline-02';sys.path.insert(0,str(R/'scripts'))
from vnext import annual_continuity as f,invocation_control as ctl
from vnext.canonical import strict_json_file,strict_json_loads,canonical_json_bytes,sha256_file,content_hash

def read(p):return strict_json_file(path=p)
def proof(p):return {'path':str(p),'sha256':sha256_file(path=p),'size':p.stat().st_size}
def records(p):return [strict_json_loads(text=l) for l in p.read_text().splitlines() if l.strip()]
code=f.code_identity();assert code['exact_head']=='1ea60fd44a0e401963515102ed2eadfc28f7e851'
log=(W/'offline-02-command.log').read_text()
for n in ('test_current_active_start_without_historical_parameters','test_lost_reference_recovery_and_partial_failure'):
 assert any(l.startswith(n+' ') and l.endswith(' ... ok') for l in log.splitlines())
answer={'record_type':'INDEPENDENT_COMPLETED_OFFLINE_METHODS_CHECK','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK','reviewer_task':'/root/runtime_boundary_review','code':code,'status':'TWO_METHODS_VERIFIED_FULL_SUITE_PENDING','execution_ready':False,'checks':{},'new_actual_provider_paid_sec_calls':[0,0,0]}
for name in ('current-start','failure-case'):
 root=D/name;binding=read(root/'stage/stage-binding.json');stage=binding['stage'];f.validate_stage(stage);f.validate_owner(stage,binding['owner_comment'])
 assert stage['schema_version']==2 and stage['maximum_provider_paid_sec_calls']==[2,2,0] and stage['normal_provider_calls']==2 and stage['conditional_repair_calls']==0
 assert stage['cumulative_provider_paid_sec_limit']==[3,3,0] and stage['update_period_ends']==['2024-12-31','2025-12-31']
 assert stage['reviewed_code']==code and stage['previous_stage']['counts']['provider']==stage['previous_stage']['counts']['paid']==1
 assert stage['previous_stage']['stage_id']=='sha256:7db4fef84baa329b7c17effa9808ae55244d08ec27e9cc318302044622231688'
 assert stage['delegation_source']=='SIMULATED_TEST_DELEGATION_PR41_CONTINUATION_NOT_OWNER_AUTHORITY' and binding['owner_comment']['id']==9999041
 f.check_id(stage['budget_registration'],'registration_id');assert read(root/'budget/registration.json')==stage['budget_registration']
 item={'stage_id':stage['stage_id'],'stage_binding':proof(root/'stage/stage-binding.json'),'grant_kind':'SIMULATED_TEST_ONLY_NOT_REAL_APPROVAL','new_maximum':[2,2,0],'prior_real_counts':[1,1,0],'aggregate_ceiling':[3,3,0]}
 if name=='current-start':
  r=read(root/'result.json');assert r['status']=='NO_CHANGE' and r['execution']=='NOT_EXECUTED' and r['counts']['provider']==r['counts']['paid']==r['counts']['sec_reserved']==0
  assert r['inspection']=={'execution':'NOT_EXECUTED','provider_paid_sec_calls':[0,0,0]} and 'provider_paid_sec_calls' not in r
  assert r['current_published']['provenance']['publication_id']==stage['initial_publication_pointer']['publication_id'] and stage['seed'] is stage['visibility_file'] is None
  assert not (root/'stage/seed-candidate').exists() and not list((root/'budget').glob('provider-*.json'))
  item.update(result=proof(root/'result.json'),new_simulated_controller_counts=[0,0,0],prior_plus_test_counts=[1,1,0])
 else:
  io=read(root/'synthetic-io-binding.json');assert io['kind']=='SAVED_ASSISTANT_CONTENT_WITH_SYNTHETIC_MODEL_ENVELOPE' and io['new_business_calls']==[0,0,0]
  mapping={};derivations=[]
  for p in io['entries']:
   oldroot=Path(p['run_directory']);oldrecords=records(oldroot/'records.jsonl');a=next(x for x in oldrecords if x['record_type']=='AI_EXTRACTION_ATTEMPT')
   req_raw=(oldroot/a['request_body_path']).read_bytes();res_raw=(oldroot/a['raw_response_path']).read_bytes();oldreq=json.loads(req_raw);oldres=json.loads(res_raw)
   req=canonical_json_bytes(value={**oldreq,'model':'deepseek-flash'});res=canonical_json_bytes(value={**oldres,'model':'deepseek-flash','id':'SIMULATED_MODEL_ENVELOPE'})
   assert hashlib.sha256(req_raw).hexdigest()==p['original_request_sha256'] and hashlib.sha256(res_raw).hexdigest()==p['original_response_sha256']
   assert hashlib.sha256(req).hexdigest()==p['synthetic_request_sha256'] and hashlib.sha256(res).hexdigest()==p['synthetic_response_sha256']
   assert json.loads(res)['choices']==oldres['choices'] and p['assistant_content_unchanged'] is True
   assert p['request_changes']==['model'] and p['response_envelope_changes']==['model','id']
   mapping[p['synthetic_request_sha256']]=(req,res,p);derivations.append(p)
  failed=read(root/'failure.json');recovery=read(root/'recovery.json');negative=read(root/'negative-binding.json')
  assert negative['status']=='PASSED_NATIVE_FAILURE_AND_RECOVERY_OFFLINE_IO' and negative['code']==code
  assert negative['actual_new_provider_paid_sec_calls']==[0,0,0] and failed['status']=='CANDIDATE_UPDATE_FAILED' and failed['execution']=='EXECUTED'
  assert failed['inspection']=={'execution':'NOT_EXECUTED','provider_paid_sec_calls':[0,0,0]} and 'provider_paid_sec_calls' not in failed
  assert recovery['status']=='RECOVERED_PRIOR_TRANSACTION' and recovery['execution']=='NOT_EXECUTED' and recovery['counts']['provider']==1
  assert failed['structured_candidate']['B01']['reason_code']=='PASS'
  pointer=read(root/'stage/publication/outputs/active_publication.json');reference=read(root/'stage/successful-candidate.json')
  assert pointer['publication_id']==negative['recovered_publication']==recovery['current_published']['provenance']['publication_id']
  candidates=[]
  for c in sorted((root/'stage/candidates').iterdir()):
   plan=read(c/'plan.json');f.check_id(plan,'plan_id');rs=records(c/'b10/records.jsonl');a=next(x for x in rs if x['record_type']=='AI_EXTRACTION_ATTEMPT')
   req,res,derivation=mapping[a['request_body_sha256']];assert (c/'b10'/a['request_body_path']).read_bytes()==req
   actual=(c/'b10'/a['raw_response_path']).read_bytes();kind='BASE_SYNTHETIC_ENVELOPE_WITH_ORIGINAL_ASSISTANT_CONTENT'
   if a['status']=='FAILED':
    malformed=json.loads(res);malformed['choices'][0]['message']['content']='{}';expected=canonical_json_bytes(value=malformed)
    assert actual==expected;kind='EXPLICIT_NEGATIVE_SYNTHETIC_ASSISTANT_CONTENT_REPLACED_WITH_EMPTY_OBJECT'
   else:assert actual==res
   assert a['model_requested']==a['model_returned']=='deepseek-flash' and a['provider_request_id']=='SIMULATED_HTTP_REPLAY'
   path=next((c/'invocation_control/executions').glob('*.json'));e=read(path);ctl._load_execution_receipt(root=c/'invocation_control',path=path,execution_id=e['execution_id'])
   assert e['counters']=={'real_model_provider_egress_count':1,'paid_model_provider_call_count':1,'mock_transport_invocation_count':0}
   assert len([x for x in rs if x['record_type']=='METRIC_RESULT'])==(1 if e['status']=='SUCCEEDED' else 0)
   candidates.append({'plan_id':plan['plan_id'],'period':plan['prepared_input']['table_input']['target_period'],'native_terminal':e['status'],'raw_response_sha256':hashlib.sha256(actual).hexdigest(),'original_and_derived_io':derivation,'response_scope':kind})
  assert len(candidates)==2 and sorted(x['native_terminal'] for x in candidates)==['FAILED_TERMINAL','SUCCEEDED']
  success=next(x for x in candidates if x['native_terminal']=='SUCCEEDED');bad=next(x for x in candidates if x['native_terminal']=='FAILED_TERMINAL')
  assert success['period']['fiscal_year']==2024 and bad['period']['fiscal_year']==2025 and reference['plan_id']==success['plan_id']
  assert negative['simulated_native_counts']['provider']==negative['simulated_native_counts']['paid']==2 and negative['simulated_native_counts']['failed_plans']==[bad['plan_id']]
  assert not negative['simulated_native_counts']['uncertain_plans'] and not negative['simulated_native_counts']['uncertain_sec']
  item.update(negative_binding=proof(root/'negative-binding.json'),recovery=proof(root/'recovery.json'),failure=proof(root/'failure.json'),synthetic_io=proof(root/'synthetic-io-binding.json'),candidates=candidates,new_simulated_controller_counts=[2,2,0],prior_plus_test_counts=[3,3,0],scope_note='Only original prior1/1/0 is real. These new2/2 native markers describe injected HTTP in isolated offline tests, not paid/API traffic.')
 answer['checks'][name]=item
assert read(O/'live/budget/closed.json')['counts']['provider']==read(O/'live/budget/closed.json')['counts']['paid']==1
assert read(R/'outputs/active_publication.json')==read(W/'baseline.json')['active']
assert f.code_identity()==code
answer.update(recorded_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),log_snapshot_sha256=sha256_file(path=W/'offline-02-command.log'),third_method='STILL_RUNNING_NOT_CREDITED',full_command_binding='NOT_YET_WRITTEN',old_real_closed_stage_unchanged=True)
(W/'independent-offline-partial-checks.json').write_text(json.dumps(answer,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'status':answer['status'],'execution_ready':False,'methods':list(answer['checks'])}))
