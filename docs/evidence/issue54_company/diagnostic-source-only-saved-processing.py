import hashlib,json,shutil,sys,time
from pathlib import Path
r=Path('/workspace/work/sec-company-compute');w=r.parent;registered=r/'config/ordinary_going_concern_assessment.json';saved=w/'recorded-d04-restored/d04-reference-5207290213/data/config/ordinary_going_concern_assessment.json'
assert not registered.exists()
sys.path[:0]=[str(r/'scripts'),str(r)]
from vnext.company_handoff import rule_bindings,export_company,PROCESSING_STATE_PATHS
from vnext.company_runtime_install import install_runtime
before=rule_bindings();start=time.monotonic();raw=saved.read_bytes();record=json.loads(raw)
try:
 registered.write_bytes(raw)
 after=rule_bindings();assert after==before
 runtime=w/'company-source-only-runtime';installation=install_runtime(output_root=runtime,kind='baseline')
 assert all(not (runtime/p).exists() for p in PROCESSING_STATE_PATHS)
 package=w/'company-source-only-marriott';metadata=export_company(source_root=r,output_root=package,trust_root=w/'company-source-only-trust',company_id='marriott_international',metric_ids=['B01'])
 assert all(not (package/p).exists() for p in PROCESSING_STATE_PATHS)
 cp=json.loads((package/'config/ordinary_source_checkpoint.json').read_text());assert set(PROCESSING_STATE_PATHS).isdisjoint(cp['rules'])
 assert registered.read_bytes()==raw
 report={'status':'SOURCE_AND_RUNTIME_EXCLUDE_SAVED_PROCESSING','saved_processing_company':record['company_id'],'target_source_company':'marriott_international','saved_input_record_id':record['input_record_id'],'saved_processing_sha256':hashlib.sha256(raw).hexdigest(),'rules_identical_with_and_without_saved_processing':True,'runtime_contains_processing_state':False,'package_contains_processing_state':False,'source_checkpoint_id':cp['checkpoint_id'],'source_sizes_bytes':metadata['sizes_bytes'],'runtime':installation,'elapsed_seconds':time.monotonic()-start,'original_processing_material_preserved':True,'new_business_calls':[0,0,0]}
 (w/'company-source-only-saved-processing-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
finally:
 assert registered.read_bytes()==raw
 registered.unlink()
