"""Actual native WB-3 recorded execution and ordinary history; synthetic FY2026."""
from pathlib import Path
import json,socket,time,hashlib,traceback
from unittest.mock import patch
from vnext.canonical import canonical_json_bytes,strict_json_loads
from vnext.continuous_call_ledger import recorded_ledger
from vnext.capacity_update_input import ensure_native_update
from vnext.ordinary_update_cycle import run_company
from vnext import continuous_semantic_calls as calls,normal_run_v3 as normal
from tests.vnext.test_d04_run_material import recorded_response
root=Path('/tmp/sec_metrics_issue28_continuous/native-refresh-execution/material-current-d04-fy2026').resolve();ledger=recorded_ledger(root=root/'ledger');source=root/'ledger/source-inputs';history=root/'history'
report={'source_kind':'ENTIRE_SYNTHETIC_FY2026_DOCUMENT_WITH_ORIGINAL_FY2025_BASELINE_RETAINED','provider_transport':'RECORDED_TEST_ONLY','new_real_calls':[0,0,0],'runtime':'COMPLETE_INDEPENDENT_RUNTIME_WITH_UPDATED_UNFROZEN_V14_V15_BINDINGS','native_wb3_receipts_are_real_recorded_implementation':True,'substituted_functions':[]};start=time.monotonic()
def save(name,value):
 (root/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(name,value.get('status',''),flush=True)
def wire(prepared):
 request=strict_json_loads(text=prepared.request_bytes.decode());response=recorded_response(request)
 return canonical_json_bytes(value={'id':'native-update-synthetic-fy2026','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(response)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
def current():return run_company(state_root=history,source_root=source,company_id='enphase_energy',metric_ids=['D04'],native_assessment_mode='RECORDED_TEST_ONLY',native_assessment_ledger=ledger)
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 try:
  with ledger.locked():before=ledger.snapshot();report['ledger_counts_before']=before['counts']
  first=current();save('history-before-native',first);assert first['metrics'][0]['status']=='INPUT_FAILED',first
  result=ensure_native_update(source_root=source,company_id='enphase_energy',metric_id='D04',ledger=ledger,max_provider_requests=2,recorded_wire_factory=wire);save('native-execution',result);assert result['status']=='NATIVE_INPUT_REGISTERED',result
  first_success=current();save('history-success',first_success);assert first_success['metrics'][0]['status']=='CANDIDATE_READY',first_success
  successful=first_success['metrics'][0]['successful_attempt']
  with ledger.locked():after_success=ledger.snapshot();report['ledger_counts_after_success']=after_success['counts']
  files={p:hashlib.sha256(p.read_bytes()).hexdigest()for p in(ledger.root/'calls').rglob('*')if p.is_file()}
  with patch.object(calls,'execute_d04_assessment',side_effect=AssertionError('REPEAT_MUST_NOT_EXECUTE')),patch.object(normal,'create_normal_run',side_effect=AssertionError('REPEAT_MUST_REUSE_RUN')):
   reused=ensure_native_update(source_root=source,company_id='enphase_energy',metric_id='D04',ledger=ledger,max_provider_requests=2,recorded_wire_factory=wire);save('native-repeat',reused);assert reused['status']=='REGISTERED_INPUT_REUSED'
   repeated=current();save('history-repeat',repeated);assert repeated['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
   log=source/'evidence/requests_log.csv';old=log.read_bytes();log.write_bytes(old+b'isolated test corruption')
   try:failed=current();save('history-input-failure',failed);assert failed['metrics'][0]['status']=='INPUT_FAILED'
   finally:log.write_bytes(old)
   restored=current();save('history-restored',restored);assert restored['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
   for value in(repeated,failed,restored):assert value['metrics'][0]['successful_attempt']==successful
  assert all(hashlib.sha256(p.read_bytes()).hexdigest()==sha for p,sha in files.items())
  with ledger.locked():report['ledger_counts_final']=ledger.snapshot()['counts'];assert report['ledger_counts_final']==after_success['counts']
  report.update(status='PASS_RECORDED_WB3_NATIVE_REGISTRATION_RUN_HISTORY',successful_attempt=successful,original_execution_files_unchanged=True)
 except Exception as error:
  report.update(status='FAILED',error_type=type(error).__name__,reason=str(error),traceback=traceback.format_exc());save('material-failure',report);raise
 finally:
  report['seconds']=time.monotonic()-start;save('material-summary',report)
