from pathlib import Path
import sys,json,hashlib,datetime,time
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext.run_store import load_frozen_run
O=Path(__file__).parent;old=Path('/Users/lyuhongwang/Documents/Codex/2026-09-11/r5-b06-structured/complete-02/snapshot');start=time.time();rs=[]
for c in ['southwest_airlines','lumen_technologies','enphase_energy']:
 d=old/'runs'/c;before={str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()};m,records,dec=load_frozen_run(run_dir=d,repo_root=old/'data');after={str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()};assert before==after
 rs.append({'company':c,'run_id':m['run_id'],'status':m['status'],'records':len(records),'result':[r for r in records if r['record_type']=='METRIC_RESULT'],'old_run_bytes_unchanged':True})
x={'status':'PASS_HISTORICAL_V1_NATIVE_GRAPH_READ_ONLY','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seconds':time.time()-start,'network':'OS deny network; writes only followup','results':rs};(O/'historical-v1-native-replay.json').write_text(json.dumps(x,indent=2));print(json.dumps(x,indent=2))
