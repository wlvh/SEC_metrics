"""Issue one C02 mechanical receipt; reuse the precise limited content read."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ORIGINAL = Path('/private/tmp/issue28-c02-normal-update-enphase-peer60aa-20261001/metrics/C02/attempts/df1f346bbddd4b4f97974e7ab7e09e48')
DATA = ORIGINAL / 'data'
RUN = ORIGINAL / 'runs/C02'
COPY = Path('/private/tmp/issue28-c02-enphase-validation-copy-20261003/run')
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'
RESULT = 'sha256:8fb7d6e3ee0a8eeefd58b9187c701b11a3b1bb3aa4954dc339da4b704044f234'


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


child = '''import json,sys
from pathlib import Path
data=Path(sys.argv[1]);run=Path(sys.argv[2]);wanted=sys.argv[3]
sys.dont_write_bytecode=True;sys.path[:0]=[str(data),str(data/'scripts')]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:raise RuntimeError('NO_NETWORK_OR_PROCESS')
sys.addaudithook(guard)
from vnext import run_store
assert Path(run_store.__file__).resolve().is_relative_to(data)
manifest=json.loads((run/'manifest.json').read_text())
assert manifest['status']=='OPEN' and manifest['company_id']=='enphase_energy'
records=[json.loads(line) for line in (run/'records.jsonl').read_text().splitlines()]
result=next(r for r in records if r['record_type']=='METRIC_RESULT' and r['metric_id']=='C02')
assert result['result_id']==wanted
receipt=run_store.validate_run(run_dir=run,repo_root=data)
assert receipt['status']=='PASSED'
assert json.loads((run/'manifest.json').read_text())==manifest
print(json.dumps({'status':'PASSED_MECHANICAL_COPY_ONLY','receipt':receipt,
 'run_id':manifest['run_id'],'requirement_id':manifest['requirement_id'],
 'requirement_closure_hash':manifest['requirement_closure_hash'],
 'runtime_module':str(run_store.__file__),'result_id':wanted,
 'compiled_spec_closure':result['spec_closure_hash'],'frozen':False,
 'content_review_scope_not_expanded':True,'new_calls':[0,0,0]}))
'''
summary = {'tested_checkout_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
           'original_attempt': str(ORIGINAL), 'installed_code_data_root': str(DATA),
           'run_copy': str(COPY), 'new_calls': [0, 0, 0],
           'new_content_or_current_390_credit': False, 'production_authorized': False}
before = inventory(ORIGINAL)
try:
    assert json.loads((RUN / 'validation.json').read_text())['status'] == 'NOT_RUN'
    COPY.parent.mkdir(exist_ok=False)
    shutil.copytree(RUN, COPY)
    assert inventory(COPY) == inventory(RUN)
    start = time.monotonic()
    with (HERE / 'mechanical.log').open('w') as log:
        done = subprocess.run([PYTHON, '-B', '-c', child, str(DATA), str(COPY), RESULT],
            cwd=COPY.parent, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            stdout=log, stderr=subprocess.STDOUT)
    summary.update(return_code=done.returncode, seconds=round(time.monotonic() - start, 3))
    assert done.returncode == 0, 'READ_RAW_MECHANICAL_LOG'
    summary['mechanical_result'] = json.loads((HERE / 'mechanical.log').read_text())
    changed = {k for k, v in inventory(COPY).items() if inventory(RUN).get(k) != v}
    assert changed == {'validation.json'}
    summary['changed_copy_files'] = sorted(changed)
    summary['original_file_sha256'] = before
    summary['status'] = 'PASS_EXACT_ENPHASE_C02_COPY_MECHANICAL_RECEIPT'
except Exception as error:
    summary.update(status='FAILED_C02_MECHANICAL_COPY', error=str(error))
    raise
finally:
    summary['original_files_unchanged'] = inventory(ORIGINAL) == before
    assert summary['original_files_unchanged']
    (HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'done.json').write_text(json.dumps({'status': summary['status']}) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'original_file_sha256'}), flush=True)
