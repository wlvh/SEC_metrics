"""Exercise the explicit D02 successor through the current normal CLI offline."""
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


ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-d02-versioned-v2-20261002')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protected = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ROOT/'evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {name: digest(path) for name, path in protected.items()}
assert not WORK.exists(), 'D02_PRIVATE_ROOT_ALREADY_EXISTS'
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    import vnext_normal_update
    capture = io.StringIO()
    started = time.monotonic()
    with contextlib.redirect_stdout(capture):
        rc = vnext_normal_update.main(['--process', '--company', 'lumen_technologies',
            '--metric', 'D02', '--data-root', str(ROOT),
            '--state-root', str(WORK/'state')])
    elapsed = time.monotonic() - started
report = json.loads(capture.getvalue())
company, = report['companies']
metric, = company['metrics']
assert metric['status'] == 'CANDIDATE_READY' and rc == 0
candidate = metric['last_verified_candidate']
attempt = metric['attempt_id']
run = WORK/'state/lumen_technologies/metrics/D02-item8-v2/attempts'/attempt/'runs/D02'
records = [json.loads(line) for line in (run/'records.jsonl').read_bytes().splitlines()]
selected = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
              and row['metric_id'] == 'D02')
evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
indexes = {(row['section_id'], row['block_index']) for row in selected['selected'].values()}
assert ('ITEM_8', 1670) not in indexes and len(indexes) == 14
assert result['result_id'] == candidate['results']['D02']['result_id']
assert evidence['status'] == 'PASS'
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
old = json.loads((ROOT/'docs/evidence/issue28_continuous/'
                  'collab-d02-lumen-20261002/audit.json').read_text())
assert result['result_id'] != old['result_id']
after = {name: digest(path) for name, path in protected.items()}
summary = {'record_type': 'ISSUE28_D02_ITEM8_V2_PRIVATE_NORMAL_UPDATE',
    'tested_tree': 'UNCOMMITTED_WORKTREE_WITH_BOUND_V13_V14_IDS',
    'code_root': str(ROOT), 'data_root': str(ROOT),
    'requirement_closure_hash': json.loads((HERE/'binding-after.json').read_text())['child_requirement_closure_hash'],
    'elapsed_seconds': round(elapsed, 3), 'cli_return_code': rc,
    'status': metric['status'], 'attempt_id': attempt,
    'run_id': json.loads((run/'manifest.json').read_text())['run_id'],
    'old_result_id_withdrawn': old['result_id'], 'new_private_result_id': result['result_id'],
    'old_selected_count': 15, 'new_selected_count': len(indexes),
    'removed_known_block': 1670, 'native_evidence_status': evidence['status'],
    'new_result_content_acceptance': False, 'current_390_credit': False,
    'legacy_exports_disabled': disabled,
    'protected_claims_source_log_active_unchanged': before == after,
    'reported_calls': report['calls'], 'new_real_calls': [0, 0, 0],
    'production_authorized': False}
(HERE/'run.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': summary['status'], 'new_result_id':result['result_id'],
                  'selected':len(indexes),'elapsed_seconds':summary['elapsed_seconds']}),
      flush=True)
assert before == after and report['calls'] == {'provider':0,'paid':0,'sec':0}
