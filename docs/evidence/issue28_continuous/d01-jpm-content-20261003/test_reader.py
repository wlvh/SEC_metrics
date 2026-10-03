"""Finite receiver checks for the newly read JPM source, no native reruns."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'current-390-d01-integration-20261003'))
import current_view as view


class JPMReaderTest(unittest.TestCase):
    def test_actual_optional_successor_and_original_scope(self):
        old = view.load_current_view()
        new = view.load_current_view(include_jpm_reviewed=True)
        a = {(r['company_id'], r['metric_id']): r for r in old['rows']}
        b = {(r['company_id'], r['metric_id']): r for r in new['rows']}
        key = ('jpmorgan_chase', 'D01')
        self.assertEqual(set(a), set(b))
        self.assertEqual(len(b), 390)
        self.assertEqual([k for k in a if a[k] != b[k]], [key])
        self.assertEqual(b[key]['implementation_identity']['result_id'], view.JPM_CONTENT_REVIEW_RESULT)
        self.assertEqual(b[key]['source_period'], a[key]['source_period'])
        self.assertEqual(len(b[key]['value'].splitlines()), 56)
        self.assertEqual(old['selected_known_defect_coordinate_count'], 18)
        self.assertEqual(new['selected_known_defect_coordinate_count'], 17)
        self.assertEqual(new['selected_saved_scope_D01_restorations'], 3)
        self.assertFalse(new['all390_acceptance'])
        self.assertFalse(new['production_authorized'])
        self.assertEqual(new['selected_product_scope_pending_count'], old['selected_product_scope_pending_count'])

    def rejection(self, mutate_delta=None, mutate_checked=None):
        parent = view.read(view.PARENT)
        rows = {(r['company_id'], r['metric_id']): deepcopy(r) for r in parent['rows']}
        delta = view.read(view.JPM_DIR / 'delta.json')
        checked = view.read(view.JPM_DIR / 'mechanical-summary.json')
        if mutate_delta:
            mutate_delta(delta)
        if mutate_checked:
            mutate_checked(checked)
        with self.assertRaises(ValueError):
            view.apply_d01_delta(rows, delta, checked, expected_count=1)

    def test_unread_result_cannot_inherit_content_credit(self):
        self.rejection(lambda d: d['changed_coordinates'][0].__setitem__('result_id', 'sha256:' + '0' * 64))

    def test_different_execution_root_cannot_inherit_receipt(self):
        self.rejection(lambda d: d['changed_coordinates'][0]['current_row']['implementation_identity'].__setitem__('semantic_execution_root', '/private/tmp/other-run'))

    def test_open_preview_cannot_replace_mechanical_pass(self):
        self.rejection(lambda d: d['changed_coordinates'][0].__setitem__('mechanical_receipt_status', 'VERIFIED_OPEN_PREVIEW'))

    def test_wrong_receipt_requirement_closure(self):
        self.rejection(mutate_checked=lambda c: c['results'][0]['mechanical_result'].__setitem__('requirement_closure_hash', 'sha256:' + '0' * 64))

    def test_missing_required_reading_hash(self):
        original = view.read
        def changed(path):
            data = original(path)
            if Path(path) == view.JPM_DIR / 'delta.json':
                del data['proof_file_sha256'][next(iter(view.JPM_REQUIRED_PROOF_PATHS))]
            return data
        with patch.object(view, 'read', side_effect=changed), self.assertRaisesRegex(ValueError, 'REQUIRED_PROOF_SET'):
            view.load_current_view(include_jpm_reviewed=True)

    def test_changed_reading_file_bytes(self):
        original = view.digest
        def changed(path):
            if Path(path) == view.JPM_DIR / 'independent-original/conclusion.md':
                return '0' * 64
            return original(path)
        with patch.object(view, 'digest', side_effect=changed), self.assertRaisesRegex(ValueError, 'PROOF_BYTES_CHANGED'):
            view.load_current_view(include_jpm_reviewed=True)


if __name__ == '__main__':
    unittest.main()
