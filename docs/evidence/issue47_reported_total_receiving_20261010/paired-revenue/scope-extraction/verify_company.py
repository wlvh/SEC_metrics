"""One affected saved-source B02 coordinate, no source/model acquisition."""
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
BASE=Path(tempfile.mkdtemp(prefix='paired-source-extraction-',
    dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
STATE=BASE/'state'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def files():return {str(p.relative_to(STATE)):digest(p) for p in STATE.rglob('*') if p.is_file()}
source_before={str(p):digest(p) for p in (SOURCE/'evidence/requests_log.csv',SOURCE/'evidence/requests_log_manifest.json')}

def invoke(label,args,forbid=False):
    code='import json,sys\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
    if forbid:
        code+='''from vnext import historical_statement_cases as cases,calculator
import vnext.historical_paired_revenue as paired
blocked={cases.prepare_historical_statement_year_case.__code__,calculator.calculate_metric.__code__,paired.revenue_claims_admitted_by_original.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_B02_MUST_NOT_CALCULATE')
sys.setprofile(guard)
'''
    code+='with patch("socket.socket.connect",side_effect=AssertionError("NETWORK_FORBIDDEN")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
    started=time.monotonic()
    p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(list(map(str,args)))],
        capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'scripts:tools:.'})
    (HERE/(label+'.stdout')).write_text(p.stdout);(HERE/(label+'.stderr')).write_text(p.stderr)
    report={'seconds':time.monotonic()-started,'exit_code':p.returncode,'arguments':list(map(str,args)),
        'report':json.loads(p.stdout)}
    (HERE/(label+'.json')).write_text(json.dumps(report,indent=2))
    print(label,report['seconds'],p.returncode,flush=True)
    assert p.returncode==0 and not p.stderr
    return report

args=['run','--company','pfizer','--period','fiscal-years','--fiscal-year-start','2023',
    '--fiscal-year-end','2023','--metric','B02','--source-root',SOURCE,'--work-dir',STATE,'--output-dir',BASE/'runs']
first=invoke('first',args)
metric=first['report']['metrics'][0];record=Path(metric['record_root'])
result=json.loads((record/'records.jsonl').read_text().splitlines()[-1])
matrix=list(csv.DictReader((Path(first['report']['output_root'])/'metrics_matrix.csv').open(encoding='utf-8-sig')))
assert len(matrix)==1 and matrix[0]['value']=='-0.4169640187381640586065982259'
assert matrix[0]['cik']=='78003' and matrix[0]['period_start']=='2023-01-01' and matrix[0]['period_end']=='2023-12-31'
assessment=json.load((record/'input-assessments.json').open())['assessments']['historical_statement']
assert all(s['complete_scope_proven'] for s in assessment['paired_revenue_scopes'].values())
before=files();repeat=invoke('forbidden-repeat',args,True)
assert repeat['report']['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not repeat['report']['metrics'][0]['calculation_performed']
assert all(files().get(n)==sha for n,sha in before.items() if '/results/' in n)
before=files();read=invoke('independent-read',['results','--company','pfizer','--state-root',STATE,'--output-root',BASE/'read'],True)
assert files()==before
rows=list(csv.DictReader((BASE/'read/metrics_matrix.csv').open(encoding='utf-8-sig')))
assert rows[0]['result_id']==matrix[0]['result_id'] and rows[0]['value']==matrix[0]['value']
assert all(digest(Path(p))==sha for p,sha in source_before.items())
summary={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'state_root':str(STATE),'first_seconds':first['seconds'],'repeat_seconds':repeat['seconds'],
    'read_seconds':read['seconds'],'value':rows[0]['value'],'unit':rows[0]['unit'],
    'result_id':rows[0]['result_id'],'source_log_manifest_unchanged':True,
    'state_files_unchanged_on_read':len(before),'new_calls':[0,0,0]}
(HERE/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
