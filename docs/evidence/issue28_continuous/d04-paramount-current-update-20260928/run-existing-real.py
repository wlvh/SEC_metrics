"""Run current ordinary D04 update from Paramount's existing real receipts."""
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
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
STATE = Path('/private/tmp/issue28-d04-paramount-normal-77f-20260928')
ORIGINAL = ROOT/'docs/evidence/issue28_continuous/batch33-authorization/d04-paramount-real'
COMPANY = 'paramount_skydance_paramount_global'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sentinels():
    paths = (LEDGER/'binding.json', LEDGER/'claims.jsonl',
             LEDGER/'source-inputs/evidence/requests_log.csv',
             LEDGER/'source-inputs/evidence/requests_log_manifest.json',
             ROOT/'outputs/active_publication.json')
    return {str(path): digest(path) if path.is_file() else None for path in paths}


def deny_process(event, args):
    if event != 'subprocess.Popen':
        return
    command = str(args[0]); argv = list(args[1])
    if Path(command).name != 'git' or len(argv) < 2 or argv[1] not in {
            'show', 'ls-files', 'rev-parse'}:
        raise AssertionError('UNAPPROVED_PROCESS')


sys.addaudithook(deny_process)
assert not STATE.exists(), 'PRIVATE_STATE_ROOT_ALREADY_EXISTS'
original = json.loads((ORIGINAL/'finish-summary.json').read_text())
original_cold = json.loads((ORIGINAL/'cold-summary.json').read_text())
assert original['status'] == 'COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS'
assert original_cold['status'] == 'PASS_PERSISTED_COMPLETE_CANDIDATE_AND_COLD_READ'
assert original['result_id'] == original_cold['result_id']
assert original['original_call_ordinals'] == list(range(179, 189))
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_wiring_receipt(requirement=requirement)
ledger = CallLedger(factory=_FACTORY, root=LEDGER,
                    binding=strict_json_file(path=LEDGER/'binding.json'), live=True)
with ledger.locked():
    before = ledger.snapshot()
before_hashes = sentinels()
before_names = sorted(path.name for path in (LEDGER/'calls').iterdir())
network_attempts = []


def no_network(*args, **kwargs):
    network_attempts.append('blocked')
    raise AssertionError('NETWORK_FORBIDDEN')


started = time.monotonic()
error = None
outcome = None
try:
    with patch.object(socket.socket, 'connect', side_effect=no_network), \
         patch.object(socket, 'getaddrinfo', side_effect=no_network), \
         patch('sec_http.urlopen', side_effect=no_network):
        outcome = cycle.run_company(state_root=STATE,
            source_root=LEDGER/'source-inputs', company_id=COMPANY,
            metric_ids=['D04'], native_assessment_mode='LIVE',
            native_assessment_ledger=ledger)
except Exception as failure:
    error = {'error_type': type(failure).__name__, 'reason': str(failure)}
with ledger.locked():
    after = ledger.snapshot()
after_hashes = sentinels()
after_names = sorted(path.name for path in (LEDGER/'calls').iterdir())

row = None if outcome is None else outcome['metrics'][0]
verified = None if row is None else row.get('last_verified_candidate')
result = None if verified is None else verified['results'].get('D04')
manifest = None
public_row = None
if result is not None:
    work = STATE/'metrics/D04/attempts'/row['successful_attempt']
    manifest = json.loads((work/'runs/D04/manifest.json').read_text())
    with (work/'rows/D04/metrics_matrix.csv').open(newline='') as stream:
        public_row = next(csv.DictReader(stream))
delta = [a-b for a,b in zip(after['counts'], before['counts'])]
report = {'status': 'ERROR' if error else row['status'],
    'company_id': COMPANY, 'metric_id': 'D04',
    'source_root': str(LEDGER/'source-inputs'), 'state_root': str(STATE),
    'current_requirement_closure': requirement['requirement_closure_hash'],
    'original_call_ordinals': original['original_call_ordinals'],
    'original_source_id': original['source_id'],
    'original_run_id': original['run_id'],
    'original_result_id': original['result_id'],
    'update_status': None if outcome is None else outcome['status'],
    'attempt_id': None if row is None else row.get('attempt_id'),
    'successful_attempt': None if row is None else row.get('successful_attempt'),
    'current_run_id': None if manifest is None else manifest['run_id'],
    'current_result_id': None if result is None else result['result_id'],
    'result_publication': None if result is None else result['publication'],
    'reason_code': None if result is None else result['reason_code'],
    'public_row': None if public_row is None else {k: public_row[k] for k in
        ('company','metric_id','status','value','fiscal_year','period_start','period_end')},
    'row_files': None if row is None else row.get('terminal',{}).get('metrics',{}).get('D04',{}).get('files'),
    'ledger_counts_before_after': [before['counts'], after['counts']],
    'ledger_rows_before_after': [len(before['rows']), len(after['rows'])],
    'ledger_call_names_unchanged': before_names == after_names,
    'sentinel_hashes_unchanged': before_hashes == after_hashes,
    'network_attempts': network_attempts,
    'new_real_calls': delta, 'production_authorized': False,
    'seconds': round(time.monotonic()-started, 3), 'error': error}
(HERE/'result.json').write_text(json.dumps(report, ensure_ascii=False,
                                       indent=2)+'\n')
print(json.dumps({k: report[k] for k in ('status','update_status','current_result_id',
    'current_run_id','public_row','new_real_calls','sentinel_hashes_unchanged',
    'seconds','error')}, ensure_ascii=False), flush=True)
assert error is None and outcome['status'] == 'UPDATES_READY'
assert row['status'] == 'CANDIDATE_READY' and result is not None
assert result['result_id'] == original['result_id']
assert result['reason_code'] == original['reason_code']
assert public_row['status'] == 'TEXT_QUAL' and public_row['value'] == ''
assert public_row['fiscal_year'] == '2025'
assert delta == [0, 0, 0] and before_names == after_names
assert before_hashes == after_hashes and not network_attempts
