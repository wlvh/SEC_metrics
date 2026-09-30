"""D01: a heading the filing runs over a page is one heading, not two lines.

``historical_text_emphasis.join_headings_split_across_a_page`` joins a heading's
two halves when only page furniture lies between them. The real cases are
Southwest's FY2022 and FY2023 reports, read from the acquisition's export; the
two filings that put a category label at the foot of a page and the first
heading at the head of the next (Southwest FY2025, Enphase FY2025) are the
cases where two emphasised blocks across a page are two headings and must stay
so. The documents are rebuilt from the bytes and the records the batch's Runs
carried (``page-split/source-records.json``), so no batch is needed. Zero calls.
"""
import copy
import hashlib
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import saved_bytes
from vnext import historical_risk_results as route
from vnext import historical_text_emphasis as builder
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.risk_signals import risk_factor_headings

RECORDS = "docs/evidence/issue47_history/d01-risk-headings/page-split/source-records.json"
WEATHER_2022 = ("The Company’s operations have been, and in the future may again be, materially and "
                "adversely disrupted by extreme weather events. An inability to quickly and "
                "effectively restore operations following adverse weather or a localized disaster "
                "or disturbance in a key geography has adversely and materially impacted, and in the "
                "future could again adversely and materially impact, the Company’s business, results "
                "of operations, and financial condition.")
BYLAWS_2022 = ("The Company’s Bylaws designate specific courts as the exclusive forum for certain "
               "legal actions between the Company and its Shareholders, which could increase costs "
               "to bring a claim, discourage claims, or limit the ability of the Company’s "
               "Shareholders to bring a claim in a judicial forum viewed by the Shareholders as more "
               "favorable for disputes with the Company or the Company’s directors, officers, or "
               "other Employees.")
_BUILT = {}


def _inputs(label):
    filing = json.loads((ROOT / RECORDS).read_text(encoding="utf-8"))["filings"][label]
    raw = saved_bytes(repo_root=ROOT, relative=filing["raw_blob"]["storage_uri"])
    return filing, raw


def _document(label, *, join=True):
    key = (label, join)
    if key not in _BUILT:
        filing, raw = _inputs(label)
        arguments = dict(raw_bytes=raw, raw_blob=filing["raw_blob"],
                         source_reference=filing["source_reference"],
                         expected_company_id=filing["source_reference"]["company_id"],
                         expected_cik=filing["calculation_target"]["entity"],
                         expected_period_end=filing["calculation_target"]["period_end"])
        if join:
            _BUILT[key] = builder.build_text_document_admitting_underline(**arguments)
        else:
            original = builder.join_headings_split_across_a_page
            builder.join_headings_split_across_a_page = lambda **_: []
            try:
                _BUILT[key] = builder.build_text_document_admitting_underline(**arguments)
            finally:
                builder.join_headings_split_across_a_page = original
    return copy.deepcopy(_BUILT[key])


def _headings(document):
    return [heading["text"] for heading in risk_factor_headings(document=document)["headings"]]


def _block(text, *, emphasised=True, linked=False, start=0):
    return {"text": text, "linked": linked, "emphasized": emphasised,
            "leading_emphasis": ({"text": text, "raw_start_byte": start,
                                  "raw_end_byte": start + len(text),
                                  "raw_span_sha256": "x"} if emphasised else None)}


def _section(blocks):
    return {"status": "LOCATED", "candidates": [{"start_block": 0,
                                                 "end_block_exclusive": len(blocks)}]}


