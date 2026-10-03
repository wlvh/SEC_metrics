from pathlib import Path
import sys,socket,json
from unittest.mock import patch
base=Path(sys.argv[1]);company=sys.argv[2];data=base/'data'/company
sys.path.insert(0,str(data/'scripts'))
from vnext.run_store import _mechanically_replay_open_run
from vnext.ordinary_projection import render_ordinary_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 manifest,records,_=_mechanically_replay_open_run(run_dir=base/'runs'/company/'B06',repo_root=data,require_complete_results=True)
 result=next(r for r in records if r['record_type']=='METRIC_RESULT');assert result['value'] is None and result['publication']=='WITHHELD'
 row=render_ordinary_run(data_root=data,run_dir=base/'runs'/company/'B06')
 receipt=row['receipt'];assert receipt['real_sec_credit'] is (company=='jpmorgan_chase')
 print(json.dumps({'status':'COLD_SCOPED_GAP_PASS','company':company,'record_count':len(records),'source_credit':receipt['source_credit'],'real_sec_credit':receipt['real_sec_credit'],'value':None,'result_state':'WITHHELD','new_calls':[0,0,0]}))
