"""Mutate the actual B01 Run-bound immutable body/headers in private copies."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
state=Path('/workspace/work/company-results-state')
controller=Path('/workspace/work/sec-company-compute/tools/vnext_company.py')
base=json.loads((state/'updates/metrics/B01/current.json').read_text())
attempt=base['successful_attempt'];work=state/'updates/metrics/B01/attempts'/attempt
manifest=json.loads((work/'runs/B01/manifest.json').read_text())
ref=next(r for r in manifest['source_references'] if 'companyfacts' in r['source_url'])
binding=json.loads((work/'data/ordinary_integrated_bindings'/ (manifest['run_id'].split(':')[-1]+'.json')).read_text())
proof=next(p for p in binding['input_binding']['source_proofs'] if p['source_url']==ref['source_url'] and p['request_attempt_id']==ref['request_attempt_id'])
assert proof['content_sha256']==ref['raw_asset_id'][7:]
results=[]
for key in ['request_repo_relative_path','request_headers_repo_relative_path']:
 copy=Path('/workspace/work')/('company-result-negative-'+key);shutil.copytree(state,copy)
 bound=copy/'updates/metrics/B01/attempts'/attempt/'data'/proof[key]
 old=hashlib.sha256(bound.read_bytes()).hexdigest();bound.write_bytes(bound.read_bytes()+b'\nACTUAL_BOUND_EXPORT_NEGATIVE\n')
 output=Path(str(copy)+'-export');start=time.monotonic()
 command=[sys.executable,str(controller),'export-results','--state-root',str(copy),'--company','marriott_international','--trust-root','/workspace/work/baseline-company-trust','--runtime-root','/workspace/work/company-results-runtime-c17','--output-root',str(output)]
 child=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'COMPANY_DENY_READ_ROOTS':str(state)+':/workspace/SEC_metrics'})
 payload=json.loads(child.stdout)
 assert child.returncode==2 and payload['status']=='EXPORTED_PARTIAL',child.stderr
 assert [c['metric_id'] for c in payload['native_candidates']]==['D01'],payload
 assert [c['metric_id'] for c in payload['failed_candidates']]==['B01'],payload
 results.append({'field':key,'run_id':manifest['run_id'],'source_reference_id':ref['source_reference_id'],
  'request_attempt_id':ref['request_attempt_id'],'actual_bound_relative_path':proof[key],
  'before_sha256':old,'after_sha256':hashlib.sha256(bound.read_bytes()).hexdigest(),
  'status':payload['status'],'reason':payload['failed_candidates'][0]['reason'],
  'other_metric_exported':['D01'],'seconds':time.monotonic()-start})
print(json.dumps({'status':'PASSED','scope':'REAL_RUN_BOUND_INPUTS_PRIVATE_COPIES','probes':results,'new_business_calls':[0,0,0]},indent=2))
