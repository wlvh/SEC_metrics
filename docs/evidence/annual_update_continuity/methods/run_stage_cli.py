"""Credential-free operator logging of the same bounded stage CLI."""
import os,sys,subprocess
from pathlib import Path
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');w=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity')
# No stored credential, provider probe or alternative executor.
env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ('API_KEY','SECRET','PASSWORD'))}
env.update(PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',TMPDIR=str(w/'live/tmp'),PYTHONPATH=str(r)+':'+str(r/'scripts'))
args=[sys.executable,str(w/'run_logged.py'),sys.argv[1],'sandbox-exec','-f',str(w/'live-isolated.sb'),sys.executable,str(r/'tools/vnext_annual_continuity.py'),*sys.argv[2:]]
raise SystemExit(subprocess.run(args,cwd=r,env=env).returncode)
