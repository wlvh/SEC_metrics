"""The E01 candidate reading that grants a zero under the content-confirmed definition.

tools/read_e01_candidates.py accepts exactly one kind of answer: a window with no
candidate item (1.01, 2.01, 8.01), whose count is zero without any confirmation.
A reader that always found nothing would grant that answer everywhere, so the
committed reading is recomputed from the saved headers and a window known to
hold candidates must show them.
"""
import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_e01_candidates as reader
from tools.read_event_counts import filings_in_index

READING = "docs/evidence/issue47_history/content-acceptance/e01-content-confirmed-read.json"


def _window(company_id, report_end):
    from tools.read_event_counts import _case_input
    from sec_urls import submissions_url
    from vnext.annual_update import saved_source
    period, cik = _case_input(company_id=company_id, report_end=report_end)
    saved = saved_source(repo_root=ROOT, url=submissions_url(cik=int(cik)))
    return reader.window_candidates(filings=filings_in_index(json.loads(saved["raw"])), cik=cik,
                                    start=period["period_start"], end=period["period_end"],
                                    codes=reader.candidate_codes())


class TheCandidateReadingIsTheSavedHeaders(unittest.TestCase):
    def test_the_committed_zero_is_what_the_headers_say(self):
        row = json.loads((ROOT / READING).read_text(encoding="utf-8"))["per_position"]["enphase-2025"]
        seen, unreadable = _window("enphase_energy", "2025-12-31")
        self.assertEqual([], unreadable)
        self.assertEqual(row["filings_in_window"], [entry["accession"] for entry in seen["filing_date"]])
        self.assertEqual({"filing_date": 0, "report_date": 0},
                         {basis: sum(len(e["candidate_items"]) for e in entries)
                          for basis, entries in seen.items()})
        self.assertEqual(("MATCH", "0"), (row["verdict"], row["published"]))

    def test_a_window_with_candidates_shows_them(self):
        # Ford 2025 holds seven candidate items (its E01 is withheld pending
        # confirmation); a reader that found nothing would call it zero.
        seen, unreadable = _window("ford_motor_company", "2025-12-31")
        self.assertEqual([], unreadable)
        found = sum(len(entry["candidate_items"]) for entry in seen["filing_date"])
        self.assertGreater(found, 0)

    def test_the_candidate_codes_are_the_successor_route_s(self):
        route = json.loads((ROOT / reader.ROUTE).read_text(encoding="utf-8"))["route"]
        self.assertEqual(sorted(route["candidate_item_codes"]), reader.candidate_codes())
        self.assertEqual(["1.01", "2.01", "8.01"], reader.candidate_codes())

    def test_the_reader_imports_nothing_from_the_route(self):
        tree = ast.parse((ROOT / "tools/read_e01_candidates.py").read_text(encoding="utf-8"))
        imported = {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}
        # "from vnext import x" names the module in its alias.
        imported |= {node.module + "." + alias.name for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module for alias in node.names}
        self.assertFalse({name for name in imported
                          if name.startswith("vnext.") and ("zero_ai" in name or "event_items" in name
                                                            or "deterministic_router" in name)})


class TheOlderWindowsAreReadOffTheExportTest(unittest.TestCase):
    """The batch's older windows, read over a restored root and recounted without it.

    Every header the reading used was recorded with the path it read, and the
    submissions index by its path; both are read back here from the checkout or
    the acquisition's export, so the zero is recomputed without the root.
    """

    BATCH = "docs/evidence/issue47_history/content-acceptance/e01-content-confirmed-read-batch.json"

    def test_every_committed_position_recounts_from_the_bytes_it_names(self):
        from tools.acceptance_readings import saved_bytes
        from tools.read_event_counts import header_items, items_of
        rows = json.loads((ROOT / self.BATCH).read_text(encoding="utf-8"))["per_position"]
        self.assertTrue(rows)
        for label, row in rows.items():
            with self.subTest(label):
                submissions = json.loads(saved_bytes(repo_root=ROOT,
                                                     relative=row["submissions_index"]))
                recorded = {entry["accession"]: entry["header"]
                            for entries in row["filings"].values() for entry in entries
                            if "header" in entry}

                def header(cik, accession):
                    items = header_items(cik, accession)
                    if items is not None:
                        return items, None
                    if accession not in recorded:
                        return None, None
                    return (items_of(saved_bytes(repo_root=ROOT, relative=recorded[accession])
                                     .decode("utf-8", errors="replace")), recorded[accession])
                seen, unreadable = reader.window_candidates(
                    filings=filings_in_index(submissions), cik=int(submissions["cik"]),
                    start=row["window"][0], end=row["window"][1], codes=reader.candidate_codes(),
                    header=header)
                self.assertEqual(row["filings"], seen)
                self.assertEqual(row["headers_not_saved"], unreadable)
                self.assertEqual(row["candidate_items_by_basis"],
                                 {basis: sum(len(entry["candidate_items"]) for entry in entries)
                                  for basis, entries in seen.items()})

    def test_a_restored_root_reading_is_a_reading_of_its_own(self):
        import sys
        from unittest.mock import patch
        argv = ["read_e01_candidates.py", "--runs-root", "/nonexistent", "--closure", "sha256:x",
                "--case", "enphase-2022=enphase_energy:2022-12-31", "--source-root", "/nonexistent",
                "--output", reader.CHECKOUT_READING]
        with patch.object(sys, "argv", argv), self.assertRaises(SystemExit) as refused:
            reader.main()
        self.assertEqual("A_SOURCE_ROOT_READING_IS_WRITTEN_TO_A_READING_OF_ITS_OWN",
                         str(refused.exception))


if __name__ == "__main__":
    unittest.main()
