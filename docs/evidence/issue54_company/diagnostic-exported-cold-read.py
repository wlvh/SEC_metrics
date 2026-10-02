import json,os,socket,sys,time
from pathlib import Path
from unittest.mock import patch
runtime=Path(sys.argv[1]);package=Path(sys.argv[2]);trust=Path(sys.argv[3]);denied=[Path(p).resolve() for p in sys.argv[4:]]
sys.dont_write_bytecode=True
sys.path[:0]=[str(runtime/'scripts'),str(runtime)];os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(trust)
from vnext.canonical import strict_json_file,sha256_file
from vnext.run_store import load_frozen_run,_mechanically_replay_open_run
from vnext.normal_history_plan import checkpoint_replayed_once
index=strict_json_file(path=package/'export.json');entry=index['native_candidates'][0];work=package/entry['path'];run=next((work/'runs').glob('*/manifest.json')).parent;manifest=strict_json_file(path=run/'manifest.json')
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve()
  if any(p==d or d in p.parents for d in denied):raise PermissionError('COLD_READ_DENIED:'+str(p))
sys.addaudithook(audit);start=time.monotonic()
for path,b in index['files'].items():
 p=package/path
 assert sha256_file(path=p)==b['sha256'] and p.stat().st_size==b['size']
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')),checkpoint_replayed_once():
 if manifest['status']=='FROZEN':result=load_frozen_run(run_dir=run,repo_root=work/'data')
 else:result=_mechanically_replay_open_run(run_dir=run,repo_root=work/'data',require_complete_results=True)
print(json.dumps({'status':'EXPORTED_RUN_REPLAYED','seconds':time.monotonic()-start,'uid':os.getuid(),'company_id':manifest['company_id'],'run_id':manifest['run_id'],'run_status':manifest['status'],'requirement_id':manifest['requirement_id'],'verified_export_files':len(index['files']),'denied_roots':[str(p) for p in denied],'new_business_calls':[0,0,0],'production_authorized':False},indent=2))
