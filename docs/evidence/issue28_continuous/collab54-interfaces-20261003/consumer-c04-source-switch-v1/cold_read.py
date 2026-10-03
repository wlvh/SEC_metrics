"""Independently replay both retained C04 Runs after the source-view switch."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
RUNTIME = BASE / 'runtime'
summary = json.loads((Path(__file__).parent / 'summary.json').read_text())
os.environ['COMPANY_TEST_RUNTIME'] = str(RUNTIME)
os.environ['SEC_METRICS_SOURCE_TRUST_ROOT'] = str(BASE / 'source-trust')
# Reuse the existing test boundary without entering its CLI dispatcher.
guard = (BASE / 'guarded-cli.py').read_text().split("with patch.object(socket.socket,'connect'")[0]
exec(compile(guard, str(BASE / 'guarded-cli.py'), 'exec'))
sys.path[:0] = [str(RUNTIME), str(RUNTIME / 'scripts')]
from vnext.ordinary_projection import render_ordinary_run

rows = []
with patch.object(socket.socket, 'connect', side_effect=ValueError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo', side_effect=ValueError('DNS_FORBIDDEN')):
    for key in ('baseline_attempt', 'current_attempt'):
        work = Path(summary[key])
        before = {p.relative_to(work).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in work.rglob('*') if p.is_file()}
        start = time.monotonic()
        rendered = render_ordinary_run(data_root=work / 'data', run_dir=work / 'runs/C04')
        for name, data in rendered['files'].items():
            assert data == (work / 'rows/C04' / name).read_bytes()
        after = {p.relative_to(work).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in work.rglob('*') if p.is_file()}
        assert before == after
        rows.append({'attempt': str(work), 'seconds': round(time.monotonic() - start, 3),
                     'receipt': rendered['receipt'], 'row': rendered['row'],
                     'row_files_equal': True, 'installed_attempt_bytes_unchanged': True})
print(json.dumps({'status': 'PASS_INDEPENDENT_PROCESS_BOTH_OLD_AND_NEW_C04_RUNS',
                  'runtime': str(RUNTIME), 'runs': rows, 'new_calls': [0, 0, 0]}, indent=2))
