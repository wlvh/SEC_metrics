"""Regression tests for SEC repair validation integrity gates.

Purpose:
    Exercise Basel threshold exclusion and light golden tamper detection
    without mutating the repository outputs.

Call relationships:
    unittest imports scripts/sec_pipeline.py, patches its workspace constants
    to a temporary package, and calls pure validation helpers.
"""

from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sec_pipeline  # noqa: E402


def read_rows(*, path: Path) -> list[dict]:
    """Read CSV rows for test fixture mutation.

    Args:
        path: CSV file path.

    Returns:
        List of row dictionaries.
    """
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def write_rows(*, path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write CSV rows after test-only tampering.

    Args:
        path: CSV file path.
        fieldnames: Stable header order.
        rows: Mutated rows.

    Expected output:
        The temporary fixture file reflects exactly the requested mutation.
    """
    with path.open(mode="w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mutate_csv_row(
    *,
    path: Path,
    selector_field: str,
    selector_value: str,
    updates: dict[str, str],
) -> None:
    """Mutate one CSV row in a temporary test workspace.

    Args:
        path: CSV file path.
        selector_field: Column used to identify the row.
        selector_value: Required selected value.
        updates: Column/value replacements for the selected row.

    Expected output:
        Exactly one matching row is updated, otherwise the test fails fast.
    """
    rows = read_rows(path=path)
    fieldnames = list(rows[0].keys())
    match_count = 0
    for row in rows:
        if row[selector_field] != selector_value:
            continue
        for field, value in updates.items():
            row[field] = value
        match_count += 1
    if match_count != 1:
        raise AssertionError(f"Expected one row for {selector_value}, got {match_count}")
    write_rows(path=path, fieldnames=fieldnames, rows=rows)


def build_light_workspace(*, root: Path) -> Path:
    """Create a minimal light package workspace in a temp directory.

    Args:
        root: Temporary directory root.

    Returns:
        Workspace path containing config, golden fixture, and key outputs.
    """
    workspace = root / "workspace"
    (workspace / "outputs").mkdir(parents=True)
    fixture_dir = workspace / "tests" / "fixtures" / "sec_10_company_spike"
    fixture_dir.mkdir(parents=True)
    shutil.copytree(src=REPO_ROOT / "config", dst=workspace / "config")
    for name in [
        "company_resolution.csv",
        "golden_results.csv",
        "metrics_matrix.csv",
    ]:
        shutil.copy(src=REPO_ROOT / "outputs" / name, dst=workspace / "outputs" / name)
    shutil.copy(
        src=(
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "sec_10_company_spike"
            / "golden_expected_values.csv"
        ),
        dst=fixture_dir / "golden_expected_values.csv",
    )
    return workspace


@contextmanager
def patched_workspace(*, workspace: Path):
    """Patch sec_pipeline path constants to a temporary workspace."""
    with mock.patch.object(sec_pipeline, "WORKDIR", workspace), mock.patch.object(
        sec_pipeline,
        "CONFIG_PATH",
        workspace / "config" / "sec_config.json",
    ), mock.patch.object(
        sec_pipeline,
        "COMPANY_REGISTRY_PATH",
        workspace / "config" / "company_registry.csv",
    ), mock.patch.object(
        sec_pipeline,
        "METRIC_APPLICABILITY_PATH",
        workspace / "config" / "metric_applicability.yaml",
    ), mock.patch.object(
        sec_pipeline,
        "REQUEST_LOG_PATH",
        workspace / "evidence" / "requests_log.csv",
    ), mock.patch.object(
        sec_pipeline,
        "LIGHT_REVIEW_MARKER_PATH",
        workspace / "LIGHT_REVIEW_PACKAGE.marker",
    ):
        yield


class LightGoldenIntegrityTest(unittest.TestCase):
    """Validate light golden integrity rejects tampered package inputs."""

    def test_missing_evidence_without_marker_is_workspace_incomplete(self) -> None:
        """Missing raw materials without marker must not auto-downgrade."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = build_light_workspace(root=Path(tmp_dir))
            with patched_workspace(workspace=workspace):
                mode, reasons = sec_pipeline.validation_package_mode()
        self.assertEqual(mode, "WORKSPACE_INCOMPLETE")
        self.assertTrue(reasons)

    def test_light_marker_allows_declared_light_mode(self) -> None:
        """The marker is the explicit declaration for light review mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = build_light_workspace(root=Path(tmp_dir))
            (workspace / "LIGHT_REVIEW_PACKAGE.marker").write_text(
                "light review package\n",
                encoding="utf-8",
            )
            with patched_workspace(workspace=workspace):
                mode, reasons = sec_pipeline.validation_package_mode()
        self.assertEqual(mode, "LIGHT_REVIEW_MODE")
        self.assertTrue(reasons)

    def test_tampered_golden_actual_fails_integrity(self) -> None:
        """Changing actual while leaving PASS must fail recomputation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = build_light_workspace(root=Path(tmp_dir))
            mutate_csv_row(
                path=workspace / "outputs" / "golden_results.csv",
                selector_field="assertion_id",
                selector_value="G3_clean_xbrl_revenue",
                updates={"actual": "999", "status": "PASS"},
            )
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_light_golden_snapshot_integrity()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("G3_clean_xbrl_revenue", result["details"])

    def test_tampered_fixture_expected_fails_integrity(self) -> None:
        """Changing fixture expected must fail against stored snapshot."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = build_light_workspace(root=Path(tmp_dir))
            mutate_csv_row(
                path=(
                    workspace
                    / "tests"
                    / "fixtures"
                    / "sec_10_company_spike"
                    / "golden_expected_values.csv"
                ),
                selector_field="assertion_id",
                selector_value="G3_clean_xbrl_revenue",
                updates={"expected": "999"},
            )
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_light_golden_snapshot_integrity()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("fixture_expected_mismatch", result["details"])

    def test_tampered_metrics_matrix_dependency_fails_integrity(self) -> None:
        """Changing metrics_matrix value used by golden must fail."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = build_light_workspace(root=Path(tmp_dir))
            metrics_path = workspace / "outputs" / "metrics_matrix.csv"
            rows = read_rows(path=metrics_path)
            fieldnames = list(rows[0].keys())
            match_count = 0
            for row in rows:
                if row["company"] != "Enphase Energy" or row["metric_id"] != "B01":
                    continue
                row["value"] = "999"
                match_count += 1
            if match_count != 1:
                raise AssertionError("Expected one Enphase B01 row")
            write_rows(path=metrics_path, fieldnames=fieldnames, rows=rows)
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_light_golden_snapshot_integrity()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("metrics_value_drift:B01", result["details"])


class BaselThresholdValidationTest(unittest.TestCase):
    """Validate Basel threshold concepts are never primary candidates."""

    def test_threshold_concepts_do_not_match_primary_metrics(self) -> None:
        """Requirement concepts must be regulatory thresholds only."""
        result = sec_pipeline.check_basel_threshold_concepts_never_match_primary_metric()
        self.assertEqual(result["status"], "PASS")

    def test_same_dimension_threshold_loses_to_actual_ratio(self) -> None:
        """Actual CET1 must win over same-dimension lower threshold."""
        result = sec_pipeline.check_basel_primary_selection_prefers_actual_ratio_over_threshold()
        self.assertEqual(result["status"], "PASS")


class CaptiveFinanceValidationTest(unittest.TestCase):
    """Validate captive-finance member recall and exclusion guards."""

    def test_captive_member_variants_trigger_review(self) -> None:
        """Captive/credit/legal-entity members must be recognized."""
        result = sec_pipeline.check_gm_like_captive_finance_fixture_triggers_review()
        self.assertEqual(result["status"], "PASS")

    def test_normal_credit_and_finance_terms_do_not_trigger(self) -> None:
        """Credit-loss/facility/lease/deferred-cost terms are exclusions."""
        result = sec_pipeline.check_captive_finance_excludes_normal_finance_lease_terms()
        self.assertEqual(result["status"], "PASS")


class EleventhCompanyBehaviorTest(unittest.TestCase):
    """Validate eleventh-company fixtures assert selected value identity."""

    def test_financial_institution_fixture_checks_value_context_and_dimensions(self) -> None:
        """FI fixture must select expected concept, context, dimensions, and value."""
        result = sec_pipeline.check_eleventh_company_behavior_financial_institution()
        self.assertEqual(result["status"], "PASS")


class InlineScaleValidationTest(unittest.TestCase):
    """Validate iXBRL scale and parser-route regressions."""

    def test_scaled_inline_value_cases_pass(self) -> None:
        """Scale, sign, parentheses, and passthrough cases must pass."""
        self.assertEqual(sec_pipeline.scaled_inline_value_validation_failures(), [])

    def test_inline_parser_route_applies_scale(self) -> None:
        """XML-parseable iXBRL fixture must still apply ix scale."""
        self.assertEqual(sec_pipeline.inline_scale_route_fixture_failures(), [])

    def test_full_evidence_jpm_cet1_amount_crosscheck(self) -> None:
        """Complete local evidence should retain the scaled CET1 amount."""
        self.assertEqual(sec_pipeline.jpm_cet1_capital_scale_crosscheck_failures(), [])


class FullInstanceFallbackTest(unittest.TestCase):
    """Validate 10-K/A targets map to original full-instance candidates."""

    def setUp(self) -> None:
        """Skip fallback evidence tests when submissions evidence is absent."""
        if not (REPO_ROOT / "evidence" / "submissions").exists():
            self.skipTest("full submissions evidence unavailable")

    def test_ten_k_a_targets_resolve_original_full_instance(self) -> None:
        """Southwest/Paramount-like amended targets must find original 10-K rows."""
        matches = 0
        for role_row in sec_pipeline.all_role_rows():
            rows = sec_pipeline.recent_filing_rows(
                company=role_row["company"],
                cik=int(role_row["cik"]),
                entity_role=role_row["entity_role"],
            )
            target = sec_pipeline.select_latest_10k(rows=rows)
            if target["form"] != "10-K/A":
                continue
            fallback = sec_pipeline.original_full_instance_fallback_row(
                rows=rows,
                target=target,
                company_config=sec_pipeline.company_by_name(
                    company_name=role_row["company"],
                ),
                parsed_rows=None,
            )
            self.assertIsNotNone(fallback)
            self.assertEqual(fallback["source_role"], "target_original_full_instance")
            self.assertEqual(fallback["form"], "10-K")
            self.assertEqual(fallback["reportDate"], target["reportDate"])
            matches += 1
        self.assertGreaterEqual(matches, 2)

    def test_sparse_instance_rows_trigger_fallback_reason(self) -> None:
        """Tiny parsed target instance must be marked fallback-worthy."""
        company_config = sec_pipeline.load_company_registry()[0]
        target = {
            "form": "10-K",
            "reportDate": date(year=2025, month=12, day=31).isoformat(),
            "accessionNumber": "mock-accession",
        }
        reasons = sec_pipeline.full_instance_fallback_reasons(
            target=target,
            company_config=company_config,
            parsed_rows=[],
        )
        self.assertIn("target_instance_fact_count_lt_500", reasons)


class ScannerConstantFoldingTest(unittest.TestCase):
    """Validate AST scanner catches string-addition identity tampering."""

    def test_string_addition_tamper_is_detected(self) -> None:
        """String constant folding must catch split company names."""
        self.assertTrue(sec_pipeline.scanner_constant_folding_tamper_detected())


class ImplementationMapTest(unittest.TestCase):
    """Validate repair instructions are mapped to implementation evidence."""

    def test_implementation_map_covers_all_instruction_ids(self) -> None:
        """I1-I8 must each have at least one map row."""
        rows = sec_pipeline.implementation_map_rows()
        instruction_ids = {row["instruction_id"] for row in rows}
        self.assertEqual(
            instruction_ids,
            {"I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"},
        )


if __name__ == "__main__":
    unittest.main()
