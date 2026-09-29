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
            _visible_801_section(b'<html><body>Item 8.01 Other Events. First. '
                                 b'Item 8.01 Other Events. Second.</body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_HEADING_MISSING_OR_AMBIGUOUS'):
            _visible_801_section(b'<html><body>Item 8.01 of this report was '
                                 b'mentioned before Item 8.01 Other Events.'
                                 b'</body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_SECTION_EMPTY'):
            _visible_801_section(b'<html><body>Item 8.01 Other Events.'
                                 b' Item 9.01 Financial Statements and Exhibits.'
                                 b'</body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_SECTION_END_UNPROVEN'):
            _visible_801_section(b'<html><body>Item 8.01 Other Events. '
                                 b'A reported transaction.</body></html>')
        with self.assertRaisesRegex(ValueError,
                'E01_ITEM_SOURCE_ITEM_801_BOUNDARY_AMBIGUOUS'):
            _visible_801_section(b'<html><body>Item 8.01 Other Events. '
                                 b'See Item 1.01 of this report. '
                                 b'Item 9.01 Financial Statements and Exhibits.'
                                 b'</body></html>')


if __name__ == '__main__':
    unittest.main()
