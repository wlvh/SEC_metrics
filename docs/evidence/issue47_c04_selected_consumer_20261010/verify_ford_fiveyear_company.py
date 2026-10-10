"""Continue Ford selected C04 years with the unchanged public/historical implementation."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
old=json.loads(Path('work/auditor-company/actual-company.json').read_text());state=Path(old['state_root']);source=old['row']['source_root'];base=Path(tempfile.mkdtemp(prefix='ford-c04-fiveyear-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def snapshot():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ['company-task.json','current-result.json','completed-check.json'])}
before=snapshot();source_log=Path(source)/'evidence/requests_log.csv';source_hash=hashlib.sha256(source_log.read_bytes()).hexdigest()
args=['run','--company','ford_motor_company','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2025','--metric','C04','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
def invoke(name,args,guard_all=False):
 code='import sys,json\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\nfrom vnext import historical_auditor_case as cases,calculator\n'
 code+='a=cases.prepare_historical_auditor_year_case.__code__;calcs={calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}\ndef guard(frame,event,arg):\n if event=="call" and ((frame.f_code is a and ('+('True' if guard_all else 'frame.f_locals.get("fiscal_year")==2022')+'))'+(' or frame.f_code in calcs' if guard_all else '')+'):raise AssertionError("Unchanged C04 must not compute")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No new network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-t,'exit_code':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr};(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,p.returncode,round(r['seconds'],3),flush=True);assert p.returncode in [0,2] and not p.stderr,r;return r,json.loads(p.stdout)
first,report=invoke('fiveyear-add-four-periods',args);assert len(report['metrics'])==5;original=next(m for m in report['metrics'] if m['requested_fiscal_year']==2022);assert original['status']=='NO_SOURCE_CONTENT_CHANGE' and not original['calculation_performed'] and original['result_id']==old['row']['result_id'];assert all(snapshot().get(k)==h for k,h in before.items());post=snapshot();completed=[m['requested_fiscal_year'] for m in report['metrics'] if m['status'] in ['CANDIDATE_READY','CANDIDATE_WITHHELD','NO_SOURCE_CONTENT_CHANGE','PREVIOUS_INPUT_WITHHELD']]
# Failed input preparation is not a completed business withholding; do not call it stable reuse.
groups=[]
for y in completed:
 if groups and y==groups[-1][-1]+1:groups[-1].append(y)
 else:groups.append([y])
repeats=[]
for i,g in enumerate(groups):
 a=args.copy();a[a.index('--fiscal-year-start')+1]=str(g[0]);a[a.index('--fiscal-year-end')+1]=str(g[-1]);r,rep=invoke('forbidden-repeat-'+str(i),a,True);assert not any(m.get('calculation_performed') for m in rep['metrics']);assert all(m['status'] in ['NO_SOURCE_CONTENT_CHANGE','PREVIOUS_INPUT_WITHHELD'] for m in rep['metrics']);assert snapshot()==post;repeats.append(r)
read,view=invoke('independent-all-results',['results','--company','ford_motor_company','--state-root',str(state),'--output-root',str(base/'read')],True);assert read['exit_code']==0 and snapshot()==post;assert hashlib.sha256(source_log.read_bytes()).hexdigest()==source_hash
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));selected=[r for r in rows if r['metric_id']=='C04' and r['fiscal_year'] in ['2021','2022','2023','2024','2025']];assert len(selected)==5
checks=[]
for row in selected:
 if not row.get('record_root'):continue
 root=Path(row['record_root']);assess=json.loads((root/'input-assessments.json').read_text())['assessments']['historical_auditor'];checks.append({'fiscal_year':row['fiscal_year'],'row':row,'assessment':assess})
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'first':first,'repeat':repeats,'read':read,'metrics':report['metrics'],'rows':selected,'assessment_checks':checks,'state_root':str(state),'output_root':str(base),'old_protected_files':len(before),'final_protected_files':len(post),'FY2022_case_calls':0,'new_calls':[0,0,0],'unchanged_source_log':True,'business_acceptance':'not asserted from calculation alone'};Path('work/c04-fiveyear/actual-company.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS company five-year consumer status, old FY22 unchanged, completed-only forbidden reuse and independent CSV',flush=True)
