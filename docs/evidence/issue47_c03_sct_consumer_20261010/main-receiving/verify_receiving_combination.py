"""Existing task only: shared C03/financial dispatch, zero computation."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/pfizer-statements-company-nvw2pcdt/state')
SOURCE = Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
OUT = Path(tempfile.mkdtemp(prefix='c03-main-receiving-', dir=STATE.parent))

def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

def invoke(label, arguments):
    code = '''import runpy,socket
def forbidden(*args, **kwargs): raise AssertionError('RECEIVING_COMPUTATION_OR_NETWORK_FORBIDDEN')
socket.socket.connect=forbidden
import vnext.historical_compensation_case as compensation
import vnext.historical_statement_cases as statements
compensation.prepare_historical_compensation_sources=forbidden
compensation.resolve_c03=forbidden
compensation.resolve_proxy_compensation_table=forbidden
statements.prepare_historical_annual_input=forbidden
import vnext.calculator as calculator
calculator.calculate_metric=forbidden
runpy.run_path('tools/vnext_company.py',run_name='__main__')
'''
    started=time.monotonic()
    process=subprocess.run([sys.executable,'-c',code,*map(str,arguments)],
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'scripts:tools:.'},
        capture_output=True,text=True)
    (HERE/(label+'.stdout')).write_text(process.stdout)
    (HERE/(label+'.stderr')).write_text(process.stderr)
    report={'seconds':time.monotonic()-started,'exit_code':process.returncode,
            'arguments':list(map(str,arguments)),'report':json.loads(process.stdout)}
    (HERE/(label+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(label,report['seconds'],process.returncode,flush=True)
    return report

before=hashes(STATE)
source_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
    (SOURCE/'evidence/requests_log.csv',SOURCE/'evidence/requests_log_manifest.json')}
baseline=invoke('combination-baseline-read',['results','--company','pfizer',
    '--state-root',STATE,'--output-root',OUT/'baseline'])
assert before==hashes(STATE)
assert baseline['exit_code']==0
mixed=invoke('combination-mixed-forbidden-repeat',['run','--company','pfizer',
    '--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025',
    '--metric','C03','--metric','B02','--source-root',SOURCE,
    '--work-dir',STATE,'--output-dir',OUT/'runs'])
assert len(mixed['report']['metrics'])==2
by_metric={m['metric_id']:m for m in mixed['report']['metrics']}
assert not by_metric['C03']['calculation_performed']
assert by_metric['C03']['status']=='NO_SOURCE_CONTENT_CHANGE'
assert by_metric['B02']['status']=='INPUT_OR_EXECUTION_FAILED'
assert by_metric['B02']['reason']=='RECEIVING_COMPUTATION_OR_NETWORK_FORBIDDEN'
after=hashes(STATE)
assert all(after.get(name)==digest for name,digest in before.items()
           if '/results/' in name or name.startswith('shared-inputs/'))
read=invoke('combination-independent-read',['results','--company','pfizer',
    '--state-root',STATE,'--output-root',OUT/'read'])
assert after==hashes(STATE)
assert read['exit_code']==0
fields=('value','unit','cik','period_start','period_end','result_id','status','accession')
def rows(directory):
    with (directory/'metrics_matrix.csv').open(encoding='utf-8-sig') as stream:
        return {(r['metric_id'],r['fiscal_year']):{k:r[k] for k in fields}
                for r in csv.DictReader(stream)}
assert rows(OUT/'baseline')==rows(OUT/'read')
assert len(rows(OUT/'read'))==30
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest
           for p,digest in source_before.items())
summary={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'main_commit':subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip(),
    'state_root':str(STATE),'output_root':str(OUT),'rows_preserved':30,
    'mixed_repeated_metrics':['C03','B02'],'C03_reused':True,
    'B02_reprocessing_refused_by_constructed_control':True,
    'mixed_reuse_pass':False,'new_result_directories':0,
    'mixed_seconds':mixed['seconds'],'read_seconds':read['seconds'],
    'state_files_unchanged_on_read':len(after),'source_log_manifest_unchanged':True,
    'new_calls':[0,0,0]}
(HERE/'receiving-combination-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary),flush=True)
