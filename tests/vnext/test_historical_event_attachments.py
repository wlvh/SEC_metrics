"""Reviewed attachment declaration guards; all source/approval objects are in memory."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.vnext import historical_event_attachments as attachments


class AttachmentDeclarationTest(unittest.TestCase):
    def setUp(self):
        self.raw = b'<html><a href="ex-99.htm">Exhibit 99</a></html>'
        self.span = self.raw[6:-7]
        self.parent = 'https://www.sec.gov/Archives/edgar/data/1/000000000124000001/primary.htm'
        self.target = self.parent.replace('primary.htm', 'ex-99.htm')
        self.item = {'company_id': 'test_company', 'report_end': '2024-12-31',
            'accession': '0000000001-24-000001', 'parent_url': self.parent,
            'parent_sha256': hashlib.sha256(self.raw).hexdigest(),
            'anchor_start': 6, 'anchor_end': len(self.raw)-7,
            'anchor_sha256': hashlib.sha256(self.span).hexdigest(),
            'literal_href': 'ex-99.htm', 'source_url': self.target,
            'source_role': 'incorporated_EX99', 'item_id': 'test-item', 'maximum_sec_attempts': 1}
        self.requirements = [{'source_url': self.parent, 'accession': self.item['accession'],
            'dependency_class': 'FISCAL_EVENT_FILING', 'primary_cik': '2', 'registrant_cik': '1'}]

    def declare(self, item=None, raw=None, company='test_company', periods=('2024-12-31',)):
        with patch.object(attachments, 'strict_json_file', return_value={'items': [item or self.item]}), \
             patch.object(attachments, '_read_saved', side_effect=[
                 ({'raw': raw or self.raw, 'proof': {'request_attempt_id': 'original-parent'}}, None),
                 (None, 'SAVED_SOURCE_MISSING')]), \
             patch('scripts.vnext.ordinary_source_authority.verify_ordinary_source_proofs') as verify:
            result = attachments.attachment_dependencies(repo_root=Path('/not-a-real-source'),
                company_id=company, requirements=self.requirements, report_ends=periods)
            return result, verify.call_args_list

    def test_one_reviewed_link_retains_parent_registrant_and_successor_boundary(self):
        rows, calls = self.declare()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source_url'], self.target)
        self.assertEqual(rows[0]['registrant_cik'], '1')
        self.assertEqual(rows[0]['primary_cik'], '2')
        self.assertTrue(rows[0]['new_acquisition_required'])
        self.assertEqual(rows[0]['retry_count'], 0)
        self.assertFalse(rows[0]['source_acquisition_credit'])
        self.assertEqual(rows[0]['source_contract_scope'], 'SUCCESSOR_INPUT_ONLY_NO_OLD_REQUEST_OR_RUN_REBINDING')
        self.assertEqual(len(calls), 1)

    def test_unrelated_company_and_window_do_not_receive_dependency(self):
        self.assertEqual(self.declare(company='another_company')[0], [])
        self.assertEqual(self.declare(periods=('2023-12-31',))[0], [])

    def test_changed_parent_or_anchor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PARENT_BYTES_CHANGED'):
            self.declare(raw=self.raw+b'changed')
        item = deepcopy(self.item)
        item['anchor_start'] += 1
        with self.assertRaisesRegex(ValueError, 'ANCHOR_BYTES_CHANGED'):
            self.declare(item=item)

    def test_link_cannot_be_redirected_outside_exact_owner_scope(self):
        item = deepcopy(self.item)
        item['source_url'] = 'https://example.com/ex-99.htm'
        with self.assertRaisesRegex(ValueError, 'TARGET_OUTSIDE_REVIEWED_SCOPE'):
            self.declare(item=item)


if __name__ == '__main__':
    unittest.main()
