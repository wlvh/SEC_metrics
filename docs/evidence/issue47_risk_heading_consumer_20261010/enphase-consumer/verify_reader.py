"""Shared reader only: preserve completed subset and unrequested original failure."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/enphase-statements-company-jvkm2nml/state')
base=Path(tempfile.mkdtemp(prefix='enphase-d01-failure-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes()
args=['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(base/'read')]
code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_risk_heading_case as case
a=case.prepare_historical_risk_heading_year_case.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is a:raise AssertionError('Read must not prepare or calculate')
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-start
(base/'execution.json').write_text(json.dumps({'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':elapsed,'arguments':args,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode,'protected_files':before},indent=2)+'\n')
assert p.returncode==0 and not p.stderr,(p.returncode,p.stdout,p.stderr)
assert before==hashes()
view=json.loads(p.stdout);rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))
fail=next(m for m in view['metrics'] if m['metric_id']=='D01' and m['fiscal_year']==2021)
assert fail['value'] is None and fail['reason']=='DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND'
assert fail['requested_in_latest_execution'] is False
old=json.loads(Path('work/d01-enphase-consumer/fouryear-existing-summary.json').read_text())
current=[r for r in rows if r['metric_id']=='D01' and r['value']]
assert [(r['fiscal_year'],r['value'],r['result_id']) for r in current]==[(r['fiscal_year'],r['value'],r['result_id']) for r in old['rows'] if r['metric_id']=='D01']
assert len(rows)==25
failed_row=next(r for r in rows if r['metric_id']=='D01' and r['fiscal_year']=='2021')
assert 'DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND' in failed_row['notes']
assert failed_row['period_role']=='SAVED_CHECK_NOT_REQUESTED_WITHOUT_RESULT'
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':elapsed,'arguments':args,'state_root':str(state),'output_root':str(base),'new_calls':[0,0,0],'factory_calls':0,'protected_files':before,'all_state_files_preserved':True,'metric_rows':len(rows),'failure':fail,'failed_csv_row':failed_row,'four_correct_values_and_ids_preserved':True,'stdout':p.stdout}
Path('work/d01-enphase-consumer/reader-combination.json').write_text(json.dumps(r,indent=2)+'\n');print(elapsed,len(rows),len(before),failed_row['period_role'],flush=True)
