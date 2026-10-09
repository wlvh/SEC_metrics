"""Actual CLI refusal and existing historical-state reuse, with no calls."""
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/bank-performance-jpm-20261009/state')
source=json.loads((state/'company-task.json').read_text())['source_root']
out=Path(tempfile.mkdtemp(prefix='historical-period-entry-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
def hashes():
 return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ('current-result.json','completed-check.json'))}
old=hashes();ops=[]
def invoke(name,args,rc):
 code='import sys,json;from unittest.mock import patch;from tools.vnext_company import main\nfrom vnext import historical_statement_cases as cases\na=cases.prepare_historical_statement_year_case.__code__;b=cases._filing_source.__code__;c=cases._deterministic_metric_graph.__code__\ndef guard(frame,event,arg):\n if event=="call" and (frame.f_code is a or frame.f_code is b or frame.f_code is c):raise AssertionError("No saved-year recomputation")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No network")),patch("vnext.company_online.run_online_company",side_effect=AssertionError("No online state/ledger/capture")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 started=time.monotonic();p=subprocess.run([sys.executable,'-c',code,json.dumps(args)],text=True,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'scripts:tools:.'})
 (out/(name+'.stdout')).write_text(p.stdout);(out/(name+'.stderr')).write_text(p.stderr)
 ops.append({'name':name,'seconds':time.monotonic()-started,'exit_code':p.returncode,'stderr':p.stderr,'stdout':p.stdout});assert p.returncode==rc,(p.stdout,p.stderr)
 return json.loads(p.stdout) if rc==0 else None
bad_base=['run','--company','jpmorgan_chase','--metric','B01','--call-context',str(out/'context-does-not-exist.json'),'--work-dir',str(out/'must-not-create-state'),'--output-dir',str(out/'must-not-create-output')]
for name,extra in [('history-online',['--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2025']),('latest-with-start',['--fiscal-year-start','2021']),('latest-with-end',['--fiscal-year-end','2025'])]:
 invoke(name,bad_base+extra,2)
 assert not(out/'must-not-create-state').exists() and not(out/'must-not-create-output').exists()
args=['run','--company','jpmorgan_chase','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--metric','B01','--source-root',source,'--work-dir',str(state),'--output-dir',str(out/'run')]
v=invoke('saved-history-unchanged',args,0);assert v['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not v['metrics'][0]['calculation_performed'],v
invoke('independent-read',['results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(out/'read')],0)
assert hashes()==old
record={'constructed_refusal_controls':True,'actual_existing_saved_state_reused':True,'base_main':'f6ef7886','code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_root':source,'state_root':str(state),'output_root':str(out),'protected_old_files':len(old),'all_old_files_preserved':True,'factory_amount_and_graph_calls':0,'invalid_state_or_output_created':False,'ledger_or_network_access':False,'new_calls':[0,0,0],'operations':ops}
Path('docs/evidence/issue47_history_online_period_20261010/actual-consumer.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['code_commit','protected_old_files','all_old_files_preserved']},indent=2))
