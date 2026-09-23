"""Preserve completed new candidates and verify their installed runtime offline."""
from pathlib import Path
import json,subprocess,sys,shutil,os,time,hashlib
source=Path('/tmp/sec_metrics_d04_unattempted6_live_20260922')
destination=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/native-candidate-results-20260922')
evidence=Path(__file__).resolve().parent
companies=sys.argv[1:];assert companies
started=time.monotonic();reports=[]
empty=destination/'empty-cold-working-directory';empty.mkdir(parents=True,exist_ok=True)
code='''import sys,json
from pathlib import Path
base=Path(sys.argv[1]);sys.path.insert(0,str(base/'data'));sys.path.insert(0,str(base/'data/scripts'));sys.dont_write_bytecode=True
blocked=[]
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
  blocked.append(event);raise RuntimeError('NETWORK_OR_PROCESS_FORBIDDEN:'+event)
sys.addaudithook(audit)
from vnext.ordinary_projection import render_ordinary_run
from vnext import run_store
assert Path(run_store.__file__).resolve().is_relative_to(base/'data')
expected=json.loads((base/'summary.json').read_text())
rendered=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
assert rendered['receipt']['result_id']==expected['result_id'] and rendered['receipt']['semantic_assessment_mode']=='LIVE'
for name,raw in rendered['files'].items():assert (base/'rows'/name).read_bytes()==raw
assert not blocked
print(json.dumps({'status':'PASS_NEW_CANDIDATE_INSTALLED_RUNTIME_COLD_READ','company_id':expected['company_id'],'run_id':expected['run_id'],'result_id':expected['result_id'],'public_rows_identical':True,'network_or_process_events':blocked,'new_calls':[0,0,0]}))
'''
for company in companies:
 original=source/company;summary=json.loads((original/'summary.json').read_text());assert summary['status']=='COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS'
 target=destination/company;target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():
  def inventory(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
  assert inventory(original)==inventory(target),'Existing preserved candidate differs'
 else:shutil.copytree(original,target)
 log=evidence/(company+'-cold-verified.log')
 with log.open('wb') as stream:
  result=subprocess.run(['/tmp/sec_metrics_cold39_20260922/bin/python','-c',code,str(target)],stdout=stream,stderr=subprocess.STDOUT,cwd=empty,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 row={'company_id':company,'persistent_candidate_root':str(target),'return_code':result.returncode,'new_calls':[0,0,0]};reports.append(row)
 if result.returncode:break
report={'status':'PASS_PERSISTED_NEW_CANDIDATES_AND_COLD_READ' if all(r['return_code']==0 for r in reports) and len(reports)==len(companies) else 'FAILED_COLD_READ_NO_RETRY','companies':reports,'seconds':round(time.monotonic()-started,3),'new_calls':[0,0,0],'old_archive_repacked':False,'production_authorized':False}
(evidence/('cold-verified-'+companies[0]+'-summary.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
