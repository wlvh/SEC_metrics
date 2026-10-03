"""Authorized substantive B13 contract validation; never a same-digest retry."""
from pathlib import Path
import json,os,time
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,execute_capacity_assessment,build_plan,request_digest
from vnext.native_request_construction import request_construction_session
from vnext.capacity_reference_contract import COMPACT_VERSION
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
out=Path('/tmp/issue28_b13_typed_live_20260923');out.mkdir(exist_ok=False);e=Path(__file__).resolve().parent
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');validate_wiring_receipt(requirement=requirement)
ledger=live_ledger(requirement=requirement)
with ledger.locked():initial=ledger.snapshot()
assert initial['counts']==[120,120,49] and len(initial['rows'])==169 and not initial['stopped_channels']
# Existing private credential; no account operation or balance probe.
os.environ['DEEPSEEK_API_KEY']=Path('/Users/lyuhongwang/.local/state/sec_metrics/private-credentials/deepseek-20260914.key').read_text().strip()
started=time.monotonic();report={'status':'RUNNING','before':initial['counts'],'limit_new_provider_requests':16,'requirement_closure_hash':requirement['requirement_closure_hash'],'companies':[],'same_digest_retries_authorized':False,'production_authorized':False}
def save():
 with ledger.locked():state=ledger.snapshot()
 report.update(after=state['counts'],new_calls=[a-b for a,b in zip(state['counts'],initial['counts'])],through_ordinal=len(state['rows']),seconds=round(time.monotonic()-started,3))
 assert report['new_calls'][0]<=16 and report['new_calls'][2]==0
 (e/'live-b13-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n')
save()
try:
 with request_construction_session(requirement):
  for company,count in [('enphase_energy',6),('ford_motor_company',11)]:
   with ledger.locked():state=ledger.snapshot()
   if state['stopped_channels']:report['status']='STOPPED_CHANNEL';break
   row={'company_id':company,'status':'PREPARING','calls':[],'reused':[]};report['companies'].append(row);save()
   try:
    originals=prepare_requests(company_id=company,metric_id='B13',reference_context=True,program_quantity_roles=True)
    selected,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger,source_references=True,compact_references=True)
    assert len(selected)==count
    pending=[]
    with ledger.locked():state=ledger.snapshot()
    for obj,variant in zip(selected,variants):
     if variant['original_ordinal'] is not None:
      row['reused'].append(variant['original_ordinal']);continue
     policy,plan=build_plan(obj);request=json.loads(obj.request_bytes)
     assert request['source_reference_contract']['version']==COMPACT_VERSION
     digest=request_digest(request,policy)
     assert ('PROVIDER',digest) not in state['requests'],'UNCHANGED_DIGEST_RETRY_NOT_AUTHORIZED'
     pending.append(obj)
    if company=='enphase_energy':assert row['reused']==[111] and len(pending)==5
    assert len(pending)<=16-report['new_calls'][0]
    row.update(status='EXECUTING_NEW_COMPACT_CONTRACT',planned_new_calls=len(pending));save()
    failed=False
    for obj in pending:
     path,outcome=execute_capacity_assessment(prepared=obj,ledger=ledger);terminal=outcome['terminal']
     row['calls'].append({'ordinal':int(path.name),'status':terminal['status'],'stop_reason':terminal['stop_reason'],'call_path':str(path)});save();print(company,path.name,terminal['status'],flush=True)
     if terminal['status']!='SUCCEEDED':failed=True;row['status']='FAILED_TERMINAL_NO_RETRY';save();break
    if failed:continue
    registered=register_assessment_input(prepared_requests=selected,ledger=ledger);data=out/company/'data';run=out/company/'run';source=json.loads(selected[0].source_bytes)
    install_inputs(data_root=data,company_id=company,metric_id='B13',assessment_mode='LIVE',assessment_input_id=registered['input_record_id'],request_context_format=source['request_context_format'],program_quantity_roles=True)
    created=create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='B13');rendered=render_ordinary_run(data_root=data,run_dir=run)
    for name,raw in rendered['files'].items():
     p=out/company/'rows'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    row.update(status='COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS',run_id=created['manifest']['run_id'],result=created['result'],material_root=str(out/company));(out/company/'summary.json').write_text(json.dumps(row,ensure_ascii=False,indent=2,default=str)+'\n');save()
   except Exception as error:
    row.update(status='BLOCKED_OR_FAILED_NO_RETRY',error_type=type(error).__name__,error=str(error));save();print(company,type(error).__name__,str(error),flush=True)
  if report['status']=='RUNNING':report['status']='BOUNDED_BATCH_COMPLETED_WITH_SEPARATE_COORDINATE_TERMINALS'
finally:save()
