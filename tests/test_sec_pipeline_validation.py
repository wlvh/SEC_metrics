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


if __name__ == "__main__":
    unittest.main()
