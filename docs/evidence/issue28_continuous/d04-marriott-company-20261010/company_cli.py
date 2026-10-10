"""Existing complete Marriott D04 responses through the public company CLI."""
import argparse,csv,hashlib,io,json,os,socket,subprocess,sys,tempfile,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

p=argparse.ArgumentParser();p.add_argument('--code-root',required=True,type=Path);p.add_argument('--output-root',required=True,type=Path);a=p.parse_args()
ROOT=a.code_root.resolve();HERE=a.output_root.resolve();HERE.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tools'),str(ROOT)]
from vnext_company import main
from vnext import current_d04_result
from vnext.continuous_call_ledger import CallLedger
LEDGER=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
BASE=Path(tempfile.mkdtemp(prefix='issue28-marriott-d04-',dir='/private/tmp'))
protected=[LEDGER/'claims.jsonl',LEDGER/'binding.json']
for ordinal in range(115,119):protected.extend(p for p in (LEDGER/'calls'/f'{ordinal:04d}').rglob('*') if p.is_file())
def hashes(paths):return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
original=hashes(protected)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
code_files=['scripts/vnext/current_d04_result.py','scripts/vnext/ordinary_current_update.py','scripts/vnext/company_current_records.py','scripts/vnext/company_local.py','tools/vnext_company.py','scripts/vnext/capacity_update_input.py']
code={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in code_files}
args=['run','--company','marriott_international','--source-root',str(LEDGER/'source-inputs'),'--work-dir',str(BASE/'state'),'--output-dir',str(BASE/'output'),'--metric','D04']
operations=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')),patch.object(CallLedger,'claim',side_effect=AssertionError('No new call claim permitted')):
 for label,forbid in [('first',False),('repeat-with-forbidden-factory',True)]:
  stream=io.StringIO();start=time.perf_counter()
  if forbid:
   with patch.object(current_d04_result,'prepare_current_d04_case',side_effect=AssertionError('No unchanged D04 reprocessing')),redirect_stdout(stream):rc=main(args)
  else:
   with redirect_stdout(stream):rc=main(args)
  elapsed=time.perf_counter()-start;text=stream.getvalue();(HERE/(label+'.json')).write_text(text)
  report=json.loads(text);operations.append({'label':label,'seconds':elapsed,'exit_code':rc,'report':report})
  print(label,rc,elapsed,report.get('metrics'),flush=True)
  if rc not in (0,2) or len(report.get('metrics',[]))!=1:raise AssertionError('company incomplete report')
  m=report['metrics'][0]
  if m.get('result_reason_code')!='D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE':raise AssertionError('actual D04 report requires investigation; do not change expected semantics')
  if forbid:
   assert m['status']=='PREVIOUS_INPUT_WITHHELD' and m['calculation_performed'] is False
   assert m['result_id']==operations[0]['report']['metrics'][0]['result_id']
# Independent process uses same public results entry and forbids sockets/call claims/update.
record_files=[p for p in (BASE/'state').rglob('*') if p.is_file() and p.name not in ['.lock']]
before_read=hashes(record_files)
runner="""import sys,socket;from pathlib import Path;from unittest.mock import patch
root=Path(sys.argv[1]);sys.path[:0]=[str(root/'scripts'),str(root/'tools'),str(root)]
from vnext_company import main
from vnext import ordinary_current_update,current_d04_result
from vnext.continuous_call_ledger import CallLedger
with patch.object(socket.socket,'connect',side_effect=AssertionError('no network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('no DNS')),patch.object(CallLedger,'claim',side_effect=AssertionError('no claims')),patch.object(ordinary_current_update,'run_once',side_effect=AssertionError('reader must not update')),patch.object(current_d04_result,'prepare_current_d04_case',side_effect=AssertionError('reader must not reprocess')):
 raise SystemExit(main(sys.argv[2:]))
"""
start=time.perf_counter();read=subprocess.run([sys.executable,'-c',runner,str(ROOT),'results','--company','marriott_international','--state-root',str(BASE/'state'),'--output-root',str(BASE/'independent-output')],capture_output=True,text=True,cwd='/private/tmp')
(HERE/'independent-results.json').write_text(read.stdout);(HERE/'independent-results.stderr').write_text(read.stderr)
read_seconds=time.perf_counter()-start;assert read.returncode==0,(read.returncode,read.stderr)
assert before_read==hashes(record_files)
rows=list(csv.DictReader((BASE/'independent-output'/'metrics_matrix.csv').open()))
assert len(rows)==1 and rows[0]['metric_id']=='D04' and rows[0]['status']=='TEXT_QUAL',rows
assert original==hashes(protected),'original calls/ledger bytes changed'
summary={'code_root':str(ROOT),'code_head':head,'code_files':code,'state_root':str(BASE/'state'),'source_root':str(LEDGER/'source-inputs'),'output_root':str(BASE/'output'),'independent_output':str(BASE/'independent-output'),'operations':operations,'read_seconds':read_seconds,'reader_exit_code':read.returncode,'reader_state_files_protected':len(record_files),'original_files_protected':len(protected),'originals_unchanged':True,'rows':rows,'new_calls':[0,0,0],'source_mode':'existing full saved real requests and responses; no simulated business answer','production_authorized':False}
(HERE/'company-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('independent-read',read.returncode,read_seconds,'rows',len(rows),'protected',len(protected),flush=True)
