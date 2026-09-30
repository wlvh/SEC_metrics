"""The older-year C03 reading, held to the saved proxies.

tools/read_c03_across_proxies.py accepts a year's CEO pay only when every saved
proxy that tags it reports one total, they agree, and a proxy the result does
not name is among them. Reads the acquisition's export (saved-source tier).
Zero calls.
"""
import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_c03_across_proxies as reader

READING = "docs/evidence/issue47_history/content-acceptance/c03-across-proxies-read-batch.json"


def _committed():
    return json.loads((ROOT / READING).read_text(encoding="utf-8"))["per_position"]


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

    def _read(self, row, *, result_filings=None):
        if result_filings is None:
            result_filings = {report["accession"] for report in row["proxies_reporting_the_target_period"]
                              if report["named_by_the_result"]}
        return reader.read_year(
            proxies=[proxy for cik in row["ciks"] for proxy in self.proxies.get(cik, [])],
            period=row["period"], result_filings=result_filings, published=row["published"])

    def test_every_position(self):
        for label, row in self.committed.items():
            with self.subTest(label):
                read = self._read(row)
                self.assertEqual({key: row[key] for key in read}, read)

    def test_a_year_two_proxies_report_differently_is_not_chosen_between(self):
        read = self._read(self.committed["macys-2024"])
        self.assertEqual(("NOT_READ", "PROXIES_REPORT_DIFFERENT_AMOUNTS"),
                         (read["verdict"], read["why_not_read"]))
        amounts = {value for report in read["proxies_reporting_the_target_period"]
                   for value in report["values"]}
        self.assertEqual({11563739, 11821259}, amounts)

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
        for label, row in self.committed.items():
            if row["verdict"] != "MATCH":
                continue
            with self.subTest(label):
                self.assertTrue([report for report in row["proxies_reporting_the_target_period"]
                                 if not report["named_by_the_result"]])


if __name__ == "__main__":
    unittest.main()
