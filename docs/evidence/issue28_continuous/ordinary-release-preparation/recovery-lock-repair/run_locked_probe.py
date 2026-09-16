from pathlib import Path
import subprocess,sys,json,os
p=Path(__file__).resolve().parent;rows=[]
for mode in ['old','new','foreign']:
 try:
  done=subprocess.run([sys.executable,str(p/'locked_guard_probe.py'),mode],capture_output=True,text=True,timeout=4,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 except subprocess.TimeoutExpired as e:
  assert mode=='old';rows.append({'mode':mode,'status':'REAL_EXCLUSIVE_LOCK_THEN_NESTED_SHARED_LOCK_TIMED_OUT','timeout_seconds':4})
 else:
  assert done.returncode==0,(mode,done.stdout,done.stderr);rows.append(json.loads(done.stdout))
(p/'locked-probe-result.json').write_text(json.dumps({'scope':'Actual fcntl lock; edge and already verified view fixture isolate guard; full native transaction remains separate','results':rows,'new_calls':[0,0,0]},indent=2)+'\n');print(json.dumps(rows))
