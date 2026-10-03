"""Historical event route before/after with the separately scoped package."""
import json,os,subprocess,sys,time
from pathlib import Path
w=Path('/workspace/work');state=w/'company-event-historical-state'
base=['--state-root',str(state),'--trust-root',str(w/'company-history-trust'),'--company','jpmorgan_chase']
env={**os.environ,'COMPANY_DENY_READ_ROOTS':'/workspace/SEC_metrics:/workspace/work/sec-company-compute:/workspace/work/history-preparation:/workspace/work/history-mixed-restored','PYTHONDONTWRITEBYTECODE':'1'}
stages=[]
for label,tree,args in [
 ('before','company-history-runtime-export-scope',['compute',*base,'--metric','C01','--report-end','2023-12-31']),
 ('after','company-event-historical-runtime-v2',['compute',*base,'--metric','C01','--report-end','2023-12-31']),
 ('export','company-event-historical-runtime-v2',['export-results',*base,'--runtime-root',str(w/'company-event-historical-runtime-v2'),'--output-root',str(w/'company-event-historical-v2-export')])]:
 start=time.monotonic();child=subprocess.run([sys.executable,'-B',str(w/'isolated_company_cli.py'),str(w/tree),*args],env=env,capture_output=True,text=True)
 (w/('company-event-historical-v2-'+label+'.json')).write_text(child.stdout)
 (w/('company-event-historical-v2-'+label+'.stderr.log')).write_text(child.stderr)
 stage={'stage':label,'runtime_root':str(w/tree),'seconds':time.monotonic()-start,'exit_code':child.returncode}
 try:
  d=json.loads(child.stdout);stage.update(status=d.get('status'),metrics=[{'metric_id':m['metric_id'],'status':m['status'],'reason':m.get('reason'),'new_candidate_created':m.get('new_candidate_created')}for m in d.get('metrics',[])])
 except ValueError:stage['stderr_tail']=child.stderr[-1600:]
 stages.append(stage);print(json.dumps(stage),flush=True)
 (w/'company-event-historical-v2-probe.json').write_text(json.dumps({'uid':os.getuid(),'source_root':str(state/'source'),'new_business_calls':[0,0,0],'stages':stages},indent=2))
 if label=='after' and (child.returncode!=0 or d['metrics'][0]['status']!='CANDIDATE_READY'):break
