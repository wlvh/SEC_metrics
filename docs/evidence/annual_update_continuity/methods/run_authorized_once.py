"""Operator wrapper: ephemeral credential, existing CLI, restricted write roots.

This script does not approve a stage or retry a request. The repository CLI
must independently verify the real Owner comment, budget, code and input.
"""
import getpass
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics')
WORK=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity')
if len(sys.argv)!=4:
    raise SystemExit('usage: wrapper APPROVAL_URL NEW_COMMAND_RECORD NEW_RESULT_FILE')
url,record,output=sys.argv[1:]
for value in (record,output):
    path=Path(value).resolve()
    if WORK/'live-logs' not in path.parents or path.exists():raise SystemExit('New live-log paths required')
key=getpass.getpass('Ephemeral provider credential: ')
if not key.strip():raise SystemExit('Credential absent; no invocation')
env={**os.environ,'DEEPSEEK_API_KEY':key,'PYTHONDONTWRITEBYTECODE':'1','GIT_OPTIONAL_LOCKS':'0',
     'TMPDIR':str(WORK/'live/tmp'),'PYTHONPATH':str(ROOT)+':'+str(ROOT/'scripts')}
argv=[sys.executable,str(WORK/'run_logged.py'),record,'sandbox-exec','-f',str(WORK/'live-isolated.sb'),
      sys.executable,str(ROOT/'tools/vnext_annual_continuity.py'),'run-once','--approval-url',url,'--output-json',output]
result=subprocess.run(argv,cwd=ROOT,env=env)
env.pop('DEEPSEEK_API_KEY',None);key=''
raise SystemExit(result.returncode)
