import json
import unittest

from vnext.c02_model_processing import _response, _bytes, build_development_assessment


class C02ModelProcessingTest(unittest.TestCase):
    def setUp(self):
        self.document = {'blocks': [{}, {}, {}]}
        self.answer = {'facts': [
            {'kind': 'board_size', 'statement': 'Seven directors', 'source_blocks': [0, 1],
             'stated_time': 'CURRENT_IN_FILING'},
            {'kind': 'board_independence', 'statement': 'Six are independent',
             'source_blocks': [1, 2], 'stated_time': 'CURRENT_IN_FILING'}],
            'unresolved': [{'source_blocks': [2], 'reason': 'Chair not established'}]}

    def check_answer(self, value):
        return _response(json.dumps(value).encode(), self.document)

    def test_shared_context_and_unresolved_preserved(self):
        value, selected = self.check_answer(self.answer)
        self.assertEqual(value, self.answer)
        self.assertEqual(selected, [0, 1, 2])

    def test_duplicate_not_automatically_removed(self):
        self.answer['facts'].append(dict(self.answer['facts'][0]))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_FACT'):
            self.check_answer(self.answer)

    def test_invalid_reference_types_and_ranges(self):
        for ids in [[True], [3], [-1], [0, 0], ['0'], [[0]]]:
            with self.subTest(ids=ids):
                self.answer['facts'][0]['source_blocks'] = ids
                with self.assertRaisesRegex(ValueError, 'REFERENCE_INVALID'):
                    self.check_answer(self.answer)

    def test_no_truncation_of_excess_facts(self):
        self.answer['facts'] = self.answer['facts'] * 33
        with self.assertRaisesRegex(ValueError, 'FACT_BOUND_NO_TRUNCATION'):
            self.check_answer(self.answer)

    def test_duplicate_json_key_and_unknown_kind_refused(self):
        with self.assertRaises(ValueError):
            _response(b'{"facts":[],"facts":[],"unresolved":[]}', self.document)
        self.answer['facts'][0]['kind'] = 'ARBITRARY_BACKGROUND'
        with self.assertRaisesRegex(ValueError, 'KIND_INVALID'):
            self.check_answer(self.answer)

    def test_real_origin_refused_before_source_read(self):
        with self.assertRaisesRegex(ValueError, 'REAL_EXECUTION_NOT_AUTHORIZED'):
            build_development_assessment(data_root='/must-not-read', company_id='anything',
                request_body=b'x', response_body=b'x', source_reference_id='wrong',
                expected_request_sha256='wrong', expected_response_sha256='wrong', origin='LIVE')

    def test_evidence_unicode_is_lossless(self):
        self.answer['facts'][0]['statement'] = 'Seven directors\u037e no fabricated date'
        value, _ = _response(_bytes(self.answer), self.document)
        self.assertEqual(value, self.answer)
        self.assertIn('\u037e', _bytes(value).decode())


if __name__ == '__main__':
    unittest.main()
