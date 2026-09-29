"""Compare Pfizer's new private records with the retained 390 index fields."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
parent = HERE.parent/'d04-remaining-20260922/current-390.json'
index = json.loads(parent.read_text())
old = {row['metric_id']: row for row in index['rows']
       if row['company_id'] == 'pfizer'
       and row['metric_id'] not in {'B13', 'D03', 'D04'}}
current = json.loads((HERE/'cold.json').read_text())
assert len(old) == len(current['rows']) == 36
rows = []
for result in current['rows']:
    metric = result['metric_id']
    previous = old[metric]
    if result['result_id'] is None:
        rows.append({'metric_id': metric, 'current_status': result['status'],
            'business_fields_equal': None,
            'historical_result_id': previous['implementation_identity']['result_id'],
            'current_result_id': None, 'result_id_equal': False})
        continue
    fields = {'value': previous['value'] == result['value'],
        'unit': previous['unit'] == result['unit'],
        'reason_code': previous['reason_code'] == result['reason_code'],
        'period_start': previous['source_period']['period_start'] == result['period_start'],
        'period_end': previous['source_period']['period_end'] == result['period_end'],
        'quality': previous['quality'] == result['quality'],
        'applicability': previous['applicability'] == result['applicability']}
    rows.append({'metric_id': metric, 'current_status': result['status'],
        'business_fields_equal': fields,
        'historical_result_id': previous['implementation_identity']['result_id'],
        'current_result_id': result['result_id'],
        'result_id_equal': previous['implementation_identity']['result_id'] ==
            result['result_id']})
body = {'record_type': 'ISSUE28_PFIZER_PRIVATE_36_OLD_INDEX_COMPARISON',
    'historical_index': str(parent.relative_to(HERE.parents[3])),
    'rows': rows,
    'comparable_business_fields_equal_count': sum(row['business_fields_equal'] is not None
        and all(row['business_fields_equal'].values()) for row in rows),
    'noncomparable_status_count': sum(row['business_fields_equal'] is None for row in rows),
    'same_result_id_count': sum(row['result_id_equal'] for row in rows),
    'historical_index_is_current_authority': False,
    'new_business_result_claim': False}
(HERE/'comparison.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'business_fields_equal_count': body['comparable_business_fields_equal_count'],
    'noncomparable_status_count': body['noncomparable_status_count'],
    'same_result_id_count': body['same_result_id_count'],
    'business_field_differences': [row['metric_id'] for row in rows
        if row['business_fields_equal'] is not None
        and not all(row['business_fields_equal'].values())]}, sort_keys=True))
