"""Persist the real Enphase D04 candidate and independently cold read it."""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


evidence = Path(__file__).resolve().parent
original = Path('/tmp/sec_metrics_issue28_d04_enphase_real_20260924')
destination = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/native-candidate-results-20260924')
target = destination/'enphase_energy'
started = time.monotonic()
expected = json.loads((original/'summary.json').read_text())
assert expected['status'] == 'COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS'


def inventory(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


if target.exists():
    assert inventory(original) == inventory(target), 'PERSISTED_CANDIDATE_DIFFERS'
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(original, target)
    assert inventory(original) == inventory(target), 'PERSISTED_COPY_CHANGED'

empty = destination/'empty-cold-working-directory'
empty.mkdir(parents=True, exist_ok=True)
code = '''import sys,json
from pathlib import Path
base=Path(sys.argv[1]);sys.path.insert(0,str(base/'data'));sys.path.insert(0,str(base/'data/scripts'));sys.dont_write_bytecode=True
blocked=[]
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
  blocked.append(event);raise RuntimeError('NETWORK_OR_PROCESS_FORBIDDEN:'+event)
sys.addaudithook(audit)
from vnext.ordinary_projection import render_ordinary_run
from vnext import run_store
assert Path(run_store.__file__).resolve().is_relative_to(base/'data')
expected=json.loads((base/'summary.json').read_text())
rendered=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
assert rendered['receipt']['result_id']==expected['result_id'] and rendered['receipt']['semantic_assessment_mode']=='LIVE'
for name,raw in rendered['files'].items():assert (base/'rows'/name).read_bytes()==raw
assert not blocked
print(json.dumps({'status':'PASS_INSTALLED_RUNTIME_COLD_READ','company_id':expected['company_id'],'run_id':expected['run_id'],'result_id':expected['result_id'],'public_rows_identical':True,'network_or_process_events':blocked,'new_calls':[0,0,0]}))
'''
env = {k: v for k, v in os.environ.items()
       if k not in {'DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'SEC_CONTACT_EMAIL'}}
env['PYTHONDONTWRITEBYTECODE'] = '1'
with (evidence/'cold.log').open('wb') as stream:
    result = subprocess.run(['/tmp/sec_metrics_cold39_20260922/bin/python', '-c', code,
                             str(target)], stdout=stream, stderr=subprocess.STDOUT,
                            cwd=empty, env=env)
report = {'record_type':'ISSUE28_D04_ENPHASE_PERSISTED_INDEPENDENT_COLD_READ',
          'status':'PASS_PERSISTED_COMPLETE_CANDIDATE_AND_COLD_READ'
              if result.returncode == 0 else 'FAILED_COLD_READ_NO_RETRY',
          'company_id':'enphase_energy', 'persistent_candidate_root':str(target),
          'run_id':expected['run_id'], 'result_id':expected['result_id'],
          'source_file_count':len(inventory(original)),
          'identical_persisted_bytes':inventory(original) == inventory(target),
          'cold_return_code':result.returncode,
          'new_calls':[0,0,0], 'production_authorized':False,
          'seconds':round(time.monotonic()-started,3)}
(evidence/'cold-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
raise SystemExit(result.returncode)
