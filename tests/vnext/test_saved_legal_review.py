"""Small retained-call fixtures test mechanics, never model correctness."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from vnext import legal_review_contract as contract
from vnext import saved_legal_review as saved
from vnext.canonical import content_hash, sha256_bytes


class SavedLegalReviewTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        document={'source_reference_id':'source-reference','raw_asset_id':'raw-asset',
            'text_document_id':'document','blocks':[{'text':'We are a defendant in a pending lawsuit.'}]}
        self.request=contract.review_request(company_id='company',target_cik='123',
            period_end='2025-12-31',document=document,pool=[0],keyword_admitted=[0])
        self.provider={'messages':contract.provider_messages(self.request),'model':'deepseek-flash',
            'max_tokens':4096,'temperature':0,'stream':False,'response_format':{'type':'json_object'}}
        self.source={'company_id':'company','metric_id':'D02','request':deepcopy(self.request),
            'source_proofs':[{'source_url':'saved-source','content_sha256':'raw-asset'}]}
        self.answer={'decisions':[{'block_id':'b0','decision':'IN_SCOPE',
            'quote':document['blocks'][0]['text']}],'also_in_scope':[]}
        self.response={'id':'recorded-provider-id','choices':[{'finish_reason':'stop',
            'message':{'role':'assistant','content':json.dumps(self.answer)}}],
            'usage':{'prompt_tokens':90,'completion_tokens':20,'total_tokens':110}}
        self.journal={'mode':'RECORDED','status_code':200,'error_class':'','intent_id':'intent',
            'provider_request_id':'recorded-provider-id','execution_id':'execution','wire_id':'wire',
            'usage':{'input_tokens':90,'output_tokens':20,'actual_cost':None}}
        self.terminal={'status':'SUCCEEDED','intent_id':'intent','terminal_id':'terminal',
            'counts':[1,1,0],'counts_kind':'RECORDED_FIXTURE_NOT_REAL_CALL'}
        self.write()

    def write(self):
        def encode(value):return json.dumps(value,sort_keys=True).encode()
        provider=encode(self.provider);raw=encode(self.response)
        answer=json.dumps(self.answer).encode()
        self.journal.update(request_sha256=sha256_bytes(content=provider),
            raw_response_sha256=sha256_bytes(content=raw),assistant_output_sha256=sha256_bytes(content=answer))
        files={'semantic-request.json':encode(self.request),'source.json':encode(self.source),
            'invocation_control/requests/request.bin':provider,'wire/raw-response.bin':raw,
            'wire/assistant-output.bin':answer,'wire/journal.json':encode(self.journal)}
        self.terminal['evidence']={name:sha256_bytes(content=value) for name,value in files.items()}
        files['terminal.json']=encode(self.terminal)
        for name,value in files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)

    def read(self,request=None):
        return saved.read_saved_legal_review(call_root=self.root,request=request or self.request)

    def test_nonempty_review_preserves_original_identity_and_never_becomes_company_result(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.read()
        self.assertEqual(result['included_block_ids'],['b0'])
        self.assertEqual(result['original_execution_id'],'execution')
        self.assertEqual(result['original_counts'],[1,1,0])
        self.assertEqual(result['new_calls'],{'provider':0,'paid':0,'sec':0})
        self.assertFalse(result['complete_company_result'])
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertEqual(result['original_execution_mode'],'RECORDED')
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_changed_source_or_current_period_cannot_borrow_old_answer(self):
        for key,value in [('period_end','2026-12-31'),('target_cik','456'),('company_id','other')]:
            request={**self.request,key:value}
            request['request_id']=content_hash(value={k:v for k,v in request.items() if k!='request_id'})
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'CURRENT_REQUEST_DIFFERS'):
                self.read(request)
        self.source['request']['filing']['raw_asset_id']='another-raw-asset';self.write()
        with self.assertRaisesRegex(ValueError,'CURRENT_REQUEST_DIFFERS'):self.read()

    def test_projection_or_wrong_contract_cannot_be_used_as_the_full_request(self):
        projected={**self.request,'blocks':[]}
        with self.assertRaisesRegex(ValueError,'REQUEST_ID_CHANGED'):self.read(projected)
        with self.assertRaisesRegex(ValueError,'CONTRACT_NOT_SUPPORTED'):self.read({'contract':'D04'})

    def test_provider_messages_and_wire_identity_are_checked_independently(self):
        self.provider['messages'][1]['content']='different request';self.write()
        with self.assertRaisesRegex(ValueError,'PROVIDER_MESSAGES_DIFFER'):self.read()
        self.provider['messages']=contract.provider_messages(self.request)
        self.response['id']='another-parallel-response';self.write()
        with self.assertRaisesRegex(ValueError,'PROVIDER_RESPONSE_DIFFERS'):self.read()

    def test_prefix_or_http_failure_is_not_accepted_even_with_complete_json(self):
        self.response['choices'][0]['finish_reason']='length';self.write()
        with self.assertRaisesRegex(ValueError,'RESPONSE_NOT_COMPLETE'):self.read()
        self.response['choices'][0]['finish_reason']='stop';self.journal['status_code']=402;self.write()
        with self.assertRaisesRegex(ValueError,'WIRE_EXECUTION_DIFFERS'):self.read()

    def test_failed_or_unfinished_original_is_not_accepted(self):
        for status in ('FAILED_TERMINAL','UNKNOWN','RUNNING'):
            self.terminal['status']=status;self.write()
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'NOT_SUCCEEDED'):self.read()

    def test_changed_bytes_are_not_silently_read_from_the_old_receipt(self):
        path=self.root/'wire/assistant-output.bin';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'BYTES_CHANGED'):self.read()

    def test_assistant_file_and_http_content_must_be_the_same_answer(self):
        self.response['choices'][0]['message']['content']='{"decisions":[],"also_in_scope":[]}'
        self.write()
        with self.assertRaisesRegex(ValueError,'ASSISTANT_OUTPUT_DIFFERS'):self.read()

    def test_missing_mandatory_decision_is_still_refused_by_existing_contract(self):
        self.answer={'decisions':[],'also_in_scope':[]}
        self.response['choices'][0]['message']['content']=json.dumps(self.answer);self.write()
        with self.assertRaisesRegex(ValueError,'BLOCKS_UNDECIDED'):self.read()

    def test_unsettled_review_keeps_the_original_undecided_block(self):
        self.answer['decisions'][0]['decision']='CANNOT_TELL_FROM_THE_TEXT'
        self.response['choices'][0]['message']['content']=json.dumps(self.answer);self.write()
        result=self.read()
        self.assertIsNone(result['included_block_ids'])
        self.assertEqual(result['unsettled_block_ids'],['b0'])
        self.assertEqual(result['withheld_reason'],contract.WITHHELD_REASON)
        self.assertFalse(result['complete_company_result'])

    def test_missing_usage_remains_unknown_and_contradictory_counts_are_refused(self):
        self.response.pop('usage');self.write()
        result=self.read()
        self.assertFalse(result['usage_known']);self.assertIsNone(result['usage']['input_tokens'])
        self.assertIsNone(result['usage']['output_tokens']);self.assertIsNone(result['usage']['actual_cost'])
        self.response['usage']={'prompt_tokens':99,'completion_tokens':20};self.write()
        with self.assertRaisesRegex(ValueError,'TOKEN_USAGE_DIFFERS'):self.read()


if __name__=='__main__':unittest.main()
