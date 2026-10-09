"""Finite HTML layout cases for the pinned E01 reader/guard pair."""
from pathlib import Path
from unittest.mock import patch
import unittest

from vnext.e01_item_text_28_v2 import headed_item_codes, item_text
from vnext.e01_header_document_guard_28_v2 import check_document_header_items

ROOT = Path(__file__).resolve().parents[2]
CODES = {'1.01', '2.01', '8.01'}


def document(between):
    return ('<html><body><div>SEE' + between +
            'Item 2.01 Completion of Acquisition'
            '<p>The issuer completed the transaction.</p>'
            'SIGNATURES</div></body></html>').encode()


class E01LayoutSuccessorFastTest(unittest.TestCase):
    def test_removed_box_and_laid_out_hidden_box_have_distinct_context(self):
        for between in ('<div hidden>removed</div>',
                        '<div style="display:none">removed</div>',
                        '<span hidden>' + 'removed '*50 + '</span>', '<br hidden>'):
            with self.subTest(removed=between):
                self.assertEqual(set(), headed_item_codes(raw_bytes=document(between)))
        for between in ('<div style="visibility:hidden">blank</div>',
                        '<div style="opacity:0">blank</div>',
                        '<div aria-hidden="true">blank</div>'):
            with self.subTest(laid_out=between):
                raw = document(between)
                self.assertEqual({'2.01'}, headed_item_codes(raw_bytes=raw))
                with self.assertRaisesRegex(ValueError, 'HEADED_BUT_NOT_LISTED:synthetic:2.01'):
                    check_document_header_items(raw_bytes=raw, listed_item_codes=[],
                        candidate_item_codes=CODES, accession='synthetic')
                self.assertEqual(['2.01'], check_document_header_items(raw_bytes=raw,
                    listed_item_codes=['2.01'], candidate_item_codes=CODES, accession='synthetic'))
                parsed = item_text(raw_bytes=raw, item_code='2.01')
                self.assertIn('The issuer completed the transaction.', parsed['text'])
                self.assertEqual('SIGNATURES', parsed['end_marker'])
                self.assertNotIn('blank', parsed['text'])

    def test_removed_parent_does_not_restore_descendant_layout(self):
        raw = document('<div hidden><div style="visibility:hidden">blank</div></div>')
        self.assertEqual(set(), headed_item_codes(raw_bytes=raw))

    def test_guard_and_item_end_share_reference_context(self):
        raw = ('<p>Item 1.01 Entry into a Material Definitive Agreement.</p>'
               '<p>The issuer signed an acquisition agreement.</p>'
               '<p>SEE<br>Item 2.01 Completion of Acquisition.</p>'
               '<p>SIGNATURES</p>').encode()
        self.assertEqual({'1.01'}, headed_item_codes(raw_bytes=raw))
        parsed = item_text(raw_bytes=raw, item_code='1.01')
        self.assertEqual('SIGNATURES', parsed['end_marker'])
        self.assertIn('SEE Item 2.01', parsed['text'])

    def test_hidden_or_linked_heading_cannot_create_a_candidate(self):
        raw = ('<p><a href="#x">Item 2.01 Completion of Acquisition.</a></p>'
               '<h2 hidden>Item 8.01 Other Events.</h2>'
               '<p>Item 2.02 Results of Operations.</p>').encode()
        self.assertEqual({'2.02'}, headed_item_codes(raw_bytes=raw))


class E01LayoutSuccessorMaterialTest(unittest.TestCase):
    def test_saved_positive_and_empty_inputs_keep_source_identity_and_coverage(self):
        from vnext import ordinary_e01_item_text_input_v2 as old
        from vnext import ordinary_e01_item_text_input_v3 as new
        for company, count in [('enphase_energy', 0), ('pfizer', 3)]:
            with self.subTest(company=company):
                prior = old.prepare_current_e01_item_text(repo_root=ROOT, company_id=company)
                with patch.object(new, 'check_document_header_items', wraps=check_document_header_items) as checked:
                    current = new.prepare_current_e01_item_text(repo_root=ROOT, company_id=company)
                self.assertEqual(len(current['event_filings']), checked.call_count)
                self.assertEqual(prior['items'], current['items'])
                self.assertEqual(prior['header_document_checks'], current['header_document_checks'])
                self.assertEqual(count, current['candidate_count'])
                self.assertEqual('ORDINARY_E01_SOURCE_BOUND_ITEM_TEXT_V3', current['record_type'])
                self.assertNotEqual(prior['input_id'], current['input_id'])
                self.assertEqual('NOT_PERFORMED', current['semantic_confirmation_status'])
                self.assertFalse(current['metric_result_created'])
                with self.assertRaisesRegex(ValueError, 'SOURCE_REPLAY_CHANGED'):
                    new.verify_current_e01_item_text(candidate=prior, repo_root=ROOT, company_id=company)


if __name__ == '__main__':
    unittest.main()
