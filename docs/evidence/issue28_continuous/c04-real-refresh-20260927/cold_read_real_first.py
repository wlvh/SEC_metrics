"""Read both immutable Marriott C04 versions after one actual SEC refresh."""
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from vnext import c04_update_cycle as c04
from vnext.canonical import strict_json_file


WORK = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03')
STATE = WORK/'state/marriott_international/metrics/C04-registration-v3'


def main():
    report = strict_json_file(path=WORK/'real-refresh-1.json')
    row, = report['companies'][0]['updates']['metrics']
    configuration = c04.cycle._read(STATE/'configuration.json')
    attempts = [row['previous_successful_attempt'], row['successful_attempt']]
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         patch.object(subprocess, 'Popen',
                      side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
        results = [c04._verify_candidate(STATE,
            c04.cycle._terminal(STATE, attempt), configuration)['C04']
            for attempt in attempts]
    assert len(set(attempts)) == len(set(result['result_id'] for result in results)) == 2
    assert all(result['publication'] == 'PUBLISHED' and result['value'] == '0'
               for result in results)
    assert results[1]['result_id'] == row['last_verified_candidate']['results']['C04']['result_id']
    assert report['ledger_counts_after'] == [143, 143, 50]
    print(json.dumps({'status': 'PASS_OLD_AND_NEW_C04_AFTER_REAL_SEC_SOURCE',
        'attempts': attempts, 'result_ids': [r['result_id'] for r in results],
        'values': [r['value'] for r in results], 'network_forbidden': True,
        'subprocess_forbidden': True, 'new_calls': [0, 0, 0],
        'source_refresh_completed': False, 'production_authorized': False},
        ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
