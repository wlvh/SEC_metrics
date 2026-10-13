import csv,hashlib,io,json,socket,subprocess,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tools'),str(ROOT)]
from vnext_company import main
from vnext.continuous_call_ledger import recorded_ledger
from vnext.canonical import content_hash
from vnext import current_statement_metric_case
SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
ledger=recorded_ledger(root=OUT/'isolated-recorded-ledger',limits=(0,0,20))
with ledger.locked():ledger.snapshot()
context={'company_id':'marriott_international','metric_ids':['B04'],'ledger_root':str(ledger.root),'maximum_counts':[0,0,20],'execution_mode':'RECORDED_TEST_ONLY','purpose':'remaining_development_feasibility','requirement_id':'ordinary-online-b04-recorded-development','requirement_closure_hash':content_hash(value={'recorded':True}),'recorded_http_root':str(SOURCE)}
(OUT/'context.json').write_text(json.dumps(context,indent=2)+'\n')
args=['run','--company','marriott_international','--call-context',str(OUT/'context.json'),'--metric','B04','--work-dir',str(OUT/'task'),'--output-dir',str(OUT/'output'),'--max-sec-requests','20']
ops=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No live network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
 for name,forbid in [('first',False),('repeat-forbidden-factory',True)]:
  stream=io.StringIO();start=time.perf_counter()
  if forbid:
   with patch.object(current_statement_metric_case,'prepare_current_statement_metric_case',side_effect=AssertionError('No unchanged B04 calculation')),redirect_stdout(stream):code=main(args)
  else:
   with redirect_stdout(stream):code=main(args)
  report=json.loads(stream.getvalue());seconds=time.perf_counter()-start;(OUT/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
  ops.append({'phase':name,'exit_code':code,'seconds':seconds,'report':report});print(name,code,seconds,report.get('metrics'),report.get('discovery'),flush=True)
  metric=report['metrics'][0]
  if name=='first':
   if metric.get('status')!='CANDIDATE_READY':
    (OUT/'failure.json').write_text(json.dumps(ops,indent=2)+'\n');raise AssertionError('Actual source or producer gap; no fake answer')
   saved=Path(metric['result_root']);before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in saved.rglob('*') if p.is_file()}
  else:
   assert metric['status']=='NO_SOURCE_CONTENT_CHANGE' and not metric['calculation_performed']
   assert metric['result_id']==ops[0]['report']['metrics'][0]['result_id']
   assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in saved.rglob('*') if p.is_file()}
runner="""import sys,socket;from pathlib import Path;from unittest.mock import patch
r=Path(sys.argv[1]);sys.path[:0]=[str(r/'scripts'),str(r/'tools'),str(r)]
from vnext_company import main
from vnext import ordinary_current_update
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(ordinary_current_update,'run_once',side_effect=AssertionError('No reader update')):
 raise SystemExit(main(sys.argv[2:]))
"""
start=time.perf_counter();read=subprocess.run([sys.executable,'-c',runner,str(ROOT),'results','--company','marriott_international','--state-root',str(OUT/'task/company-state'),'--output-root',str(OUT/'independent-results')],capture_output=True,text=True,cwd='/private/tmp');seconds=time.perf_counter()-start
(OUT/'read.json').write_text(read.stdout);(OUT/'read.stderr').write_text(read.stderr);assert read.returncode==0,(read.returncode,read.stderr)
rows=list(csv.DictReader((OUT/'independent-results/metrics_matrix.csv').open()));assert len(rows)==1 and rows[0]['value']=='2601000000' and rows[0]['unit']=='USD' and rows[0]['fiscal_year']=='2025',rows
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in saved.rglob('*') if p.is_file()}
with ledger.locked():counts=ledger.snapshot()['counts']
summary={'base_main':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'code_state':'named uncommitted allowed explicit B04 / preserved default / CLI help changes','code_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/vnext/company_online.py','tools/vnext_company.py','tests/vnext/test_company_online.py']},'operations':ops,'read_seconds':seconds,'rows':rows,'result_files_preserved':len(before),'result_bytes':sum(Path(p).stat().st_size for p in before),'isolated_recorded_counts':counts,'new_real_calls':[0,0,0],'production_authorized':False,'external_boundary':'existing RecordedSecHttpClient only; all discovery/capture/selection/calculation/save/read real'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('PASS_ONLINE_B04',seconds,rows,counts,flush=True)
