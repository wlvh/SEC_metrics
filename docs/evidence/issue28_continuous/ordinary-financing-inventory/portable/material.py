import sys,pathlib,json,hashlib,subprocess
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(root),str(root/'scripts')]
from vnext.b06_financing_inventory import prepare_saved_financing_inventory,POLICY_PATH
from tests.vnext.test_normal_zero_ai_results import original_sources_only
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/financing-inventory-portable');out.mkdir(exist_ok=False);data=out/'data';data.mkdir();expected={}
paths={POLICY_PATH,'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for company in ['pfizer','southwest_airlines','marriott_international']:
 with original_sources_only():p=prepare_saved_financing_inventory(repo_root=root,company_id=company)
 expected[company]=p
 for proof in p['source_proofs']:paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
(out/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2))
for relative in paths:
 p=data/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/relative).read_bytes())
code='''import pathlib,sys,json
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'scripts')]
from vnext.b06_financing_inventory import prepare_saved_financing_inventory,POLICY_PATH
from vnext.batch_workflow import BatchWorkflowError
from tests.vnext.test_normal_zero_ai_results import original_sources_only
expected=json.loads((out/'expected.json').read_text());data=out/'data';assert not (data/'.git').exists()
for company,p in expected.items():
 with original_sources_only():actual=prepare_saved_financing_inventory(repo_root=data,company_id=company)
 assert actual==p
 print('COLD_SAVED_ORIGINAL_REBUILD',company,'PASS')
p=next(p for p in expected['southwest_airlines']['source_proofs'] if p['document_name'].endswith('.xml'))
f=data/p['request_repo_relative_path'];old=f.read_bytes();f.write_bytes(old+b' ')
try:
 with original_sources_only():prepare_saved_financing_inventory(repo_root=data,company_id='southwest_airlines')
 raise AssertionError('Changed original admitted')
except (ValueError,BatchWorkflowError) as e:print('CHANGED_SOURCE_REJECTED',type(e).__name__,str(e)[:120])
finally:f.write_bytes(old)
f=data/POLICY_PATH;old=f.read_bytes();f.write_bytes(old+b' ')
try:
 with original_sources_only():prepare_saved_financing_inventory(repo_root=data,company_id='pfizer')
 raise AssertionError('Changed caller policy admitted')
except ValueError as e:print('CHANGED_POLICY_REJECTED',type(e).__name__,str(e))
finally:f.write_bytes(old)
'''
p=out/'cold.py';p.write_text(code);result=subprocess.run(['/usr/bin/python3',str(p),str(root),str(out)],capture_output=True,text=True)
(out/'cold.log').write_text(result.stdout+result.stderr);print(result.stdout+result.stderr);assert result.returncode==0,result.returncode
(out/'index.json').write_text(json.dumps({'status':'PASS','scenarios':5,'code_sha256':hashlib.sha256((root/'scripts/vnext/b06_financing_inventory.py').read_bytes()).hexdigest(),'policy_sha256':hashlib.sha256((root/POLICY_PATH).read_bytes()).hexdigest(),'calls':{'provider':0,'paid':0,'sec':0},'source_files':{p:hashlib.sha256((data/p).read_bytes()).hexdigest() for p in sorted(paths)}},indent=2))
