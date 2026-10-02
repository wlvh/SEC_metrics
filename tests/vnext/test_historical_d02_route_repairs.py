"""Four D02 route repairs, each on the filing whose reading found it.

The older-year readings (docs/evidence/issue47_history/d02-older-years/) found
four ways the historical D02 selection takes what the filing did not say, or
misses what it did, none of them the keyword proxy:

* Southwest FY2023 prints "Item 4. Mine Safety Disclosures" as the last line
  of a page. The frozen heading scan refuses a heading followed by a bare
  number (a contents row), so Item 3 ran on and Item 4's "Not applicable."
  became an excerpt.
* Pfizer's FY2022-FY2024 page footers became excerpts: in FY2023/FY2024 Item 3
  is four blocks, too few for repetition inside it to show; in FY2022 the
  footer is one block and the page number separates it from the running head.
* Lumen FY2021's Item 3 names two captions its note does not carry, and the
  route took the whole note - right-of-way and purchase commitments included.
* Macy's FY2021 Item 8 is a pointer page; the statements printed after the
  items were never read, so the self-insurance claims accrual the later years'
  values carry was missing.

Each case builds the document from the saved bytes (the checkout or the
acquisition's export) and asks the route's own functions. What must not move
is asserted beside what must: D03's candidates, the excerpts that are not
furniture, and the filings where a rule finds its pattern but moves nothing.
"""
import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.saved_filings import saved_filing as _saved
from vnext import historical_text_results as route
from vnext import text_coverage
from vnext.canonical import content_hash, sha256_bytes
from vnext.historical_dei import release_aware
from vnext.records import validate_record

BUILD = release_aware(text_coverage.build_text_document)
_ARCHIVE_URL = re.compile(r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/(.+)$")


def document(file_name):
    """The frozen text document of a saved annual report, and its bytes."""
    raw, url = _saved(file_name)
    cik, digits, name = _ARCHIVE_URL.match(url).groups()
    blob = validate_record(record={"record_type": "RAW_BLOB",
                                   "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                                   "byte_length": len(raw), "media_type": "text/html",
                                   "storage_uri": "evidence/x/" + file_name})
    identity = {"raw_asset_id": blob["raw_asset_id"], "company_id": "company", "source_url": url,
                "accession": digits[:10] + "-" + digits[10:12] + "-" + digits[12:],
                "document_name": name, "source_role": "target_primary"}
    reference = validate_record(record={"record_type": "SOURCE_REFERENCE",
                                        "source_reference_id": content_hash(value=identity),
                                        **identity, "request_attempt_id": "attempt"})
    stamp = re.search(r"(\d{8})\.htm$", file_name).group(1)
    built = BUILD(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                  expected_company_id="company", expected_cik=cik,
                  expected_period_end=stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:])
    return built, raw


def proposal(file_name, *, without=None):
    """The route's D02/D03 proposal; ``without`` names a repair to switch off for comparison."""
    built, raw = document(file_name)
    return proposal_of(built, raw, without=without)


def proposal_of(built, raw, *, without=None):
    """``proposal`` for a document already built - a constructed one included."""
    saved = {}
    if without == "PAGE_STRUCTURE_FURNITURE":
        saved["page_structure_furniture"] = route.page_structure_furniture
        route.page_structure_furniture = lambda blocks: set()
    if without == "APPENDED_STATEMENTS":
        saved["appended_statements_range"] = route.appended_statements_range
        route.appended_statements_range = lambda **arguments: None
    if without == "STATEMENTS_START":
        # As before the repair: the statements start at the first title after Item 8.
        saved["statements_start"] = route.statements_start
        route.statements_start = lambda titles: titles[0][0] if titles else None
    try:
        corrected = route.narrow_document_sections(document=built)
        return corrected, route.referenced_note_candidates(document=corrected, raw_bytes=raw)
    finally:
        for name, value in saved.items():
            setattr(route, name, value)


def excerpts(found, metric="D02"):
    return [c["block_index"] for c in found[metric]["candidates"]]


