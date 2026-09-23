"""Read-only current D04 request identity check for an unapproved milestone."""
import json
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_call_policy import configured_transport_policy
from vnext.continuous_semantic_calls import prepare_requests, request_digest, select_native_request_variants
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext import invocation_control as control


evidence = Path(__file__).resolve().parent
calls = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls')
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
policy = configured_transport_policy(requirement=requirement, repo_root=ROOT)
result = {}
with tempfile.TemporaryDirectory(prefix='issue28-d04-authorization-read-') as tmp:
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy', side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        for ordinal, company in [(113, 'paramount_skydance_paramount_global'),
                                 (114, 'enphase_energy')]:
            prepared = prepare_requests(company_id=company, metric_id='D04', native=True,
                                        reference_context=True, complete_response_contract=True)
            selected, report = select_native_request_variants(
                prepared_requests=prepared,
                ledger=recorded_ledger(root=Path(tmp)/company))
            old = calls/('%04d' % ordinal)
            intent = json.loads((old/'intent.json').read_text())
            terminal = json.loads((old/'terminal.json').read_text())
            matches = [i for i, item in enumerate(selected)
                       if request_digest(json.loads(item.request_bytes), policy) == intent['request_digest']]
            assert len(matches) == 1, (company, matches)
            index = matches[0]
            request = json.loads(selected[index].request_bytes)
            assert request['metric_id'] == 'D04' and request['company_id'] == company
            assert terminal['status'] == 'FAILED_TERMINAL' and not terminal['stop_reason']
            assert all(row['original_ordinal'] is None for row in report)
            result[company] = {
                'original_failed_ordinal': ordinal,
                'original_intent_id': intent['intent_id'],
                'original_terminal_id': terminal['terminal_id'],
                'original_request_digest': intent['request_digest'],
                'current_matching_group_index': index,
                'current_group_count': len(selected),
                'current_matching_request_id': request['request_id'],
                'current_request_digest_equals_failed_digest': True,
                'current_matching_group_units': len(request['units']),
                'current_matching_group_required_candidates': len(request['required_candidate_assessments']),
                'current_matching_group_has_original_greek_question_mark': b'\xcd\xbe' in selected[index].provider_request_body_bytes,
                'current_group_request_digests': [request_digest(json.loads(item.request_bytes), policy)
                                                  for item in selected],
                'fresh_success_credit': False,
            }
assert sum(value['current_group_count'] for value in result.values()) == 16
summary = {
    'status': 'CURRENT_D04_TWO_COMPANIES_IDENTIFIED_NO_AUTHORIZATION_OR_CALL',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'companies': result,
    'group_count': 16,
    'network_disabled': True,
    'original_failures_mutated': False,
    'new_real_calls': [0, 0, 0],
}
(evidence/'current-request-identity.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
