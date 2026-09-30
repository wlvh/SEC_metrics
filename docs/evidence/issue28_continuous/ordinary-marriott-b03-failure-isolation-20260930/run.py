"""One saved-source normal update: B03 fails while B01 and C04 finish."""

from contextlib import redirect_stdout
import hashlib
import importlib.util
from io import StringIO
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
PROCESSING = Path('/private/tmp/issue28-b03-marriott-contract-20260929/sources')
STATE = Path('/private/tmp/issue28-marriott-b03-failure-isolation-20260930/state')
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts'), str(ROOT / 'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not STATE.exists(), 'PRIVATE_STATE_ALREADY_EXISTS'
    originals = {'claims': LEDGER / 'claims.jsonl',
        'source_log': LEDGER / 'source-inputs/evidence/requests_log.csv',
        'active': ROOT / 'outputs/active_publication.json'}
    before = {key: digest(path) for key, path in originals.items()}
    expected = json.loads((ROOT /
        'docs/evidence/issue28_continuous/ordinary-marriott-cli-b01-c04-20260929/create.json').read_text())
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         probe.legacy_disabled() as disabled:
        from vnext.continuous_call_policy import REQUIREMENT_ID
        from vnext.ordinary_processing_source import current_processing_source
        from vnext.requirements import load_requirement_snapshot
        import vnext_normal_update
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / REQUIREMENT_ID)
        source = current_processing_source(acquisition_root=LEDGER / 'source-inputs',
            output_parent=PROCESSING, requirement=requirement)
        capture = StringIO()
        with redirect_stdout(capture):
            rc = vnext_normal_update.main(['--process', '--company',
                'marriott_international', '--metric', 'B01', '--metric', 'B03',
                '--metric', 'C04', '--data-root', str(source['data_root']),
                '--state-root', str(STATE)])
    report = json.loads(capture.getvalue())
    company, = report['companies']
    rows = {row['metric_id']: row for row in company['metrics']}
    assert rc == 2 and company['status'] == 'UPDATES_PARTIAL'
    assert set(rows) == {'B01', 'B03', 'C04'}
    assert rows['B01']['status'] == rows['C04']['status'] == 'CANDIDATE_READY'
    assert rows['B03']['status'] == 'EXECUTION_FAILED'
    assert 'COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED' in \
        rows['B03']['terminal']['error']['reason']
    results = {metric: rows[metric]['last_verified_candidate']['results'][metric]
        for metric in ('B01', 'C04')}
    assert {metric: result['result_id'] for metric, result in results.items()} == \
        expected['result_ids']
    assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
    assert before == {key: digest(path) for key, path in originals.items()}
    body = {'tested_head': __import__('subprocess').check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'source_root': str(source['data_root']),
        'source_snapshot_id': source['snapshot_id'],
        'state_root': str(STATE),
        'old_semantic_exports_disabled': disabled,
        'company_status': company['status'],
        'metric_statuses': {metric: row['status'] for metric, row in rows.items()},
        'successful_result_ids': {metric: result['result_id'] for metric, result in results.items()},
        'b03_attempt_id': rows['B03']['attempt_id'],
        'b03_error': rows['B03']['terminal']['error']['reason'],
        'originals_unchanged': True, 'new_real_calls': [0, 0, 0],
        'new_complete_company_or_390_credit': 0, 'formal_adoption': False}
    (HERE / 'run.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'company_status': body['company_status'],
        'metric_statuses': body['metric_statuses'],
        'old_semantic_exports_disabled': disabled,
        'originals_unchanged': True, 'new_real_calls': [0, 0, 0]},
        sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
