"""Add only two unprocessed Ford C03 years to its existing ordinary task."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
STATE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/c03-ford-ecd-rvv7auy0/state')
SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
OUT=Path(tempfile.mkdtemp(prefix='ford-c03-two-year-',dir=STATE.parent))
REFERENCE=json.load((HERE/'reference-before-consumer.json').open())
EXPECTED={r['fiscal_year']:str(r['total']) for r in REFERENCE['rows']}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files():return {str(p.relative_to(STATE)):digest(p) for p in STATE.rglob('*') if p.is_file()}
source_before={str(p):digest(p) for p in (SOURCE/'evidence/requests_log.csv',SOURCE/'evidence/requests_log_manifest.json')}

def invoke(label,args,forbid=False):
    code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
    if forbid:
        code+='''from vnext import historical_compensation_case as cases,calculator
blocked={cases.prepare_historical_compensation_year_case.__code__,cases.resolve_c03.__code__,cases.resolve_proxy_compensation_table.__code__,calculator.calculate_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_C03_MUST_NOT_CALCULATE')
sys.setprofile(guard)
'''
    code+='with patch("socket.socket.connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
    started=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(list(map(str,args)))],
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'scripts:tools:.'},capture_output=True,text=True)
    (HERE/(label+'.stdout')).write_text(p.stdout);(HERE/(label+'.stderr')).write_text(p.stderr)
    r={'seconds':time.monotonic()-started,'exit_code':p.returncode,'arguments':list(map(str,args)),'report':json.loads(p.stdout)}
    (HERE/(label+'.json')).write_text(json.dumps(r,indent=2));print(label,p.returncode,r['seconds'],flush=True)
    assert p.returncode in (0,2) and not p.stderr
    return r

if (HERE/'two-year-first.json').exists():
    baseline=json.load((HERE/'baseline-read.json').open())
    first=json.load((HERE/'two-year-first.json').open())
    OUT=Path(first['arguments'][-1]).parent
else:
    before=files();baseline=invoke('baseline-read',['results','--company','ford_motor_company','--state-root',STATE,'--output-root',OUT/'baseline'],True)
    assert files()==before
    first=None
args=['run','--company','ford_motor_company','--period','fiscal-years','--fiscal-year-start','2023','--fiscal-year-end','2024','--metric','C03','--source-root',SOURCE,'--work-dir',STATE,'--output-dir',OUT/'runs']
if first is None:first=invoke('two-year-first',args)
assert {m['requested_fiscal_year'] for m in first['report']['metrics']}=={2023,2024}
assert first['exit_code']==2 and all(m['status']=='CANDIDATE_WITHHELD' for m in first['report']['metrics'])
after=files()
repeat=invoke('two-year-forbidden-repeat',args,True)
assert repeat['exit_code']==2
assert all(m['status']=='PREVIOUS_INPUT_WITHHELD' and not m['calculation_performed'] and not m['new_candidate_created'] for m in repeat['report']['metrics'])
assert all(files().get(n)==sha for n,sha in after.items() if '/results/' in n)
before_read=files();read=invoke('independent-four-year-read',['results','--company','ford_motor_company','--state-root',STATE,'--output-root',OUT/'read'],True)
assert files()==before_read
def rows(path):return list(csv.DictReader((path/'metrics_matrix.csv').open(encoding='utf-8-sig')))
old={r['fiscal_year']:r for r in rows(OUT/'baseline')};current={r['fiscal_year']:r for r in rows(OUT/'read')}
assert set(current)=={'2022','2023','2024','2025'}
fields=('value','unit','cik','period_start','period_end','result_id','status','accession')
assert all(all(old[y][k]==current[y][k] for k in fields) for y in old)
for y,value in EXPECTED.items():
    row=current[str(y)];reference=next(r for r in REFERENCE['rows'] if r['fiscal_year']==y)
    assert row['value']=='' and row['cik']=='37996'
    assert row['period_start']==f'{y}-01-01' and row['period_end']==f'{y}-12-31'
    assert row['accession']==reference['selected_proxy']['accessionNumber'] and row['form']=='DEF 14A'
    assert 'C03_TARGET_FACT_INVALID' in row['notes']
assert all(digest(Path(p))==sha for p,sha in source_before.items())
summary={'product_code_commit':'813cf6a1 guide-only/source2532d4a3','state_root':str(STATE),'output_root':str(OUT),
    'first_seconds':first['seconds'],'repeat_seconds':repeat['seconds'],'read_seconds':read['seconds'],
    'newly_processed_years':[2023,2024],'old_2022_2025_values_dates_ids_unchanged':True,
    'state_files_unchanged_on_read':len(before_read),'source_log_manifest_unchanged':True,
    'rows':[{k:r[k] for k in ('fiscal_year',*fields,'form','filed_date','requested_in_latest_execution')} for r in current.values()],
    'expected_original_table_values':EXPECTED,'actual_new_values':None,
    'new_years_complete':False,'withheld_reason':'C03_TARGET_FACT_INVALID: former-person nil fact',
    'new_calls':[0,0,0],'new_content_reference_scope':'two original Summary Compensation Table rows; no blind/model experiment'}
(HERE/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
