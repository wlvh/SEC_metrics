"""Measure the completed private 36-metric run without re-executing it."""
from datetime import datetime
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
METRICS = Path('/private/tmp/issue28-southwest-current-36-cli-20260929/state/'
    'southwest_airlines/metrics')
created = json.loads((HERE/'result.json').read_text())
rows = []
for item in created['rows']:
    metric = item['metric_id']
    root = METRICS/('C04-registration-v3' if metric == 'C04' else metric)
    state = json.loads((root/'current.json').read_text())
    attempt = root/'attempts'/state['latest_attempt']
    intent = json.loads((attempt/'intent.json').read_text())
    terminal = json.loads((attempt/'terminal.json').read_text())
    start = datetime.fromisoformat(intent['started_at'])
    end = datetime.fromisoformat(terminal['completed_at'])
    rows.append({'metric_id': metric,
        'intent_to_terminal_seconds': round((end-start).total_seconds(), 3),
        'terminal_status': terminal['status'],
        'started_at': intent['started_at'],
        'completed_at': terminal['completed_at']})
assert len(rows) == 36
file_birth_seconds = {}
for stem in ('run', 'cold'):
    first = (HERE/f'{stem}.log').stat().st_birthtime
    last = (HERE/f'{stem}.exit').stat().st_birthtime
    file_birth_seconds[stem] = round(last-first, 3)
body = {'record_type': 'ISSUE28_SOUTHWEST_36_PRIVATE_TIMING',
    'native_intent_to_terminal_sum_seconds': round(sum(
        row['intent_to_terminal_seconds'] for row in rows), 3),
    'native_first_intent': min(row['started_at'] for row in rows),
    'native_last_terminal': max(row['completed_at'] for row in rows),
    'file_birth_elapsed_seconds': file_birth_seconds,
    'file_birth_elapsed_is_local_host_observation': True,
    'top_five_metric_durations': sorted(rows,
        key=lambda row: row['intent_to_terminal_seconds'], reverse=True)[:5],
    'rows': rows,
    'new_real_calls': [0, 0, 0]}
(HERE/'timing.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'sum_metric_seconds': body['native_intent_to_terminal_sum_seconds'],
    'local_run_file_elapsed_seconds': file_birth_seconds['run'],
    'local_cold_file_elapsed_seconds': file_birth_seconds['cold'],
    'top_five': [(row['metric_id'], row['intent_to_terminal_seconds'])
        for row in body['top_five_metric_durations']]}, sort_keys=True))
