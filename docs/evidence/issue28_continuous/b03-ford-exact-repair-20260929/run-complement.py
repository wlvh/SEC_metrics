"""Rebuild Ford's 34 unaffected ordinary routes under the current closure."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = Path('/private/tmp/issue28-ford-b03-complement-20260929/state')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
processing = json.loads((HERE/'processing.json').read_text())
source = Path(processing['processing_root'])
assert not STATE.exists()
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.normal_run_v3 import _policy, update_metric_ids
    from vnext.ordinary_processing_source import verify_processing_source
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    metrics = [metric for metric in _policy(ROOT)['metric_ids']
               if metric not in {'B03', 'B06'}]
    assert len(metrics) == 34 and len(set(metrics)) == 34
    assert set(metrics) <= set(update_metric_ids())
    verified_before = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source, requirement=requirement)
    assert verified_before['snapshot_id'] == processing['source_snapshot_id']
    import vnext_normal_update
    output = io.StringIO()
    args = ['--process', '--company', 'ford_motor_company', '--data-root',
            str(source), '--state-root', str(STATE)]
    for metric in metrics:
        args += ['--metric', metric]
    with contextlib.redirect_stdout(output):
        rc = vnext_normal_update.main(args)
    report = json.loads(output.getvalue())
    (HERE/'complement-report.json').write_text(json.dumps(report,
        ensure_ascii=False, indent=2) + '\n')
    verified_after = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source, requirement=requirement)
company, = report['companies']
rows = []
for row in company.get('metrics', []):
    result = (row.get('last_verified_candidate') or {}).get('results', {}).get(
        row['metric_id'])
    rows.append({'metric_id': row['metric_id'], 'status': row['status'],
        'result_id': None if result is None else result['result_id'],
        'value': None if result is None else result['value'],
        'reason_code': None if result is None else result['reason_code']})
body = {'record_type': 'ISSUE28_FORD_B03_CURRENT_CLOSURE_34_COMPLEMENT',
    'source_snapshot_id': processing['source_snapshot_id'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'normal_cli_return_code': rc, 'company_status': company['status'],
    'selected_metric_ids': metrics, 'rows': rows,
    'old_semantic_exports_disabled': disabled,
    'source_unchanged': verified_before == verified_after,
    'original_claims_source_and_active_unchanged': before ==
        {key: digest(path) for key, path in originals.items()},
    'new_real_calls': [0, 0, 0], 'formal_adoption': False,
    'all390_acceptance': False}
(HERE/'complement.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'company_status': company['status'],
    'ready': sum(row['status'] == 'CANDIDATE_READY' for row in rows),
    'metric_count': len(rows), 'calls': [0, 0, 0]}, sort_keys=True), flush=True)
assert rc == 0 and company['status'] == 'UPDATES_READY'
assert len(rows) == 34 and [row['metric_id'] for row in rows] == metrics
assert all(row['status'] == 'CANDIDATE_READY' and row['result_id'] for row in rows)
assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
assert body['source_unchanged'] and body['original_claims_source_and_active_unchanged']
