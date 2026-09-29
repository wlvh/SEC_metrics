"""Independently reopen the private Ford B03 native Run and source proof."""
import hashlib
import importlib.util
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
created = json.loads((HERE/'private-result.json').read_text())
source = Path(processing['processing_root'])
metric_root = PRIVATE/'state-repair/ford_motor_company/metrics/B03'
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext import ordinary_b03_scope_update as b03
    from vnext import ordinary_update_cycle as cycle
    from vnext.canonical import strict_json_file
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import verify_processing_source
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source, requirement=requirement)
    assert verified['snapshot_id'] == processing['source_snapshot_id']
    configuration = strict_json_file(path=metric_root/'configuration.json')
    state = cycle._state(metric_root, configuration)
    assert state['successful_attempt'] == created['attempt_id']
    terminal = cycle._terminal(metric_root, state['successful_attempt'])
    result = b03._verify_candidate(metric_root, terminal, configuration)['B03']
    assert result['result_id'] == created['result_id']
    assert result['value'] == created['value']
    assert result['publication'] == 'PUBLISHED'
    assert terminal['metrics']['B03']['result_id'] == result['result_id']
    assert state['latest_attempt'] == state['successful_attempt']
    historical = json.loads((ROOT/
        'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json').read_text())
    old, = [row for row in historical['rows']
        if row['company_id'] == 'ford_motor_company' and row['metric_id'] == 'B03']
    assert old['implementation_identity']['result_id'] == \
        created['old_historical_result_id_retained']
    assert old['implementation_identity']['result_id'] != result['result_id']
    after_source = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs',
        processing_root=source, requirement=requirement)
assert verified == after_source
assert before == {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_FORD_B03_EXACT_NATIVE_COLD_READ',
    'source_snapshot_id': verified['snapshot_id'],
    'result_id': result['result_id'], 'value': result['value'],
    'reason_code': result['reason_code'],
    'old_historical_result_id_retained':
        old['implementation_identity']['result_id'],
    'successful_attempt': state['successful_attempt'],
    'saved_terminal_id': terminal['record_id'],
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False, 'all390_acceptance': False}
(HERE/'cold.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'result_id': result['result_id'],
    'value': result['value'], 'calls': [0, 0, 0]}, sort_keys=True), flush=True)
