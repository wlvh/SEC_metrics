"""No-call source and context census for the remaining Enphase B13 V4 groups."""
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
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
ledger = live_ledger(requirement=requirement)
with ledger.locked():
    before = ledger.snapshot()
    batch = read_authorization(ledger)
assert before['counts'] == [142, 142, 49] and len(before['rows']) == 191
assert before['stopped_channels'] == []
expected = [row for row in groups_for(batch)
            if row['metric_id'] == 'B13' and row['company_id'] == 'enphase_energy']
assert len(expected) == 6
rows = []
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
     patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
     patch.object(control, 'effective_invocation_policy',
                  side_effect=AssertionError('NO_LEGACY')), \
     request_construction_session(requirement):
    base = prepare_requests(company_id='enphase_energy', metric_id='B13',
                            reference_context=True, program_quantity_roles=True)
    assert len(base) == 6
    originals = [json.loads(item.request_bytes) for item in base]
    for index in range(1, 6):
        selected, report = select_native_request_variants(
            prepared_requests=base, ledger=ledger, source_references=True,
            compact_references=True, semantic_role_labels=True,
            relevance_repair_group_index=index)
        request = json.loads(selected[index].request_bytes)
        assert request['source_reference_contract']['version'] == RELEVANCE_VERSION
        assert request['source_id'] == expected[index]['source_id']
        assert request['units'] == originals[index]['units']
        assert request['required_candidate_assessments'] == \
            originals[index]['required_candidate_assessments']
        assert report[0]['original_ordinal'] == 190
        assert report[index]['original_ordinal'] is None
        measurement = measure_request(selected[index].provider_request_body_bytes,
                                      require_reference=True)
        assert measurement['fits'] and measurement['output_reserve_tokens'] == 4096
        policy, _ = build_plan(selected[index])
        rows.append({
            'group_index': index,
            'group_id': 'B13:enphase_energy:' + str(index),
            'source_id': request['source_id'],
            'v3_digest': expected[index]['initial_request_digest'],
            'v4_digest': request_digest(request, policy),
            'source_unit_count': len(request['units']),
            'required_candidate_count': len(request['required_candidate_assessments']),
            'input_tokens': measurement['input_tokens'],
            'output_reserve_tokens': measurement['output_reserve_tokens']})
with ledger.locked():
    after = ledger.snapshot()
assert after['counts'] == before['counts'] and len(after['rows']) == 191
summary = {
    'record_type': 'ISSUE28_B13_191_ENPHASE_V4_NO_CALL_PREFLIGHT',
    'status': 'PASS_GROUPS_1_TO_5_SOURCE_REQUIRED_AND_CONTEXT_PRESERVED',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'groups': rows,
    'network_disabled_during_preflight': True,
    'new_calls': [0, 0, 0],
    'original_191_upgraded': False,
    'future_model_accuracy_proven': False,
}
(evidence / 'preflight-summary.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': summary['status'],
                  'groups': [(row['group_index'], row['v4_digest'],
                              row['input_tokens'], row['required_candidate_count'])
                             for row in rows], 'new_calls': summary['new_calls']}))
