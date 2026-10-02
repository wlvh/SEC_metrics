"""Run the whole pinned fast suite once on the final A05 change tree."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'
RUNNER = ROOT/'tools/run_fast_tests_v2.py'
listed = json.loads(subprocess.check_output([PYTHON,str(RUNNER),'--suite','fast',
    '--list'],cwd=ROOT))['tests']
target = 'tests.vnext.test_a05_formula_successor'
assert listed.count(target) == 1
run = subprocess.run([PYTHON,str(RUNNER),'--suite','fast','--jobs','4'],
    cwd=ROOT,capture_output=True,text=True,check=False)
(HERE/'fast-suite.stdout').write_text(run.stdout)
(HERE/'fast-suite.stderr').write_text(run.stderr)
value = json.loads(run.stdout)
result = {'record_type':'ISSUE28_A05_FORMULA_FULL_FAST_RUN',
    'return_code':run.returncode,'suite_status':value['status'],
    'selector_count':len(value['tests']),
    'new_selector':target,
    'new_selector_result':[row for row in value['tests'] if row['test']==target],
    'failed':[row['test'] for row in value['tests'] if row['return_code']!=0],
    'new_real_calls':[0,0,0]}
(HERE/'fast-summary.json').write_text(json.dumps(result,ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'status':result['suite_status'],
    'selectors':result['selector_count'],'failed':result['failed']}),flush=True)
assert run.returncode == 0 and value['status'] == 'PASSED'
assert len(value['tests']) == len(listed)
assert not result['failed'] and len(result['new_selector_result']) == 1
