"""Exact XML-item context, whole original responsibilities, offline only."""
from copy import deepcopy
import hashlib
import json
import time
from pathlib import Path
from vnext.capacity_semantic_review import _shared_units,_restore_units,_share_xml_styles,_xml_values,_STYLE_REF
from vnext.continuous_request_context import measure_request
from vnext.canonical import sha256_bytes

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
# Reuse the already exercised literal id/link inventory, without rerunning
# its measurement loop. No model meaning or keyword decision is imported.
pre=(HERE/'measure.py').read_text().split('prompt=(',1)[0]
namespace={"__file__":str(HERE/"measure.py")};exec(compile(pre,str(HERE/'measure.py'),'exec'),namespace)
source=namespace['source'];units=namespace['units'];graph=namespace['graph'];owner_ids=namespace['owner_ids'];ids=namespace['ids'];unresolved=namespace['unresolved']
byid={u['unit_id']:u for u in units};visible=[u for u in units if u['kind']=='VISIBLE_TEXT'];nodes={}
for u in units:
 if u['kind']=='NATIVE_FACTS':
  for w in u['payload']['facts']:
   attrs=w['attributes'];key=attrs.get('id')
   if not key:continue
   f=w['fact'];payload=u['payload'];ctx=f['context_ref'];unit=f['unit_ref'];env=w['namespace_environment_id']
   nodes[key]={'original_unit_id':u['unit_id'],'kind':'NATIVE_FACT','source_index':f['ordinal'],'original_item':w,'context':payload['contexts'].get(ctx),'unit':payload['units'].get(unit),'namespaces':payload['namespace_environments'][env]}
 elif u['kind']=='NATIVE_SUPPLEMENTS':
  for i,o in enumerate(u['payload']['objects']):
   for n in [o,*o['nested_objects']]:
    key=n['attributes'].get('id')
    if not key:continue
    raw=o['raw_xml'] if n is o else o['raw_xml'][n['relative_start_character']:n['relative_end_character']]
    assert sha256_bytes(content=raw.encode())==n['raw_xml_sha256']
    nodes[key]={'original_unit_id':u['unit_id'],'kind':'NATIVE_SUPPLEMENT','source_index':i,'element_id':key,'original_element':{k:v for k,v in n.items() if k not in ['raw_xml','nested_objects']},'raw_xml':raw,'root_raw_xml_sha256':o['raw_xml_sha256'],'relative_character_range':None if n is o else [n['relative_start_character'],n['relative_end_character']]}

def contexts_for(owned):
 todo=list(owner_ids[owned]);seen=set()
 while todo:
  item=todo.pop()
  if item in seen:continue
  seen.add(item);todo.extend(graph[item]-seen)
 return [nodes[key] for key in sorted(seen-owner_ids[owned]) if key in nodes]

prompt=(Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004/source-unit-pilot-time/prompt.txt')).read_text()
start=time.monotonic();rows=[]
for ordinal,u in enumerate(units):
 context={visible[0]['unit_id']}
 if u['kind']=='VISIBLE_TEXT':
  pos=next(i for i,v in enumerate(visible) if v['unit_id']==u['unit_id'])
  for i in [pos-1,pos+1]:
   if 0<=i<len(visible):context.add(visible[i]['unit_id'])
 context.discard(u['unit_id']);provided=[v for v in units if v['unit_id'] in context|{u['unit_id']}]
 packed,shared=_shared_units(provided);assert _restore_units(packed,shared)==provided
 items=deepcopy(contexts_for(u['unit_id']));original_items=deepcopy(items);context_shared={}
 _share_xml_styles(items,context_shared)
 restored_items=deepcopy(items)
 for obj,key in _xml_values(restored_items):obj[key]=_STYLE_REF.sub(lambda m:context_shared['xml_style_attributes'][m.group(1)],obj[key])
 assert restored_items==original_items
 payload={'source_id':source['semantic_source_id'],'company_id':source['company_id'],'target_period':source['prepared_annual_input']['table_input']['target_period'],'source_filing':source['documents'][0]['filing'],'source_extent':'WHOLE_ORIGINAL_OWNER_UNITS_EXACT_CONTEXT_ITEMS','source_unit_count':len(units),'responsibility_unit_ids':[u['unit_id']],'context_only_unit_ids':[v['unit_id'] for v in provided if v['unit_id'] in context],'source_units':packed,'shared_source_dictionaries':shared,'context_only_native_items':items,'context_xml_style_attributes':context_shared['xml_style_attributes']}
 body={'model':'deepseek-flash','messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,'stream':False,'thinking':{'type':'disabled'}}
 wire=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();m=measure_request(wire,require_reference=True)
 rows.append({'source_ordinal':ordinal,'unit_id':u['unit_id'],'kind':u['kind'],'context_units':len(context),'context_native_items':len(items),'input_tokens':m['input_tokens'],'context_tokens':m['context_tokens'],'request_bytes':len(wire),'fits':m['fits'],'request_sha256':sha256_bytes(content=wire)})
result={'source_id':source['semantic_source_id'],'owned_units_once':[r['unit_id'] for r in rows]==source['required_unit_ids'],'original_owner_unit_count':len(units),'owner_payloads_roundtrip':True,'xml_context_slice_hashes_verified':True,'physical_link_count':len(namespace['links']),'unresolved_physical_links':unresolved,'request_count_if_one_unit':len(rows),'fits_count':sum(r['fits'] for r in rows),'oversized_count':sum(not r['fits'] for r in rows),'maximum_context':max(r['context_tokens'] for r in rows),'rows':rows,'seconds':round(time.monotonic()-start,3),'model_blind_input_not_tested':True,'semantic_context_sufficiency_verified':False,'complete_company_ready':False,'business_calls':[0,0,0]}
(HERE/'measured-shared-item-context.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
