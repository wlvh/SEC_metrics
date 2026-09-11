import hashlib,json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
root=Path('/Users/lyuhongwang/Developer/SEC_metrics')
record=Path(sys.argv[1]);argv=sys.argv[2:];log=record.with_suffix('.log')
assert not record.exists() and not log.exists()
start=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
with log.open('xb') as out:
 p=subprocess.run(argv,cwd=root,stdout=out,stderr=subprocess.STDOUT)
result={'record_type':'ACTUAL_COMMAND_EXECUTION_BINDING','command':argv,'cwd':str(root),'head':head,
'head_after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
'started_at_utc':start,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-clock,
'exit_code':p.returncode,'log':str(log),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'log_size':log.stat().st_size}
with record.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
print(json.dumps(result));sys.exit(p.returncode)
