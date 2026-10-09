"""Re-read representative private metric histories in a new Python process."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import sha256_file
from vnext import ordinary_update_cycle as ordinary
from vnext import ordinary_b03_scope_update as guarded

HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-current-36-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
CLAIMS = ACQUIRED.parent/'claims.jsonl'
SELECTED = ('A01', 'B01', 'B03', 'B06', 'C04', 'D02', 'E01')
full = json.loads((HERE/'result.json').read_text())
by_metric = {row['metric_id']: row for row in full['metric_rows']}
assert len(by_metric) == 36 and set(SELECTED) <= set(by_metric)
before = (sha256_file(path=ACQUIRED/'evidence/requests_log.csv'),
          sha256_file(path=CLAIMS))
checked = []
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    for metric in SELECTED:
        row = by_metric[metric]
        if row['status'] != 'CANDIDATE_READY':
            checked.append({'metric_id': metric, 'status': row['status'],
                'cold_result': 'NOT_A_SUCCESS_CANDIDATE'})
            continue
        root = WORK/'state/metrics'/metric
        config = ordinary._config(root, ACQUIRED, 'marriott_international',
                                  [metric], 'LIVE')
        state = ordinary._state(root, config)
        assert state['successful_attempt'] is not None
        terminal = ordinary._terminal(root, state['successful_attempt'])
        verifier = guarded._verify_candidate if metric == 'B03' else \
            ordinary._verify_candidate
        result = verifier(root, terminal, config)[metric]
        assert result['result_id'] == row['result_id']
        checked.append({'metric_id': metric, 'status': row['status'],
            'cold_result': 'PASS_INSTALLED_RUN_AND_ROW_REPLAY',
            'result_id': result['result_id'],
            'publication': result['publication'],
            'reason_code': result['reason_code']})
after = (sha256_file(path=ACQUIRED/'evidence/requests_log.csv'),
         sha256_file(path=CLAIMS))
assert before == after
body = {'record_type': 'ISSUE28_MARRIOTT_PRIVATE_ORDINARY_COLD_READ',
    'selected_metrics': list(SELECTED), 'rows': checked,
    'original_source_and_claims_unchanged': True,
    'calls': [0, 0, 0], 'production_authorized': False}
(HERE/'cold.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'checked': len(checked),
    'replayed': sum(row['cold_result'] == 'PASS_INSTALLED_RUN_AND_ROW_REPLAY'
        for row in checked), 'calls': [0, 0, 0]}, sort_keys=True))
