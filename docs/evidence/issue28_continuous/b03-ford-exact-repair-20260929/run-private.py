"""Exercise the current Ford B03 route from original #28 saved sources."""
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
PRIVATE = Path('/private/tmp/issue28-b03-ford-exact-20260929')
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
state = PRIVATE/'state'
assert not state.exists()
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import verify_processing_source
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    before_source = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source, requirement=requirement)
    assert before_source['snapshot_id'] == processing['source_snapshot_id']
    import vnext_normal_update
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = vnext_normal_update.main(['--process', '--company',
            'ford_motor_company', '--metric', 'B03', '--data-root',
            str(source), '--state-root', str(state)])
    report = json.loads(output.getvalue())
    (HERE/'private-report.json').write_text(json.dumps(report,
        ensure_ascii=False, indent=2) + '\n')
    after_source = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source, requirement=requirement)
company, = report['companies']
metric, = company['metrics']
candidate = metric['last_verified_candidate']['results']['B03']
assert rc == 0 and company['status'] == 'UPDATES_READY'
assert metric['status'] == 'CANDIDATE_READY'
assert candidate['value'] == '-0.007128858795196163766173431518'
assert candidate['publication'] == 'PUBLISHED'
assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
assert before_source == after_source
after = {key: digest(path) for key, path in originals.items()}
assert before == after
body = {'record_type': 'ISSUE28_FORD_B03_EXACT_PRIVATE_NORMAL_UPDATE',
    'source_snapshot_id': processing['source_snapshot_id'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'normal_cli_return_code': rc, 'company_status': company['status'],
    'metric_status': metric['status'],
    'attempt_id': metric['attempt_id'],
    'result_id': candidate['result_id'],
    'value': candidate['value'], 'reason_code': candidate['reason_code'],
    'publication': candidate['publication'],
    'old_historical_result_id_retained':
        'sha256:1829d73dac66a195a590ab84ea1f1d1800a77fae60d828b6f37d5cbeec2abd30',
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False, 'all390_acceptance': False}
(HERE/'private-result.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'status': body['company_status'],
    'result_id': body['result_id'], 'value': body['value'],
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
