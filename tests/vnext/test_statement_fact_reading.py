"""The statement reading that grants 75 acceptances, held to the filings it reads.

tools/read_statement_facts.py replaces a reading whose code was never
committed and which skipped every value ``int()`` could not parse. Each case
below is one rule the filings need, checked where a filing needs it, plus the
committed reading re-derived from the saved bytes.
"""
import ast
import json
import unittest
from decimal import Decimal

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_statement_facts as reader

READING = "docs/evidence/issue47_history/content-acceptance/cross-source-read.json"


def _committed():
    return json.loads((ROOT / READING).read_text(encoding="utf-8"))["per_position"]


def _text(label):
    return (ROOT / _committed()[label]["document"]).read_text(encoding="utf-8-sig",
                                                              errors="replace")


def _fiscal_year(label):
    period = _committed()[label]["period"]
    return (period["period_start"], period["period_end"], False)


class TheReaderIsNotTheRouteTest(unittest.TestCase):

    def test_it_imports_none_of_the_route_s_statement_modules(self):
        tree = ast.parse((ROOT / "tools/read_statement_facts.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for route_module in ("calculator", "historical_results", "normal_companyfacts_results",
                             "deterministic_router", "historical_zero_ai_results",
                             "normal_zero_ai_results", "ordinary_financial_results"):
            with self.subTest(route_module):
                self.assertFalse([name for name in imported if route_module in name])


class EachRuleOnTheFilingThatNeedsItTest(unittest.TestCase):

    def test_a_value_with_a_decimal_point_is_read(self):
        """The fact the earlier reading could not see: '1.2' at scale 9."""
        facts, unread = reader.parse_facts(_text("salesforce-2026"))
        self.assertEqual([], unread)
        self.assertEqual(Decimal("1200000000"), reader.pick(
            facts, ["DepreciationDepletionAndAmortization"], _fiscal_year("salesforce-2026"))[1])

    def test_a_value_tagged_again_elsewhere_is_one_fact(self):
        """Every filing here tags net income more than once for the year - the
        statement, the cash flow statement, notes. Counting each as a candidate
        would make the chain's first concept ambiguous everywhere. (No filing
        here tags a rounded copy of a needed value in the same context; that
        rule is exercised by a built case below.)"""
        facts, _ = reader.parse_facts(_text("marriott-2025"))
        entries = facts["NetIncomeLoss"][_fiscal_year("marriott-2025")]
        self.assertGreater(len(entries), 1)
        self.assertEqual((entries[0][0], None), reader.consolidate(entries))

    def test_two_names_for_total_d_and_a_that_disagree_accept_neither(self):
        case = reader.read_case(text=_text("salesforce-2026"),
                                period=_committed()["salesforce-2026"]["period"],
                                published={"B03": "0.2295243829018663455749548465"})
        self.assertEqual("DIRECT_CANDIDATES_DISAGREE", case["metrics"]["B03"]["verdict"])
        self.assertEqual({"DepreciationDepletionAndAmortization": "1200000000.0",
                          "DepreciationAndAmortization": "3631000000"},
                         case["metrics"]["B03"]["direct_d_and_a_candidates"])

    def test_two_names_that_agree_are_one_quantity(self):
        facts, _ = reader.parse_facts(_text("lumen-2025"))
        found = reader.values_for(facts, reader.DA, _fiscal_year("lumen-2025"))
        self.assertEqual(2, len(found))
        self.assertEqual(1, len({value for value, _ in found.values()}))

    def test_a_later_revenue_concept_is_recorded_not_treated_as_a_contradiction(self):
        """Contract revenue before total revenues is the definition's order."""
        row = _committed()["lumen-2025"]
        self.assertEqual({"Revenues": "12402000000"},
                         row["later_chain_concepts_the_filing_also_tags"]["revenue"])
        self.assertEqual("MATCH", row["metrics"]["B01"]["verdict"])


class TheBuiltCasesTest(unittest.TestCase):

    def test_the_fixed_zero_dash_is_zero(self):
        text = ('<xbrli:context id="c"><xbrli:period><xbrli:startDate>2025-01-01'
                '</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>'
                '</xbrli:period></xbrli:context>'
                '<ix:nonFraction name="us-gaap:InterestExpense" contextRef="c" '
                'format="ixt:fixed-zero" decimals="-6" scale="6">&#8212;</ix:nonFraction>')
        facts, unread = reader.parse_facts(text)
        self.assertEqual([], unread)
        self.assertEqual([(Decimal(0), "-6")],
                         facts["InterestExpense"][("2025-01-01", "2025-12-31", False)])

    def test_duplicates_that_do_not_round_to_each_other_have_no_value(self):
        self.assertEqual((None, "INCONSISTENT_DUPLICATES"), reader.consolidate(
            [(Decimal("27300000000"), "-8"), (Decimal("27412000000"), "-6")]))
        self.assertEqual((Decimal("27312000000"), None), reader.consolidate(
            [(Decimal("27300000000"), "-8"), (Decimal("27312000000"), "-6")]))

    def test_an_unparseable_needed_value_is_listed_not_dropped(self):
        text = ('<xbrli:context id="c"><xbrli:period><xbrli:startDate>2025-01-01'
                '</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>'
                '</xbrli:period></xbrli:context>'
                '<ix:nonFraction name="us-gaap:Revenues" contextRef="c" '
                'format="ixt-sec:numwordsen" scale="9">three</ix:nonFraction>')
        facts, unread = reader.parse_facts(text)
        self.assertNotIn("Revenues", facts)
        self.assertEqual(["Revenues"], [entry["concept"] for entry in unread])


class TheCommittedReadingRederivesFromTheBytesTest(unittest.TestCase):

    def test_every_position_and_metric(self):
        for label, row in _committed().items():
            published = {metric: entry["published"] for metric, entry in row["metrics"].items()}
            case = reader.read_case(text=_text(label), period=row["period"], published=published)
            with self.subTest(label):
                self.assertEqual({m: (e["read"], e["verdict"]) for m, e in row["metrics"].items()},
                                 {m: (e["read"], e["verdict"]) for m, e in case["metrics"].items()})
                self.assertEqual(row["concepts_used"], case["concepts_used"])

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
