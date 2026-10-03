from dataclasses import replace
from pathlib import Path
from vnext.canonical import strict_json_loads, sha256_bytes
from vnext.capacity_reference_contract import upgrade_request
from vnext.continuous_call_policy import configured_transport_policy
from vnext.continuous_semantic_calls import prepare_requests, request_body, _source_json, _json
from vnext.native_assessment_replay import replay_native_response
from vnext.normal_source_authority import ROOT
path=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0190')
prepared=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)[0]
original=strict_json_loads(text=prepared.request_bytes.decode())
request=upgrade_request(original,compact=True,role_labels=True,relevance_scope=True)
policy=configured_transport_policy(requirement=prepared.requirement,repo_root=ROOT)
selected=replace(prepared,request_bytes=_source_json(request),provider_request_body_bytes=request_body(request,policy),output_schema_bytes=_json(request['response_protocol']))
assert path.joinpath('source.json').read_bytes()==selected.source_bytes, 'source bytes differ'
assert path.joinpath('semantic-request.json').read_bytes()==selected.request_bytes, 'request bytes differ'
replay=replay_native_response(prepared=selected,path=path)
receipt=replay['success']['acceptance_receipt']
print({'status':'CURRENT_READ_ONLY_190_REPLAY_PASS','request_id':request['request_id'],'source_sha256':sha256_bytes(content=selected.source_bytes),'original_acceptance_receipt_id':receipt['acceptance_receipt_id'],'revalidation_id':replay['revalidation']['revalidation_id'],'original_ordinal':190,'new_provider_calls':0})
