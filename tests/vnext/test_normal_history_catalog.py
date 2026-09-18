"""The historical annual catalog reports saved metadata, never a fiscal label.

Every assertion here runs against the repository's own saved SEC bytes with no
network and no new business call. A report end date is metadata; an issuer
fiscal-year label is only established later from original DEI contexts.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_history_catalog import (HistoryCatalogError, annual_periods,
                                          load_annual_history,
                                          plan_historical_sources,
                                          target_period_candidates)


FORD_FIVE = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31", "2021-12-31"]
FORD_ACCESSIONS = ["0000037996-26-000015", "0000037996-25-000013", "0000037996-24-000009",
                   "0000037996-23-000012", "0000037996-22-000013"]


class HistoryCatalogTest(unittest.TestCase):
    def test_five_year_candidates_are_the_newest_distinct_annual_report_ends(self):
        with original_sources_only():
            candidates = target_period_candidates(repo_root=ROOT,
                                                  company_id="ford_motor_company", count=5)
        self.assertEqual(FORD_FIVE, [c["report_date"] for c in candidates])
        self.assertEqual(FORD_ACCESSIONS,
                         [c["current_filing"]["accessionNumber"] for c in candidates])
        self.assertEqual([1, 2, 3, 4, 5], [c["target_ordinal"] for c in candidates])
        self.assertEqual(FORD_FIVE[1:] + ["2020-12-31"],
                         [c["prior_report_date"] for c in candidates])
        for candidate in candidates:
            self.assertEqual("METADATA_CANDIDATE_READY", candidate["metadata_status"])
            self.assertEqual([], candidate["metadata_blocking_reasons"])
            self.assertIsNone(candidate["fiscal_year"])
            self.assertEqual("ISSUER_LABEL_REQUIRES_ORIGINAL_DOCUMENT",
                             candidate["fiscal_label_status"])
            self.assertEqual("10-K", candidate["current_filing"]["form"])

    def test_window_loads_only_the_history_a_bounded_window_can_need(self):
        with original_sources_only():
            history = load_annual_history(repo_root=ROOT, company_id="ford_motor_company",
                                          required_annual_count=6)
            wide = load_annual_history(repo_root=ROOT, company_id="salesforce",
                                       required_annual_count=6)
        # Ford's own recent block already reaches back six annual periods, so no
        # declared shard can hold a relevant filing and none is read.
        self.assertEqual(["CIK0000037996.json"], history["loaded_inventories"])
        self.assertEqual(2, len(history["declared_shards"]))
        self.assertEqual([], history["limitations"])
        self.assertEqual("2020-12-31", history["window_oldest_report_end"])
        self.assertTrue(history["window_proven"])
        # Salesforce's recent block does not, so exactly the reachable shard is read.
        self.assertEqual(["CIK0001108524.json", "CIK0001108524-submissions-001.json"],
                         wide["loaded_inventories"])
        self.assertEqual([], wide["limitations"])
        self.assertEqual("2021-01-31", wide["window_oldest_report_end"])

    def test_plan_is_deterministic_and_never_spends_a_business_call(self):
        with original_sources_only():
            first = plan_historical_sources(repo_root=ROOT, company_id="ford_motor_company",
                                            count=5)
            second = plan_historical_sources(repo_root=ROOT, company_id="ford_motor_company",
                                             count=5)
        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, first["calls"])
        self.assertFalse(first["fetch_authorized"])
        self.assertFalse(first["metric_executed"])
        self.assertFalse(first["production_authorized"])
        self.assertFalse(first["sources_ready"])
        self.assertEqual("PLAN_READY", first["plan_status"])

    def test_one_url_is_declared_once_and_keeps_every_consumer(self):
        with original_sources_only():
            plan = plan_historical_sources(repo_root=ROOT, company_id="ford_motor_company",
                                           count=5)
        urls = [item["source_url"] for item in plan["requirements"]]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(len(urls), plan["deduplicated_known_get_count"])
        shared = ("https://www.sec.gov/Archives/edgar/data/37996/"
                  "000003799625000013/f-20241231.htm")
        item = next(r for r in plan["requirements"] if r["source_url"] == shared)
        # One saved document serves the 2024 target and the 2025 prior dependency.
        self.assertEqual(["prior_annual_primary", "target_primary"], item["source_roles"])
        self.assertEqual(["period:2024-12-31", "period:2025-12-31:B02"], item["consumers"])
        self.assertEqual("ANNUAL_PERIOD_IDENTITY", item["dependency_class"])

    def test_missing_primary_html_is_not_hidden_by_the_native_instance_route(self):
        with original_sources_only():
            plan = plan_historical_sources(repo_root=ROOT, company_id="ford_motor_company",
                                           count=5)
        shared = ("https://www.sec.gov/Archives/edgar/data/37996/"
                  "000003799625000013/f-20241231.htm")
        item = next(r for r in plan["requirements"] if r["source_url"] == shared)
        self.assertEqual("MISSING_SAVED_SOURCE", item["saved_status"])
        alternative = item["alternative_dependency"]
        self.assertEqual("VERIFIED_ACCESSION_NATIVE_INSTANCE", alternative["status"])
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"}, alternative["annual_period"])
        self.assertEqual(["prior_annual_primary"], alternative["satisfies_source_roles"])
        self.assertFalse(alternative["establishes_issuer_fiscal_label"])
        self.assertFalse(alternative["substitutes_html_text_range"])
        self.assertFalse(alternative["source_acquisition_credit"])
        # This one document serves both the 2025 prior role, which the instance
        # can close, and the 2024 target role, which it cannot: an issuer fiscal
        # label needs the full document. So it stays an acquisition requirement
        # and 2024 is not reported as identity-ready.
        self.assertEqual(["prior_annual_primary", "target_primary"], item["source_roles"])
        self.assertTrue(item["new_acquisition_required"])
        self.assertEqual(["2025-12-31"], plan["annual_identity_ready_report_dates"])
        unsatisfied = ("https://www.sec.gov/Archives/edgar/data/37996/"
                       "000003799622000013/f-20211231.htm")
        blocked = next(r for r in plan["requirements"] if r["source_url"] == unsatisfied)
        self.assertEqual("MISSING_SAVED_SOURCE", blocked["saved_status"])
        self.assertEqual("NOT_ESTABLISHED", blocked["alternative_dependency"]["status"])
        self.assertTrue(blocked["new_acquisition_required"])

    def test_amendment_stays_with_its_own_period_and_is_not_a_sixth_year(self):
        with original_sources_only():
            candidates = target_period_candidates(repo_root=ROOT,
                                                  company_id="marriott_international", count=5)
        report_dates = [c["report_date"] for c in candidates]
        self.assertEqual(["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31",
                          "2021-12-31"], report_dates)
        self.assertNotIn("2020-12-31", report_dates)
        oldest = candidates[-1]
        self.assertEqual("2020-12-31", oldest["prior_report_date"])
        self.assertEqual("0001628280-21-002433", oldest["prior_filing"]["accessionNumber"])
        self.assertEqual([("10-K/A", "0001628280-21-006440")],
                         [(a["form"], a["accessionNumber"]) for a in oldest["prior_amendments"]])
        for candidate in candidates:
            self.assertEqual([], candidate["current_amendments"])

    def test_non_calendar_and_53_week_report_ends_are_kept_as_reported(self):
        with original_sources_only():
            macys = target_period_candidates(repo_root=ROOT, company_id="macys", count=5)
            salesforce = target_period_candidates(repo_root=ROOT, company_id="salesforce", count=5)
        self.assertEqual(["2026-01-31", "2025-02-01", "2024-02-03", "2023-01-28",
                          "2022-01-29"], [c["report_date"] for c in macys])
        self.assertEqual(["2026-01-31", "2025-01-31", "2024-01-31", "2023-01-31",
                          "2022-01-31"], [c["report_date"] for c in salesforce])
        for candidate in macys + salesforce:
            self.assertFalse(candidate["report_date"].endswith("-12-31"))
            self.assertIsNone(candidate["fiscal_year"])

    def test_unsaved_and_incoherent_history_shards_stay_explicit_gaps(self):
        with original_sources_only():
            plan = plan_historical_sources(repo_root=ROOT, company_id="jpmorgan_chase", count=5)
        kinds = {item["kind"] for item in plan["catalog_limitations"]}
        self.assertIn("HISTORY_SHARD_NOT_SAVED", kinds)
        self.assertIn("HISTORY_SHARD_SNAPSHOT_CONFLICT", kinds)
        # A rotating shard layout is not "no filings": fewer annual periods are
        # reachable and every reachable one is blocked, never silently ready.
        self.assertLess(len(plan["target_candidates"]), 5)
        self.assertTrue(plan["target_candidates"])
        for candidate in plan["target_candidates"]:
            self.assertEqual("METADATA_BLOCKED", candidate["metadata_status"])
            self.assertIn("HISTORY_SNAPSHOT_CONFLICT", candidate["metadata_blocking_reasons"])
        self.assertEqual([], plan["annual_identity_ready_report_dates"])
        self.assertFalse(plan["complete_plan_proven"])
        missing = {item["history_name"] for item in plan["catalog_limitations"]
                   if item["kind"] == "HISTORY_SHARD_NOT_SAVED"}
        declared = {item["source_url"] for item in plan["requirements"]
                    if item["dependency_class"] == "SUBMISSIONS_HISTORY"}
        for name in missing:
            self.assertIn("https://data.sec.gov/submissions/" + name, declared)

    def test_incomplete_index_discovery_is_reported_as_unknown_not_as_a_total(self):
        with original_sources_only():
            plan = plan_historical_sources(repo_root=ROOT, company_id="macys", count=5)
        self.assertTrue(plan["further_requests_pending_index_discovery"])
        self.assertFalse(plan["complete_plan_proven"])
        self.assertEqual(sorted(plan["accession_indexes_not_yet_discovered"]),
                         plan["accession_indexes_not_yet_discovered"])
        self.assertTrue(all(accession for accession in plan["accession_indexes_not_yet_discovered"]))
        counted = sum(entry["new_acquisition_required"]
                      for entry in plan["requirements_by_dependency_class"].values())
        self.assertEqual(plan["new_acquisition_count"], counted)
        self.assertEqual(plan["new_acquisition_count"], len(plan["new_acquisition_urls"]))

    def test_grouping_never_merges_two_report_ends_or_invents_an_original(self):
        with original_sources_only():
            history = load_annual_history(repo_root=ROOT, company_id="marriott_international",
                                          required_annual_count=6)
        periods = annual_periods(history=history)
        ends = [period["report_date"] for period in periods]
        self.assertEqual(sorted(set(ends), reverse=True), ends)
        amended = next(period for period in periods if period["report_date"] == "2020-12-31")
        self.assertEqual("SINGLE_ORIGINAL_ANNUAL", amended["original_status"])
        self.assertEqual(1, amended["amendment_count"])
        self.assertEqual("10-K", amended["original"]["form"])

    def test_an_invalid_window_or_company_is_an_explicit_refusal(self):
        with original_sources_only():
            with self.assertRaises(HistoryCatalogError) as zero:
                load_annual_history(repo_root=ROOT, company_id="ford_motor_company",
                                    required_annual_count=0)
            with self.assertRaises(HistoryCatalogError) as unknown:
                load_annual_history(repo_root=ROOT, company_id="not_a_registered_company")
        self.assertEqual("HISTORY_REQUIRED_ANNUAL_COUNT_INVALID", str(zero.exception))
        self.assertEqual("IMPLEMENTATION_GAP", zero.exception.category)
        self.assertEqual("HISTORY_COMPANY_NOT_UNIQUE", str(unknown.exception))


if __name__ == "__main__":
    unittest.main()
