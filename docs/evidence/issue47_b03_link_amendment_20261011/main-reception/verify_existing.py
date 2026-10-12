"""Upgrade the two already-read Southwest consumers using the same company CLI."""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
args=parser.parse_args();base=args.output_root.resolve();base.mkdir(parents=True,exist_ok=False)
source=args.source_root.resolve()
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json']
before_source={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def invoke(name,cli,forbidden=False):
 code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b03_case as h,selected_income_calculation as s,historical_statement_cases as t,calculator
blocked={h.prepare_historical_income_year_case.__code__,h.prepare_selected_income_sources.__code__,s.calculate_selected_income.__code__,t.prepare_historical_current_annual_year_case.__code__,t._prepare_historical_statement_case.__code__,calculator.calculate_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('Unchanged/read cannot prepare or calculate')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
 start=time.perf_counter();r=subprocess.run([sys.executable,'-B','-c',code,json.dumps(cli),'1' if forbidden else '0'],capture_output=True,text=True)
 entry={'arguments':cli,'seconds':time.perf_counter()-start,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(base/(name+'.json')).write_text(json.dumps(entry,indent=2)+'\n');assert not r.stderr and r.returncode in (0,2),(name,r.returncode,r.stderr);print(name,round(entry['seconds'],3),r.returncode,flush=True);return entry,json.loads(r.stdout)
def rows(output):
 with (output/'metrics_matrix.csv').open() as stream:return list(csv.DictReader(stream))
receipt=[]
for metric,stem in [('B03','b03-link-amendment-20261011-47'),('B07','b07-link-amendment-20261011-47')]:
 state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence')/stem/'state';old=hashes(state);protected={p:h for p,h in old.items() if '/results/' in p}
 pre,_=invoke(metric+'-read-before',['results','--company','southwest_airlines','--state-root',str(state),'--output-root',str(base/(metric+'-before'))],True);assert old==hashes(state);before_rows=rows(base/(metric+'-before'))
 cli=['run','--company','southwest_airlines','--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025','--metric',metric,'--source-root',str(source),'--work-dir',str(state),'--output-dir',str(base/(metric+'-runs'))]
 upgrade,result=invoke(metric+'-one-upgrade',cli);assert result['metrics'][0]['status']=='CANDIDATE_READY';assert all(hashes(state).get(p)==h for p,h in protected.items())
 all_result={p:h for p,h in hashes(state).items() if '/results/' in p};repeat,result=invoke(metric+'-forbidden-repeat',cli,True);assert not result['metrics'][0]['calculation_performed'] and not result['metrics'][0]['new_candidate_created'];assert all(hashes(state).get(p)==h for p,h in all_result.items())
 before_read=hashes(state);read,_=invoke(metric+'-read',['results','--company','southwest_airlines','--state-root',str(state),'--output-root',str(base/(metric+'-read'))],True);assert before_read==hashes(state);after_rows=rows(base/(metric+'-read'));keys=('metric_id','fiscal_year','period_start','period_end','value','unit','status','result_id');assert sorted(tuple(r[k] for k in keys) for r in before_rows)==sorted(tuple(r[k] for k in keys) for r in after_rows)
 receipt.append({'metric':metric,'pre':pre,'upgrade':upgrade,'repeat':repeat,'read':read,'rows':after_rows,'old_result_files_preserved':len(protected),'repeat_result_files_preserved':len(all_result),'read_state_files_unchanged':len(before_read)})
assert before_source=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
(base/'receipt.json').write_text(json.dumps({'source_root':str(source),'records':receipt,'source_hashes_unchanged':before_source,'new_calls':[0,0,0]},indent=2)+'\n');print('Both original values/IDs/periods and genuine missing year preserved')
