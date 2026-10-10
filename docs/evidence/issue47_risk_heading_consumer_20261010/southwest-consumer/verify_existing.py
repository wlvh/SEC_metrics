"""Repeat only successful coordinates and read saved limitations; no re-extraction."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/southwest-statements-company-j7od5ap_/state');source=json.load((state/'company-task.json').open())['source_root'];base=Path(tempfile.mkdtemp(prefix='southwest-d01-repeat-read-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
refs=json.load(open('work/d01-southwest-consumer/existing-reference.json'))['years']
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and (p.name in {'company-task.json','completed-check.json','current-result.json'} or '/results/' in str(p) or '/shared-inputs/' in str(p))}
before=hashes();checks=[]
def invoke(name,args):
 code='''import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_risk_heading_case as case
a=case.prepare_historical_risk_heading_year_case.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is a:raise AssertionError('Do not re-extract saved D01')
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('No new network')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr};checks.append(r);assert p.returncode==0 and not p.stderr and before==hashes(),r;print(name,r['seconds'],flush=True);return json.loads(p.stdout)
for year in (2021,2024):
 args=['run','--company','southwest_airlines','--period','fiscal-years','--fiscal-year-start',str(year),'--fiscal-year-end',str(year),'--metric','D01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
 report=invoke('repeat-FY'+str(year),args);assert len(report['metrics'])==1 and report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not report['metrics'][0]['calculation_performed']
view=invoke('independent-subset-and-failure-read',['results','--company','southwest_airlines','--state-root',str(state),'--output-root',str(base/'read')]);rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));d01=[r for r in rows if r['metric_id']=='D01'];good=[r for r in d01 if r['value']];bad=[r for r in d01 if not r['value']]
assert len(rows)==25 and len(good)==2 and len(bad)==3
for r in good:
 old=refs[r['fiscal_year']]['reference'];assert r['value'].splitlines()==old['headings_read'] and r['accession']==old['accession'];assert r['unit']=='text' and r['period_start']==r['fiscal_year']+'-01-01' and r['period_end']==r['fiscal_year']+'-12-31'
for r in bad:assert r['requested_in_latest_execution']=='False' and r['period_role']=='SAVED_CHECK_NOT_REQUESTED_WITHOUT_RESULT'
failures={m['fiscal_year']:m for m in view['metrics'] if m['metric_id']=='D01' and m['value'] is None};assert failures[2022]['reason']==failures[2023]['reason']=='D01_MULTISPAN_HEADING_UNSUPPORTED';assert failures[2025]['reason']=='HISTORICAL_RISK_HEADINGS_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED'
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'checks':checks,'rows':rows,'failures':failures,'protected_files':before,'all_result_and_other_pointer_files_preserved':True,'state_root':str(state),'output_root':str(base),'two_complete_values_match_existing_references':True,'original_page_split_references_not_re_extracted':True,'new_calls':[0,0,0]};Path('work/d01-southwest-consumer/existing-repeat-read.json').write_text(json.dumps(r,indent=2)+'\n');print('Two correct years, three precise saved failures, old financial records retained',flush=True)
