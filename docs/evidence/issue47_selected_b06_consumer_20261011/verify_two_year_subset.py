import argparse,csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--state-root',type=Path,required=True);parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output-root',type=Path,required=True);options=parser.parse_args()
state=options.state_root.resolve();source=options.source_root.resolve();base=options.output_root.resolve();base.mkdir(parents=True,exist_ok=False)
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes();protected={p:h for p,h in before.items() if p.startswith('updates/B06/periods/FY2024/') and ('/results/' in p or p.endswith(('current-result.json','completed-check.json')))}
args=['run','--company','enphase_energy','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2025','--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(base/'runs')];records=[]
def invoke(name,argv,allow_new=False):
 code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_b06_case as h,current_b06_case as b,calculator
count=[]
def guard(frame,event,arg):
 if event!="call":return
 if frame.f_code is h.prepare_historical_b06_year_case.__code__:
  year=frame.f_locals["fiscal_year"];count.append(year)
  if year!=2025 or not ALLOW:raise AssertionError("Only new FY2025 may process")
 elif not ALLOW and frame.f_code in {h.prepare_selected_debt_sources.__code__,b.prepare_selected_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}:
  raise AssertionError("Stable subset/read cannot prepare or calculate")
sys.setprofile(guard)
with patch("socket.socket.connect",side_effect=AssertionError("No true network")):
 code=main(json.loads(sys.argv[1]))
assert count==([2025] if ALLOW else []),count
raise SystemExit(code)
'''.replace('ALLOW','True' if allow_new else 'False')
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(argv)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-t,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':argv};records.append(r);(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,round(r['seconds'],3),p.returncode,flush=True);assert p.returncode==0 and not p.stderr,r;return json.loads(p.stdout)
a=invoke('add-one-adjacent-year',args,True);assert [(m['requested_fiscal_year'],m['calculation_performed']) for m in a['metrics']]==[(2024,False),(2025,True)]
assert all(hashes().get(p)==h for p,h in protected.items())
subset=list(args);subset[subset.index('--fiscal-year-start')+1]='2025';a=invoke('subset-2025-repeat',subset);assert not a['metrics'][0]['calculation_performed']
read_before=hashes();invoke('read-two-years',['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(base/'read')]);assert read_before==hashes()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));assert len(rows)==2
assert {r['fiscal_year']:r['value'] for r in rows}=={'2024':'1.563451362278755750189672227','2025':'1.107959077222837051285943352'}
assert {r['fiscal_year']:r['period_end'] for r in rows}=={'2024':'2024-12-31','2025':'2025-12-31'}
(base/'receipt.json').write_text(json.dumps({'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'records':records,'rows':rows,'FY2024_protected_files':protected,'state_files_unchanged_on_read':len(read_before),'new_calls':[0,0,0]},indent=2)+'\n');print('only new year computed; subset repeat and both original dates/values retained',flush=True)
