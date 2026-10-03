"""Actual next-company source and first complete visible request, offline."""
import json
import socket
import time
from pathlib import Path
from vnext.r6_regulatory_semantics import prepare_regulatory_semantic_source
from vnext.continuous_request_context import FORMAT_VERSION, measure_request
from vnext.native_unit_index import evidence_json_bytes
from vnext.canonical import sha256_bytes

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
TARGET=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004')

def blocked(*a,**k):raise AssertionError('NETWORK_FORBIDDEN')
socket.socket=blocked;socket.create_connection=blocked
start=time.monotonic();source=prepare_regulatory_semantic_source(repo_root=ROOT,company_id='jpmorgan_chase',request_context_format=FORMAT_VERSION,ordinary_registered=True)
source_seconds=time.monotonic()-start
TARGET.mkdir(exist_ok=False,parents=True)
source_raw=evidence_json_bytes(source);(TARGET/'source.json').write_bytes(source_raw)
visible=[u for u in source['units'] if u['kind']=='VISIBLE_TEXT'];rows=[];bounds=[]
for u in visible:
 start_row=len(rows);rows.extend([[b['block_index'],b['html_quotation_context'],b['text']] for b in u['payload']['blocks']]);bounds.append({'unit_id':u['unit_id'],'start_row':start_row,'end_row_exclusive':len(rows)})
prompt=(ROOT/'docs/evidence/issue28_continuous/d03-complete-context-plan-20261003/input-prompt.txt').read_text()
payload={'source_id':source['semantic_source_id'],'company_id':source['company_id'],'target_period':source['prepared_annual_input']['table_input']['target_period'],'source_filing':source['documents'][0]['filing'],'visible_columns':['source_index','html_quotation_context','text'],'complete_visible_rows':rows,'visible_unit_bounds':bounds,'native_units':[],'shared_source_dictionaries':{},'responsibility_unit_ids':[u['unit_id'] for u in visible],'visible_context_role':'RESPONSIBILITY'}
body={'model':'deepseek-flash','messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,'stream':False,'thinking':{'type':'disabled'}}
raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();(TARGET/'visible-request-body.json').write_bytes(raw);(TARGET/'input.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
measurement=measure_request(raw,require_reference=True)
record={'code_root':str(ROOT),'data_root':str(ROOT),'input_root':str(TARGET),'source_id':source['semantic_source_id'],'source_sha256':sha256_bytes(content=source_raw),'source_seconds':round(source_seconds,3),'documents':len(source['documents']),'units_total':len(source['units']),'visible_units':len(visible),'visible_rows':len(rows),'native_units_total':len(source['units'])-len(visible),'request_sha256':sha256_bytes(content=raw),'measurement':measurement,'full_company_input':False,'business_calls':[0,0,0]}
(HERE/'prepare-summary.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record))
