import sys,json,copy
from pathlib import Path
sys.dont_write_bytecode=True
import vnext
vnext.__path__.insert(0,'/tmp/sec_metrics_issue28_continuous/b13-role-proof-independent-review/v4/overlay/scripts/vnext')
from tests.vnext.test_capacity_quantity_roles import assessment,QUARTER
from vnext.capacity_semantic_review import validate_response
from vnext.r6_semantic_source import _bytes
text=QUARTER.replace('We continued','In 2024, we continued')+' '+QUARTER.replace('We continued','In 2025, we continued')
_,_,request,response=assessment(text,'AVAILABLE_CAPACITY');results=[]
for label,r in [('current_only',response),('both_periods',copy.deepcopy(response))]:
 if label=='both_periods':
  for u in r['units']:
   for f in list(u['findings']):u['findings'].append({**f,'timing':'HISTORICAL'})
 try:checked=validate_response(request=request,raw_response=_bytes(r));results.append({'name':label,'accepted':True,'unresolved':checked['unresolved']})
 except Exception as e:results.append({'name':label,'accepted':False,'reason':str(e)})
Path('/tmp/sec_metrics_issue28_continuous/b13-role-proof-independent-review/v4/mixed-period.json').write_text(json.dumps({'text':text,'results':results,'new_calls':[0,0,0]},indent=2)+'\n')
print(results)
