"""E01's keyword items, read from their own text.

The frozen matcher compares E01's aliases with each claim's brief, and for an
hdr-coded filing that brief is the program's sentence "8-K item 8.01 parsed
from hdr.sgml", so no 8.01 was ever read. historical_event_items reads the
item from its heading to the next item heading or the signatures in the
primary document and records every alias there. What an alias there means is
undecided, so the route answers only what that meaning cannot move.

The text cases run on every saved 8-K that carries an 8.01, and are compared
with tools/read_e01_eight_o_ones.py, which finds the item its own way and
imports none of the route's modules. The heading cases that need a shape no
saved filing has are built in memory and say so.
"""
import json
import re
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_e01_eight_o_ones as reading
from vnext.deterministic_router import _hdr_item_codes, _visible_text, load_event_route_catalog
from vnext.historical_event_items import (NOT_LOCATED_REASON, PENDING_REASON,
                                          EventItemTextError, alias_occurrences,
                                          item_headings, item_text, keyword_item_answer)
from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
from vnext.normal_period_selection import resolve_period_selection

MATERIALS = ROOT / "evidence/accession_materials"
WINDOWS = {"enphase_energy": "2025-12-31", "ford_motor_company": "2025-12-31",
           "lumen_technologies": "2025-12-31", "macys": "2026-01-31",
           "marriott_international": "2025-12-31", "pfizer": "2025-12-31",
           "southwest_airlines": "2025-12-31"}
# Read by eye against each filing; recorded in
# docs/evidence/issue47_history/e01-keyword-branch/eight-o-one-judgements.json.
ALIAS_IN_THE_ITEM = {"macys": {"0000794367-25-000128"},
                     "marriott_international": {"0001193125-25-036732",
                                                "0001193125-25-184082"},
                     "pfizer": {"0000078003-25-000159"}}
PUBLISHED = {"enphase_energy": "0", "ford_motor_company": "2", "lumen_technologies": "7",
             "southwest_airlines": "2"}


def _saved_eight_ks():
    """(folder, primary bytes, hdr item codes) for every saved 8-K."""
    found = []
    for folder in sorted(MATERIALS.iterdir()):
        headers = sorted(folder.glob("*.hdr.sgml"))
        if not headers:
            continue
        header = headers[0].read_bytes()
        form = re.search(r"<TYPE>\s*([^\r\n]+)", header.decode("utf-8", "replace"))
        if form is None or form.group(1).strip() not in ("8-K", "8-K/A"):
            continue
        primaries = [path for path in folder.iterdir() if path.suffix in (".htm", ".html")]
        found.append((folder.name, primaries[0].read_bytes(), _hdr_item_codes(raw_bytes=header)))
    return found


def _html(*paragraphs):
    return ("<html><body>" + "".join("<p>" + p + "</p>" for p in paragraphs)
            + "</body></html>").encode("utf-8")


