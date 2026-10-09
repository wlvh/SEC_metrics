"""One private Paramount 36-metric normal CLI run from authenticated #28 sources."""
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
WORK = Path('/private/tmp/issue28-paramount_skydance_paramount_global-current-36-cli-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = Path('/private/tmp/issue28-marriott-cli-b01-c04-20260929/sources/'
    'cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
assert not WORK.exists()
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
    metrics = _policy(ROOT)['metric_ids']
    assert len(metrics) == len(set(metrics)) == 36
    assert set(metrics) <= set(update_metric_ids())
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=SOURCE, requirement=requirement)
    assert verified['snapshot_id'] == 'sha256:' + SOURCE.name
    import vnext_normal_update
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        rc = vnext_normal_update.main(['--process', '--company', 'paramount_skydance_paramount_global',
            '--data-root', str(SOURCE), '--state-root', str(WORK/'state')])
    report = json.loads(capture.getvalue())
company, = report['companies']
rows = []
for item in company.get('metrics', []):
    metric = item['metric_id']
    result = (item.get('last_verified_candidate') or {}).get('results', {}).get(metric)
    rows.append({'metric_id': metric, 'status': item['status'],
        'error_type': item.get('error_type'), 'reason': item.get('reason'),
        'terminal_error': (item.get('terminal') or {}).get('error'),
        'result_id': None if result is None else result['result_id'],
        'publication': None if result is None else result['publication'],
        'result_reason': None if result is None else result['reason_code']})
    print(metric, item['status'], flush=True)
after = {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_PARAMOUNT_SKYDANCE_PARAMOUNT_GLOBAL_36_NORMAL_CLI_PRIVATE_UPDATE',
    'tested_product_head': 'c88ed896aaa704fc2a47abd7f48b4c4ae05b5865',
    'company_id': 'paramount_skydance_paramount_global',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'source_snapshot_id': verified['snapshot_id'],
    'normal_cli_return_code': rc, 'status': company['status'],
    'metric_count': len(rows), 'rows': rows,
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': before == after,
    'reported_calls': report['calls'],
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False, 'all390_acceptance': False}
(HERE/'result.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'], 'metric_count': len(rows),
    'status_counts': {status: sum(row['status'] == status for row in rows)
        for status in sorted({row['status'] for row in rows})},
    'originals_unchanged': body['original_claims_source_and_active_unchanged']},
    sort_keys=True), flush=True)
assert before == after
assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
assert len(rows) == 36 and {row['metric_id'] for row in rows} == set(metrics)
