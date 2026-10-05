"""Saved processing input replay only; no new source/Result or model call."""
import json,sys,socket,time
from pathlib import Path
from unittest.mock import patch
r=Path('/workspace/work/recorded-d04-restored/d04-reference-5207290213/data')
sys.path[:0]=[str(r/'scripts'),str(r)]
from vnext.requirements import load_requirement_snapshot
from vnext.capacity_assessment_input import load_registered_input
from vnext.canonical import strict_json_file
start=time.monotonic()
record=strict_json_file(path=r/'config/ordinary_going_concern_assessment.json')
sources=[]
for p in r.parent.glob('ledger/calls/*/source.json'):
 source=strict_json_file(path=p)
 if source.get('semantic_source_id')==record['source_id']:sources.append(source)
assert sources and all(s==sources[0] for s in sources)
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
 requirement=load_requirement_snapshot(snapshot_dir=r/'requirements/issue_28_v14')
 accepted=load_registered_input(data_root=r,source=sources[0],requirement=requirement,mode=record['mode'],input_record_id=record['input_record_id'])
report={'status':'SAVED_PROCESSING_INPUT_REPLAYED','company_id':accepted['company_id'],'metric_id':'D04','mode':accepted['mode'],'input_record_id':accepted['input_record_id'],'source_id':accepted['source_id'],'requirement_closure_hash':accepted['requirement_closure_hash'],'native_requests':len(accepted['native_requests']),'seconds':time.monotonic()-start,'new_business_calls':[0,0,0],'new_source_package_metric_completed':False,'result_used':False}
print(json.dumps(report,indent=2))
