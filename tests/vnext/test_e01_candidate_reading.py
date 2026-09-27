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
        self.assertFalse({name for name in imported
                          if name.startswith("vnext.") and ("zero_ai" in name or "event_items" in name
                                                            or "deterministic_router" in name)})


if __name__ == "__main__":
    unittest.main()
