"""B13 where the approved definition leaves the company out, at a pinned period.

The load-bearing case is the differential: the ordinary route reads the scope
from Issue #28's call policy and this one reads it from the definition's own
heading, so the two sources are held to each other through their answers - for
three companies of three different shapes, field for field and down to the
result identifier. A route that answered "not applicable" for every company
would pass the rest and fail the in-scope refusal; one that ignored the pinned
period would pass the rest and fail the earlier-years case.
"""
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import capacity_run
from vnext import historical_capacity_results as route
from vnext.normal_period_selection import resolve_period_selection

FIELDS = ("applicability", "quality", "publication", "reason_code", "value", "unit",
          "period_start", "period_end", "scope_key", "spec_closure_hash", "value_kind",
          "result_id")


def _historical(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return route.resolve_historical_capacity_metric(
            repo_root=ROOT, company_id=company_id, metric_id="B13",
            period_selection=selection)


class TheScopeIsTheDefinitionsTest(unittest.TestCase):

    def test_the_heading_names_ford_and_enphase(self):
        scope = route.approved_scope(repo_root=ROOT)
        self.assertEqual(["enphase_energy", "ford_motor_company"], scope["company_ids"])
        self.assertEqual(["Ford", "Enphase"], scope["heading_names"])

    def test_a_heading_that_names_no_single_company_stops_the_route(self):
        text = (ROOT / route.DEFINITION_PATH).read_text(encoding="utf-8")
        for replacement in ("（Ford / Nobody）", "（）"):
            with self.subTest(replacement), TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "config").mkdir()
                shutil.copyfile(ROOT / "config/company_registry.csv",
                                root / "config/company_registry.csv")
                (root / route.DEFINITION_PATH).write_text(
                    text.replace("（Ford / Enphase）", replacement), encoding="utf-8")
                with self.assertRaises(route.HistoricalCapacityError):
                    route.approved_scope(repo_root=root)

    def test_a_name_two_companies_answer_to_stops_the_route(self):
        """Taking the first match would pick one of them by file order."""
        registry = (ROOT / "config/company_registry.csv").read_text(encoding="utf-8")
        ford = next(line for line in registry.splitlines()
                    if line.startswith("ford_motor_company,"))
        twin = ford.replace("ford_motor_company,Ford Motor Company", "ford_credit,Ford Credit", 1)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config/company_registry.csv").write_text(
                registry.rstrip("\n") + "\n" + twin + "\n", encoding="utf-8")
            shutil.copyfile(ROOT / route.DEFINITION_PATH, root / route.DEFINITION_PATH)
            with self.assertRaises(route.HistoricalCapacityError) as raised:
                route.approved_scope(repo_root=root)
        self.assertIn("NOT_ONE_COMPANY:Ford", str(raised.exception))


class TheOutOfScopeAnswerTest(unittest.TestCase):

    def test_it_is_the_ordinary_routes_answer_field_for_field(self):
        """Calendar year, a 52/53-week year, and a successor registrant."""
        for company_id, report_end in (("marriott_international", "2025-12-31"),
                                       ("macys", "2026-01-31"),
                                       ("paramount_skydance_paramount_global", "2025-12-31")):
            with self.subTest(company_id):
                with original_sources_only():
                    ordinary = capacity_run.prepare_case(data_root=ROOT,
                                                         company_id=company_id)["results"]["B13"]
                historical = _historical(company_id, report_end)["result"]
                self.assertEqual({field: ordinary[field] for field in FIELDS},
                                 {field: historical[field] for field in FIELDS})

    def test_an_earlier_year_answers_for_that_year(self):
        periods = {report_end: _historical("marriott_international", report_end)
                   for report_end in ("2023-12-31", "2024-12-31")}
        for report_end, component in periods.items():
            with self.subTest(report_end):
                self.assertEqual(report_end, component["result"]["period_end"])
                self.assertEqual("N_A_STRUCTURAL", component["result"]["applicability"])
                self.assertNotEqual(periods["2023-12-31"]["prepared_input"]["filing"]["accessionNumber"],
                                    periods["2024-12-31"]["prepared_input"]["filing"]["accessionNumber"])

    def test_a_company_in_scope_is_refused_rather_than_answered(self):
        with self.assertRaises(route.HistoricalCapacityError) as raised:
            _historical("ford_motor_company", "2025-12-31")
        self.assertEqual("HISTORICAL_B13_IN_SCOPE_NEEDS_THE_SEMANTIC_REVIEW:ford_motor_company",
                         str(raised.exception))
        self.assertFalse(route.out_of_scope(repo_root=ROOT, company_id="enphase_energy"))
        self.assertTrue(route.out_of_scope(repo_root=ROOT, company_id="pfizer"))
        self.assertFalse(route.out_of_scope(repo_root=ROOT, company_id="pfizer", metric_id="D03"))


if __name__ == "__main__":
    unittest.main()
