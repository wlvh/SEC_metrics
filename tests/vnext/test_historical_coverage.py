"""The target frame is fixed before it is filled, and every position is classified.

These cases run against the repository's own saved SEC bytes with no network and
no new business call. They assert the frame's shape and its classification rules
rather than a particular set of values, so the matrix cannot silently shrink its
denominator as material arrives.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import (WIRED_HISTORICAL_METRICS, CoverageError,
                                       build_coverage_matrix, declared_metric_ids)


PERIOD_LEVEL = {"TARGET_PERIOD_METADATA_BLOCKED", "SOURCE_MISSING_TARGET_ORIGINAL",
                "HISTORICAL_ROUTE_NOT_WIRED"}


class HistoricalCoverageTest(unittest.TestCase):
    def test_the_declared_metric_universe_is_checked_against_its_own_total(self):
        with original_sources_only():
            metrics, policy = declared_metric_ids(repo_root=ROOT)
        self.assertEqual(39, len(metrics))
        self.assertEqual(policy["declared_issue_metric_count"], len(metrics))
        # D03 is an implementation gap, so it stays inside the declared universe
        # instead of being removed from the denominator.
        for pending in ("B13", "D03", "D04"):
            self.assertIn(pending, metrics)
        self.assertEqual(sorted(set(metrics)), metrics)

    def test_every_target_position_carries_exactly_one_classified_status(self):
        with original_sources_only():
            matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"], years=5)
        self.assertEqual(39 * 5, matrix["target_frame_positions"])
        self.assertEqual(39 * 5, matrix["enumerated_positions"])
        self.assertEqual(0, matrix["missing_positions_from_unreachable_periods"])
        self.assertEqual(sum(matrix["status_counts"].values()), matrix["enumerated_positions"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, matrix["calls"])
        self.assertFalse(matrix["native_run_created"])
        self.assertFalse(matrix["production_authorized"])
        seen = {(p["company_id"], p["report_end"], p["metric_id"]) for p in matrix["positions"]}
        self.assertEqual(len(seen), len(matrix["positions"]))
        for position in matrix["positions"]:
            self.assertTrue(position["status"])
            self.assertIsInstance(position["detail"], dict)
        # Macy's only has one period whose own original is saved, so exactly one
        # period contributes resolved metric statuses and the other four are
        # reported as a source gap rather than dropped from the frame.
        established = [p for p in matrix["company_reports"][0]["periods"]
                       if p["period_status"] == "PERIOD_ESTABLISHED"]
        self.assertEqual(1, len(established))
        self.assertEqual("2026-01-31", established[0]["report_end"])
        self.assertEqual(2025, established[0]["fiscal_year"])
        missing = [p for p in matrix["positions"]
                   if p["status"] == "SOURCE_MISSING_TARGET_ORIGINAL"]
        self.assertEqual(39 * 4, len(missing))
        self.assertTrue(all(p["detail"]["document_name"].endswith((".htm", ".html"))
                            for p in missing))
        resolved = [p for p in matrix["positions"] if p["report_end"] == "2026-01-31"]
        self.assertEqual(39, len(resolved))
        wired = [p for p in resolved if p["metric_id"] in WIRED_HISTORICAL_METRICS]
        self.assertEqual(len(WIRED_HISTORICAL_METRICS), len(wired))
        self.assertTrue(all(p["status"] != "HISTORICAL_ROUTE_NOT_WIRED" for p in wired))
        unwired = [p for p in resolved if p["metric_id"] not in WIRED_HISTORICAL_METRICS]
        self.assertTrue(unwired)
        # An unwired route is an implementation gap, never a disclosure claim.
        self.assertEqual({"HISTORICAL_ROUTE_NOT_WIRED"}, {p["status"] for p in unwired})

    def test_one_period_s_route_limitation_does_not_remove_the_rest_of_the_frame(self):
        with original_sources_only():
            matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["southwest_airlines"],
                                           years=5)
        self.assertEqual(39 * 5, matrix["enumerated_positions"])
        periods = matrix["company_reports"][0]["periods"]
        blocked = [p for p in periods if p["period_status"] == "ROUTE_BLOCKED"]
        # Southwest's most recent annual period carries a 10-K/A, and the
        # historical amendment route is not wired, so that period is blocked
        # while every other period keeps its own status.
        self.assertEqual(1, len(blocked))
        self.assertEqual("2025-12-31", blocked[0]["report_end"])
        self.assertEqual("HISTORICAL_COMPANYFACTS_AMENDED_TARGET_NOT_IMPLEMENTED",
                         blocked[0]["route_error"]["reason"])
        self.assertEqual(4, len([p for p in periods if p["period_status"] != "ROUTE_BLOCKED"]))
        for position in matrix["positions"]:
            if position["report_end"] == "2025-12-31":
                self.assertEqual("HISTORICAL_ROUTE_NOT_WIRED", position["status"])
                self.assertEqual("HISTORICAL_COMPANYFACTS_AMENDED_TARGET_NOT_IMPLEMENTED",
                                 position["detail"]["reason"])

    def test_an_unknown_company_set_is_an_explicit_refusal(self):
        with original_sources_only():
            with self.assertRaises(CoverageError) as unknown:
                build_coverage_matrix(repo_root=ROOT, company_ids=["not_a_company"], years=1)
            with self.assertRaises(CoverageError) as duplicated:
                build_coverage_matrix(repo_root=ROOT, company_ids=["macys", "macys"], years=1)
        self.assertEqual("COVERAGE_COMPANY_SET_INVALID", str(unknown.exception))
        self.assertEqual("COVERAGE_COMPANY_SET_INVALID", str(duplicated.exception))


if __name__ == "__main__":
    unittest.main()
