"""Real main first run and candidate unchanged check/read; shared read-only sources."""
import contextlib
import csv
import io
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from tools.vnext_company import main
from vnext.canonical import sha256_file

source = Path(sys.argv[1]).resolve()
baseline = Path(sys.argv[2]).resolve()
program = Path.cwd()
evidence = Path(__file__).resolve().parent
base = Path(tempfile.mkdtemp(prefix='issue28-proof-main63-company-'))
state, output, reader = (base / p for p in ('state', 'output', 'reader'))
args = ['run', '--company', 'marriott_international', '--metric', 'B01',
        '--source-root', str(source), '--work-dir', str(state), '--output-dir', str(output)]
env = dict(__import__('os').environ, PYTHONDONTWRITEBYTECODE='1',
           PYTHONPATH='scripts:tools:.', TMPDIR='/private/tmp')
driver = '''import json,socket,sys,time
from unittest.mock import patch
from tools.vnext_company import main
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 code=main(json.loads(sys.argv[1]))
print(json.dumps({'driver_exit':code,'driver_seconds':time.monotonic()-start}))
sys.exit(code)
'''
started = time.monotonic()
first = subprocess.run([sys.executable, '-c', driver, json.dumps(args)],
    cwd=baseline, env=env, capture_output=True, text=True)
first_seconds = time.monotonic() - started
(evidence/'main-63a-company-first.log').write_text(first.stdout+first.stderr)
assert first.returncode in (0, 2), first.stderr

def snapshot(root):
    return {str(p.relative_to(root)): sha256_file(path=p)
            for p in root.rglob('*') if p.is_file()}

saved = snapshot(state)
result_files = {p: h for p, h in saved.items() if '/results/' in '/' + p}
assert result_files, first.stdout
source_files = {p: sha256_file(path=source/p) for p in (
    'config/company_registry.csv', 'evidence/requests_log.csv',
    'evidence/requests_log_manifest.json')}
stream = io.StringIO()
with patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')), \
     patch('vnext.ordinary_current_update.create_saved_result',
           side_effect=AssertionError('Unchanged task must not prepare/compute/write result')), \
     patch('vnext.calculator.calculate_metric', side_effect=AssertionError('No graph calculation')), \
     patch('vnext.calculator.calculate_observation_metric',
           side_effect=AssertionError('No observation calculation')):
    started = time.monotonic()
    with contextlib.redirect_stdout(stream):
        repeat_exit = main(args)
    repeat_seconds = time.monotonic()-started
repeat = json.loads(stream.getvalue())
assert repeat_exit in (0, 2), stream.getvalue()
assert repeat['metrics'][0]['status'] == 'NO_SOURCE_CONTENT_CHANGE', stream.getvalue()
assert repeat['metrics'][0]['calculation_performed'] is False
assert repeat['metrics'][0]['new_candidate_created'] is False
assert result_files == {p: h for p, h in snapshot(state).items() if '/results/' in '/' + p}
assert source_files == {p: sha256_file(path=source/p) for p in source_files}

before_read = snapshot(state)
started = time.monotonic()
read = subprocess.run([sys.executable, 'tools/vnext_company.py', 'results',
    '--company', 'marriott_international', '--state-root', str(state),
    '--output-root', str(reader)], cwd=program, env=env, capture_output=True, text=True)
read_seconds = time.monotonic()-started
assert read.returncode == 0, read.stderr
assert before_read == snapshot(state)
rows = list(csv.DictReader((reader/'metrics_matrix.csv').open()))
assert len(rows) == 1 and rows[0]['value'] == '26186000000', rows
assert rows[0]['unit'] == 'USD' and rows[0]['cik'] == '1048286'
assert rows[0]['period_start'] == '2025-01-01' and rows[0]['period_end'] == '2025-12-31'
citations = list(csv.DictReader((reader/'metric_evidence.csv').open()))
assert citations and all(r['source_url'].startswith('https://') for r in citations)
record = {'baseline_main': '63a340ca38db6054c44bef53e63bb5827b0f07ce',
    'baseline_code_root': str(baseline), 'candidate_code_root': str(program),
    'tested_tree': 'uncommitted normal main merge and precise controller conflict resolution',
    'source_root': str(source), 'state_root': str(state), 'cli_args': args,
    'first_seconds_including_process_start': first_seconds, 'first_exit': first.returncode,
    'repeat_seconds_in_process': repeat_seconds, 'repeat_exit': repeat_exit,
    'independent_read_seconds': read_seconds, 'independent_read_exit': read.returncode,
    'repeat_report': repeat, 'rows': rows, 'citation_rows': citations,
    'result_files_preserved': result_files, 'all_state_read_unchanged': True,
    'source_log_registry_unchanged': True, 'calls': {'sec': 0, 'provider': 0, 'paid': 0}}
(evidence/'main-63a-actual-company.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: record[k] for k in ('first_seconds_including_process_start',
    'first_exit', 'repeat_seconds_in_process', 'repeat_exit',
    'independent_read_seconds', 'independent_read_exit')}, indent=2))
