"""Compare current private results with the old 390 index without adopting it."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-marriott-current-36-20260929/state/metrics')
old_index = json.loads((HERE.parent/'d04-remaining-20260922/current-390.json').read_text())
prior = {row['metric_id']: row for row in old_index['rows']
         if row['company_id'] == 'marriott_international'}
current = json.loads((HERE/'result.json').read_text())
rows = []
for summary in current['metric_rows']:
    metric = summary['metric_id']
    state = json.loads((STATE/metric/'current.json').read_text())
    run = (STATE/metric/'attempts'/state['successful_attempt']/'runs'/metric)
    records = [json.loads(line) for line in (run/'records.jsonl').read_text().splitlines()]
    actual, = [row for row in records if row.get('record_type') == 'METRIC_RESULT'
               and row.get('metric_id') == metric]
    assert summary['result_id'] == actual['result_id']
    old = prior[metric]
    fields = {'value': old['value'] == actual['value'],
        'unit': old['unit'] == actual['unit'],
        'reason_code': old['reason_code'] == actual['reason_code'],
        'period_start': old['source_period']['period_start'] == actual['period_start'],
        'period_end': old['source_period']['period_end'] == actual['period_end'],
        'quality': old['quality'] == actual['quality'],
        'applicability': old['applicability'] == actual['applicability']}
    rows.append({'metric_id': metric, 'fields_equal': fields,
        'historical_result_id': old['implementation_identity']['result_id'],
        'current_result_id': actual['result_id'],
        'result_identity_equal': old['implementation_identity']['result_id']
            == actual['result_id']})
assert len(rows) == 36
body = {'record_type': 'ISSUE28_MARRIOTT_PRIVATE_36_OLD_INDEX_COMPARISON',
    'historical_index': str(HERE.parent/'d04-remaining-20260922/current-390.json'),
    'rows': rows,
    'all_business_fields_equal': all(all(row['fields_equal'].values()) for row in rows),
    'same_result_id_count': sum(row['result_identity_equal'] for row in rows),
    'historical_index_is_current_authority': False,
    'new_business_result_claim': False}
(HERE/'comparison.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'all_business_fields_equal': body['all_business_fields_equal'],
    'same_result_id_count': body['same_result_id_count'],
    'different_result_id_count': 36-body['same_result_id_count']},
    sort_keys=True))
