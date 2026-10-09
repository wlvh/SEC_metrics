"""One explicit resource config through formatter, meter and response checks."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext.canonical import canonical_json_bytes
from vnext.request_limits import RequestLimits,DEFAULT_LIMITS
from vnext.continuous_semantic_calls import request_body,usage_error,usage_observation,request_digest
from vnext.continuous_request_context import measure_request,measured_groups,with_request_limits

POLICY=SimpleNamespace(model='deepseek-flash')
REQUEST={'system_prompt':'Return JSON.','text':'hello'}


def usage(prompt,completion):
    return json.dumps({'usage':{'prompt_tokens':prompt,'completion_tokens':completion,
                              'total_tokens':prompt+completion}}).encode()


class RequestLimitsTest(unittest.TestCase):
    def test_default_wire_bytes_and_context_identity_are_preserved(self):
        raw=request_body(REQUEST,POLICY)
        expected=canonical_json_bytes(value={'model':'deepseek-flash','messages':[
            {'role':'system','content':'Return JSON.'},
            {'role':'user','content':'{"text":"hello"}'}],
            'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,
            'stream':False,'thinking':{'type':'disabled'}})
        self.assertEqual(raw,expected)
        self.assertEqual(raw,request_body(REQUEST,POLICY,limits=DEFAULT_LIMITS))
        a=measure_request(raw,require_reference=True)
        b=measure_request(raw,require_reference=True,limits=DEFAULT_LIMITS)
        self.assertEqual(a,b);self.assertEqual(a['input_tokens'],35)
        self.assertEqual(a['output_reserve_tokens'],4096)
        self.assertNotIn('request_limits',a['identity'])

    def test_explicit_8192_reaches_wire_measurement_and_usage_validation(self):
        limits=RequestLimits(output_tokens=8192)
        raw=request_body(REQUEST,POLICY,limits=limits)
        self.assertEqual(json.loads(raw)['max_tokens'],8192)
        measured=measure_request(raw,require_reference=True,limits=limits)
        self.assertEqual(measured['input_tokens'],35)
        self.assertEqual(measured['context_tokens'],35+8192)
        self.assertEqual(measured['maximum_context_tokens'],200000)
        self.assertEqual(measured['identity']['request_limits'],limits.as_dict())
        self.assertEqual(usage_error(usage(35,6168),limits=limits,enforce_total_context=True),'')
        self.assertEqual(usage_error(usage(35,8193),limits=limits,enforce_total_context=True),'OUTPUT_LIMIT')
        with self.assertRaisesRegex(ValueError,'PARAMETERS_UNSUPPORTED'):
            measure_request(raw,require_reference=True)

    def test_output_reserve_total_context_payload_and_invalid_types_are_distinct(self):
        limits=RequestLimits(output_tokens=40,max_context_tokens=70)
        measured=measure_request(request_body(REQUEST,POLICY,limits=limits),limits=limits,require_reference=True)
        self.assertFalse(measured['fits']);self.assertEqual(measured['context_tokens'],75)
        self.assertEqual(usage_error(usage(60,20),limits=limits,enforce_total_context=True),'CONTEXT_LIMIT')
        tiny=RequestLimits(max_payload_bytes=10)
        with self.assertRaisesRegex(ValueError,'PAYLOAD_LIMIT'):
            measure_request(request_body(REQUEST,POLICY),limits=tiny)
        for kwargs in ({'output_tokens':True},{'max_context_tokens':0},{'output_tokens':200000},
                       {'output_tokens':'8192'}):
            with self.assertRaises(ValueError):RequestLimits(**kwargs)

    def test_unknown_usage_cost_and_legacy_check_behavior_stay_explicit(self):
        raw=b'{"error":{"message":"Insufficient Balance"}}'
        self.assertEqual(usage_error(raw,limits=RequestLimits(output_tokens=8192)),'USAGE_UNKNOWN')
        self.assertIsNone(usage_observation(raw)['actual_cost'])
        self.assertIsNone(usage_observation(raw)['input_tokens'])
        # The old omitted-limits usage checker keeps its old semantics;
        # explicit current config adds its separate output bound check.
        self.assertEqual(usage_error(usage(35,6168)),'')
        self.assertEqual(usage_error(usage(35,6168),limits=DEFAULT_LIMITS),'OUTPUT_LIMIT')

    def test_grouper_uses_same_limit_without_dropping_units(self):
        units=[{'unit_id':str(i),'document_id':'d','text':'x '*20} for i in range(3)]
        def factory(group):return {'system_prompt':'Return JSON.','units':group}
        chosen=RequestLimits(output_tokens=8192)
        single=measure_request(request_body(factory(units[:1]),POLICY,limits=chosen),limits=chosen,require_reference=True)
        limits=RequestLimits(output_tokens=8192,max_context_tokens=single['context_tokens']+1)
        groups=measured_groups(units,factory,limits=limits)
        self.assertEqual([u for g in groups for u in g],units)
        self.assertEqual([len(g) for g in groups],[1,1,1])
        for group in groups:
            body=request_body(factory(group),POLICY,limits=limits)
            self.assertEqual(json.loads(body)['max_tokens'],8192)
            self.assertTrue(measure_request(body,limits=limits,require_reference=True)['fits'])

    def test_digest_records_resource_change_without_inventing_call_permission(self):
        request={'record_type':'D04_SEMANTIC_VERIFICATION_REQUEST','metric_id':'D04',
            'system_prompt':'Return JSON.','target_cik':'12345','target_period':{'fiscal_year':2025},
            'fiscal_label_context':{},'document_context':{'filing':{'accessionNumber':'fixture'}},
            'units':[],'response_protocol':{},'category_definitions':{},'required_candidate_assessments':[]}
        default=request_digest(request,POLICY)
        self.assertEqual(default,request_digest(request,POLICY,limits=DEFAULT_LIMITS))
        self.assertNotEqual(default,request_digest(request,POLICY,limits=RequestLimits(output_tokens=8192)))

    def test_saved_envelope_changes_only_output_parameter_and_preserves_source_strings(self):
        body=json.loads(request_body(REQUEST,POLICY))
        body['messages'][1]['content']='verbatim \u037e and e\u0301'
        original=json.dumps(body,ensure_ascii=False,indent=2).encode()
        self.assertEqual(original,with_request_limits(original,limits=DEFAULT_LIMITS))
        changed=with_request_limits(original,limits=RequestLimits(output_tokens=8192))
        decoded=json.loads(changed)
        self.assertEqual({k:v for k,v in body.items() if k!='max_tokens'},
                         {k:v for k,v in decoded.items() if k!='max_tokens'})
        self.assertEqual(decoded['messages'][1]['content'],'verbatim \u037e and e\u0301')


if __name__=='__main__':unittest.main()
