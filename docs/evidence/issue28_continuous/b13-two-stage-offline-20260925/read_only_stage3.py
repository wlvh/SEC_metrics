"""Read-only current semantic revalidation of saved B13 V5 group-one judgment."""
from dataclasses import replace
from pathlib import Path
from vnext.canonical import strict_json_file, sha256_bytes
from vnext.continuous_call_policy import configured_transport_policy
from vnext.continuous_semantic_calls import prepare_requests, request_body, _source_json, _json
from vnext.native_assessment_replay import replay_native_response
from vnext.normal_source_authority import ROOT

path = Path('/tmp/sec_metrics_issue28_b13_two_stage_recorded_20260925_1/ledger/calls/0003')
base = prepare_requests(company_id='enphase_energy', metric_id='B13',
    reference_context=True, program_quantity_roles=True)[1]
request = strict_json_file(path=path/'semantic-request.json')
policy = configured_transport_policy(requirement=base.requirement, repo_root=ROOT)
prepared = replace(base, request_bytes=_source_json(request),
    provider_request_body_bytes=request_body(request, policy),
    output_schema_bytes=_json(request['response_protocol']))
assert prepared.source_bytes == (path/'source.json').read_bytes()
assert prepared.request_bytes == (path/'semantic-request.json').read_bytes()
replay = replay_native_response(prepared=prepared, path=path)
accepted = replay['success']['acceptance_receipt']
print({'status': 'CURRENT_V5_STAGE3_READ_ONLY_REPLAY_PASS',
    'requirement_closure_hash': prepared.requirement['requirement_closure_hash'],
    'request_id': request['request_id'],
    'source_sha256': sha256_bytes(content=prepared.source_bytes),
    'original_ordinal': 3,
    'original_acceptance_receipt_id': accepted['acceptance_receipt_id'],
    'current_revalidation_id': replay['revalidation']['revalidation_id'],
    'new_recorded_calls': 0, 'new_real_calls': [0, 0, 0]})
