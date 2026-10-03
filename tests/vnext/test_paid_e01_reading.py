"""A paid format pass cannot replace either direction of an E01 reading."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from read_e01_confirmed import reference_count


class PaidE01ReadingTest(unittest.TestCase):
    def fixture(self):
        text = 'The registrant agreed to acquire the entire business.'
        item = {'item_id': 'item', 'accession': 'filing', 'item_code': '2.01',
                'text': text, 'text_sha256': 'sha256:' + hashlib.sha256(text.encode()).hexdigest()}
        return ({'items': [item]}, {'item': 'REPORTS_A_TRANSACTION'},
                {'filing_date': [('filing', '2.01')], 'report_date': [('filing', '2.01')]},
                {'contract_check': 'PASSED', 'fits_the_output_ceiling': True, 'disagreements': []})

    def test_confirmed_value_requires_exact_two_direction_coverage(self):
        args = self.fixture()
        self.assertEqual(reference_count(*args), (1, None))
        for basis in ('filing_date', 'report_date'):
            census = {k: list(v) for k, v in args[2].items()}
            census[basis].append(('unread-filing', '8.01'))
            self.assertEqual(reference_count(args[0], args[1], census, args[3]),
                             (None, 'INDEPENDENT_CENSUS_AND_REQUEST_DIFFER'))

    def test_unknown_original_never_becomes_zero(self):
        request, refs, census, paid = self.fixture()
        refs['item'] = 'CANNOT_TELL_FROM_THE_ITEM_TEXT'
        self.assertEqual(reference_count(request, refs, census, paid),
                         (None, 'REFERENCE_ITEM_DOES_NOT_SETTLE_IT'))

    def test_model_disagreement_cannot_be_granted_by_equal_count(self):
        request, refs, census, paid = self.fixture()
        paid['disagreements'] = [{'item': 'item'}]
        self.assertEqual(reference_count(request, refs, census, paid),
                         (None, 'PAID_DECISIONS_DIFFER_FROM_PRECALL_READING'))

    def test_missing_reference_or_changed_text_refuses(self):
        request, refs, census, paid = self.fixture()
        with self.assertRaisesRegex(ValueError, 'REFERENCE_DOES_NOT_COVER_REQUEST_EXACTLY'):
            reference_count(request, {}, census, paid)
        request['items'][0]['text'] += ' unbound alteration'
        with self.assertRaisesRegex(ValueError, 'REFERENCE_ITEM_TEXT_CHANGED'):
            reference_count(request, refs, census, paid)

    def test_rejected_paid_contract_never_grants(self):
        request, refs, census, paid = self.fixture()
        paid['contract_check'] = 'REFUSED'
        self.assertEqual(reference_count(request, refs, census, paid),
                         (None, 'PAID_CONTRACT_NOT_PASSED'))


if __name__ == '__main__':
    unittest.main()
