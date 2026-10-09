"""Use current ordinary update code with existing real Enphase D04 receipts."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext import ordinary_update_cycle as cycle
from vnext.canonical import strict_json_file
from vnext.continuous_call_ledger import CallLedger, _FACTORY
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928')
COMPANY = 'enphase_energy'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sentinel_hashes():
    paths = (LEDGER/'binding.json', LEDGER/'claims.jsonl',
             LEDGER/'source-inputs/evidence/requests_log.csv',
             LEDGER/'source-inputs/evidence/requests_log_manifest.json',
             ROOT/'outputs/active_publication.json')
    return {str(path): digest(path) if path.is_file() else None for path in paths}


def deny_process(event, args):
    if event != 'subprocess.Popen':
        return
    command = str(args[0])
    argv = list(args[1])
    if Path(command).name != 'git' or len(argv) < 2 or argv[1] not in {
            'show', 'ls-files', 'rev-parse'}:
        raise AssertionError('UNAPPROVED_PROCESS')


sys.addaudithook(deny_process)
started = time.monotonic()
assert not STATE.exists(), 'PRIVATE_STATE_ROOT_ALREADY_EXISTS'
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_wiring_receipt(requirement=requirement)
ledger = CallLedger(factory=_FACTORY, root=LEDGER,
                    binding=strict_json_file(path=LEDGER/'binding.json'), live=True)
with ledger.locked():
    before = ledger.snapshot()
before_hashes = sentinel_hashes()
before_call_names = sorted(path.name for path in (LEDGER/'calls').iterdir())
error = None
result = None
network_attempts = []


def no_network(*args, **kwargs):
    network_attempts.append('blocked')
    raise AssertionError('NETWORK_FORBIDDEN')


try:
    with patch.object(socket.socket, 'connect', side_effect=no_network), \
         patch.object(socket, 'getaddrinfo', side_effect=no_network), \
         patch('sec_http.urlopen', side_effect=no_network):
        result = cycle.run_company(state_root=STATE,
            source_root=LEDGER/'source-inputs', company_id=COMPANY,
            metric_ids=['D04'], native_assessment_mode='LIVE',
            native_assessment_ledger=ledger)
except Exception as failure:
    error = {'error_type': type(failure).__name__, 'reason': str(failure)}

with ledger.locked():
    after = ledger.snapshot()
after_hashes = sentinel_hashes()
after_call_names = sorted(path.name for path in (LEDGER/'calls').iterdir())
row = None if result is None else result['metrics'][0]
verified = None if row is None else row.get('last_verified_candidate')
native_result = None if verified is None else verified['results'].get('D04')
report = {
    'status': 'ERROR' if error else row['status'],
    'company_id': COMPANY, 'metric_id': 'D04',
    'source_root': str(LEDGER/'source-inputs'), 'state_root': str(STATE),
    'current_requirement_closure': requirement['requirement_closure_hash'],
    'prior_real_ordinals': [173, 174, 175, 176, 177, 178],
    'update_status': None if result is None else result['status'],
    'attempt_id': None if row is None else row.get('attempt_id'),
    'successful_attempt': None if row is None else row.get('successful_attempt'),
    'result_id': None if native_result is None else native_result['result_id'],
    'result_publication': None if native_result is None else native_result['publication'],
    'reason_code': None if native_result is None else native_result['reason_code'],
    'row_files': None if row is None else row.get('terminal', {}).get('metrics', {}).get('D04', {}).get('files'),
    'ledger_counts_before': before['counts'],
    'ledger_counts_after': after['counts'],
    'ledger_rows_before_after': [len(before['rows']), len(after['rows'])],
    'ledger_call_names_unchanged': before_call_names == after_call_names,
    'sentinel_hashes_unchanged': before_hashes == after_hashes,
    'network_attempts': network_attempts,
    'new_real_calls': [0, 0, 0], 'production_authorized': False,
    'seconds': round(time.monotonic()-started, 3), 'error': error,
}
(HERE/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: report[key] for key in ('status', 'update_status',
    'result_id', 'reason_code', 'ledger_counts_before', 'ledger_counts_after',
    'ledger_call_names_unchanged', 'sentinel_hashes_unchanged', 'seconds',
    'error')}, ensure_ascii=False), flush=True)
assert error is None and result['status'] == 'UPDATES_READY'
assert row['status'] == 'CANDIDATE_READY' and native_result is not None
assert before['counts'] == after['counts'] and before_call_names == after_call_names
assert before_hashes == after_hashes and not network_attempts
