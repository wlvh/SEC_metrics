"""Actual selected historical B06: source/case, stable withholding and CSV read."""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output-root',type=Path,required=True);a=parser.parse_args();source=a.source_root.resolve();base=a.output_root.resolve();base.mkdir(parents=True,exist_ok=False)
def digest(state):return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
def invoke(name,cli,forbid):
 code="""import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b06_case as h,current_b06_case as b,calculator
blocked={h.prepare_selected_debt_sources.__code__,h.prepare_selected_debt_input.__code__,b.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('No source/case/calculation on stable repeat or read')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
 t=time.perf_counter();r=subprocess.run([sys.executable,'-B','-c',code,json.dumps(cli),'1' if forbid else '0'],text=True,capture_output=True);d={'arguments':cli,'seconds_subprocess_inclusive':time.perf_counter()-t,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(base/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n');assert r.returncode in (0,2) and not r.stderr,d;print(name,round(d['seconds_subprocess_inclusive'],3),r.returncode,flush=True);return d,json.loads(r.stdout)
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'];before_source={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch};rows=[]
for company,year,period in [('enphase_energy',2021,('2021-12-31','2021-12-31')),('salesforce',2022,('2022-01-31','2022-01-31'))]:
 state=base/company/'state';cli=['run','--company',company,'--period','fiscal-years','--fiscal-year-start',str(year),'--fiscal-year-end',str(year),'--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(base/company/'runs')]
 first,res=invoke(company+'-first',cli,False);m=res['metrics'][0];assert len(res['metrics'])==1 and m['status']=='CANDIDATE_WITHHELD',m
 after=digest(state);protected={p:h for p,h in after.items() if '/results/' in p or p.endswith('completed-check.json') or p=='company-task.json'}
 again,rep=invoke(company+'-repeat',cli,True);rm=rep['metrics'][0];assert not rm['calculation_performed'] and not rm['new_candidate_created'] and rm['result_id']==m['result_id'],rm;assert all(digest(state).get(p)==h for p,h in protected.items())
 before=digest(state);read,data=invoke(company+'-read',['results','--company',company,'--state-root',str(state),'--output-root',str(base/company/'read')],True);assert before==digest(state)
 records=list(csv.DictReader((base/company/'read/metrics_matrix.csv').open()));assert len(records)==1;row=records[0];assert not row['value'] and row['status']=='WITHHELD' and row['fiscal_year']==str(year) and (row['period_start'],row['period_end'])==period and row['result_id']==m['result_id'],row
 rows.append({'company_id':company,'fiscal_year':year,'phases':{name:{k:d[k] for k in ['arguments','seconds_subprocess_inclusive','exit']} for name,d in [('first',first),('repeat',again),('read',read)]},'metric':m,'repeat_metric':rm,'row':{k:row[k] for k in ['metric_id','value','status','unit','fiscal_year','period_start','period_end','cik','result_id','notes']},'protected_files':len(protected),'read_state_files_unchanged':len(before)})
assert before_source=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
x={'execution':'public189 exact plus uncommitted historical caller/config repair','local_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_metadata_hashes_unchanged':before_source,'companies':rows,'new_calls':[0,0,0]};(base/'summary.json').write_text(json.dumps(x,indent=2)+'\n');print('Two actual historical ordinary states complete; no new business value credited')
