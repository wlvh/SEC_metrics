"""A metric that does not apply is an answer, not a missing implementation.

The coverage frame reported eighty-two positions as HISTORICAL_ROUTE_NOT_WIRED
because six metrics are gated on `financial` and none of the reachable
companies is a bank, and two are gated on `lodging` and eight of the ten are
not hotels. That reads as "we have not built this" for a question the Spec's
own applicability and the registry's own traits already answer.

The load-bearing case is the refusal. A route that answered "not applicable"
whenever it was asked would satisfy every positive case here and would be
making a false statement about Marriott's occupancy.
"""
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.calculator import metric_is_applicable
from vnext.historical_structural_results import (SPEC_PATHS, HistoricalStructuralError,
                                                 resolve_historical_structural_metric,
                                                 structurally_not_applicable)
from vnext.normal_period_selection import resolve_period_selection
from vnext.specs import compile_spec_file
from vnext.traits import repository_company_traits

RETAILER = ("macys", "2026-01-31")
HOTEL = ("marriott_international", "2025-12-31")


class OnlyWhereTheTraitsSayItDoesNotApplyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.retail_selection = resolve_period_selection(repo_root=ROOT,
                                                            company_id=RETAILER[0],
                                                            report_end=RETAILER[1])
            cls.hotel_selection = resolve_period_selection(repo_root=ROOT,
                                                           company_id=HOTEL[0],
                                                           report_end=HOTEL[1])

    def test_every_declared_spec_is_gated_on_a_trait(self):
        """A Spec without a gate can never be structurally non-applicable."""
        for metric_id, path in SPEC_PATHS.items():
            with self.subTest(metric=metric_id):
                compiled = compile_spec_file(path=ROOT / path,
                                             dependency_specs={})["compiled"]
                self.assertEqual(metric_id, compiled["metric_id"])
                self.assertTrue(compiled["applicability"]["all"]
                                or compiled["applicability"]["none"])
                self.assertFalse(compiled["dependencies"])

    def test_the_route_refuses_the_company_the_metric_is_for(self):
        """Marriott's occupancy is exactly what must not be answered this way."""
        for metric_id in ("B10", "B11"):
            with self.subTest(metric=metric_id):
                self.assertFalse(structurally_not_applicable(
                    repo_root=ROOT, company_id=HOTEL[0], metric_id=metric_id))
                with original_sources_only():
                    with self.assertRaises(HistoricalStructuralError) as refused:
                        resolve_historical_structural_metric(
                            repo_root=ROOT, company_id=HOTEL[0], metric_id=metric_id,
                            period_selection=self.hotel_selection)
                self.assertEqual(
                    "HISTORICAL_STRUCTURAL_METRIC_IS_APPLICABLE_HERE:%s:%s"
                    % (HOTEL[0], metric_id), str(refused.exception))
                self.assertEqual("IMPLEMENTATION_GAP", refused.exception.category)

    def test_a_metric_this_route_does_not_carry_is_refused_by_name(self):
        for metric_id in ("B01", "B06", "B13", "D02"):
            with self.subTest(metric=metric_id):
                self.assertFalse(structurally_not_applicable(
                    repo_root=ROOT, company_id=RETAILER[0], metric_id=metric_id))
                with self.assertRaises(HistoricalStructuralError) as refused:
                    resolve_historical_structural_metric(
                        repo_root=ROOT, company_id=RETAILER[0], metric_id=metric_id,
                        period_selection=self.retail_selection)
                self.assertEqual("HISTORICAL_STRUCTURAL_METRIC_NOT_WIRED:" + metric_id,
                                 str(refused.exception))

    def test_the_answer_comes_from_the_shared_calculator_not_from_here(self):
        """This route supplies the period and the company; it decides nothing.

        calculate_metric refuses to consume a fact for a metric whose traits do
        not match and builds the N_A_STRUCTURAL result itself, so the check is
        that what comes back is what it produces - a published structural
        non-applicability with no value and no observations.
        """
        traits = list(repository_company_traits(repo_root=ROOT, company_id=RETAILER[0]))
        with original_sources_only():
            for metric_id in sorted(SPEC_PATHS):
                with self.subTest(metric=metric_id):
                    compiled = compile_spec_file(path=ROOT / SPEC_PATHS[metric_id],
                                                 dependency_specs={})["compiled"]
                    self.assertFalse(metric_is_applicable(
                        applicability=compiled["applicability"], traits=traits))
                    component = resolve_historical_structural_metric(
                        repo_root=ROOT, company_id=RETAILER[0], metric_id=metric_id,
                        period_selection=self.retail_selection)
                    result = component["result"]
                    self.assertEqual("N_A_STRUCTURAL", result["applicability"])
                    self.assertEqual("TRAIT_NOT_APPLICABLE", result["reason_code"])
                    self.assertEqual("PUBLISHED", result["publication"])
                    self.assertIsNone(result["value"])
                    self.assertEqual([], component["observations"])
                    self.assertEqual([], component["claims"])
                    self.assertEqual({"provider": 0, "paid": 0, "sec": 0},
                                     component["calls"])

    def test_the_run_is_still_bound_to_the_period_that_was_asked_for(self):
        """Otherwise it is a free-floating assertion rather than a year's answer."""
        with original_sources_only():
            component = resolve_historical_structural_metric(
                repo_root=ROOT, company_id=RETAILER[0], metric_id="A03",
                period_selection=self.retail_selection)
        self.assertEqual(RETAILER[1], component["target_period"]["period_end"])
        self.assertEqual(RETAILER[1], component["result"]["period_end"])
        self.assertEqual(self.retail_selection["current_filing"]["accessionNumber"],
                         component["target"]["accession"])
        # And to the sources that period was admitted with, so the record is
        # checkable rather than merely consistent with itself.
        self.assertTrue(component["source_references"])
        self.assertFalse(component["selection"]["value_taken_from_any_filing"])
        self.assertFalse(component["selection"]["disclosure_absence_asserted"])

    def test_the_coverage_frame_counts_a_route_per_position_not_per_metric(self):
        from vnext.historical_coverage import (STRUCTURAL_APPLICABILITY_METRICS,
                                               WIRED_HISTORICAL_METRICS)
        self.assertEqual(sorted(SPEC_PATHS), sorted(STRUCTURAL_APPLICABILITY_METRICS))
        # None of these is in the per-metric wired list, because none of them
        # has a route at the company the metric is actually for.
        self.assertFalse(set(STRUCTURAL_APPLICABILITY_METRICS)
                         & set(WIRED_HISTORICAL_METRICS))
        self.assertTrue(structurally_not_applicable(repo_root=ROOT,
                                                    company_id=RETAILER[0], metric_id="B10"))
        self.assertFalse(structurally_not_applicable(repo_root=ROOT,
                                                     company_id=HOTEL[0], metric_id="B10"))


if __name__ == "__main__":
    unittest.main()
