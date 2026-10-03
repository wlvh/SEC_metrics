"""One no-network Marriott update over all 36 ordinary #28 routes."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import sha256_file
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.normal_run_v3 import update_metric_ids
from vnext.ordinary_b03_scope_update import run_company
from vnext.ordinary_processing_source import current_processing_source
from vnext.requirements import load_requirement_snapshot

HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-current-36-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
CLAIMS = ACQUIRED.parent/'claims.jsonl'
METRICS = [metric for metric in update_metric_ids()
           if metric not in {'B13', 'D04'}]
assert len(METRICS) == 36 and not WORK.exists()
before = {'source_log': sha256_file(path=ACQUIRED/'evidence/requests_log.csv'),
          'claims': sha256_file(path=CLAIMS)}
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    source = current_processing_source(acquisition_root=ACQUIRED,
        output_parent=WORK/'sources', requirement=requirement)
    print('SOURCE_SNAPSHOT', source['snapshot_id'], flush=True)
    outcome = run_company(state_root=WORK/'state',
        source_root=source['data_root'], source_identity_root=ACQUIRED,
        company_id='marriott_international', metric_ids=METRICS)
after = {'source_log': sha256_file(path=ACQUIRED/'evidence/requests_log.csv'),
         'claims': sha256_file(path=CLAIMS)}
assert before == after and outcome['calls'] == {
    'provider': 0, 'paid': 0, 'sec': 0}
rows = []
for item in outcome['metrics']:
    candidate = item.get('last_verified_candidate')
    metric = item['metric_id']
    result = ((candidate.get('results') or {}).get(metric)
              if isinstance(candidate, dict) else None)
    rows.append({'metric_id': metric, 'status': item['status'],
        'reason': item.get('reason'), 'error': item.get('error'),
        'terminal_error': (item.get('terminal') or {}).get('error'),
        'result_id': result.get('result_id') if isinstance(result, dict) else None,
        'result_publication': result.get('publication')
            if isinstance(result, dict) else None,
        'result_reason': result.get('reason_code')
            if isinstance(result, dict) else None})
body = {'record_type': 'ISSUE28_MARRIOTT_36_ORDINARY_PRIVATE_UPDATE',
    'company_id': 'marriott_international', 'metric_ids': METRICS,
    'source_snapshot_id': source['snapshot_id'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'source_and_claims_unchanged': before == after,
    'status': outcome['status'], 'metric_rows': rows,
    'calls': [0, 0, 0], 'production_authorized': False,
    'new_fiscal_year_source_arrival_proven': False,
    'all390_acceptance': False}
(HERE/'result.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': outcome['status'],
    'metric_count': len(rows),
    'status_counts': {state: sum(row['status'] == state for row in rows)
        for state in sorted({row['status'] for row in rows})},
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
