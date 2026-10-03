from pathlib import Path
import sys,socket,json
from unittest.mock import patch
base=Path(sys.argv[1]);company='paramount_skydance_paramount_global';metric=sys.argv[2];data=base/'data'/company
sys.path.insert(0,str(data/'scripts'))
from vnext.run_store import _mechanically_replay_open_run
from vnext.ordinary_projection import render_ordinary_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 manifest,records,_=_mechanically_replay_open_run(run_dir=base/'runs'/company/metric,repo_root=data,require_complete_results=True)
 results=[r for r in records if r['record_type']=='METRIC_RESULT']
 assert all(r['quality']=='NOT_MEANINGFUL' and r['value'] is None and r['reason_code']=='ANNUAL_DURATION_OUT_OF_RANGE' for r in results)
 row=render_ordinary_run(data_root=data,run_dir=base/'runs'/company/metric)
 assert row['receipt']['real_sec_credit'] is False
 print(json.dumps({'status':'COLD_CURRENT_INCOME_PASS','metric':metric,'records':len(records),'result_ids':[r['metric_id'] for r in results],'real_sec_credit':False,'new_calls':[0,0,0]}))
