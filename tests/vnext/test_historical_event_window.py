"""An event window is a measurement; a Run coordinate is a fiscal identity.

For a continuous primary registrant the two happen to be the same dates, which
is why one field served both for as long as it did. For a successor registrant
the approved policy widens the event window to the prior calendar year's start,
and then they are not the same thing at all: the widened window is two years of
filing dates, and a Run claiming it as its fiscal coordinate is refused -
correctly - for exceeding 53 weeks.

The two wrong answers are easy to reach from here. Widening the coordinate
makes the Run claim a fiscal year it did not have; narrowing the sources to fit
the coordinate drops filings the policy says belong to the measurement. These
cases assert neither happened.
"""
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_results import _run_coordinate
from vnext.historical_zero_ai_results import (event_measurement_window,
                                              resolve_historical_zero_ai_metric)
from vnext.normal_period_selection import resolve_period_selection

SUCCESSOR = "paramount_skydance_paramount_global"
CONTINUOUS = "pfizer"
PERIOD = "2025-12-31"
PINNED = {"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"}
WIDENED = {"fiscal_year": 2025, "period_start": "2024-01-01", "period_end": "2025-12-31"}


class TheWindowAndTheCoordinateAreSeparateTest(unittest.TestCase):
    def test_a_continuous_primary_registrant_measures_the_pinned_period(self):
        window, scope = event_measurement_window(repo_root=ROOT, company_id=CONTINUOUS,
                                                 pinned=PINNED, registered_event=False)
        self.assertIs(PINNED, window)
        self.assertIsNone(scope)

    def test_a_successor_registrant_measures_the_widened_window(self):
        window, scope = event_measurement_window(repo_root=ROOT, company_id=SUCCESSOR,
                                                 pinned=PINNED, registered_event=True)
        self.assertEqual(WIDENED, window)
        self.assertEqual(PINNED, scope["pinned_period"])
        # Both registered identities, and no authority to combine their
        # financial statements - widening an event window is not that.
        self.assertEqual(["2041610", "813828"], sorted(scope["registered_ciks"]))
        self.assertIs(False, scope["financial_cross_entity_combination_authorized"])

    def test_the_run_coordinate_keeps_a_window_that_fits_and_pins_one_that_does_not(self):
        instant = {"period_start": "2025-12-31", "period_end": "2025-12-31"}
        duration = {"period_start": "2025-01-01", "period_end": "2025-12-31"}
        for primary in (instant, duration):
            with self.subTest(window=primary["period_start"]):
                self.assertEqual({"fiscal_year": 2025, **primary},
                                 _run_coordinate(pinned=PINNED, primary=primary))
        widened = {"period_start": "2024-01-01", "period_end": "2025-12-31"}
        self.assertEqual(PINNED, _run_coordinate(pinned=PINNED, primary=widened))

    def test_the_widened_window_is_not_a_legal_run_coordinate(self):
        """Which is why the coordinate cannot simply follow the result."""
        from vnext.records import RecordError, validate_run_coordinates
        traits = ["SIC_7812"]
        with self.assertRaises(RecordError) as refused:
            validate_run_coordinates(target_period=WIDENED, company_traits=traits,
                                     point_in_time_fiscal_label=True)
        self.assertIn("53", str(refused.exception) + str(refused.exception.__cause__ or ""))
        validate_run_coordinates(target_period=PINNED, company_traits=traits,
                                 point_in_time_fiscal_label=True)


class TheHistoricalRouteAnswersAsTheOrdinaryOneDoesTest(unittest.TestCase):
    """The port is faithful when both routes reach the same state on the same day.

    Paramount's most recent annual period is the one case where the two are
    comparable: the ordinary route resolves the current period and the
    historical route resolves that same period by pinning it. Asserting they
    agree - including on which document is missing - is a stronger check than
    asserting the historical one succeeds, because a port that quietly widened
    or narrowed the source set would still succeed.
    """
    @classmethod
    def setUpClass(cls):
        from vnext.normal_zero_ai_results import resolve_ordinary_zero_ai_metric
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=SUCCESSOR,
                                                 report_end=PERIOD)
            cls.historical = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=SUCCESSOR, metric_id="C01",
                period_selection=selection)
            cls.ordinary = resolve_ordinary_zero_ai_metric(
                repo_root=ROOT, company_id=SUCCESSOR, metric_id="C01")

    def test_both_routes_measure_the_same_window(self):
        self.assertEqual(
            WIDENED, self.ordinary["input_binding"]["registered_event_scope"]["window"])
        self.assertEqual(
            WIDENED, self.historical["input_binding"]["registered_event_scope"]["window"])

    def test_both_routes_stop_at_the_same_missing_document(self):
        """A source gap, named. Not an implementation gap and not a value."""
        self.assertEqual("SOURCE_UNAVAILABLE", self.historical["selection"]["category"])
        self.assertEqual(self.ordinary["selection"]["reason"],
                         self.historical["selection"]["reason"])
        self.assertTrue(self.historical["selection"]["reason"].startswith(
            "SAVED_SOURCE_MISSING:https://www.sec.gov/Archives/edgar/data/813828/"))
        self.assertIsNone(self.historical["result"]["value"])
        self.assertEqual("WITHHELD", self.historical["result"]["publication"])

    def test_the_result_keeps_the_widened_window_and_the_component_keeps_the_pinned_one(self):
        self.assertEqual("2024-01-01", self.historical["result"]["period_start"])
        self.assertEqual("2025-12-31", self.historical["result"]["period_end"])
        self.assertEqual(PINNED, self.historical["pinned_target_period"])


