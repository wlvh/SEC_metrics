"""Candidate first/repeat/read; compare the already executed main reference."""
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

evidence = Path(__file__).resolve().parent
baseline = json.loads((evidence/'main-63a-actual-company.json').read_text())
source = Path(baseline['source_root'])
base = Path(tempfile.mkdtemp(prefix='issue28-proof-candidate-new-'))
state, output, reader = (base/p for p in ('state', 'output', 'reader'))
args = ['run', '--company', 'marriott_international', '--metric', 'B01',
        '--source-root', str(source), '--work-dir', str(state), '--output-dir', str(output)]

def snapshot(root):
    return {str(p.relative_to(root)): sha256_file(path=p)
            for p in root.rglob('*') if p.is_file()}

stream = io.StringIO()
with patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')):
    started = time.monotonic()
    with contextlib.redirect_stdout(stream):
        first_exit = main(args)
    first_seconds = time.monotonic()-started
    protected = {p: h for p, h in snapshot(state).items() if '/results/' in '/'+p}
    started = time.monotonic()
    with patch('vnext.ordinary_current_update.create_saved_result',
               side_effect=AssertionError('Unchanged task cannot calculate')), \
         patch('vnext.calculator.calculate_metric', side_effect=AssertionError('No graph calculate')), \
         patch('vnext.calculator.calculate_observation_metric', side_effect=AssertionError('No observation calculate')), \
         contextlib.redirect_stdout(stream):
        repeat_exit = main(args)
    repeat_seconds = time.monotonic()-started
assert protected == {p: h for p, h in snapshot(state).items() if '/results/' in '/'+p}
before_read = snapshot(state)
started = time.monotonic()
read = subprocess.run([sys.executable, 'tools/vnext_company.py', 'results',
    '--company', 'marriott_international', '--state-root', str(state),
    '--output-root', str(reader)], capture_output=True, text=True)
read_seconds = time.monotonic()-started
assert read.returncode == 0 and snapshot(state) == before_read, read.stderr
rows = list(csv.DictReader((reader/'metrics_matrix.csv').open()))
keys = ('metric_id', 'company_id', 'cik', 'value', 'unit', 'status',
        'period_start', 'period_end', 'fiscal_year', 'result_id')
assert [{k: r[k] for k in keys} for r in rows] == [
    {k: r[k] for k in keys} for r in baseline['rows']], rows
assert first_exit == repeat_exit == 0, stream.getvalue()
assert rows[0]['local_metric_status'] == 'NO_SOURCE_CONTENT_CHANGE'
citations = list(csv.DictReader((reader/'metric_evidence.csv').open()))
assert citations
record = {'code_root': str(Path.cwd()), 'tested_mode': 'uncommitted main merge',
    'source_root': str(source), 'state_root': str(state), 'args': args,
    'first_seconds_in_process': first_seconds, 'repeat_seconds_in_process': repeat_seconds,
    'independent_read_seconds': read_seconds, 'first_exit': first_exit,
    'repeat_exit': repeat_exit, 'read_exit': read.returncode,
    'baseline_business_fields_and_result_id_equal': True, 'rows': rows,
    'citation_rows': citations, 'protected_result_files': protected,
    'independent_read_all_state_unchanged': True, 'stdout': stream.getvalue(),
    'calls': {'sec': 0, 'provider': 0, 'paid': 0}}
(evidence/'new-company-actual.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: record[k] for k in ('first_seconds_in_process',
    'repeat_seconds_in_process', 'independent_read_seconds', 'first_exit', 'repeat_exit', 'read_exit')}, indent=2))
