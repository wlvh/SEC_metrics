import subprocess,os,time,json
from pathlib import Path
t=time.monotonic()
x=subprocess.run(['/private/tmp/issue28-tokenizers-venv/bin/python', 'tools/run_fast_tests.py', '--jobs', '4'],cwd='/private/tmp/issue28-main-fast-final-9d',env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":"scripts:tools"},stdout=open('/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics/docs/evidence/issue28_foundation_integration_20261004/main-final-fast.log',"w"),stderr=subprocess.STDOUT)
Path('/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics/docs/evidence/issue28_foundation_integration_20261004/main-final-fast-summary.json').write_text(json.dumps({"head":"9d1ece070e70828ec99bfe6204a2e440f84b4730","root":'/private/tmp/issue28-main-fast-final-9d',"returncode":x.returncode,"seconds":time.monotonic()-t,"command":['/private/tmp/issue28-tokenizers-venv/bin/python', 'tools/run_fast_tests.py', '--jobs', '4']},indent=2)+"\n")
