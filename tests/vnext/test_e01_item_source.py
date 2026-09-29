"""Bounded original-body transport for header-listed E01 Item 8.01."""
from pathlib import Path
import tempfile
import unittest

from tests.vnext.test_deterministic_router import (COMPANY_ID,
    EVENT_ACCESSION, TARGET_PERIOD, fixture_sources, make_reference)
from vnext.deterministic_router import (adapt_8k_item_index,
                                        source_set_manifest)
from vnext.e01_item_source import (_visible_801_section,
                                   bound_801_primary_section,
                                   verify_bound_801_primary_section)


class E01ItemSourceTest(unittest.TestCase):
    def test_header_identity_kept_while_original_801_body_is_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = fixture_sources(root=root)
            primary_bytes = (b'<html><body>'
                b'<h2>Item 1.01 Entry into a Material Definitive Agreement</h2>'
                b'<p>The company signed a credit agreement.</p>'
                b'<h2>Item 8.01 Other Events</h2>'
                b'<p>The company announced an acquisition transaction.</p>'
                b'<h2>Item 9.01 Financial Statements and Exhibits</h2>'
                b'<p>Exhibit index.</p></body></html>')
            primary = make_reference(root=root,
                relative='evidence/accession/test-8k-item-section.htm',
                content=primary_bytes,
                source_url=('https://www.sec.gov/Archives/edgar/data/1/'
                            '000000000125000003/test-8k-item-section.htm'),
                accession=EVENT_ACCESSION,
                document_name='test-8k-item-section.htm',
                source_role='fy_8k_primary')
            manifest = source_set_manifest(
                company_id=COMPANY_ID, source_role='fy_8k_item_inventory',
                form_types=['8-K'], fiscal_or_date_window=TARGET_PERIOD,
                discovery_policy='PINNED_SUBMISSIONS_FISCAL_WINDOW_V1',
                inventory_source_reference=fixture['references']['inventory'],
                inventory_bytes=fixture['bytes']['inventory'],
                ordered_source_references=[fixture['references']['hdr'], primary],
                cutoff_timestamp_or_pinned_submissions_attempt=
                    fixture['references']['inventory']['request_attempt_id'])
            claims = adapt_8k_item_index(
                filing_documents=[{
                    'hdr_bytes': fixture['bytes']['hdr'],
                    'hdr_source_reference': fixture['references']['hdr'],
                    'primary_document_bytes': primary_bytes,
                    'primary_source_reference': primary,
                }],
                source_set_manifest=manifest,
                inventory_source_reference=fixture['references']['inventory'],
                inventory_bytes=fixture['bytes']['inventory'])
            selected, = [row for row in claims
                         if row['attributes']['item_code'] == '8.01']
            bound = bound_801_primary_section(
                claim=selected,
                primary_source_reference=primary,
                primary_document_bytes=primary_bytes)
            self.assertEqual(selected['verified_claim_id'],
                             bound['verified_claim_id'])
            self.assertEqual('8-K item 8.01 parsed from hdr.sgml',
                             selected['attributes']['brief'])
            self.assertIn('acquisition transaction', bound['section_text'])
            self.assertNotIn('credit agreement', bound['section_text'])
            self.assertNotIn('Exhibit index', bound['section_text'])
            self.assertFalse(bound['metric_result_created'])
            self.assertEqual(bound, verify_bound_801_primary_section(
                section=bound, claim=selected,
                primary_source_reference=primary,
                primary_document_bytes=primary_bytes))
            with self.assertRaisesRegex(ValueError,
                    'E01_ITEM_SOURCE_SECTION_CHANGED'):
                verify_bound_801_primary_section(
                    section={**bound, 'section_text': 'Item 8.01 Other Events. Wrong.'},
                    claim=selected, primary_source_reference=primary,
                    primary_document_bytes=primary_bytes)
            with self.assertRaisesRegex(ValueError,
                    'Adapter bytes differ from SourceReference'):
                bound_801_primary_section(
                    claim=selected,
                    primary_source_reference=primary,
                    primary_document_bytes=primary_bytes + b' ')
            other, = [row for row in claims
                      if row['attributes']['item_code'] == '1.01']
            with self.assertRaisesRegex(ValueError,
                    'E01_ITEM_SOURCE_ITEM_801_VERIFIED_CLAIM_REQUIRED'):
                bound_801_primary_section(
                    claim=other,
                    primary_source_reference=primary,
                    primary_document_bytes=primary_bytes)

    def test_ambiguous_and_missing_heading_fail_closed(self):
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_HEADING_MISSING_OR_AMBIGUOUS'):
            _visible_801_section(b'<html><body>Item 1.01 Agreement.</body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_HEADING_MISSING_OR_AMBIGUOUS'):
            _visible_801_section(b'<html><body><h2>Item 8.01 Other Events</h2>'
                                 b'<p>First.</p><h2>Item 8.01 Other Events</h2>'
                                 b'<p>Second.</p><h2>Item 9.01 Financial '
                                 b'Statements and Exhibits</h2></body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_HEADING_MISSING_OR_AMBIGUOUS'):
            _visible_801_section(b'<html><body><p>Item 8.01 Other Events. '
                                 b'Its contents are inline prose.</p>'
                                 b'<h2>Item 9.01 Financial Statements and '
                                 b'Exhibits</h2></body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_SECTION_EMPTY'):
            _visible_801_section(b'<html><body><h2>Item 8.01 Other Events</h2>'
                                 b'<h2>Item 9.01 Financial Statements and '
                                 b'Exhibits</h2></body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_SECTION_END_UNPROVEN'):
            _visible_801_section(b'<html><body><h2>Item 8.01 Other Events</h2>'
                                 b'<p>A reported transaction.</p></body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_BOUNDARY_AMBIGUOUS'):
            _visible_801_section(b'<html><body><h2>Item 8.01 Other Events</h2>'
                                 b'<p>A reported transaction.</p>'
                                 b'<h2>Item 1.01 Entry into a Material Definitive '
                                 b'Agreement</h2><h2>Item 9.01 Financial '
                                 b'Statements and Exhibits</h2></body></html>')

    def test_body_cross_references_are_not_section_boundaries(self):
        section = _visible_801_section(
            b'<html><body><h2>Item 8.01 Other Events</h2>'
            b'<p>For related documents see Item 9.01 Financial Statements '
            b'and Exhibits below; SIGNATURES follow.</p>'
            b'<p>Item 9.01 Financial Statements and Exhibits.</p>'
            b'<p>We signed an acquisition agreement.</p>'
            b'<h2>Item 9.01 Financial Statements and Exhibits</h2>'
            b'</body></html>')
        self.assertIn('We signed an acquisition agreement.',
                      section['section_text'])
        self.assertIn('SIGNATURES follow', section['section_text'])
        self.assertIn('Item 9.01 Financial Statements and Exhibits.',
                      section['section_text'])
        self.assertTrue(section['section_text'].endswith(
            'We signed an acquisition agreement.'))
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_BOUNDARY_AMBIGUOUS'):
            _visible_801_section(
                b'<html><body><h2>Item 8.01 Other Events</h2>'
                b'<p><strong>Item 9.01 Financial Statements and Exhibits'
                b'</strong></p><p>Possible later 8.01 text.</p>'
                b'<h2>Item 9.01 Financial Statements and Exhibits</h2>'
                b'</body></html>')
        bold_paragraph = _visible_801_section(
            b'<html><body><p><strong>Item 8.01 Other Events</strong></p>'
            b'<p>We signed an acquisition agreement.</p>'
            b'<p><strong>Item 9.01 Financial Statements and Exhibits'
            b'</strong></p></body></html>')
        self.assertIn('acquisition agreement', bold_paragraph['section_text'])
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_BOUNDARY_AMBIGUOUS'):
            _visible_801_section(
                b'<html><body><p><strong>Item 8.01 Other Events</strong></p>'
                b'<p>First sentence.</p><p><strong>Item 9.01 Financial '
                b'Statements and Exhibits</strong></p><p>More 8.01 text.</p>'
                b'<p><strong>Item 9.01 Financial Statements and Exhibits'
                b'</strong></p></body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_BOUNDARY_AMBIGUOUS'):
            _visible_801_section(
                b'<html><body><p><strong>Item 8.01 Other Events</strong></p>'
                b'<p>See the exhibit discussion below:</p>'
                b'<p><strong>Item 9.01 Financial Statements and Exhibits'
                b'</strong></p><p>We signed an acquisition agreement.</p>'
                b'<h2>Item 9.01 Financial Statements and Exhibits</h2>'
                b'</body></html>')

    def test_hidden_or_unproven_visibility_does_not_create_section(self):
        for hidden in (
                b'<script>Item 8.01 Other Events. Hidden words. Item 9.01 '
                b'Financial Statements and Exhibits.</script>',
                b'<div style="display:none"><h2>Item 8.01 Other Events</h2>'
                b'<p>Hidden words.</p><h2>Item 9.01 Financial Statements '
                b'and Exhibits</h2></div>',
                b'<div hidden><h2>Item 8.01 Other Events</h2>'
                b'<p>Hidden words.</p><h2>Item 9.01 Financial Statements '
                b'and Exhibits</h2></div>',
                b'<div aria-hidden="true"><h2>Item 8.01 Other Events</h2>'
                b'<p>Hidden words.</p><h2>Item 9.01 Financial Statements '
                b'and Exhibits</h2></div>'):
            with self.subTest(hidden=hidden[:50]), self.assertRaisesRegex(
                    ValueError,
                    'E01_ITEM_SOURCE_ITEM_801_HEADING_MISSING_OR_AMBIGUOUS'):
                _visible_801_section(b'<html><body>' + hidden +
                                     b'<p>Visible document lacks 8.01.</p>'
                                     b'</body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_VISIBILITY_UNPROVEN'):
            _visible_801_section(b'<html><head><style>.hide {display:none}'
                                 b'</style></head><body><h2>Item 8.01 Other '
                                 b'Events</h2><p>A report.</p><h2>Item 9.01 '
                                 b'Financial Statements and Exhibits</h2>'
                                 b'</body></html>')
        for hidden_style in (b'opacity:0.0', b'color:transparent'):
            with self.subTest(style=hidden_style), self.assertRaisesRegex(
                    ValueError, 'E01_ITEM_SOURCE_VISIBILITY_UNPROVEN'):
                _visible_801_section(
                    b'<html><body><h2>Item 8.01 Other Events</h2>'
                    b'<p style="' + hidden_style + b'">Hidden acquisition '
                    b'assertion.</p><p>Visible disclosure.</p>'
                    b'<h2>Item 9.01 Financial Statements and Exhibits</h2>'
                    b'</body></html>')


if __name__ == '__main__':
    unittest.main()
