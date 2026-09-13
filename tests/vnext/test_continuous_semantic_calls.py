"""Actual saved-source factory, real envelope and MOCK WB-3 bridge."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import io
import json
import os
import socket
import tempfile
import tarfile
import unittest

from vnext import ai_adapter as adapter
from vnext import invocation_control as control
from vnext.canonical import canonical_json_bytes, strict_json_loads
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests,build_plan,execute_feasibility,usage_observation,request_digest
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


class ContinuousSemanticCallsTest(unittest.TestCase):
    def test_actual_source_factory_existing_opener_and_controller_offline(self):
        material=os.environ.get('CONTINUOUS_WIRING_MATERIAL_ROOT')
        if material:
            directory=Path(material).resolve();self.assertFalse(directory.exists());directory.mkdir(parents=True)
        else:
            tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);directory=Path(tmp.name).resolve()
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')), \
             patch.object(control,'effective_invocation_policy',side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')):
            requests=prepare_requests(company_id='enphase_energy')
            prepared=min(requests,key=lambda r:len(r.provider_request_body_bytes))
            policy,plan=build_plan(prepared)
            request=strict_json_loads(text=prepared.request_bytes.decode())
            self.assertEqual(request_digest(request,policy),
                request_digest({**request,'request_id':'new-id','source_id':'new-code-id'},policy))
            # An empty set of findings is only protocol input for this bridge.
            # Its correctness is not assumed and may be rejected by the checker.
            response={'request_id':request['request_id'],'units':[
                {'unit_id':u['unit_id'],'reviewed':True,'findings':[],'unresolved':[]} for u in request['units']]}
            raw=canonical_json_bytes(value={'id':'offline-wire-test','model':'deepseek-flash',
                'choices':[{'message':{'role':'assistant','content':json.dumps(response)},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,
                         'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':100}})
            class FakeResponse(io.BytesIO):
                headers={'x-request-id':'offline-wire-test'}
            observed=[]
            def fake_open(*,fullurl,timeout):
                self.assertEqual(fullurl.full_url,'https://api.deepseek.com/chat/completions')
                self.assertEqual(fullurl.data,prepared.provider_request_body_bytes)
                self.assertEqual(timeout,120);observed.append(fullurl.data)
                return FakeResponse(raw)
            with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-test-not-a-secret'}), \
                 patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=fake_open):
                transport=adapter._build_repository_transport(policy=policy)
                with self.assertRaisesRegex(adapter.AIAdapterError,'RESERVATION_OWNER_EGRESS_REQUIRED'):
                    transport.complete(prepared_request=prepared)
                result=transport.complete(prepared_request=prepared,
                    egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
                self.assertEqual(result.raw_response_bytes,raw)
            self.assertEqual(len(observed),1)
            with self.assertRaisesRegex(ValueError,'PAYLOAD_CHANGED'):
                replace(prepared,provider_request_body_bytes=b'{}').validate(policy)
            ledger=recorded_ledger(root=directory/'recorded-ledger')
            path,outcome=execute_feasibility(prepared=prepared,ledger=ledger,recorded_wire=raw)
            rule_index=json.loads((path/'execution-rules.json').read_text())['files']
            from vnext.canonical import sha256_bytes
            with tarfile.open(path/'execution-rules.tar.gz') as archive:
                members=archive.getmembers();self.assertEqual({m.name for m in members},set(rule_index))
                for member in members:
                    data=archive.extractfile(member).read()
                    self.assertEqual(rule_index[member.name],{'sha256':sha256_bytes(content=data),'size':len(data)})
            self.assertFalse(outcome['native_result_created'])
            self.assertFalse(outcome['semantic_correctness_verified'])
            self.assertEqual(outcome['terminal']['status'],'FAILED_TERMINAL')
            with ledger.locked():
                self.assertEqual(ledger.snapshot()['counts'],[1,1,0])
                self.assertEqual(ledger.snapshot()['stopped_channels'],[])
            self.assertIsNone(usage_observation(b'{"error":"402"}')['input_tokens'])
            self.assertIsNone(usage_observation(raw)['actual_cost'])
            self.assertIsNone(plan['observability']['estimated_cost'])
            with control._successor_plan_context(repo_root=ROOT,authority=prepared.authority):
                self.assertIsNone(control._usage(value=usage_observation(None))['input_tokens'])
            with self.assertRaises(control.InvocationControlError):control._usage(value=usage_observation(None))
            parent=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v13')
            self.assertEqual(parent['requirement_closure_hash'],
                'sha256:e1ac4b08b4b31aa5d7a411ac76b8d29c33075e82da3fe5f939009566194dc1f4')
            summary={'status':'OFFLINE_WIRING_PASS','requirement_id':prepared.requirement['requirement_id'],
                'closure':prepared.requirement['requirement_closure_hash'],
                'request_bytes':len(prepared.provider_request_body_bytes),
                'estimated_context_tokens':plan['observability']['estimated_context_tokens'],
                'source_request_count':len(requests),'selected_request_count':1,
                'source_unit_coverage_preserved':True,'model':policy.model,
                'maximum_context_tokens':200000,'retry_count':0,
                'real_request_factory_to_controller_verified':True,'mocked_official_opener_invocations':1,
                'network_disabled':True,'legacy_default_forbidden':True,
                'calls':{'provider':0,'paid':0,'sec':0},'semantic_correctness_verified':False,
                'native_result_created':False,'production_authorized':False,'native_mock_path':str(path)}
            (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps(summary),flush=True)


if __name__=='__main__':unittest.main()
