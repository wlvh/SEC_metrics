"""Process only the three remaining existing Enphase historical B02 coordinates."""
import argparse,csv,hashlib,json,subprocess,sys,time
from decimal import Decimal,localcontext
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--task-root',type=Path,required=True);a=p.parse_args()
root=a.task_root.resolve();root.mkdir(parents=True,exist_ok=False);state=root/'state';source=a.source_root.resolve()
def hashes():return {str(f.relative_to(state)):hashlib.sha256(f.read_bytes()).hexdigest() for f in state.rglob('*') if f.is_file()} if state.exists() else {}
def invoke(name,args,forbid=False):
 code="""import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as h,historical_paired_revenue as p,calculator
blocked={h.prepare_historical_statement_year_case.__code__,p.revenue_claims_admitted_by_original.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def prof(f,e,a):
 if e=='call' and f.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
if sys.argv[2]=='1':sys.setprofile(prof)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
"""
 start=time.perf_counter();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args),str(int(forbid))],capture_output=True,text=True)
 r={'seconds':time.perf_counter()-start,'exit':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr}
 (root/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,round(r['seconds'],3),p.returncode,flush=True);assert p.returncode in (0,2) and not p.stderr,r
 return json.loads(p.stdout),r
args=['run','--company','enphase_energy','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2023','--metric','B02','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(root/'runs')]
first,fr=invoke('first',args)
assert len(first['metrics'])==3,first
# Repeat only completed checks. An actual input failure is not stable withholding.
failed=[m for m in first['metrics'] if m['status']=='INPUT_OR_EXECUTION_FAILED']
if not failed:
 protected={n:h for n,h in hashes().items() if '/results/' in n};repeat,rr=invoke('repeat-forbidden',args,True)
 assert all(not m['calculation_performed'] and not m['new_candidate_created'] for m in repeat['metrics']),repeat
 assert all(hashes().get(n)==h for n,h in protected.items())
else:rr={'not_run':'An actual input failure needs repair; do not falsely demand stable-result reuse'}
before=hashes();read,dr=invoke('independent-read',['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(root/'read')],True);assert before==hashes()
rows=list(csv.DictReader((root/'read/metrics_matrix.csv').open(encoding='utf-8-sig')));assert len(rows)==3,rows
checks=[]
for row in rows:
 r=Path(row['record_root']) if row.get('record_root') else None
 if r and (r/'input-assessments.json').exists():
  assessment=json.loads((r/'input-assessments.json').read_text())['assessments']['historical_statement']
  if row['value']:
   scopes=assessment['paired_revenue_scopes'];assert all(s['complete_scope_proven'] for s in scopes.values())
   original={role:s['reported_totals'][0] for role,s in scopes.items()}
   with localcontext() as c:
    c.prec=28;current=Decimal(original['current']['total']['value']);prior=Decimal(original['prior']['total']['value']);assert Decimal(row['value'])==(current-prior)/prior
   checks.append({'fy':row['fiscal_year'],'value':row['value'],'originals':original})
  else:checks.append({'fy':row['fiscal_year'],'value':None,'assessment':assessment})
(root/'original-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
(root/'summary.json').write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'phases':{'first':{k:fr[k] for k in ['seconds','exit']},'repeat':{k:rr[k] for k in ['seconds','exit'] if k in rr},'read':{k:dr[k] for k in ['seconds','exit']}},'rows':rows,'actual_input_failures':failed,'read_state_files_unchanged':len(before),'new_calls':[0,0,0]},indent=2)+'\n')
print(json.dumps([{'fy':r['fiscal_year'],'status':r['status'],'value':r['value']} for r in rows]))

