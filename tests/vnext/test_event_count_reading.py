"""The event-count reading that grants C01 and E02-E05, held to the saved filings.

tools/read_event_counts.py replaces a reading whose code was never committed
and whose submissions index was whichever copy an unsorted glob found first.
"""
import ast
import collections
import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_event_counts as reader
from tools.acceptance_readings import EVENT_READINGS, RESTORED_ROOT_EVENT_READINGS, saved_bytes

READING = "docs/evidence/issue47_history/content-acceptance/event-count-read.json"
# A position whose results ran under another closure is its own reading.
READINGS = EVENT_READINGS


def _committed(paths=READINGS):
    positions = {}
    for path in paths:
        for label, row in json.loads((ROOT / path).read_text(encoding="utf-8"))[
                "per_position"].items():
            assert label not in positions, label
            positions[label] = row
    return positions


def _recount(label):
    """The committed position counted again from the bytes it names.

    A header only the acquisition saved is read from the path the reading
    recorded, out of the checkout or the export; one the checkout's accession
    materials hold is read from there, as the reader read it. A successor's
    year is counted over each registered CIK's index, in the reading's order.
    """
    row = _committed()[label]
    indexes = row.get("submissions_indexes") or {None: row["submissions_index"]}
    recorded = {entry["accession"]: entry["header"] for entries in row["filings"].values()
                for entry in entries if "header" in entry}

    def header(cik, accession):
        items = reader.header_items(cik, accession)
        if items is not None:
            return items, None
        if accession not in recorded:
            return None, None
        text = saved_bytes(repo_root=ROOT, relative=recorded[accession]).decode(
            "utf-8", errors="replace")
        return reader.items_of(text), recorded[accession]
    counts = {basis: collections.Counter() for basis in ("filing_date", "report_date")}
    seen, unreadable = {basis: [] for basis in counts}, []
    # The reading's own order of registrants (its JSON keys are sorted as text).
    for registrant in row.get("registered_ciks") or [None]:
        path = indexes[registrant]
        submissions = json.loads(saved_bytes(repo_root=ROOT, relative=path))
        cik = int(submissions["cik"])
        each, admitted, missing = reader.count_window(
            filings=reader.filings_in_index(submissions), cik=cik, start=row["window"][0],
            end=row["window"][1], header=header, metrics=sorted(row["metrics"]))
        for basis in counts:
            counts[basis].update(each[basis])
            seen[basis].extend(entry if registrant is None else {**entry, "cik": registrant}
                               for entry in admitted[basis])
        unreadable.extend(missing)
    return counts, seen, sorted(set(unreadable))


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
        checkout = [path for path in READINGS if path not in RESTORED_ROOT_EVENT_READINGS]
        for label, row in _committed(checkout).items():
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


