import os,sys,json,shutil,time
from pathlib import Path
w=Path('/workspace/work');runtime=w/'company-runtime-release';out=w/'company-rehashed-admission-negative';shutil.copytree(w/'product-b-source-v2',out)
sys.path[:0]=[str(runtime/'scripts'),str(runtime)];os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(w/'company-admission-negatives/external-readonly-trust')
from vnext.canonical import canonical_json_bytes,content_hash,strict_json_file
from vnext.company_handoff import check_package
p=out/'config/ordinary_source_checkpoint.json';cp=strict_json_file(path=p);original=cp['checkpoint_id'];cp['real_sec_credit']=True;cp['source_credit']='VERIFIED_SEC_ACQUISITION';cp['checkpoint_id']=content_hash(value={k:v for k,v in cp.items() if k!='checkpoint_id'});p.write_bytes(canonical_json_bytes(value=cp));meta=strict_json_file(path=out/'company-source-package.json');meta['checkpoint_id']=cp['checkpoint_id'];(out/'company-source-package.json').write_bytes(canonical_json_bytes(value=meta));start=time.monotonic()
try:check_package(package_root=out,company_id='jpmorgan_chase')
except Exception as e:
 assert cp['checkpoint_id'][7:] in str(e),str(e)
 report={'status':'REJECTED','case':'rehashed_recorded_to_live_packet_without_external_trust','original_checkpoint':original,'attempted_checkpoint':cp['checkpoint_id'],'reason':str(e),'error_type':type(e).__name__,'seconds':time.monotonic()-start,'new_business_calls':[0,0,0]}
else:raise AssertionError('Self-signed LIVE input accepted')
(w/'company-rehashed-admission-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
