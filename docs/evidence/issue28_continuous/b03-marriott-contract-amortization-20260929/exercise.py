"""One private current B01+B03 normal update after the source-scope guard."""

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


CODE_ROOT = Path(__file__).resolve().parents[4]
LEDGER_ROOT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
PROCESSING_PARENT = Path('/private/tmp/issue28-b03-marriott-contract-20260929/sources')
STATE_ROOT = Path('/private/tmp/issue28-b03-marriott-contract-20260929/normal-update')
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(CODE_ROOT / 'scripts'), str(CODE_ROOT / 'tools')]

from vnext.canonical import strict_json_file
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.ordinary_processing_source import current_processing_source
from vnext.requirements import load_requirement_snapshot
import vnext_normal_update


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not STATE_ROOT.exists()
    source_root = LEDGER_ROOT / 'source-inputs'
    protected = {'claims': LEDGER_ROOT / 'claims.jsonl',
                 'source_log': source_root / 'evidence/requests_log.csv',
                 'active': CODE_ROOT / 'outputs/active_publication.json'}
    before = {key: digest(path) for key, path in protected.items()}
    requirement = load_requirement_snapshot(
        snapshot_dir=CODE_ROOT / 'requirements' / REQUIREMENT_ID)
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')):
        processing = current_processing_source(
            acquisition_root=source_root, output_parent=PROCESSING_PARENT,
            requirement=requirement)
        capture = StringIO()
        with redirect_stdout(capture):
            rc = vnext_normal_update.main(['--process',
                '--company', 'marriott_international',
                '--metric', 'B01', '--metric', 'B03',
                '--data-root', str(processing['data_root']),
                '--state-root', str(STATE_ROOT)])
    report = json.loads(capture.getvalue())
    company, = report['companies']
    rows = {row['metric_id']: row for row in company['metrics']}
    assert rc == 2 and company['status'] == 'UPDATES_PARTIAL'
    assert set(rows) == {'B01', 'B03'}
    assert rows['B01']['status'] == 'CANDIDATE_READY'
    assert rows['B03']['status'] == 'EXECUTION_FAILED'
    assert 'B03_CURRENT_SOURCE_SCOPE_UNRESOLVED:' \
        'COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED' in \
        rows['B03']['terminal']['error']['reason']
    b01_result = rows['B01']['last_verified_candidate']['results']['B01']
    assert b01_result['publication'] == 'PUBLISHED'
    b03_pointer = strict_json_file(path=STATE_ROOT /
        'marriott_international/metrics/B03/current.json')
    assert b03_pointer['successful_attempt'] is None
    b03_terminal = strict_json_file(path=STATE_ROOT /
        'marriott_international/metrics/B03/attempts' /
        rows['B03']['attempt_id'] / 'terminal.json')
    assert b03_terminal['status'] == 'EXECUTION_FAILED'
    after = {key: digest(path) for key, path in protected.items()}
    assert before == after
    assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
    body = {'record_type': 'ISSUE28_MARRIOTT_B01_POSITIVE_B03_SCOPE_FAILURE',
        'processing_snapshot_id': processing['snapshot_id'],
        'normal_cli_return_code': rc,
        'company_status': company['status'],
        'b01_result_id': b01_result['result_id'],
        'b01_status': rows['B01']['status'],
        'b03_status': rows['B03']['status'],
        'b03_attempt_id': rows['B03']['attempt_id'],
        'b03_terminal_error': b03_terminal['error'],
        'b03_successful_attempt': b03_pointer['successful_attempt'],
        'original_protected_hashes_unchanged': before == after,
        'new_real_calls': [0, 0, 0], 'new_b03_result_credit': False,
        'formal_adoption': False, 'all390_acceptance': False}
    (HERE / 'exercise.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'company_status': body['company_status'],
        'b01_status': body['b01_status'], 'b03_status': body['b03_status'],
        'b03_error': body['b03_terminal_error']['reason'],
        'b03_successful_attempt': body['b03_successful_attempt'],
        'originals_unchanged': before == after,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
