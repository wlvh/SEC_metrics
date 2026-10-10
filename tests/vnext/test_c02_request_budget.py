"""Output-budget preparation preserves all source bytes and old defaults."""
import json
import unittest

from vnext.c02_request_budget import with_c02_output_budget
from vnext.request_limits import RequestLimits


def body(prompt='Maximum 64 facts, complete JSON within 4096 output tokens.'):
    return json.dumps({'model':'deepseek-flash','temperature':0,'max_tokens':4096,
        'stream':False,'thinking':{'type':'disabled'},'response_format':{'type':'json_object'},
        'messages':[{'role':'system','content':prompt},{'role':'user','content':
            '{"strings":["Exact source \\n whitespace","complete JSON within 999 output tokens"],"block_count":2,"geometry":[[1,1,false]],"tables":[]}'}]},ensure_ascii=False,indent=1).encode()


class C02RequestBudgetTest(unittest.TestCase):
    def test_default_preserves_original_wire_bytes(self):
        raw=body();self.assertEqual(with_c02_output_budget(raw),raw)

    def test_explicit_budget_updates_both_limits_without_changing_source_or_schema(self):
        raw=body();old=json.loads(raw)
        actual=json.loads(with_c02_output_budget(raw,limits=RequestLimits(output_tokens=8192)))
        self.assertEqual(actual['max_tokens'],8192)
        self.assertIn('complete JSON within 8192 output tokens',actual['messages'][0]['content'])
        self.assertEqual(actual['messages'][1],old['messages'][1])
        for field in ('model','temperature','stream','thinking','response_format'):
            self.assertEqual(actual[field],old[field])
        self.assertEqual(raw,body())

    def test_existing_contradictory_text_is_corrected_in_new_bytes_only(self):
        value=json.loads(body());value['max_tokens']=8192;raw=json.dumps(value).encode()
        actual=json.loads(with_c02_output_budget(raw,limits=RequestLimits(output_tokens=8192)))
        self.assertIn('within 8192 output tokens',actual['messages'][0]['content'])
        self.assertIn('within 4096 output tokens',json.loads(raw)['messages'][0]['content'])

    def test_an_envelope_only_template_keeps_its_task_text(self):
        prompt='Return facts and unresolved.'
        actual=json.loads(with_c02_output_budget(body(prompt),limits=RequestLimits(output_tokens=8192)))
        self.assertEqual(actual['messages'][0]['content'],prompt)
        self.assertEqual(actual['max_tokens'],8192)

    def test_ambiguous_textual_limits_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'MULTIPLE_TEXTUAL_LIMITS'):
            with_c02_output_budget(body('complete JSON within 4096 output tokens; complete JSON within 2048 output tokens'))

    def test_received_context_payload_and_output_caps_cannot_be_raised(self):
        for limit in [RequestLimits(output_tokens=8193),RequestLimits(max_context_tokens=200001),
                      RequestLimits(max_payload_bytes=8388609)]:
            with self.subTest(limit=limit),self.assertRaisesRegex(ValueError,'RESOURCE_CEILING_EXCEEDED'):
                with_c02_output_budget(body(),limits=limit)


if __name__=='__main__':unittest.main()
