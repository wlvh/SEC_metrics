import csv,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/pfizer-statements-company-nvw2pcdt/state')
source=json.loads((state/'company-task.json').read_text())['source_root']
base=Path(tempfile.mkdtemp(prefix='pfizer-revenue-scope-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
ops=[]
def protect():
 return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
old=protect(); preserved={n:sha for n,sha in old.items() if '/B01/periods/FY2023/' not in '/'+n or '/results/' in '/'+n}
def invoke(name,args,forbid=False):
 code='import sys,json;from unittest.mock import patch;from tools.vnext_company import main\nfrom vnext import historical_statement_cases as case\n'
 if forbid:
  code+='a=case.prepare_historical_statement_year_case.__code__;b=case.calculate_metric.__code__\ndef guard(frame,event,arg):\n if event=="call" and (frame.f_code is a or frame.f_code is b):raise AssertionError("No unchanged-input calculation")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([sys.executable,'-c',code,json.dumps(args)],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'scripts:tools:.'})
 (base/(name+'.stdout')).write_text(p.stdout);(base/(name+'.stderr')).write_text(p.stderr)
 value=json.loads(p.stdout);ops.append({'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'status':value.get('status'),'metrics':value.get('metrics')})
 Path('work/revenue-scope/progress.json').write_text(json.dumps({'output_root':str(base),'operations':ops},indent=2)+'\n');print({k:ops[-1][k] for k in ['name','seconds','exit_code','status']},flush=True)
 assert p.returncode==0,(p.stdout,p.stderr);return value
args=['run','--company','pfizer','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023','--metric','B01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
v=invoke('correct-known-scope',args);assert len(v['metrics'])==1 and v['metrics'][0]['status']=='CANDIDATE_READY',v
assert all(hashlib.sha256((state/n).read_bytes()).hexdigest()==sha for n,sha in preserved.items())
before=protect();v=invoke('repeat-forbid-factory',args,True);assert all(not m['calculation_performed'] and m['status']=='NO_SOURCE_CONTENT_CHANGE' for m in v['metrics']),v
assert before==protect();invoke('independent-results',['results','--company','pfizer','--state-root',str(state),'--output-root',str(base/'read')],True);assert before==protect()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));selected=[r for r in rows if r['metric_id']=='B01' and r['fiscal_year']=='2023'];assert len(selected)==1
r=selected[0];assert (r['value'],r['unit'],r['period_start'],r['period_end'])==('58496000000','USD','2023-01-01','2023-12-31'),r
assert r['result_id']=='sha256:128c170a19b5505f3ce22e837aaea836159b4652e334aa4b5bdf298e007786da',r
assert len(rows)==20, len(rows)
assert any('a6e31052ee3e389e46442777fa69c0d06c6ec43e847dd65c412c0e05509aa8f7' in (state/n).read_text() for n in preserved if '/results/' in '/'+n)
Path('docs/evidence/issue47_revenue_scope_consumer_20261010/actual-company.json').write_text(json.dumps({'base_main':'f6ef7886d6630f7675c25cd42e306c373ab05769','public_commits':['b962b6c9a69d3d7fd85541f6b92346a7b651c093','83eaa4da5d18c7accc0c093b1ef4db5f5158da16','62243bfdce042a79508f242df65cc897fcfaf035'],'source_root':source,'state_root':str(state),'output_root':str(base),'operations':ops,'selected_result':r,'total_coordinates_read':len(rows),'old_files':len(old),'protected_old_files':len(preserved),'final_files':len(before),'old_results_and_other_coordinates_preserved':True,'repeat_factory_and_calculator_calls':0,'new_calls':[0,0,0]},indent=2)+'\n')
