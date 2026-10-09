"""Saved source through actual WB-3/transport; only HTTP is recorded.

Synthetic responses test mechanics, not model interpretation or new company
results. Every ledger is isolated; real business sockets are prohibited.
"""
from contextlib import ExitStack
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import continuous_semantic_calls as calls, ai_adapter, invocation_control
from vnext.canonical import strict_json_file, strict_json_loads
from vnext.continuous_call_ledger import recorded_ledger
from vnext.current_request_configuration import live_scope
from vnext.request_limits import RequestLimits


class CurrentConfigurationTest(unittest.TestCase):
    def test_retired_proof_fields_are_not_current_processing_dependencies(self):
        from vnext import current_request_configuration as config
        actual=config.load_current_configuration(repo_root=REPO_ROOT)
        read=config.strict_json_file
        def changed(*,path):
            value=read(path=path)
            if path.name=='issue28_continuous_calls_v1.json':
                value={**value,'rule_paths':['removed-historical-rule'],
                    'requirement_id':'historical-only','offline_wiring_receipt_path':'changed-old-receipt'}
            return value
        with patch.object(config,'strict_json_file',side_effect=changed):
            after=config.load_current_configuration(repo_root=REPO_ROOT)
        self.assertEqual(actual,after)

    def test_real_transport_configuration_change_is_detected(self):
        from vnext import current_request_configuration as config
        actual=config.load_current_configuration(repo_root=REPO_ROOT)
        read=config.strict_json_file
        def changed(*,path):
            value=read(path=path)
            if path.name=='issue28_current_request_runtime_v1.json':
                value={**value,'transport':{**value['transport'],'timeout_seconds':119}}
            return value
        with patch.object(config,'strict_json_file',side_effect=changed):
            after=config.load_current_configuration(repo_root=REPO_ROOT)
            self.assertNotEqual(actual['configuration_hash'],after['configuration_hash'])
            with self.assertRaisesRegex(ValueError,'CONFIGURATION_CHANGED'):
                config.transport_policy(configuration=actual,repo_root=REPO_ROOT)


class Response(io.BytesIO):
    headers = {'x-request-id': 'RECORDED-HTTP-TEST'}


class CurrentVariantLimitsTest(unittest.TestCase):
    def test_real_variant_selection_keeps_body_and_transport_limits(self):
        from tests.vnext.test_native_request_variants import synthetic_source
        from vnext.current_request_configuration import load_current_configuration,transport_policy
        source,_=synthetic_source()
        configuration=load_current_configuration(repo_root=REPO_ROOT)
        limits=RequestLimits(output_tokens=8192,max_payload_bytes=4*1024*1024)
        policy=transport_policy(configuration=configuration,repo_root=REPO_ROOT,limits=limits)
        context=invocation_control.prepare_current_invocation_context(repo_root=REPO_ROOT,
            configuration=configuration,transport=policy,limits=limits)
        raw=calls._source_json(source)
        prepared=[calls.SemanticRequest(calls._FACTORY,raw,calls._source_json(r),
            calls.request_body(r,policy,limits=limits),calls._json(r['response_protocol']),
            configuration,context,limits=limits) for r in calls.source_requests(source)]
        with tempfile.TemporaryDirectory() as directory:
            ledger=recorded_ledger(root=Path(directory).resolve()/'ledger')
            selected,report=calls.select_native_request_variants(prepared_requests=prepared,ledger=ledger)
            # Constructed selector-state fixture only. No HTTP/acceptance or
            # business credit; exercise the already-successful variant branch.
            with ledger.locked():
                item=selected[0]
                request=strict_json_loads(text=item.request_bytes.decode())
                path,intent=ledger.claim(channel='PROVIDER',request_digest=calls.request_digest(
                    request,policy,limits=limits),requirement=configuration,
                    plan_id=invocation_control.content_hash(value='constructed-selector-plan'),
                    purpose='remaining_development_feasibility')
                (path/'semantic-request.json').write_bytes(item.request_bytes)
                body={'intent_id':intent['intent_id'],'status':'SUCCEEDED','stop_reason':'',
                      'counts':[1,1,0],'evidence':{}}
                (path/'terminal.json').write_text(json.dumps({**body,
                    'terminal_id':invocation_control.content_hash(value=body)}))
            with patch('vnext.native_assessment_replay.replay_native_response',
                       return_value={'revalidation':{'constructed_selector_fixture':True}}) as replay:
                retained,receipt=calls.select_native_request_variants(prepared_requests=prepared,ledger=ledger)
            self.assertEqual(receipt[0]['original_ordinal'],1)
            checked=replay.call_args.kwargs['prepared']
            self.assertEqual(json.loads(checked.provider_request_body_bytes)['max_tokens'],8192)
            self.assertEqual(calls._prepared_transport_policy(checked).maximum_payload_bytes,4*1024*1024)
        self.assertEqual(len(selected),3)
        for item in selected:
            request=strict_json_loads(text=item.request_bytes.decode())
            self.assertEqual(json.loads(item.provider_request_body_bytes)['max_tokens'],8192)
            self.assertEqual(calls._prepared_transport_policy(item).maximum_payload_bytes,4*1024*1024)
            self.assertEqual(item.provider_request_body_bytes,calls.request_body(request,policy,limits=limits))
        self.assertTrue(all(row['original_ordinal'] is None for row in report))


class CurrentRequestRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(calls, 'load_requirement_snapshot', side_effect=AssertionError('No Requirement ancestry')):
            cls.requests = calls.prepare_requests(company_id='enphase_energy', metric_id='D04')
        # This recorded group is a mechanical empty-response control. The full
        # source/task census remains in every object; no company absence claim.
        cls.prepared = next(p for p in cls.requests if not strict_json_loads(
            text=p.request_bytes.decode())['required_candidate_assessments'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()/'ledger'
        self.ledger = recorded_ledger(root=self.root)
        self.http_bodies = []
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('No network')))
        self.stack.enter_context(patch.object(socket.socket,'connect_ex',side_effect=AssertionError('No network')))
        self.stack.enter_context(patch.object(socket,'create_connection',side_effect=AssertionError('No network')))
        self.stack.enter_context(patch.dict(os.environ,{'DEEPSEEK_API_KEY':'SYNTHETIC-NONBUSINESS-TEST-KEY'}))

    def wire(self, *, prepared=None, usage=True, finish='stop'):
        prepared = prepared or self.prepared
        request = strict_json_loads(text=prepared.request_bytes.decode())
        answer = {'request_id':request['request_id'], 'units':[
            {'unit_id':u['unit_id'],'reviewed':True,'findings':[],'unresolved':[]}
            for u in request['units']]}
        raw = {'id':'RECORDED-TEST-RESPONSE','model':'deepseek-flash','choices':[
            {'finish_reason':finish,'message':{'role':'assistant','content':json.dumps(answer)}}]}
        if usage:
            _,plan=calls.build_plan(prepared)
            count=plan['observability']['estimated_context_tokens']-prepared.limits.output_tokens
            raw['usage']={'prompt_tokens':count,'completion_tokens':5,'total_tokens':count+5}
        return json.dumps(raw).encode()

    def http(self, wire=None, error=None):
        def open_request(**kwargs):
            request=kwargs['request']
            self.assertEqual(request.full_url,'https://api.deepseek.com/chat/completions')
            self.assertEqual(request.get_method(),'POST')
            self.assertEqual(request.get_header('Authorization'),'Bearer RECORDED-NO-CREDENTIAL')
            self.http_bodies.append(request.data)
            if kwargs.get('before_socket_open'):kwargs['before_socket_open']()
            if error:raise error
            return Response(wire)
        return ai_adapter.recorded_provider_http(open_request)

    def execute(self, *, prepared=None, wire=None, error=None):
        with self.http(wire=wire if wire is not None else self.wire(prepared=prepared),error=error):
            return calls.execute_feasibility(prepared=prepared or self.prepared,ledger=self.ledger)

    def test_real_preparation_transport_usage_save_and_restart_read(self):
        with patch.object(calls,'load_requirement_snapshot',side_effect=AssertionError('No old proof')), \
             patch.object(invocation_control,'load_requirement_snapshot',side_effect=AssertionError('No controller ancestry')):
            path,observed=self.execute()
        self.assertEqual(self.http_bodies,[self.prepared.provider_request_body_bytes])
        self.assertTrue((path/'wire/raw-response.bin').is_file())
        self.assertTrue((path/'wire/assistant-output.bin').is_file())
        self.assertTrue((path/'execution-configuration.json').is_file())
        self.assertFalse((path/'execution-rules.tar.gz').exists())
        journal=strict_json_file(path=path/'wire/journal.json')
        self.assertEqual(journal['mode'],'RECORDED_TEST_ONLY')
        self.assertIsNone(journal['usage']['actual_cost'])
        self.assertEqual(observed['response_check']['status'],'SOURCE_REFERENCES_AND_RESPONSE_SHAPE_VALID')
        self.assertFalse(observed['response_check']['semantic_correctness_verified'])
        self.assertFalse(observed['native_result_created'])
        with recorded_ledger(root=self.root).locked() as reopened:
            self.assertEqual(reopened.snapshot()['counts'],[1,1,0])
        stored=calls.read_saved_semantic_call(ledger=recorded_ledger(root=self.root),ordinal=1)
        self.assertEqual(stored['assistant_output'],(path/'wire/assistant-output.bin').read_bytes())
        self.assertEqual(stored['calls'],{'provider':0,'paid':0,'sec':0})

    def test_nondefault_limits_are_actual_object_and_http_configuration_only(self):
        limits=RequestLimits(output_tokens=8192)
        from vnext.current_request_configuration import transport_policy
        policy=transport_policy(configuration=self.prepared.requirement,repo_root=REPO_ROOT,limits=limits)
        prepared=replace(self.prepared,limits=limits,authority=invocation_control.prepare_current_invocation_context(
            repo_root=REPO_ROOT,configuration=self.prepared.requirement,transport=policy,limits=limits),
            provider_request_body_bytes=calls.request_body(strict_json_loads(
                text=self.prepared.request_bytes.decode()),policy,limits=limits))
        self.execute(prepared=prepared,wire=self.wire(prepared=prepared))
        self.assertEqual(json.loads(self.http_bodies[0])['max_tokens'],8192)
        _,plan=calls.build_plan(prepared)
        self.assertEqual(plan['resource_limits']['maximum_context_tokens'],limits.max_context_tokens)
        with self.assertRaisesRegex(ValueError,'NONDEFAULT_LIVE_LIMITS_NOT_AUTHORIZED'):
            live_scope(configuration=prepared.requirement,metric_id='D04',limits=limits)

    def test_exhausted_allowance_and_unapproved_purpose_never_reach_http(self):
        for limits,purposes,error in [((0,0,0),None,'COUNT_EXHAUSTED'),
                                      ((240,240,80),[],'PURPOSE_NOT_APPROVED')]:
            with self.subTest(error=error):
                self.ledger=recorded_ledger(root=self.root/error,limits=limits)
                if purposes is not None:
                    from vnext.canonical import content_hash
                    body={k:v for k,v in self.ledger.binding.items() if k!='binding_id'}
                    body['purposes']=purposes;self.ledger.binding={**body,'binding_id':content_hash(value=body)}
                with self.assertRaisesRegex(ValueError,error):self.execute()
        self.assertEqual(self.http_bodies,[])

    def test_unknown_usage_is_null_counted_and_stops_without_retry(self):
        path,observed=self.execute(wire=self.wire(usage=False))
        self.assertEqual(observed['terminal']['stop_reason'],'USAGE_UNKNOWN')
        self.assertIsNone(strict_json_file(path=path/'wire/journal.json')['usage']['input_tokens'])
        with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.execute()
        self.assertEqual(len(self.http_bodies),1)

    def test_timeout_is_unknown_counted_and_stops_without_retry(self):
        path,observed=self.execute(error=TimeoutError('recorded HTTP timeout'))
        self.assertEqual(observed['terminal']['stop_reason'],'UNKNOWN_REMOTE_OUTCOME')
        self.assertEqual(strict_json_file(path=path/'wire/journal.json')['error_class'],'TIMEOUT')
        with recorded_ledger(root=self.root).locked() as reopened:
            self.assertEqual(reopened.snapshot()['counts'],[1,1,0])
        with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.execute()
        self.assertEqual(len(self.http_bodies),1)

    def test_same_request_is_not_paid_twice_after_restart(self):
        self.execute()
        self.ledger=recorded_ledger(root=self.root)
        with self.assertRaisesRegex(ValueError,'REDRAW_FORBIDDEN'):self.execute()
        self.assertEqual(len(self.http_bodies),1)

    def test_interrupted_claim_is_not_reused_or_automatically_retried(self):
        original=calls.preserve_execution_rules
        with patch.object(calls,'preserve_execution_rules',side_effect=OSError('recorded write interruption')):
            with self.assertRaisesRegex(OSError,'write interruption'):self.execute()
        self.ledger=recorded_ledger(root=self.root)
        with self.ledger.locked():
            snapshot=self.ledger.snapshot()
            self.assertEqual(snapshot['counts'],[1,1,0])
            self.assertEqual(snapshot['rows'][0]['status'],'UNKNOWN_PENDING_RECONCILIATION')
        with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.execute()
        self.assertEqual(self.http_bodies,[])

    def test_written_terminal_gap_reconciles_without_another_http_or_count(self):
        def crash(phase):
            if phase == 'AFTER_EXECUTION_SEALED':raise OSError('recorded terminal gap')
        with patch.object(invocation_control,'_INVOCATION_TERMINAL_RECOVERY_HOOK',crash):
            with self.assertRaisesRegex(OSError,'terminal gap'):self.execute()
        self.assertEqual(len(self.http_bodies),1)
        self.ledger=recorded_ledger(root=self.root)
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['stopped_channels'],['PROVIDER'])
        terminal=calls.reconcile_saved_provider_terminal(ledger=self.ledger,ordinal=1)
        self.assertEqual(terminal['counts'],[1,1,0])
        self.assertEqual(list((self.root/'calls/0001/invocation_control/reservations').glob('*.json')),[])
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[1,1,0])
        with self.assertRaisesRegex(ValueError,'REDRAW_FORBIDDEN'):self.execute()
        self.assertEqual(len(self.http_bodies),1)

    def test_402_keeps_original_error_and_stops_after_one_http(self):
        from urllib.error import HTTPError
        raw=b'{"error":{"message":"recorded insufficient balance"}}'
        error=HTTPError('https://api.deepseek.com/chat/completions',402,'recorded',{},io.BytesIO(raw))
        path,observed=self.execute(error=error)
        self.assertEqual(observed['terminal']['stop_reason'],'HTTP_402')
        self.assertEqual((path/'wire/raw-response.bin').read_bytes(),raw)
        self.assertIsNone(strict_json_file(path=path/'wire/journal.json')['usage']['actual_cost'])
        with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.execute()
        self.assertEqual(len(self.http_bodies),1)

    def test_truncated_response_is_failed_without_relabel_or_retry(self):
        path,observed=self.execute(wire=self.wire(finish='length'))
        journal=strict_json_file(path=path/'wire/journal.json')
        self.assertEqual(journal['error_class'],'DEEPSEEK_RESPONSE_INVALID')
        self.assertEqual(observed['terminal']['status'],'FAILED_TERMINAL')
        self.assertFalse((path/'wire/assistant-output.bin').exists())
        self.assertFalse(observed['native_result_created'])
        with self.assertRaisesRegex(ValueError,'REDRAW_FORBIDDEN'):self.execute()
        self.assertEqual(len(self.http_bodies),1)

    def test_source_byte_change_rejects_before_claim(self):
        prepared=replace(self.prepared,source_bytes=self.prepared.source_bytes+b' ')
        # JSON whitespace is not a business/source mutation; change a source
        # identity rather than falsely expecting that whitespace to be rejected.
        value=strict_json_loads(text=prepared.source_bytes.decode());value['company_id']='wrong'
        prepared=replace(prepared,source_bytes=json.dumps(value).encode())
        with self.assertRaisesRegex(ValueError,'CONTINUOUS_SOURCE_CHANGED'):self.execute(prepared=prepared)
        self.assertEqual(self.http_bodies,[])
        self.assertFalse((self.root/'claims.jsonl').exists())

    def test_recorded_ledger_without_recorded_http_never_claims_or_sends(self):
        with self.assertRaisesRegex(ValueError,'CURRENT_RECORDED_HTTP_BOUNDARY_REQUIRED'):
            calls.execute_feasibility(prepared=self.prepared,ledger=self.ledger)
        self.assertFalse((self.root/'claims.jsonl').exists())
        self.assertEqual(self.http_bodies,[])

    def test_recorded_http_cannot_relabel_a_live_execution(self):
        self.ledger.live=True  # Invalid test relabel; no real binding/root.
        with self.http(wire=self.wire()):
            with self.assertRaisesRegex(ValueError,'CURRENT_RECORDED_HTTP_CANNOT_RUN_LIVE'):
                calls.execute_feasibility(prepared=self.prepared,ledger=self.ledger)
        self.assertFalse((self.root/'claims.jsonl').exists())
        self.assertEqual(self.http_bodies,[])


