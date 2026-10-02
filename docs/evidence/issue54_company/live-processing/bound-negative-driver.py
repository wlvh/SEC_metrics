import hashlib,json,shutil,subprocess,os,sys,time
from pathlib import Path
w=Path('/workspace/work');state=w/'company-d04-c13-state';clone=w/'company-d04-c13-bound-negative';out=w/'company-d04-c13-bound-negative-export'
pointer=next((state/'updates/processing').glob('D04/*/current.json'));candidate=json.loads(pointer.read_text())['candidate'];work=Path(candidate['rows_root']).parent
manifest=json.loads((work/'runs/D04/manifest.json').read_text());ref=next(r for r in manifest['source_references'] if r['document_name']=='enph-20251231.htm')
b=json.loads((work/'data/ordinary_integrated_bindings'/(manifest['run_id'].split(':')[-1]+'.json')).read_text());proof=next(p for p in b['input_binding']['source_proofs'] if p['request_attempt_id']==ref['request_attempt_id']);assert proof['content_sha256']==ref['raw_asset_id'][7:]
shutil.copytree(state,clone)
# Relocate only #54's thin local indices, never native Run/data or saved inputs.
paths=list(clone.glob('*.json'))+list((clone/'company-executions').glob('*.json'))+list((clone/'updates').glob('**/current.json'))
for p in paths:
 raw=p.read_text()
 if str(state) in raw:p.chmod(p.stat().st_mode|0o600);p.write_text(raw.replace(str(state),str(clone)))
bound=clone/work.relative_to(state)/'current-source'/proof['request_headers_repo_relative_path'];before=hashlib.sha256(bound.read_bytes()).hexdigest();original=hashlib.sha256((work/'current-source'/proof['request_headers_repo_relative_path']).read_bytes()).hexdigest();bound.chmod(bound.stat().st_mode|0o600);bound.write_bytes(bound.read_bytes()+b'\nLIVE_D04_ACTUAL_CURRENT_BOUND_HEADER_NEGATIVE\n')
start=time.monotonic();cmd=[sys.executable,'-B',str(w/'isolated_company_cli.py'),str(w/'company-d04-acquired-runtime-final'),'export-results','--state-root',str(clone),'--trust-root',str(w/'company-d04-combined-source-trust'),'--processing-trust-root',str(w/'company-d04-live-trust'),'--company','enphase_energy','--runtime-root',str(w/'company-d04-acquired-runtime-final'),'--runtime-root',str(w/'company-d04-acquired-runtime-v6'),'--runtime-root',str(w/'company-d04-live-program'),'--output-root',str(out)]
env={**os.environ,'COMPANY_DENY_READ_ROOTS':str(state)+':/workspace/SEC_metrics:/workspace/work/sec-company-compute:/workspace/work/ordinary-mixed-restored-complete','PYTHONPATH':str(w/'tokenizer-validation')}
child=subprocess.run(cmd,env=env,capture_output=True,text=True);(w/'company-d04-c13-bound-negative.stdout.json').write_text(child.stdout);(w/'company-d04-c13-bound-negative.stderr.log').write_text(child.stderr)
payload=json.loads(child.stdout);assert child.returncode==2 and payload['status']=='EXPORTED_PARTIAL';assert len(payload['failed_candidates'])==1 and not payload['native_candidates'];assert 'COMPANY_SOURCE_BYTES_CHANGED' in payload['failed_candidates'][0]['reason'];assert hashlib.sha256((work/'current-source'/proof['request_headers_repo_relative_path']).read_bytes()).hexdigest()==original
report={'status':'PASSED','scope':'ACTUAL_D04_RUN_REFERENCED_HEADER_IN_CURRENT_EQUIVALENCE_SOURCE_PRIVATE_COPY','run_id':manifest['run_id'],'request_attempt_id':ref['request_attempt_id'],'source_reference_id':ref['source_reference_id'],'actual_bound_relative_path':proof['request_headers_repo_relative_path'],'before_sha256':before,'after_sha256':hashlib.sha256(bound.read_bytes()).hexdigest(),'original_unchanged':True,'rejection':payload['failed_candidates'][0]['reason'],'seconds':time.monotonic()-start,'new_business_calls':[0,0,0]};print(json.dumps(report,indent=2));(w/'company-d04-c13-bound-negative.json').write_text(json.dumps(report,indent=2))
