"""Whole original unit plus whole context unit; bounded developer regression."""
import json
from pathlib import Path
from vnext.continuous_request_context import measure_request
from vnext.canonical import sha256_bytes

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004')
TARGET=BASE/'source-unit-pilot';TARGET.mkdir(exist_ok=False)
source=json.loads((BASE/'source.json').read_bytes());visible=[u for u in source['units'] if u['kind']=='VISIBLE_TEXT'];owned=visible[20];context=visible[0]
prompt=(ROOT/'docs/evidence/issue28_continuous/d03-complete-context-plan-20261003/input-prompt.txt').read_text()
old='This is a partial-responsibility development request within a complete source plan. It supplies every visible block as context plus the assigned native units, if any. Assess every responsibility_unit_id. The other visible units in a native request are context only, not a second assessment. Each original unit has one assessment owner in the plan. Do not infer whole-company absence from a partial request or from an empty finding list.'
new='This is a bounded original-source-unit development request, not a complete company plan or an absence assessment. The input provides whole, unmodified responsibility units and separately labelled whole context-only units. Assess every responsibility_unit_id. Each finding needs an evidence reference in a responsibility unit; context-only evidence may support it but must not become a second standalone assessment. Source outside these units is not supplied. Preserve unresolved when necessary related context is missing. Do not infer whole-company absence or complete-source review from this partial input or an empty finding list.'
assert old in prompt;prompt=prompt.replace(old,new)
input={'source_id':source['semantic_source_id'],'company_id':source['company_id'],'target_period':source['prepared_annual_input']['table_input']['target_period'],'source_filing':source['documents'][0]['filing'],'source_extent':'ORIGINAL_UNIT_SUBSET_DEVELOPMENT_NO_COMPLETE_COMPANY_CREDIT','original_source_unit_count':len(source['units']),'source_units':[owned,context],'responsibility_unit_ids':[owned['unit_id']],'context_only_unit_ids':[context['unit_id']]}
wire={'model':'deepseek-flash','messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(input,ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,'stream':False,'thinking':{'type':'disabled'}}
raw=json.dumps(wire,ensure_ascii=False,separators=(',',':')).encode();(TARGET/'input.json').write_text(json.dumps(input,ensure_ascii=False,indent=2)+'\n');(TARGET/'prompt.txt').write_text(prompt);(TARGET/'request-body.json').write_bytes(raw)
measurement=measure_request(raw,require_reference=True);assert measurement['fits'];assert all(u==next(v for v in source['units'] if v['unit_id']==u['unit_id']) for u in input['source_units'])
record={'input_root':str(TARGET),'source_id':source['semantic_source_id'],'source_sha256':sha256_bytes(content=(BASE/'source.json').read_bytes()),'owner_units':1,'context_only_units':1,'original_unit_count':len(source['units']),'whole_source_coverage':False,'company_native_acceptance':False,'request_sha256':sha256_bytes(content=raw),'prompt_sha256':sha256_bytes(content=prompt.encode()),'measurement':measurement,'business_calls':[0,0,0]}
(HERE/'unit-input-summary.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k!='measurement'}));print('input/context tokens',measurement['input_tokens'],measurement['context_tokens'])
