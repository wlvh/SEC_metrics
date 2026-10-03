"""Independently re-import the installed C02 runtime and replay its private Run."""
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
WORK = Path('/private/tmp/issue28-c02-composition-enphase-v3-20261001')
DATA = WORK / 'data'
RUN = WORK / 'run'
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(DATA), str(DATA / 'scripts')]

from vnext.ordinary_projection import render_ordinary_run
from vnext.run_store import _mechanically_replay_open_run


def tree_identity(path):
    rows = []
    for file in sorted(p for p in path.rglob('*')
                       if p.is_file() and '__pycache__' not in p.parts):
        assert not file.is_symlink()
        rows.append((str(file.relative_to(path)), hashlib.sha256(file.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(), len(rows)


before = (tree_identity(DATA), tree_identity(RUN))
expected = json.loads((HERE / 'enphase-summary.json').read_text())
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    manifest, records, _ = _mechanically_replay_open_run(
        run_dir=RUN, repo_root=DATA, require_complete_results=True)
    rendered = render_ordinary_run(data_root=DATA, run_dir=RUN)
after = (tree_identity(DATA), tree_identity(RUN))
assert before == after
result = next(r for r in records if r.get('record_type') == 'METRIC_RESULT'
              and r.get('metric_id') == 'C02')
candidate = next(r for r in records if r.get('record_type') == 'DETERMINISTIC_TEXT_CANDIDATE')
blocks = {r['block_index'] for r in candidate['selected'].values()}
public = next(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
assert result['result_id'] == expected['result_id']
assert manifest['run_id'] == expected['run_id']
assert len(blocks) == expected['candidate_count'] and 294 not in blocks and 210 in blocks
assert public['metric_id'] == 'C02' and public['status'] == expected['public_row_status']
body = {'record_type': 'ISSUE28_C02_COMPOSITION_INSTALLED_COLD_READ',
        'result_id': result['result_id'], 'run_id': manifest['run_id'],
        'public_row_status': public['status'], 'candidate_count': len(blocks),
        'data_file_count': before[0][1], 'run_file_count': before[1][1],
        'trees_byte_identical_before_after': True, 'calls': [0, 0, 0],
        'production_authorized': False}
(HERE / 'enphase-cold.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True))
