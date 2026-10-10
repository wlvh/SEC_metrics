"""Only the confirmed FY2023 B01 subtotal error needs a new calculation."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/statement-pilot-macys-20261009/state')
source=json.loads((state/'company-task.json').read_text())['source_root']
base=Path(tempfile.mkdtemp(prefix='macys-reported-total-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def protect():
    return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in state.rglob('*') if p.is_file() and
            ('results' in p.parts or p.name in {'current-result.json','completed-check.json','company-task.json'})}
before=protect();old_b01=json.loads((state/'updates/B01/periods/FY2023/current-result.json').read_text())['result_id']
args=['run','--company','macys','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023',
      '--metric','B01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
def invoke(name,args,forbid=False):
    code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
    if forbid:
        code+="""from vnext import historical_statement_cases as cases,company_fiscal_range as ranges
a=cases.prepare_historical_statement_year_case.__code__;b=cases.calculate_metric.__code__;c=ranges.discover_fiscal_range.__code__
def guard(frame,event,arg):
 if event=='call' and (frame.f_code is a or frame.f_code is b or frame.f_code is c):raise AssertionError('Unchanged company result cannot discover or calculate again')
sys.setprofile(guard)
"""
    code+="with patch('socket.socket.connect',side_effect=AssertionError('No new HTTP')):\n raise SystemExit(main(json.loads(sys.argv[1])))"
    start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
    r={'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':args}
    (base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    assert p.returncode==0 and not p.stderr,r
    return r,json.loads(p.stdout)
first,report=invoke('correct-one-revenue-total',args)
assert len(report['metrics'])==1 and report['metrics'][0]['requested_fiscal_year']==2023
assert report['metrics'][0]['status']=='CANDIDATE_READY'
assert all(hashlib.sha256((state/k).read_bytes()).hexdigest()==v for k,v in before.items()
           if 'results' in Path(k).parts or not k.startswith('updates/B01/periods/FY2023/'))
after=protect();repeat,report=invoke('repeat-forbidden-discovery-and-calculation',args,True)
assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not report['metrics'][0]['calculation_performed']
assert after==protect()
read,view=invoke('independent-results',['results','--company','macys','--state-root',str(state),'--output-root',str(base/'read')],True)
assert after==protect()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))
row=next(r for r in rows if r['metric_id']=='B01' and r['fiscal_year']=='2023')
assert (row['value'],row['unit'],row['period_start'],row['period_end'])==('23866000000','USD','2023-01-29','2024-02-03')
growth=next(r for r in rows if r['metric_id']=='B02' and r['fiscal_year']=='2023')
assert growth['value']=='' and growth['status']=='WITHHELD_KNOWN_DEFECT'
assert row['result_id']!=old_b01
newroot=Path(row['record_root']);assessment=json.loads((newroot/'input-assessments.json').read_text())
scope=assessment['assessments']['historical_statement']['selected_revenue_scope']
assert scope['method']=='SELECTED_REPORTED_CONSOLIDATED_REVENUE_V2' and scope['complete_scope_proven']
assert scope['selected_fiscal_column_year']==2023
record={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'first':first,'repeat':repeat,'read':read,'state_root':str(state),'source_root':source,'output_root':str(base),
        'selected_b01':row,'still_withheld_b02':growth,'rows':rows,'old_result_id':old_b01,
        'protected_old_files':before,'protected_final_files':after,'old_result_files_and_other_pointers_preserved':True,
        'repeat_discovery_factory_calculator_calls':0,'new_calls':[0,0,0]}
Path('work/reported-revenue-consumer/actual-company.json').write_text(json.dumps(record,indent=2)+'\n')
print([(r['name'],r['seconds']) for r in (first,repeat,read)])
