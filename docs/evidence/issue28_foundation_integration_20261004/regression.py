"""Integration regressions, isolated tests only; no live acquisition."""
import json
import os
from pathlib import Path
import subprocess
import time
HERE=Path(__file__).parent
selectors=['tests.vnext.test_replay','tests.vnext.test_publication','tests.vnext.test_source_records','tests.vnext.test_requirement_baseline','tests.vnext.test_issue28_requirement_transition','tests.vnext.test_normal_run_authority']
s=time.monotonic();p=subprocess.run(['/private/tmp/issue28-tokenizers-venv/bin/python','-m','unittest',*selectors,'-q'],cwd=Path.cwd(),env={**os.environ,'PYTHONPATH':'scripts:tools','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True)
(HERE/'regression.log').write_text(p.stdout+p.stderr);record={'returncode':p.returncode,'seconds':round(time.monotonic()-s,3),'selectors':selectors,'tree':'main af1984 + fixed0bc runtime/snapshot materialized scope, before candidate commit','business_calls':[0,0,0]};(HERE/'regression-summary.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(p.returncode)
