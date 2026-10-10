"""One affected predecessor event coordinate through the shared company CLI."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/paramount-event-cli-1791538080993122000/state')
source='/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs'
company='paramount_skydance_paramount_global'
base=Path(tempfile.mkdtemp(prefix='event-reporter-source-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def protected():
    return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in state.rglob('*') if p.is_file() and
            ('results' in p.parts or p.name in {'current-result.json','completed-check.json','company-task.json'})}
before=protected();old_id=json.loads((state/'updates/C01/periods/FY2021/completed-check.json').read_text())['result_id']
args=['run','--company',company,'--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs'),
      '--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--metric','C01']
def invoke(name,args,repeat=False):
    code="""import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_event_cases as cases
from vnext.normal_governance_input import _Sources
factory=cases.prepare_historical_event_year_case.__code__;primary=_Sources.primary.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is primary:raise AssertionError('No extra annual primary read for unamended event source proof')
"""
    if repeat:code+=" if event=='call' and frame.f_code is factory:raise AssertionError('Unchanged event must reuse')\n"
    code+="sys.setprofile(guard)\nwith patch('socket.socket.connect',side_effect=AssertionError('No HTTP')):\n raise SystemExit(main(json.loads(sys.argv[1])))\n"
    start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
    r={'name':name,'arguments':args,'seconds':time.monotonic()-start,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    (base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    assert p.returncode==0 and not p.stderr,r
    return r,json.loads(p.stdout)
first,report=invoke('one-affected-coordinate',args)
assert len(report['metrics'])==1 and report['metrics'][0]['requested_fiscal_year']==2021
assert report['metrics'][0]['status']=='CANDIDATE_READY'
assert all((state/k).is_file() and hashlib.sha256((state/k).read_bytes()).hexdigest()==v
           for k,v in before.items() if 'results' in Path(k).parts or not k.startswith('updates/C01/periods/FY2021/'))
after=protected();repeat,report=invoke('repeat-forbidden-factory',args,True)
assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not report['metrics'][0]['calculation_performed']
assert protected()==after
read,view=invoke('independent-read',['results','--company',company,'--state-root',str(state),'--output-root',str(base/'read')],True)
assert protected()==after
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))
row=next(r for r in rows if r['metric_id']=='C01' and r['fiscal_year']=='2021')
assert (row['value'],row['unit'],row['period_start'],row['period_end'],row['cik'])==('1','count','2021-01-01','2021-12-31','813828')
record={'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'first':first,'repeat':repeat,'read':read,
        'rows':rows,'selected_row':row,'state_root':str(state),'output_root':str(base),
        'old_result_id':old_id,'new_result_id':row['result_id'],'old_protected_files':before,
        'new_protected_files':after,'old_business_records_preserved':True,
        'extra_event_reader_primary_calls':0,'unchanged_repeat_factory_calls':0,'new_calls':[0,0,0]}
Path('work/event-reporter-consumer/actual-company.json').write_text(json.dumps(record,indent=2)+'\n')
print([(r['name'],r['seconds']) for r in (first,repeat,read)])
