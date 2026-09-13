import gzip,json,sys,time
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.r6_semantic_source import prepare_d04_semantic_source
from vnext.r6_semantic_review import requests_from_source
from vnext.normal_annual_input import _registry_rows
from tests.vnext.test_normal_zero_ai_results import original_sources_only
out=Path('/tmp/sec_metrics_issue28_continuous/d04-ten-company-inputs-v3');out.mkdir()
rows=[]
with original_sources_only():
 for c in _registry_rows(repo_root=ROOT):
  company=c['company_id'];started=time.monotonic()
  try:
   source=prepare_d04_semantic_source(repo_root=ROOT,company_id=company);requests=requests_from_source(source)
   for name,data in [('source',source),('requests',requests)]:
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    (out/(company+'-'+name+'.json.gz')).write_bytes(gzip.compress(raw,mtime=0))
   row={'company_id':company,'status':'INPUTS_SERIALIZED','source_id':source['semantic_source_id'],
    'documents':len(source['documents']),'units':len(source['units']),'requests':len(requests),
    'source_payload_bytes':sum(u['payload_bytes'] for u in source['units']),
    'native_facts':sum(d['native_coverage']['fact_count'] for d in source['documents']),
    'semantic_interpretation_executed':False,'provider_tokens_measured':False,'calls':{'provider':0,'paid':0,'sec':0}}
  except Exception as e:
   row={'company_id':company,'status':'SOURCE_PREPARATION_FAILED','error_type':type(e).__name__,'reason':str(e),
        'semantic_interpretation_executed':False,'calls':{'provider':0,'paid':0,'sec':0}}
  row['duration_seconds']=round(time.monotonic()-started,3);rows.append(row)
  print(json.dumps(row,ensure_ascii=False),flush=True)
(out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
