import json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');N=Path(__file__).parent
ready=json.loads((N/'independent-execution-readiness.json').read_text())
assert ready['conclusion']=='NO_BLOCKING_FINDINGS' and ready['execution_ready'] is True
command=json.loads((N/'offline-02-command.json').read_text());assert command['exit_code']==0
assert command['head']==command['head_after']==ready['reviewed_head']
audit=json.loads((N.parent/'historical-material-audit.json').read_text())
argv=[sys.executable,str(N/'run_logged.py'),str(N/'live-logs/stage-proposal-command.json'),
 'sandbox-exec','-f',str(N/'live-isolated.sb'),sys.executable,str(ROOT/'tools/vnext_annual_continuity.py'),
 'stage-proposal','--stage-root',str(N/'live/stage'),'--data-root',str(N/'live/data'),
 '--budget-root',str(N/'live/budget'),'--review-file',str(N/'independent-execution-readiness.json'),
 '--seed-b01',audit['s0_feasibility']['B01']['run_directory'],
 '--seed-b10',audit['s0_feasibility']['B10']['run_directory'],
 '--visibility-file',str(N/'live/visibility.json'),
 '--expires-at-utc',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
 '--historical-period-start','2023-01-01','--historical-period-end','2025-12-31',
 '--previous-approval-url','https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5616160149',
 '--delegation-source','codex-task:01a081bb-9220-7de3-a311-b481906b3146#2026-09-10-PR41-two-run-continuation',
 '--update-period-ends','2024-12-31','2025-12-31','--output-json',str(N/'live-logs/stage-proposal.json')]
env={k:v for k,v in os.environ.items() if not k.endswith('_API_KEY')};env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(N/'live/tmp'),PYTHONPATH=str(ROOT/'scripts'))
raise SystemExit(subprocess.run(argv,cwd=ROOT,env=env).returncode)
