"""D01: a heading the filing runs over a page is refused by name, not joined.

``historical_text_emphasis.split_heading_requires_multispan`` recognises one
layout - an unterminated heading, the page number, the linked "Table of
Contents" line, a lower-case continuation - and the document builder stops
with D01_MULTISPAN_HEADING_UNSUPPORTED. A heading so laid out cannot be one
verbatim excerpt of one raw span: the bytes between its halves hold the page
number and the contents line. An earlier version joined the halves under one
span from the first half's start to the second half's end; the claim's text
then was not the text of its own span, which these cases show on the filing.

The real cases are Southwest's FY2022 and FY2023 reports, read from the
acquisition's export; Southwest FY2025 and Enphase FY2025 put a category label
at the foot of a page and the first heading at the head of the next - two
headings, which stay two and are built as the batch built them. The documents
are rebuilt from the bytes and the records the batch's Runs carried
(``page-split/source-records.json``). Zero calls.
"""
import copy
import html
import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_text_coverage import BODY, annual, binding
from tools.acceptance_readings import saved_bytes
from vnext import historical_risk_results as route
from vnext import historical_text_emphasis as builder
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.risk_signals import risk_factor_headings
from vnext.text_coverage import TextCoverageError

RECORDS = "docs/evidence/issue47_history/d01-risk-headings/page-split/source-records.json"
REFUSAL = "D01_MULTISPAN_HEADING_UNSUPPORTED"
# The document each batch Run read, by the identity its candidate recorded
# (frame4, closure 500ddf5f). The two filings without the layout must be built
# exactly so.
BATCH_DOCUMENTS = {
    "southwest-2025": "page-boundary/measured-after.json",
    "enphase-2025": "page-boundary/measured-after.json",
}
_BUILT = {}


def _inputs(label):
    filing = json.loads((ROOT / RECORDS).read_text(encoding="utf-8"))["filings"][label]
    raw = saved_bytes(repo_root=ROOT, relative=filing["raw_blob"]["storage_uri"])
    return filing, raw


def _arguments(label):
    filing, raw = _inputs(label)
    return dict(raw_bytes=raw, raw_blob=filing["raw_blob"],
                source_reference=filing["source_reference"],
                expected_company_id=filing["source_reference"]["company_id"],
                expected_cik=filing["calculation_target"]["entity"],
                expected_period_end=filing["calculation_target"]["period_end"])


def _document(label, *, refuse=True):
    """The successor's document; with ``refuse=False`` the layout check is stubbed out."""
    key = (label, refuse)
    if key not in _BUILT:
        if refuse:
            _BUILT[key] = builder.build_text_document_admitting_underline(**_arguments(label))
        else:
            original = builder.split_heading_requires_multispan
            builder.split_heading_requires_multispan = lambda **_: False
            try:
                _BUILT[key] = builder.build_text_document_admitting_underline(**_arguments(label))
            finally:
                builder.split_heading_requires_multispan = original
    return copy.deepcopy(_BUILT[key])


def _headings(document):
    return [heading["text"] for heading in risk_factor_headings(document=document)["headings"]]


def _layouts(document):
    """Every place in Item 1A where the recognised layout starts."""
    scope = document["sections"]["ITEM_1A"]["candidates"][0]
    found = []
    for index in range(scope["start_block"], scope["end_block_exclusive"] - 3):
        window = document["blocks"][index:index + 4]
        if builder.split_heading_requires_multispan(
                blocks=window, section={"status": "LOCATED", "candidates": [
                    {"start_block": 0, "end_block_exclusive": 4}]}):
            found.append(index)
    return found


