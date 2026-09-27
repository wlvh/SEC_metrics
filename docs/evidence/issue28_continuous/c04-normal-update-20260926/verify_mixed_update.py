"""A C04 update does not replace the older route for its B01 neighbour."""
import contextlib
import io
import json
from pathlib import Path
import socket
from unittest.mock import patch

from vnext.normal_source_authority import ROOT
from tools.vnext_normal_update import main as update_cli


HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-c04-mixed-update-20260926-01')


def main():
    assert not STATE.exists()
    stream = io.StringIO()
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         contextlib.redirect_stdout(stream):
        code = update_cli(['--process', '--data-root', str(ROOT),
            '--state-root', str(STATE), '--company', 'marriott_international',
            '--metric', 'B01', '--metric', 'C04'])
    report = json.loads(stream.getvalue())
    company, = report['companies']
    rows = {row['metric_id']: row for row in company['metrics']}
    assert code == 0 and company['status'] == 'UPDATES_READY'
    assert set(rows) == {'B01', 'C04'}
    assert all(row['status'] == 'CANDIDATE_READY' for row in rows.values())
    assert (STATE/'marriott_international/metrics/B01/configuration.json').is_file()
    assert (STATE/'marriott_international/metrics/C04-registration-v3/configuration.json').is_file()
    assert not (STATE/'marriott_international/metrics/C04/configuration.json').exists()
    summary = {'status': 'PASS_MIXED_ORDINARY_AND_C04_UPDATE',
        'source_root': str(ROOT), 'state_root': str(STATE),
        'b01_success': rows['B01']['successful_attempt'],
        'c04_success': rows['C04']['successful_attempt'],
        'c04_route_state_separate_from_legacy': True,
        'network_disabled': True, 'new_real_calls': [0, 0, 0],
        'production_authorized': False}
    (HERE/'mixed-update-summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