class TheTwoSouthwestReportsTest(unittest.TestCase):

    def test_fy2022_delivers_two_whole_headings_where_it_delivered_four_halves(self):
        before, after = _headings(_document("southwest-2022", join=False)), _headings(
            _document("southwest-2022"))
        self.assertEqual((33, 31), (len(before), len(after)))
        self.assertIn(WEATHER_2022, after)
        self.assertIn(BYLAWS_2022, after)
        self.assertEqual([], [text for text in after if text[:1].islower()])
        self.assertEqual(4, len([text for text in before if text not in after]))

    def test_fy2023_delivers_one_whole_heading(self):
        before, after = _headings(_document("southwest-2023", join=False)), _headings(
            _document("southwest-2023"))
        self.assertEqual((29, 28), (len(before), len(after)))
        self.assertEqual([], [text for text in after if text[:1].islower()])

    def test_the_joined_span_is_the_bytes_it_names(self):
        document = _document("southwest-2022")
        _, raw = _inputs("southwest-2022")
        joins = document["headings_joined_across_a_page"]
        self.assertEqual(2, len(joins))
        for join in joins:
            first, second = (document["blocks"][join["first_block"]],
                             document["blocks"][join["second_block"]])
            prefix = first["leading_emphasis"]
            self.assertIsNone(second["leading_emphasis"])
            self.assertEqual(first["text"] + " " + second["text"], prefix["text"])
            self.assertEqual(prefix["raw_span_sha256"], hashlib.sha256(
                raw[prefix["raw_start_byte"]:prefix["raw_end_byte"]]).hexdigest())
            self.assertEqual(second["raw_end_byte"], prefix["raw_end_byte"])
            furniture = [document["blocks"][index]["text"] for index in join["furniture_blocks"]]
            self.assertEqual(["Table of Contents"], furniture[1:])
            self.assertTrue(furniture[0].isdigit())

    def test_the_route_s_candidate_and_evidence_carry_the_joined_heading(self):
        filing, raw = _inputs("southwest-2022")
        arguments = dict(
            compiled_spec=compile_historical_spec_file(
                repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["D01"], dependency_specs={}),
            target=filing["calculation_target"], source_references=[filing["source_reference"]],
            raw_blobs={filing["raw_blob"]["raw_asset_id"]: filing["raw_blob"]},
            raw_bytes_by_id={filing["raw_blob"]["raw_asset_id"]: raw})
        candidate = route.create_deterministic_text_candidate(**arguments)
        evidence = route.build_text_evidence(candidate=candidate, **arguments)
        self.assertEqual("PASS", evidence["status"])
        values = list(evidence["normalized_values"].values())
        self.assertEqual(31, len(values))
        self.assertIn(WEATHER_2022, values)


class TwoHeadingsAcrossAPageStayTwoTest(unittest.TestCase):
    """A category label at the foot of a page and the heading that opens the next."""

    def test_the_two_filings_that_have_one_are_unchanged_to_the_byte(self):
        for label in ("southwest-2025", "enphase-2025"):
            with self.subTest(label):
                joined, not_joined = _document(label), _document(label, join=False)
                self.assertNotIn("headings_joined_across_a_page", joined)
                self.assertEqual(not_joined["text_document_id"], joined["text_document_id"])


class TheJoinRuleTest(unittest.TestCase):
    """Each condition of the rule, on blocks built to break exactly that one."""

    RAW = b"x" * 400

    def _join(self, blocks):
        return builder.join_headings_split_across_a_page(
            blocks=blocks, section=_section(blocks), raw_bytes=self.RAW)

    def _split(self, *, first="An inability to restore operations following adverse weather or",
               between=(("36", False, False), ("Table of Contents", True, True)),
               second="a localized disaster could harm the Company."):
        blocks = [_block(first, start=0)]
        for text, emphasised, linked in between:
            blocks.append(_block(text, emphasised=emphasised, linked=linked, start=100))
        blocks.append(_block(second, start=200))
        return blocks

    def test_a_split_heading_is_joined(self):
        blocks = self._split()
        self.assertEqual([{"first_block": 0, "second_block": 3, "furniture_blocks": [1, 2]}],
                         self._join(blocks))
        self.assertIsNone(blocks[3]["leading_emphasis"])
        self.assertTrue(blocks[0]["leading_emphasis"]["text"].endswith("or a localized disaster "
                                                                       "could harm the Company."))

    def test_a_first_half_that_ends_a_sentence_is_a_heading_of_its_own(self):
        self.assertEqual([], self._join(self._split(first="Weather could harm us.")))

    def test_a_second_block_that_begins_a_sentence_is_a_heading_of_its_own(self):
        self.assertEqual([], self._join(self._split(second="The Company is subject to FAA rules.")))

    def test_without_a_page_between_them_nothing_is_joined(self):
        self.assertEqual([], self._join(self._split(between=())))

    def test_body_text_between_them_is_not_page_furniture(self):
        self.assertEqual([], self._join(self._split(
            between=(("36", False, False), ("The paragraph goes on.", False, False)))))

    def test_an_unlinked_contents_line_is_not_page_furniture(self):
        self.assertEqual([], self._join(self._split(
            between=(("Table of Contents", True, False),))))

    def test_a_half_that_is_not_emphasised_whole_is_not_a_heading_half(self):
        blocks = self._split()
        blocks[3]["leading_emphasis"]["text"] = "a localized disaster"
        self.assertEqual([], self._join(blocks))

    def test_outside_item_1a_nothing_is_joined(self):
        blocks = self._split()
        self.assertEqual([], builder.join_headings_split_across_a_page(
            blocks=blocks, section={"status": "NOT_FOUND", "candidates": []}, raw_bytes=self.RAW))


if __name__ == "__main__":
    unittest.main()
