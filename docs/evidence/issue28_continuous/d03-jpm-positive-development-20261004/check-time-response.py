"""Mechanical partial-response check; no semantic or complete-company credit."""
import hashlib
import json
import socket
import subprocess
import time
from pathlib import Path
from vnext import d03_model_processing as mapper
from vnext.continuous_request_context import _load_tokenizer,measure_request

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-jpm-positive-20261004/source.json')
summary=json.loads((HERE/'time-input-summary.json').read_text());INPUT=Path(summary['input_root'])

def blocked(*a,**k):raise AssertionError('NETWORK_SUBPROCESS_FORBIDDEN')
socket.socket=blocked;socket.create_connection=blocked;subprocess.Popen=blocked;subprocess.run=blocked
start=time.monotonic();source_raw=SOURCE.read_bytes();assert hashlib.sha256(source_raw).hexdigest()==summary['source_sha256'];source=json.loads(source_raw)
request=(INPUT/'request-body.json').read_bytes();assert hashlib.sha256(request).hexdigest()==summary['request_sha256'];wire=json.loads(request);payload=json.loads(wire['messages'][1]['content']);assert payload==json.loads((INPUT/'input.json').read_text())
units={u['unit_id']:u for u in payload['source_units']};old={u['unit_id']:u for u in source['units']};assert all(u==old[k] for k,u in units.items());assert set(units)==set(payload['responsibility_unit_ids'])|set(payload['context_only_unit_ids'])
raw=(HERE/'independent-time-input/response.log').read_bytes();parsed=mapper._response(raw,payload,units);tokenizer,_=_load_tokenizer();output_tokens=len(tokenizer.encode(raw.decode(),add_special_tokens=False).ids)
try:mapper._input(source,request)
except ValueError as e:assert str(e)=='D03_MODEL_REQUEST_CONTRACT_OR_RESOURCE_CHANGED';complete_contract_refusal=str(e)
else:raise AssertionError('PARTIAL_INPUT_ACCEPTED_AS_COMPLETE')
record={'origin':'DEVELOPMENT_MODEL_INPUT_ONLY','request_sha256':summary['request_sha256'],'response_sha256':hashlib.sha256(raw).hexdigest(),'source_sha256':summary['source_sha256'],'request_measurement':measure_request(request,require_reference=True),'output_reference_tokens':output_tokens,'reference_count':sum(len(f['evidence']) for f in parsed['findings']),'findings':len(parsed['findings']),'unresolved':len(parsed['unresolved']),'scope_current_involvement':parsed['scope_current_involvement'],'owner_unit_count':len(payload['responsibility_unit_ids']),'provided_unit_count':len(units),'full_source_unit_count':len(source['units']),'complete_input_contract_refusal':complete_contract_refusal,'semantic_correctness_verified':False,'candidate_review_result_run_created':False,'business_calls':[0,0,0],'seconds':round(time.monotonic()-start,3)}
(HERE/'checked-time.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k!='request_measurement'}))
