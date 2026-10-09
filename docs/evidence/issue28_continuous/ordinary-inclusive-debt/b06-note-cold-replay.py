import json,sys,socket
from pathlib import Path
from unittest.mock import patch
data,run,output=map(lambda p:Path(p).resolve(),sys.argv[1:])
sys.path.insert(0,str(data/'scripts'))
from vnext import run_store,normal_run_v3
assert normal_run_v3.ROOT.resolve()==data and not (data/'.git').exists()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
 manifest,records,decisions=run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
result={'status':'PASS','run_id':manifest['run_id'],'run_status':manifest['status'],'record_count':len(records),'decision_count':len(decisions),'runtime_root':str(normal_run_v3.ROOT.resolve()),'git_directory_present':False,'results':[r for r in records if r['record_type']=='METRIC_RESULT'],'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
