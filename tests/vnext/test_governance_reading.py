"""The governance reading behind C03 and C04, held to the saved documents.

tools/read_governance_facts.py replaces a reading whose code was never
committed and which parsed numbers with int(), skipping what failed. Parsing
the SEC's fixed-zero dash as zero is right, and it turned up something the old
skip had hidden by accident: the pay-versus-performance table's placeholder
for a year a person was not PEO.
"""
import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_governance_facts as reader

READING = "docs/evidence/issue47_history/content-acceptance/governance-read.json"
SOUTHWEST_PROXY = ("evidence/accession_materials/southwest_airlines_92380_000119312526127237/"
                   "d121727ddef14a.htm")
YEAR_2025 = ("2025-01-01", "2025-12-31")


def _committed():
    return json.loads((ROOT / READING).read_text(encoding="utf-8"))["per_position"]


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_governance_modules(self):
        tree = ast.parse((ROOT / "tools/read_governance_facts.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("governance_signals", "historical_governance_results",
                             "historical_governance_input", "normal_governance_input"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class ThePlaceholderIsReadAsWhatTheTableSaysItIsTest(unittest.TestCase):

    def setUp(self):
        raw = (ROOT / SOUTHWEST_PROXY).read_text(encoding="utf-8-sig", errors="replace")
        self.totals = reader.peo_totals(raw, reader.contexts_of(raw))

    def test_the_dash_is_zero_and_it_is_there(self):
        dashes = [t for t in self.totals if t["key"] == YEAR_2025 and t["placeholder"]]
        self.assertTrue(dashes)
        self.assertEqual({0}, {t["value"] for t in dashes})

    def test_a_dash_for_a_person_paid_as_peo_in_other_years_is_set_aside(self):
        kept, set_aside = reader.peo_totals_for(self.totals, YEAR_2025)
        self.assertEqual([16587882], sorted({int(t["value"]) for t in kept}))
        self.assertEqual([{"members": ["luv:GaryC.KellyMember"], "shown": "—",
                           "same_person_paid_as_peo_in": ["2021", "2022"]}], set_aside)

    def test_a_dash_for_a_person_the_table_never_pays_still_counts(self):
        never_paid = [{**t, "members": ["x:NeverPaidMember"]} for t in self.totals
                      if t["key"] == YEAR_2025 and t["placeholder"]]
        others = [t for t in self.totals if t["members"] != ["luv:GaryC.KellyMember"]]
        kept, set_aside = reader.peo_totals_for(others + never_paid, YEAR_2025)
        self.assertEqual([], set_aside)
        self.assertEqual({0, 16587882}, {int(t["value"]) for t in kept})


class TheCommittedReadingRederivesTest(unittest.TestCase):

    def test_every_position(self):
        for label, row in _committed().items():
            read_by = row["C04"]["eight_k_window_read_by"]
            items = None if read_by is None else json.loads((ROOT / read_by[0]).read_text(
                encoding="utf-8"))["per_position"][label]["filings"]["filing_date"]
            entry = reader.read_case(
                company_id=row["company_id"], label=label,
                period={"period_start": row["period"][0], "period_end": row["period"][1]},
                cik=row["cik"], source_document=row["target_document"],
                selection={"prior_filing": row["prior_filing"]},
                published={"C03": row["C03"]["published"], "C04": row["C04"]["published"]},
                event_items=items)
            with self.subTest(label):
                for metric in ("C03", "C04"):
                    self.assertEqual({k: v for k, v in row[metric].items()
                                      if k not in ("checked_identity", "eight_k_window_read_by")},
                                     entry[metric])

    def test_a_window_no_reading_read_is_not_a_window_without_item_4_01(self):
        """Salesforce FY2026's window is read only by the batch's event reading."""
        default = json.loads((ROOT / reader.EVENTS).read_text(encoding="utf-8"))["per_position"]
        self.assertNotIn("salesforce-2026", default)
        self.assertEqual((None, None), reader.window_items(events={reader.EVENTS: default},
                                                           label="salesforce-2026"))
        row = _committed()["salesforce-2026"]
        entry = reader.read_case(
            company_id=row["company_id"], label="salesforce-2026",
            period={"period_start": row["period"][0], "period_end": row["period"][1]},
            cik=row["cik"], source_document=row["target_document"],
            selection={"prior_filing": row["prior_filing"]},
            published={"C03": None, "C04": "0"}, event_items=None)
        self.assertEqual((None, "THE_8K_WINDOW_WAS_NOT_READ", "NOT_READ"),
                         (entry["C04"]["read"], entry["C04"]["why_not_read"],
                          entry["C04"]["verdict"]))
        # The same firm in both years is not enough on its own.
        self.assertEqual(entry["C04"]["auditor_named_in_the_target_filing"],
                         entry["C04"]["auditor_named_in_the_previous_years_filing"])

    def test_two_readings_of_one_window_must_name_the_same_filings(self):
        rows = {"x": {"filings": {"filing_date": [{"accession": "a", "items": ["2.02"]}]}}}
        other = {"x": {"filings": {"filing_date": [{"accession": "a", "items": ["4.01"]}]}}}
        self.assertEqual((["one.json", "two.json"], rows["x"]["filings"]["filing_date"]),
                         reader.window_items(events={"one.json": rows, "two.json": rows},
                                             label="x"))
        with self.assertRaisesRegex(SystemExit, "EVENT_READINGS_DISAGREE_ON_A_WINDOW"):
            reader.window_items(events={"one.json": rows, "two.json": other}, label="x")

    def test_every_recorded_identity_was_recorded_when_the_reading_was_made(self):
        for label, row in _committed().items():
            for metric in ("C03", "C04"):
                if row[metric]["published"] is None:
                    continue
                with self.subTest(label=label, metric=metric):
                    self.assertEqual("RECORDED_AT_READING_TIME",
                                     row[metric]["checked_identity"]["established_by"])


if __name__ == "__main__":
    unittest.main()
