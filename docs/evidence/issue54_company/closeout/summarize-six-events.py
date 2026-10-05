"""Summarize the fixed six-event experiment, keeping overlapping costs separate."""
import csv, hashlib, json
from pathlib import Path
w=Path('/workspace/work')
def trace(name):
    rows=[json.loads(line) for line in (w/name).read_text().splitlines()]
    assert rows[-1]['phase']=='complete'
    return rows
before=trace('closeout-before-profile.jsonl');after=trace('closeout-after-profile.jsonl')
def candidates(rows):
    return {r['metric_id']:r['last_verified_candidate']['receipt'] for r in rows[-1]['result']['metrics']}
b=candidates(before);a=candidates(after)
consumer={p['metric_id']:p['company_path'] for p in json.loads((w/'closeout-consumer-compare.json').read_text())['positions']}
view=json.loads((w/'closeout-after-results.jsonl').read_text())
export=json.loads((w/'closeout-after-export/company-results.json').read_text())
comparisons=[]
for metric in b:
    old,new=b[metric],a[metric];prior=consumer[metric]
    checks={'before_after_result_id':old['public_row']['result_id']==new['public_row']['result_id'],
            'before_after_row_hash':old['public_row']['row_hash']==new['public_row']['row_hash'],
            'consumer_result_id':new['public_row']['result_id']==prior['result_id'],
            'consumer_row_hash':new['public_row']['row_hash']==prior['row_hash'],
            'consumer_period_selection':new['public_row']['period_selection_id']==prior['period_selection_id']}
    assert all(checks.values()),(metric,checks)
    window=next(r for r in new['results'] if r['metric_id']==metric)
    entry=next(e for e in view['metrics'] if e['metric_id']==metric)
    replayed=next(e for e in export['metrics'] if e['metric_id']==metric)
    assert entry['period']['period_start']=='2025-01-01'
    assert entry['measurement_period']=={'period_start':'2024-01-01','period_end':'2025-12-31'}
    assert replayed['measurement_period_status']=='NATIVE_REPLAY_VERIFIED' and replayed['replay_status']=='PASSED'
    assert replayed['measurement_period']==entry['measurement_period']
    comparisons.append({'metric_id':metric,'checks':checks,'result_id':new['public_row']['result_id'],
        'row_hash':new['public_row']['row_hash'],'archive_period':new['target_period'],
        'measurement_period':entry['measurement_period'], 'before_run':old['run_id'],'after_run':new['run_id'],
        'before_runtime':old['requirement_closure_hash'],'after_runtime':new['requirement_closure_hash']})
repeat=json.loads((w/'closeout-after-partial-repeat.jsonl').read_text())
assert len(view['metrics'])==6 and repeat['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
matrix=list(csv.DictReader((w/'closeout-after-export/metrics_matrix.csv').open()))
assert len(matrix)==6 and {r['metric_id'] for r in matrix}==set(a)
assert all(r['archive_period_start']=='2025-01-01' and r['measurement_period_start']=='2024-01-01' for r in matrix)
summary={'scenario':{'company':'paramount_skydance_paramount_global','report_end':'2025-12-31','metrics':list(a),
    'uid':after[0]['uid'],'source_root_before':before[0]['source'],'source_root_after':after[0]['source'],
    'same_package':'sha256:a48403140e84c58cdd122bb7e45e1ca492492dbd0eeace0a4320ead7c30ad3e4',
    'condition':'Sequential workers, fresh Python, separate per-metric data, warm filesystem cache. Same container; no kernel cache flush or exclusive host-load control.'},
    'before':{'seconds':before[-1]['seconds'],'counts':before[-1]['counts']},
    'after':{'seconds':after[-1]['seconds'],'counts':after[-1]['counts']},
    'speedup':before[-1]['seconds']/after[-1]['seconds'],
    'timing_note':'Compute totals exclude preparation/runtime/source installation and independent cold export. Inclusive phase costs overlap with preparation/validation; do not sum them.',
    'original_consumer_704_note':'Shared layout, block/memo enabled, includes163.3s independent read-back; original5197s company compute did not contain that read-back. Not a controlled speed ratio.',
    'identical_results':comparisons,'independent_cold_export_passed':6,'partial_repeat_preserves_results':6,
    'company_matrix_rows':len(matrix),'company_evidence_rows':sum(1 for _ in csv.DictReader((w/'closeout-after-export/metric_evidence.csv').open())),
    'new_business_calls':[0,0,0],'business_content_accepted':False,'openshift_acceptance':False}
(w/'closeout-performance-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in {'before','after','identical_results'}},indent=2))
