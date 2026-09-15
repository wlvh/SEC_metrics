from pathlib import Path
import os,subprocess,time,json
work=Path('/tmp/sec_metrics_issue28_continuous/native-refresh-execution').resolve();runtime=work/'current-runtime'
env=dict(os.environ,PYTHONPATH=str(runtime/'scripts')+':'+str(runtime)+':/tmp/sec_metrics_issue28_continuous/context-tokenizers-0222',PYTHONDONTWRITEBYTECODE='1')
start=time.monotonic();rows=[]
for script in ['prepare_current_material.py','complete_current_material_facts.py','run_current_material.py']:
 with(work/(script+'.log')).open('wb')as log:
  result=subprocess.run(['python3',str(work/script)],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT)
 rows.append({'script':script,'returncode':result.returncode});print(script,result.returncode,flush=True)
 if result.returncode:break
(work/'current-runtime-pipeline.json').write_text(json.dumps({'steps':rows,'seconds':time.monotonic()-start,'all_passed':len(rows)==3 and all(r['returncode']==0 for r in rows)},indent=2)+'\n')
raise SystemExit(result.returncode)
