import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--state-root',required=True,type=Path)
parser.add_argument('--saved-legal-reviews',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
args=parser.parse_args()
out=args.output_root.resolve();out.mkdir(exist_ok=False)
state=args.state_root.resolve()
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
original=hashes()
from vnext.ordinary_saved_result import read_saved_result
saved=[]
for p in state.rglob('manifest.json'):
 if '/results/' in str(p):
  r=read_saved_result(output_root=p.parent)
  saved.append(r['result'])
code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import calculator,historical_d02_case as d,historical_statement_cases as s,historical_risk_heading_case as r
blocked={calculator.calculate_metric.__code__,calculator.calculate_text_metric.__code__,calculator.calculate_observation_metric.__code__,calculator.withheld_metric_result.__code__,d.prepare_historical_legal_sources.__code__,d.finish_historical_legal_case.__code__,s.prepare_historical_statement_year_case.__code__,r.prepare_historical_risk_heading_year_case.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('READ_OR_INVALID_SCOPE_CANNOT_CALCULATE:'+frame.f_code.co_name)
sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
'''
def invoke(name,args):
 t=time.perf_counter();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
 d={'arguments':args,'seconds':time.perf_counter()-t,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr};(out/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(name,d['seconds'],d['exit'],flush=True);return d
read=invoke('read',['results','--company','ford_motor_company','--state-root',str(state),'--output-root',str(out/'read')])
assert read['exit']==0 and original==hashes()
rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open()))
indexed={r['result_id']:r for r in saved}
assert all(row.get('result_id') in indexed for row in rows)
for row in rows:
 if row.get('result_id') in indexed:
  r=indexed[row['result_id']]
  assert row['metric_id']==r['metric_id'] and row['period_start']==r['period_start'] and row['period_end']==r['period_end']
  assert row['unit']==(r['unit'] or '') and row['value']==('' if r['value'] is None else str(r['value']))
source=json.loads((state/'company-task.json').read_text())['source_root']
answer=str(args.saved_legal_reviews.resolve())
invalid=invoke('invalid-mixed',['run','--company','ford_motor_company','--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','D02','--metric','BOGUS','--source-root',source,'--saved-legal-reviews',answer,'--work-dir',str(state),'--output-dir',str(out/'invalid')])
assert invalid['exit']!=0 and original==hashes()
summary={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'read':{k:read[k] for k in ['exit','seconds']},'invalid_mixed':{k:invalid[k] for k in ['exit','seconds','stderr','stdout']},'old_record_count':len(saved),'rows':rows,'old_state_files_unchanged':len(original),'new_calls':[0,0,0]}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'old_records':len(saved),'csv_rows':len(rows),'state_files':len(original)}))
