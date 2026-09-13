from pathlib import Path
from unittest.mock import patch
import json,socket,sys,time
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(ROOT/'scripts'))
from vnext import ordinary_update_cycle as cycle,normal_run_v3 as normal
out=Path('/private/tmp/sec_metrics_issue28_continuous/update-cycle-mixed-before');assert not out.exists()
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')):
 result=cycle.run_once(state_root=out,source_root=ROOT,company_id='pfizer',metric_ids=['B01','B06'])
summary={'status':result['status'],'successful_attempt':result['successful_attempt'],'metrics':{m:v['publication'] for m,v in result['terminal']['metrics'].items()},'seconds':time.monotonic()-start,'calls':result['calls'],'production_authorized':False}
(out/'observed.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