class AHeadingAtThePageFootTest(unittest.TestCase):

    def test_item_three_closes_at_item_four_printed_above_the_page_number(self):
        built, _ = document("luv-20231231.htm")
        blocks = built["blocks"]
        item_four = [i for i, b in enumerate(blocks)
                     if b["text"].strip() == "Item 4. Mine Safety Disclosures" and not b["linked"]]
        self.assertEqual(1, len(item_four))
        heading = item_four[0]
        # The frozen scan refuses it for the number that follows, and only for that.
        self.assertIsNone(text_coverage._heading(blocks, heading))
        self.assertRegex(blocks[heading + 1]["text"], r"^\d+$")
        self.assertIn(heading + 1, route.page_number_blocks(blocks))
        frozen = built["sections"]["ITEM_3"]["candidates"][0]
        self.assertGreater(frozen["end_block_exclusive"], heading + 3)

        corrected, found = proposal("luv-20231231.htm")
        item_3 = corrected["sections"]["ITEM_3"]["candidates"]
        self.assertEqual(1, len(item_3))
        self.assertEqual(frozen["start_block"], item_3[0]["start_block"])
        self.assertEqual(heading, item_3[0]["end_block_exclusive"])
        self.assertEqual(route.ITEM_HEADING_POLICY, corrected["item_heading_policy"])
        self.assertEqual(["4"], [h["item"] for h in corrected["page_bottom_item_headings"]])
        answer = [i for i in excerpts(found) if blocks[i]["text"].strip() == "Not applicable."]
        self.assertEqual([], answer)
        # Item 3's own paragraphs are all still there.
        self.assertTrue(all(i in excerpts(found) for i in range(frozen["start_block"], heading)
                            if blocks[i]["text"].startswith(("On ", "Two complaints", "Since about"))))

    def test_a_page_foot_heading_that_moves_no_section_leaves_the_document_as_it_was(self):
        """Marriott FY2025 prints "Item 6. Reserved." at a page foot; no section ends there."""
        built, _ = document("mar-20251231.htm")
        headings, added = route.page_bottom_item_headings(document=built)
        self.assertEqual(["6"], [h["item"] for h in added])
        self.assertIs(built, route.narrow_document_sections(document=built))

    def test_the_section_derivation_is_the_frozen_one(self):
        """The successor derives sections again; on the frozen headings it must give the frozen answer."""
        for name in ("luv-20231231.htm", "pfe-20231231.htm", "mar-20251231.htm"):
            with self.subTest(name):
                built, _ = document(name)
                frozen = [h for i in range(len(built["blocks"]))
                          if (h := text_coverage._heading(built["blocks"], i)) is not None]
                self.assertEqual(built["sections"], route._sections_from(frozen))


class FurnitureByItsPlaceOnThePageTest(unittest.TestCase):

    def test_the_item_three_footer_leaves_and_the_sentence_stays(self):
        for name, year in (("pfe-20231231.htm", "2023"), ("pfe-20241231.htm", "2024")):
            with self.subTest(name):
                corrected, found = proposal(name)
                _, before = proposal(name, without="PAGE_STRUCTURE_FURNITURE")
                blocks = corrected["blocks"]
                item_3 = next(r for r in found["checked_ranges"] if r["section_id"] == "ITEM_3")
                inside = range(item_3["start_block"], item_3["end_block_exclusive"])
                footer = [i for i in inside if blocks[i]["text"].strip() == year + " Form 10-K"]
                sentence = [i for i in inside if blocks[i]["text"].startswith("Certain legal proceedings")]
                self.assertEqual(1, len(footer))
                self.assertEqual(1, len(sentence))
                self.assertIn(footer[0], excerpts(before))
                self.assertNotIn(footer[0], excerpts(found))
                self.assertIn(sentence[0], excerpts(found))
                self.assertEqual(excerpts(before, "D03"), excerpts(found, "D03"))

    def test_the_merged_footer_leaves_note_16a_and_nothing_else_does(self):
        corrected, found = proposal("pfe-20221231.htm")
        _, before = proposal("pfe-20221231.htm", without="PAGE_STRUCTURE_FURNITURE")
        blocks = corrected["blocks"]
        gone = sorted(set(excerpts(before)) - set(excerpts(found)))
        self.assertEqual({"Pfizer Inc.2022 Form 10-K"}, {blocks[i]["text"].strip() for i in gone})
        self.assertEqual(6, len(gone))
        self.assertEqual([], sorted(set(excerpts(found)) - set(excerpts(before))))
        self.assertEqual(excerpts(before, "D03"), excerpts(found, "D03"))

    def test_the_latest_year_set_is_unchanged(self):
        """Pfizer FY2025's separate footer blocks were already dropped by the scope rule."""
        _, found = proposal("pfe-20251231.htm")
        _, before = proposal("pfe-20251231.htm", without="PAGE_STRUCTURE_FURNITURE")
        self.assertEqual(excerpts(before), excerpts(found))

    def test_d03_keeps_what_the_repair_takes_out_of_d02(self):
        """Constructed: the repair is D02's, and D03 keeps the blocks it read before.

        No saved filing prints D03's words in a page footer, so on real bytes
        the D02-only scope of this repair cannot be told from one that also
        drops the blocks from D03. This case edits every copy of Pfizer
        FY2022's merged footer the same way - so it still stands at its place
        beside the page numbers - to end with "subpoena", and nothing else. D02
        must leave every copy out; D03 must keep exactly the candidates it has
        with the repair switched off, the edited copies among them.
        """
        built, raw = document("pfe-20221231.htm")
        footer = "Pfizer Inc.2022 Form 10-K"
        # The copies that stand at the footer's place beside a page number (109
        # of the 112 in this report; three are elsewhere on their page).
        placed = route.page_structure_furniture(built["blocks"])
        copies = [i for i, b in enumerate(built["blocks"]) if b["text"].strip() == footer and i in placed]
        self.assertGreaterEqual(len(copies), 100)
        edited = {**built, "blocks": [dict(block, text=block["text"] + " subpoena") if i in copies
                                      else block for i, block in enumerate(built["blocks"])]}
        corrected, found = proposal_of(edited, raw)
        _, before = proposal_of(edited, raw, without="PAGE_STRUCTURE_FURNITURE")
        self.assertTrue(set(copies) <= route.page_structure_furniture(edited["blocks"]))
        self.assertFalse(set(copies) & set(excerpts(found)))
        self.assertTrue(set(copies) & set(excerpts(before, "D03")))
        self.assertEqual(excerpts(before, "D03"), excerpts(found, "D03"))

    def test_a_repeated_matter_label_is_not_furniture(self):
        """Note 16A names Comirnaty under two matters; it does not sit at a fixed place beside page numbers."""
        corrected, found = proposal("pfe-20221231.htm")
        blocks = corrected["blocks"]
        furniture = route.page_structure_furniture(blocks)
        labels = [i for i in excerpts(found) if blocks[i]["text"].strip() == "Comirnaty"]
        self.assertEqual(2, len(labels))
        self.assertFalse(set(labels) & furniture)


