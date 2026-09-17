from pathlib import Path
import sys,socket,json
from unittest.mock import patch
base=Path(sys.argv[1]);company=sys.argv[2];metric=sys.argv[3];data=base/'data'/company
sys.path.insert(0,str(data/'scripts'))
from vnext.run_store import _mechanically_replay_open_run
from vnext.ordinary_projection import render_ordinary_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 manifest,records,_=_mechanically_replay_open_run(run_dir=base/'runs'/company/metric,repo_root=data,require_complete_results=True)
 row=render_ordinary_run(data_root=data,run_dir=base/'runs'/company/metric)
 assert row['receipt']['source_credit']=='VERIFIED_SEC_ACQUISITION' and row['receipt']['real_sec_credit'] is True
 print(json.dumps({'status':'COLD_ACTUAL_ACQUISITION_RUN_PASS','company':company,'metric':metric,'record_count':len(records),'source_credit':row['receipt']['source_credit'],'real_sec_credit':row['receipt']['real_sec_credit'],'new_calls':[0,0,0]}))
