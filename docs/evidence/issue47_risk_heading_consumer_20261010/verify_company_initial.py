import csv,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/liquidity-marriott-20261009/state');source=json.loads((state/'company-task.json').read_text())['source_root'];out=Path(tempfile.mkdtemp(prefix='marriott-d01-company-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'));ops=[]
ref=json.loads(Path('docs/evidence/issue47_risk_heading_consumer_20261010/existing-marriott-reference.json').read_text())
def protect():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
old=protect()
def invoke(name,args,forbid=False):
 code='import sys,json;from unittest.mock import patch;from tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_risk_heading_case as case\na=case.prepare_historical_risk_heading_year_case.__code__\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code is a:raise AssertionError("No unchanged D01 preparation or calculation")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([sys.executable,'-c',code,json.dumps(args)],capture_output=True,text=True,env={**os.environ,'PYTHONPATH':'scripts:tools:.','PYTHONDONTWRITEBYTECODE':'1'});(out/(name+'.stdout')).write_text(p.stdout);(out/(name+'.stderr')).write_text(p.stderr);value=json.loads(p.stdout);ops.append({'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'status':value.get('status')});Path('work/d01-consumer/progress.json').write_text(json.dumps({'output_root':str(out),'operations':ops},indent=2)+'\n');print(ops[-1],flush=True);assert p.returncode==0,(p.stdout,p.stderr);return value
args=['run','--company','marriott_international','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2025','--metric','D01','--source-root',source,'--work-dir',str(state),'--output-dir',str(out/'runs')]
v=invoke('first-five-d01',args);assert len(v['metrics'])==5 and all(m['status']=='CANDIDATE_READY' for m in v['metrics']);assert all(hashlib.sha256((state/n).read_bytes()).hexdigest()==s for n,s in old.items());before=protect()
v=invoke('repeat-forbid-d01-factory',args,True);assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in v['metrics']);assert before==protect();invoke('independent-results',['results','--company','marriott_international','--state-root',str(state),'--output-root',str(out/'read')],True);assert before==protect()
rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open()));comp=[]
for r in rows:
 if r['metric_id']!='D01':continue
 expected=ref[r['period_end']];assert r['value'].split('\n')==expected['reference_headings'];assert r['unit']=='text' and r['status']=='TEXT_QUAL';assert r['accession']==expected['accession'];assert r['result_id']==expected['previous_result_id'],(r['fiscal_year'],r['result_id'],expected['previous_result_id']);comp.append({k:r[k] for k in ['metric_id','fiscal_year','unit','status','period_start','period_end','accession','result_id']})
assert len(comp)==5
Path('docs/evidence/issue47_risk_heading_consumer_20261010/actual-company.json').write_text(json.dumps({'base_main':'f6ef7886','public_commit':'656a1d3c91a7599cab5127049b4b7f26f608d2fe','tested_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_tree_modified_files':['scripts/vnext/historical_risk_heading_case.py'],'source_root':source,'state_root':str(state),'output_root':str(out),'operations':ops,'comparisons':comp,'old_files':len(old),'all_files':len(before),'old_files_preserved':True,'repeat_factory_calls':0,'new_calls':[0,0,0]},indent=2)+'\n')
