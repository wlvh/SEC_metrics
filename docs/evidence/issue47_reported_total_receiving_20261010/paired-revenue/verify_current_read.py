"""Only read the precise current unresolved state; no repeated source attempt."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/pfizer-statements-company-nvw2pcdt/state');base=Path(tempfile.mkdtemp(prefix='pfizer-paired-scope-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes();args=['results','--company','pfizer','--state-root',str(state),'--output-root',str(base/'read')]
code='''import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as cases
a=cases.prepare_historical_statement_year_case.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is a:raise AssertionError('Do not process this unresolved source again')
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);elapsed=time.monotonic()-start;assert p.returncode==0 and not p.stderr and before==hashes()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));b02=next(r for r in rows if r['metric_id']=='B02' and r['fiscal_year']=='2023');assert not b02['value'] and b02['status']=='WITHHELD';b01=next(r for r in rows if r['metric_id']=='B01' and r['fiscal_year']=='2023');assert b01['value']=='58496000000'
first=json.load(open('work/paired-revenue-consumer/first-company.json'));m=json.loads(first['stdout'])['metrics'][0];assessment=json.load((Path(m['result_root'])/'input-assessments.json').open())['assessments']['historical_statement'];assert assessment['reason']=='HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN';assert set(assessment['paired_revenue_scopes'])=={'current'}
sc=assessment['paired_revenue_scopes']['current'];assert sc['complete_scope_proven'];assert sc['reported_totals'][0]['total']['value']=='58496000000'
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':elapsed,'arguments':args,'output_root':str(base),'all_state_files_preserved':len(before),'rows':len(rows),'B02_current_withheld':b02,'B01_correct_preserved':b01,'saved_reason_from_original_de4_execution':assessment['reason'],'current_scope':{k:sc[k] for k in ('scope_id','status','complete_scope_proven')},'no_reexecution_for_later_reason_presentation_change':True,'calls':[0,0,0],'factory_calls':0};Path('work/paired-revenue-consumer/current-read.json').write_text(json.dumps(r,indent=2)+'\n');print(elapsed,len(before),len(rows),assessment['reason'],flush=True)
