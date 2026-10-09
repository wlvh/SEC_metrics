"""One recorded V4 repair through the real B13 factory/controller; no network."""
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
from vnext.capacity_reference_contract import upgrade_request
from vnext.continuous_batch33 import (recorded_authorization,
    history_for_current, validate_history)
from vnext.continuous_batch33_repair189 import recorded_authorization as recorded_repair
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import (build_plan, execute_capacity_assessment,
    prepare_requests, request_digest, select_native_request_variants)
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.native_request_construction import request_construction_session
from vnext.native_unit_index import evidence_json_bytes
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


def seal(body, key):
    return {**body, key: content_hash(value=body)}


def failed(ledger, path, intent, *, label, error, output_tokens):
    execution_id = content_hash(value=['recorded execution', label])
    name = execution_id.split(':', 1)[1]
    execution = seal({'execution_id': execution_id, 'status':'FAILED_TERMINAL',
        'counters':{'mock_transport_invocation_count':1,
                    'real_model_provider_egress_count':0,
                    'paid_model_provider_call_count':0}}, 'execution_receipt_id')
    marker = seal({'ai_invocation_plan_id':intent['plan_id'],
        'execution_id':execution_id,'attempt_ordinal':1,
        'transport_kind':'MOCK'}, 'egress_marker_id')
    wire = {'error_class':error,'usage':{'input_tokens':10,'output_tokens':output_tokens}}
    for relative, value in [('invocation_control/executions/'+name+'.json',execution),
                            ('invocation_control/egress/'+name+'/01.json',marker),
                            ('wire/journal.json',wire)]:
        control._exclusive_write_json(path=path/relative,value=value)
    return ledger.finish_provider(path=path,intent=intent,execution=execution,wire=wire)


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
original_path = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0189')
original = json.loads((original_path/'semantic-request.json').read_text())
raw = json.loads((original_path/'wire/raw-response.bin').read_text())
content = raw['choices'][0]['message']['content']
decoder = json.JSONDecoder()
units, _ = decoder.raw_decode(content[content.index('"units":') + len('"units":'):])
position = content.index('"findings":[') + len('"findings":[')
prefix = []
while position < len(content):
    while position < len(content) and content[position] in ' \t\r\n,':
        position += 1
    try:
        row, end = decoder.raw_decode(content, position)
    except json.JSONDecodeError:
        break
    if not isinstance(row, list):
        break
    prefix.append(row)
    position = end
required = {'B443','B454','B834','B1022'}
selected_rows = [row for row in prefix if any(ref in required for ref in row[3])]
assert len(selected_rows) == 4
source_rows = deepcopy(selected_rows)
assert len([row for row in source_rows if 'B1022' in row[3]
            and row[1] == 2]) == 1
for row in source_rows:
    if 'B1022' in row[3]:
        row[1] = 0  # Recorded positive only: first-person registrant source.
