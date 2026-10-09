import csv,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
base=Path(tempfile.mkdtemp(prefix='history-source-proof-consumer-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
scenes=[('jpmorgan_chase',2021,'B01',Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/bank-performance-jpm-20261009/state')),
 ('marriott_international',2022,'B02',Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/liquidity-marriott-20261009/state'))]
results=[]
def protect(state):
 return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
for company,year,metric,state in scenes:
 original=protect(state);source=json.loads((state/'company-task.json').read_text())['source_root'];ops=[]
 def invoke(name,args):
  code='import sys,json;from unittest.mock import patch;from tools.vnext_company import main\nfrom vnext import historical_statement_cases as cases\na=cases.prepare_historical_statement_year_case.__code__;b=cases._filing_source.__code__;c=cases._deterministic_metric_graph.__code__\ndef guard(frame,event,arg):\n if event=="call" and (frame.f_code is a or frame.f_code is b or frame.f_code is c):raise AssertionError("No source-unchanged preparation or calculation")\nsys.setprofile(guard)\nwith patch("socket.socket.connect",side_effect=AssertionError("No network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
  started=time.monotonic();p=subprocess.run([sys.executable,'-c',code,json.dumps(args)],text=True,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'scripts:tools:.'})
  (base/(company+'-'+name+'.stdout')).write_text(p.stdout);(base/(company+'-'+name+'.stderr')).write_text(p.stderr)
  value=json.loads(p.stdout);ops.append({'name':name,'seconds':time.monotonic()-started,'exit_code':p.returncode,'status':value.get('status')});print(company,ops[-1],flush=True);assert p.returncode==0,(p.stdout,p.stderr);return value
 args=['run','--company',company,'--period','fiscal-years','--fiscal-year-start',str(year),'--fiscal-year-end',str(year),'--metric',metric,'--source-root',source,'--work-dir',str(state),'--output-dir',str(base/company/'runs')]
 for name in ['first-after-checker-change','repeat-unchanged']:
  value=invoke(name,args);assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in value['metrics']),value
  assert original==protect(state)
 invoke('independent-results',['results','--company',company,'--state-root',str(state),'--output-root',str(base/company/'read')]);assert original==protect(state)
 rows=list(csv.DictReader((base/company/'read/metrics_matrix.csv').open()));selected=next(r for r in rows if r['metric_id']==metric and r['fiscal_year']==str(year))
 if metric=='B01':assert selected['status']=='N_A_STRUCTURAL' and selected['value']=='',selected
 else:
  reference=json.loads(Path('docs/evidence/issue47_source_proof_consumer_20261010/existing-marriott-reference.json').read_text())['reference']
  assert all(selected[k]==str(reference[k]) for k in ['value','unit','period_start','period_end','result_id']),selected
 results.append({'company_id':company,'metric_id':metric,'fiscal_year':year,'state_root':str(state),'source_root':source,'operations':ops,'selected_row':selected,'old_files':len(original),'all_old_files_preserved':True})
Path('docs/evidence/issue47_source_proof_consumer_20261010/actual-company.json').write_text(json.dumps({'base_main':'f6ef7886','public_commit':'08d3e620239426bd692f2bdb3577c21c352aa2f9','code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'output_root':str(base),'scenes':results,'preparation_amount_and_graph_calls':0,'new_calls':[0,0,0]},indent=2)+'\n')
