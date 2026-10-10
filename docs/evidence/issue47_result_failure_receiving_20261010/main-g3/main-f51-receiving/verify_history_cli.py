import argparse,csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['first','repeat','read']);a=parser.parse_args()
w=Path('work/processing-scope-consumer');location=w/'location.json'
if a.mode=='first':
 base=Path(tempfile.mkdtemp(prefix='history-processing-scope-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'));location.write_text(json.dumps({'base':str(base)}))
else:base=Path(json.loads(location.read_text())['base'])
state=base/'state';source='/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs'
def protected():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ['current-result.json','company-task.json'])}
before=protected();args=['results','--company','marriott_international','--state-root',str(state),'--output-root',str(base/'read-pr138-20261011')] if a.mode=='read' else ['run','--company','marriott_international','--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','B04','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
if a.mode!='first':code+='from vnext import historical_statement_cases as cases,calculator\na=cases.prepare_historical_statement_year_case.__code__;b=calculator.calculate_metric.__code__\ndef guard(frame,event,arg):\n if event=="call" and (frame.f_code is a or frame.f_code is b):raise AssertionError("Unrelated D04 increment cannot calculate history")\nsys.setprofile(guard)\n'
code+='with patch("socket.socket.connect",side_effect=AssertionError("No network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);secs=time.monotonic()-t;(w/(a.mode+'.stdout')).write_text(p.stdout);(w/(a.mode+'.stderr')).write_text(p.stderr);assert p.returncode==0 and not p.stderr,(p.returncode,p.stdout,p.stderr);r=json.loads(p.stdout)
output=Path(r['output_root']);rows=list(csv.DictReader((output/'metrics_matrix.csv').open()));assert len(rows)==1;row=rows[0]
assert row['value']=='2601000000' and row['unit']=='USD' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31' and row['fiscal_year']=='2025'
if a.mode!='first':
 first=json.loads((w/'first.json').read_text());assert before==protected();assert all(row[k]==first['row'][k] for k in ['value','unit','period_start','period_end','fiscal_year','result_id','cik'])
if a.mode=='repeat':assert r['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not r['metrics'][0]['calculation_performed']
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'mode':a.mode,'seconds':secs,'row':row,'state_root':str(state),'output_root':str(output),'protected_result_files':len(protected()),'old_results_preserved':before==protected() if a.mode!='first' else None,'metric_status':r.get('metrics',[{}])[0].get('status'),'configuration_compatibility':r.get('metrics',[{}])[0].get('configuration_compatibility'),'new_calls':[0,0,0]}
(w/(a.mode+'.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(a.mode,secs,receipt['metric_status'],row['value'],flush=True)
