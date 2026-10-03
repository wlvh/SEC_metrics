"""Complete prompt counting, output reservation, and source-bound grouping."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from vnext.canonical import canonical_json_bytes, content_hash
from vnext.continuous_request_context import (
    FORMAT_VERSION, MAX_CONTEXT, OUTPUT_RESERVE, measure_request, measured_groups, render_prompt)
from vnext.continuous_semantic_calls import request_body


def envelope(text='hello', **extra):
    return request_body({'system_prompt': 'Return JSON.', 'text': text, **extra},
                        SimpleNamespace(model='deepseek-flash'))


class ContinuousRequestContextTest(unittest.TestCase):
    def test_reference_vectors_include_prompt_envelope_and_output_reserve(self):
        # These vectors were independently rendered by the pinned upstream
        # encoding.py, then encoded by its tokenizer (not by this formatter).
        for text, expected in [
            ('hello', 35), ('你好 世界。', 38),
            ('<xbrli:context id="c1">2025-12-31</xbrli:context>', 59),
            ('a\n\n b \t c', 41), ('"quotes" \\ paths / json', 42),
        ]:
            with self.subTest(text=text):
                result = measure_request(envelope(text), require_reference=True)
                self.assertEqual(result['input_tokens'], expected)
                self.assertEqual(result['context_tokens'], expected + OUTPUT_RESERVE)
                self.assertEqual(result['estimator_method'], 'PINNED_REFERENCE_CHAT_FORMAT')
                self.assertEqual(result['identity']['tokenizer_engine_version'], '0.22.2')

    def test_all_source_navigation_schema_and_messages_enter_count(self):
        raw = envelope('full annual source')
        base = measure_request(raw, require_reference=True)
        for changed in [envelope('full annual source ' * 30),
                        envelope('full annual source', required_candidate_assessments=list(range(100))),
                        envelope('full annual source', response_protocol={'nested': ['obligation'] * 100})]:
            result = measure_request(changed, require_reference=True)
            self.assertGreater(result['input_tokens'], base['input_tokens'])
            self.assertNotEqual(result['request_sha256'], base['request_sha256'])
        body = json.loads(raw)
        body['messages'][0]['content'] += ' extra instructions' * 30
        self.assertGreater(measure_request(canonical_json_bytes(value=body))['input_tokens'], base['input_tokens'])
        prompt = render_prompt(raw, provider='deepseek', model='deepseek-flash', api='chat_completions')
        self.assertTrue(prompt.startswith('<｜begin▁of▁sentence｜><｜System｜>Return JSON.'))
        self.assertIn('## Response Format:\n\n', prompt)
        self.assertTrue(prompt.endswith('<｜Assistant｜></think>'))

    def test_unsupported_service_and_format_are_explicit(self):
        for kwargs in [{'provider': 'other'}, {'model': 'deepseek-reasoner'}, {'api': 'responses'}]:
            with self.assertRaisesRegex(ValueError, 'SERVICE_UNSUPPORTED'):
                measure_request(envelope(), **kwargs)
        body = json.loads(envelope())
        for key, value in [('tools', []), ('temperature', 1), ('thinking', {'type': 'enabled'}),
                           ('stream', True), ('max_tokens', 8192), ('response_format', {'type': 'json_schema'})]:
            changed = deepcopy(body); changed[key] = value
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'UNSUPPORTED'):
                measure_request(canonical_json_bytes(value=changed))
        for messages in [[body['messages'][1]], body['messages'] + [{'role': 'assistant', 'content': 'a'}],
                         [{'role': 'system', 'content': []}, body['messages'][1]]]:
            changed = deepcopy(body); changed['messages'] = messages
            with self.assertRaisesRegex(ValueError, 'MESSAGES_UNSUPPORTED'):
                measure_request(canonical_json_bytes(value=changed))
        with self.assertRaisesRegex(ValueError, 'LITERAL_SPECIAL_TOKEN_UNSUPPORTED'):
            measure_request(envelope('<｜User｜>'))

    def test_missing_engine_is_conservative_and_cannot_regroup(self):
        with patch('vnext.continuous_request_context._load_tokenizer', return_value=(None, 'UNAVAILABLE')):
            result = measure_request(envelope())
            self.assertEqual(result['input_tokens'], result['rendered_prompt_bytes'])
            self.assertEqual(result['estimator_method'], 'UTF8_RENDERED_PROMPT_UPPER_BOUND')
            with self.assertRaisesRegex(ValueError, 'REFERENCE_REQUIRED'):
                measure_request(envelope(), require_reference=True)

    def test_resource_mutation_after_cached_parse_is_rejected(self):
        from vnext import continuous_request_context as context
        original = (context.ROOT / context.TOKENIZER_PATH).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / context.TOKENIZER_PATH
            path.parent.mkdir(parents=True)
            path.write_bytes(original)
            with patch.object(context, 'ROOT', root):
                self.assertEqual(measure_request(envelope(), require_reference=True)['input_tokens'], 35)
                path.write_bytes(original + b'changed')
                with self.assertRaisesRegex(ValueError, 'TOKENIZER_ARCHIVE_CHANGED'):
                    measure_request(envelope(), require_reference=True)

    def test_real_usage_feedback_has_a_separate_context_failure(self):
        from vnext.continuous_semantic_calls import usage_error
        def wire(prompt, output):
            return canonical_json_bytes(value={'usage': {'prompt_tokens': prompt,
                'completion_tokens': output, 'total_tokens': prompt + output}})
        self.assertEqual(usage_error(wire(35, 20), expected_prompt_tokens=35, enforce_total_context=True), '')
        self.assertEqual(usage_error(wire(36, 20), expected_prompt_tokens=35, enforce_total_context=True),
                         'CONTEXT_REFERENCE_MISMATCH')
        self.assertEqual(usage_error(wire(199000, 1001), expected_prompt_tokens=199000,
                                    enforce_total_context=True), 'CONTEXT_LIMIT')
        # Old recorded fixtures remain usage-shape evidence only.
        self.assertEqual(usage_error(wire(100, 20)), '')
        self.assertEqual(usage_error(b'{}', expected_prompt_tokens=35, enforce_total_context=True), 'USAGE_UNKNOWN')

    def test_output_reservation_changes_the_real_200000_boundary(self):
        n = MAX_CONTEXT - OUTPUT_RESERVE
        initial = measure_request(envelope('x ' * n), require_reference=True)
        n -= initial['context_tokens'] - MAX_CONTEXT
        boundary = measure_request(envelope('x ' * n), require_reference=True)
        excess = measure_request(envelope('x ' * (n + 1)), require_reference=True)
        self.assertEqual(boundary['context_tokens'], MAX_CONTEXT)
        self.assertTrue(boundary['fits'])
        self.assertFalse(excess['fits'])
        self.assertLess(excess['input_tokens'], MAX_CONTEXT)

    def test_grouper_preserves_every_unit_and_checks_full_identity(self):
        units = [{'unit_id': 'unit-' + str(i), 'document_id': 'doc', 'text': 'x ' * 100000}
                 for i in range(3)]
        def factory(group):
            body = {'system_prompt': 'Return JSON.', 'units': group,
                    'required_candidate_assessments': [{'source_index': 7}],
                    'response_protocol': {'required': ['all source units']}}
            return {**body, 'request_id': content_hash(value=body)}
        groups = measured_groups(units, factory)
        self.assertEqual([len(g) for g in groups], [1, 1, 1])
        self.assertEqual([u for g in groups for u in g], units)
        for group in groups:
            self.assertTrue(measure_request(request_body(factory(group), SimpleNamespace(model='deepseek-flash')),
                                            require_reference=True)['fits'])
        too_large = [{**units[0], 'text': 'x ' * MAX_CONTEXT}]
        with self.assertRaisesRegex(ValueError, 'SINGLE_SOURCE_UNIT_EXCEEDS_BOUND'):
            measured_groups(too_large, factory)

    def test_new_source_format_does_not_relabel_old_requests(self):
        from tests.vnext.test_capacity_semantic_review import source_packet
        from vnext.d04_native_assessment import native_source, requests_from_source
        source = source_packet()
        source.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04')
        source['documents'][0].update(language_candidate_block_indices=[7], native_candidate_ordinals=[])
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        old = native_source(source)
        current = native_source(source, request_context_format=FORMAT_VERSION)
        self.assertNotIn('request_context_format', old)
        self.assertEqual(old['units'], current['units'])
        self.assertNotEqual(old['semantic_source_id'], current['semantic_source_id'])
        old_requests = requests_from_source(old)
        new_requests = requests_from_source(current)
        self.assertEqual(old_requests, requests_from_source(native_source(source)))
        self.assertNotEqual(old_requests[0]['request_id'], new_requests[0]['request_id'])
        self.assertEqual(new_requests[0]['request_context_format'], FORMAT_VERSION)
        self.assertEqual([u['unit_id'] for r in new_requests for u in r['units']], source['required_unit_ids'])

    def test_b13_and_d03_grouped_responses_still_account_for_each_source_unit(self):
        from tests.vnext.test_capacity_semantic_review import source_packet
        from vnext import capacity_semantic_review as b13, r6_regulatory_semantics as d03
        from vnext.r6_semantic_source import _seal_unit
        source = source_packet()
        first = source['units'][0]
        second_payload = deepcopy(first['payload'])
        second_payload['blocks'][0]['block_index'] = 8
        second = _seal_unit(first['document_id'], 'VISIBLE_TEXT', second_payload, 1)
        source['units'].append(second)
        source['required_unit_ids'].append(second['unit_id'])
        source['capacity_navigation'].append({'unit_id': second['unit_id'], 'kind': 'VISIBLE_BLOCK', 'source_index': 8})
        source['request_context_format'] = FORMAT_VERSION
        def seal(value):
            value['semantic_source_id'] = content_hash(value={k:v for k,v in value.items() if k != 'semantic_source_id'})
            return value
        source = seal(source)
        request = b13.requests_from_source(source)[0]
        self.assertEqual(b13._restore_units(request['units'], request['shared_source_dictionaries']), source['units'])
        self.assertEqual(len(request['required_candidate_assessments']), 2)
        response = {'request_id': request['request_id'], 'units': [
            {'unit_id': unit['unit_id'], 'reviewed': True, 'unresolved': [], 'calculation_limits': [],
             'findings': [{'kind': 'AVAILABLE_CAPACITY', 'subject': 'TARGET_REGISTRANT', 'timing': 'CURRENT_REPORT',
                          'reason': 'The complete supplied sentence reports quarterly widget capacity.',
                          'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': index}]}]}
            for unit, index in zip(source['units'], [7, 8])]}
        checked = b13.validate_response(request=request, raw_response=canonical_json_bytes(value=response))
        self.assertEqual(len(checked['findings']), 2)
        missing = deepcopy(response); missing['units'].pop()
        with self.assertRaises(ValueError):
            b13.validate_response(request=request, raw_response=canonical_json_bytes(value=missing))
        doc = source['documents'][0]
        doc.update(language_candidate_block_indices=[7, 8], native_candidate_ordinals=[],
                   registrant_name_binding={'accepted_source_names': ['Example Company']},
                   raw_blob={'raw_asset_id': 'sha256:' + '3' * 64},
                   source_reference={'source_reference_id': 'sha256:' + '4' * 64})
        source.update(metric_id='D03', record_type='D03_COMPLETE_SEMANTIC_SOURCE')
        source = seal(source)
        request = d03.requests_from_source(source)[0]
        self.assertEqual(request['units'], source['units'])
        self.assertEqual(len(request['required_candidate_assessments']), 2)
        response = {'request_id': request['request_id'], 'units': [
            {'unit_id': unit['unit_id'], 'reviewed': True, 'findings': [], 'unresolved': [],
             'context_only_source_indices': [index]} for unit, index in zip(source['units'], [7, 8])]}
        checked = d03.validate_response(request=request, raw_response=canonical_json_bytes(value=response))
        self.assertEqual(len(checked['findings']), 2)
        self.assertFalse(checked['semantic_correctness_verified'])
        missing = deepcopy(response); missing['units'].pop()
        with self.assertRaises(ValueError):
            d03.validate_response(request=request, raw_response=canonical_json_bytes(value=missing))


if __name__ == '__main__':
    unittest.main()
