"""Actual wrong-company import must retain the existing C04 source and Run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
EVIDENCE = Path(__file__).resolve().parent / 'consumer-v1'
STATE = BASE / 'state-marriott_international'
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'
env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'COMPANY_TEST_RUNTIME': str(BASE/'runtime')}


def hashes(paths):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


protected_paths = [STATE/'current_source.json'] + list((STATE/'source').rglob('*'))
protected_paths += [p for p in STATE.rglob('*') if '/attempts/' in str(p)]
before = hashes(protected_paths)
steps = []
for name, args, expected in [
    ('wrong-company-import', ['install', '--package-root', str(BASE/'package-enphase_energy'),
       '--state-root', str(STATE), '--trust-root', str(BASE/'source-trust'), '--company', 'marriott_international'], 1),
    ('c04-after-rejected-import', ['compute', '--state-root', str(STATE),
       '--trust-root', str(BASE/'source-trust'), '--company', 'marriott_international', '--metric', 'C04'], 0),
]:
    start = time.monotonic()
    command = [PYTHON, str(BASE/'guarded-cli.py'), *args]
    with (EVIDENCE/(name+'.log')).open('w') as stream:
        done = subprocess.run(command, cwd=BASE/'runtime', env=env, stdout=stream, stderr=subprocess.STDOUT)
    steps.append({'name': name, 'exit': done.returncode, 'seconds': round(time.monotonic()-start,3)})
    assert done.returncode == expected, name
rejected = (EVIDENCE/'wrong-company-import.log').read_text()
assert 'COMPANY_SOURCE_WRONG_COMPANY' in rejected
failed_import = json.loads((STATE/'latest_import.json').read_text())
assert failed_import['status'] == 'FAILED' and failed_import['committed_source_unchanged'] is True
after = hashes(protected_paths)
assert before == after
report = json.loads((EVIDENCE/'c04-after-rejected-import.log').read_text())
original = json.loads((EVIDENCE/'summary.json').read_text())['marriott_international']['compute']['metrics'][0]
current = report['metrics'][0]
assert current['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert current['successful_attempt'] == original['successful_attempt']
result = {'status':'PASS_ACTUAL_C04_REJECTED_IMPORT_RECOVERY', 'steps':steps,
          'source_pointer_and_original_run_files_unchanged': before==after,
          'checked_file_count':len(before), 'same_successful_attempt':current['successful_attempt'],
          'latest_import_failed_separate_from_current_committed_source':failed_import,
          'new_business_calls':[0,0,0], 'whole_business_or_cluster_acceptance':False}
(EVIDENCE/'negative-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'steps':steps,'files_unchanged':len(before)},indent=2))
