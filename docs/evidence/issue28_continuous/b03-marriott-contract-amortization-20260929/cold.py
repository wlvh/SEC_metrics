"""Independent-process read of the private B01 success and B03 failure."""

import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


CODE_ROOT = Path(__file__).resolve().parents[4]
STATE = Path('/private/tmp/issue28-b03-marriott-contract-20260929/normal-update')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_ROOT / 'scripts'))

from vnext.b03_contract_amortization_scope import assess_current_b03_scope
from vnext.canonical import strict_json_file
from vnext.ordinary_projection import render_ordinary_run


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    earlier = strict_json_file(path=HERE / 'exercise.json')
    prefix = STATE / 'marriott_international/metrics'
    b01 = prefix / 'B01'
    b03 = prefix / 'B03'
    b01_pointer = strict_json_file(path=b01 / 'current.json')
    b03_pointer = strict_json_file(path=b03 / 'current.json')
    assert b01_pointer['successful_attempt'] is not None
    assert b03_pointer['successful_attempt'] is None
    b01_work = b01 / 'attempts' / b01_pointer['successful_attempt']
    b03_work = b03 / 'attempts' / earlier['b03_attempt_id']
    watched = [b01 / 'current.json', b03 / 'current.json',
               b01_work / 'runs/B01/records.jsonl',
               b03_work / 'runs/B03/records.jsonl',
               b03_work / 'terminal.json']
    before = {str(path): digest(path) for path in watched}
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')):
        b01_read = render_ordinary_run(data_root=b01_work / 'data',
            run_dir=b01_work / 'runs/B01', _return_replay_context=True)
        b03_read = render_ordinary_run(data_root=b03_work / 'data',
            run_dir=b03_work / 'runs/B03', _return_replay_context=True)
        b03_scope = assess_current_b03_scope(
            case=b03_read['replay_context']['case'],
            data_root=b03_work / 'data')
    b01_result, = [row for row in b01_read['replay_context']['records']
                   if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'B01']
    b03_result, = [row for row in b03_read['replay_context']['records']
                   if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'B03']
    assert b01_result['result_id'] == earlier['b01_result_id']
    assert b03_result['result_id'] == ('sha256:3043aa63cbf7616f9866fb93b8f69200'
                                       'a2246a33dfec8f1d09502a34af39a72a')
    assert b03_result['publication'] == 'PUBLISHED'
    assert b03_scope['blocked'] and b03_scope['status'] == \
        'COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED'
    terminal = strict_json_file(path=b03_work / 'terminal.json')
    assert terminal['status'] == 'EXECUTION_FAILED'
    after = {str(path): digest(path) for path in watched}
    assert before == after
    body = {'record_type': 'ISSUE28_MARRIOTT_B03_SCOPE_PRIVATE_COLD_READ',
        'b01_result_id': b01_result['result_id'],
        'b03_historical_result_id_retained': b03_result['result_id'],
        'b03_historical_result_publication': b03_result['publication'],
        'b03_current_scope_status': b03_scope['status'],
        'b03_current_success_pointer': b03_pointer['successful_attempt'],
        'b03_terminal_status': terminal['status'],
        'watched_private_files_unchanged': before == after,
        'new_real_calls': [0, 0, 0], 'formal_adoption': False}
    (HERE / 'cold.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'b01_result_id': b01_result['result_id'],
        'b03_current_credit': False,
        'b03_scope': b03_scope['status'],
        'private_files_unchanged': before == after,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
