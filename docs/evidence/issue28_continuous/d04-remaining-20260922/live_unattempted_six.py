"""Eight remaining current D04 coordinates; max71 calls, no automatic retry."""
from pathlib import Path
import json,os,time
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,execute_d04_assessment,build_plan
from vnext.native_request_construction import request_construction_session
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
out=Path('/tmp/sec_metrics_d04_unattempted6_live_20260922');out.mkdir(exist_ok=False)
evidence=ROOT/'docs/evidence/issue28_continuous/d04-remaining-20260922';evidence.mkdir(exist_ok=True)
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');validate_wiring_receipt(requirement=requirement)
ledger=live_ledger(requirement=requirement)
with ledger.locked():initial=ledger.snapshot()
assert not initial['stopped_channels'] and initial['counts'][2]==49
os.environ['DEEPSEEK_API_KEY']=Path('/Users/lyuhongwang/.local/state/sec_metrics/private-credentials/deepseek-20260914.key').read_text().strip()
started=time.monotonic();report={'status':'RUNNING','requirement_closure_hash':requirement['requirement_closure_hash'],'before':initial['counts'],'companies':[],'allowed_provider_requests':71,'production_authorized':False}
def save():
 with ledger.locked():state=ledger.snapshot()
 report.update(after=state['counts'],last_ordinal=len(state['rows']),seconds=round(time.monotonic()-started,3),stopped_channels=state['stopped_channels'])
 report['new_calls']=[a-b for a,b in zip(state['counts'],initial['counts'])]
 (evidence/'unattempted-six-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 assert report['new_calls'][0]<=71 and report['new_calls'][2]==0
 return state
companies=[('marriott_international',4),('southwest_airlines',6),('jpmorgan_chase',27),('salesforce',5),('lumen_technologies',8),('macys',5),]
assert sum(n for _,n in companies)==55
assert initial['counts']==[65,65,49] and len(initial['rows'])==114
save()
try:
 with request_construction_session(requirement):
  for company,count in companies:
   row={'company_id':company,'planned_request_count':count,'calls':[],'status':'PREPARING'};report['companies'].append(row);save()
   try:
    originals=prepare_requests(company_id=company,metric_id='D04',native=True,reference_context=True,complete_response_contract=True)
    selected,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger)
    assert len(selected)==count,'CURRENT_REQUEST_CENSUS_DIFFERS'
    for prepared in selected:build_plan(prepared)
    row['status']='EXECUTING';save()
    for prepared,variant in zip(selected,variants):
     if variant['original_ordinal'] is not None:
      row['calls'].append({'ordinal':variant['original_ordinal'],'status':'ORIGINAL_SUCCESS_REVALIDATED'});continue
     if save()['counts'][0]-initial['counts'][0]>=71:raise RuntimeError('CURRENT_TASK_PROVIDER_LIMIT_REACHED')
     path,result=execute_d04_assessment(prepared=prepared,ledger=ledger)
     terminal=result['terminal'];row['calls'].append({'ordinal':int(path.name),'status':terminal['status'],'call_path':str(path),'stop_reason':terminal['stop_reason']})
     print(company,path.name,terminal['status'],flush=True);state=save()
     if state['stopped_channels']:raise RuntimeError('FIXED_LEDGER_CHANNEL_STOPPED')
     if terminal['status']!='SUCCEEDED' or terminal['stop_reason']:
      row['status']='CONTENT_FAILURE_NO_RETRY';break
    if row['status']=='CONTENT_FAILURE_NO_RETRY':save();continue
    registered=register_assessment_input(prepared_requests=selected,ledger=ledger)
    base=out/company;data=base/'data';run=base/'run';source=json.loads(selected[0].source_bytes)
    install_inputs(data_root=data,company_id=company,metric_id='D04',assessment_mode='LIVE',assessment_input_id=registered['input_record_id'],request_context_format=source['request_context_format'],complete_response_contract=True)
    created=create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='D04');rendered=render_ordinary_run(data_root=data,run_dir=run)
    for name,raw in rendered['files'].items():
     target=base/'rows'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    row.update(status='COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS',run_id=created['manifest']['run_id'],result_id=created['result']['result_id'],value_kind=created['result']['value_kind'],material_root=str(base))
    (base/'summary.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n');save()
   except Exception as exc:
    row.update(status='STOPPED_COORDINATE_EXCEPTION_NO_RETRY',error_type=type(exc).__name__,error=str(exc));state=save()
    if state['stopped_channels']:raise
    if 'CANDIDATE_OWNER_PROVENANCE_UNAVAILABLE' in str(exc):
     report['status']='AUTHORITY_UNAVAILABLE_NO_FURTHER_ATTEMPT';save();raise SystemExit(2)
    print(company,type(exc).__name__,str(exc),flush=True)
 report['status']='COMPLETE_SIX_PREVIOUSLY_UNATTEMPTED_NATIVE_COORDINATES' if all(r['status']=='COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS' for r in report['companies']) else 'BOUNDED_ATTEMPT_COMPLETED_WITH_COORDINATE_GAPS';save()
finally:os.environ.pop('DEEPSEEK_API_KEY',None)
