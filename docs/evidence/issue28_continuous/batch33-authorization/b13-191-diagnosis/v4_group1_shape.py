"""Check a synthetic complete group1 V4 response without any model call."""
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.capacity_native_assessment import build_acceptance
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import (build_plan, prepare_requests,
    select_native_request_variants)
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
ledger = live_ledger(requirement=requirement)
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
     patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
     patch.object(control, 'effective_invocation_policy',
                  side_effect=AssertionError('NO_LEGACY')), \
     request_construction_session(requirement):
    prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                reference_context=True, program_quantity_roles=True)
    selected, _ = select_native_request_variants(
        prepared_requests=prepared, ledger=ledger, source_references=True,
        compact_references=True, semantic_role_labels=True,
        relevance_repair_group_index=1)
    item = selected[1]
    request = json.loads(item.request_bytes)
    assert len(request['units']) == 4
    assert request['required_candidate_assessments'] == []
    response = {'units': [{'unit_index': index, 'reviewed': True,
                           'unresolved': [], 'calculation_limits': []}
                          for index in range(4)], 'findings': []}
    _, plan = build_plan(item)
    acceptance = build_acceptance(prepared=item, plan=plan,
                                  response_body=json.dumps(response).encode())
summary = {
    'record_type': 'ISSUE28_B13_191_V4_SYNTHETIC_COMPLETE_SHAPE',
    'status': 'PASS_SYNTHETIC_EMPTY_FINDINGS_ORIGINAL_SOURCE_ACCEPTED',
    'source_unit_count': 4, 'required_candidate_count': 0,
    'synthetic_candidate_hash': acceptance['candidate_hash'],
    'real_model_accuracy_proven': False,
    'original_191_upgraded': False,
    'new_calls': [0, 0, 0],
}
(evidence / 'v4-shape-summary.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary))
