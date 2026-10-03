"""The older-year C03 reading, held to the saved proxies.

tools/read_c03_across_proxies.py accepts a year's CEO pay only when every saved
proxy that tags it reports one total, they agree, and a proxy the result does
not name is among them - or, for a year the proxies disagree on, when the
owner's decision says a year is its first report and the first proxy (the
filing the result names) reports that total. A first report the tags cannot
reach (a proxy filed before the pay-versus-performance table) is read off that
filing's Summary Compensation Table. Reads the acquisition's export
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
ROUND_3FBA = C03_ACROSS_PROXIES[3]


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
                # "from vnext import x" names the module in its alias.
                imported.add(node.module)
                imported.update(node.module + "." + alias.name for alias in node.names)
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
            result_filings |= {report["accession"] for report in row.get("untagged_first_reports", ())}
        registrant = [proxy for cik in row["ciks"] for proxy in self.proxies.get(cik, [])]
        return reader.read_year(
            proxies=registrant, period=row["period"], result_filings=result_filings,
            published=row["published"], first_reported=first_reported,
            untagged=lambda: reader.untagged_reports(
                documents=reader.documents_of_filings(result_filings), proxies=registrant,
                period=row["period"], result_filings=result_filings))

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

    def test_a_first_report_the_tags_cannot_reach_is_read_off_its_table(self):
        """JPMorgan FY2021: the 2022 proxy tags no total; the later proxies disagree."""
        row = _committed(ROUND_3FBA)["jpmorgan-2021"]
        self.assertEqual(("MATCH", "84428145", "FIRST_REPORTED", "SUMMARY_COMPENSATION_TABLE"),
                         (row["verdict"], row["read"], row["read_as"], row["first_report_read_from"]))
        table = row["untagged_first_reports"]
        self.assertEqual(1, len(table))
        self.assertEqual(["James Dimon"], table[0]["peo_names_in_the_tagged_proxies"])
        self.assertEqual(sum(table[0]["components"]), table[0]["values"][0])
        self.assertEqual(row["first_report"], table[0]["accession"])
        # Every tagged report came later, and they do not agree with each other.
        self.assertTrue(all(int(r["accession"].split("-")[1]) > int(row["first_report"].split("-")[1])
                            for r in row["proxies_reporting_the_target_period"]))
        self.assertEqual([84428145, 85159860], row["later_amounts"])

    def test_without_the_table_the_untagged_first_report_is_not_read(self):
        row = _committed(ROUND_3FBA)["jpmorgan-2021"]
        registrant = [proxy for cik in row["ciks"] for proxy in self.proxies.get(cik, [])]
        read = reader.read_year(proxies=registrant, period=row["period"],
                                result_filings={row["first_report"]}, published=row["published"],
                                first_reported=reader.DECISION)
        self.assertEqual(("NOT_READ", "FIRST_REPORT_NOT_ONE_TOTAL_IN_THE_FILING_THE_RESULT_NAMES"),
                         (read["verdict"], read["why_not_read"]))

    def test_a_table_filed_after_a_tagged_report_is_not_the_first_report(self):
        row = _committed(ROUND_3FBA)["jpmorgan-2021"]
        registrant = [proxy for cik in row["ciks"] for proxy in self.proxies.get(cik, [])]
        later = {"accession": "0000019617-24-000999", "values": [84428145], "named_by_the_result": True}
        read = reader.read_year(proxies=registrant, period=row["period"],
                                result_filings={later["accession"]}, published=row["published"],
                                first_reported=reader.DECISION, untagged=lambda: [later])
        self.assertEqual(("NOT_READ", "FIRST_REPORT_NOT_ONE_TOTAL_IN_THE_FILING_THE_RESULT_NAMES"),
                         (read["verdict"], read["why_not_read"]))

    def test_the_table_is_not_read_when_the_tags_name_two_peos(self):
        row = _committed(ROUND_3FBA)["jpmorgan-2021"]
        table = row["untagged_first_reports"][0]
        sct = "<p>Summary Compensation Table</p>" + _table(
            HEADER, ["James Dimon CEO", "2021", "1,000", "500", "7,000", "250", "8,750"])
        tagged = ('<xbrli:context id="c1"><xbrli:period><xbrli:startDate>2021-01-01</xbrli:startDate>'
                  '<xbrli:endDate>2021-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
                  '<ix:nonNumeric name="ecd:PeoName" contextRef="c1">James Dimon</ix:nonNumeric>'
                  '<ix:nonNumeric name="ecd:PeoName" contextRef="c1">Lee Kim</ix:nonNumeric>')
        reports = reader.untagged_reports(
            documents=[{"document": table["document"], "sha256": "s", "text": sct}],
            proxies=[{"text": tagged}], period=row["period"], result_filings={table["accession"]})
        self.assertEqual(["THE_TAGGED_PROXIES_DO_NOT_NAME_ONE_PEO_FOR_THE_YEAR"],
                         [report.get("refused") for report in reports])

    def test_the_accepted_positions_are_confirmed_by_a_filing_the_result_does_not_name(self):
        for path in C03_ACROSS_PROXIES:
            for label, row in _committed(path).items():
                # A first report is confirmed by the route's own filing only, and says so.
                if row["verdict"] != "MATCH" or row.get("read_as") == "FIRST_REPORTED":
                    continue
                with self.subTest(reading=path, label=label):
                    self.assertTrue([report for report in row["proxies_reporting_the_target_period"]
                                     if not report["named_by_the_result"]])


def _table(*rows):
    return "<table>" + "".join("<tr>" + "".join("<td>" + cell + "</td>" for cell in row) + "</tr>"
                               for row in rows) + "</table>"


HEADER = ["Name and principal position", "Year", "Salary ($)1", "Bonus($)2", "Stock awards ($)",
          "All other compensation ($)", "Total ($)"]


class TheTableIsReadByItsOwnArithmeticTest(unittest.TestCase):
    """table_total on small tables written for the case; zero files read."""

    def test_the_summary_compensation_table_and_not_another_pay_table(self):
        committee_view = _table(["Name and principal position", "Year", "Salary", "Cash", "PSUs", "Total"],
                                ["Pat RowChief Executive Officer", "2021", "$", "1,000", "$", "2,000",
                                 "$", "3,000", "$", "6,000"])
        sct = _table(HEADER, ["Pat RowChief Executive Officer", "2021", "$", "1,000", "$", "500",
                              "$", "7,000", "$", "250", "7", "$", "8,750"],
                     ["2020", "1,000", "—", "6,000", "200", "7,200"])
        read = reader.table_total(text=committee_view + sct, name="Pat Row", year="2021")
        self.assertEqual((8750, [1000, 500, 7000, 250]),
                         (read.get("total"), read.get("components")))

    def test_a_row_whose_components_do_not_add_up_is_not_read(self):
        sct = _table(HEADER, ["Pat Row CEO", "2021", "1,000", "500", "7,000", "250", "9,999"])
        self.assertEqual({"refused": "THE_COMPONENTS_DO_NOT_ADD_UP_TO_THE_TOTAL"},
                         reader.table_total(text=sct, name="Pat Row", year="2021"))

    def test_a_year_row_continues_the_person_above_and_no_one_else(self):
        sct = _table(HEADER, ["Pat Row CEO", "2021", "1,000", "500", "7,000", "250", "8,750"],
                     ["2020", "1,000", "—", "6,000", "200", "7,200"],
                     ["Lee Kim CFO", "2021", "900", "—", "1,000", "100", "2,000"])
        self.assertEqual(7200, reader.table_total(text=sct, name="Pat Row", year="2020")["total"])
        self.assertEqual(2000, reader.table_total(text=sct, name="Lee Kim", year="2021")["total"])

    def test_two_rows_for_the_person_and_year_are_not_chosen_between(self):
        sct = _table(HEADER, ["Pat Row CEO", "2021", "1,000", "500", "7,000", "250", "8,750"])
        self.assertEqual({"refused": "THE_NAMED_PEO_HAS_2_ROWS_FOR_THE_YEAR"},
                         reader.table_total(text=sct + sct, name="Pat Row", year="2021"))

    def test_the_table_is_read_only_for_the_one_peo_the_tags_name(self):
        tagged = ('<xbrli:context id="c1"><xbrli:period><xbrli:startDate>2021-01-01</xbrli:startDate>'
                  '<xbrli:endDate>2021-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
                  '<ix:nonNumeric name="ecd:PeoName" contextRef="c1">Pat Row</ix:nonNumeric>'
                  '<ix:nonNumeric name="ecd:PeoName" contextRef="c1">Lee Kim</ix:nonNumeric>')
        self.assertEqual({"Pat Row", "Lee Kim"},
                         reader.peo_names_for([{"text": tagged}], ("2021-01-01", "2021-12-31")))
        self.assertEqual(set(), reader.peo_names_for([{"text": tagged}], ("2020-01-01", "2020-12-31")))


if __name__ == "__main__":
    unittest.main()
