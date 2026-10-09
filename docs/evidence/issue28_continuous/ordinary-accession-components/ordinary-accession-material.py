import argparse,csv,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=a.repo.resolve();out=a.output.resolve()
if out.exists() or out==repo or repo in out.parents:raise SystemExit('Fresh external output required')
out.mkdir(parents=True);sys.path[:0]=[str(repo),str(repo/'scripts')]
from tests.vnext.test_normal_companyfacts_results import copy_sources
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_accession_results import resolve_ordinary_accession_metrics
from vnext.canonical import sha256_file
paths=['config/normal_accession_metrics_v1.json','scripts/vnext/normal_accession_results.py','tests/vnext/test_normal_accession_results.py','evidence/requests_log.csv','evidence/requests_log_manifest.json']
before={p:sha256_file(path=repo/p) for p in paths}
child='''import sys,json
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[1]+"/scripts"]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_accession_results import verify_ordinary_accession_metrics
with original_sources_only():
 r=verify_ordinary_accession_metrics(candidate=json.loads(Path(sys.argv[2]).read_text()),repo_root=Path(sys.argv[3]),company_id=sys.argv[4])
 print(json.dumps({"component_id":r["component_id"],"metric_count":len(r["metrics"]),"calls":r["calls"],"status":"REBUILT_FROM_SAVED_SOURCE"}))
'''
(out/'cold.py').write_text(child)
rows=[]
with original_sources_only():
 for c in csv.DictReader((repo/'config/company_registry.csv').open()):
  company=c['company_id'];start=time.monotonic();r=resolve_ordinary_accession_metrics(repo_root=repo,company_id=company)
  file=out/(company+'.json');file.write_text(json.dumps(r,ensure_ascii=False))
  row={'company_id':company,'component_id':r['component_id'],'metrics':[{'metric_id':m,**{k:x['result'][k] for k in ('value','unit','period_start','period_end','applicability','publication')},'measure':x['measure']} for m,x in r['metrics'].items()]}
  if company in {'jpmorgan_chase','salesforce'}:
   data=out/(company+'-data');data.mkdir();copy_sources(r,data)
   done=subprocess.run([sys.executable,'-I','-B',str(out/'cold.py'),str(repo),str(file),str(data),company],cwd=out,text=True,capture_output=True,timeout=120)
   (out/(company+'-cold.log')).write_text(done.stdout+done.stderr)
   row['cold_exit']=done.returncode;row['no_git_data_root']=not (data/'.git').exists()
   if done.returncode:raise RuntimeError(done.stderr)
  row['elapsed_seconds']=round(time.monotonic()-start,3);rows.append(row)
  (out/'index.json').write_text(json.dumps(rows,indent=2));print(company,'PASS',row.get('cold_exit'),flush=True)
after={p:sha256_file(path=repo/p) for p in paths}
(out/'execution.json').write_text(json.dumps({'command':sys.argv,'before':before,'after':after,'unchanged':before==after,'calls':{'provider':0,'paid':0,'sec':0},'native_runs_created':False},indent=2))
if before!=after:raise SystemExit('Input or protected ledger drift')
