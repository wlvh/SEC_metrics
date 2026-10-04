import subprocess,os,json,time,shutil
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics');CONTROL=Path('/private/tmp/issue28-foundation-main-control-af1984ad');HERE=ROOT/'docs/evidence/issue28_foundation_integration_20261004'
selectors=['tests.vnext.test_issue28_requirement_transition.Issue28RequirementTransitionTest.test_baseline_binds_exact_merged_main_and_parent_tree', 'tests.vnext.test_issue28_requirement_transition.Issue28RequirementTransitionTest.test_legacy_publication_keeps_hash_only_identity']
python='/private/tmp/issue28-tokenizers-venv/bin/python'
rows=[]
def check(label,folder,tests):
 t=time.monotonic();log=HERE/(label+'.log')
 x=subprocess.run([python,'-m','unittest','-v',*tests],cwd=folder,env={**os.environ,'PYTHONPATH':'scripts:tools','PYTHONDONTWRITEBYTECODE':'1'},stdout=log.open('w'),stderr=subprocess.STDOUT)
 rows.append({'label':label,'root':str(folder),'selectors':tests,'seconds':time.monotonic()-t,'returncode':x.returncode})
 (HERE/'main-historical-comparison-summary.json').write_text(json.dumps(rows,indent=2)+'\n')
check('main-original-two-broad-regressions',CONTROL,selectors)
# Exactly the same corrected test bytes on both code roots. No production
# source, snapshot or active pointer is changed in the main control.
shutil.copyfile(ROOT/'tests/vnext/test_issue28_requirement_transition.py',CONTROL/'tests/vnext/test_issue28_requirement_transition.py')
check('main-fixed-two-broad-regressions',CONTROL,selectors)
check('candidate-fixed-two-broad-regressions',ROOT,selectors)
check('candidate-historical-transition-full',ROOT,['tests.vnext.test_issue28_requirement_transition'])
