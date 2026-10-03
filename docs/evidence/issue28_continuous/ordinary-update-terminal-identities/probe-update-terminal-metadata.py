from pathlib import Path
from unittest.mock import patch
import json,shutil,socket,sys
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path('/private/tmp/sec_metrics_issue28_continuous')
sys.path.insert(0,str(ROOT/'scripts'))
from vnext import normal_run_v3 as normal,ordinary_update_cycle as cycle
from vnext.canonical import content_hash
root=BASE/'update-terminal-metadata-before';assert not root.exists()
shutil.copytree(BASE/'update-metric-isolation-first/metrics/B01',root,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
observed=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')),patch.object(normal,'create_normal_run',side_effect=AssertionError('No new Run expected')):
 for field,changed in [('attempt_id','0'*32),('record_type','UNRELATED_TERMINAL_TYPE')]:
  state=json.loads((root/'current.json').read_text());path=root/'attempts'/state['latest_attempt']/'terminal.json'
  value=json.loads(path.read_text());value[field]=changed
  value['record_id']=content_hash(value={k:v for k,v in value.items() if k!='record_id'})
  path.write_text(json.dumps(value,indent=2)+'\n')
  try:
   result=cycle.run_once(state_root=root,source_root=ROOT,company_id='pfizer',metric_ids=['B01'])
   observation={'field':field,'altered_terminal':str(path),'outcome':'ACCEPTED','status':result['status'],'new_candidate_created':result['new_candidate_created']}
  except Exception as error:observation={'field':field,'altered_terminal':str(path),'outcome':'REJECTED','error_type':type(error).__name__,'reason':str(error)}
  observed.append(observation);print(json.dumps(observation),flush=True)
(root/'observed.json').write_text(json.dumps({'observations':observed,'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False},indent=2)+'\n')
