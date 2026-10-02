"""Body/header disagreement is stopped by the explicit ordinary E01 successor."""
from pathlib import Path
from unittest.mock import patch
import unittest

from vnext.e01_header_document_guard_28_v1 import (
    check_document_header_items, headed_item_codes)


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = {'1.01', '2.01', '8.01'}


def html(*paragraphs):
    return ('<html><body>' + ''.join('<p>' + p + '</p>' for p in paragraphs)
            + '</body></html>').encode('utf-8')


class E01HeaderDocumentGuardFastTest(unittest.TestCase):
    def test_invisible_layout_and_line_breaks_do_not_break_the_same_block_reference(self):
        for between in ('<br style="display:none">', '<br hidden>',
                        '<hr hidden>', '<div hidden>not displayed</div>',
                        '<h2 style="display:none">not displayed</h2>',
                        '<span hidden>' + ('not displayed ' * 20) + '</span>', '<br>'):
            raw = ('<html><body><p>SEE ' + between +
                   'Item 2.01 Completion of Acquisition.</p></body></html>').encode()
            with self.subTest(between=between):
                self.assertEqual(set(), headed_item_codes(raw_bytes=raw))
                self.assertEqual([], check_document_header_items(raw_bytes=raw,
                    listed_item_codes=[], candidate_item_codes=CANDIDATES,
                    accession='synthetic'))
        raw = ('<html><body><p><span hidden>SEE</span><br>'
               'Item 2.01 Completion of Acquisition.</p></body></html>').encode()
        self.assertEqual({'2.01'}, headed_item_codes(raw_bytes=raw))

    def test_reference_context_is_visible_and_in_the_same_block(self):
        title = '<h2>Item 2.01 Completion of Acquisition or Disposition of Assets.</h2>'
        for prefix in ('<p style="display:none">SEE</p>',
                       '<p>Location: Portland, OR</p>',
                       '<p>Location: Portland, or</p>',
                       '<p>see</p>'):
            raw = ('<html><body>' + prefix + title +
                   '<p>The company completed an acquisition.</p></body></html>').encode()
            with self.subTest(prefix=prefix):
                self.assertEqual({'2.01'}, headed_item_codes(raw_bytes=raw))
                with self.assertRaisesRegex(ValueError, 'HEADED_BUT_NOT_LISTED:synthetic:2.01'):
                    check_document_header_items(raw_bytes=raw,
                        listed_item_codes=[], candidate_item_codes=CANDIDATES,
                        accession='synthetic')
        for prefix in ('<span>SEE </span>', '<b>See</b> ',
                       '<span style="display:none">SECRET</span><b>See</b> '):
            raw = ('<html><body><p>' + prefix +
                   'Item 2.01 Completion of Acquisition.</p></body></html>').encode()
            with self.subTest(inline_prefix=prefix):
                self.assertEqual(set(), headed_item_codes(raw_bytes=raw))
        raw = ('<html><body><p><span style="display:none">SEE</span>'
               'Item 2.01 Completion of Acquisition.</p></body></html>').encode()
        self.assertEqual({'2.01'}, headed_item_codes(raw_bytes=raw))

    def test_unlisted_candidate_and_no_header_claims_stop_by_name(self):
        raw = html('Item 2.01 Completion of Acquisition or Disposition of Assets.',
                   'The company completed an acquisition.', 'SIGNATURES')
        for listed in (['2.02', '7.01', '9.01'], []):
            with self.subTest(listed=listed):
                with self.assertRaisesRegex(ValueError,
                        'ORDINARY_E01_ITEM_HEADED_BUT_NOT_LISTED:synthetic:2.01'):
                    check_document_header_items(raw_bytes=raw,
                        listed_item_codes=listed, candidate_item_codes=CANDIDATES,
                        accession='synthetic')
        self.assertEqual(['2.01'], check_document_header_items(raw_bytes=raw,
            listed_item_codes=['2.01'], candidate_item_codes=CANDIDATES,
            accession='synthetic'))

    def test_contents_reference_hidden_heading_and_non_candidate_do_not_expand_scope(self):
        raw = ('<html><body><p><a href="#x">Item 2.01 Completion of Acquisition.</a></p>'
               '<p style="display:none">Item 8.01 Other Events.</p>'
               '<p>See Item 1.01 Entry into a Material Definitive Agreement.</p>'
               '<p>Item 2.02 Results of Operations and Financial Condition.</p>'
               '<p>Results.</p><p>SIGNATURES</p></body></html>').encode('utf-8')
        self.assertEqual({'2.02'}, headed_item_codes(raw_bytes=raw))
        self.assertEqual(['2.02'], check_document_header_items(raw_bytes=raw,
            listed_item_codes=['9.01'], candidate_item_codes=CANDIDATES,
            accession='synthetic'))


class E01HeaderDocumentGuardMaterialTest(unittest.TestCase):
    def test_saved_positive_and_zero_inputs_use_guard_for_every_filing(self):
        from vnext import ordinary_e01_item_text_input as old
        from vnext import ordinary_e01_item_text_input_v2 as new
        for company, count in (('enphase_energy', 0), ('pfizer', 3)):
            with self.subTest(company=company):
                prior = old.prepare_current_e01_item_text(repo_root=ROOT, company_id=company)
                with patch.object(new, 'check_document_header_items',
                                  wraps=check_document_header_items) as checked:
                    current = new.prepare_current_e01_item_text(repo_root=ROOT, company_id=company)
                self.assertEqual(len(current['event_filings']), checked.call_count)
                self.assertEqual(count, current['candidate_count'])
                self.assertEqual(prior['items'], current['items'])
                self.assertEqual('NOT_PERFORMED', current['semantic_confirmation_status'])
                self.assertFalse(current['metric_result_created'])
                self.assertEqual('ORDINARY_E01_SOURCE_BOUND_ITEM_TEXT_V2', current['record_type'])
                self.assertNotEqual(prior['input_id'], current['input_id'])
                self.assertEqual(len(current['event_filings']),
                                 len(current['header_document_checks']))
                self.assertEqual(current, new.verify_current_e01_item_text(
                    candidate=current, repo_root=ROOT, company_id=company))
                with self.assertRaisesRegex(ValueError, 'SOURCE_REPLAY_CHANGED'):
                    new.verify_current_e01_item_text(candidate=prior,
                        repo_root=ROOT, company_id=company)

    def test_changed_adapter_claims_cannot_bypass_header_source_check(self):
        # Actual saved Pfizer sources are authenticated by real source discovery.
        # Only its returned claim list is deliberately altered; no source is changed.
        from vnext import ordinary_e01_item_text_input_v2 as new
        original = new._event_sources

        def drop_claim(**kwargs):
            claims, sets, filings = original(**kwargs)
            changed = [c for c in claims if c['attributes']['item_code'] != '8.01']
            self.assertLess(len(changed), len(claims))
            return changed, sets, filings

        with patch.object(new, '_event_sources', side_effect=drop_claim):
            with self.assertRaisesRegex(ValueError, 'HEADER_CLAIM_SET_CHANGED'):
                new.prepare_current_e01_item_text(repo_root=ROOT, company_id='pfizer')


if __name__ == '__main__':
    unittest.main()
