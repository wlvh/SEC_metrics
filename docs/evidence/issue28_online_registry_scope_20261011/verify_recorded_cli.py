"""Actual online CLI with existing saved SEC replies and a new isolated recorded ledger."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from vnext.continuous_call_ledger import recorded_ledger
from vnext.canonical import content_hash
from tools.vnext_company import main
from sec_http import parse_request_log_rows
ROOT=Path.cwd();ORIGIN=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/company-online-recorded-no-network-20261009/task/sources');E=Path(__file__).parent
STATE=Path(tempfile.mkdtemp(prefix='issue28-online-registry-'))
ledger=recorded_ledger(root=STATE/'recorded-ledger',limits=(0,0,20))
with ledger.locked():ledger.snapshot()
ctx={'company_id':'marriott_international','metric_ids':['B01'],'recorded_http_root':str(ORIGIN),'ledger_root':str(ledger.root),'maximum_counts':[0,0,20],'execution_mode':'RECORDED_TEST_ONLY','purpose':'remaining_development_feasibility','requirement_id':'ordinary-company-capture-v1','requirement_closure_hash':content_hash(value={'recorded':True})}
context=STATE/'context.json';context.write_text(json.dumps(ctx))
args=['run','--company','marriott_international','--work-dir',str(STATE/'task'),'--output-dir',str(STATE/'out'),'--call-context',str(context),'--metric','B01','--max-sec-requests','10']
def snap(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
def run(forbid=False):
 output=io.StringIO();start=time.perf_counter()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch('sys.stdout',output):
  if forbid:
   with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No repeat calculation')),patch('vnext.ordinary_current_update.save_calculated_case',side_effect=AssertionError('No repeat result write')):code=main(args)
  else:code=main(args)
 value=json.loads(output.getvalue());return code,value,time.perf_counter()-start
start_origin=snap(ORIGIN);first_code,first,first_seconds=run();assert first_code==0,(first_code,first)
assert first['status']=='FLOW_COMPLETED',first
row=list(csv.DictReader((Path(first['output_root'])/'metrics_matrix.csv').open()))[0]
assert row['value']=='26186000000' and row['unit']=='USD' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
source=STATE/'task/sources';registry=source/'config/company_registry.csv'
registry.write_bytes(registry.read_bytes().replace(b'pfizer,Pfizer,',b'pfizer,Pfizer unrelated display,'))
immutable_paths={r['repo_relative_path'] for r in parse_request_log_rows(text=(source/'evidence/requests_log.csv').read_text()) if '/Archives/' in r['source_url'] and r['status_code']=='200'}
immutable_before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in immutable_paths}
result_before=snap(STATE/'task/company-state/updates/B01/results')
with ledger.locked():count_before=ledger.snapshot()['counts']
repeat_code,repeat,repeat_seconds=run(True);assert repeat_code==0 and repeat['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE',repeat
assert repeat['metrics'][0]['result_id']==first['metrics'][0]['result_id']
assert result_before==snap(STATE/'task/company-state/updates/B01/results')
assert immutable_before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in immutable_paths}
with ledger.locked():count_after=ledger.snapshot()['counts']
# Online discovery intentionally refreshes submissions and CompanyFacts;
# originals are reused, and no business model calls are possible.
assert count_after[2]-count_before[2]==2,(count_before,count_after)
before_read=snap(STATE/'task/company-state');start=time.perf_counter()
code='import runpy,socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network")); sys.argv='+repr(['tools/vnext_company.py','results','--company','marriott_international','--state-root',str(STATE/'task/company-state'),'--output-root',str(STATE/'read')])+'; runpy.run_path("tools/vnext_company.py",run_name="__main__")'
read=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start;assert read.returncode==0,read.stderr;assert before_read==snap(STATE/'task/company-state')
assert snap(ORIGIN)==start_origin
report={'code_root':str(ROOT),'source_replies_root':str(ORIGIN),'new_test_state':str(STATE),'args':args,'first':first,'repeat':repeat,'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'csv':row,'recorded_counts_before_resume':count_before,'recorded_counts_after_resume':count_after,'original_source_responses_unchanged':True,'same_results_no_repeat_factory':True,'independent_read_state_unchanged':True,'new_calls':{'sec':0,'provider':0,'paid':0},'business_acceptance':False}
(E/'actual-recorded-cli.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':repeat['status'],'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,'value':row['value'],'unit':row['unit'],'period':[row['period_start'],row['period_end']],'simulated_counts':[count_before,count_after],'no_recalculation':True,'new_calls':[0,0,0]}))
