"""Output shape changes cannot drop facts, sources, time or uncertainty."""
import copy
import unittest

from tools.c02_development_response_codec import compact, expand


class C02DevelopmentResponseCodecTest(unittest.TestCase):
    def answer(self):
        return {'facts': [{'kind': 'board_membership', 'statement': '  Alice is a director.  ',
            'source_blocks': [3, 5], 'stated_time': 'CURRENT_IN_FILING'},
            {'kind': 'board_membership', 'statement': 'Bob formerly served; date unknown.',
             'source_blocks': [7], 'stated_time': 'FORMER; UNKNOWN_DATE'}],
            'unresolved': [{'source_blocks': [9], 'reason': 'Year-end roster not established.'}]}

    def test_all_fields_uncertainty_and_whitespace_roundtrip(self):
        answer = self.answer()
        self.assertEqual(answer, expand(compact(answer)))
        self.assertEqual(1, len(compact(answer)['kinds']))
        self.assertEqual(2, len(compact(answer)['times']))

    def test_wrong_reference_boolean_and_duplicate_dictionary_reject(self):
        for kind in ['kind', 'time', 'boolean', 'dictionary']:
            value = copy.deepcopy(compact(self.answer()))
            if kind == 'kind': value['facts'][0][0] = 9
            elif kind == 'time': value['facts'][0][3] = -1
            elif kind == 'boolean': value['facts'][0][0] = True
            else: value['kinds'].append(value['kinds'][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError): expand(value)

    def test_unsupported_fields_and_over_limit_are_not_silently_cut(self):
        answer = self.answer()
        answer['facts'][0]['new_field'] = 'must not disappear'
        with self.assertRaisesRegex(ValueError, 'FIELDS_INVALID'): compact(answer)
        answer = self.answer()
        answer['facts'] *= 33
        with self.assertRaisesRegex(ValueError, 'FACT_LIMIT'): compact(answer)


if __name__ == '__main__':
    unittest.main()