class NativeCurrentRequestTest(unittest.TestCase):
    """One actual saved-source native request, synthetic HTTP answer only."""
    setUp=CurrentRequestRuntimeTest.setUp
    wire=CurrentRequestRuntimeTest.wire
    http=CurrentRequestRuntimeTest.http

    @classmethod
    def setUpClass(cls):
        with patch.object(calls,'load_requirement_snapshot',side_effect=AssertionError('No Requirement ancestry')):
            cls.requests=calls.prepare_requests(company_id='enphase_energy',metric_id='D04',
                native=True,reference_context=True,complete_response_contract=True)
        cls.prepared=next(p for p in cls.requests if not strict_json_loads(
            text=p.request_bytes.decode())['required_candidate_assessments'])

    def test_current_native_candidate_evidence_saves_and_reads_without_a_metric_result(self):
        with self.http(wire=self.wire()):
            path,observed=calls.execute_d04_assessment(prepared=self.prepared,ledger=self.ledger)
        self.assertEqual(len(self.http_bodies),1)
        self.assertEqual(observed['terminal']['status'],'SUCCEEDED')
        self.assertTrue(observed['native_candidate_evidence_created'])
        self.assertFalse(observed['native_result_created'])
        self.assertFalse(observed['production_authorized'])
        read=calls.read_saved_semantic_call(ledger=recorded_ledger(root=self.root),ordinal=1)
        self.assertEqual(read['terminal']['terminal_id'],observed['terminal']['terminal_id'])
        self.assertIsNotNone(read['assistant_output'])
        self.assertEqual(read['wire']['mode'],'RECORDED_TEST_ONLY')
        from vnext.native_assessment_replay import replay_native_response
        replay=replay_native_response(prepared=self.prepared,path=path)
        self.assertEqual(replay['success']['response_body'],read['assistant_output'])


if __name__=='__main__':unittest.main()
