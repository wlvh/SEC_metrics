from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'current-390-d01-integration-20261003'))
import current_view as v


class MarriottB03ReceivingViewTest(unittest.TestCase):
    def setUp(self):
        self.delta = v.read(HERE/'delta.json')
        self.checked = v.read(HERE/'mechanical-summary.json')
        self.original = v.load_current_view(include_jpm_reviewed=True)

    def apply(self, delta=None, checked=None):
        rows = {(r['company_id'], r['metric_id']): deepcopy(r) for r in self.original['rows']}
        v.apply_marriott_b03_delta(rows, delta or self.delta, checked or self.checked)
        return rows

    def test_same_result_receives_actual_later_run_with_limited_source_credit(self):
        before = deepcopy(self.original)
        rows = self.apply()
        row = rows[('marriott_international', 'B03')]
        self.assertEqual(390, len(rows))
        self.assertEqual(self.delta['native_result']['result_id'], row['implementation_identity']['result_id'])
        self.assertEqual(self.checked['mechanical_result']['run_id'], row['implementation_identity']['run_id'])
        self.assertFalse(row['economic_all_amortization_scope_proven'])
        self.assertFalse(row['formal_adoption_or_active_credit'])
        self.assertEqual(before, self.original)
        for r in before['rows']:
            key = (r['company_id'], r['metric_id'])
            if key != ('marriott_international', 'B03'):
                self.assertEqual(rows[key], r)

    def test_old_run_does_not_inherit_repair_or_receipt(self):
        delta = deepcopy(self.delta)
        delta['current_row']['implementation_identity']['run_id'] = delta['prior_run_id']
        with self.assertRaisesRegex(ValueError, 'PROOF_INVALID'):
            self.apply(delta)

    def test_wrong_value_period_or_unapproved_da_amount_refused(self):
        for kind in ['value','period','scope','economic']:
            with self.subTest(kind=kind):
                delta = deepcopy(self.delta)
                if kind == 'value': delta['current_row']['value'] = '0.99'
                if kind == 'period': delta['current_row']['source_period']['fiscal_year'] = 2024
                if kind == 'scope': delta['repair_admission']['selected_DA_usd'] = '593000000'
                if kind == 'economic': delta['repair_admission']['economic_all_amortization_proven'] = True
                with self.assertRaises(ValueError): self.apply(delta)

    def test_other_company_or_failed_receipt_does_not_clear_coordinate(self):
        for kind in ['company','receipt','unchanged']:
            with self.subTest(kind=kind):
                delta, checked = deepcopy(self.delta), deepcopy(self.checked)
                if kind == 'company': delta['current_row']['company_id'] = 'ford_motor_company'
                if kind == 'receipt': checked['mechanical_result']['receipt']['status'] = 'FAILED'
                if kind == 'unchanged': checked['original_files_unchanged'] = False
                with self.assertRaises(ValueError): self.apply(delta, checked)

    def test_actual_reader_requires_complete_source_proof_set(self):
        delta = deepcopy(self.delta)
        delta['proof_file_sha256'].pop(next(iter(delta['proof_file_sha256'])))
        original_read = v.read
        with patch.object(v, 'read', side_effect=lambda p: delta if p == HERE/'delta.json' else original_read(p)):
            with self.assertRaisesRegex(ValueError, 'REQUIRED_PROOF_SET_CHANGED'):
                v.load_current_view(include_marriott_b03_reviewed=True)

    def test_actual_reader_cross_checks_uri_repair_and_cold_run(self):
        path = v.BASE/'b03-marriott-contract-exclusion-20261001/exercise-repair.json'
        altered = v.read(path)
        altered['tested_module_sha256'] = '0'*64
        original_read = v.read
        with patch.object(v, 'read', side_effect=lambda p: altered if p == path else original_read(p)):
            with self.assertRaisesRegex(ValueError, 'ADMISSION_IDENTITY_CHANGED'):
                v.load_current_view(include_marriott_b03_reviewed=True)

    def test_actual_reader_default_and_shared_compatibility_are_preserved(self):
        default = v.load_current_view()
        self.assertNotIn('selected_saved_scope_Marriott_B03_run_refresh', default)
        before = next(r for r in default['rows'] if r['company_id']=='marriott_international' and r['metric_id']=='B03')
        self.assertEqual(before['implementation_identity']['run_id'], self.delta['prior_run_id'])
        new = v.load_current_view(include_jpm_reviewed=True, include_marriott_b03_reviewed=True)
        self.assertEqual(390, new['coordinate_count'])
        self.assertEqual(17, new['selected_known_defect_coordinate_count'])
        self.assertFalse(new['all390_acceptance'])
        self.assertEqual(1, new['selected_saved_scope_Marriott_B03_run_refresh'])
