import csv,hashlib,json,subprocess,sys,tempfile,time
from decimal import Decimal
import argparse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args()
base=args.output_root.resolve();base.mkdir(parents=True,exist_ok=False)
state=base/'state';source=Path.cwd()
args=['run','--company','enphase_energy','--metric','B06','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(base/'runs')]
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
records=[]
def invoke(name,argv,forbid=False):
 code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import current_b06_case as b,calculator\nblocked={b.prepare_current_b06_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code in blocked:raise AssertionError("No preparation/calculation on unchanged input or read")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No true network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 t=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(argv)],capture_output=True,text=True);r={'name':name,'seconds':time.monotonic()-t,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':argv};(base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');records.append(r);print(name,round(r['seconds'],3),p.returncode,flush=True);assert not p.stderr and p.returncode in (0,2),r;return json.loads(p.stdout)
a=invoke('fresh-current',args);m=a['metrics'][0];assert m['status']=='CANDIDATE_READY' and m['calculation_performed'],m
protected={p:h for p,h in hashes().items() if '/results/' in p or '/shared-inputs/' in p or p.endswith(('current-result.json','completed-check.json')) or p=='company-task.json'}
b=invoke('repeat-current',args,True);assert not b['metrics'][0]['calculation_performed'] and not b['metrics'][0]['new_candidate_created']
assert all(hashes().get(p)==h for p,h in protected.items());before=hashes()
invoke('read-current',['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(base/'read')],True);assert before==hashes()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));assert len(rows)==1
row=rows[0];assert Decimal(row['value'])==Decimal('1204377000')/Decimal('1087023000') and row['unit']=='ratio' and row['period_start']==row['period_end']=='2025-12-31',row
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'state_root':str(state),'records':records,'rows':rows,'protected_files':protected,'read_state_files_unchanged':len(before),'new_calls':[0,0,0]}
(base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('original current ratio and instant period preserved; reuse/read do not calculate',flush=True)
