from pathlib import Path
from unittest.mock import patch
import json,socket,time
from vnext.canonical import canonical_json_bytes,strict_json_loads
from vnext.continuous_semantic_calls import prepare_requests,execute_capacity_assessment
from vnext.continuous_call_ledger import recorded_ledger
from vnext.capacity_semantic_review import _restore_units
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.run_store import _mechanically_replay_open_run
root=Path('/tmp/sec_metrics_issue28_continuous/b13-v6/material-enphase-format').resolve();root.mkdir(exist_ok=False)
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),request_construction_session(requirement) as construction:
 prepared=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)
 print('prepared',len(prepared),time.monotonic()-started,flush=True)
 ledger=recorded_ledger(root=root/'ledger')
 for number,p in enumerate(prepared):
  request=strict_json_loads(text=p.request_bytes.decode());contract=request['program_quantity_contract']
  owned={(r['unit_id'],r['source_kind'],r['source_index']) for r in contract['verified_quantity_roles']+contract['verified_nonphysical_references']}
  rows=[]
  for unit in _restore_units(request['units'],request['shared_source_dictionaries']):
   findings=[{'kind':'OTHER_CONTEXT','subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT',
    'evidence':[{'kind':r['kind'],'source_index':r['source_index']}],
    'reason':'Recorded integration input, not model or source semantic qualification.'}
    for r in request['required_candidate_assessments'] if r['unit_id']==unit['unit_id'] and (r['unit_id'],r['kind'],r['source_index']) not in owned]
   rows.append({'unit_id':unit['unit_id'],'reviewed':True,'findings':findings,'unresolved':[],'calculation_limits':[]})
  response={'request_id':request['request_id'],'units':rows}
  wire=canonical_json_bytes(value={'id':'b13-v6-recorded','model':'deepseek-flash','choices':[{'message':{'role':'assistant','content':json.dumps(response)},'finish_reason':'stop'}],
   'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
  path,outcome=execute_capacity_assessment(prepared=p,ledger=ledger,recorded_wire=wire)
  assert outcome['terminal']['status']=='SUCCEEDED',(path,outcome)
  print('recorded',number+1,time.monotonic()-started,flush=True)
 registered=register_assessment_input(prepared_requests=prepared,ledger=ledger)
 print('registered',registered['input_record_id'],time.monotonic()-started,flush=True)
 source=strict_json_loads(text=prepared[0].source_bytes.decode())
 case=install_inputs(data_root=root/'data',company_id='enphase_energy',assessment_mode='RECORDED_TEST_ONLY',
  assessment_input_id=registered['input_record_id'],request_context_format=source.get('request_context_format'),program_quantity_roles=True)
 print('installed',time.monotonic()-started,flush=True)
 created=create_normal_run(data_root=root/'data',run_dir=root/'run',company_id='enphase_energy',metric_id='B13')
 assert created['result']['value_kind']=='TEXT_V1' and 'approximately five-million microinverters per quarter' in created['result']['value']
 rendered=render_ordinary_run(data_root=root/'data',run_dir=root/'run')
 assert rendered['receipt']['semantic_assessment_mode']=='RECORDED_TEST_ONLY'
 print('native-public',created['result']['result_id'],time.monotonic()-started,flush=True)
 summary={'new_contract':'B13_PROGRAM_QUANTITY_ROLES_V1','source_requests':len(prepared),'result':created['result'],
  'rendered_row':rendered['row'],'seconds':time.monotonic()-started,'new_real_calls':[0,0,0],
  'evidence_type':'COMPLETE_REAL_SOURCE_RECORDED_RESPONSE_NATIVE_RUN','real_company_result_credit':False,'production_authorized':False,'construction_builds':construction.builds,'construction_hits':construction.hits}
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
