"""Reopen the registered five-group D03 recorded set in a new process."""
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

from vnext.continuous_call_ledger import recorded_ledger
from vnext.d03_native_assessment import collect_recorded_assessments


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


saved = json.loads((HERE/'result.json').read_text())
originals = {'claims': REAL/'claims.jsonl',
    'source_log': REAL/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
ledger = recorded_ledger(root=WORK/'ledger')
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    collected = collect_recorded_assessments(
        company_id='marriott_international', ledger=ledger,
        include_company_review=True, source_root=WORK/'ledger/source-inputs')
    review = collected['company_review']
    assert collected['source_id'] == saved['source_id']
    assert collected['required_request_ids'] == saved['request_ids']
    assert [row['terminal_id'] for row in collected['completed']] == saved['terminal_ids']
    assert len(collected['completed']) == saved['completed_group_count'] == 5
    assert len(collected['complete_source_unit_ids']) == saved['complete_source_unit_count'] == 17
    assert len(collected['unresolved_request_ids']) == saved['unresolved_group_count'] == 1
    assert review['review_unit']['status'] == 'PENDING'
    assert review['recorded_only'] is True
    assert review['native_result_or_run_created'] is False
with ledger.locked():
    counts = ledger.snapshot()['counts']
assert counts == saved['recorded_test_ledger_counts'] == [5, 5, 0]
assert before == {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_D03_REGISTERED_EXTERNAL_FULL_COLD_READ',
    'source_id': collected['source_id'],
    'request_ids_match': True, 'terminal_ids_match': True,
    'completed_group_count': 5, 'source_unit_count': 17,
    'unresolved_group_count': 1,
    'review_status': review['review_unit']['status'],
    'recorded_only': True, 'native_result_or_run_created': False,
    'recorded_test_ledger_counts': counts,
    'real_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0]}
(HERE/'cold.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'groups': 5, 'source_units': 17,
    'review_status': 'PENDING', 'recorded_counts': counts}, sort_keys=True),
    flush=True)
