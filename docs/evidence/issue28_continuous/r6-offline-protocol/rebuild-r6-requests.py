import gzip,json,sys
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.r6_semantic_review import requests_from_source
from vnext.r6_semantic_source import POLICY_PATH
from vnext.canonical import sha256_file,strict_json_loads
from vnext.normal_source_authority import verify_saved_source_proofs
out=Path('/tmp/sec_metrics_issue28_continuous/d04-request-drafts-final');out.mkdir();rows=[]
for file in sorted(Path('/tmp/sec_metrics_issue28_continuous/d04-ten-company-inputs-v3').glob('*-source.json.gz')):
 source=strict_json_loads(text=gzip.decompress(file.read_bytes()).decode())
 assert source['module_sha256']==sha256_file(path=ROOT/'scripts/vnext/r6_semantic_source.py')
 assert source['policy_sha256']==sha256_file(path=ROOT/POLICY_PATH)
 verify_saved_source_proofs(data_root=ROOT,proofs=source['source_proofs'])
 requests=requests_from_source(source);target=out/(source['company_id']+'.json.gz')
 target.write_bytes(gzip.compress(json.dumps(requests,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
 row={'company_id':source['company_id'],'source_id':source['semantic_source_id'],'source_file':str(file),'source_file_sha256':sha256_file(path=file),
      'request_count':len(requests),'request_file':target.name,'request_file_sha256':sha256_file(path=target),
      'fiscal_label_context':requests[0]['fiscal_label_context'],'source_tree_reparsed':False,'original_source_bytes_reverified':True,
      'provider_request_sent':False}
 rows.append(row);print(source['company_id'],len(requests),row['fiscal_label_context'],flush=True)
(out/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
