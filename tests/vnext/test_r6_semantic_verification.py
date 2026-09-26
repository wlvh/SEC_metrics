"""Read actual historical proposal bytes; new verification uses MOCK only."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from vnext import ai_adapter as adapter, invocation_control as control
from vnext.canonical import canonical_json_bytes
from vnext.normal_source_authority import ROOT
from vnext.continuous_semantic_calls import prepare_requests,build_plan,execute_feasibility,request_digest
from vnext.continuous_call_ledger import recorded_ledger
from vnext import r6_semantic_verification as verification


class SemanticVerificationTest(unittest.TestCase):
    def test_prior_history_and_existing_provider_bridge_offline(self):
        location=os.environ.get('SEMANTIC_VERIFICATION_MATERIAL_ROOT')
        if location:
            directory=Path(location).resolve();self.assertFalse(directory.exists());directory.mkdir(parents=True)
        else:
            temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);directory=Path(temp.name).resolve()
        packet=ROOT/'docs/evidence/issue28_continuous/regulatory-semantic-references'
        index=json.loads((packet/'provider-observations-index.json').read_text());archive=packet/index['archive']
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),index['archive_binding']['sha256'])
        with tarfile.open(archive) as tar:
            for name,item in index['files'].items():
                if not name.startswith('calls/0040/'):continue
                raw=tar.extractfile(item['archive_member']).read()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])
                dest=directory/'prior-history'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        prior=directory/'prior-history/calls/0040';original=verification._read_prior_directory(prior)
        p=prior/'wire/assistant-output.bin';saved=p.read_bytes();p.write_bytes(saved+b' ')
        with self.assertRaisesRegex(ValueError,'SEMANTIC_CHECK_PRIOR_BYTES_CHANGED'):verification._read_prior_directory(prior)
        p.write_bytes(saved)
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')), \
             patch.object(control,'effective_invocation_policy',side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')), \
             patch.object(verification,'_prior',side_effect=lambda ordinal:verification._read_prior_directory(prior)):
            requests=prepare_requests(company_id='pfizer',metric_id='D03',prior_call_ordinal=40)
            self.assertEqual(len(requests),1);prepared=requests[0];request=json.loads(prepared.request_bytes);policy,plan=build_plan(prepared)
            self.assertEqual(request['prior_request_id'],original[2]['request_id'])
            self.assertEqual(request['prior_assistant_output_sha256'],original[5])
            self.assertEqual(request['units'],original[2]['units'])
            response={'request_id':request['request_id'],'assessments':[]}
            for proposal in request['proposals']:
                e=proposal['finding']['evidence'][0]
                response['assessments'].append({'proposal_id':proposal['proposal_id'],'judgment':'UNRESOLVED',
                    'reason':'Offline bridge fixture; this is not a semantic review answer.',
                    'evidence':[{'unit_id':proposal['unit_id'],**e}]})
            raw=canonical_json_bytes(value=response);checked=verification.validate_response(request=request,raw_response=raw)
            self.assertTrue(checked['all_proposals_assessed']);self.assertFalse(checked['all_proposals_supported'])
            self.assertFalse(checked['independent_code_review']);self.assertFalse(checked['semantic_correctness_verified'])
            bad=copy.deepcopy(response);bad['assessments'].pop()
            with self.assertRaisesRegex(ValueError,'SEMANTIC_CHECK_PROPOSALS_INCOMPLETE'):
                verification.validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            bad=copy.deepcopy(response);bad['assessments'][0]['evidence'][0]['source_index']=999999
            with self.assertRaisesRegex(ValueError,'SEMANTIC_CHECK_REFERENCE_RANGE'):
                verification.validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            changed=copy.deepcopy(request);changed['proposals'][0]['finding']['kind']='UNRESOLVED'
            self.assertNotEqual(request_digest(changed,policy),request_digest(request,policy))
            wire=canonical_json_bytes(value={'id':'semantic-check-offline-only','model':'deepseek-flash','choices':[{
                'message':{'role':'assistant','content':raw.decode()},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':1000,'completion_tokens':1000,'total_tokens':2000,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000}})
            class FakeResponse(io.BytesIO):headers={'x-request-id':'semantic-check-offline-only'}
            seen=[]
            def opener(*,fullurl,timeout):
                self.assertEqual(fullurl.full_url,'https://api.deepseek.com/chat/completions');self.assertEqual(timeout,120)
                self.assertEqual(fullurl.data,prepared.provider_request_body_bytes);seen.append(fullurl.data);return FakeResponse(wire)
            with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-a-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=opener):
                observed=adapter._build_repository_transport(policy=policy).complete(prepared_request=prepared,
                    egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
                self.assertEqual(observed.raw_response_bytes,wire)
            self.assertEqual(len(seen),1)
            ledger=recorded_ledger(root=directory/'recorded-ledger');path,outcome=execute_feasibility(prepared=prepared,ledger=ledger,recorded_wire=wire)
            self.assertIn('response_check',outcome);self.assertFalse(outcome['native_result_created'])
            with ledger.locked():self.assertEqual(ledger.snapshot()['counts'],[1,1,0])
            summary={'status':'SEMANTIC_VERIFICATION_OFFLINE_WIRING_PASS','closure':prepared.requirement['requirement_closure_hash'],
                'proposals':len(request['proposals']),'request_bytes':len(prepared.provider_request_body_bytes),
                'source_references_and_original_proposal_bytes_replayed':True,'native_mock_path':str(path),
                'calls':[0,0,0],'network_disabled':True,'real_request_factory_to_controller_verified':True,
                'independent_code_review':False,'semantic_correctness_verified':False,'native_result_created':False}
            (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':unittest.main()
