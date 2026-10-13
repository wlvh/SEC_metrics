import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--state-root',required=True,type=Path)
parser.add_argument('--original-call-root',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
args=parser.parse_args()
out=args.output_root.resolve();out.mkdir(exist_ok=False)
state=args.state_root.resolve()
source=Path(json.loads((state/'company-task.json').read_text())['source_root'])
answers=out/'bad-answers/call0009';answers.mkdir(parents=True)
original=args.original_call_root.resolve()/'semantic-request.json'
(answers/'semantic-request.json').write_bytes(original.read_bytes())
def hashes():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=hashes();oldresults={p:h for p,h in before.items() if '/results/' in p}
code='''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import calculator,historical_statement_cases as s,historical_d02_case as d
blocked={calculator.calculate_metric.__code__,calculator.calculate_text_metric.__code__,calculator.calculate_observation_metric.__code__,calculator.withheld_metric_result.__code__,s.prepare_historical_statement_year_case.__code__,d.prepare_historical_legal_sources.__code__,d.finish_historical_legal_case.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('REPEAT_OR_READ_CANNOT_PROCESS:'+frame.f_code.co_name)
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
'''
def invoke(name,args,guard):
 t=time.perf_counter();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args),'1' if guard else '0'],capture_output=True,text=True)
 d={'arguments':args,'seconds':time.perf_counter()-t,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr};(out/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(name,d['seconds'],d['exit'],flush=True)
 assert p.returncode in (0,2) and not p.stderr,(name,d)
 return d,json.loads(p.stdout)
args=['run','--company','ford_motor_company','--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','D02','--metric','B04','--source-root',str(source),'--saved-legal-reviews',str(out/'bad-answers'),'--work-dir',str(state),'--output-dir',str(out/'runs')]
first,d=invoke('first',args,False)
metrics={m['metric_id']:m for m in d['metrics']};assert metrics['D02']['status']=='INPUT_OR_EXECUTION_FAILED';assert metrics['B04']['result_reason_code']=='PASS',metrics
b04=metrics['B04'];assert oldresults=={p:hashes()[p] for p in oldresults};after=hashes()
repeat,r=invoke('repeat',args,True)
again={m['metric_id']:m for m in r['metrics']};assert again['B04']['result_id']==b04['result_id'] and not again['B04']['calculation_performed'];assert again['D02']['status']=='INPUT_OR_EXECUTION_FAILED'
pre_read=hashes();read,v=invoke('read',['results','--company','ford_motor_company','--state-root',str(state),'--output-root',str(out/'read')],True);assert pre_read==hashes()
rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open()));selected=[r for r in rows if r['fiscal_year']=='2025' and r['metric_id'] in ('B04','D02')]
assert len(selected)==2
assert next(r for r in selected if r['metric_id']=='B04')['value']=='-8162000000'
assert next(r for r in selected if r['metric_id']=='D02')['value']==''
summary={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'phases':{n:{k:x[k] for k in ('exit','seconds')} for n,x in [('first',first),('repeat',repeat),('read',read)]},'metrics':metrics,'repeat_metrics':again,'selected_csv_rows':selected,'all_csv_rows':len(rows),'old_result_files_unchanged':len(oldresults),'state_files_before':len(before),'state_files_after':len(hashes()),'new_calls':[0,0,0],'constructed_package':'Only the existing request member copied read-only; terminal deliberately missing'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'old_result_files':len(oldresults),'csv_rows':len(rows),'B04':selected[0]['value']}))
