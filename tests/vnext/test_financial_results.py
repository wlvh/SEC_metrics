"""Ordinary native financial records; no fixture answers, egress or Run writes."""

import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.test_financial_candidates import no_answers_or_network
from tests.vnext.test_financial_duration import ROOT
from vnext import financial_results as native
from vnext.calculator import calculate_observation_metric
from vnext.normal_annual_input import NormalAnnualInputError
from vnext.normal_annual_input import _registry_rows
from vnext.annual_update import AnnualUpdateError
from vnext.normal_source_authority import NormalSourceAuthorityError
from vnext.records import validate_record


class FinancialResultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = {metric: cls.resolve(metric) for metric in native.SPEC_PATHS}

    @staticmethod
    def resolve(metric, root=ROOT, company="jpmorgan_chase"):
        with no_answers_or_network():
            return native.resolve_ordinary_financial_metric(repo_root=root, company_id=company, metric_id=metric)

    def test_real_six_metrics_keep_measurement_periods_and_replay_through_calculator(self):
        for metric, value, start in (("A03", "1.11", "2025-10-01"), ("A04", "0.025", "2025-01-01"),
                                     ("A09", "0.0066", "2025-12-31"), ("A11", "4791000000000", "2025-12-31"),
                                     ("A12", "40000000", "2025-01-01"), ("A13", "42758000000", "2025-01-01")):
            result = self.actual[metric]
            self.assertEqual(value, result["result"]["value"])
            self.assertEqual(start, result["result"]["period_start"])
            self.assertEqual("2025-01-01", result["filing_period"]["period_start"])
            self.assertEqual("PUBLISHED", result["result"]["publication"])
            self.assertEqual("NOT_CREATED", result["native_run_status"])
            self.assertFalse(result["formal_publication_authorized"])
            self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, result["calls"])
            self.assertEqual(1, len(result["observations"]))
            self.assertEqual(9, len(result["records"]))
            for record in result["records"]:
                self.assertEqual(record, validate_record(record=record))
            rebuilt, trace = calculate_observation_metric(compiled_spec=result["compiled_spec"],
                target=result["target"], company_traits=result["company_traits"], observation=result["observations"][0])
            self.assertEqual(result["result"], rebuilt)
            self.assertEqual(result["trace"], trace)
            self.assertEqual(result, self.resolve(metric))
        self.assertEqual("SOURCE_DISCLOSED_AVERAGE", self.actual["A03"]["input_binding"]["measurement_time_basis"])
        var = self.actual["A12"]["source_fact"]["totals"][0]
        self.assertEqual("95", var["risk_horizon"]["confidence_percent"])
        self.assertEqual(1, var["risk_horizon"]["holding_period_days"])
        self.assertEqual("AVERAGE", var["statistical_window"]["statistic"])
        self.assertFalse(self.actual["A03"]["source_fact"]["historical_citi_exception_reused"])

    def test_nine_nonfinancial_companies_have_54_structural_results_without_reader_or_observation(self):
        companies = [row["company_id"] for row in _registry_rows(repo_root=ROOT)
                     if row["industry_profile"] != "financial_institution"]
        self.assertEqual(9, len(companies))
        rows = []
        with patch.object(native, "_fact", side_effect=AssertionError("structural input reached financial reader")):
            for company in companies:
                for metric in native.SPEC_PATHS:
                    result = self.resolve(metric, company=company)
                    rows.append((company, metric))
                    self.assertEqual("N_A_STRUCTURAL", result["result"]["applicability"])
                    self.assertEqual("TRAIT_NOT_APPLICABLE", result["result"]["reason_code"])
                    self.assertIsNone(result["result"]["value"])
                    self.assertEqual([], result["observations"])
                    self.assertIsNone(result["source_fact"])
                    self.assertEqual(result["filing_period"], result["target_period"])
                    self.assertEqual("STRUCTURAL_NO_MEASUREMENT", result["input_binding"]["measurement_time_basis"])
                    self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, result["calls"])
                    for record in result["records"]:
                        validate_record(record=record)
        self.assertEqual(54, len(set(rows)))

    def test_caller_cannot_supply_answer_receipt_table_or_fixture_company(self):
        for argument in ("value", "source_fact", "table_id", "source_set_manifest"):
            with self.subTest(argument=argument), self.assertRaises(TypeError):
                native.resolve_ordinary_financial_metric(repo_root=ROOT, company_id="jpmorgan_chase",
                                                        metric_id="A09", **{argument: "caller input"})
        for company in ("citigroup", "bank_of_america"):
            with self.subTest(company=company), self.assertRaisesRegex(NormalAnnualInputError, "COMPANY_NOT_UNIQUE"):
                self.resolve("A09", company=company)

    def test_component_only_status_never_becomes_a_verified_observation(self):
        # TEST_ONLY stubs simulate a partial component with a tempting amount.
        # No fake component is accepted as an API input or native observation.
        cases = [
            ("A03", "inspect_lcr_disclosed_fact", {"status": "UNRESOLVED", "value": "1.11"}),
            ("A04", "inspect_nim_relationships", {"status": "RELATIONSHIP_PROVEN", "semantic_status": "UNRESOLVED"}),
            ("A11", "inspect_aum_balance", {"status": "BALANCE_SCOPE_PROVEN", "semantic_status": "UNRESOLVED", "value": "4791000000000"}),
            ("A12", "inspect_total_var", {"status": "TOTAL_VAR_SCOPE_PROVEN", "semantic_status": "UNRESOLVED"}),
            ("A13", "inspect_inline_financial_claims", {"outcome": "STRUCTURED_SOURCE_CONFLICT",
                "source_set_scope": "NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET", "value": "42758000000"}),
        ]
        for metric, name, incomplete in cases:
            with self.subTest(metric=metric), patch.object(native, name, return_value=incomplete):
                result = self.resolve(metric)
            self.assertEqual([], result["observations"])
            self.assertEqual("WITHHELD", result["result"]["publication"])
            self.assertIsNone(result["result"]["value"])
            self.assertFalse(result["input_binding"]["source_semantics_passed"])

    def test_unprocessed_annual_amendment_blocks_the_financial_value(self):
        prepared = copy.deepcopy(self.actual["A04"]["prepared_input"])
        prepared["update_status"] = "AMENDMENT_PROCESSING_REQUIRED"
        with patch.object(native, "prepare_saved_annual_input", return_value=prepared), patch.object(
                native, "_fact", side_effect=AssertionError("unprocessed amendment reached resolver")):
            result = self.resolve("A04")
        self.assertEqual("WITHHELD", result["result"]["publication"])
        self.assertIsNone(result["result"]["value"])
        self.assertEqual([], result["observations"])

    def test_source_failure_and_failed_admission_keep_explicit_input_categories(self):
        with patch.object(native, "prepare_saved_annual_input", side_effect=AnnualUpdateError("LATEST_SOURCE_REQUEST_FAILED: TEST_ONLY")):
            with self.assertRaises(native.FinancialResultError) as caught:
                self.resolve("A04")
        self.assertEqual("SOURCE_ACCESS_FAILED", caught.exception.category)
        with patch.object(native, "verify_saved_source_proofs", side_effect=NormalSourceAuthorityError("SOURCE_NOT_IN_TRUSTED_SAVED_BASELINE")):
            with self.assertRaises(native.FinancialResultError) as caught, patch.object(
                    native, "_fact", side_effect=AssertionError("failed admission reached resolver")):
                self.resolve("A04")
        self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)

    def _isolated(self, root):
        original = self.actual["A04"]
        paths = {original["spec_path"], "config/company_registry.csv", "config/metric_applicability.yaml",
                 "catalog/company_traits.yaml", "evidence/requests_log.csv", "evidence/requests_log_manifest.json"}
        for proof in original["source_proofs"]:
            paths.update((proof["request_repo_relative_path"], proof["request_headers_repo_relative_path"]))
        for relative in paths:
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, dest)

    def test_portable_source_replay_and_caller_rule_or_acquisition_changes_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="financial-native-source-") as tmp:
            root = Path(tmp)
            self._isolated(root)
            self.assertEqual(self.actual["A04"], self.resolve("A04", root=root))
            path = root / self.actual["A04"]["spec_path"]
            original = path.read_bytes()
            path.write_bytes(original.replace(b'"basis": "managed_basis"', b'"basis": "reported_basis"'))
            with self.assertRaises(native.FinancialResultError) as caught:
                self.resolve("A04", root=root)
            self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)
            path.write_bytes(original)
            proof = self.actual["A04"]["source_proofs"][1]
            source = root / proof["request_repo_relative_path"]
            source.write_bytes(source.read_bytes() + b" ")
            with self.assertRaises(native.FinancialResultError) as caught, patch.object(native, "_fact", side_effect=AssertionError("untrusted source reached resolver")):
                self.resolve("A04", root=root)
            self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)


if __name__ == "__main__":
    unittest.main()
