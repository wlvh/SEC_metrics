"""Summarize the finished private metric attempts without rerunning them."""
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-current-36-20260929')
result = json.loads((HERE/'result.json').read_text())
rows = []
for entry in result['metric_rows']:
    metric = entry['metric_id']
    current = WORK/'state/metrics'/metric/'current.json'
    if not current.is_file():
        rows.append({'metric_id': metric, 'status': entry['status'],
                     'duration_seconds': None})
        continue
    state = json.loads(current.read_text())
    attempt = WORK/'state/metrics'/metric/'attempts'/state['latest_attempt']
    intent = json.loads((attempt/'intent.json').read_text())
    terminal = json.loads((attempt/'terminal.json').read_text())
    start = datetime.fromisoformat(intent['started_at'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(terminal['completed_at'].replace('Z', '+00:00'))
    rows.append({'metric_id': metric, 'status': terminal['status'],
        'duration_seconds': round((end-start).total_seconds(), 3),
        'result_id': entry['result_id']})
assert len(rows) == len(result['metric_ids'])
body = {'record_type': 'ISSUE28_MARRIOTT_ORDINARY_UPDATE_TIMING',
    'source_snapshot_id': result['source_snapshot_id'],
    'metric_count': len(rows), 'metric_rows': rows,
    'known_seconds_sum': round(sum(row['duration_seconds'] or 0 for row in rows), 3),
    'timing_kind': 'INTENT_TO_TERMINAL_PER_METRIC_NOT_WHOLE_JOB_WALL_TIME'}
(HERE/'timing.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'metric_count': len(rows),
    'known_seconds_sum': body['known_seconds_sum'],
    'slowest': sorted((row for row in rows if row['duration_seconds'] is not None),
        key=lambda row: -row['duration_seconds'])[:8]}, sort_keys=True))
