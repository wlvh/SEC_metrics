"""Classify the completed 36-metric CLI report without repeating the run."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
saved = json.loads((HERE/'result.json').read_text())
assert (HERE/'run.exit').read_text().strip() == '1'
rows = {row['metric_id']: row for row in saved['rows']}
assert saved['metric_count'] == len(rows) == 36
assert saved['normal_cli_return_code'] == 2
assert saved['status'] == 'UPDATES_PARTIAL'
assert saved['reported_calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
assert saved['original_claims_source_and_active_unchanged']
assert rows['B06']['status'] == 'CANDIDATE_WITHHELD'
assert rows['B06']['result_id'] is None
assert all(row['status'] == 'CANDIDATE_READY' and row['result_id']
           and row['publication'] == 'PUBLISHED'
           for metric, row in rows.items() if metric != 'B06')
body = {'record_type': 'ISSUE28_SOUTHWEST_NORMAL_CLI_PARTIAL_RESULT_CHECK',
    'original_script_exit': 1,
    'original_script_last_assertion_too_strict': True,
    'normal_cli_return_code': 2,
    'normal_cli_status': saved['status'],
    'candidate_ready_count': 35,
    'candidate_withheld_count': 1,
    'withheld_metric_id': 'B06',
    'other_metrics_untouched_by_B06_withholding': True,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'native_B06_reason_and_rows_separately_revalidated': False}
(HERE/'verification.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'status': body['normal_cli_status'],
    'ready': 35, 'withheld': 1, 'real_calls': [0, 0, 0]}, sort_keys=True))
