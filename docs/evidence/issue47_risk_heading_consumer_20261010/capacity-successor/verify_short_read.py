import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/enphase-statements-company-jvkm2nml/state');base=Path(tempfile.mkdtemp(prefix='enphase-capacity-delivery-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes();args=['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(base/'read')]
code='''import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_risk_heading_case as case
a=case.prepare_historical_risk_heading_year_case.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is a:raise AssertionError('Read only')
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-start
assert p.returncode==0 and not p.stderr and before==hashes()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));reference=json.load(open('work/d01-capacity-consumer/actual-company.json'))['rows'];assert rows==reference and len(rows)==25
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':elapsed,'exit_code':p.returncode,'arguments':args,'rows':len(rows),'all_existing_rows_equal_actual_company_composition':True,'all_state_files_preserved':len(before),'factory_calls':0,'new_calls':[0,0,0],'stdout':p.stdout};Path('work/d01-capacity-delivery/short-read.json').write_text(json.dumps(r,indent=2)+'\n');print(elapsed,len(before),len(rows))
