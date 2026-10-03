"""Current D04 factory/controller through a recorded batch resume, no live call."""
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
from vnext.continuous_batch33 import recorded_authorization, validate_history
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import (build_plan, execute_d04_assessment,
                                             prepare_requests, request_digest,
                                             select_native_request_variants)
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
    return ledger.finish_provider(path=path, intent=intent,
                                  execution=execution, wire=wire)


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
groups = deepcopy(json.loads((evidence/'initial-group-set.json').read_text())['groups'])
# Test ordinals are deliberately short; the real server-bound manifest still
# points to original114. This recorded ledger proves the same-digest mechanism.
groups[0]['historical_ordinal'] = 1
with tempfile.TemporaryDirectory(prefix='issue28-batch33-offline-wiring-') as temporary:
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
    with ledger.locked():
        failed_path, failed_intent = ledger.claim(channel='PROVIDER',
            request_digest=request_digest(request, policy),
            requirement=requirement, plan_id=content_hash(value='recorded old114 plan'),
            purpose='remaining_development_feasibility')
        control._exclusive_write_bytes(path=failed_path/'semantic-request.json',
                                       content=candidate.request_bytes)
        control._exclusive_write_bytes(path=failed_path/'source.json',
                                       content=candidate.source_bytes)
        failed_terminal = fail_recorded(ledger, failed_path, failed_intent,
                                        label='old114-content-failure', error='')
        path, intent = ledger.claim(channel='PROVIDER',
            request_digest=content_hash(value='recorded Ford171 stop'),
            requirement=requirement, plan_id=content_hash(value='recorded old171 plan'),
            purpose='remaining_development_feasibility')
        old_terminal = fail_recorded(ledger, path, intent,
                                     label='old171-HTTP402', error='HTTP_402')
        authorization = recorded_authorization(ledger=ledger, groups=groups,
                                               original_stop_ordinal=2)
        assert ledger.snapshot()['stopped_channels'] == ['PROVIDER']
    old_hashes = {str(item): hashlib.sha256(item.read_bytes()).hexdigest()
                  for old in (failed_path, path) for item in old.rglob('*') if item.is_file()}
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        selected, report = select_native_request_variants(prepared_requests=prepared,
            ledger=ledger)
        assert len(selected) == 6 and all(x['original_ordinal'] is None for x in report)
        candidate = selected[0]
        request = json.loads(candidate.request_bytes)
        assert request['metric_id'] == 'D04'
        answer = recorded_response(request)
        response = evidence_json_bytes({'id': 'batch33-recorded-d04', 'model': 'deepseek-flash',
            'choices': [{'message': {'role': 'assistant',
                                    'content': json.dumps(answer, ensure_ascii=False)},
                         'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                      'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})
        policy, plan = build_plan(candidate)
        class Reply(io.BytesIO):
            headers = {'x-request-id': 'batch33-recorded-d04'}
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
        assert snapshot['counts'] == [3, 3, 0]
        assert snapshot['stopped_channels'] == []
    assert old_hashes == {str(item): hashlib.sha256(item.read_bytes()).hexdigest()
                          for old in (failed_path, path) for item in old.rglob('*') if item.is_file()}
    new_intent = json.loads((new_path/'intent.json').read_text())
    assert new_intent['batch_authorization_id'] == authorization['authorization_id']
    assert new_intent['batch_group_id'] == 'D04:enphase_energy:0'
    assert new_intent['batch_resume_171'] is True
    assessment = collect_native_assessments(prepared_requests=selected, ledger=ledger)
    assert len(assessment['completed']) == 1 and len(assessment['missing_request_ids']) == 5
    assert assessment['failed_requests'] == []
    assert assessment['recovered_batch_failed_ordinals'] == [1]
    assert assessment['batch_history']['authorization']['authorization_id'] == authorization['authorization_id']
    native_row = {'ordinal': int(new_path.name), 'intent': new_intent,
                  'terminal': result['terminal']}
    assert validate_history(history=assessment['batch_history'], mode='RECORDED_TEST_ONLY',
        native_rows=[native_row],
        request_digests={int(new_path.name): request_digest(request, policy)},
        recovered_failed_ordinals=[1])
    summary = {'status': 'PASS_RECORDED_BATCH33_D04_FIRST_GROUP_FACTORY_CONTROLLER',
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'recorded_old_stop_status': old_terminal['status'],
        'recorded_old_stop_reason': old_terminal['stop_reason'],
        'recorded_old_same_digest_failure_status': failed_terminal['status'],
        'recorded_old_same_digest_failure_ordinal': 1,
        'recorded_old_stop_bytes_unchanged': True,
        'new_recorded_claim_group': new_intent['batch_group_id'],
        'new_recorded_claim_consumed_resume': True,
        'new_recorded_terminal': result['terminal']['status'],
        'new_recorded_native_candidate': True,
        'partial_native_collection_completed_requests': 1,
        'partial_native_collection_missing_requests': 5,
        'batch_claim_prefix_cold_validated': True,
        'old_same_digest_failure_excluded_only_after_new_success': True,
        'restart_cold_snapshot_counts': snapshot['counts'],
        'restart_cold_snapshot_stopped_channels': snapshot['stopped_channels'],
        'real_171_or_113_114_history_in_test_ledger': False,
        'network_disabled': True, 'new_real_calls': [0, 0, 0],
        'complete_company_result': False}
(evidence/'offline-wiring-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
