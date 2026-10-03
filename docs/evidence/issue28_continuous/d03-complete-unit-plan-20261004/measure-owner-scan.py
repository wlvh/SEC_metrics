"""Whole-owner scan cost; followup context intentionally remains a gate."""
import hashlib
import json
import time
from pathlib import Path
from vnext.capacity_semantic_review import _shared_units,_restore_units
from vnext.continuous_request_context import measure_request

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
source=json.load(open('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004/source.json'));units=source['units'];visible=[u for u in units if u['kind']=='VISIBLE_TEXT'];identity=visible[0]
prompt=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004/source-unit-pilot-time/prompt.txt').read_text()

def request(owners):
 ids={u['unit_id'] for u in owners};context=[] if identity['unit_id'] in ids else [identity];provided=owners+context;packed,shared=_shared_units(provided);assert _restore_units(packed,shared)==provided
 value={'source_id':source['semantic_source_id'],'company_id':source['company_id'],'target_period':source['prepared_annual_input']['table_input']['target_period'],'source_filing':source['documents'][0]['filing'],'responsibility_unit_ids':[u['unit_id'] for u in owners],'context_only_unit_ids':[u['unit_id'] for u in context],'source_units':packed,'shared_source_dictionaries':shared,'source_extent':'FIRST_OWNER_SCAN_ONLY_RELATED_CONTEXT_NOT_GUARANTEED'}
 body={'model':'deepseek-flash','messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(value,ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,'stream':False,'thinking':{'type':'disabled'}}
 raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();return raw,measure_request(raw,require_reference=True)

start=time.monotonic();groups=[];owned=[];current=[]
for unit in units:
 raw,m=request(current+[unit])
 # This lower first-pass input budget is an estimate, not a changed service
 # configuration or proof4096 can hold every group's findings.
 if current and (not m['fits'] or m['input_tokens']>100000 or len(current)>=4):
  wire,old=request(current);groups.append({'owner_unit_ids':[u['unit_id'] for u in current],'input_tokens':old['input_tokens'],'context_tokens':old['context_tokens'],'fits':old['fits'],'request_sha256':hashlib.sha256(wire).hexdigest()});current=[unit]
 else:current.append(unit)
if current:
 wire,m=request(current);groups.append({'owner_unit_ids':[u['unit_id'] for u in current],'input_tokens':m['input_tokens'],'context_tokens':m['context_tokens'],'fits':m['fits'],'request_sha256':hashlib.sha256(wire).hexdigest()})
owned=[u for row in groups for u in row['owner_unit_ids']];assert owned==source['required_unit_ids'] and len(owned)==len(set(owned))
result={'source_id':source['semantic_source_id'],'original_unit_count':len(units),'ownership_complete_once':True,'request_count_first_scan':len(groups),'all_first_scan_requests_fit':all(r['fits'] for r in groups),'maximum_context':max(r['context_tokens'] for r in groups),'groups':groups,'maximum_owner_units_per_scan':4,'grouping_input_target_not_service_limit':100000,'followup_context_request_count_unmeasured':True,'followup_dynamic_cap_unfixed':True,'output4096_or_semantic_coverage_unverified':True,'complete_company_ready':False,'business_calls':[0,0,0],'seconds':round(time.monotonic()-start,3)}
(HERE/'measured-owner-scan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='groups'}))