class APartialWindowIsNotCountedTest(unittest.TestCase):
    """The two refusals --source-root added: a window reaching a history block,
    and a filing whose header cannot be read."""

    def test_a_block_reaches_through_the_day_after_its_declared_end(self):
        # SEC files the day between two blocks' ranges in the older block.
        index = {"filings": {"files": [{"name": "b1", "filingTo": "2018-01-16"}]}}
        self.assertEqual(["b1"], reader.history_blocks_reached(index, "2018-01-16"))
        self.assertEqual(["b1"], reader.history_blocks_reached(index, "2018-01-17"))
        self.assertEqual([], reader.history_blocks_reached(index, "2018-01-18"))

    def test_a_saved_index_whose_recent_table_misses_the_window_start(self):
        # Pfizer's recent table begins 2021-02-02; its block 001 ends 2021-01-31.
        from sec_urls import submissions_url
        from vnext.annual_update import saved_source
        index = json.loads(saved_source(repo_root=ROOT, url=submissions_url(cik=78003))["raw"])
        self.assertIn("CIK0000078003-submissions-001.json",
                      reader.history_blocks_reached(index, "2021-01-01"))
        self.assertEqual([], reader.history_blocks_reached(index, "2025-01-01"))

    def test_an_unreadable_header_is_not_a_count_even_when_the_numbers_agree(self):
        self.assertEqual("NOT_READ", reader.verdict(published="2", by_filing_date=2,
                                                    by_report_date=2, unreadable=["x"]))

    def test_the_ledger_s_latest_copy_must_have_its_recorded_digest(self):
        import csv
        import hashlib
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence").mkdir()
            (root / "evidence/a.hdr.sgml").write_bytes(b"<ITEMS>5.02\n")
            fields = ["method", "source_url", "status_code", "error", "repo_relative_path",
                      "content_sha256"]

            def ledger(*rows):
                with (root / "evidence/requests_log.csv").open("w", newline="") as opened:
                    writer = csv.DictWriter(opened, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                return reader.ledger_rows(root)
            good = {"method": "GET", "source_url": "u", "status_code": "200", "error": "",
                    "repo_relative_path": "evidence/a.hdr.sgml",
                    "content_sha256": hashlib.sha256(b"<ITEMS>5.02\n").hexdigest()}
            self.assertEqual((b"<ITEMS>5.02\n", "evidence/a.hdr.sgml"),
                             reader.latest_saved(root=root, rows=ledger(good), url="u"))
            # A failed latest request is not read around, even over an earlier success.
            self.assertIsNone(reader.latest_saved(
                root=root, rows=ledger(good, {**good, "status_code": "503"}), url="u"))
            with self.assertRaisesRegex(SystemExit, "SAVED_BYTES_DIFFER_FROM_THE_LEDGER"):
                reader.latest_saved(root=root, rows=ledger({**good, "content_sha256": "0" * 64}),
                                    url="u")

    def test_a_restored_root_reading_records_the_header_it_read_from_the_ledger(self):
        restored = _committed(RESTORED_ROOT_EVENT_READINGS)
        recorded = [entry for row in restored.values() for entries in row["filings"].values()
                    for entry in entries if "header" in entry]
        self.assertTrue(recorded)
        for entry in recorded:
            with self.subTest(entry["accession"]):
                self.assertTrue(entry["header"].startswith("evidence/request_attempts/"))
                self.assertTrue(entry["header"].endswith(entry["accession"] + ".hdr.sgml"))
        # E01's keyword rule reads every saved document of a filing, which an
        # acquired filing does not have; it is not counted over a restored root.
        self.assertTrue(all("E01" not in row["metrics"] for row in restored.values()))


class ASuccessorYearIsCountedOverItsApprovedWindowTest(unittest.TestCase):
    """The window and the registrants come from the approved policy, not the result."""

    PARAMOUNT = "paramount_skydance_paramount_global"

    def test_the_successor_year_reaches_back_and_counts_both_registrants(self):
        window, ciks, policy = reader.event_window(
            company_id=self.PARAMOUNT, cik="2041610",
            period={"fiscal_year": 2025, "period_start": "2025-01-01",
                    "period_end": "2025-12-31"})
        self.assertEqual((("2024-01-01", "2025-12-31"), ["813828", "2041610"],
                          "PRIOR_CALENDAR_YEAR_START_TO_TARGET_END"), (window, ciks, policy))

    def test_the_predecessor_s_own_year_is_its_own_window(self):
        window, ciks, _ = reader.event_window(
            company_id=self.PARAMOUNT, cik="813828",
            period={"fiscal_year": 2024, "period_start": "2024-01-01",
                    "period_end": "2024-12-31"})
        self.assertEqual((("2024-01-01", "2024-12-31"), ["813828"]), (window, ciks))

    def test_a_policy_this_reading_does_not_implement_stops_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("config/company_registry.csv", "catalog/zero_ai_public_projection.json"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / name, root / name)
            catalog = json.loads((root / "catalog/zero_ai_public_projection.json").read_text(
                encoding="utf-8"))
            catalog["event_window_policy_by_continuity"]["successor_predecessor"] = "OTHER"
            (root / "catalog/zero_ai_public_projection.json").write_text(json.dumps(catalog),
                                                                         encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "EVENT_WINDOW_POLICY_NOT_READ_HERE"):
                reader.event_window(company_id=self.PARAMOUNT, cik="2041610", root=root,
                                    period={"fiscal_year": 2025, "period_start": "2025-01-01",
                                            "period_end": "2025-12-31"})

    def test_the_committed_successor_reading_counts_each_registrant(self):
        from tools.acceptance_readings import EVENTS_SUCCESSOR
        row = _committed([EVENTS_SUCCESSOR])["paramount-2025"]
        with (ROOT / "config/company_registry.csv").open(encoding="utf-8") as opened:
            roles = next(r["roles"] for r in csv.DictReader(opened)
                         if r["company_id"] == self.PARAMOUNT)
        self.assertEqual(sorted(entry.split(":")[1] for entry in roles.split(";")),
                         sorted(row["registered_ciks"]))
        self.assertEqual(set(row["registered_ciks"]),
                         {entry["cik"] for entry in row["filings"]["filing_date"]})


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
                # NOT_READ binds no identity: nothing was compared, so nothing is granted.
                if entry["published"] is None or entry["verdict"] == "NOT_READ":
                    continue
                with self.subTest(label=label, metric=metric):
                    self.assertEqual("RECORDED_AT_READING_TIME",
                                     entry["checked_identity"]["established_by"])


if __name__ == "__main__":
    unittest.main()
