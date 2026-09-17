"""Keep historical/other-entity D04 statements out of current-target results."""
import copy,json,tarfile,hashlib
import unittest
from vnext.normal_source_authority import ROOT
from vnext.canonical import content_hash,canonical_json_bytes,sha256_file
from vnext.r6_semantic_scope import validate_response,POLICY_PATH


class SemanticScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=ROOT/'docs/evidence/issue28_continuous/historical-semantic-controls'
        index=json.loads((folder/'actual-provider-controls-index.json').read_text())
        def read(name):
            item=index['files']['calls/0052/'+name]
            with tarfile.open(folder/index['archive']) as tar:raw=tar.extractfile(item['archive_member']).read()
            assert hashlib.sha256(raw).hexdigest()==item['sha256'];return raw
        cls.original_request=json.loads(read('semantic-request.json'));cls.original_response=read('wire/assistant-output.bin')

    def successor_fixture(self):
        request=copy.deepcopy(self.original_request)
        request['policy_sha256']=sha256_file(path=ROOT/POLICY_PATH)
        policy=json.loads((ROOT/POLICY_PATH).read_text());request['system_prompt']=policy['system_prompt'];request['category_definitions']=policy['category_definitions']
        request['request_id']=content_hash(value={k:v for k,v in request.items() if k!='request_id'})
        response=json.loads(self.original_response);response['request_id']=request['request_id']
        return request,response

    def test_original_failed_response_keeps_its_original_policy_failure(self):
        with self.assertRaisesRegex(ValueError,'D04_CURRENT_TARGET_CATEGORY_CONFLICT'):
            validate_response(request=self.original_request,raw_response=self.original_response)

    def test_successor_scope_projection_preserves_raw_recorded_proposal(self):
        request,response=self.successor_fixture();checked=validate_response(request=request,raw_response=canonical_json_bytes(value=response))
        self.assertEqual(checked['provider_response'],response)
        self.assertEqual([f['kind'] for f in checked['current_target_findings']],['NO_DOUBT_DECLARATION'])
        self.assertEqual(checked['scope_projection'][0]['statement_kind'],'DOUBT_DISCLOSED')
        self.assertEqual(checked['scope_projection'][0]['scoped_kind'],'HISTORICAL_STATEMENT')
        self.assertFalse(checked['semantic_correctness_verified']);self.assertFalse(checked['native_result_created'])

    def test_other_entity_and_unknown_timing_cannot_be_current_target(self):
        for change in [{'subject':'OTHER_ENTITY'},{'timing':'UNRESOLVED'}]:
            request,response=self.successor_fixture();response['units'][0]['findings'][1].update(change)
            checked=validate_response(request=request,raw_response=canonical_json_bytes(value=response))
            self.assertEqual(checked['current_target_findings'],[])

    def test_quote_integrity_remains_strict_after_scope_projection(self):
        request,response=self.successor_fixture();response['units'][0]['findings'][0]['evidence'][0]['text']='We have fabricated this purported source.'
        with self.assertRaisesRegex(ValueError,'D04_EXACT_SOURCE_TEXT_CHANGED'):
            validate_response(request=request,raw_response=canonical_json_bytes(value=response))
        with self.assertRaisesRegex(ValueError,'D04_RESPONSE_SIZE_OR_TYPE'):
            validate_response(request=request,raw_response=b' '*262145)


if __name__=='__main__':unittest.main()
