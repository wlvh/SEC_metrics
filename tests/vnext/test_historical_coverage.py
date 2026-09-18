"""The target frame is fixed before it is filled, and every position is classified.

These cases run against the repository's own saved SEC bytes with no network and
no new business call. They assert the frame's shape and its classification rules
rather than a particular set of values, so the matrix cannot silently shrink its
denominator as material arrives.

The property they exist to defend is that a position's first blocking reason is
not a statement that it is the only one. Counting first blockers as remaining
work is what turns "these positions are waiting for a document" into a source
budget that hides the routes those same positions also lack.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import (WIRED_ACCESSION_METRICS, WIRED_HISTORICAL_METRICS,
                                       CoverageError, build_coverage_matrix,
                                       declared_metric_ids)


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
        self.assertEqual(2, matrix["schema_version"])
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
        # The point of the separate dimensions: of those 156 positions whose
        # first blocker is a missing document, 92 have no historical route
        # either. Acquiring all 156 documents would fill 64 of them. Counting
        # first blockers as the remaining work is exactly the error this frame
        # is built to make visible.
        also_unwired = [p for p in missing if not p["historical_route_implemented"]]
        self.assertEqual((39 - len(WIRED_HISTORICAL_METRICS)) * 4, len(also_unwired))
        self.assertEqual(len(also_unwired), matrix["positions_missing_source_and_route"])
        self.assertLess(matrix["positions_missing_source_and_route"], len(missing))
        self.assertTrue(matrix["first_blocking_reason_is_not_the_only_blocker"])
        self.assertTrue(all(p["first_blocking_reason"] == p["status"]
                            for p in matrix["positions"]))
        # Each dimension is counted over the whole frame, independently.
        self.assertEqual({"target_period_established": 39 * 5, "target_original_saved": 39,
                          "historical_route_implemented": len(WIRED_HISTORICAL_METRICS) * 5,
                          "native_run_wired": 0, "verified_outcome": 16},
                         matrix["dimension_counts"])
        resolved = [p for p in matrix["positions"] if p["report_end"] == "2026-01-31"]
        self.assertEqual(39, len(resolved))
        wired = [p for p in resolved if p["metric_id"] in WIRED_HISTORICAL_METRICS]
        self.assertEqual(len(WIRED_HISTORICAL_METRICS), len(wired))
        self.assertTrue(all(p["status"] != "HISTORICAL_ROUTE_NOT_WIRED" for p in wired))
        unwired = [p for p in resolved if p["metric_id"] not in WIRED_HISTORICAL_METRICS]
        self.assertTrue(unwired)
        # An unwired route is an implementation gap, never a disclosure claim.
        self.assertEqual({"HISTORICAL_ROUTE_NOT_WIRED"}, {p["status"] for p in unwired})

    def test_one_adapter_s_limitation_does_not_remove_the_metrics_another_resolved(self):
        """Adapters fail separately because they answer separate questions.

        Southwest's most recent annual period carries a 10-K/A. The Company
        Facts and revenue routes both refuse an amended target, but that refusal
        says nothing about whether an instant fact can be read from the selected
        filing's own inline XBRL. Before the adapters were isolated, the first
        refusal removed the whole period from the frame and the instant metrics
        were reported as unwired, which was not true of them.
        """
        with original_sources_only():
            matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["southwest_airlines"],
                                           years=5)
        self.assertEqual(39 * 5, matrix["enumerated_positions"])
        periods = matrix["company_reports"][0]["periods"]
        established = [p for p in periods if p["period_status"] == "PERIOD_ESTABLISHED"]
        self.assertEqual(1, len(established))
        self.assertEqual("2025-12-31", established[0]["report_end"])
        errors = established[0]["adapter_errors"]
        self.assertEqual({"companyfacts", "revenue"}, set(errors))
        self.assertEqual("HISTORICAL_COMPANYFACTS_AMENDED_TARGET_NOT_IMPLEMENTED",
                         errors["companyfacts"]["reason"])
        self.assertEqual("HISTORICAL_ZERO_AI_AMENDED_TARGET_NOT_IMPLEMENTED",
                         errors["revenue"]["reason"])
        # An unimplemented amendment route is an implementation gap, never a
        # source gap and never a disclosure claim.
        self.assertEqual({"IMPLEMENTATION_GAP"},
                         {detail["category"] for detail in errors.values()})
        amended = [p for p in matrix["positions"] if p["report_end"] == "2025-12-31"]
        self.assertEqual(39, len(amended))
        instants = {p["metric_id"]: p for p in amended if p["metric_id"] in WIRED_ACCESSION_METRICS}
        self.assertEqual(set(WIRED_ACCESSION_METRICS), set(instants))
        # The instant adapter ran on the same period and its own rules decided
        # the outcome, so these are resolved positions rather than blocked ones.
        for position in instants.values():
            self.assertEqual("N_A_STRUCTURAL", position["status"])
            self.assertTrue(position["verified_outcome"])
        blocked = [p for p in amended if p["status"] == "HISTORICAL_ROUTE_NOT_WIRED"]
        self.assertEqual(39 - len(WIRED_ACCESSION_METRICS), len(blocked))
        for position in blocked:
            if position["metric_id"] in WIRED_HISTORICAL_METRICS:
                self.assertIn("AMENDED_TARGET_NOT_IMPLEMENTED", position["detail"]["reason"])

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
