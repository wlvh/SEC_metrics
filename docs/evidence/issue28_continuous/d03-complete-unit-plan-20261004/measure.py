"""Offline complete-owner plan with literal native links, not a truth parser."""
import hashlib
import json
import socket
import time
from collections import defaultdict
from pathlib import Path

from vnext.capacity_semantic_review import _shared_units, _restore_units
from vnext.continuous_request_context import measure_request
from vnext.canonical import content_hash

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004/source.json')
source_raw=SOURCE.read_bytes();assert hashlib.sha256(source_raw).hexdigest()=='11189144bf0bff60c8995086f9fb2bfa253a38a1206d557a059b9c771f8486a9'
source=json.loads(source_raw);units=source['units'];by_id={u['unit_id']:u for u in units}
assert source['required_unit_ids']==[u['unit_id'] for u in units]
assert source['semantic_source_id']==content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
visible=[u for u in units if u['kind']=='VISIBLE_TEXT'];identity_context=visible[0]['unit_id']
ids={};owner_ids=defaultdict(set);graph=defaultdict(set);links=[];unresolved=[]
for u in units:
 if u['kind']=='NATIVE_FACTS':items=[w['attributes'] for w in u['payload']['facts']]
 elif u['kind']=='NATIVE_SUPPLEMENTS':items=[a for o in u['payload']['objects'] for a in [o['attributes'],*[n['attributes'] for n in o['nested_objects']]]]
 else:continue
 for a in items:
  if a.get('id'):
   assert a['id'] not in ids or ids[a['id']]==u['unit_id'];ids[a['id']]=u['unit_id'];owner_ids[u['unit_id']].add(a['id'])
  if a.get('id') and a.get('continuedat'):links.append((a['id'],a['continuedat'],'CONTINUATION'))
  for left in a.get('fromrefs','').split():
   for right in a.get('torefs','').split():links.append((left,right,'FOOTNOTE_RELATIONSHIP'))
for a,b,kind in links:
 if a not in ids or b not in ids:unresolved.append({'from':a,'to':b,'kind':kind});continue
 graph[a].add(b);graph[b].add(a)

def context_for(owned):
 result={identity_context};todo=list(owner_ids[owned]);seen=set()
 while todo:
  item=todo.pop()
  if item in seen:continue
  seen.add(item);result.add(ids[item]);todo.extend(graph[item]-seen)
 # Whole neighbouring original units preserve the visible boundary without
 # claiming they solve arbitrary long-distance semantics or cross-reference.
 if by_id[owned]['kind']=='VISIBLE_TEXT':
  pos=next(i for i,u in enumerate(visible) if u['unit_id']==owned)
  for i in [pos-1,pos+1]:
   if 0<=i<len(visible):result.add(visible[i]['unit_id'])
 return result-{owned}

prompt=(Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004/source-unit-pilot-time/prompt.txt')).read_text()
start=time.monotonic();rows=[]
for ordinal,u in enumerate(units):
 context=context_for(u['unit_id']);provided=[v for v in units if v['unit_id'] in context|{u['unit_id']}]
 packed,shared=_shared_units(provided);assert _restore_units(packed,shared)==provided
 payload={'source_id':source['semantic_source_id'],'company_id':source['company_id'],'target_period':source['prepared_annual_input']['table_input']['target_period'],'source_filing':source['documents'][0]['filing'],'source_extent':'WHOLE_ORIGINAL_UNITS_WITH_SEPARATE_CONTEXT_ROLES','source_unit_count':len(units),'responsibility_unit_ids':[u['unit_id']],'context_only_unit_ids':[v['unit_id'] for v in provided if v['unit_id'] in context],'source_units':packed,'shared_source_dictionaries':shared}
 body={'model':'deepseek-flash','messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,'stream':False,'thinking':{'type':'disabled'}}
 wire=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();measure=measure_request(wire,require_reference=True)
 rows.append({'source_ordinal':ordinal,'unit_id':u['unit_id'],'kind':u['kind'],'context_units':len(context),'input_tokens':measure['input_tokens'],'context_tokens':measure['context_tokens'],'request_bytes':len(wire),'fits':measure['fits'],'request_sha256':hashlib.sha256(wire).hexdigest()})
 assert len(rows)<=len(units)
result={'source_sha256':hashlib.sha256(source_raw).hexdigest(),'source_id':source['semantic_source_id'],'owners':[r['unit_id'] for r in rows],'original_source_unit_ids':source['required_unit_ids'],'owned_units_once':len(rows)==len({r['unit_id'] for r in rows}) and [r['unit_id'] for r in rows]==source['required_unit_ids'],'source_payloads_roundtrip':True,'requests_if_single_unit':len(rows),'fits_count':sum(r['fits'] for r in rows),'oversized_count':sum(not r['fits'] for r in rows),'native_physical_link_count':len(links),'unresolved_physical_links':unresolved,'rows':rows,'maximum_context':max(r['context_tokens'] for r in rows),'seconds':round(time.monotonic()-start,3),'semantic_context_sufficiency_verified':False,'prompt_input_shared_representation_not_yet_blind_tested':True,'live_authorized':False,'business_calls':[0,0,0]}
(HERE/'measured-whole-unit-context.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','owners','original_source_unit_ids']},ensure_ascii=False))
