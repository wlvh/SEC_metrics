"""E01's candidate items, read from their own text, under the content-confirmed meaning.

The frozen matcher compares E01's aliases with each claim's brief, and for an
hdr-coded filing that brief is the program's sentence "8-K item 8.01 parsed
from hdr.sgml", so no 8.01 was ever read. The owner's 2026-09-27 decision made
E01 count content-confirmed M&A announcements: every 1.01, 2.01 and 8.01 item
is a candidate, read from its heading to the next item heading or the
signatures in the primary document, and none counts until its content
confirmation is registered. No confirmation is registered yet, so a window
with a candidate is withheld by name.

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
from vnext.canonical import content_hash
from vnext.deterministic_router import (_compiled_event_spec, _hdr_item_codes, _visible_text,
                                        load_event_route_catalog)
from vnext.historical_event_items import (CONFIRMATION_REASON, NOT_LOCATED_REASON,
                                          EventItemTextError, content_confirmation_candidates,
                                          item_headings, item_text, successor_event_route)
from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
from vnext.normal_period_selection import resolve_period_selection

MATERIALS = ROOT / "evidence/accession_materials"
WINDOWS = {"enphase_energy": "2025-12-31", "ford_motor_company": "2025-12-31",
           "lumen_technologies": "2025-12-31", "macys": "2026-01-31",
           "marriott_international": "2025-12-31", "pfizer": "2025-12-31",
           "southwest_airlines": "2025-12-31"}
# Values of the approved item-rule definition, published before the decision;
# none of them is a value of the content-confirmed meaning.
PUBLISHED = {"enphase_energy": "0", "ford_motor_company": "2", "lumen_technologies": "7",
             "southwest_airlines": "2"}
CANDIDATE_CODES = ("1.01", "2.01", "8.01")


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


class TheContentConfirmedRouteCountsNothingItHasNotConfirmed(unittest.TestCase):
    """The owner's E01 meaning, on the seven saved windows."""

    @classmethod
    def setUpClass(cls):
        cls.components = {}
        for company, report_end in WINDOWS.items():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company,
                                                 report_end=report_end)
            cls.components[company] = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=company, metric_id="E01", period_selection=selection)

    def _has_candidate(self, component):
        return any(claim["attributes"]["item_code"] in CANDIDATE_CODES for claim in component["claims"])

    def test_a_window_with_a_candidate_is_withheld_by_name(self):
        withheld = [company for company, component in self.components.items() if self._has_candidate(component)]
        self.assertEqual(6, len(withheld))
        for company in withheld:
            component = self.components[company]
            with self.subTest(company):
                self.assertEqual((component["result"]["publication"], component["result"]["reason_code"]),
                                 ("WITHHELD", CONFIRMATION_REASON))
                self.assertEqual(component["selection"]["category"], "CONTENT_CONFIRMATION_NOT_EXECUTED")

    def test_a_window_with_no_candidate_is_answered_zero_by_the_route_s_matcher(self):
        # Enphase filed no 1.01, 2.01 or 8.01 item in its fiscal-year window.
        component = self.components["enphase_energy"]
        self.assertFalse(self._has_candidate(component))
        self.assertEqual((component["result"]["publication"], component["result"]["value"]), ("PUBLISHED", "0"))
        (observation,) = component["observations"]
        bound = observation["source_binding"]["content_confirmation"]
        self.assertEqual((bound["status"], bound["candidates"]), ("NO_CANDIDATE_ITEM", []))
        self.assertEqual(component["selection"]["content_confirmation"]["candidate_item_codes"],
                         list(CANDIDATE_CODES))

    def test_every_candidate_item_is_read_from_its_own_text(self):
        for company, component in self.components.items():
            listed = sorted((claim["attributes"]["accession"], claim["attributes"]["item_code"])
                            for claim in component["claims"]
                            if claim["attributes"]["item_code"] in CANDIDATE_CODES)
            answer = component["selection"]["content_confirmation"]
            read = sorted((item["accession"], item["item_code"]) for item in answer["candidates"])
            with self.subTest(company):
                self.assertEqual(read, listed)
                self.assertTrue(all(item["confirmation"] == "NOT_REGISTERED" for item in answer["candidates"]))
                self.assertTrue(all(item["text_sha256"].startswith("sha256:") for item in answer["candidates"]))

    def test_no_value_of_the_approved_definition_is_carried_over(self):
        # A window with a candidate loses its approved-definition value; the
        # one window with none has its zero recomputed under the successor's
        # Spec, which is why an acceptance of the old zero does not reach it.
        frozen = _compiled_event_spec(metric_id="E01",
                                      route=load_event_route_catalog(repo_root=ROOT)["routes"]["E01"])
        for company, value in PUBLISHED.items():
            result = self.components[company]["result"]
            with self.subTest(company):
                self.assertNotEqual(frozen["spec_closure_hash"], result["spec_closure_hash"])
                if self._has_candidate(self.components[company]):
                    self.assertNotEqual("PUBLISHED", result["publication"])
                    self.assertIsNone(result["value"])

    def test_the_spec_is_the_successor_route_s(self):
        frozen = load_event_route_catalog(repo_root=ROOT)["routes"]["E01"]
        frozen_spec = _compiled_event_spec(metric_id="E01", route=frozen)
        for company, component in self.components.items():
            with self.subTest(company):
                self.assertNotEqual(component["result"]["spec_closure_hash"], frozen_spec["spec_closure_hash"])
                self.assertEqual(component["spec_origin"]["catalog_path"],
                                 "catalog/r6/E01_content_confirmed_ma_v1.json")

    def test_the_brief_is_never_consulted(self):
        """A brief rewritten to name a merger changes no candidate: the brief is not read."""
        component = self.components["ford_motor_company"]
        catalog = load_event_route_catalog(repo_root=ROOT)
        route = successor_event_route(repo_root=ROOT, metric_id="E01", frozen_route=catalog["routes"]["E01"])
        records = {r.get("source_reference_id") or r["raw_asset_id"]: r for r in component["source_records"]}
        rewritten = [{**claim, "attributes": {**claim["attributes"], "brief": "merger acquisition transaction"}}
                     for claim in component["claims"]]
        before = content_confirmation_candidates(repo_root=ROOT, route=route, claims=component["claims"],
                                                 records=records)
        after = content_confirmation_candidates(repo_root=ROOT, route=route, claims=rewritten, records=records)
        self.assertEqual(before, after)
        self.assertEqual(before["status"], "CONFIRMATION_NOT_REGISTERED")

    def test_a_successor_written_against_another_route_is_refused(self):
        frozen = load_event_route_catalog(repo_root=ROOT)["routes"]["E01"]
        altered = {**frozen, "direct_item_codes": ["1.01"]}
        self.assertNotEqual(content_hash(value=dict(altered)), content_hash(value=dict(frozen)))
        with self.assertRaises(EventItemTextError) as caught:
            successor_event_route(repo_root=ROOT, metric_id="E01", frozen_route=altered)
        self.assertIn("HISTORICAL_EVENT_SUCCESSOR_PREDECESSOR_CHANGED", str(caught.exception))

    def test_a_route_without_candidates_is_untouched(self):
        selection = resolve_period_selection(repo_root=ROOT, company_id="ford_motor_company",
                                             report_end="2025-12-31")
        for metric_id in ("C01", "E05"):
            component = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id="ford_motor_company", metric_id=metric_id,
                period_selection=selection)
            with self.subTest(metric_id):
                self.assertNotIn("content_confirmation", component["selection"])
                self.assertEqual("PUBLISHED", component["result"]["publication"])


class TheReasonsAreNamed(unittest.TestCase):

    def test_the_reason_codes(self):
        self.assertEqual(CONFIRMATION_REASON, "HISTORICAL_E01_CONTENT_CONFIRMATION_NOT_REGISTERED")
        self.assertEqual(NOT_LOCATED_REASON, "HISTORICAL_EVENT_ITEM_TEXT_NOT_LOCATED")


if __name__ == "__main__":
    unittest.main()
