"""Independent-process, no-network D01 source/Run and update-state replay."""
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

CASES = {'paramount': 'paramount_skydance_paramount_global',
         'marriott': 'marriott_international'}
assert len(sys.argv) in {2, 3} and sys.argv[1] in CASES
short = sys.argv[1]
final = len(sys.argv) == 3 and sys.argv[2] == 'final'
assert len(sys.argv) == 2 or final
company = CASES[short]
state = Path('/private/tmp/issue28-d01-emphasis-' + short + '-20261002'
             + ('-final' if final else ''))
metric_root = state / 'metrics/D01'
source_log = ROOT / 'evidence/requests_log.csv'
before = sha256_file(path=source_log)
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    config = cycle._config(metric_root, ROOT, company, ['D01'], 'LIVE')
    snapshot = cycle._state(metric_root, config)
    success = cycle._terminal(metric_root, snapshot['successful_attempt'])
    repeat = cycle._terminal(metric_root, snapshot['latest_attempt'])
    result = cycle._verify_candidate(metric_root, success, config)['D01']
assert before == sha256_file(path=source_log)
assert success['status'] == 'CANDIDATE_READY'
assert repeat['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
prior = json.loads((HERE / (('final-' if final else '') + short + '-private-update.json')).read_text())
assert prior['result_id'] == result['result_id']
body = {'record_type': 'ISSUE28_D01_EMPHASIS_PRIVATE_COLD_READ',
        'company_id': company, 'result_id': result['result_id'],
        'first_status': success['status'], 'repeat_status': repeat['status'],
        'source_log_unchanged': True, 'new_real_calls': [0, 0, 0],
        'current_390_credit': False, 'production_authorized': False}
(HERE / (('final-' if final else '') + short + '-cold-read.json')).write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
