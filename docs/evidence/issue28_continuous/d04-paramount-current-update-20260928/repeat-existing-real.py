"""Repeat the same real Paramount D04 input without creating another Run."""
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


HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = Path('/private/tmp/issue28-d04-paramount-normal-77f-20260928')
HISTORY = STATE/'metrics/D04'
first = json.loads((HERE/'result.json').read_text())
original = first['successful_attempt']
assert original is not None


def tree(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def no_network(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


def deny_process(event, args):
    if event == 'subprocess.Popen':
        command = str(args[0]); argv = list(args[1])
        if Path(command).name != 'git' or len(argv) < 2 or argv[1] not in {
                'show', 'ls-files', 'rev-parse'}:
            raise AssertionError('UNAPPROVED_PROCESS')


sys.addaudithook(deny_process)
ledger = CallLedger(factory=_FACTORY, root=LEDGER,
                    binding=strict_json_file(path=LEDGER/'binding.json'), live=True)
with ledger.locked():
    before = ledger.snapshot()
saved_package = tree(HISTORY/'attempts'/original)
started = time.monotonic()
with patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    outcome = cycle.run_company(state_root=STATE,
        source_root=LEDGER/'source-inputs', company_id='paramount_skydance_paramount_global',
        metric_ids=['D04'], native_assessment_mode='LIVE',
        native_assessment_ledger=ledger)
with ledger.locked():
    after = ledger.snapshot()
row = outcome['metrics'][0]
verified = row['last_verified_candidate']
original_unchanged = tree(HISTORY/'attempts'/original) == saved_package
report = {'status': row['status'], 'company_status': outcome['status'],
          'first_successful_attempt': original,
          'repeat_attempt_id': row.get('attempt_id'),
          'successful_attempt_after_repeat': row.get('successful_attempt'),
          'new_candidate_created': row.get('new_candidate_created'),
          'result_id': verified['results']['D04']['result_id'],
          'original_success_package_unchanged': original_unchanged,
          'ledger_counts_before_after': [before['counts'], after['counts']],
          'ledger_rows_before_after': [len(before['rows']), len(after['rows'])],
          'new_real_calls': [0, 0, 0], 'production_authorized': False,
          'seconds': round(time.monotonic()-started, 3)}
(HERE/'repeat-result.json').write_text(json.dumps(report,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: report[key] for key in ('status', 'result_id',
    'new_candidate_created', 'original_success_package_unchanged',
    'ledger_counts_before_after', 'seconds')}, ensure_ascii=False), flush=True)
assert outcome['status'] == 'UPDATES_READY'
assert row['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert row['successful_attempt'] == original and row['new_candidate_created'] is False
assert report['result_id'] == first['current_result_id']
assert original_unchanged and before['counts'] == after['counts']
assert len(before['rows']) == len(after['rows'])
