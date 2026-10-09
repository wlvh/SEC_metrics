"""Consume the shared CLI; do not replace its controller or result reader."""
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
first = json.loads((HERE/'first-salesforce.json').read_text())
state = Path(first['state_root'])

def digest(root, protected_only=False):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and
            (not protected_only or p.name in {'company-task.json', 'current-result.json', 'completed-check.json'}
             or 'results' in p.parts or 'shared-inputs' in p.parts)}

def execute(args, prelude=None):
    command = [sys.executable, '-B'] + (['-c', prelude] if prelude else ['tools/vnext_company.py']) + args
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True)
    return {'seconds': time.monotonic()-start, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}

GUARD = """import sys,runpy,socket,urllib.request
sys.path[:0]=['.','scripts','tools']
def forbidden(*a,**k):raise AssertionError('No discovery, business preparation or calculation on repeat/read')
socket.socket.connect=forbidden;urllib.request.urlopen=forbidden
from vnext import company_fiscal_range as ranges,historical_statement_cases as cases,calculator
ranges.discover_fiscal_range=forbidden
cases.prepare_historical_statement_year_case=forbidden
cases.resolve_period_selection=forbidden
calculator.calculate_metric=forbidden;calculator.calculate_text_metric=forbidden
sys.argv=['tools/vnext_company.py',*sys.argv[1:]]
runpy.run_path('tools/vnext_company.py',run_name='__main__')
"""

before = digest(state, True)
repeat = execute(first['arguments'], GUARD)
report = json.loads(repeat['stdout'])
assert repeat['exit_code'] == 0 and not repeat['stderr'], repeat
assert report['status'] == 'FLOW_COMPLETED'
assert len(report['metrics']) == 1
assert report['metrics'][0]['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert not report['metrics'][0]['calculation_performed']
assert before == digest(state, True)
out = state.parent/'independent-read'
read = execute(['results', '--company', 'salesforce', '--state-root', str(state), '--output-root', str(out)], GUARD)
assert read['exit_code'] == 0 and not read['stderr'], read
rows = list(csv.DictReader((out/'metrics_matrix.csv').open()))
assert len(rows) == 1
row = rows[0]
assert (row['value'], row['unit'], row['fiscal_year'], row['period_start'], row['period_end']) == (
    '41525000000', 'USD', '2026', '2025-02-01', '2026-01-31')
assert before == digest(state, True)
(HERE/'salesforce-repeat-read.json').write_text(json.dumps({
    'repeat': repeat, 'independent_read': read, 'rows': rows,
    'protected_files_before_after': before, 'protected_files_preserved': True,
    'source_scope': 'NO_DEMONSTRATED_SPLIT; this run does not newly prove every revenue component',
    'new_calls': [0, 0, 0]}, indent=2)+'\n')
print('Salesforce repeat/read:', repeat['seconds'], read['seconds'], 'protected:', len(before))

macys = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/statement-pilot-macys-20261009/state')
before = digest(macys)
out = state.parent/'macys-existing-read'
read = execute(['results', '--company', 'macys', '--state-root', str(macys), '--output-root', str(out)], GUARD)
assert read['exit_code'] == 0 and not read['stderr'], read
rows = list(csv.DictReader((out/'metrics_matrix.csv').open()))
assert len(rows) == 22
holds = [r for r in rows if r['status'] == 'WITHHELD_KNOWN_DEFECT']
assert {(r['metric_id'], r['fiscal_year']) for r in holds} == {('B01', '2023'), ('B02', '2023')}
assert all(not r['value'] for r in holds)
assert all(r['status'] != 'WITHHELD_KNOWN_DEFECT' for r in rows if r['fiscal_year'] == '2022')
assert before == digest(macys)
(HERE/'macys-existing-read.json').write_text(json.dumps({
    'independent_read': read, 'rows': rows, 'existing_row_count': len(rows),
    'original_state_files_before_after': before, 'original_state_preserved': True,
    'confirmed_defects': ['FY2023 B01 5f17ec97', 'FY2023 B02 db609edd'],
    'FY2022': 'not confirmed wrong; still a source-scope investigation',
    'calculation_or_discovery_calls': 0, 'new_calls': [0, 0, 0]}, indent=2)+'\n')
print('Macy existing read:', read['seconds'], 'rows:', len(rows), 'holds:', len(holds), 'protected:', len(before))
