"""Existing historical task; current-only code changes are simulated in memory."""
from contextlib import redirect_stdout
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

from tools.vnext_company import main
from vnext import ordinary_current_update as update
from vnext import historical_d04_selection as selection, saved_d04_replay as replay, calculator

parser=argparse.ArgumentParser()
parser.add_argument('--state-root',required=True,type=Path)
parser.add_argument('--saved-call-package',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
options=parser.parse_args()
state=options.state_root.resolve()
task=json.loads((state/'company-task.json').read_text());source=Path(task['source_root'])
package=options.saved_call_package.resolve()
out=options.output_root.resolve()
out.mkdir(exist_ok=False)
def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '/results/' in str(p.relative_to(root))}
old=hashes(state);protected=[package,source/'config/company_registry.csv',
    source/'evidence/requests_log.csv',source/'evidence/requests_log_manifest.json']
source_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
blocked={f.__code__ for f in (selection.prepare_historical_d04_selection,
    replay.prepare_selected_saved_d04_case,replay.read_saved_d04_assessment,
    calculator.calculate_metric,calculator.calculate_observation_metric)}
def guard(frame,event,arg):
    if event=='call' and frame.f_code in blocked:
        raise AssertionError('UNUSED_CURRENT_CHANGE_MUST_NOT_REPLAY:'+frame.f_code.co_name)
command=['run','--company','marriott_international','--period','fiscal-years',
    '--fiscal-year-start','2024','--fiscal-year-end','2024','--metric','D04',
    '--source-root',str(source),'--saved-call-package',str(package),
    '--work-dir',str(state),'--output-dir',str(out/'runs')]
actual=update.sha256_file
def simulated(*,path):
    if Path(path).name in ('current_d04_result.py','capacity_update_input.py'):
        return 'CONSTRUCTED_UNUSED_CURRENT_CODE_CHANGE'
    return actual(path=path)
stream=io.StringIO();started=perf_counter();previous=sys.getprofile()
try:
    sys.setprofile(guard)
    with patch.object(update,'sha256_file',side_effect=simulated), \
         patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         redirect_stdout(stream):
        code=main(command)
finally:
    sys.setprofile(previous)
payload=json.loads(stream.getvalue())
receipt={'scope':'ACTUAL_EXISTING_D04_TASK_WITH_CONSTRUCTED_CURRENT_CODE_CHANGE',
    'seconds':perf_counter()-started,'exit_code':code,'arguments':command,'payload':payload,
    'result_files_unchanged':old==hashes(state),'result_file_count':len(old),
    'source_package_and_ledger_unchanged':source_before=={
        str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},'new_calls':[0,0,0]}
assert receipt['result_files_unchanged'] and receipt['source_package_and_ledger_unchanged']
assert all(not m['calculation_performed'] and not m['new_candidate_created'] for m in payload['metrics'])
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('arguments','payload')},indent=2))
