from pathlib import Path
import socket,sys,json
from unittest.mock import patch
base=Path(sys.argv[1]).resolve();company='paramount_skydance_paramount_global';data=base/'data'/company;sys.path.insert(0,str(data/'scripts'))
from vnext.run_store import _mechanically_replay_open_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 manifest,records,specs=_mechanically_replay_open_run(run_dir=base/'runs'/company/'B02',repo_root=data,require_complete_results=True)
 result=next(r for r in records if r['record_type']=='METRIC_RESULT')
 assert result['quality']=='NOT_MEANINGFUL' and result['value'] is None
 print(json.dumps({'status':'COLD_CONTINUITY_REPLAY_PASS','closure':manifest['requirement_closure_hash'],'result_reason':result['reason_code'],'record_count':len(records),'calls':[0,0,0]}))
