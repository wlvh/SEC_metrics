"""Compare current ten saved D01 originals under old and explicit source readers."""
import csv
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
from vnext.d01_emphasis_results import create_deterministic_text_candidate
from vnext.normal_run_v3 import prepare_case

companies = [row['company_id'] for row in csv.DictReader(
    (ROOT / 'config/company_registry.csv').open())]
assert len(companies) == len(set(companies)) == 10
before = (sha256_file(path=ROOT / 'evidence/requests_log.csv'),
          sha256_file(path=Path('/Users/lyuhongwang/.local/state/sec_metrics/'
                                'issue28-2026-09-13/claims.jsonl')))
signal.alarm(1800)
rows = []
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    for company in companies:
        try:
            case = prepare_case(data_root=ROOT, company_id=company, metric_id='D01',
                                d01_emphasis=True)
            args = case['text_arguments']
            new = create_deterministic_text_candidate(**args)
            old = create_deterministic_text_candidate(**{
                key: value for key, value in args.items() if key != 'd01_emphasis_policy'})
            old_text = {claim['text'] for claim in old['selected'].values()}
            new_text = {claim['text'] for claim in new['selected'].values()}
            rows.append({'company_id': company, 'period_end': args['target']['period_end'],
                         'old_count': len(old['selected']), 'new_count': len(new['selected']),
                         'added': sorted(new_text - old_text),
                         'removed': sorted(old_text - new_text),
                         'new_candidate_hash': new['candidate_hash']})
        except Exception as error:
            rows.append({'company_id': company, 'status': 'REQUIRES_INVESTIGATION',
                         'error_type': type(error).__name__, 'reason': str(error)})
after = (sha256_file(path=ROOT / 'evidence/requests_log.csv'),
         sha256_file(path=Path('/Users/lyuhongwang/.local/state/sec_metrics/'
                               'issue28-2026-09-13/claims.jsonl')))
assert before == after
body = {'record_type': 'ISSUE28_D01_CURRENT_SAVED_SOURCE_COMPARISON',
        'fixed_peer_read': '2b4f571ef18274299145c63b4c355aa97c45d030',
        'rows': rows, 'new_real_calls': [0, 0, 0],
        'source_log_and_ledger_unchanged': True,
        'source_selection_only_no_content_acceptance': True}
(HERE / 'measure-current.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'rows': len(rows), 'changed': [r['company_id'] for r in rows
                  if r.get('added') or r.get('removed')],
                  'unresolved': [r['company_id'] for r in rows
                                 if r.get('status') == 'REQUIRES_INVESTIGATION']}), flush=True)
