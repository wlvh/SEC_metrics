"""No-call census for a one-group B13 relevance-scope repair candidate."""
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.capacity_reference_contract import RELEVANCE_VERSION, ROLE_VERSION
from vnext.continuous_batch33 import groups_for, read_authorization
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_request_context import measure_request
from vnext.continuous_semantic_calls import (build_plan, prepare_requests,
    request_digest, select_native_request_variants)
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
ledger = live_ledger(requirement=requirement)
with ledger.locked():
    before = ledger.snapshot()
    batch = read_authorization(ledger)
assert before['counts'] == [140, 140, 49] and len(before['rows']) == 189
assert before['stopped_channels'] == []
expected = [row for row in groups_for(batch)
            if row['metric_id'] == 'B13' and row['company_id'] == 'enphase_energy']
assert len(expected) == 6
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
     patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
     patch.object(control, 'effective_invocation_policy',
                  side_effect=AssertionError('NO_LEGACY')), \
     request_construction_session(requirement):
    base = prepare_requests(company_id='enphase_energy', metric_id='B13',
                            reference_context=True, program_quantity_roles=True)
    selected, report = select_native_request_variants(prepared_requests=base,
        ledger=ledger, source_references=True, compact_references=True,
        semantic_role_labels=True, relevance_repair_group_index=0)
assert len(selected) == len(base) == 6
assert all(row['original_ordinal'] is None for row in report)
requests = [json.loads(item.request_bytes) for item in selected]
originals = [json.loads(item.request_bytes) for item in base]
assert all(a['units'] == b['units'] and
           a['required_candidate_assessments'] == b['required_candidate_assessments']
           for a, b in zip(requests, originals))
assert requests[0]['source_reference_contract']['version'] == RELEVANCE_VERSION
assert all(request['source_reference_contract']['version'] == ROLE_VERSION
           for request in requests[1:])
measurements = [measure_request(item.provider_request_body_bytes,
                                require_reference=True) for item in selected]
plans = [build_plan(item) for item in selected]
assert all(item['fits'] and item['output_reserve_tokens'] == 4096
           for item in measurements)
digests = [request_digest(request, policy) for request, (policy, _) in
           zip(requests, plans)]
assert digests[0] != expected[0]['initial_request_digest']
assert all(digest == row['initial_request_digest']
           for digest, row in zip(digests[1:], expected[1:]))
assert all(request['source_id'] == expected[index]['source_id']
           for index, request in enumerate(requests))
with ledger.locked():
    after = ledger.snapshot()
assert after['counts'] == before['counts'] and len(after['rows']) == 189
summary = {'record_type':'ISSUE28_B13_189_V4_ONE_GROUP_REPAIR_CENSUS',
           'status':'PASS_ONE_GROUP_V4_SOURCE_PRESERVED_AND_CONTEXT_FITS',
           'requirement_closure_hash':requirement['requirement_closure_hash'],
           'source_id':requests[0]['source_id'],
           'repair_group_id':'B13:enphase_energy:0',
           'failed_ordinal':189,
           'old_v3_digest':expected[0]['initial_request_digest'],
           'new_v4_digest':digests[0],
           'unchanged_other_five_digests':digests[1:],
           'all_source_units_and_required_assessments_preserved':True,
           'group_count':6,
           'group0_required_candidate_count':len(requests[0]['required_candidate_assessments']),
           'group0_source_unit_count':len(requests[0]['units']),
           'group0_input_tokens':measurements[0]['input_tokens'],
           'maximum_input_tokens':max(item['input_tokens'] for item in measurements),
           'output_reserve_tokens':4096,
           'resource_limit':200000,
           'network_disabled_during_preflight':True,
           'new_calls':[0,0,0],
           'live_repair_authorized':False,
           'original_189_upgraded':False}
(evidence/'v4-preflight-summary.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ('status','new_v4_digest','group0_input_tokens',
    'maximum_input_tokens','output_reserve_tokens','new_calls')}))
