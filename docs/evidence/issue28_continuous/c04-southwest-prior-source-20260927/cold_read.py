"""Independent, network-free replay of Southwest's private C04 Run."""
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext import c04_update_cycle as c04
from vnext.canonical import strict_json_file

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = LEDGER / 'private-c04-southwest-20260927'
SOURCE = LEDGER / 'source-inputs'
receipt = strict_json_file(path=LEDGER / 'calls/0195/sec-receipt.json')
assert receipt['status'] == 'SUCCEEDED' and receipt['actual_sec_egress_count'] == 1
state = strict_json_file(path=STATE / 'current.json')
configuration = c04.cycle._read(STATE / 'configuration.json')
success = c04.cycle._terminal(STATE, state['successful_attempt'])
all_attempts = sorted(path for path in (STATE / 'attempts').iterdir()
                      if path.is_dir())
failed = [c04.cycle._terminal(STATE, path.name) for path in all_attempts
          if path.name != state['successful_attempt']]
assert len(failed) == 1 and failed[0]['status'] == 'EXECUTION_FAILED'
assert failed[0]['error']['reason'] == 'SUBPROCESS_FORBIDDEN'
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch.object(subprocess, 'Popen',
                  side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
    result = c04._verify_candidate(STATE, success, configuration)['C04']
assert result['result_id'] == 'sha256:2f06895d80507148edfd7602427abffb8f6918323a48689c26345345c8170fe6'
assert result['publication'] == 'PUBLISHED' and result['value'] == '0'
assert success['input']['targets']['C04']['fiscal_year'] == 2025
assert SOURCE.is_dir()
print(json.dumps({'status': 'PASS_PRIVATE_NATIVE_C04_COLD_READ',
    'sec_ordinal': 195, 'prior_annual_role': 'prior_annual_primary',
    'current_fiscal_year': 2025, 'result_id': result['result_id'],
    'publication': result['publication'], 'value': result['value'],
    'successful_attempt': state['successful_attempt'],
    'preserved_failed_attempt': failed[0]['attempt_id'],
    'row_bytes_verified': True, 'network_and_subprocess_forbidden': True,
    'calls_during_cold_read': [0, 0, 0], 'production_authorized': False},
    ensure_ascii=False, sort_keys=True))
