import subprocess,os,json,time
from pathlib import Path
t=time.monotonic()
x=subprocess.run(['/private/tmp/issue28-tokenizers-venv/bin/python', '-m', 'unittest', '-v', 'tests.vnext.test_issue28_requirement_transition'],cwd='/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics',env={**os.environ,"PYTHONPATH":"scripts:tools","PYTHONDONTWRITEBYTECODE":"1"},stdout=open('/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics/docs/evidence/issue28_foundation_integration_20261004/historical-transition-final.log',"w"),stderr=subprocess.STDOUT)
Path('/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics/docs/evidence/issue28_foundation_integration_20261004/historical-transition-final-summary.json').write_text(json.dumps({"returncode":x.returncode,"seconds":time.monotonic()-t},indent=2)+"\n")
