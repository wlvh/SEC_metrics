"""Validate an exact Run copy; source-contract repair is separate bound evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ATTEMPT = Path('/private/tmp/issue28-b03-marriott-namespace-repair-20261001/normal-update/marriott_international/metrics/B03/attempts/aa11c78b0cd64e1fb7b88bd65393b780')
DESTINATION = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/b03-marriott-390-receiving-20261004/run-copy')


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


child = '''import json,sys,hashlib
from pathlib import Path
data=Path(sys.argv[1]);run=Path(sys.argv[2]);wanted=sys.argv[3]
sys.dont_write_bytecode=True;sys.path[:0]=[str(data),str(data/'scripts')]
def guard(event,args):
 if event=='open' and isinstance(args[0],(str,bytes,Path)):
  p=Path(args[0]).absolute();original=Path('/Users/lyuhongwang/Developer/SEC_metrics')
  if p==original or original in p.parents:raise RuntimeError('ORIGINAL_CHECKOUT_READ_FORBIDDEN')
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:raise RuntimeError('NO_NETWORK_OR_PROCESS')
sys.addaudithook(guard)
from vnext import run_store
from vnext.ordinary_projection import render_ordinary_run
assert Path(run_store.__file__).resolve().is_relative_to(data)
manifest=json.loads((run/'manifest.json').read_text());assert manifest['status']=='OPEN'
records=[json.loads(line) for line in (run/'records.jsonl').read_text().splitlines()]
result,=[r for r in records if r['record_type']=='METRIC_RESULT' and r['metric_id']=='B03']
assert result['result_id']==wanted and result['publication']=='PUBLISHED'
receipt=run_store.validate_run(run_dir=run,repo_root=data);assert receipt['status']=='PASSED'
rendered=render_ordinary_run(data_root=data,run_dir=run)
assert json.loads((run/'manifest.json').read_text())==manifest
print(json.dumps({'status':'PASSED_MECHANICAL_COPY_ONLY','receipt':receipt,'native_result':result,
 'run_id':manifest['run_id'],'requirement_id':manifest['requirement_id'],
 'requirement_closure_hash':manifest['requirement_closure_hash'],'runtime_module':str(run_store.__file__),
 'public_row_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in rendered['files'].items()},
 'current_uri_repair_admission_credit_from_this_replay':False,'calls':[0,0,0]}))
'''


def main():
    result = {'original_attempt': str(ATTEMPT), 'installed_code_data_root': str(ATTEMPT/'data'),
              'run_copy': str(DESTINATION), 'new_calls': [0, 0, 0], 'formal_adoption': False}
    before = inventory(ATTEMPT)
    original = ATTEMPT/'runs/B03'
    assert json.loads((original/'validation.json').read_text())['status'] == 'NOT_RUN'
    assert not DESTINATION.exists()
    shutil.copytree(original, DESTINATION)
    assert inventory(original) == inventory(DESTINATION)
    start = time.monotonic()
    try:
        with (HERE/'mechanical-copy.log').open('w') as log:
            done = subprocess.run(['/private/tmp/issue28-tokenizers-venv/bin/python', '-B', '-c', child,
                str(ATTEMPT/'data'), str(DESTINATION),
                'sha256:3043aa63cbf7616f9866fb93b8f69200a2246a33dfec8f1d09502a34af39a72a'],
                cwd=DESTINATION.parent, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                stdout=log, stderr=subprocess.STDOUT)
        result.update(return_code=done.returncode, seconds=round(time.monotonic()-start, 3),
                      original_files_unchanged=inventory(ATTEMPT) == before)
        assert result['original_files_unchanged'] and done.returncode == 0
        result['mechanical_result'] = json.loads((HERE/'mechanical-copy.log').read_text())
        changed = sorted(k for k, v in inventory(DESTINATION).items() if inventory(original).get(k) != v)
        assert changed == ['validation.json']
        result.update(status='PASS_ONE_EXACT_MARRIOTT_B03_RUN_COPY', changed_copy_files=changed)
    except Exception as error:
        result.update(status='FAILED_COPY_VALIDATION', error=str(error))
        raise
    finally:
        (HERE/'mechanical-summary.json').write_text(json.dumps(result, indent=2)+'\n')
        (HERE/'done.json').write_text(json.dumps({'status': result['status'], 'completed': True})+'\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'mechanical_result'}))


if __name__ == '__main__':
    main()
