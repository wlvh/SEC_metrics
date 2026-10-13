"""Existing company entry only; source reference numbers are not input values."""
import argparse
from contextlib import ExitStack, redirect_stdout
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_statement_cases, calculator, batch_workflow


def hashes(root, results_only=False):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file()
        and (not results_only or '/results/' in str(p.relative_to(root)))}


parser = argparse.ArgumentParser()
parser.add_argument('phase',choices=['before','first','repeat','read'])
parser.add_argument('--state',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
source=Path(json.loads((args.state/'company-task.json').read_text())['source_root'])
company='paramount_skydance_paramount_global'
before=hashes(args.state)
old=hashes(args.state,True)
source_paths=(source/'config/company_registry.csv',source/'evidence/requests_log.csv',
              source/'evidence/requests_log_manifest.json')
source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
command=(['results','--company',company,'--state-root',str(args.state),
          '--output-root',str(args.output/'csv')] if args.phase in ('before','read') else
         ['run','--company',company,'--period','fiscal-years',
          '--fiscal-year-start','2024','--fiscal-year-end','2024',
          '--metric','B04','--metric','B07','--source-root',str(source),
          '--work-dir',str(args.state),'--output-dir',str(args.output/'runs')])
blocked={f.__code__ for f in (historical_statement_cases.prepare_historical_statement_year_case,
    historical_statement_cases.prepare_historical_current_annual_year_case,
    calculator.calculate_metric,batch_workflow.calculate_metric)}
old_profile=sys.getprofile()
def profile(frame,event,arg):
    if event=='call' and frame.f_code in blocked:
        raise AssertionError('CALCULATION_FORBIDDEN:'+frame.f_code.co_name)
    if old_profile is not None:old_profile(frame,event,arg)
stream=io.StringIO()
started=perf_counter()
with ExitStack() as stack:
    stack.enter_context(patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')))
    if args.phase!='first':
        sys.setprofile(profile)
        stack.callback(sys.setprofile,old_profile)
    with redirect_stdout(stream):code=main(command)
elapsed=perf_counter()-started
after=hashes(args.state)
new=hashes(args.state,True)
receipt={'phase':args.phase,'seconds':elapsed,'exit_code':code,'arguments':command,
    'stdout':stream.getvalue(),'all_old_results_preserved':all(new.get(k)==v for k,v in old.items()),
    'old_new_result_files':[len(old),len(new)],'old_new_state_files':[len(before),len(after)],
    'result_files_unchanged':old==new,'all_state_unchanged':before==after,
    'source_registration_and_ledger_unchanged':source_hashes=={
        str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},'new_calls':[0,0,0]}
(args.output/'execution.json.gz').write_bytes(gzip.compress((json.dumps(receipt,indent=2)+'\n').encode(),mtime=0))
print(json.dumps({k:v for k,v in receipt.items() if k not in ('arguments','stdout')},indent=2))
payload=json.loads(receipt['stdout'])
assert receipt['all_old_results_preserved'] and receipt['source_registration_and_ledger_unchanged']
if args.phase in ('before','read'):assert receipt['all_state_unchanged']
if args.phase=='repeat':
    assert receipt['result_files_unchanged']
    assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in payload['metrics'])
