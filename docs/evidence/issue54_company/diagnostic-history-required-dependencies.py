import os,sys,json,shutil,time
from pathlib import Path
w=Path('/workspace/work');runtime=w/'company-history-runtime-v4';state=w/'company-history-jpm-v4-state';out=w/'company-history-dependency-negatives';out.mkdir()
r=json.loads((state/'company-results.json').read_text());work=Path(r['metrics'][0]['last_verified_candidate']['rows_root']).parent;run=work/'runs/A08';records=[json.loads(s) for s in (run/'records.jsonl').read_text().splitlines()];blobs={a['raw_asset_id']:a for a in records if a['record_type']=='RAW_BLOB'};references=[a for a in records if a['record_type']=='SOURCE_REFERENCE']
selected=[('required_submissions_shard',next(a for a in references if '-submissions-' in a['document_name'])),('required_prior_annual',next(a for a in references if a['accession']=='0000019617-23-000231' and a['document_name'].endswith('.htm')))]
sys.path[:0]=[str(runtime/'scripts'),str(runtime)];os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(w/'company-history-trust')
from vnext.run_store import load_frozen_run
results=[]
for name,reference in selected:
 case=out/name;shutil.copytree(work/'data',case/'data');shutil.copytree(run,case/'run');path=blobs[reference['raw_asset_id']]['storage_uri'];(case/'data'/path).unlink();start=time.monotonic()
 try:load_frozen_run(run_dir=case/'run',repo_root=case/'data')
 except Exception as e:
  reason=str(e);assert 'RawBlob' in reason or 'source' in reason.lower() or 'regular file' in reason.lower(),reason
  results.append({'case':name,'source_reference_id':reference['source_reference_id'],'request_attempt_id':reference['request_attempt_id'],'actual_run_storage_uri':path,'status':'REJECTED','error_type':type(e).__name__,'reason':reason,'seconds':time.monotonic()-start})
 else:raise AssertionError(name+' was accepted')
report={'status':'PASSED','company_id':'jpmorgan_chase','report_end':'2023-12-31','native_run_id':json.loads((run/'manifest.json').read_text())['run_id'],'probes':results,'new_business_calls':[0,0,0]};(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
