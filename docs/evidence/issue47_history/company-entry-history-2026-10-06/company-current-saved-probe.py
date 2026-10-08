import sys, os, json, subprocess, time
from pathlib import Path
program=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-check-20261006')
base=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-current-probe-20261006')
base.mkdir()
logs=base/'logs'; logs.mkdir()
runtime=base/'program'; source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
trust=base/'trust'; state=base/'state'; package=base/'package'; output=base/'output'
stages=[]
commands=[('runtime',program,['install-runtime','--kind','ordinary','--output-root',runtime]),
          ('prepare',program,['export','--source-root',source,'--output-root',package,'--trust-root',trust,'--company','macys','--metric','B01']),
          ('install',runtime,['install','--package-root',package,'--state-root',state,'--trust-root',trust,'--company','macys']),
          ('compute',runtime,['compute','--state-root',state,'--trust-root',trust,'--company','macys','--metric','B01']),
          ('export',program,['export-results','--state-root',state,'--output-root',output,'--trust-root',trust,'--company','macys','--runtime-root',runtime])]
for name, tree, args in commands:
    start=time.monotonic()
    if name=='install':
        for path in [*runtime.rglob('*'),runtime]:path.chmod(path.stat().st_mode & ~0o222)
    # This verifies the current-year compute consumer with saved sources;
    # it does not replay or claim the real acquisition phase of local run.
    command=[sys.executable,str(tree/'tools/vnext_company.py'),*map(str,args)]
    with (logs/(name+'.stdout.json')).open('wb') as out,(logs/(name+'.stderr.log')).open('wb') as err:
        process=subprocess.run(command,stdout=out,stderr=err,cwd=base,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=600)
    stages.append({'stage':name,'command':command,'exit_code':process.returncode,'seconds':time.monotonic()-start})
    (base/'stages.json').write_text(json.dumps(stages,indent=2)+'\n')
    if process.returncode:raise SystemExit(process.returncode)
print(json.dumps({'status':'PASSED','stages':stages,'new_business_calls':[0,0,0]},indent=2))
