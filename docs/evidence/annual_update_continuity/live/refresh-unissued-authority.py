import json,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');w=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');sys.path[:0]=[str(r),str(r/'scripts')]
from vnext import annual_continuity as c,annual_runtime as runtime
from vnext.annual_continuity_sources import frozen_foundation_receipts
assert not (w/'real-stage-approval.json').exists()
budget=w/'live/budget';registration=(budget/'registration.json').read_bytes();assert set(p.name for p in budget.iterdir())=={'registration.json'}
assert not (w/'live/stage').exists()
data=w/'live/data';requirement=c._requirement();frozen=frozen_foundation_receipts();changed=[]
for name in runtime._authority_files(requirement):
 p=data/name;raw=frozen[name]['bytes'] if name in frozen else (r/name).read_bytes()
 if p.read_bytes()!=raw:
  old=p.read_bytes();backup=w/'live-logs/pre-grant-output-fix-authority'/name;backup.parent.mkdir(parents=True,exist_ok=True)
  with backup.open('xb') as out:out.write(old)
  p.write_bytes(raw);changed.append({'path':name,'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(raw).hexdigest(),'preserved_before':str(backup)})
runtime.verify_data_root(data,requirement);assert (budget/'registration.json').read_bytes()==registration
result={'record_type':'UNISSUED_STAGE_AUTHORITY_REBIND_AFTER_CLI_OUTPUT_FAILURE','code':c.code_identity(),'requirement_closure_hash':requirement['requirement_closure_hash'],'changes':changed,'budget_registration_bytes_unchanged':True,'registration_file_sha256':hashlib.sha256(registration).hexdigest(),'business_calls':[0,0,0],'real_approval_issued':False,'time':datetime.now(timezone.utc).isoformat()}
with (w/'live-logs/refresh-unissued-authority.json').open('x') as out:json.dump(result,out,indent=2)
print(json.dumps(result))
