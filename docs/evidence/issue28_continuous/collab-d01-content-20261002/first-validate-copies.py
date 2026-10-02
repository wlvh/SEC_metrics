"""Issue a mechanical receipt on exact copies; preserve the old OPEN Runs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = Path('/private/tmp/issue28-d01-validation-copies-20261003')
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'
CASES = [
    ('paramount_skydance', Path('/private/tmp/issue28-d01-emphasis-paramount-20261002-final/metrics/D01/attempts/2bf85d7f0f6a4cf9b43447c3e018408a'),
     'sha256:6795449bafa12651099b226e569ad3b2882f72a89cd317adb559c8096058afdd'),
    ('marriott_international', Path('/private/tmp/issue28-d01-emphasis-marriott-20261002-final/metrics/D01/attempts/5fa26e4007ef4ce1aee75cd5869d836b'),
     'sha256:99c76e50d0fb19cd6116a80350a6f1ca38924b5731e812695484d28381b348f8'),
]


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
manifest=json.loads((run/'run_manifest.json').read_text())
assert manifest['status']=='OPEN'
records=[json.loads(line) for line in (run/'records.jsonl').read_text().splitlines()]
assert wanted in [r.get('result_id') for r in records if r['record_type']=='METRIC_RESULT']
receipt=run_store.validate_run(run_dir=run,repo_root=data)
assert receipt['status']=='PASSED'
assert json.loads((run/'run_manifest.json').read_text())==manifest
print(json.dumps({'status':'PASSED_MECHANICAL_COPY_ONLY','receipt':receipt,'run_id':manifest['run_id'],
 'requirement_id':manifest['requirement_id'],'requirement_closure_hash':manifest['requirement_closure_hash'],
 'runtime_module':str(run_store.__file__),'result_id':wanted,'frozen':False,'new_calls':[0,0,0]}))
'''
summary = {'code_head': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
           'results': [], 'new_calls': [0,0,0], 'production_authorized': False}
BASE.mkdir()
try:
    for company, attempt, expected in CASES:
        data=attempt/'data';original=attempt/'runs/D01';copied=BASE/company/'run'
        before=inventory(attempt)
        assert json.loads((original/'validation.json').read_text())['status']=='NOT_RUN'
        shutil.copytree(original,copied)
        assert inventory(original)==inventory(copied)
        started=time.monotonic()
        with (HERE/('mechanical-'+company+'.log')).open('w') as log:
            done=subprocess.run([PYTHON,'-B','-c',child,str(data),str(copied),expected],
                cwd=BASE,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
        row={'company_id':company,'original_attempt':str(attempt),'installed_code_data_root':str(data),
             'run_copy':str(copied),'return_code':done.returncode,'seconds':round(time.monotonic()-started,3),
             'original_files_unchanged':inventory(attempt)==before}
        summary['results'].append(row)
        assert row['original_files_unchanged'] and done.returncode==0, 'READ_RAW_FAILURE_LOG'
        row['mechanical_result']=json.loads((HERE/('mechanical-'+company+'.log')).read_text())
        changed={k for k,v in inventory(copied).items() if inventory(original).get(k)!=v}
        assert changed=={'validation.json'}
        row['changed_copy_files']=sorted(changed)
    summary['status']='PASS_TWO_EXACT_RUN_COPY_MECHANICAL_RECEIPTS'
except Exception as error:
    summary.update(status='FAILED_COPY_VALIDATION',error=str(error))
    raise
finally:
    (HERE/'mechanical-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (HERE/'mechanical-done.json').write_text(json.dumps({'status':summary['status']})+'\n')
    print(json.dumps({'status':summary['status'],'results':summary['results']},ensure_ascii=False),flush=True)
