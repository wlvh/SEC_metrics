"""A complete C02 set over 64 fails locally while another metric completes."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import sha256_file
from vnext.ordinary_update_cycle import run_company

STATE = Path('/private/tmp/issue28-c02-marriott-over64-20261001')
assert not STATE.exists()
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    outcome = run_company(state_root=STATE, source_root=ROOT,
        company_id='marriott_international', metric_ids=['B01', 'C02'])
assert before == sha256_file(path=source_log)
rows = {r['metric_id']: r for r in outcome['metrics']}
assert outcome['status'] == 'UPDATES_PARTIAL'
assert rows['B01']['status'] == 'CANDIDATE_READY'
assert rows['C02']['status'] == 'EXECUTION_FAILED'
assert 'TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND' in str(rows['C02']['terminal']['error'])
assert rows['C02']['successful_attempt'] is None
body = {'record_type': 'ISSUE28_C02_COMPLETE_SET_OVER_NATIVE_BOUND',
        'company_id': 'marriott_international',
        'normal_update_status': outcome['status'],
        'b01_status': rows['B01']['status'],
        'c02_status': rows['C02']['status'],
        'c02_reason': rows['C02']['terminal']['error']['reason'],
        'c02_successful_attempt': None,
        'source_log_unchanged': True,
        'calls': [0, 0, 0], 'production_authorized': False}
(HERE / 'marriott-over64.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
