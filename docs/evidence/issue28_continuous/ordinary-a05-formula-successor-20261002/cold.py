"""Separate-process reread of the bound A05 formula and success pointer."""
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-a05-formula-successor-20261002')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


first = json.loads((HERE/'result.json').read_text())
assert first['status'] == 'CANDIDATE_READY' and first['cli_return_code'] == 0
protected = {'claims':ACQUIRED/'claims.jsonl',
    'source_log':ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before = {key:digest(path) for key,path in protected.items()}
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    import vnext_normal_update
    capture = io.StringIO()
    started = time.monotonic()
    with contextlib.redirect_stdout(capture):
        rc = vnext_normal_update.main(['--process','--company','jpmorgan_chase',
            '--metric','A05','--data-root',first['processing_root'],
            '--state-root',str(WORK/'state')])
    elapsed = time.monotonic()-started
report = json.loads(capture.getvalue())
company, = report['companies']
metric, = company['metrics']
candidate = metric['last_verified_candidate']
row_path = Path(candidate['rows_root'])/'A05/metrics_matrix.csv'
row, = list(csv.DictReader(row_path.open()))
after = {key:digest(path) for key,path in protected.items()}
summary = {'record_type':'ISSUE28_A05_FORMULA_PRIVATE_COLD_READ',
    'elapsed_seconds':round(elapsed,3),'cli_return_code':rc,
    'status':metric['status'],'new_candidate_created':metric['new_candidate_created'],
    'new_attempt_id':metric['attempt_id'],
    'successful_attempt':metric['successful_attempt'],
    'previous_successful_attempt':metric['previous_successful_attempt'],
    'result_id':candidate['results']['A05']['result_id'],
    'formula':row['formula'],'public_row_sha256':digest(row_path),
    'old_successful_attempt_retained':metric['successful_attempt']==first['attempt_id'],
    'legacy_exports_disabled':disabled,
    'protected_source_ledger_and_active_unchanged':before==after,
    'reported_calls':report['calls'],'new_real_calls':[0,0,0],
    'production_authorized':False}
(HERE/'cold.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:summary[key] for key in ('status','result_id','formula',
    'new_candidate_created','elapsed_seconds')}),flush=True)
assert rc==0 and metric['status']=='NO_SOURCE_CONTENT_CHANGE'
assert not metric['new_candidate_created']
assert summary['result_id']==first['result_id']
assert summary['formula']==first['formula']
assert summary['public_row_sha256']==first['public_row_sha256']
assert summary['old_successful_attempt_retained']
assert before==after and report['calls']=={'provider':0,'paid':0,'sec':0}
