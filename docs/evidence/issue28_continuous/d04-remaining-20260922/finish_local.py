"""Finish only local registration/Run work using all original successful calls."""
from pathlib import Path
from unittest.mock import patch
import json,time,socket
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants
from vnext.native_request_construction import request_construction_session
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
r=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');ledger=live_ledger(requirement=r)
with ledger.locked():before=ledger.snapshot()
assert before['counts']==[120,120,49] and len(before['rows'])==169
root=Path('/tmp/sec_metrics_d04_unattempted6_live_20260922');evidence=Path(__file__).resolve().parent;rows=[];started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_NETWORK')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')),patch('vnext.continuous_semantic_calls.execute_d04_assessment',side_effect=AssertionError('NO_NEW_PROVIDER')),request_construction_session(r):
 for company,count in [('salesforce',5),('lumen_technologies',8),('macys',5)]:
  originals=prepare_requests(company_id=company,metric_id='D04',native=True,reference_context=True,complete_response_contract=True)
  selected,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger)
  assert len(selected)==count and all(v['original_ordinal'] is not None for v in variants)
  registered=register_assessment_input(prepared_requests=selected,ledger=ledger)
  base=root/company;assert not base.exists();data=base/'data';run=base/'run';source=json.loads(selected[0].source_bytes)
  install_inputs(data_root=data,company_id=company,metric_id='D04',assessment_mode='LIVE',assessment_input_id=registered['input_record_id'],request_context_format=source['request_context_format'],complete_response_contract=True)
  created=create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='D04');rendered=render_ordinary_run(data_root=data,run_dir=run)
  for name,raw in rendered['files'].items():
   path=base/'rows'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  row={'company_id':company,'status':'COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS','run_id':created['manifest']['run_id'],'result_id':created['result']['result_id'],'value_kind':created['result']['value_kind'],'original_call_ordinals':[v['original_ordinal'] for v in variants],'material_root':str(base),'new_calls':[0,0,0]}
  (base/'summary.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print(company,'LOCAL_FINISH_PASS',flush=True)
 with ledger.locked():after=ledger.snapshot()
 assert after['counts']==before['counts'] and len(after['rows'])==169
 result={'status':'PASS_THREE_LOCAL_RUNS_FROM_ORIGINAL_SUCCESSES','companies':rows,'new_calls':[0,0,0],'counts':after['counts'],'seconds':round(time.monotonic()-started,3),'git':'/Library/Developer/CommandLineTools/usr/bin/git','license_accepted_or_system_setting_changed':False}
 (evidence/'local-finish-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
