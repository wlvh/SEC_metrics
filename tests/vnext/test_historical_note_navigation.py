"""D02's note navigation does not read a page number as a note heading.

The frozen scan builds a note heading from an emphasized bare identifier
followed by an emphasized block starting with a letter. Pfizer prints every
page's number that way, below its running footer, so a page that begins with a
bold heading becomes a note heading; in the FY2024 report page 16 does, "Note
16A" found two Note 16 headings and D02 stopped at
TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE. ``historical_text_results.
note_references`` runs the frozen scan with page numbers blanked.

These cases read real annual reports (Pfizer FY2024 and FY2021, Macy's FY2021
from the acquisition's export; Pfizer FY2025 from the checkout), so they
belong to the source-material tier. Load-bearing:
  * Pfizer FY2024 resolves Note 16A to the real Note 16, as FY2025 does;
  * Macy's numbered note headings - the form the frozen rule exists for -
    are not page numbers, and its navigation is the frozen one;
  * D02's preparation goes through this navigation, not the frozen one.
"""
from __future__ import annotations

import json
import re
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import saved_bytes
from vnext import historical_text_results as route
from vnext import text_coverage
from vnext.canonical import content_hash, sha256_bytes
from vnext.historical_dei import release_aware
from vnext.historical_text_results import note_references, page_number_blocks
from vnext.records import validate_record
from vnext.text_business_candidates import _note_references, _ranges, legal_risk_candidates

# (saved path, source URL, report end)
PFIZER_2024 = ("evidence/request_attempts/05/05b77064b72e16b39bc80dfa10d12d18e4b470c0df63c2cb89d3884e813bb97f/pfe-20241231.htm",
               "https://www.sec.gov/Archives/edgar/data/78003/000007800325000054/pfe-20241231.htm", "2024-12-31")
PFIZER_2021 = ("evidence/request_attempts/a6/a6dc538da8dd8c78563933a612ccb61bcc77ed9d067383ee6ed394612d5f0dd8/pfe-20211231.htm",
               "https://www.sec.gov/Archives/edgar/data/78003/000007800322000027/pfe-20211231.htm", "2021-12-31")
PFIZER_2025 = ("evidence/request_attempts/17/175e07c21ee258eddd9952e443d34df2a297d0c38e2d1312dff0a64a31c401ab/pfe-20251231.htm",
               "https://www.sec.gov/Archives/edgar/data/78003/000007800326000026/pfe-20251231.htm", "2025-12-31")
MACYS_2021 = ("evidence/request_attempts/3c/3c0ef7be7458818e691c1015b116240c720a554d4d0aef4cde4b6e712641a388/m-10k_20220129.htm",
              "https://www.sec.gov/Archives/edgar/data/794367/000156459022011726/m-10k_20220129.htm", "2022-01-29")
_PATTERNS = json.loads((ROOT / "catalog/r6/text_business_candidates_v1.json").read_text())["patterns"]
_IDENTIFIER = re.compile(_PATTERNS["note_identifier"], re.I)
_HEADING = re.compile(_PATTERNS["note_heading"], re.I)


