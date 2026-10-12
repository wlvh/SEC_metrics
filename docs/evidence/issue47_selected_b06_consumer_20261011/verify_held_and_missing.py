import argparse,csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args()
source=args.source_root.resolve();base=args.output_root.resolve();base.mkdir(parents=True,exist_ok=False);state=base/'state';records=[]
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
def invoke(name,args,forbid=False):
 code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_b06_case as h,current_b06_case as b,calculator\nblocked={h.prepare_selected_debt_sources.__code__,b.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code in blocked:raise AssertionError("Stable result must not process")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-t,'exit':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr};records.append(r);(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,round(r['seconds'],3),p.returncode,flush=True);assert not p.stderr and p.returncode in (0,2),r;return json.loads(p.stdout)
args=['run','--company','macys','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(base/'runs')]
a=invoke('macys2024-first',args);assert a['metrics'][0]['status']=='CANDIDATE_WITHHELD',a
protected={p:h for p,h in hashes().items() if '/results/' in p or '/shared-inputs/' in p or p.endswith(('current-result.json','completed-check.json')) or p=='company-task.json'}
a=invoke('macys2024-repeat',args,True);assert a['metrics'][0]['status']=='PREVIOUS_INPUT_WITHHELD' and not a['metrics'][0]['calculation_performed'];assert all(hashes().get(p)==h for p,h in protected.items())
missing=list(args);missing[missing.index('--fiscal-year-start')+1]='2027';missing[missing.index('--fiscal-year-end')+1]='2027';a=invoke('missing-year',missing)
assert a['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED' and a['metrics'][0]['error_category']=='SOURCE_UNAVAILABLE',a
assert all(hashes().get(p)==h for p,h in protected.items());before=hashes()
invoke('independent-read',['results','--company','macys','--state-root',str(state),'--output-root',str(base/'read')],True);assert before==hashes()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));assert len(rows)==2
r=next(x for x in rows if x['fiscal_year']=='2024');assert not r['value'] and r['status']=='WITHHELD' and r['period_end']=='2025-02-01',r
missing=next(x for x in rows if x['fiscal_year']=='2027');assert not missing['value'] and 'SOURCE_UNAVAILABLE' in missing['notes'],missing
(base/'receipt.json').write_text(json.dumps({'code_commit':'2baffef0','state_root':str(state),'records':records,'rows':rows,'protected':protected,'read_state_files_unchanged':len(before),'new_calls':[0,0,0]},indent=2)+'\n');print('real stable withholding and missing year remain separate; saved result retained',flush=True)
