"""Zero-egress current-head D04 Run from existing Enphase real receipts."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]

from vnext import ordinary_update_cycle as cycle
from vnext.canonical import strict_json_file
from vnext.continuous_call_ledger import CallLedger, _FACTORY
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

HERE = REPO / 'docs/evidence/issue28_continuous/d04-unified-release-20260928'
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = Path('/private/tmp/issue28-d04-enphase-release-current-dea6-20260928')
OLD = Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928/metrics/D04')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root):
    return {str(path.relative_to(root)): sha(path)
            for path in root.rglob('*') if path.is_file()}


def forbidden(*_args, **_kwargs):
    raise AssertionError('CURRENT_D04_REBUILD_NETWORK_FORBIDDEN')


def main():
    assert not STATE.exists(), 'PRIVATE_STATE_ROOT_ALREADY_EXISTS'
    old_pointer = strict_json_file(path=OLD / 'current.json')
    old_work = OLD / 'attempts' / old_pointer['successful_attempt']
    old_tree = tree(old_work)
    old_terminal = strict_json_file(path=old_work / 'terminal.json')
    old_result_id = old_terminal['metrics']['D04']['result_id']
    requirement = load_requirement_snapshot(
        snapshot_dir=REPO / 'requirements/issue_28_v14')
    validate_execution_authority(repo_root=REPO, requirement=requirement)
    validate_wiring_receipt(requirement=requirement)
    ledger = CallLedger(factory=_FACTORY, root=LEDGER,
        binding=strict_json_file(path=LEDGER / 'binding.json'), live=True)
    with ledger.locked():
        before = ledger.snapshot()
    immutable_paths = [LEDGER / 'binding.json', LEDGER / 'claims.jsonl',
        LEDGER / 'source-inputs/evidence/requests_log.csv',
        LEDGER / 'source-inputs/evidence/requests_log_manifest.json',
        REPO / 'outputs/active_publication.json']
    before_hashes = {str(path): sha(path) for path in immutable_paths}
    started = time.monotonic()
    result = None
    error = None
    try:
        with patch.object(socket.socket, 'connect', side_effect=forbidden), \
             patch.object(socket, 'getaddrinfo', side_effect=forbidden), \
             patch('sec_http.urlopen', side_effect=forbidden):
            result = cycle.run_company(state_root=STATE,
                source_root=LEDGER / 'source-inputs',
                company_id='enphase_energy', metric_ids=['D04'],
                native_assessment_mode='LIVE', native_assessment_ledger=ledger)
    except Exception as failure:
        error = {'type': type(failure).__name__, 'reason': str(failure)}
    with ledger.locked():
        after = ledger.snapshot()
    after_hashes = {str(path): sha(path) for path in immutable_paths}
    row = result['metrics'][0] if result is not None else None
    successful = row['successful_attempt'] if row is not None else None
    terminal = (strict_json_file(path=STATE / 'metrics/D04/attempts' /
        successful / 'terminal.json') if successful else None)
    run = (strict_json_file(path=STATE / 'metrics/D04/attempts' /
        successful / 'runs/D04/manifest.json') if successful else None)
    report = {'tested_head': 'dea6e4a0', 'status': 'ERROR' if error else row['status'],
        'update_status': None if result is None else result['status'],
        'state_root': str(STATE), 'source_root': str(LEDGER / 'source-inputs'),
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'old_result_id': old_result_id,
        'current_result_id': None if terminal is None else terminal['metrics']['D04']['result_id'],
        'current_run_id': None if run is None else run['run_id'],
        'old_success_tree_unchanged': tree(old_work) == old_tree,
        'ledger_counts_before': before['counts'],
        'ledger_counts_after': after['counts'],
        'ledger_rows_before_after': [len(before['rows']), len(after['rows'])],
        'ledger_and_active_bytes_unchanged': before_hashes == after_hashes,
        'new_real_calls': [0, 0, 0], 'production_authorized': False,
        'seconds': round(time.monotonic() - started, 3), 'error': error}
    (HERE / 'current-enphase-followup-result.json').write_text(json.dumps(report,
        ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    assert error is None and result['status'] == 'UPDATES_READY'
    assert row['status'] == 'CANDIDATE_READY' and terminal is not None
    assert report['old_result_id'] == report['current_result_id']
    assert report['old_success_tree_unchanged']
    assert before['counts'] == after['counts'] and len(before['rows']) == len(after['rows'])
    assert before_hashes == after_hashes


if __name__ == '__main__':
    main()
