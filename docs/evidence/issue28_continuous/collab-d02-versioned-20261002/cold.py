"""Separate-process D02 installed Run and ordinary update re-entry."""
import contextlib
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
WORK = Path('/private/tmp/issue28-d02-versioned-20261002')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]
spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


first = json.loads((HERE/'run.json').read_text())
assert first['status'] == 'CANDIDATE_READY'
root = WORK/'state/lumen_technologies/metrics/D02-item8-v1'
run = root/'attempts'/first['attempt_id']/'runs/D02'
data = root/'attempts'/first['attempt_id']/'data'
protected = {'claims': Path('/Users/lyuhongwang/.local/state/sec_metrics/'
                            'issue28-2026-09-13/claims.jsonl'),
             'source_log': ROOT/'evidence/requests_log.csv',
             'active': ROOT/'outputs/active_publication.json'}
before = {name: digest(path) for name, path in protected.items()}
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.ordinary_projection import render_ordinary_run
    start = time.monotonic()
    rendered = render_ordinary_run(data_root=data, run_dir=run)
    import vnext_normal_update
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        rc = vnext_normal_update.main(['--process','--company','lumen_technologies',
            '--metric','D02','--data-root',str(ROOT),
            '--state-root',str(WORK/'state')])
    elapsed = time.monotonic()-start
report = json.loads(capture.getvalue())
company, = report['companies']
metric, = company['metrics']
candidate = metric['last_verified_candidate']
assert rendered['receipt']['result_id'] == first['new_private_result_id']
assert candidate['results']['D02']['result_id'] == first['new_private_result_id']
after = {name: digest(path) for name, path in protected.items()}
summary = {'record_type': 'ISSUE28_D02_ITEM8_PRIVATE_INSTALLED_COLD_READ',
    'elapsed_seconds': round(elapsed,3), 'cli_return_code': rc,
    'status': metric['status'], 'new_candidate_created': metric['new_candidate_created'],
    'first_attempt_retained': metric['successful_attempt'] == first['attempt_id'],
    'result_id': first['new_private_result_id'],
    'public_row_sha256': hashlib.sha256(rendered['files']['metrics_matrix.csv']).hexdigest(),
    'legacy_exports_disabled': disabled,
    'protected_claims_source_log_active_unchanged': before == after,
    'reported_calls': report['calls'], 'new_real_calls': [0,0,0],
    'current_390_credit': False, 'production_authorized': False}
(HERE/'cold.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key:summary[key] for key in (
    'status','result_id','new_candidate_created','elapsed_seconds')}), flush=True)
assert rc == 0 and metric['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert not metric['new_candidate_created'] and summary['first_attempt_retained']
assert before == after and report['calls'] == {'provider':0,'paid':0,'sec':0}
