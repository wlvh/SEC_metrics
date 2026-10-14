"""Small original-call fixtures; no real model answer or business result credit."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest

from tests.vnext.test_capacity_semantic_review import source_packet
from vnext.canonical import content_hash, sha256_bytes
from vnext.continuous_semantic_calls import request_body, request_digest
from vnext.d04_native_assessment import native_source, requests_from_source, build_acceptance
from vnext.current_d04_result import require_complete_assessment
from vnext.request_limits import RequestLimits
from vnext.saved_d04_replay import read_saved_d04_assessment


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def sealed(value, field):
    return {**value, field: content_hash(value=value)}


def fixture(*, nonempty=False, continuous=False, retry_count=0, output_tokens=4096):
    source = source_packet()
    source.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04')
    if nonempty:
        from vnext.r6_semantic_source import _seal_unit
        unit=source['units'][0];payload=deepcopy(unit['payload'])
        payload['blocks'][0]['text']='There is substantial doubt about our ability to continue as a going concern.'
        unit=_seal_unit(unit['document_id'],'VISIBLE_TEXT',payload,0)
        source.update(units=[unit],required_unit_ids=[unit['unit_id']])
    annual = source['prepared_annual_input']
    annual.update(company_id=source['company_id'], filing={'accessionNumber': 'annual'})
    annual['table_input']['target_period'] = {
        'fiscal_year': 2025, 'period_start': '2025-01-01', 'period_end': '2025-12-31'}
    source['documents'][0].update(language_candidate_block_indices=[7] if nonempty else [], native_candidate_ordinals=[],
        source_reference={'source_reference_id':'sha256:'+'3'*64})
    source['semantic_source_id'] = content_hash(value={k: v for k, v in source.items() if k != 'semantic_source_id'})
    source = native_source(source, complete_response_contract=True)
    request = requests_from_source(source)[0]
    limits=RequestLimits(output_tokens=output_tokens)
    wire = request_body(request, SimpleNamespace(model='deepseek-flash'),limits=limits)
    key = content_hash(value={'provider_request_body_sha256':sha256_bytes(content=wire),
        'provider':'deepseek','model':'deepseek-flash','api':'chat_completions'})
    binding = sealed({'record_type': ('CONTINUOUS_CALL_ALLOWANCE' if continuous
                                     else 'ISSUE_47_HISTORICAL_MODEL_ALLOWANCE'),
        'limits': [35,35,0], 'purposes': ['synthetic-original-input-control'],
        'execution_mode': 'RECORDED_TEST_ONLY'}, 'binding_id')
    plan = sealed({'requirement_id': 'synthetic-old-requirement',
        'requirement_closure_hash': 'sha256:' + '9' * 64,
        'source_identity_hash': source['semantic_source_id'],
        'selected_representation_hash': request['request_id'],
        'output_schema_hash': content_hash(value=request['response_protocol']),
        'provider_request_body_sha256': sha256_bytes(content=wire),
        'provider_request_identity': key, 'provider':'deepseek',
        'model': 'deepseek-flash', 'api':'chat_completions',
        'task_contract_hash': content_hash(value={'task': 'synthetic-d04'}),
        **({'invocation_policy':{'automatic_retry_count':retry_count,
                                'response_reuse_authorized':False}} if continuous else {})}, 'ai_invocation_plan_id')
    response = encoded({'request_id':request['request_id'], 'units':[
        {'unit_id': u['unit_id'], 'reviewed':True, 'unresolved':[], 'findings':([
            {'kind':'DOUBT_DISCLOSED','subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT',
             'evidence':[{'kind':'VISIBLE_BLOCK','source_index':7}],
             'reason':'Constructed current source explicitly discloses substantial doubt.'}]
            if nonempty else [])}
        for u in request['units']]})
    draft = build_acceptance(prepared=SimpleNamespace(source_bytes=encoded(source),
        request_bytes=encoded(request)), plan=plan, response_body=response)
    accepted = sealed({'schema_version':1, 'record_type':'INVOCATION_ACCEPTANCE_RECEIPT',
        'ai_invocation_plan_id':plan['ai_invocation_plan_id'],
        'provider_request_identity':key, 'response_body_sha256':sha256_bytes(content=response),
        **draft}, 'acceptance_receipt_id')
    success = sealed({'ai_invocation_plan_id':plan['ai_invocation_plan_id'],
        'provider_request_identity':key, 'provider_request_body_sha256':sha256_bytes(content=wire),
        'response_body_sha256':sha256_bytes(content=response), 'response_body_size':len(response),
        'acceptance_receipt_id':accepted['acceptance_receipt_id'],
        'usage':{'actual_cost':None,'input_tokens':None,'output_tokens':None}},
        'success_response_receipt_id')
    intent = sealed({'record_type':('CONTINUOUS_CALL_INTENT' if continuous
                                     else 'ISSUE_47_HISTORICAL_MODEL_CALL_INTENT'),
        'ordinal':20,
        **({'binding_id':binding['binding_id'],'channel':'PROVIDER',
            'requirement_closure_hash':plan['requirement_closure_hash']} if continuous else
           {'allowance_binding_id':binding['binding_id'],'automatic_retry_count':0}),
        'purpose':'synthetic-original-input-control',
        'execution_mode':'RECORDED_TEST_ONLY', 'plan_id':plan['ai_invocation_plan_id'],
        'requirement_id':plan['requirement_id'],
        **({} if continuous else {'request_identity':key}),
        'request_digest':(request_digest(request, SimpleNamespace(model='deepseek-flash'),limits=limits)
                          if continuous else 'sha256:'+sha256_bytes(content=wire))}, 'intent_id')
    root = 'root/calls/0020'
    files = {'root/binding.json':encoded(binding), root+'/source.json':encoded(source),
        root+'/semantic-request.json':encoded(request), root+'/intent.json':encoded(intent),
        root+'/invocation_control/plans/'+plan['ai_invocation_plan_id'][7:]+'.json':encoded(plan),
        root+'/invocation_control/requests/'+key[7:]+'.bin':wire,
        root+'/invocation_control/responses/'+key[7:]+'/response.bin':response,
        root+'/invocation_control/responses/'+key[7:]+'/receipt.json':encoded(success),
        root+'/invocation_control/acceptances/'+key[7:]+'/receipt.json':encoded(accepted)}
    execution=sealed({'ai_invocation_plan_id':plan['ai_invocation_plan_id'],
        'provider_request_identity':key,'status':'SUCCEEDED',
        'success_response_receipt_id':success['success_response_receipt_id']},
        'execution_receipt_id')
    files[root+'/invocation_control/executions/original.json']=encoded(execution)
    terminal = sealed({'record_type':('CONTINUOUS_CALL_TERMINAL' if continuous
                                       else 'ISSUE_47_HISTORICAL_MODEL_CALL_TERMINAL'),
        'intent_id':intent['intent_id'], 'status':'SUCCEEDED','stop_reason':'',
        'counts':[0,0,0], 'execution_receipt_id':execution['execution_receipt_id'],
        'evidence':{name[len(root)+1:]:sha256_bytes(content=raw)
            for name,raw in files.items() if name.startswith(root+'/')}}, 'terminal_id')
    files[root+'/terminal.json'] = encoded(terminal)
    return files, source, [{'ordinal':20,'source_member':root+'/source.json',
                           'request_member':root+'/semantic-request.json'}]


def continuous_fixture(*, nonempty=False, retry_count=0, output_tokens=4096):
    """Construct the existing #28 artifact profile; never relabel a real call."""
    return fixture(nonempty=nonempty,continuous=True,retry_count=retry_count,output_tokens=output_tokens)


