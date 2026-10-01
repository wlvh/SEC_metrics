"""Independent-process no-network read of a peer4d ordinary C02 Run."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext import ordinary_update_cycle as cycle
from vnext.canonical import sha256_file

CASES = {
    'paramount': 'paramount_skydance_paramount_global',
    'salesforce': 'salesforce',
}
assert len(sys.argv) == 2 and sys.argv[1] in CASES
short = sys.argv[1]
company = CASES[short]
state = Path('/private/tmp/issue28-c02-peer4d-' + short + '-20261002')
metric_root = state / 'metrics/C02'
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    config = cycle._config(metric_root, ROOT, company, ['C02'], 'LIVE')
    snapshot = cycle._state(metric_root, config)
    success = cycle._terminal(metric_root, snapshot['successful_attempt'])
    repeat = cycle._terminal(metric_root, snapshot['latest_attempt'])
    result = cycle._verify_candidate(metric_root, success, config)['C02']
assert before == sha256_file(path=source_log)
assert success['status'] == 'CANDIDATE_READY'
assert repeat['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
run = metric_root / 'attempts' / snapshot['successful_attempt'] / 'runs/C02'
manifest = json.loads((run / 'manifest.json').read_text())
rows = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
candidate = next(row for row in rows if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
prior = json.loads((HERE / ('peer4d-' + short + '-update.json')).read_text())
assert prior['result_id'] == result['result_id']
assert prior['run_id'] == manifest['run_id']
assert prior['candidate_hash'] == candidate['candidate_hash']
body = {
    'record_type': 'ISSUE28_C02_PEER4D_PRIVATE_COLD_READ',
    'company_id': company, 'run_id': manifest['run_id'],
    'result_id': result['result_id'],
    'candidate_hash': candidate['candidate_hash'],
    'grouped_excerpt_count': len(candidate['selected']),
    'first_status': success['status'], 'repeat_status': repeat['status'],
    'publication': result['publication'], 'quality': result['quality'],
    'requirement_closure_hash': manifest['requirement_closure_hash'],
    'source_log_unchanged': True, 'new_real_calls': [0, 0, 0],
    'business_content_acceptance': False, 'current_390_credit': False,
    'production_authorized': False,
}
(HERE / ('peer4d-' + short + '-cold.json')).write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
