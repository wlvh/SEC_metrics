"""Private positive B03 normal update under the explicit V14 guard."""

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
STATE_ROOT = Path('/private/tmp/issue28-b03-marriott-contract-20260929/pfizer-positive')
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
                '--company', 'pfizer', '--metric', 'B03',
                '--data-root', str(processing['data_root']),
                '--state-root', str(STATE_ROOT)])
    report = json.loads(capture.getvalue())
    company, = report['companies']
    row, = company['metrics']
    result = row['last_verified_candidate']['results']['B03']
    pointer = strict_json_file(path=STATE_ROOT / 'pfizer/metrics/B03/current.json')
    assert rc == 0 and company['status'] == 'UPDATES_READY'
    assert row['status'] == 'CANDIDATE_READY'
    assert pointer['successful_attempt'] == row['attempt_id']
    assert result['result_id'] == ('sha256:b6d0e8c0f7decc22cbe4598de6ceff4f5982'
                                   '0258b30bd6012af06e7c4cb0799b')
    assert result['publication'] == 'PUBLISHED' and result['reason_code'] == 'PASS'
    assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
    after = {key: digest(path) for key, path in protected.items()}
    assert before == after
    body = {'record_type': 'ISSUE28_B03_CURRENT_GUARD_UNAFFECTED_POSITIVE',
        'company_id': 'pfizer', 'metric_id': 'B03',
        'processing_snapshot_id': processing['snapshot_id'],
        'normal_cli_return_code': rc, 'company_status': company['status'],
        'metric_status': row['status'], 'result_id': result['result_id'],
        'result_value': result['value'], 'result_quality': result['quality'],
        'successful_attempt': pointer['successful_attempt'],
        'protected_hashes_unchanged': before == after,
        'new_real_calls': [0, 0, 0], 'formal_adoption': False}
    (HERE / 'positive.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': body['metric_status'],
        'result_id': body['result_id'],
        'protected_hashes_unchanged': before == after,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
