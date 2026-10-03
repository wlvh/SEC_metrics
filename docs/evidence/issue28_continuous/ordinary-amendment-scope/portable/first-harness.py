import sys,pathlib,json,subprocess,hashlib
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(root),str(root/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.annual_amendment_scope import prepare_saved_amendment_input,POLICY_PATH
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/amendment-portable-material');out.mkdir(exist_ok=False)
data=out/'data';data.mkdir()
with original_sources_only(): packet=prepare_saved_amendment_input(repo_root=root,company_id='southwest_airlines',input_class='ORIGINAL_STATEMENT_VALUES')
paths={POLICY_PATH,'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for proof in packet['source_proofs']:
 paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
for relative in paths:
 p=data/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/relative).read_bytes())
(out/'expected.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2))
code='''import sys,pathlib,json
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.annual_amendment_scope import prepare_saved_amendment_input,POLICY_PATH
expected=json.loads((out/'expected.json').read_text());data=out/'data'
assert not (data/'.git').exists()
with original_sources_only(): actual=prepare_saved_amendment_input(repo_root=data,company_id='southwest_airlines',input_class='ORIGINAL_STATEMENT_VALUES')
assert actual==expected
print('COLD_NO_GIT_SAVED_SOURCE_REPLAY PASS')
amendment=actual['scopes'][0]['amendment'];proof=next(p for p in actual['source_proofs'] if p['content_sha256']==amendment['raw_sha256'])
p=data/proof['request_repo_relative_path'];original=p.read_bytes()
p.unlink()
try:
 with original_sources_only(): prepare_saved_amendment_input(repo_root=data,company_id='southwest_airlines',input_class='ORIGINAL_STATEMENT_VALUES')
 raise AssertionError('Missing amendment body accepted')
except (ValueError,FileNotFoundError) as e:print('MISSING_AMENDMENT_REJECTED',type(e).__name__,str(e)[:150])
finally:p.write_bytes(original)
p.write_bytes(original+b' ')
try:
 with original_sources_only(): prepare_saved_amendment_input(repo_root=data,company_id='southwest_airlines',input_class='ORIGINAL_STATEMENT_VALUES')
 raise AssertionError('Changed amendment body accepted')
except ValueError as e:print('CHANGED_AMENDMENT_REJECTED',type(e).__name__,str(e)[:150])
finally:p.write_bytes(original)
p=data/POLICY_PATH;original=p.read_bytes();p.write_bytes(original+b' ')
try:
 with original_sources_only(): prepare_saved_amendment_input(repo_root=data,company_id='southwest_airlines',input_class='ORIGINAL_STATEMENT_VALUES')
 raise AssertionError('Changed policy accepted')
except ValueError as e:print('CHANGED_DATA_POLICY_REJECTED',type(e).__name__,str(e))
finally:p.write_bytes(original)
'''
p=out/'cold.py';p.write_text(code)
result=subprocess.run(['/usr/bin/python3',str(p),str(root),str(out)],capture_output=True,text=True)
(out/'cold.log').write_text(result.stdout+result.stderr);print(result.stdout+result.stderr)
assert result.returncode==0,result.returncode
(out/'index.json').write_text(json.dumps({'status':'PASS','scenarios':4,'new_calls':{'provider':0,'paid':0,'sec':0},'files':{relative:hashlib.sha256((data/relative).read_bytes()).hexdigest() for relative in sorted(paths)},'module_sha256':hashlib.sha256((root/'scripts/vnext/annual_amendment_scope.py').read_bytes()).hexdigest()},indent=2))
