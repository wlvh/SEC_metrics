"""Offline preparation of a saved semantic input; no model answers or calls."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import development_request_context as context
from vnext import development_semantic_requests as calls
from vnext.request_limits import DEFAULT_LIMITS, RequestLimits


SAVED = REPO_ROOT / 'docs/evidence/issue28_continuous/b13-source-indexing/original68'
POLICY = SimpleNamespace(model='deepseek-flash')
OMITTED_FIELDS = {'system_prompt', 'provider_request_sent', 'provider_tokens_measured',
                  'production_authorized'}


class DevelopmentRequestPreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_bytes = (SAVED / 'semantic-request.json').read_bytes()
        cls.saved_request = json.loads(cls.saved_bytes)
        cls.saved_wire_hash = json.loads((SAVED / 'wire/journal.json').read_bytes())['request_sha256']
        cls.saved_digest = json.loads((SAVED / 'intent.json').read_bytes())['request_digest']

    def setUp(self):
        self.request = deepcopy(self.saved_request)
        # Both accepted and rejected preparations must stay outside real call
        # factories, ledger reservation, execution, transport and sockets.
        for target in (
            'vnext.continuous_semantic_calls.prepare_requests',
            'vnext.continuous_semantic_calls.SemanticRequest',
            'vnext.continuous_semantic_calls.build_plan',
            'vnext.continuous_semantic_calls.load_requirement_snapshot',
            'vnext.continuous_call_ledger.CallLedger.claim',
            'vnext.continuous_semantic_calls._execute_semantic',
            'vnext.continuous_semantic_calls.transport_payload',
            'socket.socket',
        ):
            guard = patch(target, side_effect=AssertionError('Offline preparation reached ' + target))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)

    def assert_complete_input(self, raw, request):
        body = json.loads(raw)
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': request['system_prompt']})
        payload = json.loads(body['messages'][1]['content'])
        self.assertEqual(payload, {k: v for k, v in request.items() if k not in OMITTED_FIELDS})
        return body

    def test_default_matches_actual_saved_wire_digest_and_main_measurement(self):
        raw, measured = context.prepare_development_request(self.request)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.saved_wire_hash)
        self.assertEqual(len(raw), 145209)
        self.assertEqual(raw, calls.request_body(self.request, POLICY))
        self.assertEqual(calls.request_digest(self.request, POLICY), self.saved_digest)
        self.assertEqual(measured, context.measure_request(raw, require_reference=True))
        self.assertEqual(measured['input_tokens'], 47927)
        self.assertEqual(measured['context_tokens'], 52023)
        self.assertEqual(measured['context_authority_hash'],
                         'sha256:0aecf80fe3abcd1426d269053ea5630a6ac73e53dac76375378973225d110cf1')
        self.assertNotIn('request_limits', measured['identity'])
        self.assert_complete_input(raw, self.saved_request)
        self.assertEqual(self.request, self.saved_request)
        self.assertEqual((SAVED / 'semantic-request.json').read_bytes(), self.saved_bytes)

    def test_same_explicit_limits_build_and_measure_exactly_once(self):
        limits = RequestLimits(output_tokens=8192)
        with patch.object(calls, 'request_body', wraps=calls.request_body) as build, \
                patch.object(context, 'measure_request', wraps=context.measure_request) as meter:
            raw, measured = context.prepare_development_request(self.request, limits=limits)
        build.assert_called_once()
        self.assertIs(build.call_args.kwargs['limits'], limits)
        meter.assert_called_once_with(raw, limits=limits, require_reference=True)
        self.assertEqual(json.loads(raw)['max_tokens'], 8192)
        self.assertEqual(measured['input_tokens'], 47927)
        self.assertEqual(measured['output_reserve_tokens'], 8192)
        self.assertEqual(measured['context_tokens'], 56119)
        self.assertEqual(measured['identity']['request_limits'], limits.as_dict())

    def test_nondefault_keeps_all_source_unicode_prompt_and_response_protocol(self):
        literal = 'verbatim \u037e and e\u0301\n全量原文\t'
        self.request['system_prompt'] += '\n' + literal
        self.request['units'][0]['payload']['development_unicode_probe'] = literal
        before = deepcopy(self.request)
        default, first = context.prepare_development_request(self.request)
        configured, second = context.prepare_development_request(
            self.request, limits=RequestLimits(output_tokens=8192))
        old = self.assert_complete_input(default, before)
        new = self.assert_complete_input(configured, before)
        self.assertEqual({k: v for k, v in old.items() if k != 'max_tokens'},
                         {k: v for k, v in new.items() if k != 'max_tokens'})
        self.assertEqual(json.loads(new['messages'][1]['content'])['units'][0]['payload']
                         ['development_unicode_probe'], literal)
        self.assertEqual(first['input_tokens'], second['input_tokens'])
        self.assertEqual(self.request, before)

    def test_input_plus_output_reserve_inclusive_boundary_and_rejection(self):
        _, measured = context.prepare_development_request(self.request, limits=RequestLimits(output_tokens=8192))
        total = measured['context_tokens']
        exact = RequestLimits(output_tokens=8192, max_context_tokens=total)
        _, boundary = context.prepare_development_request(self.request, limits=exact)
        self.assertTrue(boundary['fits'])
        self.assertEqual(boundary['context_tokens'], exact.max_context_tokens)
        too_small = RequestLimits(output_tokens=8192, max_context_tokens=total - 1)
        self.assertLess(measured['input_tokens'], too_small.max_context_tokens)
        with self.assertRaisesRegex(ValueError, 'CONTINUOUS_CONTEXT_RESOURCE_LIMIT'):
            context.prepare_development_request(self.request, limits=too_small)

    def test_complete_payload_boundary_and_rejection_before_tokenization(self):
        raw = calls.request_body(self.request, POLICY)
        exact = RequestLimits(max_payload_bytes=len(raw))
        prepared, measured = context.prepare_development_request(self.request, limits=exact)
        self.assertEqual(prepared, raw)
        self.assertEqual(measured['request_bytes'], exact.max_payload_bytes)
        with patch.object(context, '_load_tokenizer', side_effect=AssertionError('Payload should reject first')):
            with self.assertRaisesRegex(ValueError, 'CONTINUOUS_CONTEXT_PAYLOAD_LIMIT'):
                context.prepare_development_request(self.request,
                    limits=RequestLimits(max_payload_bytes=len(raw) - 1))

    def test_wrong_configuration_rejects_before_building_wire(self):
        with patch.object(calls, 'request_body', side_effect=AssertionError('Bad config should reject first')):
            for invalid in ({}, True, 8192, '8192'):
                with self.subTest(limits=invalid):
                    with self.assertRaisesRegex(ValueError, 'REQUEST_LIMITS_TYPE_REQUIRED'):
                        context.prepare_development_request(self.request, limits=invalid)

    def test_missing_reference_cannot_fall_back_to_a_development_acceptance(self):
        with patch.object(context, '_load_tokenizer', return_value=(None, 'TOKENIZER_DEPENDENCY_UNAVAILABLE')):
            for limits in (DEFAULT_LIMITS, RequestLimits(output_tokens=8192)):
                with self.subTest(limits=limits):
                    with self.assertRaisesRegex(ValueError,
                            'CONTINUOUS_CONTEXT_REFERENCE_REQUIRED:TOKENIZER_DEPENDENCY_UNAVAILABLE'):
                        context.prepare_development_request(self.request, limits=limits)


if __name__ == '__main__':
    unittest.main()
