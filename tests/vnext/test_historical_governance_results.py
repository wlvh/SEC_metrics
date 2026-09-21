"""C04 for a pinned annual period, and what it says when the material is not there.

The load-bearing case is one company answered for two periods. C04 delivers a
flag for the period whose accession material is saved and a withheld Result
naming the missing file for the one whose is not; a route that ignored the
period would give both the same answer and pass every other case here.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS
from vnext.historical_governance_results import (SUPPORTED_METRICS,
                                                 HistoricalGovernanceError,
                                                 resolve_historical_governance_metric)
from vnext.historical_results import prepare_historical_run_input
from vnext.normal_period_selection import resolve_period_selection

MARRIOTT = "marriott_international"
# The most recent period, whose accession material is saved, and an earlier one
# whose is not. Both are in this repository's saved originals, so the pair is a
# real contrast rather than one real case and one fabricated absence.
DELIVERS = "2025-12-31"
WITHHOLDS = "2023-12-31"


def _resolve(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return resolve_historical_governance_metric(
            repo_root=ROOT, company_id=company_id, metric_id="C04",
            period_selection=selection)


class HistoricalGovernanceResultsTest(unittest.TestCase):
    def test_one_company_two_periods_two_answers(self):
        """The whole point of a pinned route, stated as a contrast."""
        delivered = _resolve(MARRIOTT, DELIVERS)["result"]
        withheld = _resolve(MARRIOTT, WITHHOLDS)["result"]
        self.assertEqual(("EXACT", "PUBLISHED", "PASS"),
                         (delivered["quality"], delivered["publication"],
                          delivered["reason_code"]))
        self.assertIsNotNone(delivered["value"])
        self.assertEqual(("NONE", "WITHHELD"),
                         (withheld["quality"], withheld["publication"]))
        self.assertNotEqual(delivered["reason_code"], withheld["reason_code"])
        # And each answers for its own period rather than for the newest one.
        self.assertEqual(DELIVERS, delivered["period_end"])
        self.assertEqual(WITHHOLDS, withheld["period_end"])

    def test_a_missing_file_is_a_source_gap_not_a_route_gap(self):
        """The frame has to be able to tell them apart.

        Reporting a missing accession index as an unimplemented route is how a
        settled question reads as an open one, and the reverse hides real work
        behind an acquisition request.
        """
        component = _resolve(MARRIOTT, WITHHOLDS)
        self.assertEqual("HISTORICAL_GOVERNANCE_SOURCE_ROUTE_UNRESOLVED",
                         component["result"]["reason_code"])
        self.assertIsNotNone(component["limitation"])
        self.assertIn("SAVED_SOURCE_MISSING", component["limitation"]["reason"])
        # A withheld Result still carries the sources that were read, so the
        # Run is about this period rather than about nothing.
        self.assertTrue(component["source_proofs"])
        self.assertTrue(component["source_references"])

    def test_the_selection_is_by_the_period_and_says_so(self):
        component = _resolve(MARRIOTT, WITHHOLDS)
        self.assertEqual("PINNED_PERIOD_END_EQUALITY", component["selection"]["annual"])
        self.assertEqual("GREATEST_ANNUAL_REPORT_END_BEFORE_THE_PINNED_ONE",
                         component["selection"]["prior"])
        self.assertEqual(WITHHOLDS, component["target_period"]["period_end"])

    def test_the_route_is_reachable_through_the_run_input(self):
        """Wired, not merely written: the dispatcher has to find it."""
        self.assertIn("C04", SUPPORTED_METRICS)
        self.assertIn("C04", WIRED_HISTORICAL_METRICS)
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=DELIVERS)
            prepared = prepare_historical_run_input(
                repo_root=ROOT, company_id=MARRIOTT, metric_id="C04",
                period_selection=selection)
        self.assertEqual("C04", prepared["primary_metric_id"])
        self.assertEqual("PUBLISHED", prepared["primary_result"]["publication"])
        # The Run's coordinate is the pinned fiscal year, not the measurement.
        self.assertEqual(DELIVERS, prepared["target_period"]["period_end"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, prepared["calls"])

    def test_an_unwired_governance_metric_is_refused_by_name(self):
        """C03 reads the annual meeting proxy and is not wired here.

        Answering for it would be inventing a route, and the refusal names the
        metric so the frame reports a gap rather than a silence.
        """
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=DELIVERS)
            with self.assertRaises(HistoricalGovernanceError) as refused:
                resolve_historical_governance_metric(
                    repo_root=ROOT, company_id=MARRIOTT, metric_id="C03",
                    period_selection=selection)
        self.assertTrue(str(refused.exception).startswith(
            "HISTORICAL_GOVERNANCE_METRIC_NOT_WIRED:"))


if __name__ == "__main__":
    unittest.main()
