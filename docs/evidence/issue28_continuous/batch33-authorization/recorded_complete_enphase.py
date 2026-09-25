"""One new recorded batch chain through Enphase D04 Run and cold read.

The real original171/114 slots and live provider channel are never opened.
"""
import json
import socket
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.canonical import content_hash
from vnext.capacity_assessment_input import register_assessment_input, load_registered_input
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.capacity_run import install_inputs
from vnext.continuous_batch33 import recorded_authorization
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import (execute_d04_assessment, prepare_requests,
                                             request_digest, select_native_request_variants)
from vnext.continuous_call_policy import configured_transport_policy
from vnext.native_request_construction import request_construction_session
from vnext.native_unit_index import evidence_json_bytes
from vnext.normal_run_v3 import create_normal_run
from vnext.normal_source_authority import ROOT
from vnext.ordinary_projection import render_ordinary_run
from vnext.requirements import load_requirement_snapshot
from vnext.run_store import _mechanically_replay_open_run
from tests.vnext.test_d04_run_material import recorded_response


def seal(body, field):
    return {**body, field: content_hash(value=body)}


def fail_recorded(ledger, path, intent, label, error):
    execution_id=content_hash(value=['recorded',label]);name=execution_id[7:]
    execution=seal({'execution_id':execution_id,'status':'FAILED_TERMINAL',
        'counters':{'mock_transport_invocation_count':1,
                    'real_model_provider_egress_count':0,
                    'paid_model_provider_call_count':0}},'execution_receipt_id')
    marker=seal({'ai_invocation_plan_id':intent['plan_id'],'execution_id':execution_id,
                 'attempt_ordinal':1,'transport_kind':'MOCK'},'egress_marker_id')
    wire={'error_class':error,'usage':{'input_tokens':10,'output_tokens':1}}
    for relative,value in [('invocation_control/executions/'+name+'.json',execution),
                           ('invocation_control/egress/'+name+'/01.json',marker),
                           ('wire/journal.json',wire)]:
        control._exclusive_write_json(path=path/relative,value=value)
    return ledger.finish_provider(path=path,intent=intent,execution=execution,wire=wire)


evidence=Path(__file__).resolve().parent
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
policy=configured_transport_policy(requirement=requirement,repo_root=ROOT)
groups=deepcopy(json.loads((evidence/'initial-group-set.json').read_text())['groups'])
groups[0]['historical_ordinal']=1
with tempfile.TemporaryDirectory(prefix='issue28-batch33-enphase-complete-') as temporary, \
     patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')), \
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')), \
     patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')), \
     patch.object(control,'effective_invocation_policy',side_effect=AssertionError('NO_LEGACY')), \
     request_construction_session(requirement):
    root=Path(temporary).resolve();ledger=recorded_ledger(root=root/'ledger')
    prepared=prepare_requests(company_id='enphase_energy',metric_id='D04',native=True,
                              reference_context=True,complete_response_contract=True)
    selected,_=select_native_request_variants(prepared_requests=prepared,ledger=ledger)
    assert len(selected)==6
    first=json.loads(selected[0].request_bytes)
    with ledger.locked():
        failed,intent=ledger.claim(channel='PROVIDER',request_digest=request_digest(first,policy),
            requirement=requirement,plan_id=content_hash(value='old114-plan'),
            purpose='remaining_development_feasibility')
        control._exclusive_write_bytes(path=failed/'semantic-request.json',content=selected[0].request_bytes)
        control._exclusive_write_bytes(path=failed/'source.json',content=selected[0].source_bytes)
        fail_recorded(ledger,failed,intent,'old114-content','')
        stopped,stop_intent=ledger.claim(channel='PROVIDER',
            request_digest=content_hash(value='Ford171-HTTP402'),requirement=requirement,
            plan_id=content_hash(value='old171-plan'),purpose='remaining_development_feasibility')
        fail_recorded(ledger,stopped,stop_intent,'old171-http402','HTTP_402')
        authorization=recorded_authorization(ledger=ledger,groups=groups,original_stop_ordinal=2)
    selected,_=select_native_request_variants(prepared_requests=prepared,ledger=ledger)
    terminals=[]
    for index,obj in enumerate(selected):
        request=json.loads(obj.request_bytes)
        answer=recorded_response(request)
        wire=evidence_json_bytes({'id':'batch33-enphase-recorded-'+str(index),'model':'deepseek-flash',
            'choices':[{'message':{'role':'assistant','content':json.dumps(answer,ensure_ascii=False)},
                        'finish_reason':'stop'}],
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,
                     'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
        path,result=execute_d04_assessment(prepared=obj,ledger=ledger,recorded_wire=wire)
        assert result['terminal']['status']=='SUCCEEDED', (index,result)
        new_intent=json.loads((path/'intent.json').read_text())
        assert new_intent['batch_authorization_id']==authorization['authorization_id']
        assert new_intent['batch_group_id']=='D04:enphase_energy:'+str(index)
        terminals.append(result['terminal']['terminal_id'])
        print('RECORDED_GROUP_PASS',index,flush=True)
    assessment=collect_native_assessments(prepared_requests=selected,ledger=ledger)
    assert assessment['all_source_requests_accepted'] and not assessment['failed_requests']
    assert assessment['recovered_batch_failed_ordinals']==[1]
    (root/'journal').mkdir()
    with patch('vnext.capacity_assessment_input._journal',return_value=root/'journal'):
        registered=register_assessment_input(prepared_requests=selected,ledger=ledger)
        source=json.loads(prepared[0].source_bytes)
        data,run=root/'data',root/'run'
        install_inputs(data_root=data,company_id='enphase_energy',assessment_mode='RECORDED_TEST_ONLY',
            assessment_input_id=registered['input_record_id'],metric_id='D04',
            request_context_format=source.get('request_context_format'),
            complete_response_contract=bool(source.get('response_contract_version')))
        loaded=load_registered_input(data_root=data,source=source,requirement=requirement,
                                      mode='RECORDED_TEST_ONLY')
        assert loaded['input_record_id']==registered['input_record_id']
        created=create_normal_run(data_root=data,run_dir=run,company_id='enphase_energy',metric_id='D04')
        _mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
        rendered=render_ordinary_run(data_root=data,run_dir=run)
    with ledger.locked():
        snapshot=ledger.snapshot()
        assert snapshot['counts']==[8,8,0] and snapshot['stopped_channels']==[]
    summary={'status':'PASS_RECORDED_BATCH33_ENPHASE_D04_COMPLETE_RUN_AND_COLD_READ',
        'requirement_closure_hash':requirement['requirement_closure_hash'],
        'recorded_groups':6,'recorded_terminal_ids':terminals,
        'old_same_digest_failed_ordinal':1,'old_http402_stopped_ordinal':2,
        'recovered_batch_failed_ordinals':assessment['recovered_batch_failed_ordinals'],
        'native_input_id':registered['input_record_id'],
        'run_id':created['manifest']['run_id'],'result_id':created['result']['result_id'],
        'public_row_status':rendered['row']['status'],'public_row_value':rendered['row']['value'],
        'cold_read':'PASS_IN_PROCESS_MECHANICAL_REPLAY','test_ledger_counts':snapshot['counts'],
        'test_ledger_stopped_channels':snapshot['stopped_channels'],
        'network_disabled':True,'real_calls':[0,0,0],
        'real_company_result_credit':False,'production_authorized':False}
(evidence/'recorded-complete-enphase-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
