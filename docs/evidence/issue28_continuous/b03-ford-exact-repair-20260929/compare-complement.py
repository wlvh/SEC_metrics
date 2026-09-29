"""Compare business fields for the 34 current-closure Ford replays."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
old = json.loads((HERE.parent/'ordinary-ford-current-36-cli-20260929'/'cold.json').read_text())
new = json.loads((HERE/'complement-report.json').read_text())
old_rows = {row['metric_id']: row for row in old['rows']
            if row['status'] == 'CANDIDATE_READY'}
company, = new['companies']
new_rows = {}
for row in company['metrics']:
    metric = row['metric_id']
    assert row['status'] == 'CANDIDATE_READY'
    new_rows[metric] = row['last_verified_candidate']['results'][metric]
assert len(old_rows) == len(new_rows) == 34
assert set(old_rows) == set(new_rows)
same_result_ids = [metric for metric in old_rows if
                   old_rows[metric]['result_id'] ==
                   new_rows[metric]['result_id']]
keys = ('value', 'unit', 'reason_code', 'publication', 'period_start',
        'period_end', 'quality', 'applicability')
differences = []
for metric in sorted(old_rows):
    for key in keys:
        if old_rows[metric].get(key) != new_rows[metric].get(key):
            differences.append({'metric_id': metric, 'field': key,
                'old': old_rows[metric].get(key),
                'current': new_rows[metric].get(key)})
body = {'record_type': 'ISSUE28_FORD_B03_CURRENT_CLOSURE_34_BUSINESS_FIELD_COMPARISON',
        'compared_metric_count': len(old_rows),
        'fields': list(keys), 'differences': differences,
        'all_compared_business_fields_same': not differences,
        'same_result_id_count': len(same_result_ids),
        'different_result_id_count': len(old_rows) - len(same_result_ids),
        'new_real_calls': [0, 0, 0]}
(HERE/'complement-comparison.json').write_text(json.dumps(body,
    ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'compared': len(old_rows),
    'difference_count': len(differences),
    'same_result_id_count': len(same_result_ids),
    'calls': [0, 0, 0]},
    sort_keys=True), flush=True)
assert not differences
