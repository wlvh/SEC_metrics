"""The bank-measures reading, re-derived from the saved reports, and its guards.

tools/read_bank_measures.py reads A03, A04, A09, A11, A12 and A13 off the
bank's annual report's own tables, importing none of the financial inspectors.
Each committed position is read again from its report's bytes and must be the
same. On the oldest report the rows that carry the measure's words without
being the measure - the counterfactual VaR adjustment, the yield excluding a
business, the international total of another table - are shown to be there and
not read. Constructed tables hold each guard to what it says: tables that
disagree, a header without the target year or without the window, two scales,
and an LCR stated by one source only or under another group are not read.

Reads the reports from the checkout or the acquisition's export (saved-source
tier). Zero calls.
"""
import ast
import inspect
import json
import unittest
from datetime import date

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_bank_measures as reader
from tools.acceptance_readings import BANK_MEASURES_READINGS, saved_bytes

FIELDS = ("reads", "read", "window", "why_not_read")


def _report(label):
    case = json.loads((ROOT / BANK_MEASURES_READINGS[0]).read_text(encoding="utf-8"))[
        "per_position"][label]
    return case, saved_bytes(repo_root=ROOT, relative=case["document"]).decode(
        "utf-8-sig", errors="replace")


def _table(*rows):
    return "<table>" + "".join(
        "<tr>" + "".join("<td>%s</td>" % cell for cell in row) + "</tr>" for row in rows) + "</table>"


def _yield_table(figure="1.64"):
    return _table(["Year ended December 31,"], ["2021", "2020"],
                  ["Net yield on average interest-earning assets – managed basis (a)",
                   figure, "%", "1.78", "%"])


END = date(2021, 12, 31)


class TheCommittedReadingReDerives(unittest.TestCase):

    def test_every_position_of_every_reading_re_derives(self):
        for path in BANK_MEASURES_READINGS:
            body = json.loads((ROOT / path).read_text(encoding="utf-8"))
            self.assertTrue(body["per_position"])
            for label, case in body["per_position"].items():
                with self.subTest(path=path, label=label):
                    text = saved_bytes(repo_root=ROOT, relative=case["document"]).decode(
                        "utf-8-sig", errors="replace")
                    self.assertEqual(case["registrant_name"], reader.registrant_name(text))
                    measures = reader.read_measures(text, case["period_end"])
                    for metric in reader.METRICS:
                        self.assertEqual({key: case["metrics"][metric][key] for key in FIELDS},
                                         {key: measures[metric][key] for key in FIELDS}, metric)

    def test_every_published_value_matches(self):
        for path in BANK_MEASURES_READINGS:
            verdicts = {row["verdict"] for case in json.loads(
                (ROOT / path).read_text(encoding="utf-8"))["per_position"].values()
                for row in case["metrics"].values()}
            self.assertLessEqual(verdicts, {"MATCH", "NO_PUBLISHED_VALUE"}, path)
            self.assertIn("MATCH", verdicts, path)


class TheOldestReportsLookalikesAreNotRead(unittest.TestCase):
    """FY2021, where each measure's words also label a row that is not the measure."""

    @classmethod
    def setUpClass(cls):
        cls.case, cls.text = _report("jpmorgan-2021")
        cls.tables = reader.tables(cls.text)
        # Read again by the code under test, not taken from the committed reading.
        cls.measures = reader.read_measures(cls.text, cls.case["period_end"])

    def _rows(self, label):
        return [(ordinal, row) for ordinal, rows in self.tables for row in rows
                if row and reader._label(row[0]) == label and reader._numbers(row)]

    def test_the_counterfactual_var_total_is_not_the_average(self):
        ordinals = {ordinal for ordinal, _ in self._rows("total var")}
        read = {item["table_ordinal"] for item in self.measures["A12"]["reads"]}
        # The adjustment table names Total VaR too; only the Avg./Min/Max table is read.
        self.assertEqual(1, len(read))
        self.assertGreater(len(ordinals - read), 0)

    def test_the_yield_excluding_a_business_is_not_the_managed_basis(self):
        labels = {reader._label(row[0]) for _, rows in self.tables for row in rows
                  if row and reader._label(row[0]).startswith(
                      "net yield on average interest-earning assets")}
        self.assertGreater(len(labels), 1)
        self.assertEqual({reader._LABELS["A04"]},
                         {reader._label(item["row"][0]) for item in self.measures["A04"]["reads"]})

    def test_an_international_total_outside_the_revenue_table_is_not_read(self):
        ordinals = {ordinal for ordinal, _ in self._rows("total international")}
        read = {item["table_ordinal"] for item in self.measures["A13"]["reads"]}
        self.assertEqual(1, len(read))
        self.assertGreater(len(ordinals - read), 0)


