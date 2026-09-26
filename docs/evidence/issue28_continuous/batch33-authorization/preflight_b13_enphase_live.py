"""Read-only final-binding B13 V3 Enphase six-group preflight."""
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.capacity_reference_contract import restore_base_request
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
assert before['counts'] == [139, 139, 49] and len(before['rows']) == 188
assert before['stopped_channels'] == []
expected = [row for row in groups_for(batch)
            if row['metric_id'] == 'B13' and row['company_id'] == 'enphase_energy']
assert len(expected) == 6 and [row['group_index'] for row in expected] == list(range(6))
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
     patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
     patch.object(control, 'effective_invocation_policy',
                  side_effect=AssertionError('NO_LEGACY')), \
     request_construction_session(requirement):
    prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                reference_context=True, program_quantity_roles=True)
    selected, report = select_native_request_variants(prepared_requests=prepared,
        ledger=ledger, source_references=True, compact_references=True,
        semantic_role_labels=True)
assert len(selected) == len(prepared) == 6
assert all(row['original_ordinal'] is None for row in report)
source = json.loads(prepared[0].source_bytes)
requests = [json.loads(item.request_bytes) for item in selected]
originals = [json.loads(item.request_bytes) for item in prepared]
assert all(a['units'] == b['units'] and
           a['required_candidate_assessments'] == b['required_candidate_assessments']
           for a, b in zip(requests, originals))
measured = [measure_request(item.provider_request_body_bytes,
                            require_reference=True) for item in selected]
plans = [build_plan(item) for item in selected]
assert all(value['fits'] and value['output_reserve_tokens'] == 4096
           for value in measured)
digests = [request_digest(request, policy) for request, (policy, _) in
           zip(requests, plans)]
assert all(row['initial_request_digest'] == digest and
           row['source_id'] == request['source_id'] == source['semantic_source_id']
           for row, digest, request in zip(expected, digests, requests))
old_groups = {}
for ordinal in (111, 170):
    path = ledger.root/'calls'/('%04d' % ordinal)
    old = json.loads((path/'semantic-request.json').read_text())
    base_id = restore_base_request(old)['request_id']
    indices = [index for index, request in enumerate(requests)
               if request['source_reference_contract']['base_request_id'] == base_id]
    assert len(indices) == 1
    old_groups[str(ordinal)] = indices[0]
assert old_groups == {'111': 0, '170': 1}
with ledger.locked():
    after = ledger.snapshot()
assert after['counts'] == before['counts'] and len(after['rows']) == 188
summary = {'record_type':'ISSUE28_B13_ENPHASE_V3_CURRENT_LIVE_LEDGER_PREFLIGHT',
           'status':'PASS_CURRENT_SIX_GROUP_SOURCE_COVERAGE_IDENTITY_AND_RESOURCES',
           'requirement_closure_hash':requirement['requirement_closure_hash'],
           'source_id':source['semantic_source_id'],
           'group_count':6,
           'all_source_units_and_required_assessments_preserved':True,
           'all_request_digests_match_authorized_manifest':True,
           'all_contexts_fit':True,
           'maximum_input_tokens':max(value['input_tokens'] for value in measured),
           'output_reserve_tokens':4096,
           'historical_group_indices':old_groups,
           'request_digests':digests,
           'prior_successes_reused':False,
           'network_disabled_during_source_construction':True,
           'new_calls':[0,0,0],
           'ledger_counts':after['counts'],
           'complete_company_result':False}
(evidence/'b13-enphase-current-preflight.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='request_digests'}))
