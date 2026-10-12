"""Receive the public bond-section patch in an existing withheld company task."""
import argparse,csv,hashlib,json,socket,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--state-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
source=a.source_root.resolve();state=a.state_root.resolve();out=a.output_root.resolve();out.mkdir(parents=True,exist_ok=False)
def hashes(root):return {f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file()}
before=hashes(state);protected={k:v for k,v in before.items() if '/results/' in k or '/checks/' in k};watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'];source_before={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in watch}
child_code="""import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b06_case as history,current_b06_case as debt,calculator
blocked={history.prepare_historical_b06_year_case.__code__,debt.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('STABLE_WITHHELD_MUST_NOT_RECALCULATE')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
"""
def invoke(name,args,blocked=False):
 start=time.perf_counter();r=subprocess.run([sys.executable,'-B','-c',child_code,json.dumps(args),str(int(blocked))],capture_output=True,text=True,timeout=120)
 data={'seconds':time.perf_counter()-start,'exit_code':r.returncode,'arguments':args,'stdout':r.stdout,'stderr':r.stderr};(out/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n');print(name,round(data['seconds'],3),r.returncode,flush=True);assert r.returncode in (0,2) and not r.stderr,data;return json.loads(r.stdout),data
args=['run','--company','macys','--metric','B06','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2024','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out/'first')]
first,first_record=invoke('migration',args);m=first['metrics'][0];assert m['calculation_performed'] and m['new_candidate_created'] and m['status']=='CANDIDATE_WITHHELD',first
assessment=json.loads((Path(m['result_root'])/'input-assessments.json').read_text())['assessments']['B06'];assert assessment['selection']['reason']=='B06_REPORTED_INTEREST_DEBT_SCOPE_UNRESOLVED',assessment
assert all(hashes(state).get(n)==h for n,h in protected.items())
result_files={k:v for k,v in hashes(state).items() if '/results/' in k};folders=sorted(str(f) for f in state.glob('updates/B06/periods/*/results/*'))
repeat,repeat_record=invoke('repeat-forbidden',args[:-1]+[str(out/'repeat')],True);r=repeat['metrics'][0];assert not r['calculation_performed'] and not r['new_candidate_created'] and r['result_id']==m['result_id'],repeat
assert result_files=={k:v for k,v in hashes(state).items() if '/results/' in k};assert folders==sorted(str(f) for f in state.glob('updates/B06/periods/*/results/*'))
before_read=hashes(state);read,read_record=invoke('independent-read',['results','--company','macys','--state-root',str(state),'--output-root',str(out/'read')],True);assert hashes(state)==before_read
rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open(encoding='utf-8-sig')));assert len(rows)==1;row=rows[0];assert not row['value'] and row['status']=='WITHHELD';assert (row['fiscal_year'],row['period_start'],row['period_end'])==('2024','2025-02-01','2025-02-01'),row
assert source_before=={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in watch}
summary={'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'phases':{n:{k:r[k] for k in ('seconds','exit_code','arguments')} for n,r in [('migration',first_record),('repeat',repeat_record),('read',read_record)]},'actual_selection':assessment['selection'],'row':row,'old_result_and_check_files_preserved':len(protected),'read_state_files_preserved':len(before_read),'new_result_files_preserved':len(result_files),'source_hashes':source_before,'new_calls':[0,0,0]};(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'actual_next_reason':assessment['selection']['reason'],'result_id':m['result_id'],'old_files_preserved':len(protected),'value':row['value']}))
