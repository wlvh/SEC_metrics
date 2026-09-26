"""The event-count reading that grants C01 and E02-E05, held to the saved filings.

tools/read_event_counts.py replaces a reading whose code was never committed
and whose submissions index was whichever copy an unsorted glob found first.
"""
import ast
import json
import sys
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_event_counts as reader

READING = "docs/evidence/issue47_history/content-acceptance/event-count-read.json"
# A position whose results ran under another closure is its own reading.
READINGS = (READING,
            "docs/evidence/issue47_history/content-acceptance/event-count-read-paramount-2024.json")


def _committed():
    positions = {}
    for path in READINGS:
        for label, row in json.loads((ROOT / path).read_text(encoding="utf-8"))[
                "per_position"].items():
            assert label not in positions, label
            positions[label] = row
    return positions


def _recount(label):
    row = _committed()[label]
    submissions = json.loads((ROOT / row["submissions_index"]).read_text(encoding="utf-8"))
    cik = int(submissions["cik"])
    return reader.count_window(filings=reader.filings_in_index(submissions), cik=cik,
                               start=row["window"][0], end=row["window"][1])


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_event_modules(self):
        tree = ast.parse((ROOT / "tools/read_event_counts.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("deterministic_router", "zero_ai_r2", "normal_zero_ai_results",
                             "historical_zero_ai_results", "historical_event_sources"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class TheSavedFilingsGiveTheCommittedCountsTest(unittest.TestCase):

    def test_every_position_re_derives(self):
        for label, row in _committed().items():
            counts, seen, unreadable = _recount(label)
            with self.subTest(label):
                self.assertEqual(row["filings"], seen)
                self.assertEqual(row["headers_not_saved"], unreadable)
                self.assertEqual({metric: (entry["by_filing_date"], entry["by_report_date"])
                                  for metric, entry in row["metrics"].items()},
                                 {metric: (counts["filing_date"][metric],
                                           counts["report_date"][metric])
                                  for metric in row["metrics"]})

    def test_an_amendment_carrying_the_item_is_its_own_entry(self):
        """Marriott's window holds an 8-K/A with item 5.02; without it C01 reads 2."""
        row = _committed()["marriott-2025"]
        submissions = json.loads((ROOT / row["submissions_index"]).read_text(encoding="utf-8"))
        filings = reader.filings_in_index(submissions)
        amendments = [f for f in filings if f["form"] == "8-K/A"
                      and row["window"][0] <= f["filingDate"] <= row["window"][1]]
        self.assertEqual(1, len(amendments))
        counts, _, _ = reader.count_window(filings=filings, cik=int(submissions["cik"]),
                                           start=row["window"][0], end=row["window"][1])
        without, _, _ = reader.count_window(
            filings=[f for f in filings if f["form"] != "8-K/A"], cik=int(submissions["cik"]),
            start=row["window"][0], end=row["window"][1])
        self.assertEqual((3, 2), (counts["filing_date"]["C01"], without["filing_date"]["C01"]))

    def test_the_index_is_the_ledger_s_latest_successful_copy(self):
        from sec_urls import submissions_url
        from vnext.annual_update import saved_source
        for label, row in _committed().items():
            submissions = json.loads((ROOT / row["submissions_index"]).read_text(
                encoding="utf-8"))
            saved = saved_source(repo_root=ROOT, url=submissions_url(cik=int(submissions["cik"])))
            with self.subTest(label):
                self.assertEqual(row["submissions_index"],
                                 saved["proof"]["request_repo_relative_path"])


class ACaseOfItsOwnIsAReadingOfItsOwnTest(unittest.TestCase):

    def test_a_named_case_is_not_written_into_the_default_reading(self):
        """The default reading's positions all compare one closure's results."""
        argv = ["read_event_counts.py", "--runs-root", "/nonexistent", "--closure", "sha256:x",
                "--case", "paramount-2024=paramount_skydance_paramount_global:2024-12-31"]
        with patch.object(sys, "argv", argv), self.assertRaises(SystemExit) as refused:
            reader.main()
        self.assertEqual("A_CASE_OF_ITS_OWN_IS_WRITTEN_TO_A_READING_OF_ITS_OWN",
                         str(refused.exception))

    def test_a_case_names_its_label_company_and_period(self):
        self.assertEqual(("paramount_skydance_paramount_global", "2024-12-31", "paramount-2024"),
                         reader._case("paramount-2024=paramount_skydance_paramount_global:"
                                      "2024-12-31"))
        with self.assertRaises(SystemExit):
            reader._case("paramount-2024")


class TheVerdictTest(unittest.TestCase):

    def test_accepted_only_when_both_window_readings_agree(self):
        self.assertEqual("MATCH_BOTH_BASES",
                         reader.verdict(published="3", by_filing_date=3, by_report_date=3))
        self.assertEqual("MATCH_ON_FILING_DATE",
                         reader.verdict(published="3", by_filing_date=3, by_report_date=2))
        self.assertEqual("DIFFERS",
                         reader.verdict(published="3", by_filing_date=2, by_report_date=2))
        self.assertEqual("NO_PUBLISHED_VALUE",
                         reader.verdict(published=None, by_filing_date=0, by_report_date=0))

    def test_every_recorded_identity_was_recorded_when_the_reading_was_made(self):
        for label, row in _committed().items():
            for metric, entry in row["metrics"].items():
                if entry["published"] is None:
                    continue
                with self.subTest(label=label, metric=metric):
                    self.assertEqual("RECORDED_AT_READING_TIME",
                                     entry["checked_identity"]["established_by"])


if __name__ == "__main__":
    unittest.main()
