"""Exercise the ordinary update controller's explicit C02 route without network."""
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

STATE = Path('/private/tmp/issue28-c02-normal-update-enphase-20261001')
assert not STATE.exists()
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    first = run_company(state_root=STATE, source_root=ROOT,
        company_id='enphase_energy', metric_ids=['C02'])
    second = run_company(state_root=STATE, source_root=ROOT,
        company_id='enphase_energy', metric_ids=['C02'])
assert before == sha256_file(path=source_log)
one, two = first['metrics'][0], second['metrics'][0]
assert first['status'] == second['status'] == 'UPDATES_READY'
assert one['status'] == 'CANDIDATE_READY'
assert two['status'] == 'NO_SOURCE_CONTENT_CHANGE'
result = one['last_verified_candidate']['results']['C02']
expected = json.loads((HERE / 'enphase-summary.json').read_text())
assert result['result_id'] == expected['result_id']
assert two['successful_attempt'] == one['successful_attempt']
body = {'record_type': 'ISSUE28_C02_COMPOSITION_NORMAL_UPDATE',
        'company_id': 'enphase_energy', 'first_status': one['status'],
        'repeat_status': two['status'], 'result_id': result['result_id'],
        'same_successful_attempt_on_repeat': True,
        'original_source_log_unchanged': True,
        'calls': [0, 0, 0], 'production_authorized': False}
(HERE / 'enphase-update.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