class CaptionsTheNoteDoesNotCarryTest(unittest.TestCase):

    def test_the_whole_note_is_not_taken_in_their_place(self):
        corrected, found = proposal("lumn-20211231.htm")
        reference = next(r for r in found["note_references"] if r["status"] == "LOCATED_NOTE_RANGE")
        note = reference["range_candidates"][0]
        missing = route.unincorporable_captions(document=corrected, reference=reference, note=note)
        self.assertEqual(["other proceedings and disputes", "pending matters"], missing)
        self.assertEqual("INCOMPLETE", found["coverage_status"])
        self.assertIn("UNRESOLVED_INCORPORATED_CAPTION_" + note["section_id"], found["coverage_reasons"])
        self.assertFalse(any(r["section_id"].startswith(note["section_id"])
                             for r in found["checked_ranges"]))

    def test_captions_the_note_carries_still_limit_it(self):
        corrected, found = proposal("lumn-20221231.htm")
        reference = next(r for r in found["note_references"] if r["status"] == "LOCATED_NOTE_RANGE")
        note = reference["range_candidates"][0]
        self.assertEqual([], route.unincorporable_captions(document=corrected, reference=reference,
                                                           note=note))
        self.assertEqual("LOCAL_REQUESTED_RANGES_SCANNED", found["coverage_status"])
        captions = sorted(r["caption_text"] for r in found["checked_ranges"]
                          if r.get("scope_relation") == "INCORPORATED_CAPTION")
        self.assertEqual(["Other Proceedings, Disputes and Contingencies", "Principal Proceedings"],
                         captions)

    def test_one_missing_caption_of_two_is_enough(self):
        """Constructed from FY2022: one quoted caption the note carries, one it does not.

        No saved filing names one caption its note carries and one it does not,
        so the case edits the quoted text of the real Item 3 sentence and nothing
        else. Taking the found caption alone would silently drop what the
        filing incorporated under the other name.
        """
        corrected, found = proposal("lumn-20221231.htm")
        reference = next(r for r in found["note_references"] if r["status"] == "LOCATED_NOTE_RANGE")
        note = reference["range_candidates"][0]
        edited = {**reference, "source_occurrences": [
            {**occurrence, "text": occurrence["text"].replace("Principal Proceedings", "Pending Matters")}
            for occurrence in reference["source_occurrences"]]}
        self.assertNotEqual(reference["source_occurrences"], edited["source_occurrences"])
        self.assertEqual(["pending matters"], route.unincorporable_captions(
            document=corrected, reference=edited, note=note))

    def test_a_quoted_form_item_says_where_the_note_is_not_which_part(self):
        """Paramount's Item 3 quotes "Legal Matters" and the Form item the note is printed in.

        The second quote is "Item 8. Financial Statements and Supplementary
        Data-Notes to Consolidated Financial Statements": where the note is, not
        a caption limiting it. Read as a caption, it stopped every Paramount
        year when the repair was first measured over the frame.
        """
        corrected, found = proposal("psky-20251231.htm")
        reference = next(r for r in found["note_references"] if r["status"] == "LOCATED_NOTE_RANGE")
        note = reference["range_candidates"][0]
        quoted = [route._normalized(m.group(1)) for o in reference["source_occurrences"]
                  for m in route._QUOTED_CAPTION.finditer(o["text"])]
        self.assertTrue(any(q.startswith("item 8.") for q in quoted))
        self.assertIn("legal matters", quoted)
        self.assertEqual([], route.unincorporable_captions(document=corrected, reference=reference,
                                                           note=note))
        self.assertEqual("LOCAL_REQUESTED_RANGES_SCANNED", found["coverage_status"])
        self.assertEqual(["Legal Matters"], [r["caption_text"] for r in found["checked_ranges"]
                                             if r.get("scope_relation") == "INCORPORATED_CAPTION"])

    def test_a_quoted_note_title_is_not_a_missing_caption(self):
        """Salesforce's Item 3 quotes its note's own title; the note is taken whole."""
        corrected, found = proposal("crm-20260131.htm")
        for reference in found["note_references"]:
            if reference["status"] != "LOCATED_NOTE_RANGE":
                continue
            note = reference["range_candidates"][0]
            self.assertEqual([], route.unincorporable_captions(document=corrected,
                                                               reference=reference, note=note))
        self.assertEqual("LOCAL_REQUESTED_RANGES_SCANNED", found["coverage_status"])


