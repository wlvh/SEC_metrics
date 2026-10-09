"""Read timestamp intervals from the already saved Salesforce 36-run."""
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('/private/tmp/issue28-salesforce-current-36-cli-20261001/state/salesforce/metrics')
rows = []
for terminal in ROOT.glob('*/attempts/*/terminal.json'):
    metric = terminal.relative_to(ROOT).parts[0]
    value = json.loads(terminal.read_text())
    finished = datetime.fromisoformat(value['completed_at']).timestamp()
    attempt = terminal.parent
    record = attempt / 'runs' / metric / 'records.jsonl'
    publication = attempt / 'rows' / metric / 'metrics_matrix.csv'
    rows.append({'metric_id': metric, 'completed_at': value['completed_at'],
        'terminal_status': value['status'], 'completed_epoch': finished,
        'records_to_rows_seconds': None if not record.is_file() or not publication.is_file()
            else round(publication.stat().st_mtime - record.stat().st_mtime, 3),
        'rows_to_terminal_seconds': None if not publication.is_file()
            else round(terminal.stat().st_mtime - publication.stat().st_mtime, 3)})
rows.sort(key=lambda row: row['completed_epoch'])
for index, row in enumerate(rows):
    row['since_previous_terminal_seconds'] = None if index == 0 else round(
        row['completed_epoch'] - rows[index - 1]['completed_epoch'], 3)
for row in rows:
    del row['completed_epoch']
long_intervals = [row for row in rows if
    (row['since_previous_terminal_seconds'] or 0) >= 900]
body = {'record_type': 'ISSUE28_SALESFORCE_PRIOR_36_FILE_TIMESTAMP_INTERVALS',
    'source_scope': str(ROOT), 'row_count': len(rows),
    'long_terminal_interval_threshold_seconds': 900,
    'long_terminal_interval_count': len(long_intervals),
    'rows': rows, 'causal_root_proven': False}
(HERE / 'prior-timings.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'row_count': len(rows),
    'long_intervals': [(row['metric_id'], row['since_previous_terminal_seconds'])
        for row in long_intervals],
    'causal_root_proven': False}, sort_keys=True))
