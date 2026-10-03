import hashlib,json,socket,time
from pathlib import Path
from unittest.mock import patch
from collections import Counter
from vnext.normal_source_authority import ROOT
from vnext.normal_annual_input import _registry_rows
from vnext.normal_source_requirements import discover_saved_source_requirements
from sec_http import parse_request_log_rows,validate_request_log_manifest
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
out=Path('/tmp/sec_metrics_issue28_continuous/remaining-call-tail')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
watched=['evidence/requests_log.csv','evidence/requests_log_manifest.json','config/company_registry.csv','config/ordinary_public_projection_v1.json']
before={p:sha(base/p)for p in watched}
validate_request_log_manifest(log_path=base/'evidence/requests_log.csv')
latest={r['source_url']:r for r in parse_request_log_rows(text=(base/'evidence/requests_log.csv').read_text())}
failed={u:r for u,r in latest.items()if r['status_code']!='200' or r['error']}
companies=[];urls={};started=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
 for company in _registry_rows(repo_root=ROOT):
  cid=company['company_id'];t=time.monotonic()
  try:
   d=discover_saved_source_requirements(repo_root=base,company_id=cid)
   compact=[]
   for r in d['requirements']:
    u=r['source_url'];is_failed=u in failed
    if is_failed or r['saved_status']=='SAVED_SOURCE_BLOCKED':bucket='BLOCKED_OR_PREVIOUSLY_FAILED_NO_AUTOMATIC_RETRY'
    elif r['refresh_for_new_discovery']:bucket='DECLARED_METADATA_REFRESH'
    elif r['saved_status']=='MISSING_SAVED_SOURCE':bucket='KNOWN_MISSING_DECLARED_DEPENDENCY'
    else:bucket='VERIFIED_SAVED_REUSE_NO_NEW_SEC_REQUIRED'
    rr={k:r[k]for k in ['source_url','roles','accession','media_type','refresh_for_new_discovery','saved_status']}
    rr.update(bucket=bucket,**{k:r[k]for k in ['reason','error_type']if k in r})
    if is_failed:rr['last_failed_request']={k:failed[u][k]for k in ['status_code','error','timestamp_utc','repo_relative_path']}
    compact.append(rr)
    item=urls.setdefault(u,{'source_url':u,'companies':[],'roles':[],'buckets':[]})
    for key,val in [('companies',cid),('buckets',bucket)]:
     if val not in item[key]:item[key].append(val)
    for role in r['roles']:
     if role not in item['roles']:item['roles'].append(role)
   result={'company_id':cid,'status':d['status'],'requirements_id':d['requirements_id'],
    'source_period':None if not d['prepared_annual_input']else d['prepared_annual_input']['table_input']['target_period'],
    'metadata':d['metadata'],'complete_new_source_graph_known':d['complete_new_source_graph_known'],
    'limitations':d['limitations'],'requirements':compact,'counts':dict(Counter(r['bucket']for r in compact)),
    'required_instance_document_candidates':[r['source_url']for r in compact if 'annual_accession_instance'in r['roles']],
    'directory_enumeration_scope':'Only existing discovery-declared primary/header/index/instance dependencies; no other directory members counted',
    'seconds':time.monotonic()-t}
  except Exception as e:result={'company_id':cid,'status':'READ_ONLY_DISCOVERY_FAILED','error_type':type(e).__name__,'reason':str(e),'requirements':[],'seconds':time.monotonic()-t}
  companies.append(result)
  print(cid,result['status'],result.get('counts'),round(result['seconds'],3),flush=True)
  (out/'sec-discovery.json').write_text(json.dumps({'source_root':str(base),'source_snapshot_before':before,'companies':companies,'deduplicated_urls':list(urls.values()),'no_network':True,'new_calls':[0,0,0]},ensure_ascii=False,indent=2)+'\n')
after={p:sha(base/p)for p in watched};assert after==before
allurls=list(urls.values());counts=Counter()
for r in allurls:
 buckets=set(r['buckets'])
 if 'BLOCKED_OR_PREVIOUSLY_FAILED_NO_AUTOMATIC_RETRY'in buckets:r['decision']='BLOCKED_OR_PREVIOUSLY_FAILED_NO_AUTOMATIC_RETRY'
 elif 'DECLARED_METADATA_REFRESH'in buckets:r['decision']='DECLARED_METADATA_REFRESH'
 elif 'KNOWN_MISSING_DECLARED_DEPENDENCY'in buckets:r['decision']='KNOWN_MISSING_DECLARED_DEPENDENCY'
 else:r['decision']='VERIFIED_SAVED_REUSE_NO_NEW_SEC_REQUIRED'
 counts[r['decision']]+=1
result={'source_root':str(base),'source_snapshot_before':before,'source_snapshot_after':after,'companies':companies,'deduplicated_urls':allurls,'deduplicated_counts':dict(counts),
 'processing_rule_boundary':{'relative_path':'config/ordinary_public_projection_v1.json','fixed_source_root_sha256':before['config/ordinary_public_projection_v1.json'],'current_repository_sha256':sha(ROOT/'config/ordinary_public_projection_v1.json'),'bytes_equal':(base/'config/ordinary_public_projection_v1.json').read_bytes()==(ROOT/'config/ordinary_public_projection_v1.json').read_bytes(),
 'normal_refresh_initialization_ready':False,'known_failure':'Immutable receipt bytes differ before SEC egress; this read-only discovery is not successful refresh initialization'},
 'no_network':True,'new_calls':[0,0,0],'seconds':time.monotonic()-started,'future_metadata_changes_may_add_or_remove_dependencies':True,'all390_acceptance':False,'production_authorized':False}
(out/'sec-discovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('DEDUP',dict(counts),'SECONDS',round(result['seconds'],3),flush=True)
