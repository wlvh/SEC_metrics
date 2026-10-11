"""One saved Macy year through the actual CLI; no network or fabricated financial case."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--state-root', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
args = parser.parse_args()
state = args.state_root.resolve()
output = args.output_root.resolve()
output.mkdir(parents=True, exist_ok=False)
source = Path(json.loads((state/'company-task.json').read_text())['source_root'])

def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

before = hashes(state)
protected = {p: h for p, h in before.items() if '/results/' in p or '/shared-inputs/' in p
             or p == 'company-task.json' or p.endswith(('current-result.json', 'completed-check.json'))
             and not any(p.startswith('updates/'+m+'/periods/FY2023/') for m in ('B01', 'B02', 'B04'))}
source_controls = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (source/'evidence/requests_log.csv', source/'config/company_registry.csv')}
base = ['run', '--company', 'macys', '--period', 'fiscal-years',
        '--fiscal-year-start', '2023', '--fiscal-year-end', '2023',
        '--source-root', str(source), '--work-dir', str(state), '--output-dir', str(output/'runs')]
records = []

def invoke(name, arguments, forbid=False):
    code = '''import json,sys
from unittest.mock import patch
from tools.vnext_company import main
'''
    if forbid:
        code += '''from vnext import company_fiscal_range as ranges,historical_statement_cases as cases,calculator
blocked={ranges.discover_fiscal_range.__code__,cases.prepare_historical_statement_year_case.__code__,
 calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
def guard(frame,event,arg):
 if event=="call" and frame.f_code in blocked:
  raise AssertionError("Unchanged input cannot discover or calculate")
sys.setprofile(guard)
'''
    code += '''with patch("socket.socket.connect",side_effect=AssertionError("No real network allowed")):
 raise SystemExit(main(json.loads(sys.argv[1])))
'''
    start = time.monotonic()
    process = subprocess.run([sys.executable, '-B', '-c', code, json.dumps(arguments)],
                             capture_output=True, text=True)
    record = {'name': name, 'seconds': time.monotonic()-start, 'exit_code': process.returncode,
              'arguments': arguments, 'stdout': process.stdout, 'stderr': process.stderr}
    (output/(name+'.json')).write_text(json.dumps(record, indent=2)+'\n')
    records.append(record)
    print(name, process.returncode, round(record['seconds'], 3), flush=True)
    assert not process.stderr, record
    assert process.returncode in (0, 2), record
    return json.loads(process.stdout)

def selected(metrics):
    return base + [value for metric in metrics for value in ('--metric', metric)]

initial = invoke('one-related-version-transition', selected(['B01', 'B02', 'B04']))
assert all(m['status'] not in ('INPUT_OR_EXECUTION_FAILED', 'SOURCE_UNAVAILABLE')
           for m in initial['metrics']), initial
assert all(hashes(state).get(p) == h for p, h in protected.items())
stable = {p: h for p, h in hashes(state).items() if '/results/' in p or '/shared-inputs/' in p
          or p.endswith(('current-result.json', 'completed-check.json')) or p == 'company-task.json'}
for name, metrics in [('income-only', ['B01', 'B02']), ('mixed-again', ['B01', 'B02', 'B04']),
                      ('B01-only', ['B01']), ('B02-only', ['B02'])]:
    report = invoke(name, selected(metrics), True)
    assert all(not m['calculation_performed'] and not m['new_candidate_created'] for m in report['metrics'])
    assert all(m['status'] in ('NO_SOURCE_CONTENT_CHANGE', 'PREVIOUS_INPUT_WITHHELD') for m in report['metrics'])
    assert all(hashes(state).get(p) == h for p, h in stable.items())

read_before = hashes(state)
invoke('independent-read', ['results', '--company', 'macys', '--state-root', str(state),
                          '--output-root', str(output/'read')], True)
assert read_before == hashes(state)
rows = list(csv.DictReader((output/'read/metrics_matrix.csv').open()))
revenue = next(r for r in rows if (r['metric_id'], r['fiscal_year']) == ('B01', '2023'))
growth = next(r for r in rows if (r['metric_id'], r['fiscal_year']) == ('B02', '2023'))
assert (revenue['value'], revenue['unit'], revenue['period_start'], revenue['period_end']) == (
    '23866000000', 'USD', '2023-01-29', '2024-02-03')
assert revenue['result_id'] == 'sha256:77805235a0d19e2a7dde8d90850d96e555e92399f47a243b60ed3c4c98b2eeed'
assert not growth['value'] and growth['status'] == 'WITHHELD'
assert growth['result_id'] == 'sha256:3e8862c327c83ba437335700220e41c9599d0df1a751f89a8182f86d63aca3c2'
assert 'HISTORICAL_PAIRED_REVENUE_SCOPE_UNRESOLVED' in growth['notes']
assert {(r['metric_id'], r['fiscal_year']) for r in rows} >= {
    (m, str(y)) for m in ('B01', 'B02', 'B04', 'B05') for y in range(2021, 2026)}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in source_controls.items())
receipt = {'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
           'state_root': str(state), 'output_root': str(output), 'records': records,
           'rows': rows, 'old_protected_files': protected, 'stable_result_files': stable,
           'independent_read_files_before_after': read_before, 'source_controls': source_controls,
           'source_and_old_results_preserved': True, 'new_calls': [0, 0, 0],
           'scope': 'Existing Macy FY2023 only; no new five-year or revenue-scope acceptance'}
(output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print('B01 correct total/53-week dates preserved; B02 stable withheld; alternating selections reused; old rows intact', flush=True)
