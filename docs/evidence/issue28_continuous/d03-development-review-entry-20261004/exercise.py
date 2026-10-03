import hashlib
import json
import socket
import time
from pathlib import Path
from unittest.mock import patch

import vnext_d03_model_review as cli

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-complete-six-responses-20261004')
index=json.loads((ROOT/'docs/evidence/issue28_continuous/d03-native-input-check-20261003/complete-set.json').read_text())
manifest={'company_id':'marriott_international','source_sha256':index['source_sha256'],
 'requests':[{'request_path':str(BASE/'processing'/str(r['index'])/'request-body.bin'),
 'response_path':str(BASE/'processing'/str(r['index'])/'response.bin'),
 'request_sha256':r['request_sha256'],'response_sha256':r['response_sha256']} for r in index['requests']]}
manifest_path=HERE/'input.json';manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

def blocked(*a,**k): raise AssertionError('NETWORK_FORBIDDEN')
socket.socket=blocked;socket.create_connection=blocked

def digest_files(root):
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

target=BASE/'native-pending-cli';assert not target.exists()
start=time.monotonic();out,company=cli.save(manifest_path=manifest_path,data_root=ROOT,output_root=target);save_s=time.monotonic()-start
before=digest_files(target);start=time.monotonic();again,_=cli.save(manifest_path=manifest_path,data_root=ROOT,output_root=target);repeat_s=time.monotonic()-start
assert out==again and before==digest_files(target)
old=json.loads((ROOT/'docs/evidence/issue28_continuous/d03-model-native-mapping-20261004/build-summary.json').read_text())
assert out['records'][1]['candidate_hash']==old['candidate_hash'] and out['records'][3]['review_unit_hash']==old['unit_hash']
partial=BASE/'native-pending-cli-interrupted';assert not partial.exists();original=cli.write_immutable_bytes;count=[]
def interrupted(**kw):
 count.append(str(kw['path']))
 if len(count)==4:raise OSError('INTERRUPTION_TEST')
 original(**kw)
try:
 with patch.object(cli,'write_immutable_bytes',side_effect=interrupted):
  cli.save(manifest_path=manifest_path,data_root=ROOT,output_root=partial)
except OSError as e:assert str(e)=='INTERRUPTION_TEST'
else:raise AssertionError('INTERRUPTION_NOT_RAISED')
assert not (partial/'records.jsonl').exists();partial_before=digest_files(partial)
start=time.monotonic();resumed,_=cli.save(manifest_path=manifest_path,data_root=ROOT,output_root=partial);resume_s=time.monotonic()-start
assert resumed==out and digest_files(partial)==before
assert all(digest_files(partial)[n]==h for n,h in partial_before.items())
summary={'tested_base_sha':'2ab895d45b5051f415e07c62f87e74179afd086d','uncommitted_cli_delta':True,
 'code_root':str(ROOT),'data_root':str(ROOT),'output_root':str(target),'partial_resume_root':str(partial),
 'candidate_hash':old['candidate_hash'],'review_unit_hash':old['unit_hash'],'status':'PENDING',
 'request_count':6,'source_units':17,'findings':25,'unresolved':18,'save_seconds':round(save_s,3),
 'repeat_seconds':round(repeat_s,3),'resume_seconds':round(resume_s,3),'all_saved_bytes_identical':True,
 'old_native_pending_identity_preserved':True,'no_result_or_run':True,'business_calls':[0,0,0],
 'file_sha256':before}
(HERE/'exercise-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='file_sha256'}))
