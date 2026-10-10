"""One repaired paired-revenue coordinate using existing saved originals."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from decimal import Decimal,localcontext
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/pfizer-statements-company-nvw2pcdt/state');source=json.load((state/'company-task.json').open())['source_root'];base=Path(tempfile.mkdtemp(prefix='pfizer-paired-revenue-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def protect():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or '/shared-inputs/' in str(p) or p.name in {'company-task.json','current-result.json','completed-check.json'})}
before=protect();unchanged={k:v for k,v in before.items() if '/B02/periods/FY2023/' not in k or '/results/' in k}
args=['run','--company','pfizer','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023','--metric','B02','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
def invoke(name,args,forbid=False):
 code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_statement_cases as case,company_fiscal_range as ranges,calculator\na=case.prepare_historical_statement_year_case.__code__;b=ranges.discover_fiscal_range.__code__;c=calculator.calculate_metric.__code__\ndef guard(frame,event,arg):\n if event=="call" and (frame.f_code is a or frame.f_code is b or frame.f_code is c):raise AssertionError("Stable growth must not recalculate")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No new network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':args};(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,p.returncode,r['seconds'],flush=True);assert p.returncode==0 and not p.stderr,r;return r,json.loads(p.stdout)
first,report=invoke('one-FY2023-growth-source-transition',args);assert len(report['metrics'])==1 and report['metrics'][0]['calculation_performed'];assert all(protect().get(k)==v for k,v in unchanged.items())
root=Path(report['metrics'][0]['result_root']);assessment=json.load((root/'input-assessments.json').open())['assessments']['historical_statement'];scopes=assessment['paired_revenue_scopes'];assert set(scopes)=={'current','prior'} and all(s['complete_scope_proven'] for s in scopes.values())
records=[json.loads(l) for l in (root/'records.jsonl').read_text().splitlines()];claims=[r for r in records if r['record_type']=='DETERMINISTIC_VERIFIED_CLAIM'];assert len(claims)==2 and {c['value'] for c in claims}=={'58496000000','100330000000'};assert {c['locator']['concept'] for c in claims}=={'Revenues'}
after=protect();repeat,report=invoke('repeat-no-range-case-or-calculation',args,True);assert report['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not report['metrics'][0]['calculation_performed'];assert after==protect()
read,view=invoke('independent-old-and-new-results',['results','--company','pfizer','--state-root',str(state),'--output-root',str(base/'read')],True);assert after==protect();rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));row=next(r for r in rows if r['metric_id']=='B02' and r['fiscal_year']=='2023')
with localcontext() as context:
 context.prec=28;expected=(Decimal(58496)-Decimal(100330))/Decimal(100330)
assert Decimal(row['value'])==expected and row['unit']=='ratio' and row['period_start']=='2023-01-01' and row['period_end']=='2023-12-31'
assert len(rows)==25 and next(r for r in rows if r['metric_id']=='B02' and r['fiscal_year']=='2024')['value']==''
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'first':first,'repeat':repeat,'read':read,'state_root':str(state),'output_root':str(base),'row':row,'rows':rows,'claims':claims,'scope_summaries':{role:{k:s[k] for k in ('scope_id','status','complete_scope_proven')} for role,s in scopes.items()},'old_protected_files':before,'unchanged_old_files':unchanged,'final_protected_files':after,'new_calls':[0,0,0],'reference_amounts_only_after_calculation':True};Path('work/paired-revenue-consumer/actual-company.json').write_text(json.dumps(receipt,indent=2)+'\n');print('Complete original revenues selected, exact claim identities retained, old mismatches still withheld',flush=True)
