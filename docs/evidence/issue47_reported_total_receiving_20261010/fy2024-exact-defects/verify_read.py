"""Read exact old results with the current defect overlay; do not calculate."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from contextlib import redirect_stdout
from time import perf_counter
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_statement_cases, calculator, batch_workflow
from vnext.company_current_records import _defects,_registry

parser=argparse.ArgumentParser()
parser.add_argument('--state-root',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
options=parser.parse_args();state=options.state_root.resolve();out=options.output_root.resolve()
out.mkdir(parents=True,exist_ok=False)
def hashes():
    return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in state.rglob('*') if p.is_file()}
before=hashes()
blocked={f.__code__ for f in (historical_statement_cases.prepare_historical_statement_year_case,
    calculator.calculate_metric,batch_workflow.calculate_metric)}
def guard(frame,event,arg):
    if event=='call' and frame.f_code in blocked:raise AssertionError('READ_MUST_NOT_CALCULATE')
stream=io.StringIO();start=perf_counter();previous=sys.getprofile()
try:
    sys.setprofile(guard)
    with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),redirect_stdout(stream):
        code=main(['results','--company','macys','--state-root',str(state),'--output-root',str(out/'csv')])
finally:
    sys.setprofile(previous)
rows=list(csv.DictReader((out/'csv/metrics_matrix.csv').open()))
selected=[r for r in rows if r['metric_id'] in ('B01','B02') and r['fiscal_year']=='2024']
assert len(selected)==2
assert all(r['status']=='WITHHELD_KNOWN_DEFECT' and r['value']=='' for r in selected)
assert before==hashes()
registry=_registry()
exact={m:r['result_id'] for m in ('B01','B02') for r in selected if r['metric_id']==m}
matches={m:_defects({'company_id':'macys','metric_id':m,'period_end':'2025-02-01',
                    'result_id':result},registry) for m,result in exact.items()}
assert all(len(v)==1 for v in matches.values())
assert not _defects({'company_id':'macys','metric_id':'B01','period_end':'2025-02-01',
                     'result_id':'sha256:different-legitimate-result'},registry)
receipt={'seconds':perf_counter()-start,'exit_code':code,'state_files_unchanged':len(before),
    'exact_matches':matches,'rows':selected,'all_rows':len(rows),'new_calls':[0,0,0],
    'new_metric_result_created':False,'source_read_reference_only':True}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='rows'},indent=2))