class TheItemIsReadFromItsHeading(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.eights = [row for row in _saved_eight_ks() if "8.01" in row[2]]

    def test_every_saved_8_01_is_located_once(self):
        # Forty saved 8-Ks list an 8.01 in their header; each is headed once.
        self.assertEqual(len(self.eights), 40)
        for folder, raw, _ in self.eights:
            with self.subTest(folder):
                text = item_text(raw_bytes=raw, item_code="8.01")
                self.assertTrue(text["heading"].startswith("Item 8.01"))
                self.assertIn(text["end_marker"], ("NEXT_ITEM_HEADING", "SIGNATURES"))

    def test_the_text_is_the_one_an_independent_reading_finds(self):
        """The reading tool finds the item by its title; where it finds one the
        two texts are the same, and where it does not the filing titles the item
        'Other Information', which the tool's title pattern does not know."""
        normalise = reading._normalise
        compared, unread = 0, []
        for folder, raw, _ in self.eights:
            _, theirs = reading.eight_o_one_item(reading.visible_text(raw))
            ours = item_text(raw_bytes=raw, item_code="8.01")
            if not theirs:
                unread.append(ours["text"][:len("Item 8.01 Other Information.")])
                continue
            compared += 1
            with self.subTest(folder):
                self.assertEqual(normalise(ours["text"]), normalise(theirs))
        self.assertEqual(compared, 36)
        self.assertEqual(sorted(set(unread)), ["Item 8.01 Other Information."])

    def test_a_checkbox_glyph_before_the_heading_is_not_a_reference(self):
        # Macy's cover renders its empty boxes as the letter "o", so the word
        # before each heading is "o"; a rule that took any lowercase word for a
        # reference lost every Macy's item.
        raw = next(r for f, r, _ in self.eights if f.endswith("000079436725000010"))
        self.assertIn(" o Item 8.01", " ".join(reading.visible_text(raw).split()))
        self.assertEqual(item_text(raw_bytes=raw, item_code="8.01")["end_marker"],
                         "SIGNATURES")

    def test_a_sentence_ending_in_an_item_reference_does_not_start_that_item(self):
        # Macy's 000079436725000137: "... is incorporated into this Item 2.03
        # by reference. Item 8.01. Other Events. ..." - saved bytes.
        raw = next(r for f, r, _ in self.eights if f.endswith("000079436725000137"))
        text = item_text(raw_bytes=raw, item_code="8.01")
        self.assertTrue(text["text"].startswith("Item 8.01. Other Events. On July 28, 2025"))
        self.assertTrue(text["text"].rstrip().endswith("subject to the Tender Offer."))


class HeadingsAndReferences(unittest.TestCase):
    """Constructed text, for shapes no saved 8-K has."""

    def test_a_quoted_title_is_a_reference(self):
        raw = _html("Item 7.01 Regulation FD Disclosure. On May 1 the Company presented.",
                    "The information in this “Item 8.01 - Other Events” is furnished.",
                    "Item 9.01 Financial Statements and Exhibits.")
        self.assertEqual([code for *_, code in item_headings(_visible_text(raw_bytes=raw))],
                         ["7.01", "9.01"])
        with self.assertRaisesRegex(EventItemTextError, "EVENT_ITEM_TEXT_NOT_LOCATED:8.01"):
            item_text(raw_bytes=raw, item_code="8.01")

    def test_consecutive_headings_of_one_item_are_one_item(self):
        # Southwest heads "Item 5.02 Departure of Directors ..." and then
        # "Item 5.02(b) On February 4, 2025 ..." - saved; built here for 8.01.
        raw = _html("Item 8.01 Other Events.", "Item 8.01(a) The Company agreed to buy Acme.",
                    "Item 9.01 Financial Statements and Exhibits.")
        text = item_text(raw_bytes=raw, item_code="8.01")
        self.assertIn("agreed to buy Acme", text["text"])
        self.assertEqual(text["end_marker"], "NEXT_ITEM_HEADING")

    def test_an_item_headed_twice_around_another_is_refused(self):
        raw = _html("Item 8.01 Other Events. First.", "Item 7.01 Regulation FD Disclosure. X.",
                    "Item 8.01 Other Events. Second.")
        with self.assertRaisesRegex(EventItemTextError, "EVENT_ITEM_HEADED_MORE_THAN_ONCE:8.01"):
            item_text(raw_bytes=raw, item_code="8.01")

    def test_a_combined_heading_is_refused_rather_than_guessed(self):
        raw = _html("Items 7.01 and 8.01 Regulation FD Disclosure and Other Events.",
                    "On May 1 the Company agreed to acquire Acme Corp.",
                    "SIGNATURES")
        with self.assertRaisesRegex(EventItemTextError, "EVENT_ITEM_TEXT_NOT_LOCATED:8.01"):
            item_text(raw_bytes=raw, item_code="8.01")

    def test_the_text_ends_at_the_signatures_when_no_item_follows(self):
        raw = _html("Item 8.01 Other Events. The Company completed a merger with Acme.",
                    "SIGNATURES", "Pursuant to the requirements of the Act.")
        text = item_text(raw_bytes=raw, item_code="8.01")
        self.assertEqual(text["end_marker"], "SIGNATURES")
        self.assertNotIn("Pursuant", text["text"])


class TheAliasIsFoundInTheItemsOwnText(unittest.TestCase):

    def test_the_catalog_normalisation_and_substring_match(self):
        normalised, hits = alias_occurrences(
            text="a COMBINED  aggregate price; Acquisitions.", aliases=["combine", "acquisition"])
        self.assertEqual(normalised, "a combined aggregate price; acquisitions.")
        self.assertEqual([(hit["alias"], hit["offset"]) for hit in hits],
                         [("combine", 2), ("acquisition", 28)])

    def test_the_brief_is_never_consulted(self):
        """Ford's five 8.01s carry no alias in their own text; a brief rewritten
        to hold one changes nothing, because the brief is not read."""
        selection = resolve_period_selection(repo_root=ROOT, company_id="ford_motor_company",
                                             report_end="2025-12-31")
        component = resolve_historical_zero_ai_metric(repo_root=ROOT,
                                                      company_id="ford_motor_company",
                                                      metric_id="E01",
                                                      period_selection=selection)
        route = load_event_route_catalog(repo_root=ROOT)["routes"]["E01"]
        records = {r.get("source_reference_id") or r["raw_asset_id"]: r
                   for r in component["source_records"]}
        rewritten = [{**claim, "attributes": {**claim["attributes"],
                                              "brief": "merger acquisition transaction"}}
                     for claim in component["claims"]]
        before = keyword_item_answer(repo_root=ROOT, route=route, claims=component["claims"],
                                     records=records)
        after = keyword_item_answer(repo_root=ROOT, route=route, claims=rewritten,
                                    records=records)
        self.assertEqual(len(before["items"]), 5)
        self.assertEqual(before, after)
        self.assertEqual(after["status"], "NO_ALIAS_IN_ANY_KEYWORD_ITEM")


class TheRouteAnswersOnlyWhatTheMeaningCannotMove(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.components = {}
        for company, report_end in WINDOWS.items():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company,
                                                 report_end=report_end)
            cls.components[company] = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=company, metric_id="E01", period_selection=selection)

    def test_a_window_whose_keyword_items_carry_no_alias_is_answered(self):
        for company, value in PUBLISHED.items():
            with self.subTest(company):
                result = self.components[company]["result"]
                self.assertEqual((result["publication"], result["value"]), ("PUBLISHED", value))

    def test_a_window_where_one_carries_an_alias_is_withheld_by_name(self):
        for company, accessions in ALIAS_IN_THE_ITEM.items():
            with self.subTest(company):
                component = self.components[company]
                self.assertEqual((component["result"]["publication"],
                                  component["result"]["reason_code"]),
                                 ("WITHHELD", PENDING_REASON))
                answer = component["selection"]["keyword_item_confirmation"]
                self.assertEqual({item["accession"] for item in answer["items"]
                                  if item["alias_occurrences"]}, accessions)
                self.assertEqual(component["selection"]["category"], "PRODUCT_MEANING_PENDING")

    def test_every_keyword_item_in_the_window_is_read(self):
        for company, component in self.components.items():
            listed = {claim["attributes"]["accession"] for claim in component["claims"]
                      if claim["attributes"]["item_code"] == "8.01"}
            read = {item["accession"] for item in
                    component["selection"]["keyword_item_confirmation"]["items"]}
            with self.subTest(company):
                self.assertEqual(read, listed)

    def test_the_observation_binds_what_was_read(self):
        for company in PUBLISHED:
            component = self.components[company]
            (observation,) = component["observations"]
            bound = observation["source_binding"]["keyword_item_confirmation"]
            full = component["selection"]["keyword_item_confirmation"]
            with self.subTest(company):
                self.assertEqual([item["text_sha256"] for item in bound["items"]],
                                 [item["text_sha256"] for item in full["items"]])
                self.assertEqual(observation["source_binding"]["matched_verified_claim_ids"],
                                 component["selection"]["matched_verified_claim_ids"])
                self.assertTrue(all(item["reading"] == "NO_ALIAS_IN_ITS_OWN_TEXT"
                                    for item in bound["items"]))

    def test_a_route_without_keyword_items_is_untouched(self):
        selection = resolve_period_selection(repo_root=ROOT, company_id="ford_motor_company",
                                             report_end="2025-12-31")
        for metric_id in ("C01", "E05"):
            component = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id="ford_motor_company", metric_id=metric_id,
                period_selection=selection)
            with self.subTest(metric_id):
                self.assertNotIn("keyword_item_confirmation", component["selection"])
                for observation in component["observations"]:
                    self.assertNotIn("keyword_item_confirmation", observation["source_binding"])


class TheReasonsAreNamed(unittest.TestCase):

    def test_the_reason_codes(self):
        self.assertEqual(PENDING_REASON, "HISTORICAL_EVENT_KEYWORD_CONFIRMATION_MEANING_PENDING")
        self.assertEqual(NOT_LOCATED_REASON, "HISTORICAL_EVENT_KEYWORD_ITEM_TEXT_NOT_LOCATED")


if __name__ == "__main__":
    unittest.main()
