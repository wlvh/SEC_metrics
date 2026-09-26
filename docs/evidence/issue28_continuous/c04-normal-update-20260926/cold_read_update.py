"""Read the completed C04 update journal in a separate, networkless process."""
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from vnext.c04_update_cycle import run_once
from vnext.canonical import strict_json_file


HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-c04-normal-update-20260926-01')
COMPANY = 'marriott_international'


def main():
    summary = strict_json_file(path=HERE/'recorded-update-summary.json')
    state = WORK/'state'/COMPANY/'metrics/C04-registration-v3'
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch.object(subprocess, 'Popen',
                      side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
        current = run_once(state_root=state, source_root=WORK/'source',
                           company_id=COMPANY)
    assert current['status'] == 'NO_SOURCE_CONTENT_CHANGE'
    assert current['successful_attempt'] == summary['marriott_changed_source_success']
    for identity in (summary['marriott_first_success'],
                     summary['marriott_changed_source_success']):
        terminal = strict_json_file(path=state/'attempts'/identity/'terminal.json')
        assert terminal['status'] == 'CANDIDATE_READY'
        assert terminal['metrics']['C04']['publication'] == 'PUBLISHED'
    result = {'status': 'PASS_INSTALLED_C04_UPDATE_COLD_READ',
              'source_root': str(WORK/'source'), 'state_root': str(state),
              'historical_successes': [summary['marriott_first_success'],
                                       summary['marriott_changed_source_success']],
              'current_success': current['successful_attempt'],
              'new_candidate_created': current['new_candidate_created'],
              'network_disabled': True, 'subprocess_disabled': True,
              'new_real_calls': [0, 0, 0],
              'production_authorized': False}
    (HERE/'cold-read-summary.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
