"""A repeated unchanged Salesforce source must not create another C04 Result."""
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
STATE = LEDGER / 'private-c04-salesforce-fy2026-20260927'
before = strict_json_file(path=STATE / 'current.json')
assert before['successful_attempt'] is not None
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    result = run_company(state_root=STATE, source_root=LEDGER / 'source-inputs',
                         company_id='salesforce')
row, = result['metrics']
candidate = row['last_verified_candidate']
native = candidate['results']['C04']
assert result['status'] == 'UPDATES_READY'
assert row['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert not row['new_candidate_created']
assert row['successful_attempt'] == before['successful_attempt']
assert candidate['targets']['C04']['fiscal_year'] == 2026
assert native['publication'] == 'PUBLISHED' and native['value'] == '0'
assert result['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
print(json.dumps({'status': 'PASS_SALESFORCE_C04_UNCHANGED_INPUT_REUSED',
    'fiscal_year': 2026, 'prior_successful_attempt': before['successful_attempt'],
    'successful_attempt_after': row['successful_attempt'],
    'new_noop_attempt': row['attempt_id'],
    'old_result_id_reused': native['result_id'],
    'new_candidate_created': False,
    'new_calls': result['calls'], 'production_authorized': False},
    sort_keys=True))
