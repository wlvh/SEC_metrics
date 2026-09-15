"""Synthetic native acceptance and coordinator tests, no provider/SEC calls.

Ledger snapshots, invocation transport and private registration are doubles.
The request factory, digest, indexed mapping and native acceptance are real.
"""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext
from copy import deepcopy
from unittest.mock import patch,Mock
from vnext import capacity_update_input as update,continuous_semantic_calls as calls,ordinary_refresh_cycle as refresh
from vnext.continuous_call_ledger import recorded_ledger
from vnext.native_unit_index import reconstruct_requests,upgrade_request
from vnext.canonical import canonical_json_bytes,content_hash
from vnext.d04_native_assessment import build_acceptance
from tests.vnext.test_native_request_variants import synthetic_source,response_bytes

class NewNativeUpdateTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  self.source,_=synthetic_source();self.requests=reconstruct_requests(self.source);self.policy=SimpleNamespace(model='deepseek-flash')
  self.requirement={'requirement_closure_hash':content_hash(value='current engineering probe')}
  self.prepared=[calls.SemanticRequest(calls._FACTORY,canonical_json_bytes(value=self.source),canonical_json_bytes(value=r),calls.request_body(r,self.policy),canonical_json_bytes(value=r['response_protocol']),self.requirement,None)for r in self.requests]
  self.ledger=recorded_ledger(root=self.root/'ledger');self.state={'rows':[],'counts':[0,0,0],'stopped_channels':[],'requests':set()}
  self.executed=[];self.replays={};self.content_failure=False;self.unknown=False
  self.addCleanup(patch.stopall)
  patch.object(self.ledger,'locked',side_effect=nullcontext).start();patch.object(self.ledger,'snapshot',side_effect=lambda:deepcopy(self.state)).start()
  patch.object(calls,'configured_transport_policy',return_value=self.policy).start()
  patch('vnext.native_assessment_replay.replay_native_response',side_effect=lambda **kw:self.replays[json.loads(kw['prepared'].request_bytes)['request_id']]).start()
  self.prepare=patch.object(update,'prepare_registered_update',side_effect=self.bridge).start()
  self.execute=patch.object(calls,'execute_d04_assessment',side_effect=self.recorded_execute).start()
 def bridge(self,**kwargs):
  if len([r for r in self.state['rows']if r['status']=='SUCCEEDED'])==len(self.requests):return {'registered_input':{'input_record_id':'synthetic-private-registration'}}
  if kwargs.get('allow_incomplete'):return {'prepared_requests':self.prepared}
  raise ValueError('INCOMPLETE_SET')
 def recorded_execute(self,*,prepared,ledger,recorded_wire):
  r=json.loads(prepared.request_bytes);ordinal=len(self.state['rows'])+1;path=self.ledger.root/'calls'/f'{ordinal:04d}';path.mkdir(parents=True)
  digest=calls.request_digest(r,self.policy);self.state['requests'].add(('PROVIDER',digest));self.state['counts']=[ordinal,ordinal,0]
  (path/'intent.json').write_text(json.dumps({'request_digest':digest}))
  (path/'semantic-request.json').write_bytes(prepared.request_bytes)
  status='FAILED'if self.content_failure else 'UNKNOWN_PENDING_RECONCILIATION'if self.unknown else 'SUCCEEDED'
  self.state['rows'].append({'ordinal':ordinal,'channel':'PROVIDER','status':status,'counts':[1,1,0]})
  if self.unknown:self.state['stopped_channels']=['PROVIDER'];raise RuntimeError('INTERRUPTED_AFTER_CLAIM')
  raw=response_bytes(r)
  plan={k:content_hash(value=[k,r['request_id']])for k in ('ai_invocation_plan_id','provider_request_identity','task_contract_hash')}
  plan.update(selected_representation_hash=r['request_id'],source_identity_hash=self.source['semantic_source_id'],requirement_closure_hash=self.requirement['requirement_closure_hash'])
  acceptor=build_acceptance
  if r.get('metric_id')=='B13':
   from vnext.capacity_native_assessment import build_acceptance as acceptor
   value=json.loads(raw)
   for row in value['units']:row['calculation_limits']=[]
   raw=canonical_json_bytes(value=value)
  accepted=acceptor(prepared=prepared,plan=plan,response_body=raw)
  self.replays[r['request_id']]={'revalidation':{'synthetic_current_acceptance_id':content_hash(value=accepted['evidence_record'])}}
  self.executed.append(r['request_id']);return path,{'terminal':{'status':status,'stop_reason':'CONTENT_FAILED'if self.content_failure else '','counts':[1,1,0]}}
 def run_update(self,limit=3,metric='D04'):
  return update.ensure_native_update(source_root=self.root/'source',company_id='sample_entity',metric_id=metric,ledger=self.ledger,max_provider_requests=limit,recorded_wire_factory=lambda p:b'isolated callback')
 def test_default_zero_and_whole_source_reuse_never_execute(self):
  self.assertEqual(self.run_update(0)['status'],'PROVIDER_LIMIT_DEFERRED');self.execute.assert_not_called()
  self.prepare.side_effect=None;self.prepare.return_value={'registered_input':{'input_record_id':'old'}}
  r=self.run_update(3);self.assertEqual(r['status'],'REGISTERED_INPUT_REUSED');self.assertEqual(r['counts'],[0,0,0]);self.execute.assert_not_called()
 def test_finite_partial_success_then_exact_reuse_completes_without_redraw(self):
  first=self.run_update(2);self.assertEqual(first['status'],'PROVIDER_LIMIT_DEFERRED',first);self.assertEqual(first['counts'],[2,2,0]);self.assertEqual(first['attempted_executions'],2)
  second=self.run_update(2);self.assertEqual(second['status'],'NATIVE_INPUT_REGISTERED');self.assertEqual(second['counts'],[1,1,0]);self.assertEqual(len(set(self.executed)),3)
  third=self.run_update(2);self.assertEqual(third['status'],'REGISTERED_INPUT_REUSED');self.assertEqual(third['counts'],[0,0,0])
 def test_failure_has_one_terminal_and_next_trigger_does_not_try_other_format(self):
  self.content_failure=True;r=self.run_update(3);self.assertEqual(r['status'],'NATIVE_REQUEST_FAILED',r);self.assertEqual(r['attempted_executions'],1)
  self.content_failure=False;r=self.run_update(3);self.assertEqual(r['status'],'PRIOR_ATTEMPT_OR_CHANGED_SOURCE_GROUP_REUSE_UNSUPPORTED');self.assertEqual(len(self.executed),1)
 def test_changed_source_matching_old_group_blocks_before_any_new_call(self):
  old_digest=calls.request_digest(self.requests[1],self.policy);self.state['requests'].add(('PROVIDER',old_digest))
  r=self.run_update(3);self.assertEqual(r['status'],'PRIOR_ATTEMPT_OR_CHANGED_SOURCE_GROUP_REUSE_UNSUPPORTED');self.execute.assert_not_called()
 def test_unknown_claim_keeps_count_and_stops_provider(self):
  self.unknown=True;r=self.run_update(3);self.assertEqual(r['status'],'NATIVE_EXECUTION_ERROR');self.assertEqual(r['counts'],[1,1,0]);self.assertTrue(r['stop_provider']);self.assertEqual(r['attempted_executions'],1)
 def test_live_b13_pause_and_recorded_wire_rejection(self):
  self.ledger.live=True
  with self.assertRaisesRegex(ValueError,'WIRE_CANNOT_RUN_LIVE'):self.run_update(3)
  r=update.ensure_native_update(source_root=self.root/'source',company_id='sample_entity',metric_id='B13',ledger=self.ledger,max_provider_requests=3)
  self.assertEqual(r['status'],'LIVE_NATIVE_EXECUTION_PAUSED');self.execute.assert_not_called()
 def test_recorded_b13_uses_native_acceptance_without_lifting_live_pause(self):
  from tests.vnext.test_capacity_utilization_source import quantity_source
  self.source,_=quantity_source('<p>Revenue is recognized when services are delivered.</p>')
  self.requests=reconstruct_requests(self.source)
  self.prepared=[calls.SemanticRequest(calls._FACTORY,canonical_json_bytes(value=self.source),canonical_json_bytes(value=r),calls.request_body(r,self.policy),canonical_json_bytes(value=r['response_protocol']),self.requirement,None)for r in self.requests]
  with patch.object(calls,'execute_capacity_assessment',side_effect=self.recorded_execute):
   r=self.run_update(2,'B13');self.assertEqual(r['status'],'NATIVE_INPUT_REGISTERED',r);self.assertEqual(r['counts'],[1,1,0])
 def test_snapshot_failure_after_success_keeps_consumed_limit_and_stops_provider(self):
  original_snapshot=self.ledger.snapshot.side_effect
  def snapshot():
   if len(self.executed)==1:raise ValueError('LEDGER_READ_INTERRUPTED')
   return original_snapshot()
  self.ledger.snapshot.side_effect=snapshot
  r=self.run_update(3);self.assertEqual(r['status'],'NATIVE_EXECUTION_ERROR');self.assertEqual(r['call_accounting'],'UNKNOWN');self.assertTrue(r['stop_provider']);self.assertEqual(r['counts'],[1,1,0]);self.assertEqual(r['attempted_executions'],2)
 def test_old_success_or_source_errors_are_never_treated_as_missing_credit(self):
  for reason in ('NATIVE_ORIGINAL_ACCEPTANCE_SEMANTICS_CHANGED','NATIVE_ORIGINAL_EVIDENCE_CHANGED','UPDATE_NATIVE_COMPLETE_ORIGINAL_SET_MISSING_OR_AMBIGUOUS','SEMANTIC_SOURCE_INSTALLED_POLICY_CHANGED','SOURCE_POLICY_FILE_MISSING'):
   with self.subTest(reason=reason):
    self.prepare.side_effect=ValueError(reason)
    with self.assertRaisesRegex(ValueError,reason):self.run_update(3)
    self.execute.assert_not_called()
 def test_failed_terminal_then_one_snapshot_error_counts_ordinal_once(self):
  self.content_failure=True;original=self.ledger.snapshot.side_effect;raised=False
  def snapshot():
   nonlocal raised
   if self.executed and not raised:raised=True;raise ValueError('ONE_READ_FAILURE_AFTER_FAILED_TERMINAL')
   return original()
  self.ledger.snapshot.side_effect=snapshot
  r=self.run_update(3);self.assertEqual(r['status'],'NATIVE_EXECUTION_ERROR');self.assertEqual(r['call_accounting'],'KNOWN');self.assertEqual(r['counts'],[1,1,0]);self.assertEqual(r['counts'],self.state['counts']);self.assertEqual(r['attempted_executions'],1)
 def test_invalid_limits_and_d03_cannot_enter(self):
  for limit in (-1,True,241):
   with self.assertRaisesRegex(ValueError,'FINITE_PROVIDER_LIMIT'):self.run_update(limit)
  with self.assertRaisesRegex(ValueError,'METRIC_UNSUPPORTED'):self.run_update(1,'D03')

