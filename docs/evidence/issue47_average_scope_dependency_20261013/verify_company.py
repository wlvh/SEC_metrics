"""One selected historical A03, shared controller, no network or source writes."""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--old-state',type=Path,required=True);a=p.parse_args()
source=a.source_root.resolve();work=a.work_root.resolve();old=a.old_state.resolve();work.mkdir(parents=True,exist_ok=False)
def hashes(root):return {x.relative_to(root).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob('*') if x.is_file()}
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'];source_before={x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch};old_before=hashes(old)
child_code="""import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_average_risk_cases as cases,historical_average_risk_wording as wording,calculator
blocked={cases.prepare_historical_average_risk_year_case.__code__,wording.inspect_historical_average_risk.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
"""
def invoke(name,args,forbidden=False):
 start=time.perf_counter();result=subprocess.run([sys.executable,'-B','-c',child_code,json.dumps(args),str(int(forbidden))],capture_output=True,text=True,timeout=180)
 record={'seconds':time.perf_counter()-start,'exit_code':result.returncode,'arguments':args,'stdout':result.stdout,'stderr':result.stderr};(work/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(name,round(record['seconds'],3),result.returncode,flush=True)
 assert result.returncode==0 and not result.stderr,record
 return json.loads(result.stdout),record
args=['run','--company','jpmorgan_chase','--metric','A03','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--source-root',str(source),'--work-dir',str(work/'state'),'--output-dir',str(work/'first')]
first,first_record=invoke('first',args);item=first['metrics'][0];assert item['calculation_performed'] and item['new_candidate_created'],first
protected={k:v for k,v in hashes(work/'state').items() if '/results/' in k};folders=sorted(str(x) for x in (work/'state').glob('updates/A03/periods/*/results/*'))
repeat,repeat_record=invoke('repeat-forbidden',args[:-1]+[str(work/'repeat')],True);r=repeat['metrics'][0];assert not r['calculation_performed'] and not r['new_candidate_created'],repeat
assert r['result_id']==item['result_id'];assert protected=={k:v for k,v in hashes(work/'state').items() if '/results/' in k};assert folders==sorted(str(x) for x in (work/'state').glob('updates/A03/periods/*/results/*'))
before_read=hashes(work/'state');read,read_record=invoke('independent-read',['results','--company','jpmorgan_chase','--state-root',str(work/'state'),'--output-root',str(work/'read')],True);assert hashes(work/'state')==before_read
rows=list(csv.DictReader((work/'read/metrics_matrix.csv').open(encoding='utf-8-sig')));assert len(rows)==1;row=rows[0]
assert (row['metric_id'],row['value'],row['unit'],row['fiscal_year'],row['period_start'],row['period_end'],row['fiscal_period'],row['cik'])==('A03','1.11','ratio','2021','2021-10-01','2021-12-31','QUARTER','19617'),row
current=json.loads((work/'state/updates/A03/periods/FY2021/current-result.json').read_text());decl=current['configuration']['declared_processing_files'];target='scripts/vnext/scope_contract.py'
assert decl[target]==hashlib.sha256(Path(target).read_bytes()).hexdigest()
old_read,old_record=invoke('old-read',['results','--company','jpmorgan_chase','--state-root',str(old),'--output-root',str(work/'old-read')],True);assert hashes(old)==old_before
old_rows=list(csv.DictReader((work/'old-read/metrics_matrix.csv').open(encoding='utf-8-sig')));previous=next(x for x in old_rows if x['metric_id']=='A03' and x['fiscal_year']=='2021');assert previous['result_id']==row['result_id'];assert (previous['value'],previous['period_start'],previous['period_end'])==(row['value'],row['period_start'],row['period_end'])
assert source_before=={x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
summary={'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'uncommitted_historical_dependency_patch':True,'row':row,'phases':{n:{'seconds':v['seconds'],'exit_code':v['exit_code']} for n,v in [('first',first_record),('repeat',repeat_record),('read',read_record),('old-read',old_record)]},'actual_declared_dependency':{target:decl[target]},'new_result_files_preserved':len(protected),'new_read_state_files_preserved':len(before_read),'old_rows_read':len(old_rows),'old_state_files_preserved':len(old_before),'source_hashes':source_before,'new_calls':[0,0,0],'limits':['One fresh A03 year; A12 real source and remaining years not rerun.','Constructed dependency controls are not bank business conclusions.']}
(work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'value':row['value'],'result_id':row['result_id'],'actual_period':[row['period_start'],row['period_end']],'old_state_files':len(old_before)},indent=2))