class ASuccessorStatementMetricUsesTheApprovedIncomeProofTest(unittest.TestCase):
    """The gap this class used to assert is closed, and narrower now.

    B01 and B03 for a successor registrant need the current income input the
    ordinary route builds: the registrant's own originals, the period its
    income statement actually covers, and a Part III revenue-correction check.
    That input names the filing it proved, so it transfers to a historical
    target exactly when that filing is this target - and where it does not,
    the named gap stands rather than a proof about one report admitting
    another.

    Two things it is not. It is not a new amendment decision: the income
    input carries the approved proof the ordinary route already uses in place
    of the family question, for this case only. And it is not a value: the
    successor's first period is 146 days, so the Spec's annual-duration guard
    reports NOT_MEANINGFUL, which is the answer, not a refusal.
    """

    METRICS = ("B01", "B03")

    def _selection(self):
        return resolve_period_selection(repo_root=ROOT, company_id=SUCCESSOR,
                                        report_end=PERIOD)

    def test_the_answers_are_the_ordinary_chain_s_answers(self):
        # Load-bearing: it was measured that passing the guard alone left the
        # route asking Company Facts for the pinned fiscal year, which this
        # registrant never reported, and returning MISSING_CANDIDATE - an
        # answer about a period nobody filed. Comparing fields against the
        # ordinary chain, the measured window included, is what catches that.
        from vnext.normal_zero_ai_results import resolve_ordinary_zero_ai_metric
        fields = ("applicability", "quality", "reason_code", "value",
                  "period_start", "period_end")
        with original_sources_only():
            selection = self._selection()
            for metric_id in self.METRICS:
                with self.subTest(metric_id):
                    historical = resolve_historical_zero_ai_metric(
                        repo_root=ROOT, company_id=SUCCESSOR, metric_id=metric_id,
                        period_selection=selection)["result"]
                    ordinary = resolve_ordinary_zero_ai_metric(
                        repo_root=ROOT, company_id=SUCCESSOR,
                        metric_id=metric_id)["result"]
                    self.assertEqual({k: ordinary[k] for k in fields},
                                     {k: historical[k] for k in fields})
                    self.assertEqual("ANNUAL_DURATION_OUT_OF_RANGE",
                                     historical["reason_code"])

    def test_the_result_carries_the_measured_window_not_the_pinned_year(self):
        with original_sources_only():
            resolved = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=SUCCESSOR, metric_id="B01",
                period_selection=self._selection())
        result = resolved["result"]
        pinned = resolved["input_binding"]["prepared_input"]["table_input"]["target_period"]
        self.assertNotEqual(pinned["period_start"], result["period_start"])
        self.assertEqual(pinned["period_end"], result["period_end"])
        self.assertTrue(pinned["period_start"] <= result["period_start"])

    def test_the_income_proof_is_recorded_as_the_input_it_is(self):
        with original_sources_only():
            resolved = resolve_historical_zero_ai_metric(
                repo_root=ROOT, company_id=SUCCESSOR, metric_id="B01",
                period_selection=self._selection())
        binding = resolved["input_binding"]
        self.assertEqual("CURRENT_ORIGINAL_INCOME_STATEMENT_VALUES",
                         binding["amendment_input"]["input_class"])
        self.assertEqual("INPUT_PROPERTY_PROVEN", binding["amendment_input"]["decision"])
        self.assertTrue(binding["current_income_input"])

    def test_a_proof_about_another_filing_does_not_transfer(self):
        # The whole condition. A current-period proof used to admit a
        # different target would be a proof about one report standing behind
        # another's values, and it is refused by the name it always had.
        from unittest.mock import patch
        import vnext.historical_zero_ai_results as route
        real = route._successor_income_input

        def elsewhere(*, repo_root, company_id, metric_id, prepared):
            built = real(repo_root=repo_root, company_id=company_id,
                         metric_id=metric_id, prepared=prepared)
            self.assertIsNotNone(built, "the real proof is about this target")
            moved = {**prepared, "filing": {**prepared["filing"],
                                            "accessionNumber": "0000000000-00-000000"}}
            return real(repo_root=repo_root, company_id=company_id,
                        metric_id=metric_id, prepared=moved)

        with original_sources_only():
            selection = self._selection()
            with patch.object(route, "_successor_income_input", elsewhere):
                with self.assertRaises(ValueError) as refused:
                    resolve_historical_zero_ai_metric(
                        repo_root=ROOT, company_id=SUCCESSOR, metric_id="B01",
                        period_selection=selection)
        self.assertIn("HISTORICAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED",
                      str(refused.exception))


if __name__ == "__main__":
    unittest.main()
