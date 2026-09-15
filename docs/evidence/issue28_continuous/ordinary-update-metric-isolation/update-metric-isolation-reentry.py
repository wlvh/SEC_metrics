from pathlib import Path
from unittest.mock import patch
import json,socket,sys
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path('/private/tmp/sec_metrics_issue28_continuous')
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import normal_run_v3 as normal,ordinary_update_cycle as cycle
mode=sys.argv[1]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')),patch.object(normal,'create_normal_run',side_effect=AssertionError('Reentry must reuse all original Runs')):
 if mode=='cli':
  from tools.vnext_normal_update import main
  output=BASE/'update-metric-isolation-cli.json'
  rc=main(['--process','--state-root',str(BASE/'update-metric-isolation-cli-state'),'--company','pfizer','--metric','B01','--metric','B06','--metric','B08','--output',str(output)])
  assert rc==2
  report=json.loads(output.read_text())['companies'][0]
 else:
  assert mode=='python39'
  report=cycle.run_company(state_root=BASE/'update-metric-isolation-first',source_root=ROOT,company_id='pfizer',metric_ids=['B01','B06','B08'])
  (BASE/'update-metric-isolation-reentry39.json').write_text(json.dumps(report,indent=2)+'\n')
 assert report['status']=='UPDATES_PARTIAL'
 metrics={m['metric_id']:m for m in report['metrics']}
 assert metrics['B06']['status']=='PREVIOUS_INPUT_WITHHELD'
 for metric in ['B01','B08']:
  assert metrics[metric]['status']=='NO_SOURCE_CONTENT_CHANGE'
  assert metrics[metric]['last_verified_candidate']['current_input_matches'] is True
  assert metrics[metric]['new_candidate_created'] is False
 assert report['calls']=={'provider':0,'paid':0,'sec':0}
 print('PASS '+mode+' two verified successes and one unchanged withheld; no new Runs',file=sys.stderr)
