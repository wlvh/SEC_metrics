"""Exercise V4 group1 through real factory/controller with a recorded response."""
import json
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.canonical import content_hash, sha256_file
from vnext.continuous_batch33 import (recorded_authorization, group_id,
    history_for_current, validate_history)
from vnext.continuous_batch33_repair189 import recorded_authorization as recorded_repair189
from vnext.continuous_call_ledger import recorded_ledger
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.continuous_semantic_calls import (build_plan, execute_capacity_assessment,
    prepare_requests, request_digest, select_native_request_variants)
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


def seal(body, key):
    return {**body, key: content_hash(value=body)}


def finish(ledger, path, intent, *, status, error, output_tokens):
    identity = content_hash(value=['recorded group1 wiring', intent['ordinal']])
    name = identity.split(':', 1)[1]
    execution = seal({'execution_id':identity, 'status':status,
        'counters':{'mock_transport_invocation_count':1,
                    'real_model_provider_egress_count':0,
                    'paid_model_provider_call_count':0}}, 'execution_receipt_id')
    marker = seal({'ai_invocation_plan_id':intent['plan_id'],
                   'execution_id':identity, 'attempt_ordinal':1,
                   'transport_kind':'MOCK'}, 'egress_marker_id')
    wire = {'error_class':error,
            'usage':{'input_tokens':10, 'output_tokens':output_tokens}}
    for relative, value in (
            ('invocation_control/executions/' + name + '.json', execution),
            ('invocation_control/egress/' + name + '/01.json', marker),
            ('wire/journal.json', wire)):
        control._exclusive_write_json(path=path / relative, value=value)
    return ledger.finish_provider(path=path, intent=intent,
                                  execution=execution, wire=wire)


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
with tempfile.TemporaryDirectory(prefix='issue28-b13-v4-group1-recorded-') as temporary:
    ledger = recorded_ledger(root=Path(temporary) / 'ledger')
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        original = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                    reference_context=True, program_quantity_roles=True)
        selected, report = select_native_request_variants(
            prepared_requests=original, ledger=ledger, source_references=True,
            compact_references=True, semantic_role_labels=True,
            relevance_repair_group_index=1)
    item = selected[1]
    request = json.loads(item.request_bytes)
    assert len(request['units']) == 4 and request['required_candidate_assessments'] == []
    policy, plan = build_plan(item)
    repaired_digest = request_digest(request, policy)
    preflight = json.loads((evidence / 'preflight-summary.json').read_text())
    assert repaired_digest == preflight['groups'][0]['v4_digest']
    groups = [
        {'metric_id':'D04', 'company_id':'enphase_energy', 'group_index':0,
         'initial_request_digest':content_hash(value='recorded d04'),
         'source_id':content_hash(value='recorded d04 source'), 'historical_ordinal':None},
        {'metric_id':'B13', 'company_id':'enphase_energy', 'group_index':0,
         'initial_request_digest':content_hash(value='recorded old group0'),
         'source_id':request['source_id'], 'historical_ordinal':None},
        {'metric_id':'B13', 'company_id':'enphase_energy', 'group_index':1,
         'initial_request_digest':preflight['groups'][0]['v3_digest'],
         'source_id':request['source_id'], 'historical_ordinal':None},
    ]
    groups.extend({'metric_id':'B13', 'company_id':'enphase_energy',
                   'group_index':row['group_index'],
                   'initial_request_digest':row['v3_digest'],
                   'source_id':row['source_id'], 'historical_ordinal':None}
                  for row in preflight['groups'][1:])
    with ledger.locked():
        path, intent = ledger.claim(channel='PROVIDER',
            request_digest=content_hash(value='recorded prior stop'),
            requirement=requirement, plan_id=content_hash(value='stop plan'),
            purpose='remaining_development_feasibility')
        finish(ledger, path, intent, status='FAILED_TERMINAL',
               error='HTTP_402', output_tokens=1)
        batch = recorded_authorization(ledger=ledger, groups=groups,
                                       original_stop_ordinal=1)
        path, intent = ledger.claim(channel='PROVIDER',
            request_digest=groups[0]['initial_request_digest'],
            requirement=requirement, plan_id=content_hash(value='d04 plan'),
            purpose='remaining_development_feasibility',
            batch_group_id=group_id(groups[0]))
        finish(ledger, path, intent, status='SUCCEEDED', error='', output_tokens=1)
        path, intent = ledger.claim(channel='PROVIDER',
            request_digest=groups[1]['initial_request_digest'],
            requirement=requirement, plan_id=content_hash(value='old group0 plan'),
            purpose='remaining_development_feasibility',
            batch_group_id=group_id(groups[1]))
        control._exclusive_write_bytes(path=path / 'wire/raw-response.bin',
            content=b'{"choices":[{"finish_reason":"length"}]}')
        finish(ledger, path, intent, status='FAILED_TERMINAL',
               error='DEEPSEEK_RESPONSE_INVALID', output_tokens=4096)
        old_repair = recorded_repair189(ledger=ledger, failed_ordinal=3,
            repaired_digest=content_hash(value='recorded group0 V4'),
            source_id=request['source_id'])
        path, intent = ledger.claim(channel='PROVIDER',
            request_digest=old_repair['repaired_request_digest'],
            requirement=requirement, plan_id=content_hash(value='new group0 plan'),
            purpose='remaining_development_feasibility',
            batch_group_id=group_id(groups[1]), batch_repair_receipt=old_repair)
        old_success_intent = intent
        old_success_terminal = finish(ledger, path, intent, status='SUCCEEDED',
                                      error='', output_tokens=1)
        path, intent = ledger.claim(channel='PROVIDER',
            request_digest=groups[2]['initial_request_digest'],
            requirement=requirement, plan_id=content_hash(value='old group1 plan'),
            purpose='remaining_development_feasibility',
            batch_group_id=group_id(groups[2]))
        control._exclusive_write_bytes(path=path / 'wire/raw-response.bin',
            content=b'{"choices":[{"finish_reason":"length"}]}')
        old_group1_intent = intent
        old_group1_terminal = finish(ledger, path, intent, status='FAILED_TERMINAL',
                                     error='DEEPSEEK_RESPONSE_INVALID', output_tokens=4096)
        successor = preflight['groups']
        body = {
            'record_type':'CONTINUOUS_BATCH33_B13_ENPHASE_V4_AUTHORIZATION',
            'execution_mode':'RECORDED_TEST_ONLY', 'budget_root':str(ledger.root),
            'binding_id':ledger.binding['binding_id'],
            'batch_authorization_id':batch['authorization_id'],
            'prior_repair_189_id':old_repair['authorization_id'],
            'prior_success_190_intent_id':old_success_intent['intent_id'],
            'prior_success_190_terminal_id':old_success_terminal['terminal_id'],
            'failed_group_id':group_id(groups[2]), 'failed_ordinal':5,
            'failed_intent_id':old_group1_intent['intent_id'],
            'failed_terminal_id':old_group1_terminal['terminal_id'],
            'failed_v3_digest':old_group1_intent['request_digest'],
            'failed_raw_response_sha256':sha256_file(path=path / 'wire/raw-response.bin'),
            'successor_groups':successor,
            'base_groups_without_prior_attempt':[2, 3, 4, 5],
            'maximum_repair_executions_for_group1':1,
            'maximum_new_executions':5,
        }
        cohort = {**body, 'authorization_id':content_hash(value=body)}
        control._exclusive_write_json(path=ledger.root/'batch33-b13-v4-enphase.json',
                                      value=cohort)
    synthetic = {'units':[{'unit_index':index, 'reviewed':True,
                           'unresolved':[], 'calculation_limits':[]}
                          for index in range(4)], 'findings':[]}
    model_response = json.dumps({
        'id':'recorded-group1-v4','model':'deepseek-flash',
        'choices':[{'message':{'role':'assistant',
            'content':json.dumps(synthetic)}, 'finish_reason':'stop'}],
        'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,
                 'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}},
        ensure_ascii=False).encode()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        call_path, result = execute_capacity_assessment(prepared=item, ledger=ledger,
                                                        recorded_wire=model_response)
    assert result['terminal']['status'] == 'SUCCEEDED'
    assert result['native_candidate_evidence_created'] is True
    new_intent = json.loads((call_path / 'intent.json').read_text())
    assert new_intent['batch_attempt_index'] == 1
    assert new_intent['batch_repair_191_id'] == cohort['authorization_id']
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        selected2, report2 = select_native_request_variants(
            prepared_requests=original, ledger=ledger, source_references=True,
            compact_references=True, semantic_role_labels=True,
            relevance_repair_group_index=2)
        item2 = selected2[2]
        request2 = json.loads(item2.request_bytes)
        assert report2[1]['original_ordinal'] == 6
        assert request2['required_candidate_assessments'] == []
        assert request_digest(request2, build_plan(item2)[0]) == successor[1]['v4_digest']
        synthetic2 = {'units':[{'unit_index':index, 'reviewed':True,
            'unresolved':[], 'calculation_limits':[]}
            for index in range(len(request2['units']))], 'findings':[]}
        model_response2 = json.dumps({
            'id':'recorded-group2-v4','model':'deepseek-flash',
            'choices':[{'message':{'role':'assistant',
                'content':json.dumps(synthetic2)}, 'finish_reason':'stop'}],
            'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,
                     'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}}).encode()
        call_path2, result2 = execute_capacity_assessment(
            prepared=item2, ledger=ledger, recorded_wire=model_response2)
    assert result2['terminal']['status'] == 'SUCCEEDED'
    intent2 = json.loads((call_path2 / 'intent.json').read_text())
    assert intent2['batch_attempt_index'] == 0
    assert intent2['batch_b13_v4_id'] == cohort['authorization_id']
    assert 'batch_repair_191_id' not in intent2
    collected = collect_native_assessments(prepared_requests=selected2, ledger=ledger)
    assert len(collected['completed']) == 2
    assert len(collected['missing_request_ids']) == 4
    assert collected['failed_requests'] == []
    assert collected['recovered_batch_engineering_ordinals'] == [5]
    with ledger.locked():
        state = ledger.snapshot()
        history = history_for_current(ledger=ledger)
    assert state['counts'] == [7, 7, 0] and not state['stopped_channels']
    assert validate_history(history=history, mode='RECORDED_TEST_ONLY',
        native_rows=[{'ordinal':6, 'intent':new_intent,
                      'terminal':result['terminal']},
                     {'ordinal':7, 'intent':intent2,
                      'terminal':result2['terminal']}],
        request_digests={6:repaired_digest,7:successor[1]['v4_digest']},
        recovered_failed_ordinals=[],
        recovered_engineering_ordinals=[5])
    summary = {
        'record_type':'ISSUE28_B13_191_V4_RECORDED_FACTORY_CONTROLLER',
        'status':'PASS_ONE_REPAIR_FACTORY_CONTROLLER_AND_COLD_PREFIX',
        'requirement_closure_hash':requirement['requirement_closure_hash'],
        'recorded_failed_ordinal':5, 'recorded_repair_ordinal':6,
        'recorded_unopened_base_ordinal':7,
        'v4_group1_digest':repaired_digest,
        'v4_group2_digest':successor[1]['v4_digest'],
        'old_failure_retained':True, 'candidate_created_from_synthetic_response':True,
        'recorded_current_completed_groups':2,
        'real_model_accuracy_proven':False, 'real_calls':[0, 0, 0],
    }
    (evidence/'recorded-factory-summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary))
