import json,os,shutil,sys,time
from pathlib import Path
w=Path('/workspace/work'); runtime=w/'company-runtime-release'; package=w/'product-b-source-v2';out=w/'company-admission-negatives';out.mkdir()
trust=out/'external-readonly-trust';shutil.copytree(w/'company-trust',trust)
for p in [trust,*trust.rglob('*')]:p.chmod(p.stat().st_mode&~0o222)
sys.path[:0]=[str(runtime/'scripts'),str(runtime)];os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(trust)
from vnext.company_handoff import check_package
from vnext.canonical import strict_json_file
cp=strict_json_file(path=package/'config/ordinary_source_checkpoint.json')
rows=cp['original_checkpoint']['captures'];proof=next(c['receipt']['proof'] for c in rows if c['receipt']['proof'] is not None and c['receipt']['company_id']=='jpmorgan_chase')
checks=[('missing_body',proof['request_repo_relative_path'],'delete','jpmorgan_chase','Missing'),('missing_headers',proof['request_headers_repo_relative_path'],'delete','jpmorgan_chase','Missing'),('ledger_manifest_mismatch','evidence/requests_log_manifest.json','append','jpmorgan_chase',''),('wrong_company',None,None,'salesforce','COMPANY_SOURCE_WRONG_COMPANY'),('changed_rule',next(p for p in cp['rules'] if p.endswith('.json')),'append','jpmorgan_chase','COMPANY_HANDOFF_RULE_COPY_CHANGED')]
results=[]
for name,path,mutation,company,expected in checks:
 case=out/name;shutil.copytree(package,case)
 if mutation=='delete':(case/path).unlink()
 elif mutation=='append':
  with (case/path).open('ab') as f:f.write(b'\nTAMPER\n')
 start=time.monotonic()
 try:check_package(package_root=case,company_id=company)
 except Exception as e:
  reason=str(e)
  if expected and expected.lower() not in reason.lower():raise AssertionError((name,reason))
  results.append({'case':name,'path':path,'status':'REJECTED','error_type':type(e).__name__,'reason':reason,'seconds':time.monotonic()-start})
 else:raise AssertionError('Unexpected acceptance:'+name)
report={'status':'PASSED','uid':os.getuid(),'trust_readonly':True,'checkpoint_id':cp['checkpoint_id'],'negative_probes':results,'new_business_calls':[0,0,0]}
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
