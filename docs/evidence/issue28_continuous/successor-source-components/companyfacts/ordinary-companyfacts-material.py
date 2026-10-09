"""Persist ten real native source graphs and cold-read two without a Git data root."""
import argparse,csv,json,os,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=a.repo.resolve();out=a.output.resolve()
if out.exists() or out==repo or repo in out.parents:raise SystemExit('Fresh external data output required')
out.mkdir(parents=True)
sys.path[:0]=[str(repo),str(repo/'scripts')]
from tests.vnext.test_normal_companyfacts_results import copy_sources
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
from vnext.canonical import sha256_file
paths=['scripts/vnext/normal_companyfacts_results.py','tests/vnext/test_normal_companyfacts_results.py','catalog/deterministic_metrics.json']
protected=['evidence/requests_log.csv','evidence/requests_log_manifest.json']
identity={x:sha256_file(path=repo/x) for x in paths+protected}
child='''import json,sys
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[1]+"/scripts"]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_companyfacts_results import verify_ordinary_companyfacts_metrics
with original_sources_only():
 result=verify_ordinary_companyfacts_metrics(candidate=json.loads(Path(sys.argv[2]).read_text()),repo_root=Path(sys.argv[3]),company_id=sys.argv[4])
 print(json.dumps({"component_id":result["component_id"],"metric_count":len(result["metrics"]),"calls":result["calls"],"status":"REBUILT_FROM_SAVED_SOURCE"}))
'''
(out/'cold.py').write_text(child)
rows=[]
with original_sources_only():
 for company in csv.DictReader((repo/'config/company_registry.csv').open()):
  cid=company['company_id'];start=time.monotonic()
  item=resolve_ordinary_companyfacts_metrics(repo_root=repo,company_id=cid)
  path=out/(cid+'.json');path.write_text(json.dumps(item,ensure_ascii=False))
  row={'company_id':cid,'component_id':item['component_id'],'source_proof_count':len(item['source_proofs']),
   'current_period':item['periods']['current'],'prior_period':item['periods']['prior'],'prior_error':item['prior_error'],
   'metrics':[{k:v for k,v in r['result'].items() if k in {'metric_id','value','unit','publication','quality','applicability','period_start','period_end'}}
              | {'selection':r['selection']} for r in item['metrics'].values()]}
  if cid in {'marriott_international','macys'}:
   data=out/(cid+'-data');data.mkdir();copy_sources(item,data)
   result=subprocess.run([sys.executable,'-I','-B',str(out/'cold.py'),str(repo),str(path),str(data),cid],cwd=out,text=True,capture_output=True,timeout=120)
   (out/(cid+'-cold.log')).write_text(result.stdout+result.stderr)
   row['cold_exit']=result.returncode;row['no_git_data_root']=not (data/'.git').exists()
   if result.returncode:raise RuntimeError(result.stderr)
  row['seconds']=round(time.monotonic()-start,3);rows.append(row)
  (out/'index.json').write_text(json.dumps(rows,indent=2));print(cid,len(row['metrics']),row.get('cold_exit'),flush=True)
now={x:sha256_file(path=repo/x) for x in paths+protected}
(out/'execution.json').write_text(json.dumps({'command':sys.argv,'before':identity,'after':now,'unchanged':identity==now,
 'calls':{'provider':0,'paid':0,'sec':0},'native_runs_created':False},indent=2))
if identity!=now:raise SystemExit('Source or protected ledger changed')
