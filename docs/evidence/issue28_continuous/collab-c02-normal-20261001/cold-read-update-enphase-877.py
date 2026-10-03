"""Read the persisted normal-update pointer and C02 Run in a fresh process."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext import ordinary_update_cycle as cycle

STATE = Path('/private/tmp/issue28-c02-normal-update-enphase-877-20261001')
metric_root = STATE / 'metrics/C02'
expected = json.loads((HERE / 'enphase-update-877.json').read_text())
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    config = cycle._config(metric_root, ROOT, 'enphase_energy', ['C02'], 'LIVE')
    state = cycle._state(metric_root, config)
    assert state['successful_attempt'] is not None
    terminal = cycle._terminal(metric_root, state['successful_attempt'])
    result = cycle._verify_candidate(metric_root, terminal, config)['C02']
assert terminal['status'] == 'CANDIDATE_READY'
assert result['result_id'] == expected['result_id']
assert expected['selected_composition_fact_count'] == 54
body = {'record_type': 'ISSUE28_C02_NORMAL_UPDATE_COLD_READ',
        'successful_attempt': state['successful_attempt'],
        'latest_attempt': state['latest_attempt'],
        'result_id': result['result_id'],
        'publication': result['publication'], 'quality': result['quality'],
        'calls': [0, 0, 0], 'production_authorized': False}
(HERE / 'enphase-update-877-cold.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True))
