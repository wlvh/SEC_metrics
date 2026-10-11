"""Synthetic sanitized envelope based on PR111, not a private SDK log."""
from copy import deepcopy
import json
import unittest

from scripts import securegpt_sdk as sdk


class DocumentedSecureGPTResponseTest(unittest.TestCase):
    def sample(self):
        # Shape is documented; contents/counts/id are invented test data.
        return {'id':'synthetic-offline', 'object':'chat.completion',
            'model':'gpt-4o-2024-11-20',
            'choices':[{'index':0,'finish_reason':'stop',
                'content_filter_results':{'violence':{'filtered':False,'severity':'safe'}},
                'message':{'role':'assistant','content':'{"test_only": true}'}}],
            'prompt_filter_results':[{'prompt_index':0,'content_filter_results':{}}],
            'usage':{'prompt_tokens':71,'completion_tokens':9,'total_tokens':80}}

    def test_documented_envelope_uses_existing_shared_answer_parser(self):
        raw=self.sample();before=deepcopy(raw)
        self.assertEqual(json.loads(sdk.assistant_content(sdk.normalize_response(raw))),
                         {'test_only':True})
        self.assertEqual(raw,before)

    def test_known_counts_are_read_but_charge_is_not_invented(self):
        self.assertEqual(sdk.response_usage(self.sample()),
            {'input_tokens':71,'output_tokens':9,'total_tokens':80,'actual_cost':None})

    def test_missing_invalid_usage_remains_unknown(self):
        for usage in (None,{}, {'prompt_tokens':True,'completion_tokens':-1,'total_tokens':'80'}):
            with self.subTest(usage=usage):
                raw=self.sample();raw['usage']=usage
                self.assertEqual(sdk.response_usage(raw),
                    {'input_tokens':None,'output_tokens':None,'total_tokens':None,'actual_cost':None})

    def test_truncated_filtered_and_error_returns_cannot_be_answers(self):
        for finish in ('length','content_filter'):
            raw=self.sample();raw['choices'][0]['finish_reason']=finish
            with self.assertRaisesRegex(sdk.SecureGPTResponseError,'INCOMPLETE_OR_FILTERED'):
                sdk.assistant_content(raw)
        raw=self.sample();raw['error']={'message':'synthetic error'}
        with self.assertRaisesRegex(sdk.SecureGPTResponseError,'SDK_ERROR_RESPONSE'):
            sdk.assistant_content(raw)

    def test_injected_sdk_receives_one_text_request_without_private_imports(self):
        outer=self
        class Client:
            calls=[]
            def request(self,body):
                self.calls.append(body)
                return outer.sample()
        client=Client()
        raw=sdk.send(client=client,messages=[{'role':'user','content':'test-only'}])
        self.assertEqual(client.calls,[{'messages':[{'role':'user',
            'content':[{'type':'text','text':'test-only'}]}]}])
        self.assertEqual(sdk.assistant_content(raw),'{"test_only": true}')


if __name__=='__main__':unittest.main()
