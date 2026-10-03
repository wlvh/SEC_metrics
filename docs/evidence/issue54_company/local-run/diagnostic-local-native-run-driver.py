import json,pathlib,sys,time
from unittest.mock import patch
sys.path[:0]=['/workspace/work/sec-company-compute','/workspace/work/sec-company-compute/scripts']
from vnext import company_local as local
original=local._invoke
phase=sys.argv[1];work=pathlib.Path('/workspace/work/local-native-run');output=pathlib.Path('/workspace/work/local-native-run-output');fixture=pathlib.Path('/workspace/work/sec-company-compute')
def invoke(program,args,**kw):
 if args[0]!='acquire':return original(program,args,**kw)
 import subprocess
 start=time.monotonic()
 child=subprocess.run([sys.executable,'-B','/workspace/work/local-fixture-acquire.py',str(program),str(work),str(fixture)],capture_output=True,text=True)
 report=kw['report_file'];report.parent.mkdir(parents=True,exist_ok=True)
 report.with_suffix('.stdout.log').write_text(child.stdout);report.with_suffix('.stderr.log').write_text(child.stderr)
 result=json.loads(child.stdout,parse_float=str) if child.returncode==0 else {'status':'STAGE_FAILED','reason':child.stderr}
 return {'returncode':child.returncode,'result':result,'elapsed_seconds':format(time.monotonic()-start,'.6f'),'recorded_http_only':True}
with patch.object(local,'_invoke',side_effect=invoke):
 result=local.run_local(company_id='marriott_international',work_dir=work,output_dir=output,metric_ids=['B01','D01'] if phase=='first' else ['B01'])
print(json.dumps(result,ensure_ascii=False,indent=2))
