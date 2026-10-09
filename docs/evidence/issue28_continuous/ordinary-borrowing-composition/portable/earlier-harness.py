import sys,pathlib,json,hashlib,subprocess
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(root),str(root/'scripts')]
from vnext.b06_combined_borrowings import prepare_saved_combined_borrowings,POLICY_PATH
from tests.vnext.test_normal_zero_ai_results import original_sources_only
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/combined-borrowing-portable');out.mkdir(exist_ok=False);data=out/'data';data.mkdir()
with original_sources_only():p=prepare_saved_combined_borrowings(repo_root=root,company_id='pfizer')
(out/'expected.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
paths={POLICY_PATH,'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for proof in p['source_proofs']:
 paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
for relative in paths:
 q=data/relative;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes((root/relative).read_bytes())
code='''import pathlib,sys,json
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'scripts')]
from vnext.b06_combined_borrowings import prepare_saved_combined_borrowings,POLICY_PATH
from vnext.batch_workflow import BatchWorkflowError
from tests.vnext.test_normal_zero_ai_results import original_sources_only
expected=json.loads((out/'expected.json').read_text());data=out/'data'
assert not (data/'.git').exists()
with original_sources_only():actual=prepare_saved_combined_borrowings(repo_root=data,company_id='pfizer')
assert actual==expected
print('COLD_NO_GIT_ORIGINAL_SOURCE_REBUILD PASS')
cf=next(p for p in expected['source_proofs'] if '/companyfacts/' in p['source_url'])
p=data/cf['request_repo_relative_path'];old=p.read_bytes();p.write_bytes(old+b' ')
try:
 with original_sources_only():prepare_saved_combined_borrowings(repo_root=data,company_id='pfizer')
 raise AssertionError('Tampered Company Facts admitted')
except (ValueError,BatchWorkflowError) as e:print('TAMPERED_SOURCE_REJECTED',type(e).__name__,str(e)[:160])
finally:p.write_bytes(old)
xml=next(p for p in expected['source_proofs'] if p['document_name'].endswith('.xml'))
p=data/xml['request_repo_relative_path'];old=p.read_bytes();p.unlink()
try:
 with original_sources_only():prepare_saved_combined_borrowings(repo_root=data,company_id='pfizer')
 raise AssertionError('Missing original instance admitted')
except (ValueError,BatchWorkflowError,FileNotFoundError) as e:print('MISSING_INSTANCE_REJECTED',type(e).__name__,str(e)[:160])
finally:p.write_bytes(old)
p=data/POLICY_PATH;old=p.read_bytes();p.write_bytes(old+b' ')
try:
 with original_sources_only():prepare_saved_combined_borrowings(repo_root=data,company_id='pfizer')
 raise AssertionError('Caller policy admitted')
except ValueError as e:print('CHANGED_POLICY_REJECTED',type(e).__name__,str(e))
finally:p.write_bytes(old)
'''
s=out/'cold.py';s.write_text(code);r=subprocess.run(['/usr/bin/python3',str(s),str(root),str(out)],capture_output=True,text=True)
(out/'cold.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);assert r.returncode==0,r.returncode
index={'status':'PASS','actual_scenarios':4,'module_sha256':hashlib.sha256((root/'scripts/vnext/b06_combined_borrowings.py').read_bytes()).hexdigest(),'calls':{'provider':0,'paid':0,'sec':0},'source_files':{x:hashlib.sha256((data/x).read_bytes()).hexdigest() for x in sorted(paths)}}
(out/'index.json').write_text(json.dumps(index,indent=2))
