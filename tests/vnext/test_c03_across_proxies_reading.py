"""The older-year C03 reading, held to the saved proxies.

tools/read_c03_across_proxies.py accepts a year's CEO pay only when every saved
proxy that tags it reports one total, they agree, and a proxy the result does
not name is among them - or, for a year the proxies disagree on, when the
owner's decision says a year is its first report and the first proxy (the
filing the result names) reports that total. Reads the acquisition's export
(saved-source tier). Zero calls.
"""
import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_c03_across_proxies as reader
from tools.acceptance_readings import C03_ACROSS_PROXIES

BATCH = C03_ACROSS_PROXIES[0]
ROUND3 = C03_ACROSS_PROXIES[1]


def _committed(path=BATCH):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))["per_position"]


def _decision(path=BATCH):
    return json.loads((ROOT / path).read_text(encoding="utf-8")).get("first_reported_decision")


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_governance_modules(self):
        tree = ast.parse((ROOT / "tools/read_c03_across_proxies.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("governance_signals", "historical_governance_results",
                             "historical_governance_input", "historical_proxy_compensation",
                             "historical_dei"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class TheCommittedReadingRederivesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.proxies = reader.saved_proxies()
        cls.committed = _committed()

    def _read(self, row, *, result_filings=None, first_reported=None):
        if result_filings is None:
            result_filings = {report["accession"] for report in row["proxies_reporting_the_target_period"]
                              if report["named_by_the_result"]}
        return reader.read_year(
            proxies=[proxy for cik in row["ciks"] for proxy in self.proxies.get(cik, [])],
            period=row["period"], result_filings=result_filings, published=row["published"],
            first_reported=first_reported)

    def test_every_position_of_every_reading(self):
        for path in C03_ACROSS_PROXIES:
            for label, row in _committed(path).items():
                with self.subTest(reading=path, label=label):
                    read = self._read(row, first_reported=_decision(path))
                    self.assertEqual({key: row[key] for key in read}, read)

    def test_without_the_decision_a_disagreeing_year_is_not_chosen_between(self):
        read = self._read(self.committed["macys-2024"], first_reported=None)
        self.assertEqual(("NOT_READ", "PROXIES_REPORT_DIFFERENT_AMOUNTS"),
                         (read["verdict"], read["why_not_read"]))
        amounts = {value for report in read["proxies_reporting_the_target_period"]
                   for value in report["values"]}
        self.assertEqual({11563739, 11821259}, amounts)
        self.assertNotIn("read_as", read)

    def test_under_the_decision_each_disagreeing_year_is_its_first_report(self):
        """Macy's FY2023 (clawback later) and Marriott 2022 (flights added later)."""
        self.assertEqual(reader.DECISION, reader.first_reported_decision())
        for path, label, first, later in ((BATCH, "macys-2024", "11821259", [11563739]),
                                          (ROUND3, "marriott-2022", "18686271", [18715093])):
            row = _committed(path)[label]
            with self.subTest(label):
                self.assertEqual(("MATCH", first, "FIRST_REPORTED", later, reader.DECISION),
                                 (row["verdict"], row["read"], row["read_as"],
                                  row["later_amounts"], row["decision"]))
                self.assertTrue(row["confirmed_only_by_the_filing_the_route_read"])
                # The first report is the earliest proxy by its own year, not by
                # accession text: Macy's later proxies were filed by another agent.
                reports = row["proxies_reporting_the_target_period"]
                first_report = next(r for r in reports if r["accession"] == row["first_report"])
                self.assertTrue(first_report["named_by_the_result"])
                self.assertEqual(min(int(r["accession"].split("-")[1]) for r in reports),
                                 int(row["first_report"].split("-")[1]))

    def test_a_first_report_the_result_does_not_name_is_not_read(self):
        row = self.committed["macys-2024"]
        later = {r["accession"] for r in row["proxies_reporting_the_target_period"]
                 if not r["named_by_the_result"]}
        read = self._read(row, result_filings=later, first_reported=reader.DECISION)
        self.assertEqual(("NOT_READ", "FIRST_REPORT_NOT_ONE_TOTAL_IN_THE_FILING_THE_RESULT_NAMES"),
                         (read["verdict"], read["why_not_read"]))

    def test_a_value_only_the_result_s_own_filing_reports_is_not_accepted(self):
        row = self.committed["enphase-2023"]
        self.assertEqual("MATCH", row["verdict"])
        every = {report["accession"] for report in row["proxies_reporting_the_target_period"]}
        read = self._read(row, result_filings=every)
        self.assertEqual(("NOT_READ", "ONLY_THE_FILING_THE_RESULT_NAMES_REPORTS_IT"),
                         (read["verdict"], read["why_not_read"]))

    def test_a_year_with_two_chief_executives_is_not_chosen_between(self):
        # Lumen's 2022: Jeff Storey and Kathleen Johnson both have a PEO total
        # in every proxy that reports the year.
        read = reader.read_year(proxies=self.proxies["18926"], period=["2022-01-01", "2022-12-31"],
                                result_filings=set(), published="19816806")
        self.assertEqual(("NOT_READ", "SEVERAL_PEO_TOTALS_IN_ONE_PROXY"),
                         (read["verdict"], read["why_not_read"]))
        self.assertEqual(4, len(read["proxies_reporting_the_target_period"]))

    def test_the_accepted_positions_are_confirmed_by_a_filing_the_result_does_not_name(self):
        for path in C03_ACROSS_PROXIES:
            for label, row in _committed(path).items():
                # A first report is confirmed by the route's own filing only, and says so.
                if row["verdict"] != "MATCH" or row.get("read_as") == "FIRST_REPORTED":
                    continue
                with self.subTest(reading=path, label=label):
                    self.assertTrue([report for report in row["proxies_reporting_the_target_period"]
                                     if not report["named_by_the_result"]])


if __name__ == "__main__":
    unittest.main()
