from pathlib import Path
from unittest.mock import patch
import json,socket,sys
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path('/private/tmp/sec_metrics_issue28_continuous');sys.path.insert(0,str(ROOT/'scripts'))
from vnext import normal_run_v3 as normal,ordinary_update_cycle as cycle
root=BASE/'update-terminal-metadata-first';state=root/'state'
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')),patch.object(normal,'create_normal_run',side_effect=AssertionError('Reentry must reuse the original Run')):
 result=cycle.run_once(state_root=state,source_root=root/'source',company_id='marriott_international',metric_ids=['B01'])
 assert result['status']=='NO_SOURCE_CONTENT_CHANGE' and result['new_candidate_created'] is False
 assert result['last_verified_candidate']['current_input_matches'] is True
 path=state/'attempts'/result['latest_attempt']/'terminal.json';raw=path.read_bytes();value=json.loads(raw);value['record_type']='UNRELATED_TERMINAL_TYPE';value['record_id']=cycle.content_hash(value={k:v for k,v in value.items() if k!='record_id'})
 try:
  path.write_text(json.dumps(value,indent=2)+'\n')
  try:cycle.run_once(state_root=state,source_root=root/'source',company_id='marriott_international',metric_ids=['B01'])
  except cycle.OrdinaryUpdateError as error:assert str(error)=='UPDATE_TERMINAL_IDENTITY_CHANGED'
  else:raise AssertionError('Wrong terminal type was accepted')
 finally:path.write_bytes(raw)
 summary={'status':'PASS','runtime':sys.version,'result_status':result['status'],'successful_attempt':result['successful_attempt'],'new_candidate_created':False,'changed_terminal_type':'REJECTED_UPDATE_TERMINAL_IDENTITY_CHANGED','calls':result['calls'],'production_authorized':False}
 (BASE/'update-terminal-metadata-reentry39.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
