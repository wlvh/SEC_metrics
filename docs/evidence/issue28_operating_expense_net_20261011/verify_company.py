"""Actual saved-source CLI, forbidden recomputation and separate results process."""
import contextlib
import csv
import io
import json
import socket
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.vnext_company import main
from vnext.canonical import sha256_file

source = Path(sys.argv[1]).resolve()
evidence = Path(__file__).resolve().parent
program = Path.cwd()
base = Path(tempfile.mkdtemp(prefix='issue28-operating-net-company-'))
state, outputs, reader = (base / x for x in ('state', 'outputs', 'reader'))
args = ['run', '--company', 'southwest_airlines', '--period', 'fiscal-years',
        '--fiscal-year-start', '2022', '--fiscal-year-end', '2022',
        '--metric', 'B01', '--metric', 'B02', '--source-root', str(source),
        '--work-dir', str(state), '--output-dir', str(outputs)]
protected_source = {p: sha256_file(path=source / p) for p in (
    'config/company_registry.csv', 'evidence/requests_log.csv',
    'evidence/requests_log_manifest.json')}

def snapshot(root):
    return {str(p.relative_to(root)): sha256_file(path=p)
            for p in root.rglob('*') if p.is_file()}

stream = io.StringIO()
with patch.object(socket.socket, 'connect', side_effect=AssertionError('No HTTP or provider')):
    started = time.monotonic()
    with contextlib.redirect_stdout(stream):
        first_exit = main(args)
    first_seconds = time.monotonic() - started
    saved = snapshot(state)
    result_files = {p: h for p, h in saved.items() if '/results/' in '/' + p}
    started = time.monotonic()
    with patch('vnext.ordinary_current_update.create_saved_result',
               side_effect=AssertionError('Unchanged task must not calculate')), \
         patch('vnext.calculator.calculate_metric',
               side_effect=AssertionError('Unchanged task must not calculate a graph')), \
         patch('vnext.calculator.calculate_observation_metric',
               side_effect=AssertionError('Unchanged task must not calculate observations')), \
         contextlib.redirect_stdout(stream):
        repeat_exit = main(args)
    repeat_seconds = time.monotonic() - started
    assert result_files == {p: h for p, h in snapshot(state).items() if '/results/' in '/' + p}

before_read = snapshot(state)
started = time.monotonic()
read = subprocess.run([sys.executable, 'tools/vnext_company.py', 'results',
    '--company', 'southwest_airlines', '--state-root', str(state),
    '--output-root', str(reader)], capture_output=True, text=True)
read_seconds = time.monotonic() - started
assert read.returncode == 0, read.stderr
assert snapshot(state) == before_read
rows = list(csv.DictReader((reader / 'metrics_matrix.csv').open()))
citations = list(csv.DictReader((reader / 'metric_evidence.csv').open()))
record = {'code_root': str(program), 'pre_test_commit': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'test_mode': 'uncommitted source/test changes; real CLI and calculation/store/read; no HTTP',
    'changed_code': {p: sha256_file(path=program/p) for p in (
        'scripts/vnext/selected_reported_revenue_v2.py',
        'tests/vnext/test_selected_reported_revenue_v2.py')},
    'source_root': str(source), 'state_root': str(state), 'cli_args': args,
    'first_seconds': first_seconds, 'repeat_seconds': repeat_seconds,
    'independent_read_seconds': read_seconds, 'first_exit': first_exit,
    'repeat_exit': repeat_exit, 'read_exit': read.returncode,
    'rows': rows, 'citation_rows': citations, 'protected_result_files': result_files,
    'independent_read_all_state_unchanged': True, 'stdout': stream.getvalue(),
    'calls': {'sec': 0, 'provider': 0, 'paid': 0}}
(evidence/'actual-company.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
assert protected_source == {p: sha256_file(path=source/p) for p in protected_source}
assert len(rows) == 2, rows
by_metric = {r['metric_id']: r for r in rows}
assert by_metric['B01']['value'] == '23814000000', rows
assert Decimal(by_metric['B02']['value']) == (Decimal('23814')-Decimal('15790'))/Decimal('15790'), rows
assert by_metric['B01']['unit'] == 'USD' and by_metric['B02']['unit'] == 'ratio', rows
assert all(r['period_start'] == '2022-01-01' and r['period_end'] == '2022-12-31' for r in rows)
assert citations and all(r['source_url'].startswith('https://') for r in citations)
print(json.dumps({'rows': [{k: r[k] for k in ('metric_id', 'value', 'unit',
    'period_start', 'period_end', 'status')} for r in rows],
    'first_seconds': first_seconds, 'repeat_seconds': repeat_seconds,
    'independent_read_seconds': read_seconds, 'files': len(result_files)}, indent=2))
