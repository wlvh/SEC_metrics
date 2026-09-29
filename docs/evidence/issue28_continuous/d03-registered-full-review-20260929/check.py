"""Exercise all D03 recorded groups from a ledger-owned external source root."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-d03-registered-full-review-20260929-retry')
REAL = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.canonical import strict_json_loads
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.continuous_sec_acquisition import initialize_source_inputs
from vnext.continuous_semantic_calls import (execute_d03_recorded_assessment,
                                              prepare_d03_replay_only_requests)
from vnext.d03_native_assessment import collect_recorded_assessments
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot
from tests.vnext.test_d03_native_assessment import _response, _wire


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


originals = {'claims': REAL/'claims.jsonl',
    'source_log': REAL/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
assert not WORK.exists()
ledger = recorded_ledger(root=WORK/'ledger')
source_root = ledger.root/'source-inputs'
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
with ledger.locked():
    assert ledger.snapshot()['counts'] == [0, 0, 0]
initialize_source_inputs(root=source_root, requirement=requirement,
                         clone_baseline=True)
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    with request_construction_session(requirement):
        prepared = prepare_d03_replay_only_requests(
            company_id='marriott_international', source_root=source_root,
            source_ledger=ledger)
        assert len(prepared) == 5
        requests = [strict_json_loads(text=row.request_bytes.decode())
                    for row in prepared]
        source = strict_json_loads(text=prepared[0].source_bytes.decode())
        assert source['external_replay_only'] is True
        assert all(request['external_replay_only'] is True for request in requests)
        assert source['required_unit_ids'] == [unit['unit_id']
            for request in requests for unit in request['units']]
        terminal_ids = []
        for index, (selected, request) in enumerate(zip(prepared, requests)):
            response = _response(request)
            if index == 2:
                response['units'][0]['unresolved'] = [
                    'Synthetic recorded uncertainty; no business conclusion.']
            _, outcome = execute_d03_recorded_assessment(
                prepared=selected, ledger=ledger,
                recorded_wire=_wire(response))
            assert outcome['terminal']['status'] == 'SUCCEEDED'
            assert outcome['native_result_created'] is False
            terminal_ids.append(outcome['terminal']['terminal_id'])
    collected = collect_recorded_assessments(
        company_id='marriott_international', ledger=ledger,
        include_company_review=True, source_root=source_root)
    review = collected['company_review']
    assert len(collected['completed']) == len(requests)
    assert collected['missing_request_ids'] == []
    assert collected['failed_requests'] == []
    assert collected['semantic_correctness_verified'] is False
    assert collected['native_result_or_run_created'] is False
    assert review['recorded_only'] is True
    assert review['review_unit']['status'] == 'PENDING'
    assert review['review_unit']['system_approval_eligible'] is False
    assert review['review_decision_created'] is False
    assert review['native_result_or_run_created'] is False
with ledger.locked():
    counts = ledger.snapshot()['counts']
assert counts == [5, 5, 0]
assert before == {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_D03_REGISTERED_EXTERNAL_FULL_RECORDED_REVIEW',
    'tested_head': '76ebe42ea28eedaac640c70d127475296361d1f3',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'source_root': str(source_root),
    'source_id': source['semantic_source_id'],
    'request_ids': [request['request_id'] for request in requests],
    'terminal_ids': terminal_ids,
    'complete_source_unit_count': len(source['required_unit_ids']),
    'completed_group_count': len(collected['completed']),
    'unresolved_group_count': len(collected['unresolved_request_ids']),
    'company_review_status': review['review_unit']['status'],
    'system_approval_eligible': False,
    'recorded_only': True,
    'native_result_or_run_created': False,
    'recorded_test_ledger_counts': counts,
    'real_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0]}
(HERE/'result.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'groups': body['completed_group_count'],
    'source_units': body['complete_source_unit_count'],
    'review_status': body['company_review_status'],
    'recorded_counts': counts, 'real_calls': [0, 0, 0]}, sort_keys=True),
    flush=True)