def write_package(path, files, duplicate=None):
    with tarfile.open(path, 'w:gz') as out:
        for name, raw in files.items():
            member=tarfile.TarInfo(name);member.size=len(raw);out.addfile(member,io.BytesIO(raw))
        if duplicate:
            raw=files[duplicate];member=tarfile.TarInfo(duplicate);member.size=len(raw);out.addfile(member,io.BytesIO(raw))


class SavedD04ReplayTest(unittest.TestCase):
    def replay(self, files=None, source=None, calls=None, duplicate=None):
        defaults=fixture()
        files=defaults[0] if files is None else files
        source=defaults[1] if source is None else source
        calls=defaults[2] if calls is None else calls
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'original.tar.gz';write_package(path,files,duplicate)
            return read_saved_d04_assessment(saved_call_package=path, original_source=source,
                original_call_members=calls,prepared_annual_input=source['prepared_annual_input'])

    def test_original_group_rechecks_without_media_or_call_credit(self):
        got=self.replay()
        self.assertEqual(len(got['completed']),1)
        self.assertEqual(got['new_calls'],{'provider':0,'paid':0,'sec':0})
        self.assertFalse(got['filing_media_coverage_verified'])
        self.assertIsNone(got['completed'][0]['original_usage']['input_tokens'])
        with self.assertRaisesRegex(ValueError,'COMPLETE_SAVED_RESPONSE_SET'):
            require_complete_assessment(got)

    def test_missing_or_duplicate_call_or_member_rejected(self):
        files,source,calls=fixture()
        with self.assertRaisesRegex(ValueError,'DUPLICATE_OR_INVALID_ORDINAL'):
            self.replay(files,source,calls+calls)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_PACKAGE_MEMBER'):
            self.replay(files,source,calls,duplicate=calls[0]['source_member'])
        files.pop('root/calls/0020/intent.json')
        with self.assertRaises(ValueError):self.replay(files,source,calls)

    def test_failed_terminal_cannot_become_empty_findings(self):
        files,source,calls=fixture();name='root/calls/0020/terminal.json'
        term=json.loads(files[name]);term.pop('terminal_id');term['status']='FAILED_TERMINAL'
        files[name]=encoded(sealed(term,'terminal_id'))
        with self.assertRaisesRegex(ValueError,'NOT_SUCCESSFUL'):self.replay(files,source,calls)

    def test_wrong_year_is_not_selected_success(self):
        files,source,calls=fixture();selected=deepcopy(source['prepared_annual_input'])
        selected['table_input']['target_period']['fiscal_year']=2024
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'original.tar.gz';write_package(path,files)
            with self.assertRaisesRegex(ValueError,'SELECTED_COORDINATE_CHANGED'):
                read_saved_d04_assessment(saved_call_package=path,original_source=source,
                    original_call_members=calls,prepared_annual_input=selected)

    def test_changed_original_answer_or_wire_rejected(self):
        for part in ['/response.bin','.bin']:
            files,source,calls=fixture()
            name=next(n for n in files if '/responses/' in n and n.endswith(part)) if part=='/response.bin' else next(n for n in files if '/requests/' in n)
            files[name]+=b'changed'
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'CALL_BYTES_CHANGED'):
                self.replay(files,source,calls)


