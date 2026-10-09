"""Read-only Enphase B13 V3 census for the explicitly authorized 33-group batch."""
import json
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_call_policy import configured_transport_policy
from vnext.continuous_request_context import measure_request
from vnext.continuous_semantic_calls import prepare_requests, request_digest, select_native_request_variants
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext import invocation_control as control

e = Path(__file__).resolve().parent
calls = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls')
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
policy = configured_transport_policy(requirement=requirement, repo_root=ROOT)
with tempfile.TemporaryDirectory(prefix='issue28-enphase-v3-') as temporary:
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy', side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                    reference_context=True, program_quantity_roles=True)
        selected, report = select_native_request_variants(prepared_requests=prepared,
            ledger=recorded_ledger(root=Path(temporary)/'selection'),
            source_references=True, compact_references=True, semantic_role_labels=True)
    source = json.loads(prepared[0].source_bytes)
    requests = [json.loads(item.request_bytes) for item in selected]
    originals = [json.loads(item.request_bytes) for item in prepared]
    assert all(a['units'] == b['units'] and
               a['required_candidate_assessments'] == b['required_candidate_assessments']
               for a, b in zip(requests, originals))
    assert all(row['original_ordinal'] is None for row in report)
    measured = [measure_request(item.provider_request_body_bytes, require_reference=True)
                for item in selected]
    assert all(value['fits'] and value['output_reserve_tokens'] == 4096 for value in measured)
    from vnext.capacity_reference_contract import restore_base_request
    old_groups = {}
    for ordinal in (111, 170):
        original = json.loads((calls/('%04d' % ordinal)/'semantic-request.json').read_text())
        base_id = restore_base_request(original)['request_id']
        matches = [i for i, request in enumerate(requests)
                   if request['source_reference_contract']['base_request_id'] == base_id]
        assert len(matches) == 1
        index = matches[0]
        old_groups[str(ordinal)] = {
            'current_group_index': index,
            'new_v3_digest_differs_from_original': request_digest(requests[index], policy) !=
                json.loads((calls/('%04d' % ordinal)/'intent.json').read_text())['request_digest'],
        }
    assert old_groups['111']['current_group_index'] != old_groups['170']['current_group_index']
    summary = {
        'status': 'ENPHASE_B13_V3_COMPLETE_REQUEST_CENSUS_OFFLINE_ONLY',
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'company_id': 'enphase_energy',
        'metric_id': 'B13',
        'source_id': source['semantic_source_id'],
        'group_count': len(requests),
        'all_source_units_and_required_assessments_preserved': True,
        'all_contexts_fit': True,
        'maximum_input_tokens': max(value['input_tokens'] for value in measured),
        'output_reserve_tokens': 4096,
        'original_111_and_170_group_mapping': old_groups,
        'request_digests': [request_digest(request, policy) for request in requests],
        'network_disabled': True,
        'new_calls': [0, 0, 0],
        'complete_company_result': False,
    }
    assert len(requests) == 6 and len(set(summary['request_digests'])) == 6
(e/'enphase-v3-request-census.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps({k: value for k, value in summary.items() if k != 'request_digests'}))
