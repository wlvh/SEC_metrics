"""Independent process readback of the actual-ledger zero-call C04 candidate."""
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from vnext import c04_update_cycle as update
from vnext.canonical import sha256_file, strict_json_file


ROOT = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03')
STATE = ROOT/'state/marriott_international/metrics/C04-registration-v3'
REPORT = ROOT/'report.json'


def main():
    report = strict_json_file(path=REPORT)
    company, = report['companies']
    row, = company['updates']['metrics']
    assert row['status'] == 'CANDIDATE_READY'
    state = strict_json_file(path=STATE/'current.json')
    assert state['successful_attempt'] == row['successful_attempt']
    configuration = update.cycle._read(STATE/'configuration.json')
    terminal = update.cycle._terminal(STATE, state['successful_attempt'])
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         patch.object(subprocess, 'Popen',
                      side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
        results = update._verify_candidate(STATE, terminal, configuration)
    result = results['C04']
    assert result['publication'] == 'PUBLISHED' and result['value'] == '0'
    assert terminal['metrics']['C04']['publication'] == result['publication']
    assert report['ledger_counts_before'] == report['ledger_counts_after'] == [143, 143, 49]
    summary = {'status': 'PASS_REAL_LEDGER_SAVED_C04_ZERO_CALL_COLD_READ',
        'attempt_id': state['successful_attempt'], 'result_id': result['result_id'],
        'value': result['value'], 'publication': result['publication'],
        'terminal_sha256': sha256_file(path=STATE/'attempts'/state['successful_attempt']/'terminal.json'),
        'calls': report['calls'], 'source_refresh': company['source_refresh']['status'],
        'full_refresh_completed': False, 'new_sec_capture_executed': False,
        'production_authorized': False}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