class ContinuousSavedD04ReplayTest(unittest.TestCase):
    replay = SavedD04ReplayTest.replay
    def test_continuous_and_historical_nonempty_profiles_preserve_their_origins(self):
        for make in (fixture,continuous_fixture):
            with self.subTest(profile=make.__name__):
                files,source,calls=make(nonempty=True)
                before=dict(files);result=self.replay(files,source,calls)
                binding=json.loads(files['root/binding.json'])
                self.assertEqual(binding,result['original_allowance_binding'])
                self.assertEqual(1,len(result['source_findings']))
                self.assertEqual('DOUBT_DISCLOSED',result['source_findings'][0]['kind'])
                self.assertEqual([0,0,0],result['completed'][0]['original_counts'])
                self.assertIsNone(result['completed'][0]['original_usage']['input_tokens'])
                self.assertEqual({'provider':0,'paid':0,'sec':0},result['new_calls'])
                self.assertFalse(result['filing_media_coverage_verified'])
                self.assertFalse(result['metric_result_created'])
                self.assertEqual(before,files)

    def test_continuous_binding_cannot_consume_a_historical_terminal(self):
        files,source,calls=continuous_fixture();name='root/calls/0020/terminal.json'
        value=json.loads(files[name]);value.pop('terminal_id')
        value['record_type']='ISSUE_47_HISTORICAL_MODEL_CALL_TERMINAL'
        files[name]=encoded(sealed(value,'terminal_id'))
        with self.assertRaisesRegex(ValueError,'NOT_SUCCESSFUL'):
            self.replay(files,source,calls)

    def test_original_output_budget_is_not_replaced_by_current_default(self):
        files,source,calls=continuous_fixture(nonempty=True,output_tokens=2048)
        result=self.replay(files,source,calls)
        self.assertEqual(1,len(result['source_findings']))
        self.assertEqual({'provider':0,'paid':0,'sec':0},result['new_calls'])
        self.assertFalse(result['metric_result_created'])

    def test_continuous_retry_policy_is_read_from_the_original_plan(self):
        for count in (1,None):
            files,source,calls=continuous_fixture(retry_count=count)
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'PLAN_BINDING_CHANGED'):
                self.replay(files,source,calls)

    def test_continuous_channel_and_original_requirement_must_match(self):
        for field,value in [('channel','SEC'),('requirement_closure_hash','wrong'),('request_digest','wrong')]:
            files,source,calls=continuous_fixture();name='root/calls/0020/intent.json'
            intent=json.loads(files[name]);intent.pop('intent_id');intent[field]=value
            intent=sealed(intent,'intent_id');files[name]=encoded(intent)
            name='root/calls/0020/terminal.json';terminal=json.loads(files[name]);terminal.pop('terminal_id')
            terminal['intent_id']=intent['intent_id'];terminal['evidence']['intent.json']=sha256_bytes(content=encoded(intent))
            files[name]=encoded(sealed(terminal,'terminal_id'))
            with self.subTest(field=field),self.assertRaises(ValueError):self.replay(files,source,calls)

if __name__=='__main__':unittest.main()
