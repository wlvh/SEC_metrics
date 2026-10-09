"""No-network Paramount D01 update under the repaired page-boundary bytes."""
import json
from pathlib import Path
import signal
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import sha256_file
from vnext.ordinary_update_cycle import run_company

company, count = 'paramount_skydance_paramount_global', 38
state = Path('/private/tmp/issue28-d01-page-boundary-paramount-20261002')
assert not state.exists()
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
signal.alarm(1200)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    first = run_company(state_root=state, source_root=ROOT,
                        company_id=company, metric_ids=['D01'])
    repeat = run_company(state_root=state, source_root=ROOT,
                         company_id=company, metric_ids=['D01'])
assert before == sha256_file(path=source_log)
one, two = first['metrics'][0], repeat['metrics'][0]
assert one['status'] == 'CANDIDATE_READY', one
assert two['status'] == 'NO_SOURCE_CONTENT_CHANGE', two
assert one['successful_attempt'] == two['successful_attempt']
result = one['last_verified_candidate']['results']['D01']
run = state / 'metrics/D01/attempts' / one['successful_attempt'] / 'runs/D01'
manifest = json.loads((run / 'manifest.json').read_text())
records = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
candidate = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
assert len(candidate['selected']) == count and evidence['status'] == 'PASS'
assert all(check['status'] == 'PASS' for check in evidence['checks'])
assert any('changes in U.S. or foreign laws' in claim['text']
           for claim in candidate['selected'].values())
assert result['result_id'] == 'sha256:6795449bafa12651099b226e569ad3b2882f72a89cd317adb559c8096058afdd'
body = {
    'record_type': 'ISSUE28_D01_EMPHASIS_PRIVATE_UPDATE',
    'company_id': company, 'run_id': manifest['run_id'], 'result_id': result['result_id'],
    'candidate_hash': candidate['candidate_hash'], 'heading_count': count,
    'first_status': one['status'], 'repeat_status': two['status'],
    'source_log_unchanged': True, 'new_real_calls': [0, 0, 0],
    'requirement_closure_hash': manifest['requirement_closure_hash'],
    'current_390_credit': False, 'production_authorized': False,
    'state_root': str(state),
}
(HERE / 'private-update.json').write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
