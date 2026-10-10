"""Obtainable main-based delivery reads the real repaired result without processing."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
original=json.load(open('work/paired-revenue-consumer/repaired-company.json'));state=Path(original['state_root']);base=Path(tempfile.mkdtemp(prefix='pfizer-growth-delivery-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes();args=['results','--company','pfizer','--state-root',str(state),'--output-root',str(base/'read')]
code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as cases
fn=cases.prepare_historical_statement_year_case.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is fn:raise AssertionError('Read only, no packaging recalculation')
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-start;assert p.returncode==0 and not p.stderr and before==hashes();rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));assert rows==original['rows']
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':elapsed,'arguments':args,'rows_equal_repaired_actual_composition':True,'rows':len(rows),'all_state_files_unchanged':len(before),'code_uncommitted':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),'factory_calls':0,'new_calls':[0,0,0],'stdout':p.stdout};Path('work/paired-revenue-delivery/short-read.json').write_text(json.dumps(r,indent=2)+'\n');print(elapsed,len(rows),len(before),flush=True)
