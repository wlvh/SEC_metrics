"""Recheck all ten current saved source candidates after removing page joining."""
import json
from pathlib import Path
import signal
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.d01_emphasis_results import create_deterministic_text_candidate
from vnext.normal_run_v3 import prepare_case
from vnext.canonical import sha256_file

prior = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                    'collab-d01-source-successor-20261002/measure-current.json').read_text())
before = (sha256_file(path=ROOT / 'evidence/requests_log.csv'),
          sha256_file(path=Path('/Users/lyuhongwang/.local/state/sec_metrics/'
                                'issue28-2026-09-13/claims.jsonl')))
signal.alarm(1800)
rows = []
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    for row in prior['rows']:
        assert 'new_candidate_hash' in row
        case = prepare_case(data_root=ROOT, company_id=row['company_id'],
                            metric_id='D01', d01_emphasis=True)
        candidate = create_deterministic_text_candidate(**case['text_arguments'])
        assert candidate['candidate_hash'] == row['new_candidate_hash']
        assert len(candidate['selected']) == row['new_count']
        rows.append({'company_id': row['company_id'],
                     'candidate_hash': candidate['candidate_hash'],
                     'selected_count': len(candidate['selected']),
                     'exact_prior_source_candidate_reproduced': True})
after = (sha256_file(path=ROOT / 'evidence/requests_log.csv'),
         sha256_file(path=Path('/Users/lyuhongwang/.local/state/sec_metrics/'
                               'issue28-2026-09-13/claims.jsonl')))
assert before == after and len(rows) == 10
body = {'record_type': 'ISSUE28_D01_PAGE_RULE_CURRENT_SOURCE_REGRESSION',
        'status': 'PASS_TEN_SAVED_CURRENT_CANDIDATES_BYTE_IDENTICAL',
        'rows': rows, 'new_real_calls': [0, 0, 0],
        'source_log_and_ledger_unchanged': True,
        'scope_limit': 'Source candidate comparison only; not all content or 390 acceptance.'}
(HERE / 'current-ten.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'], 'rows': len(rows)}), flush=True)
