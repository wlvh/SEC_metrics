"""Independent-process cold read of two successes and one retained failure."""

import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = Path('/private/tmp/issue28-marriott-b03-failure-isolation-20260930/state')
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(root):
    return {str(path.relative_to(root)): digest(path) for path in root.rglob('*')
            if path.is_file()}


def main():
    saved = json.loads((HERE / 'run.json').read_text())
    assert saved['metric_statuses'] == {'B01': 'CANDIDATE_READY',
        'B03': 'EXECUTION_FAILED', 'C04': 'CANDIDATE_READY'}
    originals = {'claims': LEDGER / 'claims.jsonl',
        'source_log': LEDGER / 'source-inputs/evidence/requests_log.csv',
        'active': ROOT / 'outputs/active_publication.json'}
    before = {key: digest(path) for key, path in originals.items()}
    state_before = tree(STATE)
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         probe.legacy_disabled() as disabled:
        from vnext import ordinary_update_cycle as ordinary
        from vnext import c04_update_cycle as c04
        from vnext.canonical import strict_json_file
        from vnext.continuous_call_policy import REQUIREMENT_ID
        from vnext.ordinary_processing_source import verify_processing_source
        from vnext.requirements import load_requirement_snapshot
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / REQUIREMENT_ID)
        assert requirement['requirement_closure_hash'] == saved['requirement_closure_hash']
        source = verify_processing_source(acquisition_root=LEDGER / 'source-inputs',
            processing_root=Path(saved['source_root']), requirement=requirement)
        assert source['snapshot_id'] == saved['source_snapshot_id']
        rows = {}
        for metric, suffix, verifier in (
            ('B01', 'B01', ordinary._verify_candidate),
            ('C04', 'C04-registration-v3', c04._verify_candidate)):
            root = STATE / 'marriott_international/metrics' / suffix
            configuration = strict_json_file(path=root / 'configuration.json')
            pointer = ordinary._state(root, configuration)
            assert pointer['successful_attempt'] is not None
            terminal = ordinary._terminal(root, pointer['successful_attempt'])
            result = verifier(root, terminal, configuration)[metric]
            assert result['result_id'] == saved['successful_result_ids'][metric]
            assert result['publication'] == 'PUBLISHED'
            rows[metric] = {'result_id': result['result_id'],
                'publication': result['publication'],
                'reason_code': result['reason_code'],
                'period_end': result['period_end'], 'value': result['value']}
            if metric == 'C04':
                assert configuration['route'] == c04.ROUTE
        b03_root = STATE / 'marriott_international/metrics/B03'
        b03_config = strict_json_file(path=b03_root / 'configuration.json')
        b03_pointer = ordinary._state(b03_root, b03_config)
        b03_terminal = ordinary._terminal(b03_root, saved['b03_attempt_id'])
        assert b03_pointer['successful_attempt'] is None
        assert b03_terminal['status'] == 'EXECUTION_FAILED'
        assert b03_terminal['error']['reason'] == saved['b03_error']
    assert rows['B01']['period_end'] == rows['C04']['period_end'] == '2025-12-31'
    assert rows['B01']['value'] == '26186000000' and rows['C04']['value'] == '0'
    assert disabled == saved['old_semantic_exports_disabled']
    assert before == {key: digest(path) for key, path in originals.items()}
    assert state_before == tree(STATE)
    body = {'record_type': 'ISSUE28_MARRIOTT_B03_FAILURE_ISOLATED_COLD_READ',
        'source_snapshot_id': saved['source_snapshot_id'],
        'cold_results': rows,
        'b03_terminal_status': b03_terminal['status'],
        'b03_successful_attempt': b03_pointer['successful_attempt'],
        'old_semantic_exports_disabled': disabled,
        'private_state_tree_unchanged': True,
        'original_claims_source_log_and_active_unchanged': True,
        'new_real_calls': [0, 0, 0],
        'new_complete_company_or_390_credit': 0,
        'formal_adoption': False}
    (HERE / 'read.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'cold_results': {key: row['result_id']
        for key, row in rows.items()},
        'b03_terminal_status': body['b03_terminal_status'],
        'b03_successful_attempt': None,
        'private_state_tree_unchanged': True,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
