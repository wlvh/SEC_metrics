from copy import deepcopy
import unittest

from current_view import BASE, PARENT, assemble, read


class CurrentViewTest(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.parent = read(PARENT)
        self.delta = read(Path(__file__).with_name('delta.json'))
        self.defects = read(BASE / 'known_result_defects.json')

    def view(self, delta=None, defects=None):
        return assemble(self.parent, [], delta or self.delta, defects or self.defects)

    def test_two_fixed_results_selected_without_releasing_original_bad_ids(self):
        result = self.view()
        self.assertEqual(390, result['coordinate_count'])
        self.assertEqual(17, result['selected_known_defect_coordinate_count'])
        self.assertFalse(result['all390_acceptance'])
        for replacement in self.delta['changed_coordinates']:
            row = next(r for r in result['rows'] if r['company_id'] == replacement['company_id'] and r['metric_id'] == 'D01')
            self.assertEqual(replacement['result_id'], row['implementation_identity']['result_id'])
            self.assertEqual('SAVED_SCOPE_CONTENT_AND_MECHANICAL_RECEIPT_VALIDATED', row['selected_result_validation_scope'])

    def test_known_bad_unchanged_result_is_withheld(self):
        row = next(r for r in self.view()['rows'] if r['company_id'] == 'pfizer' and r['metric_id'] == 'E01')
        self.assertIsNone(row['value'])
        self.assertEqual('WITHHELD_KNOWN_RESULT_DEFECT', row['current_display_status'])

    def test_wrong_content_read_identity_cannot_grant_credit(self):
        delta = deepcopy(self.delta)
        delta['changed_coordinates'][0]['content_review_result_id'] = delta['changed_coordinates'][0]['prior_result_id']
        with self.assertRaisesRegex(ValueError, 'D01_DELTA_VALIDATION_IDENTITY_INVALID'):
            self.view(delta)

    def test_failed_receipt_or_changed_period_cannot_grant_credit(self):
        for kind in ('receipt', 'period'):
            with self.subTest(kind=kind):
                delta = deepcopy(self.delta)
                if kind == 'receipt':
                    delta['changed_coordinates'][0]['mechanical_receipt_status'] = 'NOT_RUN'
                else:
                    delta['changed_coordinates'][0]['current_row']['source_period']['fiscal_year'] = 2024
                with self.assertRaises(ValueError):
                    self.view(delta)

    def test_duplicate_coordinate_does_not_fill_denominator(self):
        delta = deepcopy(self.delta)
        delta['changed_coordinates'][1] = deepcopy(delta['changed_coordinates'][0])
        with self.assertRaisesRegex(ValueError, 'D01_DELTA_COORDINATE_INVALID'):
            self.view(delta)

    def test_changed_display_cannot_keep_native_result_credit(self):
        delta = deepcopy(self.delta)
        delta['changed_coordinates'][0]['current_row']['value'] = 'A made-up risk title'
        with self.assertRaisesRegex(ValueError, 'D01_DELTA_VALIDATION_IDENTITY_INVALID'):
            self.view(delta)

    def test_tampered_native_body_cannot_keep_original_result_identity(self):
        delta = deepcopy(self.delta)
        delta['changed_coordinates'][0]['native_result']['value'] = 'A made-up risk title'
        with self.assertRaises(ValueError):
            self.view(delta)


if __name__ == '__main__':
    unittest.main()
