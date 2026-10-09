"""Bounded offline V3 census; archived failures keep their original status."""
import json
import socket
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vnext.capacity_reference_contract import ROLE_LABELS, ROLE_VERSION, restore_base_request, restore_response
from vnext.capacity_semantic_review import validate_response
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_request_context import _load_tokenizer, measure_request
from vnext.continuous_semantic_calls import (execute_capacity_assessment, prepare_requests,
                                             request_digest, select_native_request_variants)
from vnext.native_request_construction import request_construction_session
from vnext.native_unit_index import validate_request_partition
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext import invocation_control as control


evidence = Path(__file__).resolve().parent
calls = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls')
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
old111 = json.loads((calls/'0111/semantic-request.json').read_text())
old170 = json.loads((calls/'0170/semantic-request.json').read_text())
assert restore_base_request(old111)['request_id'] == old111['source_reference_contract']['base_request_id']
assert restore_base_request(old170)['request_id'] == old170['source_reference_contract']['base_request_id']

with tempfile.TemporaryDirectory(prefix='issue28-role-v3-') as root:
    ledger = recorded_ledger(root=Path(root)/'selection')
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy', side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                    reference_context=True, program_quantity_roles=True)
        default, _ = select_native_request_variants(prepared_requests=prepared, ledger=ledger,
                                                      source_references=True)
        candidate, report = select_native_request_variants(prepared_requests=prepared, ledger=ledger,
                                                             source_references=True, compact_references=True,
                                                             semantic_role_labels=True)
    assert default[0].request_bytes == (calls/'0111/semantic-request.json').read_bytes()
    source = json.loads(prepared[0].source_bytes)
    requests = [json.loads(item.request_bytes) for item in candidate]
    originals = [json.loads(item.request_bytes) for item in prepared]
    assert validate_request_partition(source, requests) == [ROLE_VERSION]*len(requests)
    assert all(item['units'] == original['units'] and
               item['required_candidate_assessments'] == original['required_candidate_assessments']
               for item, original in zip(requests, originals))
    assert all(row['original_ordinal'] is None for row in report)
    try:
        execute_capacity_assessment(prepared=candidate[0], ledger=SimpleNamespace(live=True))
        raise AssertionError('V3 live candidate reached a claim path')
    except ValueError as error:
        assert str(error) == 'B13_ROLE_V3_LIVE_VALIDATION_NOT_AUTHORIZED', str(error)
    measured = [measure_request(item.provider_request_body_bytes, require_reference=True)
                for item in candidate]
    assert all(item['fits'] and item['output_reserve_tokens'] == 4096 for item in measured)
    old170_base_id = old170['source_reference_contract']['base_request_id']
    index = next(i for i, item in enumerate(requests)
                 if item['source_reference_contract']['base_request_id'] == old170_base_id)

old170_wire = json.loads((calls/'0170/wire/assistant-output.bin').read_text())
books = old170['response_protocol']['classification_codebooks']
reverse = {kind: label for label, kind in ROLE_LABELS.items()}
for row in old170_wire['findings']:
    row[0] = reverse[books['kind'][row[0]]]
tokenizer, fallback = _load_tokenizer()
assert tokenizer is not None, fallback
converted_tokens = len(tokenizer.encode(json.dumps(old170_wire, ensure_ascii=False,
                                                   separators=(',', ':')), add_special_tokens=False).ids)
assert converted_tokens <= 4096
try:
    restore_response(request=requests[index], raw_response=json.dumps(old170_wire).encode())
    raise AssertionError('Original170 duplicate response gained success credit')
except ValueError as error:
    assert str(error) == 'B13_REFERENCE_DUPLICATE_FINDING', str(error)

checked111 = validate_response(request=old111,
                               raw_response=(calls/'0111/wire/assistant-output.bin').read_bytes(),
                               source=json.loads((calls/'0111/source.json').read_text()))
assert checked111['unresolved']
policy = SimpleNamespace(model='deepseek-flash')
assert request_digest(requests[index], policy) != request_digest(old170, policy)
summary = {
    'status': 'OFFLINE_V3_REQUEST_CANDIDATE_VERIFIED_NO_MODEL_ACCURACY_CREDIT',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'candidate_version': ROLE_VERSION,
    'source_id': source['semantic_source_id'],
    'complete_request_groups': len(requests),
    'all_groups_role_v3': True,
    'source_units_and_required_assessments_identical_to_base': True,
    'default_first_request_equals_original111': True,
    'selected_prior_successes': 0,
    'live_v3_preclaim_guard': 'B13_ROLE_V3_LIVE_VALIDATION_NOT_AUTHORIZED',
    'all_contexts_fit': True,
    'maximum_input_tokens': max(item['input_tokens'] for item in measured),
    'output_reserve_tokens': 4096,
    'original170_group_input_tokens': measured[index]['input_tokens'],
    'original170_all110_wrong_and_duplicate_rows_with_role_labels_tokens': converted_tokens,
    'original170_still_rejected': 'B13_REFERENCE_DUPLICATE_FINDING',
    'original111_current_unresolved_count': len(checked111['unresolved']),
    'request_digest_materially_changed': True,
    'historical_terminal_mutated': False,
    'network_disabled': True,
    'new_real_calls': [0, 0, 0],
    'model_accuracy_or_complete_company_proven': False,
}
(evidence/'offline-candidate-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
