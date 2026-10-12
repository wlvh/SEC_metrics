"""Recover one saved failed year using the public company CLI; no source writes."""
import argparse,csv,hashlib,json,subprocess,sys,time
from decimal import Decimal,localcontext
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--state-root',type=Path,required=True)
p.add_argument('--output-root',type=Path,required=True)
a=p.parse_args(); source=a.source_root.resolve(); state=a.state_root.resolve(); out=a.output_root.resolve()
out.mkdir(parents=True,exist_ok=False)
def hashes(root):
 return {str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file()}
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json']
source_before={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in watch}
before=hashes(state); (out/'before-state.json').write_text(json.dumps(before,indent=2)+'\n')
protected_old={n:h for n,h in before.items() if '/results/' in n or '/checks/' in n}
def invoke(name,args,forbidden=False):
 code="""import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as s,historical_paired_revenue as p,calculator
blocked={s.prepare_historical_statement_year_case.__code__,s._prepare_historical_statement_case.__code__,p.revenue_claims_admitted_by_original.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
 raise SystemExit(main(json.loads(sys.argv[1])))
"""
 start=time.perf_counter(); proc=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args),str(int(forbidden))],capture_output=True,text=True)
 record={'seconds':time.perf_counter()-start,'exit_code':proc.returncode,'arguments':args,'stdout':proc.stdout,'stderr':proc.stderr}
 (out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 print(name,round(record['seconds'],3),proc.returncode,flush=True)
 assert proc.returncode in (0,2) and not proc.stderr,record
 return json.loads(proc.stdout),record
args=['run','--company','enphase_energy','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','B02','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out/'runs')]
first,first_record=invoke('recovery',args)
m=first['metrics'][0]; assert m['calculation_performed'] and m['new_candidate_created'],first
assert all(hashes(state).get(n)==h for n,h in protected_old.items())
protected=hashes(state); result_dirs={str(f) for f in state.glob('updates/B02/periods/*/results/*')}
repeat,repeat_record=invoke('repeat-forbidden',args,True)
r=repeat['metrics'][0]; assert not r['calculation_performed'] and not r['new_candidate_created'],repeat
assert r['result_id']==m['result_id']
assert result_dirs=={str(f) for f in state.glob('updates/B02/periods/*/results/*')}
assert all(hashes(state).get(n)==h for n,h in protected.items() if '/results/' in n or n.endswith(('current-result.json','completed-check.json')))
before_read=hashes(state)
read,read_record=invoke('independent-read',['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(out/'read')],True)
assert before_read==hashes(state)
rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open(encoding='utf-8-sig'))); assert len(rows)==1,rows
row=rows[0]; root=Path(row['record_root'])
assessment=json.loads((root/'input-assessments.json').read_text())['assessments']['historical_statement']
scopes=assessment['paired_revenue_scopes']; assert set(scopes)=={'current','prior'}
assert all(s['complete_scope_proven'] for s in scopes.values()),scopes
records=[json.loads(line) for line in (root/'records.jsonl').read_text().splitlines()]
claims=[x for x in records if x['record_type']=='DETERMINISTIC_VERIFIED_CLAIM']
(out/'selected-source-scopes.json').write_text(json.dumps(scopes,indent=2)+'\n')
(out/'selected-native-claims.json').write_text(json.dumps(claims,indent=2)+'\n')
assert row['unit']=='ratio' and row['cik']=='1463101'
assert (row['fiscal_year'],row['period_start'],row['period_end'])==('2024','2024-01-01','2024-12-31')
assert row['value'],row
assert source_before=={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in watch}
summary={'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'phases':{n:{k:r[k] for k in ('seconds','exit_code','arguments')} for n,r in [('recovery',first_record),('repeat',repeat_record),('read',read_record)]},'row':row,'source_hashes':source_before,'old_files_unchanged':len(protected_old),'read_state_files_unchanged':len(before_read),'new_calls':[0,0,0]}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'value':row['value'],'result_id':row['result_id'],'old_files_unchanged':len(protected_old)}))

