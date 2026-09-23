"""Recorded Enphase D04 old failure -> 402 -> separate recovery -> success.

Uses the current saved source and native controller, with all network disabled.
The test grant is not a live permission or model response.
"""
import hashlib
import io
import json
import os
import socket
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from vnext import ai_adapter as adapter, invocation_control as control
from vnext.canonical import content_hash
from vnext.continuous_batch33 import (recorded_authorization, validate_history)
from vnext.continuous_recovery_172 import recorded_authorization as recorded_recovery172
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import (build_plan, execute_d04_assessment,
    prepare_requests, request_digest, select_native_request_variants)
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.native_request_construction import request_construction_session
from vnext.native_unit_index import evidence_json_bytes
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from tests.vnext.test_d04_run_material import recorded_response


def seal(body, field):
    return {**body, field: content_hash(value=body)}


def fail_recorded(ledger, path, intent, *, label, error):
    execution_id = content_hash(value=['recorded execution', label])
    name = execution_id.split(':', 1)[1]
    execution = seal({'execution_id': execution_id, 'status': 'FAILED_TERMINAL',
        'counters': {'mock_transport_invocation_count': 1,
                     'real_model_provider_egress_count': 0,
                     'paid_model_provider_call_count': 0}}, 'execution_receipt_id')
    marker = seal({'ai_invocation_plan_id': intent['plan_id'],
        'execution_id': execution_id, 'attempt_ordinal': 1,
        'transport_kind': 'MOCK'}, 'egress_marker_id')
    wire = {'error_class': error, 'usage': {'input_tokens': 10, 'output_tokens': 1}}
    for relative, value in [('invocation_control/executions/'+name+'.json', execution),
                            ('invocation_control/egress/'+name+'/01.json', marker),
                            ('wire/journal.json', wire)]:
        control._exclusive_write_json(path=path/relative, value=value)
    return ledger.finish_provider(path=path, intent=intent, execution=execution, wire=wire)


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
row = deepcopy(json.loads((evidence/'initial-group-set.json').read_text())['groups'][0])
row['historical_ordinal'] = 1
with tempfile.TemporaryDirectory(prefix='issue28-recovery172-offline-') as temporary:
    ledger = recorded_ledger(root=Path(temporary)/'ledger')
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        prepared = prepare_requests(company_id='enphase_energy', metric_id='D04', native=True,
                                    reference_context=True, complete_response_contract=True)
        selected, _ = select_native_request_variants(prepared_requests=prepared, ledger=ledger)
    assert len(selected) == 6
    candidate = selected[0]
    request = json.loads(candidate.request_bytes)
    policy, plan = build_plan(candidate)
    digest = request_digest(request, policy)
    assert digest == row['initial_request_digest']
    with ledger.locked():
        old_path, old_intent = ledger.claim(channel='PROVIDER', request_digest=digest,
            requirement=requirement, plan_id=content_hash(value='recorded old114 plan'),
            purpose='remaining_development_feasibility')
        control._exclusive_write_bytes(path=old_path/'semantic-request.json',
                                       content=candidate.request_bytes)
        control._exclusive_write_bytes(path=old_path/'source.json',
                                       content=candidate.source_bytes)
        fail_recorded(ledger, old_path, old_intent, label='old114-content-failure', error='')
        stop_path, stop_intent = ledger.claim(channel='PROVIDER',
            request_digest=content_hash(value='recorded Ford171 stop'),
            requirement=requirement, plan_id=content_hash(value='recorded old171 plan'),
            purpose='remaining_development_feasibility')
        fail_recorded(ledger, stop_path, stop_intent, label='old171-HTTP402', error='HTTP_402')
        recorded_authorization(ledger=ledger, groups=[row], original_stop_ordinal=2)
        first_path, first_intent = ledger.claim(channel='PROVIDER', request_digest=digest,
            requirement=requirement, plan_id=plan['ai_invocation_plan_id'],
            purpose='remaining_development_feasibility',
            batch_group_id='D04:enphase_energy:0')
        control._exclusive_write_bytes(path=first_path/'semantic-request.json',
                                       content=candidate.request_bytes)
        control._exclusive_write_bytes(path=first_path/'source.json',
                                       content=candidate.source_bytes)
        first_terminal = fail_recorded(ledger, first_path, first_intent,
                                       label='first-batch-call-HTTP402', error='HTTP_402')
        assert ledger.snapshot()['stopped_channels'] == ['PROVIDER']
        recovery = recorded_recovery172(ledger=ledger, original_ordinal=3)
    frozen = {str(item): hashlib.sha256(item.read_bytes()).hexdigest()
              for old in (old_path, stop_path, first_path)
              for item in old.rglob('*') if item.is_file()}
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        selected, _ = select_native_request_variants(prepared_requests=prepared, ledger=ledger)
        answer = recorded_response(request)
        response = evidence_json_bytes({'id': 'recovery172-recorded-d04', 'model': 'deepseek-flash',
            'choices': [{'message': {'role': 'assistant',
                                    'content': json.dumps(answer, ensure_ascii=False)},
                         'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                      'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})
        class Reply(io.BytesIO):
            headers = {'x-request-id': 'recovery172-recorded-d04'}
        def opener(*, fullurl, timeout):
            assert fullurl.data == candidate.provider_request_body_bytes and timeout == 120
            return Reply(response)
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'offline-not-secret'}), \
             patch.object(adapter._DEEPSEEK_OPENER, 'open', side_effect=opener):
            adapter._build_repository_transport(policy=policy).complete(
                prepared_request=candidate,
                egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
        new_path, result = execute_d04_assessment(prepared=candidate, ledger=ledger,
                                                  recorded_wire=response)
    assert result['terminal']['status'] == 'SUCCEEDED'
    assert result['native_candidate_evidence_created'] is True
    with ledger.locked():
        snapshot = ledger.snapshot()
        assert snapshot['counts'] == [4, 4, 0] and snapshot['stopped_channels'] == []
    assert frozen == {str(item): hashlib.sha256(item.read_bytes()).hexdigest()
                      for old in (old_path, stop_path, first_path)
                      for item in old.rglob('*') if item.is_file()}
    new_intent = json.loads((new_path/'intent.json').read_text())
    assert new_intent['batch_attempt_index'] == 1
    assert new_intent['batch_recovery_172_id'] == recovery['authorization_id']
    assessment = collect_native_assessments(prepared_requests=selected, ledger=ledger)
    assert len(assessment['completed']) == 1 and len(assessment['missing_request_ids']) == 5
    assert assessment['failed_requests'] == []
    assert assessment['recovered_batch_failed_ordinals'] == [1]
    assert assessment['recovered_batch_http402_ordinals'] == [3]
    assert assessment['batch_history']['recovery_172']['authorization_id'] == recovery['authorization_id']
    assert validate_history(history=assessment['batch_history'], mode='RECORDED_TEST_ONLY',
        native_rows=[{'ordinal': 4, 'intent': new_intent, 'terminal': result['terminal']}],
        request_digests={4: digest}, recovered_failed_ordinals=[1],
        recovered_402_ordinals=[3])
    summary = {'status': 'PASS_RECORDED_RECOVERY172_D04_SAME_REQUEST_NATIVE_COLLECTION',
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'recorded_original_stop_ordinal': 2,
        'recorded_new_402_ordinal': 3,
        'recorded_recovery_success_ordinal': 4,
        'request_digest_unchanged': True,
        'all_prior_slot_bytes_unchanged': True,
        'failed_history_retained_but_not_current_credit': True,
        'native_completed_requests': 1,
        'native_missing_requests': 5,
        'network_disabled': True,
        'new_real_calls': [0, 0, 0],
        'complete_company_result': False,
        'live_recovery_authorized': False}
    (evidence/'recovery172-offline-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))
