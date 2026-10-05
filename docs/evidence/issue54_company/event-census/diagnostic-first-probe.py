"""Actual saved-source company event seam: fixed old/new runtime comparison."""
import json, os, subprocess, sys, time
from pathlib import Path

kind=sys.argv[1]
work=Path('/workspace/work')
company='marriott_international' if kind=='ordinary' else 'jpmorgan_chase'
state=work/('company-event-'+kind+'-state')
old=work/('company-results-runtime-c17' if kind=='ordinary' else 'company-history-runtime-export-scope')
new=work/('company-event-'+kind+'-runtime')
package=work/'baseline-company-packages/marriott_international' if kind=='ordinary' else work/'company-history-jpm-source'
trust=work/('baseline-company-trust' if kind=='ordinary' else 'company-history-trust')
env={**os.environ,'COMPANY_DENY_READ_ROOTS':'/workspace/SEC_metrics:/workspace/work/history-preparation:/workspace/work/history-mixed-restored', 'PYTHONDONTWRITEBYTECODE':'1'}
period=[] if kind=='ordinary' else ['--report-end','2023-12-31']
results=[]
def run(label,tree,args):
 start=time.monotonic()
 child=subprocess.run([sys.executable,'-B',str(work/'isolated_company_cli.py'),str(tree),*args],env=env,capture_output=True,text=True)
 (work/('company-event-'+kind+'-'+label+'.stdout.json')).write_text(child.stdout)
 (work/('company-event-'+kind+'-'+label+'.stderr.log')).write_text(child.stderr)
 value={'stage':label,'runtime_root':str(tree),'seconds':time.monotonic()-start,'exit_code':child.returncode}
 try:
  payload=json.loads(child.stdout);value['metrics']=payload.get('metrics');value['status']=payload.get('status');value['requirement_id']=payload.get('requirement_id')
 except ValueError: value['error_tail']=child.stderr[-2000:]
 results.append(value)
 (work/('company-event-'+kind+'-probe.json')).write_text(json.dumps({'company_id':company,'uid':os.getuid(),'scope':'REAL_SAVED_SOURCES_FIXED_RUNTIME_COMPARISON','new_business_calls':[0,0,0],'stages':results},indent=2))
 print(json.dumps(value),flush=True)
 return child,payload if child.stdout.strip() else None

base=['--state-root',str(state),'--trust-root',str(trust),'--company',company]
run('install',old,['install','--package-root',str(package),*base])
run('before',old,['compute',*base,'--metric','C01',*period])
child,payload=run('after',new,['compute',*base,'--metric','C01',*period])
if child.returncode==0 and payload and payload['metrics'][0]['status'] in {'CANDIDATE_READY','NO_SOURCE_CONTENT_CHANGE'}:
 run('repeat',new,['compute',*base,'--metric','C01',*period])
 run('export',new,['export-results',*base,'--runtime-root',str(new),'--output-root',str(work/('company-event-'+kind+'-export'))])
