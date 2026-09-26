"""Independent readback after the two bounded real Marriott SEC GETs."""
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from vnext import c04_update_cycle as c04
from vnext.canonical import strict_json_file


LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
WORK = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03')
STATE = WORK/'state/marriott_international/metrics/C04-registration-v3'


def main():
    first = strict_json_file(path=WORK/'real-refresh-1.json')
    second = strict_json_file(path=WORK/'real-refresh-2.json')
    first_row, = first['companies'][0]['updates']['metrics']
    second_row, = second['companies'][0]['updates']['metrics']
    capture, = second['captures']
    call = LEDGER/'calls/0194'
    assert capture['source_url'].endswith('/CIK0001048286.json')
    assert 'companyfacts/' in capture['source_url']
    assert strict_json_file(path=call/'sec-receipt.json') == capture['result']['receipt']
    assert strict_json_file(path=call/'terminal.json') == capture['result']['terminal']
    assert capture['result']['status'] == 'SUCCEEDED'
    assert second['ledger_counts_before'] == [143, 143, 50]
    assert second['ledger_counts_after'] == [143, 143, 51]
    assert second['calls'] == {'provider': 0, 'paid': 0, 'sec': 1}
    assert second['status'] == 'UPDATES_READY'
    company, = second['companies']
    assert company['source_refresh']['status'] == 'REFRESH_CHECK_COMPLETED'
    assert company['source_refresh']['deferred_source_urls'] == []
    assert company['source_refresh']['failed_source_urls_not_retried'] == []
    assert second_row['status'] == 'NO_SOURCE_CONTENT_CHANGE'
    assert second_row['successful_attempt'] == first_row['successful_attempt']
    configuration = c04.cycle._read(STATE/'configuration.json')
    attempts = [first_row['previous_successful_attempt'],
                first_row['successful_attempt']]
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         patch.object(subprocess, 'Popen',
                      side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
        results = [c04._verify_candidate(STATE,
            c04.cycle._terminal(STATE, identity), configuration)['C04']
            for identity in attempts]
    assert len({result['result_id'] for result in results}) == 2
    assert all(result['publication'] == 'PUBLISHED' and result['value'] == '0'
               for result in results)
    assert results[1]['result_id'] == second_row['last_verified_candidate']['results']['C04']['result_id']
    print(json.dumps({'status': 'PASS_COMPLETE_REAL_C04_SOURCE_REFRESH_AND_COLD_READ',
        'sec_ordinals': [193, 194], 'c04_successful_attempts': attempts,
        'c04_result_ids': [row['result_id'] for row in results],
        'second_source_update_status': second_row['status'],
        'source_refresh_status': company['source_refresh']['status'],
        'ledger_counts': second['ledger_counts_after'],
        'cold_read_network_and_subprocess_forbidden': True,
        'new_calls_during_read': [0, 0, 0], 'production_authorized': False},
        ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
