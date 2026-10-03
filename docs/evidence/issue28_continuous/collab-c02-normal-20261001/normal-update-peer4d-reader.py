"""No-network ordinary C02 update for the two known changed source selections."""
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

CASES = {
    'paramount': ('paramount_skydance_paramount_global', 2025, '2025-12-31', 63, 10),
    'salesforce': ('salesforce', 2026, '2026-01-31', 64, 36),
}
assert len(sys.argv) == 2 and sys.argv[1] in CASES
short = sys.argv[1]
company, fiscal_year, period_end, source_count, grouped_count = CASES[short]
state = Path('/private/tmp/issue28-c02-peer4d-' + short + '-20261002')
assert not state.exists()
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
signal.alarm(1200)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    first = run_company(state_root=state, source_root=ROOT,
                        company_id=company, metric_ids=['C02'])
    repeat = run_company(state_root=state, source_root=ROOT,
                         company_id=company, metric_ids=['C02'])
assert before == sha256_file(path=source_log)
one, two = first['metrics'][0], repeat['metrics'][0]
assert one['status'] == 'CANDIDATE_READY'
assert two['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert one['successful_attempt'] == two['successful_attempt']
result = one['last_verified_candidate']['results']['C02']
run = state / 'metrics/C02/attempts' / one['successful_attempt'] / 'runs/C02'
manifest = json.loads((run / 'manifest.json').read_text())
rows = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
candidate = next(row for row in rows if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
evidence = next(row for row in rows if row['record_type'] == 'EVIDENCE_CHECK')
represented = [index for check in evidence['checks']
               for index in check.get('selected_source_blocks', [])]
assert len(candidate['selected']) == grouped_count
assert len(represented) == len(set(represented)) == source_count
body = {
    'record_type': 'ISSUE28_C02_PEER4D_PRIVATE_NORMAL_UPDATE',
    'fixed_peer_sha': '4d0b2b9d4718e36ec84ed87588863f98ba5e4bb9',
    'company_id': company, 'fiscal_year': fiscal_year, 'period_end': period_end,
    'selected_original_source_blocks': len(represented),
    'grouped_excerpt_count': len(candidate['selected']),
    'first_status': one['status'], 'repeat_status': two['status'],
    'run_id': manifest['run_id'], 'result_id': result['result_id'],
    'candidate_hash': candidate['candidate_hash'],
    'requirement_closure_hash': manifest['requirement_closure_hash'],
    'source_log_unchanged': True, 'new_real_calls': [0, 0, 0],
    'business_content_acceptance': False, 'current_390_credit': False,
    'production_authorized': False, 'state_root': str(state),
}
(HERE / ('peer4d-' + short + '-update.json')).write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