def _visible(raw):
    """The text of an HTML byte span: tags removed, entities decoded, white space collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", raw.decode("utf-8"))).split())


def _block(text, *, emphasised=True, linked=False):
    return {"text": text, "linked": linked, "emphasized": emphasised,
            "leading_emphasis": ({"text": text, "raw_start_byte": 0, "raw_end_byte": len(text),
                                  "raw_span_sha256": "x"} if emphasised else None)}


def _section(blocks):
    return {"status": "LOCATED", "candidates": [{"start_block": 0,
                                                 "end_block_exclusive": len(blocks)}]}


class TheTwoSouthwestReportsTest(unittest.TestCase):

    def test_both_reports_are_refused_by_name(self):
        for label in ("southwest-2022", "southwest-2023"):
            with self.subTest(label), self.assertRaisesRegex(TextCoverageError, REFUSAL):
                builder.build_text_document_admitting_underline(**_arguments(label))

    def test_the_layout_is_where_the_batch_joined(self):
        # Where the earlier version joined (page-boundary/measured-before.json):
        # FY2022 at blocks 524 and 636, FY2023 at 562.
        self.assertEqual([524, 636], _layouts(_document("southwest-2022", refuse=False)))
        self.assertEqual([562], _layouts(_document("southwest-2023", refuse=False)))

    def test_one_span_across_the_halves_holds_the_page_furniture(self):
        document = _document("southwest-2022", refuse=False)
        _, raw = _inputs("southwest-2022")
        for index in _layouts(document):
            first, page, contents, second = document["blocks"][index:index + 4]
            span = _visible(raw[first["raw_start_byte"]:second["raw_end_byte"]])
            joined = first["text"] + " " + second["text"]
            self.assertNotEqual(joined, span)
            self.assertIn(page["text"].strip() + " Table of Contents", span)
            self.assertEqual(span, " ".join([first["text"], page["text"].strip(),
                                             "Table of Contents", second["text"]]))

    def test_without_the_refusal_the_halves_would_be_lines(self):
        # What refusing prevents: the frozen selector lists each half.
        headings = _headings(_document("southwest-2022", refuse=False))
        self.assertEqual(33, len(headings))
        self.assertEqual(2, len([text for text in headings if text[:1].islower()]))

    def test_the_route_refuses_rather_than_delivering_halves(self):
        filing, raw = _inputs("southwest-2022")
        arguments = dict(
            compiled_spec=compile_historical_spec_file(
                repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["D01"], dependency_specs={}),
            target=filing["calculation_target"], source_references=[filing["source_reference"]],
            raw_blobs={filing["raw_blob"]["raw_asset_id"]: filing["raw_blob"]},
            raw_bytes_by_id={filing["raw_blob"]["raw_asset_id"]: raw})
        with self.assertRaisesRegex(TextCoverageError, REFUSAL):
            route.create_deterministic_text_candidate(**arguments)


class TwoHeadingsAcrossAPageStayTwoTest(unittest.TestCase):
    """A category label at the foot of a page and the heading that opens the next."""

    def test_the_two_filings_that_have_one_build_the_batch_s_document(self):
        for label in BATCH_DOCUMENTS:
            with self.subTest(label):
                measured = json.loads((ROOT / "docs/evidence/issue47_history/d01-risk-headings"
                                       / BATCH_DOCUMENTS[label]).read_text(encoding="utf-8"))
                row = measured["per_run"]["run-" + label + "-D01"]
                self.assertEqual("BUILT", row["outcome"])
                self.assertEqual(row["batch_document_id"],
                                 _document(label)["text_document_id"])


class TheLayoutRuleTest(unittest.TestCase):
    """Each condition of the layout, on blocks built to break exactly that one."""

    def _split(self, *, first="An inability to restore operations following adverse weather or",
               between=(("36", False, False), ("Table of Contents", True, True)),
               second="a localized disaster could harm the Company."):
        blocks = [_block(first)]
        for text, emphasised, linked in between:
            blocks.append(_block(text, emphasised=emphasised, linked=linked))
        blocks.append(_block(second))
        return blocks

    def _found(self, blocks, section=None):
        return builder.split_heading_requires_multispan(
            blocks=blocks, section=_section(blocks) if section is None else section)

    def test_the_layout_is_recognised(self):
        self.assertTrue(self._found(self._split()))

    def test_a_lone_page_number_between_two_headings_is_not_the_layout(self):
        # The independent review's counterexample on #28's copy (1457e99a).
        self.assertFalse(self._found(self._split(between=(("1", False, False),))))

    def test_the_contents_line_alone_is_not_the_layout(self):
        self.assertFalse(self._found(self._split(between=(("Table of Contents", True, True),))))

    def test_the_contents_line_before_the_page_number_is_not_the_layout(self):
        self.assertFalse(self._found(self._split(
            between=(("Table of Contents", True, True), ("36", False, False)))))

    def test_a_first_half_that_ends_a_sentence_is_a_heading_of_its_own(self):
        self.assertFalse(self._found(self._split(first="Weather could harm us.")))

    def test_a_second_block_that_begins_a_sentence_is_a_heading_of_its_own(self):
        self.assertFalse(self._found(self._split(second="The Company is subject to FAA rules.")))

    def test_without_a_page_between_them_it_is_not_the_layout(self):
        self.assertFalse(self._found(self._split(between=())))

    def test_body_text_between_them_is_not_the_layout(self):
        self.assertFalse(self._found(self._split(
            between=(("36", False, False), ("The paragraph goes on.", False, False)))))

    def test_an_unlinked_contents_line_is_not_the_layout(self):
        self.assertFalse(self._found(self._split(
            between=(("36", False, False), ("Table of Contents", True, False)))))

    def test_a_half_that_is_not_emphasised_whole_is_not_a_heading_half(self):
        blocks = self._split()
        blocks[3]["leading_emphasis"]["text"] = "a localized disaster"
        self.assertFalse(self._found(blocks))

    def test_outside_item_1a_it_is_not_the_layout(self):
        self.assertFalse(self._found(self._split(), section={"status": "NOT_FOUND",
                                                             "candidates": []}))


class TheBuilderOnAConstructedReportTest(unittest.TestCase):

    def _build(self, replacement):
        return builder.build_text_document_admitting_underline(**binding(annual(BODY.replace(
            "<p>A supply constraint could affect production.</p>", replacement))))

    def test_the_layout_stops_the_document(self):
        with self.assertRaisesRegex(TextCoverageError, REFUSAL):
            self._build("<p><b>Changes in our operations could</b></p>"
                        "<p>42</p><p><a href=\"#toc\">Table of Contents</a></p>"
                        "<p><b>affect our results.</b></p>")

    def test_a_lone_digit_leaves_two_headings(self):
        document = self._build("<p><b>Regulatory Risks</b></p><p>1</p>"
                               "<p><b>other market risks</b></p>")
        headings = _headings(document)
        self.assertIn("Regulatory Risks", headings)
        self.assertIn("other market risks", headings)


if __name__ == "__main__":
    unittest.main()
