from pathlib import Path
import sys,socket,json
from unittest.mock import patch
base=Path(sys.argv[1]);data=base/'native-data';run=base/'native-run'
sys.path.insert(0,str(data/'scripts'))
from vnext.run_store import _mechanically_replay_open_run
from vnext.ordinary_projection import render_ordinary_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 manifest,records,_=_mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
 row=render_ordinary_run(data_root=data,run_dir=run)
 assert row['receipt']['source_credit']=='RECORDED_TEST_ONLY' and row['receipt']['real_sec_credit'] is False
 print(json.dumps({'status':'COLD_RECORDED_ACQUISITION_PASS','records':len(records),'real_sec_credit':False,'new_calls':[0,0,0]}))