def _document(case):
    path, url, end = case
    raw = saved_bytes(repo_root=ROOT, relative=path)
    cik, digits, name = re.match(r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/(.+)$", url).groups()
    blob = validate_record(record={"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                                   "byte_length": len(raw), "media_type": "text/html", "storage_uri": path})
    identity = {"raw_asset_id": blob["raw_asset_id"], "company_id": "company", "source_url": url,
                "accession": digits[:10] + "-" + digits[10:12] + "-" + digits[12:], "document_name": name,
                "source_role": "target_primary"}
    reference = validate_record(record={"record_type": "SOURCE_REFERENCE",
                                        "source_reference_id": content_hash(value=identity),
                                        **identity, "request_attempt_id": "attempt"})
    return release_aware(text_coverage.build_text_document)(
        raw_bytes=raw, raw_blob=blob, source_reference=reference, expected_company_id="company",
        expected_cik=cik, expected_period_end=end)


def _identifier_headings(blocks):
    return [index for index, block in enumerate(blocks)
            if not block["linked"] and block.get("emphasized") and len(block["text"]) <= 300
            and not _HEADING.match(block["text"]) and _IDENTIFIER.fullmatch(block["text"])
            and index + 1 < len(blocks) and blocks[index + 1].get("emphasized")
            and re.match(r"[A-Za-z]", blocks[index + 1]["text"])]


class ThePageNumberIsNotANoteHeading(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.documents = {case[0]: _document(case) for case in (PFIZER_2024, PFIZER_2021, PFIZER_2025, MACYS_2021)}

    def _navigation(self, case, function):
        document = self.documents[case[0]]
        ranges, _ = _ranges(document, ["ITEM_1A", "ITEM_3", "ITEM_8"])
        return function(document, ranges)

    def test_pfizer_fy2024_resolves_note_16a_to_the_real_note(self):
        frozen = self._navigation(PFIZER_2024, _note_references)
        self.assertEqual(["REFERENCE_NAVIGATION_NOT_UNIQUE_OR_INCOMPLETE"], [r["status"] for r in frozen])
        successor = self._navigation(PFIZER_2024, note_references)
        self.assertEqual(["LOCATED_NOTE_RANGE"], [r["status"] for r in successor])
        candidate = successor[0]["range_candidates"][0]
        heading = self.documents[PFIZER_2024[0]]["blocks"][candidate["start_block"]]["text"]
        self.assertEqual("Note 16. Contingencies and Certain Commitments", heading)
        self.assertEqual("WIDER_PARENT_NOTE", candidate["scope_relation"])

    def test_the_spurious_heading_was_page_16_below_the_running_footer(self):
        blocks = self.documents[PFIZER_2024[0]]["blocks"]
        frozen = self._navigation(PFIZER_2024, _note_references)
        spurious = [c["start_block"] for c in frozen[0]["range_candidates"]
                    if blocks[c["start_block"]]["text"] == "16"]
        self.assertEqual(1, len(spurious))
        self.assertIn(spurious[0], page_number_blocks(blocks))
        self.assertEqual("2024 Form 10-K", blocks[spurious[0] - 1]["text"])

    def test_on_pfizer_every_identifier_heading_is_a_page_number(self):
        for case in (PFIZER_2024, PFIZER_2021, PFIZER_2025):
            blocks = self.documents[case[0]]["blocks"]
            headings = _identifier_headings(blocks)
            with self.subTest(case[2]):
                self.assertGreater(len(headings), 60)
                self.assertEqual(set(headings), set(headings) & page_number_blocks(blocks))

    def test_where_navigation_was_unique_it_is_unchanged(self):
        # FY2025's page 16 is followed by body text, FY2021's range was unique
        # already; the located ranges are the frozen ones.
        for case in (PFIZER_2025, PFIZER_2021):
            frozen = self._navigation(case, _note_references)
            successor = self._navigation(case, note_references)
            with self.subTest(case[2]):
                self.assertEqual([r["range_candidates"] for r in frozen],
                                 [r["range_candidates"] for r in successor])

    def test_macys_numbered_note_headings_are_not_page_numbers(self):
        blocks = self.documents[MACYS_2021[0]]["blocks"]
        headings = _identifier_headings(blocks)
        self.assertGreaterEqual(len(headings), 15)
        self.assertEqual(set(), set(headings) & page_number_blocks(blocks))
        self.assertEqual(self._navigation(MACYS_2021, _note_references),
                         self._navigation(MACYS_2021, note_references))

    def test_the_referenced_notes_are_located_with_the_same_navigation(self):
        document = self.documents[PFIZER_2024[0]]
        raw = saved_bytes(repo_root=ROOT, relative=PFIZER_2024[0])
        proposal = route.referenced_note_candidates(document=document, raw_bytes=raw)
        self.assertEqual("LOCAL_REQUESTED_RANGES_SCANNED", proposal["coverage_status"])
        self.assertIn("NOTE_16_SUB_A", {scope["section_id"] for scope in proposal["checked_ranges"]})

    def test_d02_s_legal_scan_now_covers_its_ranges(self):
        document = self.documents[PFIZER_2024[0]]
        frozen = legal_risk_candidates(document=document)
        self.assertEqual("INCOMPLETE", frozen["coverage_status"])
        self.assertEqual(["UNRESOLVED_NOTE_16A"], frozen["coverage_reasons"])
        self.assertEqual("LOCAL_REQUESTED_RANGES_SCANNED",
                         route._D02_LEGAL_SCAN(document=document)["coverage_status"])


class APageNumberNeedsTheSequenceBesideTheFooter(unittest.TestCase):

    def _blocks(self, texts):
        return [{"text": text, "linked": False, "emphasized": True} for text in texts]

    def test_a_numbered_heading_after_a_running_footer_is_not_a_page(self):
        # A real note may start right below a footer. Without a neighbouring
        # page number beside the same footer, its number is not a page.
        texts = ["Footer", "body", "Footer", "body", "Footer", "16", "Contingencies", "body"]
        self.assertEqual(set(), page_number_blocks(self._blocks(texts)))

    def test_consecutive_numbers_beside_the_same_footer_are_pages(self):
        texts = ["Footer", "15", "body", "Footer", "16", "HEADING", "body", "Footer", "17", "body"]
        self.assertEqual({1, 4, 8}, page_number_blocks(self._blocks(texts)))

    def test_a_footer_that_does_not_repeat_three_times_is_not_a_running_footer(self):
        texts = ["Footer", "15", "body", "Footer", "16", "HEADING"]
        self.assertEqual(set(), page_number_blocks(self._blocks(texts)))


class D02PreparesThroughThisNavigation(unittest.TestCase):

    def test_the_d02_path_calls_the_successor_preparation(self):
        class Called(Exception):
            pass

        def called(**_arguments):
            raise Called

        with mock.patch.object(route, "_D02_PREPARATION", called):
            with self.assertRaises(Called):
                route._prepare_corrected_sources(
                    metric_id="D02", target={}, source_references=[], raw_blobs={},
                    raw_bytes_by_id={}, source_filings={})

    def test_the_successor_preparation_reads_the_successor_navigation(self):
        from vnext.historical_dei import overrides_of
        self.assertIs(route.frozen.prepare_business_text_sources,
                      route._D02_PREPARATION.release_aware_view_of)
        self.assertEqual({"legal_risk_candidates": route._D02_LEGAL_SCAN},
                         overrides_of(route._D02_PREPARATION))
        self.assertEqual({"_note_references": note_references}, overrides_of(route._D02_LEGAL_SCAN))


if __name__ == "__main__":
    unittest.main()
