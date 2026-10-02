"""The bank statement-facts reading, re-derived from the saved reports, and its guards.

tools/read_bank_statement_facts.py reads A01, A02, A05-A08 and A10 off the
bank's annual reports' inline XBRL with the catalog's approved concepts and
formulas, importing none of the route. Each committed position is read again
from the two reports it names (the target and the prior annual report) and
must be the same. Constructed documents hold each guard to what it says: a
prior year the target report restates is not read; a component the catalog
takes from the prior filing is read from it, not from the target's comparative;
a fact with a dimension the catalog does not require is not used; two
namespaces that tag one fact differently give no value; the first approved
concept wins.

Reads the reports from the checkout or the acquisition's export (saved-source
tier). Zero calls.
"""
import ast
import inspect
import json
import unittest
from decimal import Decimal

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_bank_statement_facts as reader
from tools.acceptance_readings import BANK_STATEMENT_READINGS, saved_bytes
from tools.read_statement_facts import document_text

FIELDS = ("read", "why_not_read", "components")
PERIOD = {"period_start": "2021-01-01", "period_end": "2021-12-31",
          "prior_start": "2020-01-01", "prior_end": "2020-12-31"}


def _document(*facts, contexts=None):
    """An inline XBRL fragment: contexts, then facts ``(name, context, shown)``."""
    contexts = contexts or {
        "D21": ("2021-01-01", "2021-12-31", None, ()), "D20": ("2020-01-01", "2020-12-31", None, ()),
        "I21": (None, None, "2021-12-31", ()), "I20": (None, None, "2020-12-31", ())}
    parts = []
    for name, (start, end, instant, members) in contexts.items():
        period = ("<xbrli:instant>%s</xbrli:instant>" % instant if instant else
                  "<xbrli:startDate>%s</xbrli:startDate><xbrli:endDate>%s</xbrli:endDate>"
                  % (start, end))
        dims = "".join('<xbrldi:explicitMember dimension="%s">%s</xbrldi:explicitMember>' % member
                       for member in members)
        parts.append('<xbrli:context id="%s"><xbrli:entity>%s</xbrli:entity>'
                     '<xbrli:period>%s</xbrli:period></xbrli:context>'
                     % (name, "<xbrli:segment>%s</xbrli:segment>" % dims if dims else "", period))
    for name, context, shown in facts:
        parts.append('<ix:nonFraction name="%s" contextRef="%s" unitRef="usd" decimals="-6" '
                     'scale="6">%s</ix:nonFraction>' % (name, context, shown))
    return "".join(parts)


def _branch(metric):
    return reader.specs()[metric]["branches"][0]


class TheCommittedReadingReDerives(unittest.TestCase):

    def test_every_position_re_derives_from_the_two_reports_it_names(self):
        for path in BANK_STATEMENT_READINGS:
            body = json.loads((ROOT / path).read_text(encoding="utf-8"))
            self.assertTrue(body["per_position"])
            for label, case in body["per_position"].items():
                with self.subTest(path=path, label=label):
                    target = document_text(saved_bytes(repo_root=ROOT, relative=case["document"]))
                    prior = (None if case["prior_document"] is None else
                             document_text(saved_bytes(repo_root=ROOT, relative=case["prior_document"])))
                    read = reader.read_position(target_text=target, prior_text=prior,
                                                period=case["period"])
                    for metric in reader.METRICS:
                        self.assertEqual({key: case["metrics"][metric][key] for key in FIELDS},
                                         {key: read[metric][key] for key in FIELDS}, metric)

    def test_every_published_value_matches_or_is_a_recorded_restatement(self):
        for path in BANK_STATEMENT_READINGS:
            rows = [row for case in json.loads((ROOT / path).read_text(encoding="utf-8"))[
                "per_position"].values() for row in case["metrics"].values()]
            self.assertLessEqual({row["verdict"] for row in rows},
                                 {"MATCH", "NO_PUBLISHED_VALUE", "NOT_READ"}, path)
            self.assertIn("MATCH", {row["verdict"] for row in rows}, path)
            # A published value goes unread only where the target report restates
            # the prior year the result took from the prior filing.
            self.assertEqual({"PRIOR_YEAR_RESTATED_IN_THE_TARGET"},
                             {row["why_not_read"] for row in rows if row["verdict"] == "NOT_READ"})

    def test_the_restated_prior_year_end_is_what_the_reading_found(self):
        """FY2021 A05: the FY2021 report restates total assets at the end of 2020."""
        case = json.loads((ROOT / BANK_STATEMENT_READINGS[0]).read_text(encoding="utf-8"))[
            "per_position"]["jpmorgan-2021"]
        prior = [component for component in case["metrics"]["A05"]["components"]
                 if component["accession_role"] == "prior"]
        self.assertEqual(1, len(prior))
        self.assertEqual(("3386071000000", "3384757000000"),
                         (prior[0]["value"], prior[0]["target_report_states"]))


