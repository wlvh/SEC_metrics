"""Saved-source annual selection and failure isolation, with no runtime answers."""

import copy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from vnext import normal_annual_input as normal
from tests.vnext.test_annual_input import independent_inputs


ROOT = Path(__file__).resolve().parents[2]


def metadata(company_id="marriott_international"):
    company = next(c for c in normal._registry_rows(repo_root=ROOT)
                   if c["company_id"] == company_id)
    path = ROOT / "evidence/submissions" / (
        "CIK" + company["primary_cik"].zfill(10) + ".json")
    return company, json.loads(path.read_text())


class NormalAnnualInputTest(unittest.TestCase):
    def test_saved_noncalendar_inputs_use_dei_fiscal_label(self):
        with independent_inputs():
            for company_id, start in [("salesforce", "2025-02-01"),
                                      ("macys", "2025-02-02")]:
                prepared = normal.prepare_saved_annual_input(
                    repo_root=ROOT, company_id=company_id)
                period = prepared["table_input"]["target_period"]
                self.assertEqual(start, period["period_start"])
                self.assertEqual("2026-01-31", period["period_end"])
                self.assertEqual(2025, period["fiscal_year"])
                self.assertEqual("ORIGINAL_INPUT_READY", prepared["update_status"])
                self.assertFalse(prepared["current_latest_verified"])

    def test_amendment_keeps_original_and_does_not_claim_current_success(self):
        with independent_inputs():
            prepared = normal.prepare_saved_annual_input(
                repo_root=ROOT, company_id="southwest_airlines")
        self.assertEqual("10-K", prepared["filing"]["form"])
        self.assertTrue(prepared["amendments"])
        self.assertEqual("AMENDMENT_PROCESSING_REQUIRED", prepared["update_status"])
        self.assertEqual("NOT_EXECUTED", prepared["execution"])

    def test_latest_period_cannot_fall_back_when_only_amendment_is_present(self):
        company, payload = metadata()
        block = payload["filings"]["recent"]
        chosen = normal.select_filing(company=company, submissions=payload)["filing"]
        index = block["accessionNumber"].index(chosen["accessionNumber"])
        block["form"][index] = "10-K/A"
        with self.assertRaisesRegex(normal.NormalAnnualInputError,
                                    "ORDINARY_ANNUAL_MISSING"):
            normal.select_filing(company=company, submissions=payload)

    def test_ambiguous_columns_dates_and_relevant_shards_are_not_no_change(self):
        company, source = metadata()
        wrong = copy.deepcopy(source)
        wrong["filings"]["recent"]["reportDate"].pop()
        with self.assertRaisesRegex(normal.NormalAnnualInputError, "COLUMNS_CONFLICT"):
            normal.select_filing(company=company, submissions=wrong)
        wrong = copy.deepcopy(source)
        block = wrong["filings"]["recent"]
        index = block["form"].index("10-K")
        block["reportDate"][index] = "unknown"
        with self.assertRaisesRegex(normal.NormalAnnualInputError, "FILING_DATE_INVALID"):
            normal.select_filing(company=company, submissions=wrong)
        wrong = copy.deepcopy(source)
        wrong["filings"]["files"].append({"filingFrom": "2025-01-01",
                                           "filingTo": "2026-12-31"})
        with self.assertRaisesRegex(normal.NormalAnnualInputError,
                                    "RELEVANT_HISTORY_NOT_LOADED"):
            normal.select_filing(company=company, submissions=wrong)

    def test_period_rechecks_entity_and_does_not_promote_quarter_to_year(self):
        from vnext.annual_update import saved_source
        from sec_urls import accession_document_url
        company, payload = metadata()
        filing = normal.select_filing(company=company, submissions=payload)["filing"]
        source = saved_source(repo_root=ROOT, url=accession_document_url(
            cik=int(company["primary_cik"]), accession=filing["accessionNumber"],
            document_name=filing["primaryDocument"]), accession=filing["accessionNumber"])
        with self.assertRaisesRegex(normal.NormalAnnualInputError, "DEI_SUBJECT_CONFLICT"):
            normal.annual_period(raw=source["raw"], cik=1, filing=filing)
        changed = source["raw"].replace(b"2025-01-01", b"2025-10-01")
        self.assertNotEqual(changed, source["raw"])
        with self.assertRaisesRegex(normal.NormalAnnualInputError,
                                    "ANNUAL_DURATION_NOT_IMPLEMENTED"):
            normal.annual_period(raw=changed, cik=company["primary_cik"], filing=filing)

    def test_ten_company_inspection_preserves_successor_scope(self):
        with independent_inputs():
            result = normal.inspect_saved_annual_inputs(repo_root=ROOT)
        self.assertEqual(10, len(result["companies"]))
        by_id = {c["company_id"]: c for c in result["companies"]}
        transition = by_id["paramount_skydance_paramount_global"]["prepared_input"]
        self.assertEqual("SUCCESSOR_REGISTRANT_ONLY", transition["subject_policy"]["mode"])
        self.assertEqual("2041610", transition["entity"])
        self.assertFalse(transition["subject_policy"]["cross_entity_combination_authorized"])
        self.assertTrue(transition["amendments"])
        self.assertEqual("ORIGINAL_INPUT_READY", by_id["enphase_energy"]["status"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, result["calls"])

    def _assert_registry_slice(self, start, stop):
        companies = normal._registry_rows(repo_root=ROOT)[start:stop]
        with independent_inputs(), patch.object(normal, "_registry_rows", return_value=companies):
            result = normal.inspect_saved_annual_inputs(repo_root=ROOT)
        self.assertEqual([c["company_id"] for c in companies],
                         [c["company_id"] for c in result["companies"]])
        for row in result["companies"]:
            self.assertIn(row["status"], {"ORIGINAL_INPUT_READY",
                                          "AMENDMENT_PROCESSING_REQUIRED",
                                          "SUBJECT_TRANSITION_INPUT_READY"})
            self.assertEqual("10-K", row["prepared_input"]["filing"]["form"])
            self.assertFalse(row["prepared_input"]["current_latest_verified"])
            if row["company_id"] == "paramount_skydance_paramount_global":
                policy = row["prepared_input"]["subject_policy"]
                self.assertEqual("SUCCESSOR_REGISTRANT_ONLY", policy["mode"])
                self.assertTrue(policy["per_metric_statement_scope_required"])
                self.assertFalse(policy["cross_entity_combination_authorized"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, result["calls"])

    def test_first_five_company_inputs_with_same_source_checks(self):
        self._assert_registry_slice(0, 5)

    def test_remaining_company_inputs_preserve_transition_and_continue(self):
        self._assert_registry_slice(5, 10)

    def test_unknown_subject_policy_isolated_without_using_predecessor(self):
        companies = normal._registry_rows(repo_root=ROOT)
        changed = copy.deepcopy(companies[-2:])
        changed[0]["entity_continuity_status"] = "unresolved_transition"
        with independent_inputs(), patch.object(normal, "_registry_rows", return_value=changed):
            result = normal.inspect_saved_annual_inputs(repo_root=ROOT)
        self.assertEqual("IMPLEMENTATION_GAP", result["companies"][0]["category"])
        self.assertEqual("ORIGINAL_INPUT_READY", result["companies"][1]["status"])
        company, payload = metadata("paramount_skydance_paramount_global")
        payload["cik"] = company["related_ciks"]
        with self.assertRaisesRegex(normal.NormalAnnualInputError,
                                    "SUBMISSIONS_ENTITY_CONFLICT"):
            normal.select_filing(company=company, submissions=payload)

    def test_later_source_failure_is_not_relabelled_as_old_success(self):
        with patch.object(normal, "saved_source", side_effect=normal.AnnualUpdateError(
                "LATEST_SOURCE_REQUEST_FAILED: TEST_ONLY")):
            report = normal.inspect_saved_annual_inputs(repo_root=ROOT)
        for company in report["companies"]:
            self.assertEqual("INPUT_BLOCKED", company["status"])
            self.assertNotIn("prepared_input", company)

    def test_invalid_source_fiscal_label_and_cik_are_integrity_failures(self):
        from sec_urls import accession_document_url
        company, payload = metadata("jpmorgan_chase")
        filing = normal.select_filing(company=company, submissions=payload)["filing"]
        item = normal.saved_source(repo_root=ROOT, url=accession_document_url(
            cik=int(company["primary_cik"]), accession=filing["accessionNumber"],
            document_name=filing["primaryDocument"]), accession=filing["accessionNumber"])
        pattern = (rb'(<ix:nonNumeric\b[^>]*\bname="dei:DocumentFiscalYearFocus"'
                   rb'[^>]*>)[0-9]{4}(</ix:nonNumeric>)')
        for year in [b"0000", b"2020", b"9999"]:
            changed, count = re.subn(pattern, lambda m: m[1] + year + m[2], item["raw"])
            self.assertEqual(1, count)
            with self.subTest(year=year), self.assertRaisesRegex(
                    normal.NormalAnnualInputError, "DEI_FISCAL_YEAR_CONFLICT") as caught:
                normal.annual_period(raw=changed, cik=company["primary_cik"], filing=filing)
            self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)
        spoofed = re.sub(rb'xmlns:dei="https?://xbrl\.sec\.gov/dei/[0-9]{4}"',
                         b'xmlns:dei="https://example.test/dei-lookalike"', item["raw"])
        self.assertNotEqual(item["raw"], spoofed)
        with self.assertRaisesRegex(normal.NormalAnnualInputError, "DEI_MISSING_OR_AMBIGUOUS"):
            normal.annual_period(raw=spoofed, cik=company["primary_cik"], filing=filing)
        payload["cik"] = "not-a-number"
        with self.assertRaisesRegex(normal.NormalAnnualInputError,
                                    "SOURCE_ENTITY_INVALID") as caught:
            normal.select_filing(company=company, submissions=payload)
        self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)


if __name__ == "__main__":
    unittest.main()