class StatementsPrintedAfterAPointerPageTest(unittest.TestCase):

    def test_the_statements_are_read_through_the_keyword_and_nothing_else_moves(self):
        corrected, found = proposal("m-10k_20220129.htm")
        _, before = proposal("m-10k_20220129.htm", without="APPENDED_STATEMENTS")
        blocks = corrected["blocks"]
        item_8 = next(r for r in found["checked_ranges"] if r["section_id"] == "ITEM_8")
        appended = [r for r in found["checked_ranges"] if r["section_id"] == route.APPENDED_STATEMENTS]
        self.assertEqual(1, len(appended))
        self.assertGreaterEqual(appended[0]["start_block"], item_8["end_block_exclusive"])
        self.assertRegex(appended[0]["caption_text"], r"(?i)^consolidated statements? of")
        self.assertEqual(len(blocks), appended[0]["end_block_exclusive"])
        added = sorted(set(excerpts(found)) - set(excerpts(before)))
        self.assertEqual([], sorted(set(excerpts(before)) - set(excerpts(found))))
        self.assertEqual(1, len(added))
        self.assertTrue(blocks[added[0]]["text"].startswith(
            "The Company, through its insurance subsidiary, is self-insured"))
        self.assertEqual(excerpts(before, "D03"), excerpts(found, "D03"))

    def test_an_item_8_that_holds_its_statements_is_not_a_pointer_page(self):
        for name in ("m-20230128.htm", "pfe-20251231.htm"):
            with self.subTest(name):
                _, found = proposal(name)
                self.assertFalse([r for r in found["checked_ranges"]
                                  if r["section_id"] == route.APPENDED_STATEMENTS])

    def test_a_note_item_3_incorporates_keeps_its_own_blocks(self):
        """Ford's Item 8 is a pointer page too; its keyword blocks after it are all in Note 24."""
        _, found = proposal("f-20251231.htm")
        _, before = proposal("f-20251231.htm", without="APPENDED_STATEMENTS")
        self.assertTrue([r for r in found["checked_ranges"]
                         if r["section_id"] == route.APPENDED_STATEMENTS])
        self.assertEqual(excerpts(before), excerpts(found))
        self.assertEqual(excerpts(before, "D03"), excerpts(found, "D03"))


