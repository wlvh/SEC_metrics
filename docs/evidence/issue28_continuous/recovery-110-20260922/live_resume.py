"""Explicitly authorized recovery110 once, then Enphase and Ford; no automatic restart."""
from pathlib import Path
import json,os,time
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,execute_capacity_assessment,build_plan
from vnext.native_request_construction import request_construction_session
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.canonical import content_hash
out=Path('/tmp/sec_metrics_recovery110_live_20260922');out.mkdir(exist_ok=False)
evidence=Path(__file__).resolve().parent
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_wiring_receipt(requirement=requirement)
ledger=live_ledger(requirement=requirement)
with ledger.locked():initial=ledger.snapshot()
assert initial['counts']==[61,61,49] and len(initial['rows'])==110 and initial['stopped_channels']==['PROVIDER']
os.environ['DEEPSEEK_API_KEY']=Path('/Users/lyuhongwang/.local/state/sec_metrics/private-credentials/deepseek-20260914.key').read_text().strip()
assert os.environ['DEEPSEEK_API_KEY']
started=time.monotonic();report={'recovery_authorization_url':'https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5775635612','status':'RUNNING','code_requirement':requirement['requirement_closure_hash'],'before':initial['counts'],'companies':[],'allowed_provider_requests':17,'production_authorized':False}
def save():
 with ledger.locked():state=ledger.snapshot()
 report['after']=state['counts'];report['new_calls']=[a-b for a,b in zip(state['counts'],initial['counts'])];report['last_ordinal']=len(state['rows']);report['seconds']=round(time.monotonic()-started,3)
 (evidence/'live-b13-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 assert report['new_calls'][0]<=17 and report['new_calls'][2]==0
save()
try:
 with request_construction_session(requirement):
  for company,count in [('enphase_energy',6),('ford_motor_company',11)]:
   originals=prepare_requests(company_id=company,metric_id='B13',reference_context=True,program_quantity_roles=True)
   selected,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger,source_references=True)
   assert len(selected)==count and all(v['original_ordinal'] is None for v in variants)
   # Validate the complete company plan before its first request.
   for prepared in selected:build_plan(prepared)
   row={'company_id':company,'planned_requests':count,'calls':[],'status':'RUNNING'};report['companies'].append(row);save()
   for prepared in selected:
    if not row['calls'] and company=='enphase_energy':
     from vnext.continuous_semantic_calls import request_digest
     policy,_=build_plan(prepared)
     original_intent=json.loads((ledger.root/'calls/0110/intent.json').read_text())
     assert request_digest(json.loads(prepared.request_bytes),policy)==original_intent['request_digest']
    path,result=execute_capacity_assessment(prepared=prepared,ledger=ledger)
    terminal=result['terminal'];row['calls'].append({'ordinal':int(path.name),'status':terminal['status'],'call_path':str(path),'stop_reason':terminal['stop_reason']})
    print(company,path.name,terminal['status'],flush=True);save()
    if len(row['calls'])==1 and company=='enphase_energy':
     recovery_intent=json.loads((path/'intent.json').read_text())
     authorization=json.loads((ledger.root/'recovery-110.json').read_text())
     assert recovery_intent['recovery_authorization_id']==authorization['authorization_id']
     report['recovery_consumed_at_ordinal']=int(path.name);save()
    if terminal['status']!='SUCCEEDED' or terminal['stop_reason']:
     row['status']='FAILED_TERMINAL_SCOPE_PAUSED';report['status']='B13_PAUSED_AFTER_FAILURE_NO_RETRY';save();raise SystemExit(2)
   registered=register_assessment_input(prepared_requests=selected,ledger=ledger)
   base=out/company;data=base/'data';run=base/'run'
   source=json.loads(selected[0].source_bytes)
   install_inputs(data_root=data,company_id=company,assessment_mode='LIVE',assessment_input_id=registered['input_record_id'],request_context_format=source['request_context_format'],program_quantity_roles=True)
   created=create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='B13');rendered=render_ordinary_run(data_root=data,run_dir=run)
   for name,raw in rendered['files'].items():
    target=base/'rows'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
   row.update(status='COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS',run_id=created['manifest']['run_id'],result_id=created['result']['result_id'],value_kind=created['result']['value_kind'],material_root=str(base))
   (base/'summary.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n');save()
 report['status']='COMPLETE_TWO_B13_NATIVE_COORDINATES';save()
except Exception as exc:
 report['status']='STOPPED_EXCEPTION_NO_RETRY';report['error_type']=type(exc).__name__;report['error']=str(exc);save();raise
finally:
 os.environ.pop('DEEPSEEK_API_KEY',None)
