"""Two D02 marks the frozen parse cannot see, each read where the filing sets it.

Enphase's footer carries its page number, so no two instances are the same
text and repetition in a scope never finds it; Lumen names each case in its
legal note with an underlined, italic label the bold-only parse does not
count as emphasis. Each rule is checked on its filing, against a control with
the rule off, and on constructed blocks at the edges the filings do not reach.
D03 is built in the same loop and is required not to move.
"""
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_results as route
from vnext import text_coverage
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.normal_period_selection import resolve_period_selection

_DOCUMENTS = {}


def _document(company_id, report_end):
    """The frozen D02 document and its bytes, built once per filing."""
    key = (company_id, report_end)
    if key not in _DOCUMENTS:
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                                 report_end=report_end)
            prepared = prepare_historical_business_text_input(
                repo_root=ROOT, company_id=company_id, metric_id="D02",
                period_selection=selection)
        arguments = prepared["text_arguments"]
        reference = [source for source in arguments["source_references"]
                     if source["source_role"] == "target_primary"][0]
        raw = arguments["raw_bytes_by_id"][reference["raw_asset_id"]]
        document = text_coverage.build_text_document(
            raw_bytes=raw, raw_blob=arguments["raw_blobs"][reference["raw_asset_id"]],
            source_reference=reference, expected_company_id=company_id,
            expected_cik=arguments["target"]["entity"], expected_period_end=report_end)
        _DOCUMENTS[key] = (document, raw)
    return _DOCUMENTS[key]


def _sets(proposal):
    return ({c["block_index"]: c["text"] for c in proposal["D02"]["candidates"]},
            {c["block_index"] for c in proposal["D03"]["candidates"]})


class ThePageNumberedFooterTest(unittest.TestCase):

    def test_enphase_s_footer_leaves_and_nothing_else_moves(self):
        document, raw = _document("enphase_energy", "2025-12-31")
        with patch.object(route, "_numbered_page_footers", lambda **_: set()):
            before, d03_before = _sets(route.referenced_note_candidates(document=document,
                                                                        raw_bytes=raw))
        after, d03_after = _sets(route.referenced_note_candidates(document=document,
                                                                  raw_bytes=raw))
        self.assertEqual({755}, set(before) - set(after))
        self.assertEqual(set(), set(after) - set(before))
        self.assertTrue(before[755].startswith("Enphase Energy, Inc. | 2025 Form 10-K |"))
        self.assertEqual(d03_before, d03_after)

    @staticmethod
    def _blocks(texts):
        return [{"text": text} for text in texts]

    def test_a_numbered_block_needs_three_pages_and_a_recurring_neighbour(self):
        """The edges no filing here reaches, built so the rule's two halves each bite."""
        pages = ["Registrant | Form 10-K | %d" % page for page in (41, 42, 43)]
        texts = ["Opening paragraph that occurs once.", pages[0], "Table of Contents",
                 "Note 7 | 12", "A paragraph about Note 7.", pages[1], "Table of Contents",
                 "Another paragraph.", pages[2], "Table of Contents"]
        found = route._numbered_page_footers(blocks=self._blocks(texts), start=0,
                                             stop=len(texts))
        self.assertEqual({1, 5, 8}, found)
        # Two pages are not enough to call a stem a footer, even beside a
        # neighbour that recurs on every page.
        texts = [pages[0], "Table of Contents", "One paragraph.", pages[1], "Table of Contents",
                 "Another paragraph.", "Table of Contents"]
        found = route._numbered_page_footers(blocks=self._blocks(texts), start=0,
                                             stop=len(texts))
        self.assertEqual(set(), found)
        # One stem on three pages with no recurring neighbour: a numbered run
        # of the same caption, not a footer.
        lonely = ["Segment | Results | %d" % page for page in (1, 2, 3)]
        texts = [lonely[0], "First unique paragraph.", lonely[1], "Second unique paragraph.",
                 lonely[2], "Third unique paragraph."]
        found = route._numbered_page_footers(blocks=self._blocks(texts), start=0,
                                             stop=len(texts))
        self.assertEqual(set(), found)


class TheUnderlinedCaseLabelTest(unittest.TestCase):

    def test_blum_is_admitted_from_its_own_span_and_nothing_else_moves(self):
        document, raw = _document("lumen_technologies", "2025-12-31")
        after, d03_after = _sets(route.referenced_note_candidates(document=document,
                                                                  raw_bytes=raw))
        frozen = route._note_heading
        with patch.object(route, "_note_heading",
                          lambda document, section, block, raw_bytes=None:
                          frozen(document, section, block)):
            before, d03_before = _sets(route.referenced_note_candidates(document=document,
                                                                        raw_bytes=raw))
        self.assertEqual({3400}, set(after) - set(before))
        self.assertEqual(set(), set(before) - set(after))
        self.assertEqual("Blum", after[3400])
        self.assertEqual(d03_before, d03_after)

    def test_without_the_filing_s_bytes_the_label_is_not_a_heading(self):
        """The underline is read from the span, not guessed from the text."""
        document, raw = _document("lumen_technologies", "2025-12-31")
        block = document["blocks"][3400]
        section = next(candidate["section_id"] for candidate in route.referenced_note_candidates(
            document=document, raw_bytes=raw)["D02"]["candidates"]
            if candidate["block_index"] == 3400)
        self.assertTrue(route._note_heading(document, section, block, raw_bytes=raw))
        self.assertFalse(route._note_heading(document, section, block))
        self.assertFalse(route._note_heading(document, "ITEM_8", block, raw_bytes=raw))


if __name__ == "__main__":
    unittest.main()
