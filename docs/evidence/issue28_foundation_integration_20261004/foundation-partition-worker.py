import subprocess,time,json,os
from pathlib import Path
root=Path('/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics');h=root/'docs/evidence/issue28_foundation_integration_20261004';rows=[]
for suite,jobs in [('fast',4),('source-material',2)]:
 t=time.monotonic();cmd=['/private/tmp/issue28-tokenizers-venv/bin/python','tools/run_foundation_ci.py','--suite',suite,'--jobs',str(jobs)]
 x=subprocess.run(cmd,cwd=root,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=(h/('foundation-partition-'+suite+'.log')).open('w'),stderr=subprocess.STDOUT)
 rows.append({'suite':suite,'jobs':jobs,'returncode':x.returncode,'seconds':time.monotonic()-t,'command':cmd})
 (h/'foundation-partition-run-summary.json').write_text(json.dumps(rows,indent=2)+'\n')