class TheGuardsOnConstructedTables(unittest.TestCase):

    def test_one_table_is_read(self):
        reads = reader.read_by_year_label(_yield_table(), "A04", END)
        self.assertEqual(["0.0164"], [item["value"] for item in reads])
        self.assertEqual(["2021-01-01", "2021-12-31"], reads[0]["window"])

    def test_tables_that_disagree_are_not_read(self):
        measures = reader.read_measures(_yield_table() + _yield_table("1.70"), "2021-12-31")
        self.assertIsNone(measures["A04"]["read"])
        self.assertEqual("TABLES_DISAGREE", measures["A04"]["why_not_read"])

    def test_a_header_without_the_target_year_is_not_read(self):
        # Still a header of years, newest first; only the target year is gone.
        text = _yield_table().replace("<td>2021</td>", "<td>2022</td>")
        self.assertEqual([], reader.read_by_year_label(text, "A04", END))

    def test_a_header_without_the_window_is_not_read(self):
        text = _yield_table().replace("Year ended December 31,", "Three months ended December 31,")
        self.assertEqual([], reader.read_by_year_label(text, "A04", END))

    def test_a_segment_ratio_is_not_the_firmwide_ratio(self):
        row = ["{} loans to total loans outstanding", "0.72", "%", "0.90", "%"]
        segment = _table(["December 31,"], ["2021", "2020"], [row[0].format("Nonaccrual")] + row[1:])
        firmwide = _table(["December 31,"], ["2021", "2020"],
                          [row[0].format("Firmwide nonaccrual")] + row[1:])
        self.assertEqual([], reader.read_by_year_label(segment, "A09", END))
        self.assertEqual(["0.0072"], [item["value"] for item in
                                      reader.read_by_year_label(firmwide, "A09", END)])

    def test_two_scales_in_a_header_are_not_read(self):
        rows = [["December 31,", "(in billions)"], ["2021", "2020"],
                ["Total assets under management", "3,113", "2,716"]]
        self.assertEqual(["3113000000000"], [item["value"] for item in
                                             reader.read_by_year_label(_table(*rows), "A11", END)])
        rows[0] = ["December 31,", "(in billions, except where in millions)"]
        self.assertEqual([], reader.read_by_year_label(_table(*rows), "A11", END))

    def test_international_revenue_is_read_only_under_a_revenue_column(self):
        rows = [["As of or for the year ended December 31, (in millions)", "Revenue (c)",
                 "Expense (d)", "Net income"], ["2021"],
                ["Total international", "28,971", "18,794", "10,177"], ["2020 (b)"],
                ["Total international", "28,595", "18,135", "10,460"]]
        self.assertEqual(["28971000000"], [item["value"] for item in
                                           reader.read_international_revenue(_table(*rows), END)])
        rows[0] = [rows[0][0], "Assets", "Liabilities", "Net"]
        self.assertEqual([], reader.read_international_revenue(_table(*rows), END))

    def test_a_second_revenue_table_is_read_as_well(self):
        # The reader once reused the period end's name for a row index inside
        # this loop, so a second revenue table met an integer where it needed
        # the date; the bank's reports have one such table each.
        rows = [["As of or for the year ended December 31, (in millions)", "Revenue (c)",
                 "Expense (d)"], ["2021"], ["Total international", "28,971", "18,794"]]
        measures = reader.read_measures(_table(*rows) + _table(*rows), "2021-12-31")
        self.assertEqual(2, len(measures["A13"]["reads"]))
        self.assertEqual("28971000000", measures["A13"]["read"])

    def test_average_var_needs_the_avg_min_max_split(self):
        split = _table(["Year ended December 31,", "(in millions)"], ["2021", "2020"],
                       ["Avg.", "Min", "Max", "Avg.", "Min", "Max"],
                       ["Total VaR", "55", "24", "112", "79", "28", "127"])
        unsplit = _table(["Amount by which reported average VaR would have been higher",
                          "Year ended December 31,", "(in millions)"], ["2021", "2020"],
                         ["Total VaR", "4", "9"])
        self.assertEqual(["55000000"], [item["value"] for item in reader.read_average_var(split, END)])
        self.assertEqual([], reader.read_average_var(unsplit, END))


def _lcr(group, quarter=True, selected=True):
    name = '<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="c">Example Bank &amp; Co</ix:nonNumeric>'
    tables = ""
    if quarter:
        tables += _table(["Three months ended"], ["Average amount", "December 31, 2021", "September 30, 2021"],
                         [group + ":"], ["LCR", "111", "%", "110", "%"])
    if selected:
        tables += _table(["Year ended December 31,"], ["2021", "2020"],
                         ["Firm Liquidity coverage ratio (“LCR”) (average)", "111", "%", "114", "%"])
    return name + tables


class TheLcrNeedsBothSourcesUnderTheRegistrant(unittest.TestCase):

    def test_both_sources_under_the_registrant_are_read(self):
        reads = reader.read_lcr(_lcr("Example Bank & Co."), "2021-12-31")
        self.assertEqual({"QUARTER_AVERAGE_TABLE", "SELECTED_FINANCIAL_DATA"},
                         {item["source"] for item in reads})
        self.assertEqual({"1.11"}, {item["value"] for item in reads})
        self.assertEqual({("2021-10-01", "2021-12-31")}, {tuple(item["window"]) for item in reads})

    def test_one_source_alone_is_not_read(self):
        self.assertEqual([], reader.read_lcr(_lcr("Example Bank & Co.", quarter=False), "2021-12-31"))
        self.assertEqual([], reader.read_lcr(_lcr("Example Bank & Co.", selected=False), "2021-12-31"))

    def test_a_subsidiarys_lcr_is_not_the_registrants(self):
        self.assertEqual([], reader.read_lcr(_lcr("Example Bank, N.A."), "2021-12-31"))


class TheReaderImportsNoFinancialInspector(unittest.TestCase):

    def test_no_import_names_a_financial_module(self):
        # The source of the module under test, which is the file's unless an
        # injection loaded another.
        tree = ast.parse(inspect.getsource(reader))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                # "from vnext import x" names the module in its alias.
                imported.add(node.module)
                imported.update(node.module + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        self.assertIn("vnext.normal_period_selection", imported)
        self.assertEqual([], sorted(name for name in imported if "financial" in name))


if __name__ == "__main__":
    unittest.main()
