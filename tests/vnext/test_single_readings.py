"""The lodging, RPO and compensation readings, re-derived from the saved filings.

Each of these grants acceptances and none had committed code before
tools/read_lodging_table.py and tools/read_single_facts.py.
"""
import hashlib
import json
import unittest
from decimal import Decimal

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_lodging_table as lodging
from tools import read_single_facts as single
from tools.acceptance_readings import saved_bytes

EVIDENCE = "docs/evidence/issue47_history/content-acceptance/"


def _load(name):
    return json.loads((ROOT / (EVIDENCE + name)).read_text(encoding="utf-8"))


def _text(path):
    # The export's archive where only the export holds the filing.
    return saved_bytes(repo_root=ROOT, relative=path).decode("utf-8-sig", errors="replace")


class TheLodgingTableTest(unittest.TestCase):

    def test_every_year_re_derives(self):
        rows = {**_load("lodging-table-read.json"), **_load("lodging-table-read-older-years.json")}
        self.assertEqual(5, len(rows))
        for label, row in rows.items():
            read, matching = lodging.read_table(_text(row["document"]))
            with self.subTest(label):
                self.assertEqual((row["read"], row["tables_matching_scope"]), (read, matching))
                verdicts = lodging.verdicts(read=read, published={
                    metric: row[metric]["published"] for metric in ("B10", "B11")})
                self.assertEqual({m: {k: v for k, v in row[m].items() if k != "checked_identity"}
                                  for m in ("B10", "B11")}, verdicts)

    def test_the_row_is_the_scope_section_s_not_the_first_worldwide_row(self):
        """The table's first Worldwide row is company-operated properties."""
        row = _load("lodging-table-read.json")["marriott-2025"]
        text = _text(row["document"])
        read, _ = lodging.read_table(text)
        table = lodging._TABLE.findall(text)[read["table_ordinal"]]
        worldwide = [lodging._plain(r) for r in lodging._ROW.findall(table)
                     if lodging._plain(r).startswith("Worldwide")]
        self.assertEqual(2, len(worldwide))
        self.assertIn("$ 151.41", worldwide[0])
        self.assertEqual("128.80", read["revpar"])


class TheRemainingPerformanceObligationTest(unittest.TestCase):

    def test_the_undimensioned_period_end_fact_and_the_two_not_taken(self):
        row = _load("rpo-read.json")
        value, not_taken = single.read_instant_fact(
            text=_text("evidence/accession_materials/salesforce_1108524_000110852426000060/"
                       + row["read_from"]["document"]),
            concept="us-gaap:RevenueRemainingPerformanceObligation", period_end=row["period_end"])
        self.assertEqual(Decimal(row["read"]), value)
        self.assertEqual(row["facts_not_taken"], not_taken)
        self.assertEqual({("2025-01-31", ()), ("2026-01-31", ("crm:InformaticaInc.Member",))},
                         {(entry["instant"], tuple(entry["members"])) for entry in not_taken})


    def test_another_year_is_read_from_its_own_filing(self):
        """Salesforce FY2025, from the filing only the acquisition's export holds."""
        row = _load("rpo-read-batch.json")
        raw = saved_bytes(repo_root=ROOT, relative=row["read_from"]["document"])
        self.assertEqual(row["document_sha256"], hashlib.sha256(raw).hexdigest())
        value, not_taken = single.read_instant_fact(
            text=raw.decode("utf-8-sig", errors="replace"),
            concept="us-gaap:RevenueRemainingPerformanceObligation", period_end=row["period_end"])
        self.assertEqual((Decimal(row["read"]), row["facts_not_taken"]), (value, not_taken))
        self.assertEqual(("MATCH", row["published"]), (row["verdict"], str(int(value))))
        # The later filing reports the same year-end again as its comparative.
        self.assertIn({"instant": row["period_end"], "members": [], "value": "63400000000.0"},
                      _load("rpo-read.json")["facts_not_taken"])

    def test_the_older_years_are_each_read_from_their_own_filing(self):
        """Salesforce FY2023/FY2024, read the same way from the export."""
        for name in ("rpo-read-salesforce-2023.json", "rpo-read-salesforce-2024.json"):
            with self.subTest(name):
                row = _load(name)
                raw = saved_bytes(repo_root=ROOT, relative=row["read_from"]["document"])
                self.assertEqual(row["document_sha256"], hashlib.sha256(raw).hexdigest())
                value, not_taken = single.read_instant_fact(
                    text=raw.decode("utf-8-sig", errors="replace"),
                    concept="us-gaap:RevenueRemainingPerformanceObligation",
                    period_end=row["period_end"])
                self.assertEqual((Decimal(row["read"]), row["facts_not_taken"]), (value, not_taken))
                self.assertEqual(("MATCH", row["published"]), (row["verdict"], str(int(value))))


class TheCompensationTableTest(unittest.TestCase):

    def test_the_row_sums_to_its_total_and_matches(self):
        row = _load("paramount-compensation-table-read.json")
        read = single.read_compensation_row(text=_text(row["document"]),
                                            officer="David Ellison", year="2025")
        self.assertTrue(read["sums"])
        self.assertEqual(Decimal(row["total_read"]), read["total"])
        self.assertEqual("MATCH", row["verdict"])

    def test_a_row_that_does_not_sum_is_not_read(self):
        row = _load("paramount-compensation-table-read.json")
        text = _text(row["document"]).replace("63,211,569", "63,211,570", 1)
        read = single.read_compensation_row(text=text, officer="David Ellison", year="2025")
        self.assertFalse(read["sums"])


if __name__ == "__main__":
    unittest.main()
