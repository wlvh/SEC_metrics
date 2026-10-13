"""Receive the shared source fix into an existing ordinary company task.

Source originals remain read only. Each phase saves its raw output before
assertions, so a failed verification does not require replaying completed work.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from decimal import Decimal, localcontext
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--source-root', type=Path, required=True)
p.add_argument('--baseline-root', type=Path, required=True)
p.add_argument('--output-root', type=Path, required=True)
a = p.parse_args()
source = a.source_root.resolve()
state = a.baseline_root.resolve() / 'state'
out = a.output_root.resolve()
out.mkdir(parents=True, exist_ok=False)

def hashes(root):
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in root.rglob('*') if f.is_file()}

watch = ['config/company_registry.csv', 'evidence/requests_log.csv',
         'evidence/requests_log_manifest.json']
source_before = {x: hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
before = hashes(state)
old_results = {x: h for x, h in before.items() if '/results/' in x}
(out/'before-state.json').write_text(json.dumps(before, indent=2)+'\n')

def invoke(name, command, forbidden=False):
    code = '''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_statement_cases as s,historical_paired_revenue as p,calculator
blocked={s.prepare_historical_statement_year_case.__code__,s._prepare_historical_statement_case.__code__,p.revenue_claims_admitted_by_original.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=='call' and frame.f_code in blocked:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, '-B', '-c', code,
                           json.dumps(command), str(int(forbidden))],
                          capture_output=True, text=True)
    record = dict(seconds=time.perf_counter()-start, exit_code=proc.returncode,
                  arguments=command, stdout=proc.stdout, stderr=proc.stderr)
    (out/(name+'.json')).write_text(json.dumps(record, indent=2)+'\n')
    print(name, round(record['seconds'], 3), proc.returncode, flush=True)
    assert proc.returncode in (0, 2) and not proc.stderr, record
    return json.loads(proc.stdout), record

command = ['run', '--company', 'marriott_international', '--period', 'fiscal-years',
           '--fiscal-year-start', '2023', '--fiscal-year-end', '2024', '--metric', 'B02',
           '--source-root', str(source), '--work-dir', str(state),
           '--output-dir', str(out/'runs')]
first, first_run = invoke('after-processing', command)
assert len(first['metrics']) == 2
assert all(m['calculation_performed'] and m['new_candidate_created']
           for m in first['metrics']), first
assert all(hashes(state).get(x) == h for x, h in old_results.items())
new_results = {str(f.relative_to(state)) for f in state.glob('updates/B02/periods/*/results/*')}
protected = {x: h for x, h in hashes(state).items()
             if '/results/' in x or x.endswith(('current-result.json','completed-check.json'))
             or x == 'company-task.json'}
repeat, repeat_run = invoke('repeat-forbidden', command, True)
assert all(not m['calculation_performed'] and not m['new_candidate_created']
           for m in repeat['metrics']), repeat
assert {m['result_id'] for m in first['metrics']} == {m['result_id'] for m in repeat['metrics']}
assert all(hashes(state).get(x) == h for x, h in protected.items())
assert new_results == {str(f.relative_to(state)) for f in state.glob('updates/B02/periods/*/results/*')}
before_read = hashes(state)
read, read_run = invoke('independent-read', ['results','--company','marriott_international',
                        '--state-root',str(state),'--output-root',str(out/'read')], True)
assert before_read == hashes(state)
rows = list(csv.DictReader((out/'read/metrics_matrix.csv').open(encoding='utf-8-sig')))
assert len(rows) == 2, rows
reference = {2023:(23713,20773), 2024:(25100,23713)}
for row in rows:
    fy = int(row['fiscal_year'])
    current, prior = reference[fy]
    root = Path(row['record_root'])
    assessment = json.loads((root/'input-assessments.json').read_text())['assessments']['historical_statement']
    if fy == 2023:
        assert row['value']=='' and row['status']=='WITHHELD'
        assert assessment['unresolved_revenue_role']=='prior'
        assert assessment['reason']=='SELECTED_REVENUE_STATEMENT_HEADING_SCOPE_UNRESOLVED'
        assert assessment['paired_revenue_scopes']['current']['complete_scope_proven']
        continue
    with localcontext() as ctx:
        ctx.prec = 28
        assert Decimal(row['value']) == (Decimal(current)-Decimal(prior))/Decimal(prior), row
    assert row['unit']=='ratio' and row['cik']=='1048286'
    assert row['period_start']==f'{fy}-01-01' and row['period_end']==f'{fy}-12-31'
    assert set(assessment['paired_revenue_scopes']) == {'current','prior'}
    assert all(s['complete_scope_proven'] for s in assessment['paired_revenue_scopes'].values())
    records = [json.loads(x) for x in (root/'records.jsonl').read_text().splitlines()]
    claims = [x for x in records if x['record_type']=='DETERMINISTIC_VERIFIED_CLAIM']
    assert {x['value'] for x in claims} == {str(current*1000000),str(prior*1000000)}
assert (out/'read/metric_evidence.csv').stat().st_size > 0
assert source_before == {x:hashlib.sha256((source/x).read_bytes()).hexdigest() for x in watch}
summary = dict(code_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
               phases={n:{k:v[k] for k in ('seconds','exit_code','arguments')}
                       for n,v in [('processing',first_run),('repeat',repeat_run),('read',read_run)]},
               rows=rows, old_result_files_unchanged=len(old_results),
               read_state_files_unchanged=len(before_read), source_hashes=source_before,
               new_calls=[0,0,0])
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
