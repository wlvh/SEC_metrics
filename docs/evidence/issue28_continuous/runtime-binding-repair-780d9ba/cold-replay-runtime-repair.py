from pathlib import Path
import socket,sys,json
from unittest.mock import patch
base=Path(sys.argv[1]).resolve();sys.path.insert(0,str(base/'data/scripts'))
from vnext.run_store import _mechanically_replay_open_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 manifest,records,specs=_mechanically_replay_open_run(run_dir=base/'run',repo_root=base/'data',require_complete_results=True)
 print(json.dumps({'status':'COLD_NATIVE_REPLAY_PASS','requirement_id':manifest['requirement_id'],'closure':manifest['requirement_closure_hash'],'record_count':len(records),'actual_calls':[0,0,0]}))
