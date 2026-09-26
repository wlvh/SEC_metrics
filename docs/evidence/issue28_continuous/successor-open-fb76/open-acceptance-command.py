from pathlib import Path
import sys,json,time,traceback,socket
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(ROOT/'scripts'))
from vnext.normal_run_v2 import install_normal_inputs,create_normal_run
from vnext.canonical import content_hash
from vnext.requirements import load_requirement_snapshot
out=Path('/tmp/sec_metrics_issue28_continuous/v13-open-acceptance-fb76');out.mkdir(exist_ok=False)
expected='sha256:fb76e3804bc76494f4efa7fa9d8c188f4b55413d0d1de281b3ebf5ce9348324e'
assert load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v12')['requirement_closure_hash']==expected
cases=[('marriott_international','B06'),('lumen_technologies','B06'),('marriott_international','C02'),('paramount_skydance_paramount_global','C02'),('jpmorgan_chase','D02')]+[('jpmorgan_chase',m) for m in ['A03','A04','A09','A11','A12','A13']]+[('marriott_international','A03'),('paramount_skydance_paramount_global','C03'),('salesforce','C04')]
results=[]
def audit(event,args):
 if event.startswith('socket.'):raise RuntimeError('OPEN material acceptance forbids network')
sys.addaudithook(audit)
for company,metric in cases:
 d=out/(company+'-'+metric);start=time.monotonic();r={'company_id':company,'metric_id':metric,'stage':'INSTALL','status':'RUNNING'}
 try:
  install_normal_inputs(data_root=d/'data',company_id=company,metric_id=metric)
  r['stage']='OPEN_GRAPH'
  x=create_normal_run(data_root=d/'data',run_dir=d/'run',company_id=company,metric_id=metric,freeze=False)
  assert x['manifest']['status']=='OPEN'
  (d/'result.json').write_text(json.dumps(x,ensure_ascii=False,indent=2))
  r.update(status='OPEN_COMPLETE_GRAPH_PASS',stage='COMPLETE',run_id=x['manifest']['run_id'],result_id=x['result']['result_id'],publication=x['result']['publication'],quality=x['result']['quality'],value=x['result']['value'],target_period=x['manifest']['target_period'])
 except Exception as e:
  d.mkdir(parents=True,exist_ok=True);r.update(status='FAIL',error=type(e).__name__+': '+str(e));(d/'first-failure.txt').write_text(traceback.format_exc())
 r['seconds']=round(time.monotonic()-start,3);results.append(r);(d/'outcome.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r),flush=True)
(out/'summary.json').write_text(json.dumps({'closure':expected,'cases':results,'new_calls':[0,0,0],'frozen':False,'full_acceptance':False},ensure_ascii=False,indent=2))
