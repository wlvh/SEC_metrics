"""Create a private native C04 Run from the now-complete saved Southwest source."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.c04_update_cycle import run_company
from vnext.canonical import strict_json_file

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = LEDGER / 'source-inputs'
STATE = LEDGER / 'private-c04-southwest-20260927'
previous = strict_json_file(path=STATE / 'current.json')
failed = strict_json_file(path=STATE / 'attempts' /
                          previous['latest_attempt'] / 'terminal.json')
assert failed['status'] == 'EXECUTION_FAILED'
assert failed['error']['reason'] == 'SUBPROCESS_FORBIDDEN'
assert failed['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}

with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    result = run_company(state_root=STATE, source_root=SOURCE,
                         company_id='southwest_airlines')
row, = result['metrics']
candidate = row['last_verified_candidate']
native = None if candidate is None else candidate['results']['C04']
print(json.dumps({'company_id': result['company_id'],
    'status': result['status'], 'metric_status': row['status'],
    'new_candidate_created': row['new_candidate_created'],
    'result_id': None if native is None else native['result_id'],
    'publication': None if native is None else native['publication'],
    'value': None if native is None else native.get('value'),
    'successful_attempt': row['successful_attempt'],
    'previous_failed_attempt': failed['attempt_id'],
    'state_root': str(STATE), 'source_root': str(SOURCE),
    'new_calls': result['calls'], 'production_authorized': False},
    ensure_ascii=False, sort_keys=True))
assert result['status'] == 'UPDATES_READY' and row['status'] == 'CANDIDATE_READY'
assert row['new_candidate_created'] and native is not None
