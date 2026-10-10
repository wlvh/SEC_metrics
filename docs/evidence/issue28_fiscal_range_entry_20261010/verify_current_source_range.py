"""Actual read-only fiscal range CLI; source bytes, no calculation or HTTP."""
import argparse,hashlib,json,pathlib,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--source-root',type=pathlib.Path,required=True);p.add_argument('--record',type=pathlib.Path,required=True);a=p.parse_args()
program=pathlib.Path(__file__).resolve().parents[3];source=a.source_root.resolve()
base=('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')
before={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in base}
prelude='''import sys,socket,urllib.request,runpy
sys.path[:0]=['.','scripts']
def forbidden(*a,**kw):raise AssertionError('No HTTP, financial calculation or full annual preparation in source planning')
socket.socket.connect=forbidden;urllib.request.urlopen=forbidden
import sec_http;sec_http.SecHttpClient.fetch=forbidden
from vnext import calculator,historical_annual_input,normal_annual_input_v2
calculator.calculate_metric=forbidden
historical_annual_input.prepare_historical_annual_input=forbidden
normal_annual_input_v2.prepare_saved_annual_input=forbidden
sys.argv=['tools/vnext_company.py',*sys.argv[1:]]
runpy.run_path('tools/vnext_company.py',run_name='__main__')
'''
args=['sources','--company','salesforce','--source-root',str(source),'--fiscal-year-start','2026','--fiscal-year-end','2026','--metric','B01','--metric','B02']
runs=[];protected={}
for ordinal in range(2):
 t=time.perf_counter();r=subprocess.run([sys.executable,'-B','-c',prelude,*args],cwd=program,capture_output=True,text=True);elapsed=time.perf_counter()-t
 report=json.loads(r.stdout);assert not r.stderr,r.stderr
 assert r.returncode==0 and report['status']=='FISCAL_RANGE_RESOLVED' and report['all_source_bytes_available'],report
 assert report['calls']=={'provider':0,'paid':0,'sec':0} and not report['metric_executed'] and not report['metric_acceptance_proven']
 task=report['tasks'][0];assert task['fiscal_year']==2026 and task['label']['original_dei_fiscal_year']==2025
 assert task['label']['actual_period']=={'period_start':'2025-02-01','period_end':'2026-01-31'},task['label']['actual_period']
 paths=set(base)
 proofs=[e[key] for e in report['candidates'] if e.get('source_fiscal_year_resolved') for key in ('primary_proof','companyfacts_proof')]
 proofs.extend(x['proof'] for x in task['source_preflight']['requirements'] if x.get('proof'))
 for proof in proofs:paths.update(proof[k] for k in ('request_repo_relative_path','request_headers_repo_relative_path'))
 actual={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in sorted(paths)}
 assert all(actual[f]==h for f,h in before.items())
 if ordinal:assert actual==protected and report['range_id']==runs[0]['report']['range_id']
 else:protected=actual
 runs.append({'seconds':elapsed,'exit':r.returncode,'report':report})
out={'program_root':str(program),'source_root':str(source),'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=program).decode().strip(),
 'uncommitted_source_hashes':{f:hashlib.sha256((program/f).read_bytes()).hexdigest() for f in ('scripts/vnext/company_local.py','scripts/vnext/company_fiscal_range.py','scripts/vnext/selected_source_requirements.py','scripts/vnext/historical_fiscal_labels.py','scripts/vnext/historical_statement_cases.py','tools/vnext_company.py')},
 'args':args,'runs':runs,'protected_source_files':protected,'source_ledger_unchanged':True,'requests_and_calculator_forbidden':True,'new_calls':[0,0,0]}
a.record.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'seconds':[r['seconds'] for r in runs],'issuer_year':2026,'raw_dei_year':2025,'actual_period':task['label']['actual_period'],'protected_files':len(protected),'range_id':report['range_id'],'calls':[0,0,0]}))
