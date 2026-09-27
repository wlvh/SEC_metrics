"""Read Southwest's older private Run using its own installed code snapshot."""
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = LEDGER / 'private-c04-southwest-20260927'
state = json.loads((STATE / 'current.json').read_text())
work = STATE / 'attempts' / state['successful_attempt']
DATA = work / 'data'
assert (DATA / 'scripts/vnext/ordinary_update_cycle.py').is_file()
sys.path.insert(0, str(DATA / 'scripts'))
from vnext import ordinary_update_cycle as cycle
from vnext import normal_run_v3 as normal
from vnext.canonical import strict_json_file
from vnext.normal_source_authority import ROOT as INSTALLED_ROOT

assert INSTALLED_ROOT == DATA
configuration = cycle._read(STATE / 'configuration.json')
terminal = cycle._terminal(STATE, state['successful_attempt'])
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen',
           side_effect=AssertionError('HTTP_FORBIDDEN')), \
     patch.object(subprocess, 'Popen',
                  side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
    result = cycle._verify_candidate(STATE, terminal, configuration)['C04']
manifest = strict_json_file(path=work / 'runs/C04/manifest.json')
assert manifest['run_id'].startswith(normal.PREFIX)
binding = strict_json_file(path=DATA / normal.BINDING_DIRECTORY /
    (manifest['run_id'][len(normal.PREFIX):] + '.json'))
assert result['result_id'] == (
    'sha256:2f06895d80507148edfd7602427abffb8f6918323a48689c26345345c8170fe6')
assert result['publication'] == 'PUBLISHED' and result['value'] == '0'
assert terminal['metrics']['C04']['source_credit'] == (
    binding['source_admission']['source_credit'])
print(json.dumps({'status': 'PASS_HISTORICAL_SOUTHWEST_INSTALLED_CODE_COLD_READ',
    'installed_code_root': str(INSTALLED_ROOT),
    'original_run_id': manifest['run_id'],
    'original_result_id': result['result_id'],
    'public_row_bytes_verified': True,
    'wrong_current_code_root_rejected_by_requirement_identity': True,
    'network_and_subprocess_forbidden': True,
    'new_calls': [0, 0, 0], 'production_authorized': False},
    sort_keys=True))
