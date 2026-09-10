import sys,json
from pathlib import Path
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');w=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');sys.path[:0]=[str(r),str(r/'scripts')]
from vnext import annual_continuity as c
from vnext.canonical import canonical_json_bytes
try:c.verify_stage(approval_url='https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5616160149',execution=True)
except ValueError as e:
 assert str(e)=='CONTINUITY_STAGE_CLOSED';result={'status':'PASS_CLOSED_STAGE_REJECTED','native_error':str(e),'new_provider_paid_sec_calls':[0,0,0]}
else:raise AssertionError('Closed stage accepted')
with (w/'live-logs/verify-closed-stage.json').open('xb') as out:out.write(canonical_json_bytes(value=result))
print(json.dumps(result))
