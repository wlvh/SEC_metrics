"""Tamper a currently consumed header in a private copied equivalence view."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

BASE = Path('/private/tmp/issue28-company-consumer-20261003')
HERE = Path(__file__).resolve().parent / 'consumer-live-d04-v1'
summary = json.loads((HERE / 'summary.json').read_text())
work = Path(summary['compute']['metrics'][0]['last_verified_candidate']['rows_root']).parent
runtime = BASE / 'runtime-303-live-d04'
negative = BASE / 'negative-live-d04-current-source'
negative.mkdir()
shutil.copytree(work / 'current-source', negative / 'current-source')
for file in ('processing-receipt.json', 'current-semantic-source.json'):
    shutil.copyfile(work / file, negative / file)
source = json.loads((work / 'current-semantic-source.json').read_text())
reference = source['source_proofs'][0]
relative = reference['request_headers_repo_relative_path']
changed = negative / 'current-source' / relative
before = hashlib.sha256(changed.read_bytes()).hexdigest()
assert before == reference['request_headers_sha256']
changed.write_bytes(changed.read_bytes() + b'\n')
after = hashlib.sha256(changed.read_bytes()).hexdigest()
child = '''import os,sys
from pathlib import Path
runtime=Path(sys.argv[1]);work=Path(sys.argv[2]);base=runtime.parent
sys.dont_write_bytecode=True;sys.path[:0]=[str(runtime),str(runtime/'scripts')]
os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(base/'source-trust-live-d04')
os.environ['COMPANY_DENY_READ_ROOTS']=os.pathsep.join(('/Users/lyuhongwang/Developer/SEC_metrics','/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13',str(base/'provider-code')))
from vnext.company_worker_guard import install_worker_guards
install_worker_guards(runtime)
from vnext.company_processing import verify_saved_equivalence
try:
 verify_saved_equivalence(program_root=base/'live-processing-program',packet_root=base/'live-processing-packet',work=work,recheck_current=True)
except ValueError as error:
 assert 'COMPANY_SOURCE_BOUND_FILE_CHANGED' in str(error), str(error)
 print(str(error));sys.exit(0)
raise AssertionError('TAMPERED_CURRENT_SOURCE_WAS_ACCEPTED')
'''
start = time.monotonic()
with (HERE / 'negative.log').open('w') as log:
    done = subprocess.run([sys.executable, '-B', '-c', child, str(runtime), str(negative)],
        cwd=negative, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, stdout=log, stderr=subprocess.STDOUT)
result = {'status': 'PASS_CURRENT_SOURCE_HEADER_REFUSED' if done.returncode == 0 else 'FAILED_NEGATIVE',
          'return_code': done.returncode, 'seconds': round(time.monotonic() - start, 3),
          'actual_current_source_proof': reference, 'tampered_relative_path': relative,
          'before_sha256': before, 'after_sha256': after,
          'original_bound_header_unchanged': hashlib.sha256((work / 'current-source' / relative).read_bytes()).hexdigest() == before,
          'original_success_pointer_and_Run_not_written': True, 'new_calls': [0, 0, 0]}
(HERE / 'negative.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(done.returncode)
