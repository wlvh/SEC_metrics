"""Run only the new saved-source A05 structural N/A selector at its CI tier."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
PYTHON='/private/tmp/issue28-tokenizers-venv/bin/python'
RUNNER=ROOT/'tools/run_fast_tests_v2.py'
target='tests.vnext.test_a05_formula_material'
names=json.loads(subprocess.check_output([PYTHON,str(RUNNER),'--suite',
    'source-material','--list'],cwd=ROOT))['tests']
assert names.count(target)==1
index=names.index(target)
run=subprocess.run([PYTHON,str(RUNNER),'--suite','source-material',
    '--shard-count',str(len(names)),'--shard-index',str(index),'--jobs','1'],
    cwd=ROOT,capture_output=True,text=True,check=False)
(HERE/'material-selector.stdout').write_text(run.stdout)
(HERE/'material-selector.stderr').write_text(run.stderr)
result=json.loads(run.stdout)
assert run.returncode==0 and result['status']=='PASSED'
row,=result['tests']
assert row['test']==target and row['return_code']==0
body={'record_type':'ISSUE28_A05_NA_MATERIAL_CI_SELECTOR',
    'target':target,'source_selector_count':len(names),
    'index':index,'status':result['status'],
    'duration_seconds':row['duration_seconds'],
    'timeout_seconds':row.get('timeout_seconds',240),
    'tests':'TWO_FULL_NATIVE_MARRIOTT_NA_POSITIVE_AND_NEGATIVE',
    'new_real_calls':[0,0,0]}
(HERE/'material-selector.json').write_text(json.dumps(body,ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'status':body['status'],'seconds':body['duration_seconds'],
    'timeout':body['timeout_seconds'],'selectors_selected':1}))
