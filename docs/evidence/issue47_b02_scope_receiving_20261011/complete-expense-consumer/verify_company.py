import argparse,csv,hashlib,io,json,socket,time,sys
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
p=argparse.ArgumentParser();p.add_argument('phase',choices=['migration','repeat','read']);a=p.parse_args();state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/partiii-paramount-income-20261011-47/state');out=state.parent/('complete-expense-'+a.phase+'-'+str(time.time_ns()));source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
def snapshot():return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
before=snapshot();protected={k:v for k,v in before.items() if '/results/' in k};args=['results','--company','paramount_skydance_paramount_global','--state-root',str(state),'--output-root',str(out)] if a.phase=='read' else ['run','--company','paramount_skydance_paramount_global','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','B02','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out)]
from vnext import historical_statement_cases,calculator,historical_paired_revenue,company_fiscal_range
blocked={historical_statement_cases.prepare_historical_statement_year_case.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__,historical_paired_revenue.revenue_claims_admitted_by_original.__code__,company_fiscal_range.discover_fiscal_range.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('Unchanged repeat/read must not prepare/compute')
stdout=io.StringIO();t=time.monotonic()
if a.phase!='migration':sys.setprofile(guard)
try:
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',stdout):code=main(args)
finally:sys.setprofile(None)
elapsed=time.monotonic()-t;Path('work/complete-cost-revenue/'+a.phase+'-company.stdout.log').write_text(stdout.getvalue());result=json.loads(stdout.getvalue());output=Path(result['output_root']);rows=list(csv.DictReader((output/'metrics_matrix.csv').open()));after=snapshot();assert all(after.get(k)==v for k,v in protected.items());expected={'B01':'29213000000','B03':'-0.1669462225721425392804573306'}
for r in rows:
 if r['metric_id'] in expected:assert r['value']==expected[r['metric_id']]
 if r['metric_id']=='B02':assert r['value']=='-0.01480507217051126399568325914',r
if a.phase=='read':assert before==after
if a.phase=='repeat':assert protected=={k:v for k,v in after.items() if '/results/' in k};assert not result['metrics'][0]['calculation_performed']
d={'phase':a.phase,'seconds':elapsed,'exit_code':code,'arguments':args,'metrics':result.get('metrics'),'rows':rows,'old_result_files_protected':len(protected),'state_files':len(after),'read_state_unchanged':a.phase=='read' and before==after,'new_calls':0};Path('work/complete-cost-revenue/'+a.phase+'-company.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));Path('work/complete-cost-revenue/'+a.phase+'-company.stdout.log').write_text(stdout.getvalue());print(json.dumps({'phase':a.phase,'seconds':elapsed,'exit':code,'rows':[{k:r[k] for k in ['metric_id','value','fiscal_year','result_id','local_metric_status']} for r in rows]},indent=2))
