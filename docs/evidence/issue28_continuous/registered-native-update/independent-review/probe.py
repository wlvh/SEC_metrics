"""Independent isolated guard probes; no model/SEC calls or fixed journal edits."""
import vnext
vnext.__path__.insert(0,'/tmp/sec_metrics_issue28_continuous/native-update-patch/after/scripts/vnext')
from copy import deepcopy
from contextlib import nullcontext
from dataclasses import replace
import hashlib,json,socket,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from vnext.canonical import content_hash,canonical_json_bytes,strict_json_file
from vnext import capacity_update_input as update,capacity_assessment_input as registry,continuous_semantic_calls as calls
from vnext.continuous_call_ledger import recorded_ledger,CallLedger,_FACTORY as LEDGER_FACTORY
from tests.vnext.test_native_request_variants import NativeRequestVariantsTest,synthetic_source
from vnext.native_unit_index import reconstruct_requests,upgrade_request

def seal(v,key='semantic_source_id'):
 v[key]=content_hash(value={k:x for k,x in v.items()if k!=key});return v

class IndependentUpdateReview(unittest.TestCase):
 def test_actual_source_equivalence_is_complete_and_does_not_accept_new_content(self):
  original=json.loads(Path('/tmp/sec_metrics_issue28_continuous/b13-scope-native-current/ledger/calls/0001/source.json').read_text())
  current=deepcopy(original);current['source_proofs'][0]['request_attempt_id']='new-provenance-only';seal(current)
  self.assertFalse(update.source_equivalence(current=current,original=original)['new_provider_execution'])
  attacks={
   'missing-unit':lambda s:s['units'].pop(),
   'missing-document':lambda s:s['documents'].pop(),
   'missing-proof':lambda s:s['source_proofs'].pop(),
   'duplicate-proof':lambda s:s['source_proofs'].append(deepcopy(s['source_proofs'][0])),
   'changed-url':lambda s:s['source_proofs'][0].update(source_url='https://www.sec.gov/changed.xml'),
   'changed-body':lambda s:s['source_proofs'][0].update(content_sha256='b'*64),
   'changed-unit-content':lambda s:s['units'][0]['payload'].update(independent_changed_fact='Actual new input'),
   'incomplete-flag':lambda s:s.update(source_serialization_complete=False),
   'changed-format':lambda s:s.update(request_context_format='new-format'),
   'changed-response-contract':lambda s:s.update(response_contract_version='new-output'),
   'changed-annual-period':lambda s:s['prepared_annual_input']['table_input']['target_period'].update(period_end='2026-12-31')}
  for name,attack in attacks.items():
   with self.subTest(attack=name):
    bad=deepcopy(current);attack(bad);seal(bad)
    with self.assertRaises(ValueError):update.source_equivalence(current=bad,original=original)

 def test_schema2_loader_replays_current_acceptor_and_rejects_rehashed_packet_changes(self):
  fixture=NativeRequestVariantsTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
  assessment,rows=fixture.collect(fixture.mixed,failed_original=True)
  source=fixture.source
  body={'record_type':'D04_REGISTERED_NATIVE_ASSESSMENT_INPUT','schema_version':2,'source_id':source['semantic_source_id'],
        'company_id':source['company_id'],'requirement_closure_hash':fixture.requirement['requirement_closure_hash'],
        'mode':'RECORDED_TEST_ONLY','assessment':assessment,'native_requests':rows,'new_call_authority':False,
        'production_authorized':False,'response_contract_version':source['response_contract_version'],'source_snapshot':source}
  packet=seal(body,'input_record_id');journal=fixture.root/'independent-journal';folder=journal/registry.input_key(source,fixture.requirement);folder.mkdir(parents=True)
  data=fixture.root/'data';(data/'config').mkdir(parents=True);export=data/registry.EXPORT_PATHS['D04']
  def load(value,*,mode='RECORDED_TEST_ONLY',export_value=None):
   seal(value,'input_record_id');path=folder/(value['input_record_id'][7:]+'.json');path.write_bytes(canonical_json_bytes(value=value))
   export.write_bytes(canonical_json_bytes(value=value if export_value is None else export_value))
   return registry.load_registered_input(data_root=data,source=source,requirement=fixture.requirement,mode=mode,input_record_id=value['input_record_id'])
  with patch.object(registry,'_journal',return_value=journal),patch('vnext.continuous_call_policy.configured_transport_policy',return_value=fixture.policy):
   loaded=load(deepcopy(packet));self.assertEqual(loaded['source_snapshot'],source);self.assertEqual(loaded['native_requests'],rows)
   def wrong_snapshot(p):p['source_snapshot']['units'].pop();seal(p['source_snapshot'])
   def new_request_id(p):p['native_requests'][0]['request_id']='sha256:'+'1'*64
   def lost_summary(p):p['assessment']['completed'].pop();seal(p['assessment'],'assessment_set_id')
   def old_failed(p):p['native_requests'][0]['terminal']['status']='FAILED'
   def changed_response(p):p['native_requests'][0]['assistant_output']='{"units":[]}'
   for name,attack in [('source-snapshot',wrong_snapshot),('new-request-id',new_request_id),('lost-summary',lost_summary),('old-failure',old_failed),('changed-response',changed_response),('old-schema-snapshot',lambda p:p.update(schema_version=1)),('mode',lambda p:p.update(mode='LIVE'))]:
    with self.subTest(attack=name):
     bad=deepcopy(packet);attack(bad)
     with self.assertRaises(ValueError):load(bad)
   forged=deepcopy(packet);forged['source_snapshot']['documents'].pop();seal(forged['source_snapshot']);seal(forged,'input_record_id')
   with self.assertRaises(ValueError):load(deepcopy(packet),export_value=forged)
   from vnext import d04_native_assessment
   with patch.object(d04_native_assessment,'build_acceptance',side_effect=ValueError('CURRENT_ACCEPTOR_REJECTED')):
    with self.assertRaisesRegex(ValueError,'CURRENT_ACCEPTOR_REJECTED'):load(deepcopy(packet))

 def test_selector_uses_exact_successes_and_refuses_duplicate_or_changed_success(self):
  source,_=synthetic_source();requests=reconstruct_requests(source);policy=SimpleNamespace(model='deepseek-flash')
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp).resolve();ledger=recorded_ledger(root=root/'ledger')
   prepared=[calls.SemanticRequest(calls._FACTORY,canonical_json_bytes(value=source),canonical_json_bytes(value=r),calls.request_body(r,policy),canonical_json_bytes(value=r['response_protocol']),{},None)for r in requests]
   rows=[]
   for i in range(2):
    d=ledger.root/'calls'/f'{i+1:04d}';d.mkdir(parents=True);(d/'semantic-request.json').write_bytes(prepared[0].request_bytes)
    rows.append({'channel':'PROVIDER','status':'SUCCEEDED','ordinal':i+1})
   with patch.object(ledger,'locked',side_effect=nullcontext),patch.object(ledger,'snapshot',return_value={'rows':rows}),patch.object(calls,'configured_transport_policy',return_value=policy),patch('vnext.native_assessment_replay.replay_native_response',return_value={'revalidation':{}})as replay:
    with self.assertRaisesRegex(ValueError,'MULTIPLE_SUCCESSFUL_VERSIONS'):calls.select_native_request_variants(prepared_requests=prepared,ledger=ledger)
    rows[1]['status']='FAILED'
    selected,report=calls.select_native_request_variants(prepared_requests=prepared,ledger=ledger)
    self.assertEqual(selected[0].request_bytes,prepared[0].request_bytes);self.assertEqual(report[0]['original_ordinal'],1)
    self.assertTrue(all(r['original_ordinal']is None for r in report[1:]))
    bad=deepcopy(requests[0]);bad['purpose']='tampered-with-original-id';(ledger.root/'calls/0001/semantic-request.json').write_bytes(canonical_json_bytes(value=bad))
    with self.assertRaisesRegex(ValueError,'SAVED_REQUEST_CHANGED'):calls.select_native_request_variants(prepared_requests=prepared,ledger=ledger)

 def test_duplicate_complete_source_sets_do_not_register_an_arbitrary_winner(self):
  source,_=synthetic_source();source['source_proofs']=[{'source_url':'https://www.sec.gov/a','accession':'a','document_name':'a','content_sha256':'a'*64,'request_attempt_id':'old'}];seal(source)
  second=deepcopy(source);second['source_proofs'][0]['request_attempt_id']='different-provenance';seal(second)
  requests=reconstruct_requests(source);policy=SimpleNamespace(model='deepseek-flash')
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp).resolve();ledger=recorded_ledger(root=root/'ledger');data=root/'source';(data/'evidence').mkdir(parents=True);(data/'evidence/requests_log.csv').write_text('fixture-only')
   template=calls.SemanticRequest(calls._FACTORY,canonical_json_bytes(value=source),canonical_json_bytes(value=requests[0]),calls.request_body(requests[0],policy),canonical_json_bytes(value=requests[0]['response_protocol']),{},None)
   rows=[]
   for i,original in enumerate((source,second),start=1):
    path=ledger.root/'calls'/f'{i:04d}';path.mkdir(parents=True);(path/'source.json').write_bytes(canonical_json_bytes(value=original))
    rows.append({'channel':'PROVIDER','status':'SUCCEEDED','ordinal':i})
   with patch('vnext.requirements.load_requirement_snapshot',return_value={'policy':{'budget_root':str(root/'fixed')}}),patch.object(calls,'prepare_requests',return_value=[template]),patch.object(ledger,'locked',side_effect=nullcontext),patch.object(ledger,'snapshot',return_value={'rows':rows}),patch.object(calls,'configured_transport_policy',return_value=policy),patch.object(calls,'select_native_request_variants',side_effect=lambda **kw:(kw['prepared_requests'],[])),patch('vnext.capacity_native_assessment.collect_native_assessments',return_value={'all_source_requests_accepted':True,'failed_requests':[]}),patch.object(registry,'register_assessment_input')as register:
    with self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS'):
     update.prepare_registered_update(source_root=data,company_id=source['company_id'],metric_id='D04',options={'assessment_mode':'RECORDED_TEST_ONLY','complete_response_contract':True},ledger=ledger)
    register.assert_not_called()
    rows[0]['status']=rows[1]['status']='FAILED'
    with self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS'):
     update.prepare_registered_update(source_root=data,company_id=source['company_id'],metric_id='D04',options={'assessment_mode':'RECORDED_TEST_ONLY','complete_response_contract':True},ledger=ledger)
    register.assert_not_called()

 def test_modes_factory_root_and_replay_egress_are_rejected(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp).resolve();ledger=recorded_ledger(root=root/'recorded');requirement={'policy':{'budget_root':str(root/'fixed')}}
   for mode in ('LIVE',):
    with self.assertRaisesRegex(ValueError,'LEDGER_FACTORY_OR_MODE_CHANGED'):update._ledger(requirement,mode,ledger)
   bad=CallLedger(factory=LEDGER_FACTORY,root=root/'wrong-live',binding={},live=True)
   with self.assertRaisesRegex(ValueError,'LEDGER_FACTORY_OR_MODE_CHANGED'):update._ledger(requirement,'LIVE',bad)
   with self.assertRaisesRegex(ValueError,'LEDGER_FACTORY_OR_MODE_CHANGED'):update._ledger(requirement,'RECORDED_TEST_ONLY',{'_factory':'forged'})
   with self.assertRaisesRegex(ValueError,'REPLAY_OBJECT_CANNOT_EXECUTE'):
    calls._execute_semantic(prepared=SimpleNamespace(request_bytes=b'{}',replay_only=True),ledger=ledger,recorded_wire=None,native_assessment=True)

if __name__=='__main__':
 with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
  unittest.main(verbosity=2)