class TheStatementsBeginWhereTheyArePrintedTogetherTest(unittest.TestCase):
    """The appended range starts at the statements, not at a heading that begins with one's name.

    JPMorgan's Item 8 is a pointer page too, and its MD&A opens "CONSOLIDATED
    BALANCE SHEETS AND CASH FLOWS ANALYSIS" some 3,400 blocks before
    "Consolidated statements of income". Starting there put the MD&A under the
    keyword, and the held-out reading of FY2025 judged each such admission not
    a disclosure (d02-older-years/judgements/jpmorgan_chase-2025-12-31.json).
    The statements are where titles of at least three kinds stand together.
    """

    @classmethod
    def setUpClass(cls):
        cls.corrected, cls.found = proposal("jpm-20251231.htm")
        _, cls.before = proposal("jpm-20251231.htm", without="STATEMENTS_START")

    @staticmethod
    def _appended(found):
        ranges = [r for r in found["checked_ranges"] if r["section_id"] == route.APPENDED_STATEMENTS]
        assert len(ranges) == 1, ranges
        return ranges[0]

    def test_jpmorgan_s_range_starts_at_the_income_statement(self):
        blocks = self.corrected["blocks"]
        start = self._appended(self.found)["start_block"]
        old = self._appended(self.before)["start_block"]
        self.assertEqual("Consolidated statements of income", blocks[start]["text"].strip())
        self.assertEqual("CONSOLIDATED BALANCE SHEETS AND CASH FLOWS ANALYSIS", blocks[old]["text"].strip())
        self.assertLess(old, start)

    def test_only_the_mdna_paragraphs_leave_and_each_was_judged_not_a_disclosure(self):
        start = self._appended(self.found)["start_block"]
        old = self._appended(self.before)["start_block"]
        lost = set(excerpts(self.before)) - set(excerpts(self.found))
        self.assertEqual(set(), set(excerpts(self.found)) - set(excerpts(self.before)))
        self.assertTrue(lost)
        self.assertTrue(all(old <= index < start for index in lost), sorted(lost))
        reading = json.loads((ROOT / "docs/evidence/issue47_history/d02-older-years/judgements/"
                                     "jpmorgan_chase-2025-12-31.json").read_text(encoding="utf-8"))
        verdict = {row["i"]: row["verdict"] for row in reading["judgements"] if row["kind"] == "TAKEN"}
        self.assertEqual({"NOT_DISCLOSURE"}, {verdict[index] for index in lost})
        disclosures = {index for index, value in verdict.items() if value == "DISCLOSURE"}
        self.assertEqual(set(), disclosures - set(excerpts(self.found)))
        self.assertEqual(excerpts(self.before, "D03"), excerpts(self.found, "D03"))

    def test_a_report_whose_statements_open_the_run_keeps_its_range(self):
        _, found = proposal("m-10k_20220129.htm")
        _, before = proposal("m-10k_20220129.htm", without="STATEMENTS_START")
        self.assertEqual(self._appended(before), self._appended(found))
        self.assertEqual(excerpts(before), excerpts(found))


class StatementsStartTest(unittest.TestCase):
    """The run on constructed titles: each condition held on its own."""

    def test_a_run_of_three_kinds_starts_the_statements(self):
        titles = [(1705, "BALANCE"), (1706, "BALANCE"), (5229, "INCOME"),
                  (5271, "COMPREHENSIVE"), (5287, "BALANCE")]
        self.assertEqual(5229, route.statements_start(titles))

    def test_two_kinds_are_not_the_statements(self):
        self.assertIsNone(route.statements_start([(10, "BALANCE"), (20, "CASH_FLOWS"), (30, "BALANCE")]))

    def test_a_gap_over_the_bound_breaks_the_run(self):
        self.assertIsNone(route.statements_start([(0, "INCOME"), (100, "BALANCE"), (401, "CASH_FLOWS")]))
        self.assertEqual(0, route.statements_start([(0, "INCOME"), (100, "BALANCE"), (400, "CASH_FLOWS")]))

    def test_each_title_has_its_kind(self):
        for text, kind in (("Consolidated Statements of Comprehensive Income", "COMPREHENSIVE"),
                           ("Consolidated statements of income", "INCOME"),
                           ("CONSOLIDATED STATEMENTS OF OPERATIONS", "INCOME"),
                           ("Consolidated statements of changes in stockholders\u2019 equity", "EQUITY"),
                           ("Consolidated Statements of Cash Flows", "CASH_FLOWS"),
                           ("Consolidated balance sheets analysis", "BALANCE"),
                           ("Consolidated Statements of Operations and Comprehensive Income", "INCOME")):
            with self.subTest(text):
                self.assertEqual(kind, route._statement_kind(text))


if __name__ == "__main__":
    unittest.main()
