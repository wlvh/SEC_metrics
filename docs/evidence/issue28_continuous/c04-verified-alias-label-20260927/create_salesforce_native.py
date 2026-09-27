"""Create one private FY2026 C04 native Run from original saved sources."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.c04_update_cycle import run_company

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = LEDGER / 'source-inputs'
STATE = LEDGER / 'private-c04-salesforce-fy2026-20260927'
assert not STATE.exists(), 'PRIVATE_SALESFORCE_C04_STATE_ALREADY_EXISTS'
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    result = run_company(state_root=STATE, source_root=SOURCE,
                         company_id='salesforce')
row, = result['metrics']
candidate = row['last_verified_candidate']
native = None if candidate is None else candidate['results']['C04']
print(json.dumps({'company_id': result['company_id'],
    'status': result['status'], 'metric_status': row['status'],
    'new_candidate_created': row['new_candidate_created'],
    'fiscal_year': None if candidate is None else candidate['targets']['C04']['fiscal_year'],
    'result_id': None if native is None else native['result_id'],
    'publication': None if native is None else native['publication'],
    'value': None if native is None else native.get('value'),
    'successful_attempt': row['successful_attempt'],
    'state_root': str(STATE), 'source_root': str(SOURCE),
    'new_calls': result['calls'], 'production_authorized': False},
    sort_keys=True))
assert result['status'] == 'UPDATES_READY' and row['status'] == 'CANDIDATE_READY'
assert row['new_candidate_created'] and native is not None
assert candidate['targets']['C04']['fiscal_year'] == 2026
assert native['publication'] == 'PUBLISHED' and native['value'] == '0'
