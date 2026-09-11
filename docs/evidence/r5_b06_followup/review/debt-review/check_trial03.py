from pathlib import Path
import sys,json,hashlib,time
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext.run_store import load_frozen_run
from vnext.canonical import strict_json_file
P=Path('/Users/lyuhongwang/Documents/Codex/2026-09-11/r5-b06-followup/trial-03');out=[]
for c in ['southwest_airlines','lumen_technologies','enphase_energy']:
 d=P/'runs'/c;before={str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()};m,recs,decs=load_frozen_run(run_dir=d,repo_root=P/'data');after={str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()};assert before==after
 selection=strict_json_file(path=P/'runs'/(c+'-selection.json'))['selection'];obs=[r for r in recs if r['record_type']=='OBSERVATION'];trace=[r for r in recs if r['record_type']=='EXECUTION_TRACE'];result=[r for r in recs if r['record_type']=='METRIC_RESULT'];out.append({'company':c,'run_id':m['run_id'],'result':result,'records_types':[r['record_type'] for r in recs],'selection_branch':selection['branch'],'debt':selection['debt'],'chosen_debt_fact_ids':selection['chosen_debt_fact_ids'],'native_graph_replayed':True,'run_bytes_unchanged':True})
x={'status':'PASS_NEW_CARRYING_TRIAL_NATIVE_REPLAY','scope':'SW and Lumen reconciliations plus Enphase nonregression; no full candidate validation','root':str(P),'business_calls':[0,0,0],'results':out};(Path(__file__).parent/'trial03-native-replay.json').write_text(json.dumps(x,indent=2));print(json.dumps(x,indent=2))
