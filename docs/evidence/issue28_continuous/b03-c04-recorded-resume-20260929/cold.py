"""Independent-process replay of one recorded C04 result and B03 old history."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext import ordinary_update_cycle as cycle
from vnext import ordinary_b03_scope_update as b03
from vnext import c04_update_cycle as c04


def main():
    ledger_root = Path(sys.argv[1]).resolve()
    state_root = Path(sys.argv[2]).resolve()
    source = ledger_root/'source-inputs'
    company = 'salesforce'
    b03_root = state_root/company/'metrics/B03'
    c04_root = state_root/company/'metrics/C04-registration-v3'
    with (patch.object(socket.socket, 'connect',
                       side_effect=AssertionError('NETWORK_FORBIDDEN')),
          patch.object(socket, 'getaddrinfo',
                       side_effect=AssertionError('DNS_FORBIDDEN')),
          patch('sec_http.urlopen',
                side_effect=AssertionError('HTTP_FORBIDDEN'))):
        b03_config = cycle._config(b03_root, source, company, ['B03'],
                                   'RECORDED_TEST_ONLY')
        b03_state = cycle._state(b03_root, b03_config)
        old = cycle._terminal(b03_root, b03_state['successful_attempt'])
        historical = cycle._verify_candidate(b03_root, old, b03_config)
        try:
            b03._verify_candidate(b03_root, old, b03_config)
        except b03.B03CurrentScopeConflict:
            b03_current = False
        else:
            raise AssertionError('OLD_B03_CURRENT_CREDIT_REVIVED')
        c04_config = c04._configuration(c04_root, source, company)
        c04_state = cycle._state(c04_root, c04_config)
        current = cycle._terminal(c04_root, c04_state['successful_attempt'])
        checked = c04._verify_candidate(c04_root, current, c04_config)
    assert historical['B03']['publication'] == 'PUBLISHED'
    assert checked['C04']['publication'] == 'PUBLISHED'
    assert checked['C04']['value'] == '0'
    print(json.dumps({'status':'PASS_INDEPENDENT_INSTALLED_READ',
        'old_b03_pointer':b03_state['successful_attempt'],
        'old_b03_result_id':historical['B03']['result_id'],
        'old_b03_current_credit':b03_current,
        'c04_pointer':c04_state['successful_attempt'],
        'c04_result_id':checked['C04']['result_id'],
        'c04_publication':checked['C04']['publication'],
        'c04_value':checked['C04']['value'],
        'network_enabled':False,'new_real_calls':[0,0,0]}, sort_keys=True))


if __name__ == '__main__':
    main()
