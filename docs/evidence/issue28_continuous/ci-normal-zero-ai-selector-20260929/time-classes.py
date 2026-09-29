"""Time the two unchanged classes of the one CI-timed-out source selector."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
module = 'tests.vnext.test_normal_zero_ai_results'
classes = ('OrdinaryZeroAiPrototypeTest', 'OrdinaryZeroAiAdditionalRoutesTest')
environment = dict(os.environ)
environment['PYTHONPATH'] = 'scripts:.'
environment['PYTHONDONTWRITEBYTECODE'] = '1'
results = []
for name in classes:
    log = HERE / (name + '.log')
    started = time.monotonic()
    with log.open('wb') as handle:
        completed = subprocess.run([sys.executable, '-m', 'unittest', '-v',
            module + '.' + name], cwd=ROOT, env=environment,
            stdout=handle, stderr=subprocess.STDOUT, check=False)
    elapsed = time.monotonic() - started
    row = {'selector': module + '.' + name,
           'exit_code': completed.returncode,
           'elapsed_seconds': round(elapsed, 3), 'log': log.name}
    results.append(row)
    print(json.dumps(row, sort_keys=True), flush=True)
body = {'record_type': 'ISSUE28_NORMAL_ZERO_AI_SELECTOR_CLASS_TIMING',
    'source_module_unchanged': True,
    'shard0_prior_remote_pass_seconds': 226.062,
    'shard0_later_remote_timeout_seconds': 240.117,
    'remote_timeout_seconds': 240,
    'classes': results,
    'test_assertions_modified': False,
    'new_real_calls': [0, 0, 0]}
(HERE/'timing.json').write_text(json.dumps(body, indent=2) + '\n')
assert len(results) == 2 and all(row['exit_code'] == 0 for row in results)
