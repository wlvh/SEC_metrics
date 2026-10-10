import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
old=json.loads(Path('work/range-main/actual-company.json').read_text());state=Path(old['state_root']);source=json.load((state/'company-task.json').open())['source_root'];base=Path(tempfile.mkdtemp(prefix='macys-range-missing-year-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def snapshot():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or '/shared-inputs/' in str(p) or p.name in ['company-task.json','current-result.json','completed-check.json'])}
before=snapshot();code="""import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as cases,calculator
blocked={cases.prepare_historical_statement_year_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=="call" and frame.f_code in blocked:raise AssertionError("Missing year/read cannot enter business computation")
sys.setprofile(guard)
with patch("socket.socket.connect",side_effect=AssertionError("No network")):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
runargs=['run','--company','macys','--period','fiscal-years','--fiscal-year-start','2027','--fiscal-year-end','2027','--metric','B01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
rows=[]
for name,args in [('missing',runargs),('read',['results','--company','macys','--state-root',str(state),'--output-root',str(base/'read')])]:
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);seconds=time.monotonic()-t;r={'name':name,'seconds':seconds,'exit_code':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr};(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,p.returncode,round(seconds,3),flush=True)
 assert not p.stderr;value=json.loads(p.stdout)
 if name=='missing':
  assert p.returncode==2 and len(value['metrics'])==1;m=value['metrics'][0];assert m['requested_fiscal_year']==2027 and m['status']=='INPUT_OR_EXECUTION_FAILED' and m['error_category']=='SOURCE_UNAVAILABLE' and m['previous_result'] is None
 else:assert p.returncode==0
 assert all(snapshot().get(k)==h for k,h in before.items());rows.append(r)
csvrows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));b01=next(r for r in csvrows if r['metric_id']=='B01' and r['fiscal_year']=='2023');b02=next(r for r in csvrows if r['metric_id']=='B02' and r['fiscal_year']=='2023');missing=next(r for r in csvrows if r['metric_id']=='B01' and r['fiscal_year']=='2027');assert b01['value']=='23866000000' and b02['value']=='' and b02['status']=='WITHHELD' and not missing['value'];assert len(csvrows)==23
Path('work/range-main/missing-year-receiving.json').write_text(json.dumps({'code_parent':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'public_uncommitted_merge':'870edf6b','runs':rows,'protected_files':len(before),'FY2023_values_not_recomputed':True,'business_factory_calculator_calls':0,'csvrows':csvrows,'output_root':str(base),'new_calls':[0,0,0]},indent=2)+'\n');print('PASS precise absent saved year, old successful and withheld periods remain current',flush=True)