class RefreshCoordinatorNewNativeTest(unittest.TestCase):
 def test_failure_continues_other_metrics_and_uses_one_shared_limit(self):
  from vnext.continuous_sec_acquisition import SecAcquisitionSession
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp).resolve();session=object.__new__(SecAcquisitionSession);session.data_root=root/'ledger/source-inputs';session.requirement={};counts=[0,0,0]
   session.ledger=SimpleNamespace(root=root/'ledger',live=False,locked=nullcontext,snapshot=lambda:{'counts':list(counts)})
   discovery={'status':'SAVED_SOURCE_DEPENDENCIES_AVAILABLE','requirements_id':'synthetic','requirements':[],'limitations':[]}
   attempts=[]
   def ensure(**kw):
    attempts.append(kw['max_provider_requests']);counts[0]+=1;counts[1]+=1
    return {'company_id':kw['company_id'],'metric_id':'D04','status':'NATIVE_REQUEST_FAILED','attempted_executions':1,'counts':[1,1,0],'call_accounting':'KNOWN','stop_provider':False}
   with patch.object(refresh,'_check_session'),patch.object(refresh,'initialize_source_inputs'),patch.object(refresh,'_failed_urls',return_value=set()),patch.object(refresh,'discover_saved_source_requirements',return_value=discovery),patch.object(update,'ensure_native_update',side_effect=ensure),patch.object(refresh,'run_company',return_value={'status':'UPDATES_PARTIAL','metrics':[]})as run:
    result=refresh.refresh_and_process(session=session,state_root=root/'state',company_ids=['pfizer','enphase_energy'],metric_ids=['A08','D04'],max_sec_requests=0,max_provider_requests=1)
   self.assertEqual(attempts,[1]);self.assertEqual(run.call_count,2);self.assertEqual(result['cumulative_ledger_delta'],[1,1,0]);self.assertEqual(result['calls'],{'provider':0,'paid':0,'sec':0});self.assertEqual(len(result['native_preparations']),1)

if __name__=='__main__':unittest.main(verbosity=2)
