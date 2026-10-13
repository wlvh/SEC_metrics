import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--state-root',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
args=parser.parse_args()
out=args.output_root.resolve();out.mkdir(exist_ok=False)
state=args.state_root.resolve()
source=Path(json.loads((state/'company-task.json').read_text())['source_root'])
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
initial=hashes(state);results={p:h for p,h in initial.items() if '/results/' in p}
code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_e01_company_case as h,historical_event_items as i,historical_ma_confirmation as m,calculator
blocked={h.prepare_historical_e01_year_case.__code__,i.content_confirmation_candidates.__code__,m.confirmation_request.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,calculator.withheld_metric_result.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('FACTORY_OR_CALCULATOR_FORBIDDEN_FOR_SAVED_INPUT_REUSE:'+frame.f_code.co_name)
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
'''
def invoke(name,args):
 t=time.perf_counter();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
 d={'arguments':args,'seconds':time.perf_counter()-t,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 (out/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(name,d['seconds'],d['exit'],flush=True)
 return d,json.loads(p.stdout) if p.stdout else None
read,r=invoke('read-before',['results','--company','pfizer','--state-root',str(state),'--output-root',str(out/'read-before')])
assert read['exit']==0 and initial==hashes(state)
rows=list(csv.DictReader((out/'read-before/metrics_matrix.csv').open()));assert len(rows)==1 and rows[0]['value']==''
repeat,d=invoke('repeat',['run','--company','pfizer','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2023','--metric','E01','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out/'run')])
after=hashes(state);assert results=={p:h for p,h in after.items() if '/results/' in p}
metric=d['metrics'][0] if d else None
assert metric['status']=='PREVIOUS_INPUT_WITHHELD' and not metric['calculation_performed'] and not metric['new_candidate_created']
assert metric['result_reason_code']=='E01_ITEM_METADATA_BODY_CONFLICT'
summary={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'read':{k:read[k] for k in ['seconds','exit']},'repeat':{k:repeat[k] for k in ['seconds','exit']},'metric':metric,'results_unchanged':len(results),'initial_state_files':len(initial),'after_state_files':len(after),'old_csv_row':rows[0]}
read_after,display=invoke('read-after',['results','--company','pfizer','--state-root',str(state),'--output-root',str(out/'read-after')])
assert read_after['exit']==0 and after==hashes(state)
final_rows=list(csv.DictReader((out/'read-after/metrics_matrix.csv').open()));assert len(final_rows)==1 and final_rows[0]['status']=='WITHHELD' and final_rows[0]['result_id']==metric['result_id']
summary['read_after']={k:read_after[k] for k in ('seconds','exit')};summary['restored_csv_row']=final_rows[0]
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'metric':metric,'results_unchanged':len(results)}))
