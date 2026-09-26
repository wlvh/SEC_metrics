from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
import io,json,os,socket,tarfile,time
from vnext import ai_adapter as adapter,invocation_control as control
from vnext.canonical import canonical_json_bytes,strict_json_loads,sha256_bytes
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests,build_plan,execute_capacity_assessment,execute_feasibility
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.capacity_semantic_review import _restore_units
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
base=Path('/tmp/sec_metrics_issue28_continuous/b13-v6-current/wiring').resolve();base.mkdir(exist_ok=False)
plan=json.loads((ROOT/'docs/evidence/issue28_continuous/b13-quantity-integration/program-owned-v6/company-task-request-plan.json').read_text())
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');rows=[];started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')),patch.object(control,'effective_invocation_policy',side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')),request_construction_session(requirement):
 for company in plan['companies']:
  requests=prepare_requests(company_id=company['company_id'],metric_id='B13',reference_context=True,program_quantity_roles=True)
  assert len(requests)==len(company['groups'])
  for p,g in zip(requests,company['groups']):
   r=json.loads(p.request_bytes);assert r['request_id']==g['request_id'];assert sha256_bytes(content=p.provider_request_body_bytes)==g['provider_body_sha256']
  p=requests[0];r=json.loads(p.request_bytes);contract=r['program_quantity_contract'];policy,invocation=build_plan(p)
  owned={(x['unit_id'],x['source_kind'],x['source_index']) for x in contract['verified_quantity_roles']+contract['verified_nonphysical_references']}
  response={'request_id':r['request_id'],'units':[]}
  for unit in _restore_units(r['units'],r['shared_source_dictionaries']):
   findings=[{'kind':'OTHER_CONTEXT','subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT',
    'evidence':[{'kind':x['kind'],'source_index':x['source_index']}],
    'reason':'Synthetic wiring response; no semantic qualification.'}
    for x in r['required_candidate_assessments'] if x['unit_id']==unit['unit_id'] and (x['unit_id'],x['kind'],x['source_index']) not in owned]
   response['units'].append({'unit_id':unit['unit_id'],'reviewed':True,'findings':findings,'unresolved':[],'calculation_limits':[]})
  def wire(value):return canonical_json_bytes(value={'id':'b13-v6-current-offline','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(value)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
  raw=wire(response);observed=[]
  class FakeResponse(io.BytesIO):headers={'x-request-id':'b13-v6-current-offline'}
  def fake_open(*,fullurl,timeout):
   assert fullurl.full_url=='https://api.deepseek.com/chat/completions';assert fullurl.data==p.provider_request_body_bytes;assert timeout==120;observed.append(fullurl.data);return FakeResponse(raw)
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-test-not-a-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=fake_open):
   transport=adapter._build_repository_transport(policy=policy)
   try:transport.complete(prepared_request=p)
   except adapter.AIAdapterError as error:assert 'RESERVATION_OWNER_EGRESS_REQUIRED' in str(error)
   else:raise AssertionError('unowned egress accepted')
   assert transport.complete(prepared_request=p,egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY).raw_response_bytes==raw
  assert len(observed)==1
  try:replace(p,provider_request_body_bytes=b'{}').validate(policy)
  except ValueError as error:assert 'PAYLOAD_CHANGED' in str(error)
  else:raise AssertionError('altered body accepted')
  ledger=recorded_ledger(root=base/company['company_id']/'accepted')
  try:execute_feasibility(prepared=p,ledger=ledger,recorded_wire=raw)
  except ValueError as error:assert 'B13_REQUIRES_NATIVE_ASSESSMENT_ENTRY' in str(error)
  else:raise AssertionError('legacy entry accepted')
  path,outcome=execute_capacity_assessment(prepared=p,ledger=ledger,recorded_wire=raw)
  assert outcome['terminal']['status']=='SUCCEEDED',outcome
  assert outcome['native_candidate_evidence_created'] and not outcome['native_result_created']
  index=json.loads((path/'execution-rules.json').read_text())['files']
  with tarfile.open(path/'execution-rules.tar.gz') as archive:
   assert {m.name for m in archive.getmembers()}==set(index)
   for m in archive.getmembers():
    content=archive.extractfile(m).read();assert index[m.name]=={'sha256':sha256_bytes(content=content),'size':len(content)}
  partial=collect_native_assessments(prepared_requests=requests,ledger=ledger)
  assert not partial['all_source_requests_accepted'] and partial['proposed_branch']=='INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE'
  badledger=recorded_ledger(root=base/company['company_id']/'omitted-unit')
  _,bad=execute_capacity_assessment(prepared=p,ledger=badledger,recorded_wire=wire({**response,'units':response['units'][:-1]}))
  assert bad['terminal']['status']=='FAILED_TERMINAL' and not bad['native_candidate_evidence_created']
  row={'company_id':company['company_id'],'request_count':len(requests),'all_current_request_ids_match_plan':True,'representative_group':1,'unit_count':len(r['units']),
   'required_candidates':len(r['required_candidate_assessments']),'program_quantity_count':len(contract['verified_quantity_roles']),
   'request_id':r['request_id'],'provider_body_sha256':sha256_bytes(content=p.provider_request_body_bytes),'estimated_context_tokens':invocation['observability']['estimated_context_tokens'],
   'native_acceptance':'PASS','omitted_unit':'FAILED_TERMINAL','partial_cannot_be_absence':True,'mocked_official_opener_invocations':1,'recorded_path':str(path)}
  rows.append(row);print(row,flush=True)
 summary={'status':'B13_V6_CURRENT_FACTORY_NATIVE_ACCEPTOR_RECORDED_CONTROLLER_PASS','closure':requirement['requirement_closure_hash'],
  'companies':rows,'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,
  'complete_company_result':False,'semantic_qualification':False,'production_authorized':False,'seconds':time.monotonic()-started}
 (base/'summary.json').write_bytes(canonical_json_bytes(value=summary));print(summary,flush=True)
