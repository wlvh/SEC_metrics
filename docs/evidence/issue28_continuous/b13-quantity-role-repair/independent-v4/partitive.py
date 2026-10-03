import sys,json,hashlib,socket,unittest,copy
from pathlib import Path
from unittest.mock import patch
out=Path('/tmp/sec_metrics_issue28_continuous/b13-role-proof-independent-review/v4');sys.dont_write_bytecode=True
import vnext
vnext.__path__.insert(0,str(out/'overlay/scripts/vnext'))
from vnext import capacity_quantity_roles as roles,capacity_semantic_review as semantic,capacity_text_results as native
from vnext.capacity_run import project_defined_absence
from tests.vnext.test_capacity_quantity_roles import assessment,text_arguments,QUARTER
from tests.vnext.test_capacity_text_results import CapacityTextResultTest
from vnext.r6_semantic_source import _bytes
case=unittest.TestCase();results=[]
def outcome(name,fn):
 try:value=fn();results.append({'name':name,'returned':value})
 except Exception as e:results.append({'name':name,'raised':type(e).__name__,'reason':str(e)})
def accepted(text,kind='AVAILABLE_CAPACITY',timing='CURRENT_REPORT',subject='TARGET_REGISTRANT'):
 _,_,request,response=assessment(text,kind,subject)
 for unit in response['units']:
  for finding in unit['findings']:finding['timing']=timing
 return semantic.validate_response(request=request,raw_response=_bytes(response))['unresolved']
def native_absence(text):
 args=text_arguments(text,None);reviewed=CapacityTextResultTest.reviewed(case,args);result=native.replay_text_result(**reviewed)[0]
 row,ev=project_defined_absence(case={'registered_input':{'assessment':args['assessment']},'selection':{'status':'NOT_AVAILABLE_SEC'},'text_arguments':args},result=result,row={},company={'display_name':'Synthetic fixture','primary_cik':'1463101'})
 return {'result':result,'public_row':row,'evidence_count':len(ev)}
with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')):
 for name,text in [('current',QUARTER),('historical',QUARTER.replace('We continued','In 2024, we continued')),('cause','To mitigate 2024 tariffs, '+QUARTER[0].lower()+QUARTER[1:]),('ambiguous','Following developments in 2024, '+QUARTER[0].lower()+QUARTER[1:])]:
  outcome(name+'-current',lambda text=text:accepted(text))
  if name=='historical':outcome(name+'-correct',lambda:accepted(text,timing='HISTORICAL'))
 mixed='The global automotive industry has installed manufacturing capacity that exceeds demand. Our manufacturing capacity was discontinued in 2024.'
 outcome('mixed-industry-wrong-current',lambda:accepted(mixed,'CAPACITY_QUALITATIVE'))
 outcome('mixed-industry-correct-historical',lambda:accepted(mixed,'CAPACITY_QUALITATIVE','HISTORICAL'))
 unknown='We produced a total of 80 widgets in the first quarter.'
 outcome('unsupported-labelled-production',lambda:accepted(unknown,'ACTUAL_PRODUCTION'))
 outcome('unsupported-labelled-other',lambda:accepted(unknown,'OTHER_CONTEXT'))
 outcome('unsupported-native-absence',lambda:native_absence(unknown))
 for label,text in [('partitive-production','We produced 80 of our widgets in the first quarter.'),('nominal-capacity','Our available production capacity amounted to 150 widgets per month.')]:
  outcome(label+'-other',lambda text=text:accepted(text,'OTHER_CONTEXT'))
  outcome(label+'-native-absence',lambda text=text:native_absence(text))
# All results are independent synthetic probes, not real company acceptance.
report={'patch_sha256':hashlib.sha256(Path('/tmp/sec_metrics_issue28_continuous/b13-role-proof.patch').read_bytes()).hexdigest(),'overlay_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (out/'overlay/scripts/vnext').glob('*.py')},'scope':'INDEPENDENT_SYNTHETIC_ACCEPTOR_AND_NATIVE_PUBLIC_ABSENCE_PROBES','results':results,'new_calls':[0,0,0]}
(out/'partitive.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