synthetic = {'units':units,'findings':source_rows}
with tempfile.TemporaryDirectory(prefix='issue28-b13-v4-recorded-') as temporary:
    ledger = recorded_ledger(root=Path(temporary)/'ledger')
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')), \
         patch.object(control,'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        prepared = prepare_requests(company_id='enphase_energy',metric_id='B13',
                                    reference_context=True,program_quantity_roles=True)
        selected, _ = select_native_request_variants(prepared_requests=prepared,
            ledger=ledger,source_references=True,compact_references=True,
            semantic_role_labels=True,relevance_repair_group_index=0)
    assert len(selected) == 6
    candidate = selected[0]
    new = json.loads(candidate.request_bytes)
    old = upgrade_request(json.loads(prepared[0].request_bytes),
                          compact=True,role_labels=True)
    assert old['units'] == original['units']
    assert old['required_candidate_assessments'] == original['required_candidate_assessments']
    policy, plan = build_plan(candidate)
    old_digest = request_digest(old, policy)
    new_digest = request_digest(new, policy)
    with ledger.locked():
        stop, stop_intent = ledger.claim(channel='PROVIDER',
            request_digest=content_hash(value='old provider stop'),
            requirement=requirement,plan_id=content_hash(value='old stop plan'),
            purpose='remaining_development_feasibility')
        failed(ledger,stop,stop_intent,label='old stop',error='HTTP_402',output_tokens=1)
        groups=[{'metric_id':'D04','company_id':'enphase_energy','group_index':0,
                 'initial_request_digest':content_hash(value='first d04'),
                 'source_id':content_hash(value='first source'),'historical_ordinal':None},
                {'metric_id':'B13','company_id':'enphase_energy','group_index':0,
                 'initial_request_digest':old_digest,'source_id':new['source_id'],
                 'historical_ordinal':None}]
        recorded_authorization(ledger=ledger,groups=groups,original_stop_ordinal=1)
        first, first_intent = ledger.claim(channel='PROVIDER',
            request_digest=groups[0]['initial_request_digest'],requirement=requirement,
            plan_id=content_hash(value='first d04 plan'),
            purpose='remaining_development_feasibility',batch_group_id='D04:enphase_energy:0')
        # The first recorded group is only a count/order control.
        completion_id = content_hash(value=['recorded execution','first d04'])
        name = completion_id.split(':',1)[1]
        execution = seal({'execution_id':completion_id,'status':'SUCCEEDED',
            'counters':{'mock_transport_invocation_count':1,
                        'real_model_provider_egress_count':0,
                        'paid_model_provider_call_count':0}},'execution_receipt_id')
        marker = seal({'ai_invocation_plan_id':first_intent['plan_id'],
            'execution_id':completion_id,'attempt_ordinal':1,'transport_kind':'MOCK'},
            'egress_marker_id')
        wire={'error_class':'','usage':{'input_tokens':10,'output_tokens':1}}
        for relative,value in [('invocation_control/executions/'+name+'.json',execution),
                               ('invocation_control/egress/'+name+'/01.json',marker),
                               ('wire/journal.json',wire)]:
            control._exclusive_write_json(path=first/relative,value=value)
        ledger.finish_provider(path=first,intent=first_intent,execution=execution,wire=wire)
        failed_path, failed_intent = ledger.claim(channel='PROVIDER',
            request_digest=old_digest,requirement=requirement,
            plan_id=content_hash(value='old v3 plan'),
            purpose='remaining_development_feasibility',batch_group_id='B13:enphase_energy:0')
        control._exclusive_write_bytes(path=failed_path/'wire/raw-response.bin',
            content=b'{"choices":[{"finish_reason":"length"}]}')
        control._exclusive_write_bytes(path=failed_path/'semantic-request.json',
                                       content=evidence_json_bytes(old))
        control._exclusive_write_bytes(path=failed_path/'source.json',
                                       content=candidate.source_bytes)
        original_failed = failed(ledger,failed_path,failed_intent,
            label='old v3 truncated',error='DEEPSEEK_RESPONSE_INVALID',output_tokens=4096)
        assert original_failed['status']=='FAILED_TERMINAL' and not original_failed['stop_reason']
        repair=recorded_repair(ledger=ledger,failed_ordinal=3,
                               repaired_digest=new_digest,source_id=new['source_id'])
    model_response = evidence_json_bytes({'id':'recorded-v4','model':'deepseek-flash',
        'choices':[{'message':{'role':'assistant',
            'content':json.dumps(synthetic,ensure_ascii=False)},'finish_reason':'stop'}],
        'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,
                 'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
    from vnext.capacity_native_assessment import build_acceptance
    from vnext.capacity_semantic_review import validate_response as check_response
    checked = check_response(request=json.loads(candidate.request_bytes),
        raw_response=json.dumps(synthetic,ensure_ascii=False).encode(),
        source=json.loads(candidate.source_bytes))
    print('DIRECT_CHECK_UNRESOLVED',json.dumps(checked['unresolved'],ensure_ascii=False)[:2000],flush=True)
    try:
        build_acceptance(prepared=candidate,plan=plan,
            response_body=json.dumps(synthetic,ensure_ascii=False).encode())
    except Exception as error:
        print('DIRECT_NATIVE_ACCEPTANCE_FAILURE',type(error).__name__,str(error),flush=True)
        raise
    class Reply(io.BytesIO):
        headers={'x-request-id':'recorded-v4'}
    def opener(*,fullurl,timeout):
        assert fullurl.data == candidate.provider_request_body_bytes and timeout == 120
        return Reply(model_response)
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')), \
         patch.object(control,'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-secret'}), \
         patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=opener), \
         request_construction_session(requirement):
        selected, _ = select_native_request_variants(prepared_requests=prepared,
            ledger=ledger,source_references=True,compact_references=True,
            semantic_role_labels=True,relevance_repair_group_index=0)
        candidate = selected[0]
        policy, plan = build_plan(candidate)
        assert request_digest(json.loads(candidate.request_bytes),policy) == new_digest
        adapter._build_repository_transport(policy=policy).complete(
            prepared_request=candidate,
            egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
        new_path, result = execute_capacity_assessment(prepared=candidate,
                                                        ledger=ledger,recorded_wire=model_response)
    if result['terminal']['status'] != 'SUCCEEDED':
        wire = json.loads((new_path/'wire/journal.json').read_text())
        print('RECORDED_FAILURE',result['terminal']['status'],
              wire.get('error_class'),wire.get('error_detail'),flush=True)
        print('ASSESSMENT',json.dumps(json.loads((new_path/'capacity-assessment.json').read_text()),
                                      ensure_ascii=False)[:2500],flush=True)
        for record in (new_path/'invocation_control/executions').glob('*.json'):
            data=json.loads(record.read_text())
            print('EXECUTION',json.dumps(data,ensure_ascii=False)[:2500],flush=True)
    assert result['terminal']['status']=='SUCCEEDED'
    assert result['native_candidate_evidence_created'] is True
    new_intent=json.loads((new_path/'intent.json').read_text())
    assert new_intent['batch_repair_189_id']==repair['authorization_id']
    assessment=collect_native_assessments(prepared_requests=selected,ledger=ledger)
    assert len(assessment['completed'])==1 and len(assessment['missing_request_ids'])==5
    assert assessment['recovered_batch_engineering_ordinals']==[3]
    assert assessment['failed_requests']==[]
    assert validate_history(history=assessment['batch_history'],mode='RECORDED_TEST_ONLY',
        native_rows=[{'ordinal':4,'intent':new_intent,'terminal':result['terminal']}],
        request_digests={4:new_digest},recovered_failed_ordinals=[],
        recovered_engineering_ordinals=[3])
    with ledger.locked():
        snapshot=ledger.snapshot()
        assert snapshot['counts']==[4,4,0] and snapshot['stopped_channels']==[]
    summary={'record_type':'ISSUE28_B13_189_V4_RECORDED_NATIVE_WIRING',
        'status':'PASS_RECORDED_ONE_REPAIR_FACTORY_CONTROLLER_AND_COLD_PREFIX',
        'requirement_closure_hash':requirement['requirement_closure_hash'],
        'recorded_failed_ordinal':3,'recorded_repair_ordinal':4,
        'old_v3_digest':old_digest,'new_v4_digest':new_digest,
        'source_units_and_required_assessments_preserved':True,
        'repaired_current_completed_groups':1,'missing_groups':5,
        'old_failure_retained_in_batch_history':True,
        'original_189_upgraded':False,
        'synthetic_B1022_subject_corrected_from_failed189':True,
        'real_model_accuracy_proven':False,
        'real_provider_or_sec_calls':[0,0,0],
        'new_live_repair_authority_installed':False,
        'complete_company_result':False}
    (evidence/'v4-recorded-wiring-summary.json').write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))
