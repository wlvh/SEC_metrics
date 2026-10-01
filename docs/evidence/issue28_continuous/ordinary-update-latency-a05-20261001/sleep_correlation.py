"""Correlate saved terminal gaps with local macOS sleep transitions."""
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
prior = json.loads((HERE / 'prior-timings.json').read_text())
rows = prior['rows']
local_tz = timezone(timedelta(hours=8))
raw = subprocess.check_output(['pmset', '-g', 'log'], text=True,
    errors='replace')
pattern = re.compile(r'^(2026-10-01 \d\d:\d\d:\d\d) \+0800 '
    r'(Sleep|DarkWake|Wake)\s+(.*)$')
events = []
for line in raw.splitlines():
    match = pattern.match(line)
    if not match or match[3].startswith('Requests'):
        continue
    action = match[2]
    if action == 'Sleep' and not match[3].startswith('Entering Sleep state'):
        continue
    if action == 'DarkWake' and not match[3].startswith('DarkWake from'):
        continue
    if action == 'Wake' and not match[3].startswith('Wake from'):
        continue
    events.append((datetime.strptime(match[1], '%Y-%m-%d %H:%M:%S')
                   .replace(tzinfo=local_tz).timestamp(), action))
events.sort()
spans = []
sleep_start = None
for stamp, action in events:
    if action == 'Sleep':
        sleep_start = stamp
    elif sleep_start is not None:
        spans.append((sleep_start, stamp))
        sleep_start = None


def overlap(first, end):
    return sum(max(0, min(end, stop) - max(first, start))
               for start, stop in spans)


intervals = []
for before, after in zip(rows, rows[1:]):
    start = datetime.fromisoformat(before['completed_at']).timestamp()
    end = datetime.fromisoformat(after['completed_at']).timestamp()
    sleep_seconds = overlap(start, end)
    intervals.append({'metric_id': after['metric_id'],
        'wall_seconds': round(end - start, 3),
        'macos_sleep_overlap_seconds': round(sleep_seconds, 3),
        'outside_logged_sleep_seconds': round(end - start - sleep_seconds, 3)})
long_intervals = [row for row in intervals if row['wall_seconds'] >= 900]
body = {'record_type': 'ISSUE28_SALESFORCE_TERMINAL_SLEEP_CORRELATION',
    'timezone': 'Asia/Shanghai', 'source_kind': 'local_pmset_sleep_wake_log',
    'source_scope': '2026-10-01 local 05:00-12:00 only',
    'sleep_spans_in_scope': len(spans),
    'long_interval_count': len(long_intervals),
    'long_intervals_with_sleep_overlap': sum(
        row['macos_sleep_overlap_seconds'] > 0 for row in long_intervals),
    'all_intervals_wall_seconds': round(sum(row['wall_seconds'] for row in intervals), 3),
    'all_intervals_sleep_overlap_seconds': round(sum(
        row['macos_sleep_overlap_seconds'] for row in intervals), 3),
    'intervals': intervals,
    'causal_limit': ('Sleep overlap explains unavailable wall time; it does not '
                     'measure active CPU time or prove source code has no latency issue.')}
(HERE / 'sleep-correlation.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({key: body[key] for key in (
    'sleep_spans_in_scope', 'long_interval_count',
    'long_intervals_with_sleep_overlap', 'all_intervals_wall_seconds',
    'all_intervals_sleep_overlap_seconds')}, sort_keys=True))
