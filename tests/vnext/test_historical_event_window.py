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


class ASuccessorStatementMetricIsStillAnExplicitGapTest(unittest.TestCase):
    def test_widening_an_event_window_did_not_wire_the_statement_routes(self):
        """B01 for a successor registrant needs the current income input.

        That is defined against the current period and is not ported, so it
        stays an explicit gap. Paramount's amendment refuses it one step
        earlier, so what is asserted is that the refusal is named and is one of
        the two - never silence, and never a value.
        """
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=SUCCESSOR,
                                                 report_end=PERIOD)
            with self.assertRaises(ValueError) as refused:
                resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=SUCCESSOR,
                                                  metric_id="B01",
                                                  period_selection=selection)
        self.assertIn(str(refused.exception).split(":")[0],
                      {"HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED",
                       "HISTORICAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED"})


if __name__ == "__main__":
    unittest.main()
