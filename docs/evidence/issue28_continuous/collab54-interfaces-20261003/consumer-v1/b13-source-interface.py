import json,os,subprocess,time
from pathlib import Path
b=Path('/private/tmp/issue28-company-consumer-20261003');e=Path('/Users/lyuhongwang/Developer/SEC_metrics/docs/evidence/issue28_continuous/collab54-interfaces-20261003/consumer-v1');py='/private/tmp/issue28-tokenizers-venv/bin/python'
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','COMPANY_TEST_RUNTIME':str(b/'runtime')}
steps=[]
for name,script,args,expected in [
 ('export-enphase-b13',b/'provider-code/tools/vnext_company.py',['export','--source-root','/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs','--output-root',str(b/'package-enphase-b13'),'--trust-root',str(b/'source-trust'),'--company','enphase_energy','--metric','B13','--metric','D04'],0),
 ('install-enphase-b13',b/'guarded-cli.py',['install','--package-root',str(b/'package-enphase-b13'),'--state-root',str(b/'state-enphase_energy'),'--trust-root',str(b/'source-trust'),'--company','enphase_energy'],0),
 ('compute-enphase-b13',b/'guarded-cli.py',['compute','--state-root',str(b/'state-enphase_energy'),'--trust-root',str(b/'source-trust'),'--company','enphase_energy','--metric','B13','--metric','D04'],2)]:
 start=time.monotonic()
 with (e/(name+'.log')).open('w') as f:r=subprocess.run([py,str(script),*args],env=env,cwd=b/'runtime',stdout=f,stderr=subprocess.STDOUT)
 steps.append({'name':name,'exit':r.returncode,'seconds':round(time.monotonic()-start,3)})
 assert r.returncode==expected,name
report=json.loads((e/'compute-enphase-b13.log').read_text())
assert not (b/'state-enphase_energy/updates').exists()
(e/'b13-interface-summary.json').write_text(json.dumps({'steps':steps,'report':report,'no_update_run_created':True,'scope':'ACTUAL_B13_D04_SCOPED_COMPANY_SOURCE_WITHOUT_PROCESSING_INPUT','new_business_calls':[0,0,0]},indent=2)+'\n')
print(json.dumps({'steps':steps,'metrics':report['metrics']},indent=2))
