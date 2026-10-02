from copy import deepcopy
import unittest
from unittest.mock import patch

import current_view
from current_view import BASE, PARENT, CHECKED_PATH, assemble, read


class CurrentViewTest(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.parent = read(PARENT)
        self.delta = read(Path(__file__).with_name('delta.json'))
        self.defects = read(BASE / 'known_result_defects.json')
        self.checked = read(CHECKED_PATH)

    def view(self, delta=None, defects=None):
        return assemble(self.parent, [], delta or self.delta, defects or self.defects, self.checked)

    def real_load(self, changed_delta):
        from pathlib import Path
        target = Path(current_view.__file__).with_name('delta.json')
        original_read = current_view.read
        def altered_read(path):
            return changed_delta if path == target else original_read(path)
        with patch.object(current_view, 'read', side_effect=altered_read):
            return current_view.load_current_view()

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

    def test_successor_release_does_not_clear_selected_original_bad_identity(self):
        defects = deepcopy(self.defects)
        defect = next(d for d in defects['defects'] if d['company_id'] == 'pfizer' and d['metric_id'] == 'E01')
        defect['released'] = [{'result_id': 'sha256:' + 'a' * 64, 'scope': 'separately verified successor'}]
        row = next(r for r in self.view(defects=defects)['rows'] if r['company_id'] == 'pfizer' and r['metric_id'] == 'E01')
        self.assertIsNone(row['value'])
        self.assertEqual('WITHHELD_KNOWN_RESULT_DEFECT', row['current_display_status'])

    def test_real_reader_refuses_valid_other_company_receipt(self):
        delta = deepcopy(self.delta)
        first, other = delta['changed_coordinates']
        first['mechanical_receipt'] = deepcopy(other['mechanical_receipt'])
        first['mechanical_receipt_id'] = other['mechanical_receipt_id']
        with self.assertRaisesRegex(ValueError, 'D01_DELTA_VALIDATION_IDENTITY_INVALID'):
            self.real_load(delta)

    def test_real_reader_refuses_new_result_paired_with_old_run(self):
        delta = deepcopy(self.delta)
        item = delta['changed_coordinates'][0]
        prior = next(row for row in self.parent['rows'] if row['company_id'] == item['company_id'] and row['metric_id'] == 'D01')
        item['current_row']['implementation_identity']['run_id'] = prior['implementation_identity']['run_id']
        with self.assertRaisesRegex(ValueError, 'D01_DELTA_VALIDATION_IDENTITY_INVALID'):
            self.real_load(delta)

    def test_real_reader_refuses_other_company_native_result(self):
        delta = deepcopy(self.delta)
        first, other = delta['changed_coordinates']
        for field in ('result_id', 'content_review_result_id', 'mechanical_receipt', 'mechanical_receipt_id', 'native_result'):
            first[field] = deepcopy(other[field])
        first['current_row']['implementation_identity'] = deepcopy(other['current_row']['implementation_identity'])
        for field in ('value', 'unit', 'quality', 'applicability', 'reason_code'):
            first['current_row'][field] = other['current_row'][field]
        with self.assertRaisesRegex(ValueError, 'D01_DELTA_VALIDATION_IDENTITY_INVALID'):
            self.real_load(delta)

    def test_required_mechanical_proof_cannot_be_omitted(self):
        delta = deepcopy(self.delta)
        del delta['proof_file_sha256'][str(CHECKED_PATH.relative_to(current_view.ROOT))]
        with self.assertRaisesRegex(ValueError, 'D01_REQUIRED_PROOF_SET_CHANGED'):
            self.real_load(delta)


if __name__ == '__main__':
    unittest.main()
