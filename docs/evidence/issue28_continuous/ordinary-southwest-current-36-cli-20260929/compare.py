"""Compare Southwest's new private Runs with the retained 390 index fields."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
parent = HERE.parent/'d04-remaining-20260922/current-390.json'
index = json.loads(parent.read_text())
old = {row['metric_id']: row for row in index['rows']
       if row['company_id'] == 'southwest_airlines'
       and row['metric_id'] not in {'B13', 'D03', 'D04'}}
current = json.loads((HERE/'cold.json').read_text())
assert len(old) == len(current['rows']) == 36
rows = []
for result in current['rows']:
    metric = result['metric_id']
    previous = old[metric]
    fields = {'value': previous['value'] == result['value'],
        'unit': previous['unit'] == result['unit'],
        'reason_code': previous['reason_code'] == result['reason_code'],
        'period_start': previous['source_period']['period_start'] == result['period_start'],
        'period_end': previous['source_period']['period_end'] == result['period_end'],
        'quality': previous['quality'] == result['quality'],
        'applicability': previous['applicability'] == result['applicability']}
    rows.append({'metric_id': metric, 'business_fields_equal': fields,
        'historical_result_id': previous['implementation_identity']['result_id'],
        'current_result_id': result['result_id'],
        'result_id_equal': previous['implementation_identity']['result_id'] ==
            result['result_id']})
body = {'record_type': 'ISSUE28_SOUTHWEST_PRIVATE_36_OLD_INDEX_COMPARISON',
    'historical_index': str(parent.relative_to(HERE.parents[3])),
    'rows': rows,
    'business_fields_equal_count': sum(all(row['business_fields_equal'].values())
                                       for row in rows),
    'same_result_id_count': sum(row['result_id_equal'] for row in rows),
    'historical_index_is_current_authority': False,
    'new_business_result_claim': False}
(HERE/'comparison.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'business_fields_equal_count': body['business_fields_equal_count'],
    'same_result_id_count': body['same_result_id_count'],
    'different_result_id_count': 36-body['same_result_id_count'],
    'business_field_differences': [row['metric_id'] for row in rows
        if not all(row['business_fields_equal'].values())]},
    sort_keys=True))
