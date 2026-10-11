"""One real historical B02 consumer, with explicit no-call/recompute guards."""
import argparse,contextlib,csv,hashlib,io,json,socket,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('phase',choices=['first','repeat','read']);p.add_argument('--task-root',type=Path,required=True);a=p.parse_args()
source=a.source_root;task=a.task_root;state=task/'state';task.mkdir(parents=True,exist_ok=True)
def hashes(root):return {str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob('*') if x.is_file()} if root.exists() else {}
before=hashes(state);immutable_before={k:v for k,v in before.items() if '/results/' in k or k.endswith('result.json')}
args=(['results','--company','marriott_international','--state-root',str(state),'--output-root',str(task/'independent-read')]
      if a.phase=='read' else ['run','--company','marriott_international','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--metric','B02','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(task/'runs')])
out=io.StringIO();err=io.StringIO();t=time.monotonic()
with contextlib.ExitStack() as stack:
 stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('No real network permitted')))
 if a.phase in {'repeat','read'}:
  stack.enter_context(patch('vnext.historical_statement_cases.prepare_historical_statement_year_case',side_effect=AssertionError('Unchanged input must not recalculate')))
  stack.enter_context(patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No Calculator during repeat/read')))
  stack.enter_context(patch('vnext.company_fiscal_range.discover_fiscal_range',side_effect=AssertionError('No discovery during repeat/read')))
 with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
  try:code=main(args)
  except Exception as e:code=1;err.write(type(e).__name__+':'+str(e))
elapsed=time.monotonic()-t;after=hashes(state);immutable_after={k:v for k,v in after.items() if '/results/' in k or k.endswith('result.json')}
(task/(a.phase+'.stdout.log')).write_text(out.getvalue());(task/(a.phase+'.stderr.log')).write_text(err.getvalue())
result=json.loads(out.getvalue()) if out.getvalue().strip() else {};output=Path(result.get('output_root',task/'independent-read'))
rows=list(csv.DictReader((output/'metrics_matrix.csv').open())) if (output/'metrics_matrix.csv').exists() else []
summary={'phase':a.phase,'arguments':args,'exit_code':code,'elapsed_seconds':elapsed,'result':result,'rows':rows,'state_files_before':len(before),'state_files_after':len(after),'immutable_results_preserved':all(immutable_after.get(k)==v for k,v in immutable_before.items()),'new_immutable_result_paths':sorted(set(immutable_after)-set(immutable_before)),'new_sec_calls':0,'new_provider_calls':0}
(task/(a.phase+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2))
assert rows and len(rows)==1,summary
assert rows[0]['metric_id']=='B02' and rows[0]['fiscal_year']=='2021',summary
assert not rows[0]['value'],summary
if a.phase=='repeat':
 assert immutable_before==immutable_after,summary
 assert all(not m.get('calculation_performed',False) for m in result['metrics']),summary
if a.phase=='read':assert before==after,summary
print(json.dumps({'phase':a.phase,'exit_code':code,'elapsed_seconds':elapsed,'rows':[{k:r[k] for k in ['metric_id','value','fiscal_year','local_metric_status','result_id']} for r in rows],'state_files':len(after),'new_results':len(summary['new_immutable_result_paths'])},indent=2))