class TheApprovedDefinitionIsTheCatalogs(unittest.TestCase):

    def test_the_specs_are_the_catalog_entries(self):
        catalog = json.loads((ROOT / reader.CATALOG).read_text(encoding="utf-8"))["metrics"]
        self.assertEqual({metric: catalog[metric] for metric in reader.METRICS}, reader.specs())

    def test_every_formula_the_catalog_names_is_read(self):
        for metric in reader.METRICS:
            branch = _branch(metric)
            values = [Decimal(3), Decimal(4), Decimal(6)][:len(branch["components"])]
            self.assertIsNotNone(reader.formula(branch["formula_id"], values), metric)

    def test_the_average_denominator_is_the_mean_of_the_two_year_ends(self):
        self.assertEqual(Decimal("0.6"), reader.formula("average_denominator_ratio",
                                                        [Decimal(3), Decimal(4), Decimal(6)]))


class TheGuardsOnConstructedDocuments(unittest.TestCase):

    def test_a_prior_year_the_target_restates_is_not_read(self):
        target = _document(("us-gaap:NetIncomeLoss", "D21", "50"), ("us-gaap:NetIncomeLoss", "D20", "41"))
        prior = _document(("us-gaap:NetIncomeLoss", "D20", "40"))
        read = reader.read_position(target_text=target, prior_text=prior, period=PERIOD)["A07"]
        self.assertIsNone(read["read"])
        self.assertEqual("PRIOR_YEAR_RESTATED_IN_THE_TARGET", read["why_not_read"])
        unchanged = _document(("us-gaap:NetIncomeLoss", "D21", "50"), ("us-gaap:NetIncomeLoss", "D20", "40"))
        self.assertEqual("10000000", reader.read_position(
            target_text=unchanged, prior_text=prior, period=PERIOD)["A07"]["read"])

    def test_a_prior_component_is_read_from_the_prior_filing(self):
        # The target states no comparative: only the prior filing has the year.
        target = _document(("us-gaap:NetIncomeLoss", "D21", "50"))
        prior = _document(("us-gaap:NetIncomeLoss", "D20", "40"))
        self.assertEqual("10000000", reader.read_position(
            target_text=target, prior_text=prior, period=PERIOD)["A07"]["read"])
        self.assertEqual("PRIOR_FILING_NOT_READ", reader.read_position(
            target_text=target, prior_text=None, period=PERIOD)["A07"]["why_not_read"])

    def test_the_first_approved_concept_wins(self):
        target = _document(("us-gaap:ProfitLoss", "D21", "55"), ("us-gaap:NetIncomeLoss", "D21", "50"),
                           ("us-gaap:NetIncomeLoss", "D20", "40"))
        prior = _document(("us-gaap:NetIncomeLoss", "D20", "40"))
        read = reader.read_position(target_text=target, prior_text=prior, period=PERIOD)["A07"]
        self.assertEqual("NetIncomeLoss", read["components"][0]["concept"])

    def _capital(self, members, name="us-gaap:TierOneRiskBasedCapitalToRiskWeightedAssets"):
        contexts = {"C": (None, None, "2021-12-31", members)}
        return _document((name, "C", "15.7"), contexts=contexts).replace('scale="6"', 'scale="-2"')

    def test_capital_ratios_need_exactly_the_required_dimensions(self):
        required = tuple(sorted(_branch("A01")["components"][0]["required_dimensions"].items()))
        self.assertEqual("0.157", reader.read_position(
            target_text=self._capital(required), prior_text=None, period=PERIOD)["A01"]["read"])
        extra = required + (("dei:LegalEntityAxis", "x:SubsidiaryMember"),)
        self.assertIsNone(reader.read_position(
            target_text=self._capital(extra), prior_text=None, period=PERIOD)["A01"]["read"])
        self.assertIsNone(reader.read_position(
            target_text=self._capital(required[:1]), prior_text=None, period=PERIOD)["A01"]["read"])

    def test_two_namespaces_that_disagree_give_no_value(self):
        required = tuple(sorted(_branch("A01")["components"][0]["required_dimensions"].items()))
        same = self._capital(required) + self._capital(required).replace(
            "us-gaap:TierOne", "x:TierOne").replace('id="C"', 'id="C2"').replace('contextRef="C"', 'contextRef="C2"')
        read = reader.read_position(target_text=same, prior_text=None, period=PERIOD)["A01"]
        self.assertEqual("0.157", read["read"])
        self.assertEqual(["us-gaap", "x"], read["components"][0]["approved_concepts_seen"][
            "TierOneRiskBasedCapitalToRiskWeightedAssets"]["namespaces"])
        differ = same.replace('contextRef="C2" unitRef="usd" decimals="-6" scale="-2">15.7',
                              'contextRef="C2" unitRef="usd" decimals="-6" scale="-2">15.9')
        self.assertNotEqual(same, differ)
        self.assertIsNone(reader.read_position(target_text=differ, prior_text=None,
                                               period=PERIOD)["A01"]["read"])


class TheReaderImportsNoRouteModule(unittest.TestCase):

    def test_no_import_names_a_route_module(self):
        tree = ast.parse(inspect.getsource(reader))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                imported.update(node.module + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        self.assertIn("vnext.normal_period_selection", imported)
        self.assertEqual([], sorted(name for name in imported for route in (
            "deterministic_router", "zero_ai", "calculator", "financial", "companyfacts")
            if route in name))


if __name__ == "__main__":
    unittest.main()
