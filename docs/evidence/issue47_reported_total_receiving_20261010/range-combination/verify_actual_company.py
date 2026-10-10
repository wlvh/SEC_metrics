"""One affected saved-source coordinate through the combined public range entry."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/statement-pilot-macys-20261009/state');source=json.load((state/'company-task.json').open())['source_root'];base=Path(tempfile.mkdtemp(prefix='macys-range-reported-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
args=['run','--company','macys','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023','--metric','B01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes();protected={k:h for k,h in before.items() if '/results/' in k or '/shared-inputs/' in k or k=='company-task.json' or k.endswith('current-result.json') and '/B01/periods/FY2023/' not in k or k.endswith('completed-check.json') and '/B01/periods/FY2023/' not in k}
def invoke(name,arguments,forbid=False):
 code='import sys,json\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import company_fiscal_range as ranges,historical_statement_cases as cases,calculator\na=ranges.discover_fiscal_range.__code__;b=cases.prepare_historical_statement_year_case.__code__;c=calculator.calculate_metric.__code__\ndef guard(frame,event,arg):\n if event=="call" and (frame.f_code is a or frame.f_code is b or frame.f_code is c):raise AssertionError("Repeat/read must not discover or calculate")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No new network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(arguments)],capture_output=True,text=True);result={'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'arguments':arguments,'stdout':p.stdout,'stderr':p.stderr};(base/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(name,p.returncode,result['seconds'],flush=True);assert p.returncode==0 and not p.stderr,result;return result,json.loads(p.stdout)
first,report=invoke('one-related-source-policy-transition',args)
assert len(report['metrics'])==1 and report['metrics'][0]['calculation_performed']
assert all(hashes().get(k)==h for k,h in protected.items())
after=hashes();final={k:h for k,h in after.items() if '/results/' in k or '/shared-inputs/' in k or k.endswith('current-result.json') or k.endswith('completed-check.json') or k=='company-task.json'}
repeat,report=invoke('forbidden-range-and-calculation-repeat',args,True)
assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not report['metrics'][0]['calculation_performed']
assert all(hashes().get(k)==h for k,h in final.items())
read,view=invoke('independent-existing-results',['results','--company','macys','--state-root',str(state),'--output-root',str(base/'read')],True)
assert all(hashes().get(k)==h for k,h in final.items())
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));row=next(r for r in rows if r['metric_id']=='B01' and r['fiscal_year']=='2023');hold=next(r for r in rows if r['metric_id']=='B02' and r['fiscal_year']=='2023')
assert row['value']=='23866000000' and row['unit']=='USD' and row['period_start']=='2023-01-29' and row['period_end']=='2024-02-03'
assert row['result_id']=='sha256:77805235a0d19e2a7dde8d90850d96e555e92399f47a243b60ed3c4c98b2eeed'
assert not hold['value'] and hold['status']=='WITHHELD_KNOWN_DEFECT';assert len(rows)==22
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'first':first,'repeat':repeat,'read':read,'state_root':str(state),'output_root':str(base),'row':row,'B02_hold':hold,'rows':rows,'old_protected_files':protected,'final_protected_files':final,'old_result_files_preserved':True,'one_related_coordinate_only':True,'new_calls':[0,0,0]};Path('work/range-reported-combination/actual-company.json').write_text(json.dumps(receipt,indent=2)+'\n');print('correct total and 53-week dates preserved; B02 held; other saved coordinates intact',flush=True)
