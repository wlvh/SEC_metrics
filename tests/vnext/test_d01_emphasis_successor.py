"""Short D01 source-heading and page-boundary counterexamples."""
import unittest

from tests.vnext.test_text_coverage import BODY, annual, binding
from vnext.d01_emphasis_source import build_text_document_admitting_underline
from vnext.risk_signals import risk_factor_headings
from vnext.text_coverage import build_text_document


class D01EmphasisSuccessorTest(unittest.TestCase):
    def test_bridged_period_and_underlined_heading_keep_original_spans(self):
        replacement = ('<p><b>Changes in U</b><span style="font-weight:400">.</span>'
                       '<b>S. law can affect us</b> Further explanation.</p>'
                       '<div><span style="text-decoration:underline">Underlined risk category'
                       '</span></div>')
        args = binding(annual(BODY.replace(
            '<p>A supply constraint could affect production.</p>', replacement)))
        old = build_text_document(**args)
        new = build_text_document_admitting_underline(**args)
        self.assertEqual(['Changes in U'], [h['text'] for h in risk_factor_headings(document=old)['headings']])
        self.assertEqual(['Changes in U.S. law can affect us', 'Underlined risk category'],
                         [h['text'] for h in risk_factor_headings(document=new)['headings']])
        for before, after in zip(old['blocks'], new['blocks']):
            for field in ('block_index', 'text', 'linked', 'raw_start_byte',
                          'raw_end_byte', 'raw_span_sha256'):
                self.assertEqual(before[field], after[field])
        self.assertNotIn('Further explanation', new['blocks'][3]['leading_emphasis']['text'])

    def test_page_split_is_withheld_until_two_raw_spans_can_be_bound(self):
        replacement = ('<p><b>Changes in our operations could</b></p>'
                       '<p>42</p><p><a href="#toc">Table of Contents</a></p>'
                       '<p><b>affect our results.</b></p>')
        args = binding(annual(BODY.replace(
            '<p>A supply constraint could affect production.</p>', replacement)))
        with self.assertRaisesRegex(ValueError, 'D01_MULTISPAN_HEADING_UNSUPPORTED'):
            build_text_document_admitting_underline(**args)

    def test_one_digit_between_separate_headings_is_not_a_page_join(self):
        replacement = ('<p><b>Regulatory Risks</b></p><p>1</p>'
                       '<p><b>other market risks</b></p>')
        args = binding(annual(BODY.replace(
            '<p>A supply constraint could affect production.</p>', replacement)))
        document = build_text_document_admitting_underline(**args)
        self.assertEqual(['Regulatory Risks', 'other market risks'],
                         [row['text'] for row in risk_factor_headings(document=document)['headings']])

if __name__ == '__main__':
    unittest.main()
