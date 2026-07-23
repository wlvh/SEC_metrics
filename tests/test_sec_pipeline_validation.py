"""Regression and adversarial tests for SEC pipeline audit boundaries.

Purpose:
    Verify metric semantics, exact-set validation, portable evidence identity,
    request persistence, report publication, capability anchors, and bounded
    repair behavior without mutating checked-in evidence during unit tests.

Call relationships:
    unittest imports sec_pipeline, sec_http, and the capability checker; most
    scenarios redirect workspace paths to temporary repositories, while a
    small full-evidence layer reads checked-in raw artifacts without writing.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from datetime import date
from email.message import Message
from http.client import IncompleteRead
from pathlib import Path
from unittest import mock
from urllib.request import HTTPSHandler, build_opener
from urllib.response import addinfourl


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sec_pipeline  # noqa: E402
import check_capability_contract_alignment as contract_alignment  # noqa: E402
import sec_http  # noqa: E402


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


def rows_csv_text(*, fieldnames: list[str], rows: list[dict]) -> str:
    """Serialize test rows with one explicit CSV schema."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(f=output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def csv_text_with_row_width_delta(
    *,
    text: str,
    data_row_index: int,
    extra_cell: bool,
) -> str:
    """Return CSV text with one data row widened or narrowed by one cell.

    Args:
        text: Valid CSV text containing a header and the selected data row.
        data_row_index: Zero-based data-row index, excluding the header.
        extra_cell: Add one cell when true; remove the final cell when false.

    Returns:
        UTF-8-compatible CSV text preserving every unselected row.
    """
    line_ending = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(line_ending)
    line_index = data_row_index + 1
    if line_index >= len(lines):
        raise IndexError(f"CSV data row does not exist: {data_row_index}")
    # Mutate raw CSV rather than parsed fields so DictReader must expose the
    # overflow or missing cell while every unselected byte stays unchanged.
    if extra_cell:
        lines[line_index] += ",INJECTED"
    else:
        separator_index = lines[line_index].rfind(",")
        if separator_index < 0:
            raise ValueError("CSV row has no removable final cell")
        lines[line_index] = lines[line_index][:separator_index]
    return line_ending.join(lines)


def legacy_request_row(
    *,
    source_url: str,
    legacy_root: Path,
    document_name: str,
    headers_name: str,
    body: bytes,
    timestamp_utc: str,
) -> dict:
    """Build one complete legacy request observation for path tests.

    Args:
        source_url: Requested SEC URL.
        legacy_root: Former clone directory containing the response files.
        document_name: Response body filename.
        headers_name: Sidecar filename, or blank when deliberately absent.
        body: Declared response bytes.
        timestamp_utc: Fixed UTC observation time.

    Returns:
        Legacy row whose length and digest match body.
    """
    return {
        "timestamp_utc": timestamp_utc,
        "method": "GET",
        "url": source_url,
        "status_code": "200",
        "purpose": "fixture",
        "local_path": str(legacy_root / document_name),
        "headers_path": (
            str(legacy_root / headers_name)
            if headers_name
            else ""
        ),
        "content_length": str(len(body)),
        "sha256": hashlib.sha256(body).hexdigest(),
        "user_agent": "fixture fixture@example.com",
        "retry_attempt": "0",
        "error": "",
    }


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
        raise AssertionError(
            f"Expected one row for {selector_value}, got {match_count}"
        )
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
        shutil.copy(src=REPO_ROOT / "outputs" / name,
                    dst=workspace / "outputs" / name)
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


def validation_manifest_fixture(
    *,
    mode: str,
    result: str,
    refreshed_artifacts: list[str],
) -> dict:
    """Build one structurally complete validation-manifest fixture.

    Args:
        mode: Validation package mode under test.
        result: Terminal or in-progress manifest result.
        refreshed_artifacts: Tracked artifacts completed by the fixture run.

    Returns:
        A complete manifest whose artifact lists form an exact partition.
    """
    return {
        "run_id": "fixture-run-id",
        "source_commit": "fixture-source-commit",
        "started_at_utc": "2026-07-22T00:00:00+00:00",
        "mode": mode,
        "refreshed_artifacts": refreshed_artifacts,
        "not_refreshed_artifacts": [
            artifact
            for artifact in sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
            if artifact not in refreshed_artifacts
        ],
        "result": result,
    }


def build_http_client(*, workspace: Path) -> sec_http.SecHttpClient:
    """Create one zero-retry SEC client inside a temporary workspace.

    Args:
        workspace: Test-only repository root.

    Returns:
        Configured client whose request log and manifest are isolated.
    """
    config_path = workspace / "config" / "sec_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "organization": "fixture",
                "contact_email": "fixture@example.com",
                "rate_limit_per_sec": 10,
                "max_retries": 0,
                "backoff_initial_seconds": 0,
            }
        ),
        encoding="utf-8",
    )
    return sec_http.SecHttpClient(
        workdir=workspace,
        config_path=config_path,
        log_path=workspace / "evidence" / "requests_log.csv",
    )


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


class FullGoldenIntegrityTest(unittest.TestCase):
    """Validate full Golden uses the configured exact assertion set."""

    def test_expected_set_is_independent_of_g1_generator_output(self) -> None:
        """A generator omission cannot shrink its acceptance set."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = build_light_workspace(root=Path(tmp_dir))
            path = workspace / "outputs" / "golden_results.csv"
            rows = read_rows(path=path)
            g1_rows = [
                row for row in rows if row["assertion_id"].startswith("G1_")
            ]
            omitted_id = g1_rows[0]["assertion_id"]
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "run_company_structure_golden",
                return_value=g1_rows[1:],
            ) as generator:
                expected_before = sec_pipeline.expected_golden_assertion_ids()
                generated_rows = sec_pipeline.run_company_structure_golden()
                write_rows(
                    path=path,
                    fieldnames=list(rows[0]),
                    rows=[
                        row
                        for row in rows
                        if not row["assertion_id"].startswith("G1_")
                    ] + generated_rows,
                )
                result = sec_pipeline.check_golden_results_all_pass()
                expected_after = sec_pipeline.expected_golden_assertion_ids()
            generator.assert_called_once_with()
        self.assertEqual(expected_before, expected_after)
        self.assertIn(omitted_id, expected_after)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn(f"missing={omitted_id}", result["details"])

    def test_missing_duplicate_or_unexpected_assertion_cannot_pass(
        self,
    ) -> None:
        """Shrinking or reshaping the assertion set must fail closed."""
        for mutation, expected_detail in [
            ("missing", "missing="),
            ("duplicate", "duplicate="),
            ("unexpected", "unexpected="),
        ]:
            with self.subTest(
                mutation=mutation,
            ), tempfile.TemporaryDirectory() as tmp_dir:
                workspace = build_light_workspace(root=Path(tmp_dir))
                path = workspace / "outputs" / "golden_results.csv"
                rows = read_rows(path=path)
                if mutation == "missing":
                    changed_rows = rows[1:]
                elif mutation == "duplicate":
                    changed_rows = rows + [dict(rows[0])]
                else:
                    extra = dict(rows[0])
                    extra["assertion_id"] = "G9_unexpected_fixture"
                    changed_rows = rows + [extra]
                write_rows(
                    path=path,
                    fieldnames=list(rows[0]),
                    rows=changed_rows,
                )
                with patched_workspace(workspace=workspace):
                    result = sec_pipeline.check_golden_results_all_pass()
            self.assertEqual(result["status"], "FAIL")
            self.assertIn(expected_detail, result["details"])


class StratifiedAuditIntegrityTest(unittest.TestCase):
    """Validate the audit gate requires its complete deterministic sample."""

    def test_current_complete_sample_passes(self) -> None:
        """The generator and exact-set gate must agree on all five strata."""
        metrics = sec_pipeline.load_metrics()
        rows = sec_pipeline.build_stratified_audit_rows()
        check_audit = getattr(
            sec_pipeline,
            "check_stratified_audit_all_pass_or_explicitly_caveated",
        )
        result = check_audit(audit_rows=rows, metrics=metrics)
        counts = {}
        for bucket, _source_classes, _limit in (
            sec_pipeline.STRATIFIED_AUDIT_SPECS
        ):
            counts[bucket] = len(
                [row for row in rows if row["source_bucket"] == bucket]
            )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            counts,
            {
                "STD_XBRL_DERIVED": 8,
                "DIM_XBRL": 4,
                "DEF14A": 3,
                "MDA_TEXT": 3,
                "8K_ITEM": 2,
            },
        )

    def test_shrunk_or_duplicated_sample_cannot_pass(self) -> None:
        """Deleting or duplicating an audit row must fail exact-set checks."""
        metrics = sec_pipeline.load_metrics()
        rows = sec_pipeline.build_stratified_audit_rows()
        check_audit = getattr(
            sec_pipeline,
            "check_stratified_audit_all_pass_or_explicitly_caveated",
        )
        for mutation, changed_rows, expected_detail in [
            ("missing", rows[1:], "sample_exact_set_mismatch"),
            ("duplicate", rows + [dict(rows[0])], "duplicate_sample_keys"),
        ]:
            with self.subTest(mutation=mutation):
                result = check_audit(
                    audit_rows=changed_rows,
                    metrics=metrics,
                )
            self.assertEqual(result["status"], "FAIL")
            self.assertIn(expected_detail, result["details"])


class BaselThresholdValidationTest(unittest.TestCase):
    """Validate Basel threshold concepts are never primary candidates."""

    def test_threshold_concepts_do_not_match_primary_metrics(self) -> None:
        """Requirement concepts must be regulatory thresholds only."""
        result = (
            sec_pipeline
            .check_basel_threshold_concepts_never_match_primary_metric()
        )
        self.assertEqual(result["status"], "PASS")

    def test_same_dimension_threshold_loses_to_actual_ratio(self) -> None:
        """Actual CET1 must win over same-dimension lower threshold."""
        result = (
            sec_pipeline
            .check_basel_primary_selection_prefers_actual_ratio_over_threshold()
        )
        self.assertEqual(result["status"], "PASS")


class CaptiveFinanceValidationTest(unittest.TestCase):
    """Validate captive-finance member recall and exclusion guards."""

    def test_captive_member_variants_trigger_review(self) -> None:
        """Captive/credit/legal-entity members must be recognized."""
        result = sec_pipeline.check_gm_like_captive_finance_fixture_triggers_review()
        self.assertEqual(result["status"], "PASS")

    def test_normal_credit_and_finance_terms_do_not_trigger(self) -> None:
        """Credit-loss/facility/lease/deferred-cost terms are exclusions."""
        result = (
            sec_pipeline
            .check_captive_finance_excludes_normal_finance_lease_terms()
        )
        self.assertEqual(result["status"], "PASS")


class EleventhCompanyBehaviorTest(unittest.TestCase):
    """Validate eleventh-company fixtures assert selected value identity."""

    def test_financial_institution_fixture_checks_value_context_and_dimensions(
        self,
    ) -> None:
        """FI fixture must select expected concept, context, dimensions, and value."""
        result = sec_pipeline.check_eleventh_company_behavior_financial_institution()
        self.assertEqual(result["status"], "PASS")


class InlineScaleValidationTest(unittest.TestCase):
    """Validate iXBRL scale and parser-route regressions."""

    def test_scaled_inline_value_cases_pass(self) -> None:
        """Scale, sign, parentheses, and passthrough cases must pass."""
        self.assertEqual(
            sec_pipeline.scaled_inline_value_validation_failures(), [])

    def test_inline_parser_route_applies_scale(self) -> None:
        """XML-parseable iXBRL fixture must still apply ix scale."""
        self.assertEqual(
            sec_pipeline.inline_scale_route_fixture_failures(), [])

    def test_inline_auditor_namespace_resolves_declared_uri(self) -> None:
        """Inline AuditorName must retain its declared namespace URI."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "fixture.htm"
            material = {
                "company": "Fixture Company",
                "cik": "1",
                "accession": "0000000001-26-000001",
                "document_name": file_path.name,
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/fixture.htm"
                ),
            }
            cases = [
                ("dei", "http://xbrl.sec.gov/dei/2025", True),
                ("custom", "http://xbrl.sec.gov/dei/2025", True),
                ("dei", "https://example.com/custom", False),
            ]
            for prefix, namespace_uri, accepted in cases:
                with self.subTest(
                    prefix=prefix,
                    namespace_uri=namespace_uri,
                ):
                    file_path.write_text(
                        "<html xmlns:ix='http://www.xbrl.org/2013/inlineXBRL' "
                        "xmlns:xbrli='http://www.xbrl.org/2003/instance' "
                        f"xmlns:{prefix}='{namespace_uri}'>"
                        "<xbrli:context id='c1'><xbrli:period>"
                        "<xbrli:instant>2025-12-31</xbrli:instant>"
                        "</xbrli:period></xbrli:context>"
                        f"<ix:nonNumeric name='{prefix}:AuditorName' "
                        "contextRef='c1'>Fixture LLP</ix:nonNumeric>"
                        "</html>",
                        encoding="utf-8",
                    )
                    rows = sec_pipeline.parse_inline_instance(
                        file_path=file_path,
                        material_row=material,
                    )
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["namespace"], namespace_uri)
                    self.assertEqual(
                        sec_pipeline.is_dei_namespace(
                            namespace=rows[0]["namespace"],
                        ),
                        accepted,
                    )
            file_path.write_text(
                "<html xmlns:ix='http://www.xbrl.org/2013/inlineXBRL' "
                "xmlns:dei='http://xbrl.sec.gov/dei/2025'>"
                "<ix:nonNumeric name='dei:AuditorName' contextRef='c1'>"
                "Fixture LLP</ix:nonNumeric>"
                "<div xmlns:dei='https://example.com/custom'></div>"
                "</html>",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                sec_pipeline.parse_inline_instance(
                    file_path=file_path,
                    material_row=material,
                )

    def test_full_evidence_jpm_cet1_amount_crosscheck(self) -> None:
        """Complete local evidence should retain the scaled CET1 amount."""
        self.assertEqual(
            sec_pipeline.jpm_cet1_capital_scale_crosscheck_failures(), [])

    def test_missing_jpm_cet1_evidence_is_not_a_pass(self) -> None:
        """Missing full evidence must not collapse to an empty failure list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()
            with patched_workspace(workspace=workspace):
                failures = sec_pipeline.jpm_cet1_capital_scale_crosscheck_failures()
        self.assertTrue(failures)
        self.assertIn("missing", failures[0])


class ReportVerdictTest(unittest.TestCase):
    """Validate non-evaluation cannot be promoted to a full PASS verdict."""

    def test_full_not_evaluated_blocks_go(self) -> None:
        """A critical NOT_EVALUATED row must force the full verdict to NO-GO."""
        validation_rows = [
            {
                "check_id": "missing_evidence",
                "severity": "P0",
                "status": "NOT_EVALUATED_MISSING_EVIDENCE",
            },
            {
                "check_id": "validation_gate_result",
                "severity": "P0",
                "status": "PASS",
            },
        ]
        verdict = sec_pipeline.report_verdict(
            golden_rows=[{"status": "PASS"}],
            metric_rows=[],
            validation_rows=validation_rows,
            validation_manifest=validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="PASSED",
                refreshed_artifacts=list(
                    sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
                ),
            ),
        )
        self.assertEqual(verdict, "NO-GO")
        self.assertEqual(
            sec_pipeline.blocking_validation_rows(
                rows=validation_rows,
                mode="FULL_VALIDATION",
            ),
            [validation_rows[0]],
        )
        self.assertEqual(
            sec_pipeline.validation_manifest_result(
                rows=validation_rows,
                mode="FULL_VALIDATION",
            ),
            "FAILED",
        )
        self.assertEqual(
            sec_pipeline.validation_manifest_result(
                rows=validation_rows,
                mode="LIGHT_REVIEW_MODE",
            ),
            "PASSED_WITH_CAVEATS",
        )

    def test_light_not_evaluated_is_an_explicit_caveat(self) -> None:
        """Light non-evaluation may continue only as GO WITH CAVEATS."""
        verdict = sec_pipeline.report_verdict(
            golden_rows=[{"status": "PASS"}],
            metric_rows=[],
            validation_rows=[
                {
                    "check_id": "missing_evidence",
                    "severity": "P0",
                    "status": "NOT_EVALUATED_MISSING_EVIDENCE",
                },
                {
                    "check_id": "validation_gate_result",
                    "severity": "P0",
                    "status": "SKIPPED_LIGHT_PACKAGE",
                },
            ],
            validation_manifest=validation_manifest_fixture(
                mode="LIGHT_REVIEW_MODE",
                result="PASSED_WITH_CAVEATS",
                refreshed_artifacts=[
                    artifact
                    for artifact in sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
                    if artifact != "stub_period_metrics.csv"
                ],
            ),
        )
        self.assertEqual(verdict, "GO WITH CAVEATS")

    def test_stale_validation_csv_cannot_drive_go(self) -> None:
        """A present but not-refreshed validation CSV must force NO-GO."""
        verdict = sec_pipeline.report_verdict(
            golden_rows=[{"status": "PASS"}],
            metric_rows=[],
            validation_rows=[
                {
                    "check_id": "validation_gate_result",
                    "severity": "P0",
                    "status": "PASS",
                }
            ],
            validation_manifest=validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="PASSED",
                refreshed_artifacts=[],
            ),
        )
        self.assertEqual(verdict, "NO-GO")

    def test_corrupt_manifest_values_fail_closed(self) -> None:
        """Unknown mode/result or incomplete artifact partition cannot GO."""
        manifests = [
            validation_manifest_fixture(
                mode="TYPO_FULL",
                result="PASSED",
                refreshed_artifacts=["repair_validation_results.csv"],
            ),
            validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="CORRUPT_SUCCESS",
                refreshed_artifacts=["repair_validation_results.csv"],
            ),
            {
                **validation_manifest_fixture(
                    mode="FULL_VALIDATION",
                    result="PASSED",
                    refreshed_artifacts=["repair_validation_results.csv"],
                ),
                "not_refreshed_artifacts": [],
            },
        ]
        validation_rows = [
            {
                "check_id": "validation_gate_result",
                "severity": "P0",
                "status": "PASS",
            }
        ]
        for manifest in manifests:
            with self.subTest(manifest=manifest):
                verdict = sec_pipeline.report_verdict(
                    golden_rows=[{"status": "PASS"}],
                    metric_rows=[],
                    validation_rows=validation_rows,
                    validation_manifest=manifest,
                )
                self.assertEqual(verdict, "NO-GO")

    def test_unknown_status_or_missing_aggregate_gate_fails_closed(self) -> None:
        """Report input requires the closed vocabulary and aggregate gate."""
        manifest = validation_manifest_fixture(
            mode="FULL_VALIDATION",
            result="PASSED",
            refreshed_artifacts=list(
                sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
            ),
        )
        for rows in [
            [
                {
                    "check_id": "validation_gate_result",
                    "severity": "P0",
                    "status": "UNKNOWN_SUCCESS",
                }
            ],
            [
                {
                    "check_id": "individual_check",
                    "severity": "P0",
                    "status": "PASS",
                }
            ],
        ]:
            with self.subTest(rows=rows):
                verdict = sec_pipeline.report_verdict(
                    golden_rows=[{"status": "PASS"}],
                    metric_rows=[],
                    validation_rows=rows,
                    validation_manifest=manifest,
                )
                self.assertEqual(verdict, "NO-GO")

    def test_light_plain_pass_manifest_cannot_return_plain_go(self) -> None:
        """A light package never has enough evidence for an uncaveated GO."""
        verdict = sec_pipeline.report_verdict(
            golden_rows=[{"status": "PASS"}],
            metric_rows=[],
            validation_rows=[
                {
                    "check_id": "validation_gate_result",
                    "severity": "P0",
                    "status": "PASS",
                }
            ],
            validation_manifest=validation_manifest_fixture(
                mode="LIGHT_REVIEW_MODE",
                result="PASSED",
                refreshed_artifacts=[
                    artifact
                    for artifact in sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
                    if artifact != "stub_period_metrics.csv"
                ],
            ),
        )
        self.assertEqual(verdict, "NO-GO")

    def test_successful_manifest_requires_mode_complete_refresh(self) -> None:
        """A terminal success cannot leave mode-required evidence stale."""
        fixtures = [
            validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="PASSED",
                refreshed_artifacts=["repair_validation_results.csv"],
            ),
            validation_manifest_fixture(
                mode="LIGHT_REVIEW_MODE",
                result="PASSED_WITH_CAVEATS",
                refreshed_artifacts=["repair_validation_results.csv"],
            ),
        ]
        for manifest in fixtures:
            with self.subTest(mode=manifest["mode"]):
                errors = sec_pipeline.validation_manifest_errors(
                    manifest=manifest,
                )
                self.assertTrue(
                    any("did not refresh" in error for error in errors)
                )

    def test_manifest_started_at_requires_utc_timestamp(self) -> None:
        """Malformed or non-UTC audit timestamps must fail closed."""
        for started_at_utc in ["not-a-time", "2026-07-22T00:00:00"]:
            manifest = validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="PASSED",
                refreshed_artifacts=list(
                    sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
                ),
            )
            manifest["started_at_utc"] = started_at_utc
            with self.subTest(started_at_utc=started_at_utc):
                errors = sec_pipeline.validation_manifest_errors(
                    manifest=manifest,
                )
                self.assertIn(
                    "started_at_utc must be an ISO 8601 UTC timestamp",
                    errors,
                )


class ValidationStatusVocabularyTest(unittest.TestCase):
    """Validate repair checks use the closed five-status vocabulary."""

    def test_all_declared_statuses_are_accepted(self) -> None:
        """Each declared status must produce a structurally valid row."""
        self.assertEqual(
            sec_pipeline.VALIDATION_STATUSES,
            {
                "PASS",
                "FAIL",
                "SKIPPED_LIGHT_PACKAGE",
                "NOT_EVALUATED_MISSING_EVIDENCE",
                "WORKSPACE_INCOMPLETE",
            },
        )
        for status in sec_pipeline.VALIDATION_STATUSES:
            row = sec_pipeline.validation_row(
                check_id=f"fixture_{status}",
                status=status,
                details="fixture",
            )
            self.assertEqual(row["status"], status)

    def test_unknown_status_fails_fast(self) -> None:
        """Legacy or invented pass labels must be rejected."""
        with self.assertRaises(ValueError):
            sec_pipeline.validation_row(
                check_id="fixture_unknown",
                status="PASS_LIGHT_REVIEW",
                details="fixture",
            )


class MatrixCoverageExactSetTest(unittest.TestCase):
    """Validate matrix and coverage gates reject incomplete key sets."""

    @staticmethod
    def _metrics() -> list[dict]:
        """Load the checked-in matrix without mutating repository artifacts."""
        return read_rows(path=REPO_ROOT / "outputs" / "metrics_matrix.csv")

    @staticmethod
    def _coverage() -> list[dict]:
        """Load the checked-in coverage rows for in-memory mutation."""
        return read_rows(path=REPO_ROOT / "outputs" / "coverage_matrix.csv")

    @staticmethod
    def _evidence() -> list[dict]:
        """Load checked-in metric evidence for the coverage join fixture."""
        return read_rows(path=REPO_ROOT / "outputs" / "metric_evidence.csv")

    def test_current_matrix_matches_config_derived_exact_set(self) -> None:
        """The complete matrix satisfies the registry/profile contract."""
        result = (
            sec_pipeline.check_metrics_matrix_applicability_matches_02_04_spec(
                metrics=self._metrics(),
            )
        )
        self.assertEqual(result["status"], "PASS")

    def test_matrix_equal_size_missing_duplicate_fails(self) -> None:
        """Deleting one key and duplicating another cannot retain PASS."""
        metrics = self._metrics()
        tampered = [dict(row) for row in metrics[1:]]
        tampered.append(dict(metrics[1]))
        result = (
            sec_pipeline.check_metrics_matrix_applicability_matches_02_04_spec(
                metrics=tampered,
            )
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("metrics_matrix_missing=", result["details"])
        self.assertIn("metrics_matrix_duplicate=", result["details"])

    def test_matrix_equal_size_missing_unexpected_fails(self) -> None:
        """Replacing one expected key with an unknown key cannot pass."""
        metrics = [dict(row) for row in self._metrics()]
        metrics[0]["metric_id"] = "Z99"
        result = (
            sec_pipeline.check_metrics_matrix_applicability_matches_02_04_spec(
                metrics=metrics,
            )
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("metrics_matrix_missing=", result["details"])
        self.assertIn("metrics_matrix_unexpected=", result["details"])

    def test_current_coverage_matches_current_matrix_exact_set(self) -> None:
        """Complete coverage preserves all matrix keys and evidence flags."""
        result = sec_pipeline.check_coverage_join(
            coverage=self._coverage(),
            evidence_rows=self._evidence(),
            metrics=self._metrics(),
        )
        self.assertEqual(result["status"], "PASS")

    def test_coverage_shrink_fails(self) -> None:
        """A truncated coverage artifact cannot pass the evidence join gate."""
        result = sec_pipeline.check_coverage_join(
            coverage=self._coverage()[:-1],
            evidence_rows=self._evidence(),
            metrics=self._metrics(),
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("coverage_matrix_missing=", result["details"])

    def test_coverage_equal_size_missing_duplicate_fails(self) -> None:
        """A duplicate coverage key cannot hide one deleted matrix key."""
        coverage = self._coverage()
        tampered = [dict(row) for row in coverage[1:]]
        tampered.append(dict(coverage[1]))
        result = sec_pipeline.check_coverage_join(
            coverage=tampered,
            evidence_rows=self._evidence(),
            metrics=self._metrics(),
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("coverage_matrix_missing=", result["details"])
        self.assertIn("coverage_matrix_duplicate=", result["details"])


class ValidationRunManifestTest(unittest.TestCase):
    """Validate every repair validation run declares refreshed evidence."""

    @staticmethod
    def _successful_deferred_validation(
        *,
        exit_on_failure: bool,
        manifest: dict | None = None,
    ) -> list[dict]:
        """Write a complete in-progress manifest for stage terminal tests."""
        if exit_on_failure:
            raise AssertionError("stage must defer terminal manifest success")
        if manifest is None:
            manifest = validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="IN_PROGRESS",
                refreshed_artifacts=[],
            )
        manifest["mode"] = "FULL_VALIDATION"
        manifest["refreshed_artifacts"] = list(
            sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
        )
        manifest["not_refreshed_artifacts"] = []
        sec_pipeline.write_validation_run_manifest(manifest=manifest)
        return [
            sec_pipeline.validation_row(
                check_id="validation_gate_result",
                status="PASS",
                details="all gates pass",
            )
        ]

    @staticmethod
    def _projected_report(*, validation_manifest: dict) -> str:
        """Return a minimal report bound to one projected terminal run."""
        return (
            f"- run_id: `{validation_manifest['run_id']}`\n"
            f"- result: `{validation_manifest['result']}`\n"
        )

    def test_report_write_failure_cannot_leave_success_manifest(self) -> None:
        """Stage 12 keeps IN_PROGRESS when its report cannot be persisted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            (workspace / "REPORT_十公司财务指标.md").mkdir()
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=self._successful_deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=self._projected_report,
            ):
                with self.assertRaises(IsADirectoryError):
                    sec_pipeline.stage_validate_repair()
                manifest = sec_pipeline.read_validation_run_manifest()
        self.assertEqual(manifest["result"], "IN_PROGRESS")

    def test_report_symlink_cannot_alias_the_manifest(self) -> None:
        """A report alias cannot yield success without a report artifact."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            report_path = workspace / "REPORT_十公司财务指标.md"
            report_path.symlink_to("outputs/validation_run_manifest.json")
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=self._successful_deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=self._projected_report,
            ):
                with self.assertRaises(ValueError):
                    sec_pipeline.stage_validate_repair()
                manifest = sec_pipeline.read_validation_run_manifest()
                report_is_symlink = report_path.is_symlink()
        self.assertEqual(manifest["result"], "IN_PROGRESS")
        self.assertTrue(report_is_symlink)

    def test_manifest_symlink_target_is_rejected(self) -> None:
        """Manifest persistence never follows an artifact alias."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            outputs = workspace / "outputs"
            outputs.mkdir(parents=True)
            report_path = workspace / "REPORT_十公司财务指标.md"
            report_path.write_text("old report\n", encoding="utf-8")
            manifest_path = outputs / "validation_run_manifest.json"
            manifest_path.symlink_to(report_path)
            manifest = validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="IN_PROGRESS",
                refreshed_artifacts=[],
            )
            with patched_workspace(workspace=workspace):
                with self.assertRaises(ValueError):
                    sec_pipeline.write_validation_run_manifest(
                        manifest=manifest,
                    )
            report_text = report_path.read_text(encoding="utf-8")
        self.assertEqual(
            report_text,
            "old report\n",
        )

    def test_report_build_failure_cannot_leave_success_manifest(self) -> None:
        """Stage 12 keeps IN_PROGRESS when report construction raises."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=self._successful_deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=ValueError("injected report build failure"),
            ):
                with self.assertRaises(ValueError):
                    sec_pipeline.stage_validate_repair()
                manifest = sec_pipeline.read_validation_run_manifest()
        self.assertEqual(manifest["result"], "IN_PROGRESS")

    def test_stage11_readme_failure_cannot_leave_success_manifest(
        self,
    ) -> None:
        """Stage 11 keeps IN_PROGRESS until both review documents persist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            (workspace / "README_RUN.md").mkdir()
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "migrate_portable_artifact_inventories",
            ), mock.patch.object(
                sec_pipeline,
                "apply_p0_repairs",
            ), mock.patch.object(
                sec_pipeline,
                "build_coverage_matrix",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "build_companyfacts_crosscheck",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "build_exceptions_markdown",
                return_value="# exceptions\n",
            ), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=self._successful_deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=self._projected_report,
            ), mock.patch.object(
                sec_pipeline,
                "build_readme",
                return_value="# readme\n",
            ):
                with self.assertRaises(IsADirectoryError):
                    sec_pipeline.stage_build_report()
                manifest = sec_pipeline.read_validation_run_manifest()
                report_exists = (
                    workspace / "REPORT_十公司财务指标.md"
                ).is_file()
        self.assertTrue(report_exists)
        self.assertEqual(manifest["result"], "IN_PROGRESS")

    def test_stage11_repair_failure_replaces_old_success_manifest(
        self,
    ) -> None:
        """A partial repair failure must expose the new run as in progress."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            outputs = workspace / "outputs"
            outputs.mkdir(parents=True)
            report_path = workspace / "REPORT_十公司财务指标.md"
            report_path.write_text("old report\n", encoding="utf-8")
            old_manifest = validation_manifest_fixture(
                mode="FULL_VALIDATION",
                result="PASSED",
                refreshed_artifacts=list(
                    sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
                ),
            )

            def partial_repair_then_fail() -> None:
                """Replace one batch artifact before an injected failure."""
                (outputs / "metrics_matrix.csv").write_text(
                    "partially replaced\n",
                    encoding="utf-8",
                )
                raise RuntimeError("injected repair failure")

            with patched_workspace(workspace=workspace):
                sec_pipeline.write_validation_run_manifest(
                    manifest=old_manifest,
                )
                with mock.patch.object(
                    sec_pipeline,
                    "migrate_portable_artifact_inventories",
                ), mock.patch.object(
                    sec_pipeline,
                    "apply_p0_repairs",
                    side_effect=partial_repair_then_fail,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "injected repair failure",
                    ):
                        sec_pipeline.stage_build_report()
                manifest = sec_pipeline.read_validation_run_manifest()
                report = report_path.read_text(encoding="utf-8")
                metric_text = (
                    outputs / "metrics_matrix.csv"
                ).read_text(encoding="utf-8")
        self.assertNotEqual(manifest["run_id"], old_manifest["run_id"])
        self.assertEqual(manifest["result"], "IN_PROGRESS")
        self.assertEqual(report, "old report\n")
        self.assertEqual(metric_text, "partially replaced\n")

    def test_stage11_report_and_manifest_reuse_prestarted_run(self) -> None:
        """Successful stage 11 must publish one run from start to terminal."""
        captured_run_ids = []

        def deferred_validation(
            *,
            exit_on_failure: bool,
            manifest: dict | None = None,
        ) -> list[dict]:
            """Capture and complete the manifest prestarted by stage 11."""
            if exit_on_failure or manifest is None:
                raise AssertionError("stage 11 must pass its deferred run")
            captured_run_ids.append(str(manifest["run_id"]))
            return self._successful_deferred_validation(
                exit_on_failure=exit_on_failure,
                manifest=manifest,
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "migrate_portable_artifact_inventories",
            ), mock.patch.object(
                sec_pipeline,
                "apply_p0_repairs",
            ), mock.patch.object(
                sec_pipeline,
                "build_coverage_matrix",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "build_companyfacts_crosscheck",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "build_exceptions_markdown",
                return_value="# exceptions\n",
            ), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=self._projected_report,
            ), mock.patch.object(
                sec_pipeline,
                "build_readme",
                return_value="# readme\n",
            ):
                sec_pipeline.stage_build_report()
                manifest = sec_pipeline.read_validation_run_manifest()
                report = (
                    workspace / "REPORT_十公司财务指标.md"
                ).read_text(encoding="utf-8")
        self.assertEqual(manifest["result"], "PASSED")
        self.assertEqual(captured_run_ids, [manifest["run_id"]])
        self.assertIn(manifest["run_id"], report)

    def test_report_and_manifest_publish_one_terminal_run(self) -> None:
        """Successful stage 12 report and manifest share one run identity."""
        captured = []

        def report_text(*, validation_manifest: dict) -> str:
            """Capture the projected terminal manifest used by the report."""
            captured.append(dict(validation_manifest))
            return self._projected_report(
                validation_manifest=validation_manifest,
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=self._successful_deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=report_text,
            ):
                sec_pipeline.stage_validate_repair()
                manifest = sec_pipeline.read_validation_run_manifest()
                report_path = workspace / "REPORT_十公司财务指标.md"
                report = report_path.read_text(
                    encoding="utf-8",
                )
        self.assertEqual(manifest["result"], "PASSED")
        self.assertEqual(captured[0]["result"], "PASSED")
        self.assertIn(manifest["run_id"], report)

    def test_workspace_incomplete_manifest_lists_stale_audits(self) -> None:
        """Early failure must list old stratified/scalability files as stale."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            with patched_workspace(workspace=workspace):
                prestarted = sec_pipeline.new_validation_run_manifest(
                    mode="WORKSPACE_INCOMPLETE",
                    started_at_utc=sec_pipeline.utc_now_iso(),
                )
                sec_pipeline.write_validation_run_manifest(
                    manifest=prestarted,
                )
                rows = sec_pipeline.run_repair_validation(
                    exit_on_failure=False,
                    manifest=prestarted,
                )
                manifest = sec_pipeline.read_validation_run_manifest()
        self.assertEqual(rows[0]["status"], "WORKSPACE_INCOMPLETE")
        self.assertEqual(manifest["run_id"], prestarted["run_id"])
        self.assertEqual(manifest["mode"], "WORKSPACE_INCOMPLETE")
        self.assertEqual(manifest["result"], "IN_PROGRESS")
        self.assertEqual(
            manifest["refreshed_artifacts"],
            [
                "implementation_map.csv",
                "spec_implementation_audit.csv",
                "repair_validation_results.csv",
            ],
        )
        self.assertIn("stratified_audit.csv",
                      manifest["not_refreshed_artifacts"])
        self.assertIn("scalability_audit.csv",
                      manifest["not_refreshed_artifacts"])

    def test_full_missing_inputs_short_circuits_dependent_helpers(self) -> None:
        """A full-shaped but incomplete workspace emits no helper PASS rows."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs").mkdir(parents=True)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "validation_package_mode",
                return_value=("FULL_VALIDATION", []),
            ), mock.patch.object(
                sec_pipeline,
                "check_no_placeholder_notes_in_final_metrics",
                side_effect=AssertionError("dependent helper must not run"),
            ):
                rows = sec_pipeline.run_repair_validation(
                    exit_on_failure=False,
                )
                manifest = sec_pipeline.read_validation_run_manifest()
        self.assertEqual(
            [row["check_id"] for row in rows],
            [
                "validation_package_mode",
                "required_validation_inputs_available",
                "validation_gate_result",
            ],
        )
        self.assertEqual(rows[1]["status"], "WORKSPACE_INCOMPLETE")
        self.assertEqual(rows[2]["status"], "FAIL")
        self.assertEqual(manifest["result"], "IN_PROGRESS")
        self.assertIn("stratified_audit.csv",
                      manifest["not_refreshed_artifacts"])


class MissingEvidenceStatusTest(unittest.TestCase):
    """Validate absent claim-level evidence never collapses to PASS."""

    def test_numeric_evidence_requires_complete_matching_identity(
        self,
    ) -> None:
        """A company/metric shell row cannot prove a numeric result."""
        metric = {field: "" for field in sec_pipeline.METRICS_FIELDNAMES}
        metric.update(
            {
                "company": "fixture company",
                "metric_id": "B01",
                "value": "10",
                "unit": "USD",
                "status": "OK",
                "period_end": "2025-12-31",
                "accession": "0000000001-26-000001",
            }
        )
        evidence = {field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES}
        evidence.update(
            {
                "company": metric["company"],
                "metric_id": metric["metric_id"],
            }
        )
        result = sec_pipeline.check_numeric_ok_requires_evidence(
            metrics=[metric],
            evidence_rows=[evidence],
            events=[],
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("fixture company:B01", result["details"])

    def test_numeric_evidence_period_start_must_match(self) -> None:
        """A duration cannot borrow evidence from another start date."""
        metric = {field: "" for field in sec_pipeline.METRICS_FIELDNAMES}
        metric.update(
            {
                "company": "fixture company",
                "metric_id": "B01",
                "value": "10",
                "unit": "USD",
                "status": "OK",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "accession": "0000000001-26-000001",
            }
        )
        evidence = {
            field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES
        }
        evidence.update(
            {
                "company": metric["company"],
                "metric_id": metric["metric_id"],
                "value_normalized": metric["value"],
                "unit": metric["unit"],
                "period_start": "1900-01-01",
                "period_end": metric["period_end"],
                "accession": metric["accession"],
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/sample.xml"
                ),
                "concept_or_section": "Revenue",
                "extraction_method": "fixture",
            }
        )
        result = sec_pipeline.check_numeric_ok_requires_evidence(
            metrics=[metric],
            evidence_rows=[evidence],
            events=[],
        )
        self.assertEqual(result["status"], "FAIL")

    def test_positive_event_metric_requires_exact_component_evidence(
        self,
    ) -> None:
        """A count cannot hide a deleted component or changed accession."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            raw_root = workspace / "evidence" / "events"
            raw_root.mkdir(parents=True)
            events = []
            for index in [1, 2]:
                accession = f"000000000{index}-26-00000{index}"
                raw_path = raw_root / f"event-{index}.hdr.sgml"
                raw_path.write_bytes(f"event {index}".encode("utf-8"))
                source_url = (
                    "https://www.sec.gov/Archives/edgar/data/"
                    f"{index}/{accession.replace('-', '')}/"
                    f"{raw_path.name}"
                )
                event = {
                    "company": "Fixture Company",
                    "cik": str(index),
                    "accession": accession,
                    "filing_date": f"2025-06-0{index}",
                    "item_code": "1.01",
                    "item_source": "hdr.sgml",
                    "mapping_method": "hdr_items",
                    "confidence": "0.90",
                    "brief": f"Fixture agreement {index}",
                    "source_url": source_url,
                    "local_path": str(raw_path),
                }
                with patched_workspace(workspace=workspace):
                    events.append(
                        sec_pipeline.normalize_csv_row(
                            row=event,
                            fieldnames=sec_pipeline.EVENT_FIELDNAMES,
                        )
                    )
            metric = {
                field: "" for field in sec_pipeline.METRICS_FIELDNAMES
            }
            metric.update(
                {
                    "company": "Fixture Company",
                    "metric_id": "E05",
                    "value": "2",
                    "unit": "count",
                    "status": "8K_ITEM_OK",
                    "source_class": "8K_ITEM",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                    "accession": ";".join(
                        event["accession"] for event in events
                    ),
                }
            )
            evidence = []
            for event in events:
                row = {
                    field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES
                }
                row.update(
                    {
                        "company": metric["company"],
                        "cik": event["cik"],
                        "metric_id": metric["metric_id"],
                        "source_url": event["source_url"],
                        "repo_relative_path": event["repo_relative_path"],
                        "content_sha256": event["content_sha256"],
                        "accession": event["accession"],
                        "document_name": event["document_name"],
                        "concept_or_section": "8-K Item 1.01",
                        "context_or_dimension": "FY window",
                        "unit": metric["unit"],
                        "period_start": metric["period_start"],
                        "period_end": metric["period_end"],
                        "value_raw": "1",
                        "value_normalized": metric["value"],
                        "evidence_quote": event["brief"],
                        "extraction_method": "eightk_item",
                        "parser_version": "sec_pipeline_v1",
                    }
                )
                evidence.append(row)
            with mock.patch.object(
                sec_pipeline,
                "event_component_evidence_rows",
                side_effect=AssertionError(
                    "validation must not reuse production builder"
                ),
            ):
                baseline = sec_pipeline.event_metric_evidence_errors(
                    metric=metric,
                    evidence_rows=evidence,
                    events=events,
                )
                deleted_component = sec_pipeline.event_metric_evidence_errors(
                    metric=metric,
                    evidence_rows=evidence[:1],
                    events=events,
                )
                changed_identity = sec_pipeline.event_metric_evidence_errors(
                    metric={**metric, "accession": events[0]["accession"]},
                    evidence_rows=evidence,
                    events=events,
                )
                wrong_source = sec_pipeline.event_metric_evidence_errors(
                    metric=metric,
                    evidence_rows=[
                        {**evidence[0], "source_url": "https://evil.example"},
                        evidence[1],
                    ],
                    events=events,
                )
        self.assertEqual(baseline, [])
        self.assertTrue(deleted_component)
        self.assertIn(
            "metric_accessions_do_not_match_events",
            changed_identity,
        )
        self.assertTrue(wrong_source)

    def test_event_output_gate_binds_all_deterministic_metric_fields(
        self,
    ) -> None:
        """Coordinated metadata tampering cannot preserve an event PASS."""
        company = "Fixture Company"
        accession = "0000000001-25-000020"
        source_url = (
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000020/event.hdr.sgml"
        )
        inventory = [
            {
                "company": company,
                "cik": "1",
                "entity_role": "primary",
                "accession": "0000000001-26-000010",
                "filingDate": "2026-02-01",
                "reportDate": "2025-12-31",
                "source_role": "target_10k",
            },
            {
                "company": company,
                "cik": "1",
                "entity_role": "primary",
                "accession": "0000000001-25-000010",
                "filingDate": "2025-02-01",
                "reportDate": "2024-12-31",
                "source_role": "prior_10k",
            },
            {
                "company": company,
                "cik": "1",
                "accession": accession,
                "filingDate": "2025-06-01",
                "source_role": "fy_8k",
            },
        ]
        event = {field: "" for field in sec_pipeline.EVENT_FIELDNAMES}
        event.update(
            {
                "company": company,
                "cik": "1",
                "accession": accession,
                "filing_date": "2025-06-01",
                "item_code": "1.01",
                "item_source": "hdr.sgml",
                "mapping_method": "hdr_items",
                "confidence": "0.90",
                "brief": "Fixture material agreement",
                "source_url": source_url,
                "repo_relative_path": "evidence/event.hdr.sgml",
                "content_sha256": "a" * 64,
                "document_name": "event.hdr.sgml",
            }
        )
        metric = {field: "" for field in sec_pipeline.METRICS_FIELDNAMES}
        metric.update(
            {
                "company": company,
                "cik": "1",
                "metric_id": "E05",
                "metric_name": "Material agreements",
                "value": "1",
                "unit": "count",
                "status": "8K_ITEM_OK",
                "source_class": "8K_ITEM",
                "formula": "text/event extraction",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "fiscal_year": "",
                "fiscal_period": "FY",
                "accession": accession,
                "form": "",
                "filed_date": "2025-06-01",
                "concept_or_section": "8-K Item 1.01",
                "context_or_dimension": "FY window",
                "confidence": "0.90",
                "notes": "Material agreement event.",
            }
        )
        evidence = {
            field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES
        }
        evidence.update(
            {
                "company": company,
                "cik": "1",
                "metric_id": "E05",
                "source_url": source_url,
                "repo_relative_path": event["repo_relative_path"],
                "content_sha256": event["content_sha256"],
                "accession": accession,
                "document_name": event["document_name"],
                "concept_or_section": "8-K Item 1.01",
                "context_or_dimension": "FY window",
                "unit": "count",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "value_raw": "1",
                "value_normalized": "1",
                "evidence_quote": event["brief"],
                "extraction_method": "eightk_item",
                "parser_version": "sec_pipeline_v1",
            }
        )
        tampered = {
            **metric,
            "cik": "999",
            "metric_name": "WRONG",
            "fiscal_year": "1900",
            "fiscal_period": "Q1",
            "form": "10-Q",
            "filed_date": "1900-01-01",
            "concept_or_section": "WRONG",
            "context_or_dimension": "WRONG",
            "confidence": "0.01",
            "notes": "WRONG",
        }
        with mock.patch.object(
            sec_pipeline,
            "expected_metrics_matrix_keys",
            return_value={(company, "E05")},
        ):
            baseline = sec_pipeline.check_8k_event_outputs_match_events(
                metrics=[metric],
                evidence_rows=[evidence],
                events=[event],
                inventory=inventory,
            )
            changed = sec_pipeline.check_8k_event_outputs_match_events(
                metrics=[tampered],
                evidence_rows=[evidence],
                events=[event],
                inventory=inventory,
            )
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(changed["status"], "FAIL")

    def test_event_metric_derivation_isolates_company_events(self) -> None:
        """One company's matching item must not count a peer's event."""
        def inventory_rows(
            *,
            company: str,
            cik: str,
            accession_prefix: str,
        ) -> list[dict]:
            """Build one company's target, prior, and FY 8-K identities."""
            return [
                {
                    "company": company,
                    "cik": cik,
                    "entity_role": "primary",
                    "accession": f"{accession_prefix}-26-000010",
                    "filingDate": "2026-02-01",
                    "reportDate": "2025-12-31",
                    "source_role": "target_10k",
                },
                {
                    "company": company,
                    "cik": cik,
                    "entity_role": "primary",
                    "accession": f"{accession_prefix}-25-000010",
                    "filingDate": "2025-02-01",
                    "reportDate": "2024-12-31",
                    "source_role": "prior_10k",
                },
                {
                    "company": company,
                    "cik": cik,
                    "entity_role": "primary",
                    "accession": f"{accession_prefix}-25-000020",
                    "filingDate": "2025-06-01",
                    "reportDate": "",
                    "source_role": "fy_8k",
                },
            ]

        def event_row(
            *,
            company: str,
            cik: str,
            accession_prefix: str,
        ) -> dict:
            """Build one matching material-agreement event component."""
            row = {
                field: "" for field in sec_pipeline.EVENT_FIELDNAMES
            }
            accession = f"{accession_prefix}-25-000020"
            row.update(
                {
                    "company": company,
                    "cik": cik,
                    "accession": accession,
                    "filing_date": "2025-06-01",
                    "item_code": "1.01",
                    "confidence": "0.90",
                    "brief": "Fixture material agreement",
                }
            )
            return row

        companies = [
            ("Alpha Company", "1", "0000000001"),
            ("Beta Company", "2", "0000000002"),
        ]
        inventory = [
            row
            for company, cik, prefix in companies
            for row in inventory_rows(
                company=company,
                cik=cik,
                accession_prefix=prefix,
            )
        ]
        events = [
            event_row(
                company=company,
                cik=cik,
                accession_prefix=prefix,
            )
            for company, cik, prefix in companies
        ]

        # Equal item codes across companies expose accidental global counting;
        # each expected row must retain exactly one local contribution.
        for company, _cik, prefix in companies:
            metric = sec_pipeline.expected_event_metric_row(
                company=company,
                metric_id="E05",
                events=events,
                inventory=inventory,
            )
            self.assertEqual(metric["value"], "1")
            self.assertEqual(
                metric["accession"],
                f"{prefix}-25-000020",
            )

    def test_event_output_gate_fails_when_target_filing_is_missing(
        self,
    ) -> None:
        """Missing target inventory must return FAIL instead of crashing."""
        company = "Fixture Company"
        metric = {
            field: "" for field in sec_pipeline.METRICS_FIELDNAMES
        }
        metric.update({"company": company, "metric_id": "E05"})
        with mock.patch.object(
            sec_pipeline,
            "expected_metrics_matrix_keys",
            return_value={(company, "E05")},
        ):
            result = sec_pipeline.check_8k_event_outputs_match_events(
                metrics=[metric],
                evidence_rows=[],
                events=[],
                inventory=[],
            )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("expected_metric_invalid", result["details"])

    def test_zero_event_metric_requires_complete_scan_evidence(self) -> None:
        """A zero is valid only when the complete scan has no matching item."""
        company = "Fixture Company"
        accession = "0000000001-26-000001"
        source_url = (
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000126000001/event.hdr.sgml"
        )
        inventory = [
            {
                "company": company,
                "cik": "1",
                "entity_role": "primary",
                "accession": "0000000001-26-000010",
                "filingDate": "2026-02-01",
                "reportDate": "2025-12-31",
                "source_role": "target_10k",
            },
            {
                "company": company,
                "cik": "1",
                "entity_role": "primary",
                "accession": "0000000001-25-000010",
                "filingDate": "2025-02-01",
                "reportDate": "2024-12-31",
                "source_role": "prior_10k",
            },
            {
                "company": company,
                "cik": "1",
                "accession": accession,
                "filingDate": "2025-06-01",
                "source_role": "fy_8k",
            }
        ]
        event = {field: "" for field in sec_pipeline.EVENT_FIELDNAMES}
        event.update(
            {
                "company": company,
                "cik": "1",
                "accession": accession,
                "filing_date": "2025-06-01",
                "item_code": "5.02",
                "source_url": source_url,
                "repo_relative_path": "evidence/event.hdr.sgml",
                "content_sha256": "a" * 64,
                "document_name": "event.hdr.sgml",
                "confidence": "0.90",
                "brief": "Fixture leadership event",
            }
        )
        events = [event]
        metric = {
            field: "" for field in sec_pipeline.METRICS_FIELDNAMES
        }
        metric.update(
            {
                "company": company,
                "cik": "1",
                "metric_id": "E05",
                "metric_name": "Material agreements",
                "value": "0",
                "unit": "count",
                "status": "NOT_AVAILABLE_SEC",
                "source_class": "8K_ITEM",
                "formula": "text/event extraction",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "fiscal_year": "",
                "fiscal_period": "FY",
                "accession": accession,
                "form": "",
                "filed_date": "2025-06-01",
                "concept_or_section": "8-K Item 1.01",
                "context_or_dimension": "FY-window 8-K accessions scanned",
                "confidence": "0.80",
                "notes": "FY-window 8-K scanned; no item 1.01 found.",
            }
        )
        evidence = {
            field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES
        }
        evidence.update(
            {
                "company": company,
                "cik": "1",
                "metric_id": "E05",
                "source_url": source_url,
                "repo_relative_path": "outputs/events.csv",
                "accession": accession,
                "document_name": "events.csv",
                "concept_or_section": "8-K Item 1.01",
                "context_or_dimension": (
                    "FY-window 8-K accessions scanned"
                ),
                "unit": "count",
                "period_start": metric["period_start"],
                "period_end": metric["period_end"],
                "value_raw": "0",
                "value_normalized": "0",
                "evidence_quote": (
                    "FY-window 8-K scanned; no item 1.01 found."
                ),
                "extraction_method": "eightk_zero_item_scan",
                "parser_version": "sec_pipeline_v1",
            }
        )
        expected_keys = {(company, "E05")}
        with mock.patch.object(
            sec_pipeline,
            "expected_metrics_matrix_keys",
            return_value=expected_keys,
        ):
            baseline = sec_pipeline.check_8k_event_outputs_match_events(
                metrics=[metric],
                evidence_rows=[evidence],
                events=events,
                inventory=inventory,
            )
            missing_scan = sec_pipeline.check_8k_event_outputs_match_events(
                metrics=[metric],
                evidence_rows=[],
                events=events,
                inventory=inventory,
            )
            hidden_match = sec_pipeline.check_8k_event_outputs_match_events(
                metrics=[metric],
                evidence_rows=[evidence],
                events=[{**events[0], "item_code": "1.01"}],
                inventory=inventory,
            )
            coordinated_wrong_period = (
                sec_pipeline.check_8k_event_outputs_match_events(
                    metrics=[{**metric, "period_start": "2020-01-01"}],
                    evidence_rows=[
                        {**evidence, "period_start": "2020-01-01"}
                    ],
                    events=events,
                    inventory=inventory,
                )
            )
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(missing_scan["status"], "FAIL")
        self.assertEqual(hidden_match["status"], "FAIL")
        self.assertEqual(coordinated_wrong_period["status"], "FAIL")

    def test_missing_golden_fixture_is_not_evaluated(self) -> None:
        """An absent fixture cannot prove JPM manual exclusions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()
            with patched_workspace(workspace=workspace):
                check = getattr(
                    sec_pipeline,
                    "check_jpm_table_values_not_added_to_golden_until_"
                    "manual_confirmation",
                )
                row = check()
        self.assertEqual(row["status"], "NOT_EVALUATED_MISSING_EVIDENCE")

    def test_empty_metrics_cannot_pass_placeholder_check(self) -> None:
        """No metric rows means the placeholder scan was not evaluated."""
        row = sec_pipeline.check_no_placeholder_notes_in_final_metrics(
            metrics=[],
        )
        self.assertEqual(row["status"], "NOT_EVALUATED_MISSING_EVIDENCE")

    def test_dim_xbrl_rpo_claim_requires_matching_instance_fact(self) -> None:
        """Removing only the supporting RPO facts must fail the B12 claim."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            (workspace / "outputs" / "concept_inventory").mkdir(parents=True)
            shutil.copytree(src=REPO_ROOT / "config", dst=workspace / "config")
            shutil.copy(
                src=REPO_ROOT / "outputs" / "latest_filings_inventory.csv",
                dst=workspace / "outputs" / "latest_filings_inventory.csv",
            )
            instance_path = (
                workspace
                / "outputs"
                / "concept_inventory"
                / "salesforce_instance.csv"
            )
            shutil.copy(
                src=(
                    REPO_ROOT
                    / "outputs"
                    / "concept_inventory"
                    / "salesforce_instance.csv"
                ),
                dst=instance_path,
            )
            instance_rows = read_rows(path=instance_path)
            filtered_rows = [
                row
                for row in instance_rows
                if not sec_pipeline.concept_matches_rpo(concept=row["concept"])
            ]
            removed_count = len(instance_rows) - len(filtered_rows)
            if removed_count == 0:
                raise AssertionError("Expected Salesforce RPO instance facts")
            write_rows(
                path=instance_path,
                fieldnames=list(instance_rows[0]),
                rows=filtered_rows,
            )
            metrics = read_rows(
                path=REPO_ROOT / "outputs" / "metrics_matrix.csv",
            )
            evidence_rows = read_rows(
                path=REPO_ROOT / "outputs" / "metric_evidence.csv",
            )
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_rpo_crpo_prefers_instance_fact(
                    metrics=metrics,
                    evidence_rows=evidence_rows,
                )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("claimed_dim_xbrl_without_instance_fact",
                      result["details"])


class PortableArtifactPathTest(unittest.TestCase):
    """Validate saved artifact locators survive a clone-root change."""

    def test_migration_does_not_bless_changed_evidence_bytes(self) -> None:
        """A recorded hash must survive migration and expose later tampering."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact = (
                workspace
                / "evidence"
                / "accession_materials"
                / "portable_fixture_1_000000000126000001"
                / "sample.xml"
            )
            inventory = (
                workspace / "outputs" / "accession_materials_inventory.csv"
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"original")
            with patched_workspace(workspace=workspace):
                sec_pipeline.write_csv_file(
                    path=inventory,
                    fieldnames=sec_pipeline.MATERIAL_FIELDNAMES,
                    rows=[
                        {
                            "company": "portable fixture",
                            "cik": "1",
                            "entity_role": "primary",
                            "form": "10-K",
                            "accession": "0000000001-26-000001",
                            "document_name": artifact.name,
                            "document_type": "xbrl_instance",
                            "source_url": (
                                "https://www.sec.gov/Archives/edgar/data/1/"
                                "000000000126000001/sample.xml"
                            ),
                            "local_path": str(artifact),
                            "status_code": "200",
                            "content_length": str(artifact.stat().st_size),
                        }
                    ],
                )
                original_row = sec_pipeline.read_csv_file(path=inventory)[0]
                original_hash = original_row["content_sha256"]
                original_resolution = sec_pipeline.resolve_artifact_path(
                    row=original_row
                )
                artifact.write_bytes(b"tampered")
                sec_pipeline.write_csv_file(
                    path=inventory,
                    fieldnames=sec_pipeline.MATERIAL_FIELDNAMES,
                    rows=[original_row],
                )
                migrated_row = sec_pipeline.read_csv_file(path=inventory)[0]
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=migrated_row)
                tampered_hash = sec_pipeline.file_sha256(
                    path_text=str(artifact)
                )
        self.assertEqual(original_resolution, artifact)
        self.assertEqual(migrated_row["content_sha256"], original_hash)
        self.assertNotEqual(tampered_hash, original_hash)

    def test_hash_cache_detects_same_size_rewrite_with_restored_mtime(
        self,
    ) -> None:
        """Restoring mtime must not make changed bytes reuse a cached hash."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "artifact.bin"
            path.write_bytes(b"original")
            original_stat = path.stat()
            first_hash = sec_pipeline.file_sha256(path_text=str(path))
            path.write_bytes(b"tampered")
            os.utime(
                path,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
            second_hash = sec_pipeline.file_sha256(path_text=str(path))
        self.assertNotEqual(first_hash, second_hash)

    def test_locator_rejects_non_sec_and_misaligned_accession(self) -> None:
        """Portable identity requires official SEC URLs and matching accession."""
        base_row = {
            "repo_relative_path": "evidence/sample.xml",
            "content_sha256": "0" * 64,
            "document_name": "sample.xml",
            "accession": "0000000001-26-000001",
        }
        non_sec_errors = sec_pipeline.locator_component_alignment_errors(
            row={
                **base_row,
                "source_url": "https://third-party.example/sample.xml",
            },
        )
        mismatch_errors = sec_pipeline.locator_component_alignment_errors(
            row={
                **base_row,
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000002/sample.xml"
                ),
            },
        )
        self.assertIn("source_url[0]=non_sec", non_sec_errors)
        self.assertIn("source_url[0]=accession_mismatch", mismatch_errors)

    def test_locator_document_name_must_match_portable_path(self) -> None:
        """Direct-path success cannot hide a broken clone fallback name."""
        errors = sec_pipeline.locator_component_alignment_errors(
            row={
                "repo_relative_path": "evidence/actual.xml",
                "content_sha256": "0" * 64,
                "document_name": "wrong.xml",
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/actual.xml"
                ),
                "accession": "0000000001-26-000001",
            },
        )
        self.assertIn("document_name[0]=path_mismatch", errors)

    def test_locator_document_name_must_match_source_url(self) -> None:
        """A jointly re-signed wrong SEC URL must not retain valid bytes."""
        errors = sec_pipeline.locator_component_alignment_errors(
            row={
                "repo_relative_path": "evidence/sample.xml",
                "content_sha256": "0" * 64,
                "document_name": "sample.xml",
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/other.xml"
                ),
                "accession": "0000000001-26-000001",
            },
        )
        self.assertIn("source_url[0]=document_name_mismatch", errors)

    def test_resolver_rejects_cross_accession_same_name_and_hash(self) -> None:
        """Relocation must not borrow identical bytes from another filing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            other_path = (
                workspace
                / "evidence"
                / "accession_materials"
                / "other_2_000000000226000002"
                / "same.xml"
            )
            other_path.parent.mkdir(parents=True)
            other_path.write_bytes(b"same bytes")
            row = {
                "repo_relative_path": (
                    "evidence/accession_materials/declared_1_"
                    "000000000126000001/same.xml"
                ),
                "content_sha256": hashlib.sha256(b"same bytes").hexdigest(),
                "document_name": "same.xml",
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/same.xml"
                ),
                "accession": "0000000001-26-000001",
            }
            with patched_workspace(workspace=workspace):
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=row)

    def test_archive_url_cik_must_match_row_and_filing_directory(self) -> None:
        """Archives CIK cannot drift while accession and bytes stay valid."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact = (
                workspace
                / "evidence"
                / "accession_materials"
                / "fixture_1048286_000104828626000007"
                / "same.xml"
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"same bytes")
            row = {
                "cik": "1048286",
                "repo_relative_path": str(artifact.relative_to(workspace)),
                "content_sha256": hashlib.sha256(b"same bytes").hexdigest(),
                "document_name": "same.xml",
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1048286/"
                    "000104828626000007/same.xml"
                ),
                "accession": "0001048286-26-000007",
            }
            wrong_row = {
                **row,
                "source_url": row["source_url"].replace(
                    "/data/1048286/",
                    "/data/1/",
                ),
            }
            unsupported_row = {
                **row,
                "source_url": "https://www.sec.gov/files/same.xml",
            }
            disguised_row = {
                **row,
                "source_url": (
                    "https://www.sec.gov/files/Archives/edgar/data/1048286/"
                    "000104828626000007/same.xml"
                ),
            }
            non_sec_row = {
                **row,
                "source_url": row["source_url"].replace(
                    "https://www.sec.gov",
                    "https://example.com",
                ),
            }
            with patched_workspace(workspace=workspace):
                correct_errors = (
                    sec_pipeline.locator_component_alignment_errors(row=row)
                )
                resolved = sec_pipeline.resolve_artifact_path(row=row)
                wrong_errors = (
                    sec_pipeline.locator_component_alignment_errors(
                        row=wrong_row,
                    )
                )
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=wrong_row)
                unsupported_errors = (
                    sec_pipeline.locator_component_alignment_errors(
                        row=unsupported_row,
                    )
                )
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=unsupported_row)
                disguised_errors = (
                    sec_pipeline.locator_component_alignment_errors(
                        row=disguised_row,
                    )
                )
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=disguised_row)
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=non_sec_row)
        self.assertEqual(correct_errors, [])
        self.assertEqual(resolved, artifact)
        self.assertIn("source_url[0]=cik_mismatch", wrong_errors)
        self.assertIn(
            "source_url[0]=unsupported_source_type",
            unsupported_errors,
        )
        self.assertIn(
            "source_url[0]=unsupported_source_type",
            disguised_errors,
        )

    def test_companyfacts_accession_must_exist_in_component_provenance(
        self,
    ) -> None:
        """Companyfacts identity includes CIK and selected fact provenance."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact = (
                workspace
                / "evidence"
                / "companyfacts"
                / "CIK0000000001.json"
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                json.dumps(
                    {
                        "cik": 1,
                        "facts": {
                            "us-gaap": {
                                "Revenue": {
                                    "units": {
                                        "USD": [
                                            {
                                                "start": "2025-01-01",
                                                "end": "2025-12-31",
                                                "val": 100,
                                                "accn": (
                                                    "0000000001-26-000001"
                                                ),
                                                "frame": "CY2025",
                                            }
                                        ]
                                    }
                                },
                                "Assets": {
                                    "units": {
                                        "USD": [
                                            {
                                                "end": "2025-12-31",
                                                "val": 200,
                                                "accn": (
                                                    "0000000001-26-000002"
                                                ),
                                            }
                                        ]
                                    }
                                },
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            row = {
                "cik": "1",
                "repo_relative_path": (
                    "evidence/companyfacts/CIK0000000001.json;"
                    "evidence/companyfacts/CIK0000000001.json"
                ),
                "content_sha256": ";".join(
                    [hashlib.sha256(artifact.read_bytes()).hexdigest()] * 2
                ),
                "document_name": (
                    "CIK0000000001.json;CIK0000000001.json"
                ),
                "source_url": (
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0000000001.json;"
                    "https://data.sec.gov/api/xbrl/companyfacts/"
                    "CIK0000000001.json"
                ),
                "accession": (
                    "0000000001-26-000001;0000000001-26-000002"
                ),
                "concept_or_section": "Revenue+Assets",
                "context_or_dimension": (
                    "companyfacts:USD:CY2025;companyfacts:USD:"
                ),
                "period_start": "",
                "period_end": "2025-12-31",
                "value_raw": "100;200",
            }
            wrong_accession = {
                **row,
                "accession": (
                    "0000000001-26-000001;0000000001-26-000003"
                ),
            }
            locator_path = workspace / "outputs" / "metric_evidence.csv"
            locator_path.parent.mkdir(parents=True)
            correct_csv_row = {
                field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES
            }
            correct_csv_row.update(row)
            wrong_csv_row = dict(correct_csv_row)
            wrong_csv_row["accession"] = wrong_accession["accession"]
            with patched_workspace(workspace=workspace):
                correct_errors = (
                    sec_pipeline.locator_component_alignment_errors(row=row)
                )
                resolved = sec_pipeline.resolve_artifact_paths(row=row)
                wrong_errors = (
                    sec_pipeline.locator_component_alignment_errors(
                        row=wrong_accession,
                    )
                )
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_paths(row=wrong_accession)
                with mock.patch.object(
                    sec_pipeline,
                    "portable_locator_artifact_specs",
                    return_value=[
                        (locator_path, sec_pipeline.EVIDENCE_FIELDNAMES)
                    ],
                ):
                    write_rows(
                        path=locator_path,
                        fieldnames=sec_pipeline.EVIDENCE_FIELDNAMES,
                        rows=[correct_csv_row],
                    )
                    correct_gate = (
                        sec_pipeline.check_portable_artifact_locators(
                            mode="FULL_VALIDATION",
                        )
                    )
                    write_rows(
                        path=locator_path,
                        fieldnames=sec_pipeline.EVIDENCE_FIELDNAMES,
                        rows=[wrong_csv_row],
                    )
                    wrong_gate = (
                        sec_pipeline.check_portable_artifact_locators(
                            mode="FULL_VALIDATION",
                        )
                    )
        self.assertEqual(correct_errors, [])
        self.assertEqual(resolved, [artifact, artifact])
        self.assertEqual(correct_gate["status"], "PASS")
        self.assertEqual(wrong_gate["status"], "FAIL")
        self.assertIn(
            "source_url[1]=companyfacts_identity_mismatch",
            wrong_errors,
        )

    def test_raw_locator_cannot_claim_aggregate_count_exception(self) -> None:
        """Multiple identities cannot disguise one raw filing as aggregate."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact = (
                workspace
                / "evidence"
                / "accession_materials"
                / "fixture_1_000000000126000001"
                / "same.xml"
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"same bytes")
            row = {
                "repo_relative_path": str(artifact.relative_to(workspace)),
                "content_sha256": hashlib.sha256(b"same bytes").hexdigest(),
                "document_name": "same.xml",
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/same.xml;"
                    "https://www.sec.gov/Archives/edgar/data/2/"
                    "000000000226000002/same.xml"
                ),
                "accession": (
                    "0000000001-26-000001;0000000002-26-000002"
                ),
                "extraction_method": "eightk_zero_item_scan",
            }
            with patched_workspace(workspace=workspace):
                errors = sec_pipeline.locator_component_alignment_errors(
                    row=row,
                )
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=row)
        self.assertIn(
            "source_url=2,repo_relative_path=1",
            errors,
        )
        self.assertIn(
            "accession=2,repo_relative_path=1",
            errors,
        )

    def test_single_source_derived_aggregate_uses_declared_type(self) -> None:
        """One-source event scans remain derived rather than scalar raw."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact = workspace / "outputs" / "events.csv"
            artifact.parent.mkdir(parents=True)
            accession = "0000000001-26-000001"
            source_url = (
                "https://www.sec.gov/Archives/edgar/data/1/"
                "000000000126000001/source.hdr.sgml"
            )
            event_row = {
                field: "" for field in sec_pipeline.EVENT_FIELDNAMES
            }
            event_row.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "source_url": source_url,
                    "accession": accession,
                    "item_code": "1.01",
                }
            )
            write_rows(
                path=artifact,
                fieldnames=sec_pipeline.EVENT_FIELDNAMES,
                rows=[event_row],
            )
            inventory_row = {
                field: "" for field in sec_pipeline.FILING_FIELDNAMES
            }
            inventory_row.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "accession": accession,
                    "source_role": "fy_8k",
                }
            )
            write_rows(
                path=workspace / "outputs" / "latest_filings_inventory.csv",
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=[inventory_row],
            )
            row = {
                "company": "Fixture Company",
                "repo_relative_path": "outputs/events.csv",
                "content_sha256": hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest(),
                "document_name": "events.csv",
                "source_url": source_url,
                "accession": accession,
                "extraction_method": "eightk_zero_item_scan",
            }
            with patched_workspace(workspace=workspace):
                errors = sec_pipeline.locator_component_alignment_errors(
                    row=row,
                )
                resolved = sec_pipeline.resolve_artifact_path(row=row)
        self.assertEqual(errors, [])
        self.assertEqual(resolved, artifact)

    def test_event_aggregate_requires_exact_unique_scan_pairs(self) -> None:
        """An internally valid fake Archives pair cannot replace scan input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact = workspace / "outputs" / "events.csv"
            artifact.parent.mkdir(parents=True)
            pairs = [
                (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/a.hdr.sgml",
                    "0000000001-26-000001",
                ),
                (
                    "https://www.sec.gov/Archives/edgar/data/2/"
                    "000000000226000002/b.hdr.sgml",
                    "0000000002-26-000002",
                ),
            ]
            event_rows = []
            inventory_rows = []
            for index, (source_url, accession) in enumerate(pairs, start=1):
                event_row = {
                    field: "" for field in sec_pipeline.EVENT_FIELDNAMES
                }
                event_row.update(
                    {
                        "company": "Fixture Company",
                        "cik": str(index),
                        "source_url": source_url,
                        "accession": accession,
                        "item_code": f"{index}.01",
                    }
                )
                event_rows.append(event_row)
                inventory_row = {
                    field: "" for field in sec_pipeline.FILING_FIELDNAMES
                }
                inventory_row.update(
                    {
                        "company": "Fixture Company",
                        "cik": str(index),
                        "accession": accession,
                        "source_role": "fy_8k",
                    }
                )
                inventory_rows.append(inventory_row)
            write_rows(
                path=artifact,
                fieldnames=sec_pipeline.EVENT_FIELDNAMES,
                rows=event_rows,
            )
            write_rows(
                path=workspace / "outputs" / "latest_filings_inventory.csv",
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=inventory_rows,
            )
            row = {
                "company": "Fixture Company",
                "repo_relative_path": "outputs/events.csv",
                "content_sha256": hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest(),
                "document_name": "events.csv",
                "source_url": ";".join(pair[0] for pair in pairs),
                "accession": ";".join(pair[1] for pair in pairs),
                "extraction_method": "eightk_zero_item_scan",
            }
            wrong_row = {
                **row,
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/3/"
                    "000000000326000003/fake.hdr.sgml;"
                    + pairs[1][0]
                ),
                "accession": "0000000003-26-000003;" + pairs[1][1],
            }
            with patched_workspace(workspace=workspace):
                correct_errors = (
                    sec_pipeline.locator_component_alignment_errors(row=row)
                )
                resolved = sec_pipeline.resolve_artifact_path(row=row)
                wrong_errors = (
                    sec_pipeline.locator_component_alignment_errors(
                        row=wrong_row,
                    )
                )
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.resolve_artifact_path(row=wrong_row)
        self.assertEqual(correct_errors, [])
        self.assertEqual(resolved, artifact)
        self.assertIn("source_url=events_exact_set_mismatch", wrong_errors)

    def test_event_chain_replay_rejects_deleted_filing_or_event_rows(
        self,
    ) -> None:
        """Saved submissions and raw filings independently expose shrinkage."""
        required_paths = [
            REPO_ROOT / "outputs" / "latest_filings_inventory.csv",
            REPO_ROOT / "outputs" / "events.csv",
            REPO_ROOT / "evidence" / "submissions",
        ]
        if any(not path.exists() for path in required_paths):
            self.skipTest("full submissions and raw 8-K evidence unavailable")
        inventory = read_rows(
            path=REPO_ROOT / "outputs" / "latest_filings_inventory.csv"
        )
        events = read_rows(path=REPO_ROOT / "outputs" / "events.csv")
        baseline = sec_pipeline.check_8k_event_chain_exact_set(
            inventory=inventory,
            events=events,
        )
        if baseline["status"] == "NOT_EVALUATED_MISSING_EVIDENCE":
            self.fail(
                "Full checkout lost required 8-K replay evidence: "
                + baseline["details"]
            )
        accession = events[0]["accession"]
        missing_event = sec_pipeline.check_8k_event_chain_exact_set(
            inventory=inventory,
            events=[row for row in events if row["accession"] != accession],
        )
        missing_inventory = sec_pipeline.check_8k_event_chain_exact_set(
            inventory=[
                row
                for row in inventory
                if row["accession"] != accession
            ],
            events=events,
        )
        prior = next(
            row for row in inventory if row["source_role"] == "prior_10k"
        )
        wrong_period_inventory = [
            {
                **row,
                "reportDate": "2020-12-31",
            }
            if row["company"] == prior["company"]
            and row["cik"] == prior["cik"]
            and row["source_role"] == "prior_10k"
            else row
            for row in inventory
        ]
        wrong_period = sec_pipeline.check_8k_event_chain_exact_set(
            inventory=wrong_period_inventory,
            events=events,
        )
        duplicate_item = sec_pipeline.check_8k_event_chain_exact_set(
            inventory=inventory,
            events=[*events, dict(events[0])],
        )
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(missing_event["status"], "FAIL")
        self.assertEqual(missing_inventory["status"], "FAIL")
        self.assertEqual(wrong_period["status"], "FAIL")
        self.assertEqual(duplicate_item["status"], "FAIL")
        self.assertIn("duplicate_item", duplicate_item["details"])

    def test_event_chain_binds_submissions_bytes_to_request_ledger(
        self,
    ) -> None:
        """Synchronized downstream shrinkage cannot re-sign working JSON."""
        def filing_row(
            *,
            accession: str,
            form: str,
            filing_date: str,
            report_date: str,
            document_name: str,
        ) -> dict:
            """Build one complete SEC recent filing fixture row."""
            row = {
                field: ""
                for field in [
                    "accessionNumber",
                    "filingDate",
                    "reportDate",
                    "acceptanceDateTime",
                    "act",
                    "form",
                    "fileNumber",
                    "filmNumber",
                    "items",
                    "size",
                    "isXBRL",
                    "isInlineXBRL",
                    "primaryDocument",
                    "primaryDocDescription",
                ]
            }
            row.update(
                {
                    "accessionNumber": accession,
                    "filingDate": filing_date,
                    "reportDate": report_date,
                    "form": form,
                    "items": "1.01" if form == "8-K" else "",
                    "size": 100,
                    "isXBRL": 0,
                    "isInlineXBRL": 0,
                    "primaryDocument": document_name,
                }
            )
            return row

        def filing_block(*, rows: list[dict]) -> dict:
            """Convert row fixtures into SEC parallel-array shape."""
            return {
                field: [row[field] for row in rows]
                for field in rows[0]
            }

        def request_row(*, path: Path, source_url: str) -> dict:
            """Build a successful observation for the current body bytes."""
            body = path.read_bytes()
            return {
                "timestamp_utc": "2026-07-23T00:00:00+00:00",
                "method": "GET",
                "source_url": source_url,
                "status_code": "200",
                "purpose": "submission fixture",
                "repo_relative_path": str(path.relative_to(workspace)),
                "headers_repo_relative_path": "",
                "content_length": str(len(body)),
                "content_sha256": hashlib.sha256(body).hexdigest(),
                "accession": "",
                "document_name": path.name,
                "user_agent": "fixture fixture@example.com",
                "retry_attempt": "0",
                "error": "",
            }

        def event_row(*, filing: dict) -> dict:
            """Build the single expected item component for one 8-K."""
            row = {
                field: "" for field in sec_pipeline.EVENT_FIELDNAMES
            }
            row.update(
                {
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "accession": filing["accession"],
                    "filing_date": filing["filingDate"],
                    "item_code": "1.01",
                    "item_source": "hdr.sgml",
                    "mapping_method": "hdr_items",
                    "confidence": "0.90",
                    "brief": "fixture item",
                    "source_url": (
                        "https://www.sec.gov/Archives/edgar/data/1/"
                        f"{filing['accession'].replace('-', '')}/"
                        f"{filing['accession']}.hdr.sgml"
                    ),
                    "repo_relative_path": (
                        "evidence/fixture/" + filing["accession"]
                    ),
                    "content_sha256": "a" * 64,
                    "document_name": f"{filing['accession']}.hdr.sgml",
                }
            )
            return row

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            submissions_dir = workspace / "evidence" / "submissions"
            submissions_dir.mkdir(parents=True)
            base_path = submissions_dir / "CIK0000000001.json"
            supplemental_name = "CIK0000000001-submissions-001.json"
            supplemental_path = submissions_dir / supplemental_name
            target = filing_row(
                accession="0000000001-26-000010",
                form="10-K",
                filing_date="2026-02-01",
                report_date="2025-12-31",
                document_name="annual.htm",
            )
            prior = filing_row(
                accession="0000000001-25-000010",
                form="10-K",
                filing_date="2025-02-01",
                report_date="2024-12-31",
                document_name="annual.htm",
            )
            base_event = filing_row(
                accession="0000000001-25-000020",
                form="8-K",
                filing_date="2025-06-01",
                report_date="2025-06-01",
                document_name="base.htm",
            )
            supplemental_event = filing_row(
                accession="0000000001-25-000021",
                form="8-K",
                filing_date="2025-07-01",
                report_date="2025-07-01",
                document_name="supplemental.htm",
            )
            base_payload = {
                "filings": {
                    "recent": filing_block(
                        rows=[target, prior, base_event]
                    ),
                    "files": [{"name": supplemental_name}],
                }
            }
            supplemental_payload = filing_block(
                rows=[supplemental_event]
            )
            base_bytes = json.dumps(base_payload).encode("utf-8")
            supplemental_bytes = json.dumps(
                supplemental_payload
            ).encode("utf-8")
            older_payload = {
                "filings": {
                    "recent": filing_block(rows=[target, prior]),
                    "files": [{"name": supplemental_name}],
                }
            }
            older_bytes = json.dumps(older_payload).encode("utf-8")
            base_path.write_bytes(older_bytes)
            older_request = request_row(
                path=base_path,
                source_url=(
                    "https://data.sec.gov/submissions/"
                    "CIK0000000001.json"
                ),
            )
            base_path.write_bytes(base_bytes)
            supplemental_path.write_bytes(supplemental_bytes)
            log_path = workspace / "evidence" / "requests_log.csv"
            request_rows = [
                older_request,
                request_row(
                    path=base_path,
                    source_url=(
                        "https://data.sec.gov/submissions/"
                        "CIK0000000001.json"
                    ),
                ),
                request_row(
                    path=supplemental_path,
                    source_url=(
                        "https://data.sec.gov/submissions/"
                        f"{supplemental_name}"
                    ),
                ),
            ]
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=request_rows,
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            role_rows = [
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "entity_role": "primary",
                }
            ]
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "all_role_rows",
                return_value=role_rows,
            ):
                observations = (
                    sec_pipeline.request_observation_identities()
                )
                inventory = sec_pipeline.expected_8k_window_inventory_rows(
                    observation_identities=observations,
                )
                expected_events = [
                    event_row(filing=row)
                    for row in inventory
                    if row["source_role"] == "fy_8k"
                ]
                with mock.patch.object(
                    sec_pipeline,
                    "expected_8k_event_rows",
                    return_value=expected_events,
                ):
                    baseline = sec_pipeline.check_8k_event_chain_exact_set(
                        inventory=inventory,
                        events=expected_events,
                    )
                    # A prior successful snapshot is still stale once a later
                    # 200 establishes the current submissions collection.
                    base_path.write_bytes(older_bytes)
                    shrunk_inventory = [
                        row
                        for row in inventory
                        if row["accession"] != base_event["accessionNumber"]
                    ]
                    shrunk_events = [
                        row
                        for row in expected_events
                        if row["accession"] != base_event["accessionNumber"]
                    ]
                    changed_base = (
                        sec_pipeline.check_8k_event_chain_exact_set(
                            inventory=shrunk_inventory,
                            events=shrunk_events,
                        )
                    )
                    base_path.write_bytes(base_bytes)
                    supplemental_path.unlink()
                    without_supplement_inventory = [
                        row
                        for row in inventory
                        if row["accession"]
                        != supplemental_event["accessionNumber"]
                    ]
                    without_supplement_events = [
                        row
                        for row in expected_events
                        if row["accession"]
                        != supplemental_event["accessionNumber"]
                    ]
                    missing_supplement = (
                        sec_pipeline.check_8k_event_chain_exact_set(
                            inventory=without_supplement_inventory,
                            events=without_supplement_events,
                        )
                    )
                    changed_supplemental = {
                        **supplemental_payload,
                        "form": ["10-Q"],
                    }
                    changed_bytes = json.dumps(
                        changed_supplemental
                    ).encode("utf-8")
                    supplemental_path.write_bytes(changed_bytes)
                    supplemental_path.with_suffix(
                        ".json.headers.json"
                    ).write_text(
                        json.dumps(
                            {
                                "url": request_rows[1]["source_url"],
                                "status_code": 200,
                                "content_length": len(changed_bytes),
                                "sha256": hashlib.sha256(
                                    changed_bytes
                                ).hexdigest(),
                            }
                        ),
                        encoding="utf-8",
                    )
                    changed_supplement = (
                        sec_pipeline.check_8k_event_chain_exact_set(
                            inventory=without_supplement_inventory,
                            events=without_supplement_events,
                        )
                    )
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(changed_base["status"], "FAIL")
        self.assertIn(
            "latest successful observation",
            changed_base["details"],
        )
        self.assertEqual(
            missing_supplement["status"],
            "NOT_EVALUATED_MISSING_EVIDENCE",
        )
        self.assertEqual(changed_supplement["status"], "FAIL")
        self.assertIn(
            "lack a matching request",
            changed_supplement["details"],
        )

    def test_supplemental_submission_names_fail_fast(self) -> None:
        """Null, traversal, whitespace, and wrong-CIK names are invalid."""
        invalid_values = [
            None,
            "..",
            " CIK0000000001-submissions-001.json",
            "CIK0000000002-submissions-001.json",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                expected_error = TypeError if value is None else ValueError
                with self.assertRaises(expected_error):
                    sec_pipeline.submission_supplemental_names(
                        submission={
                            "filings": {"files": [{"name": value}]}
                        },
                        cik=1,
                    )

    def test_event_parser_preserves_declared_item_multisets(self) -> None:
        """Supported hdr and primary forms must retain every unique item."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            raw_dir = workspace / "evidence" / "fixture"
            raw_dir.mkdir(parents=True)
            filing = {
                "company": "Fixture Company",
                "cik": "1",
                "accession": "0000000001-26-000001",
                "filingDate": "2025-06-01",
            }
            hdr_path = raw_dir / "fixture.hdr.sgml"
            hdr_path.write_text(
                "<ITEMS>1.01\n<ITEMS>2.03\n"
                "<ITEMS>5.02\n<ITEMS>1.01\n",
                encoding="utf-8",
            )
            primary_path = raw_dir / "fixture.htm"
            primary_path.write_text(
                "<html><body>Item 1.01 Agreement. Item 5.02 "
                "Leadership. Item 1.01 Repeated.</body></html>",
                encoding="utf-8",
            )
            with patched_workspace(workspace=workspace):
                hdr_rows = sec_pipeline.event_rows_from_document(
                    filing_row=filing,
                    document_path=hdr_path,
                    source_url=(
                        "https://www.sec.gov/Archives/edgar/data/1/"
                        "000000000126000001/fixture.hdr.sgml"
                    ),
                    item_source="hdr.sgml",
                )
                primary_rows = sec_pipeline.event_rows_from_document(
                    filing_row=filing,
                    document_path=primary_path,
                    source_url=(
                        "https://www.sec.gov/Archives/edgar/data/1/"
                        "000000000126000001/fixture.htm"
                    ),
                    item_source="primary_document",
                )
        self.assertEqual(
            [row["item_code"] for row in hdr_rows],
            ["1.01", "2.03", "5.02"],
        )
        self.assertEqual(
            [row["item_code"] for row in primary_rows],
            ["1.01", "5.02"],
        )

    def test_event_replay_accepts_primary_only_and_rejects_no_items(
        self,
    ) -> None:
        """Replay mirrors the live hdr-to-primary fallback boundary."""
        def observation_identity(*, path: Path, source_url: str) -> tuple:
            """Return one successful request identity for fixture bytes."""
            body = path.read_bytes()
            return (
                source_url,
                "200",
                str(len(body)),
                hashlib.sha256(body).hexdigest(),
                path.name,
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            filing = {
                field: "" for field in sec_pipeline.FILING_FIELDNAMES
            }
            filing.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "entity_role": "primary",
                    "form": "8-K",
                    "accession": "0000000001-26-000001",
                    "filingDate": "2025-06-01",
                    "reportDate": "2025-06-01",
                    "primaryDocument": "report.htm",
                    "source_role": "fy_8k",
                    "source_url": (
                        "https://www.sec.gov/Archives/edgar/data/1/"
                        "000000000126000001/report.htm"
                    ),
                }
            )
            with patched_workspace(workspace=workspace):
                base_path = sec_pipeline.accession_dir_path(
                    company=filing["company"],
                    cik=1,
                    accession=filing["accession"],
                )
                base_path.mkdir(parents=True)
                primary_path = base_path / filing["primaryDocument"]
                primary_path.write_text(
                    "<html><body>Item 5.02 Leadership.</body></html>",
                    encoding="utf-8",
                )
                primary_identity = observation_identity(
                    path=primary_path,
                    source_url=filing["source_url"],
                )
                rejected_identity = (
                    primary_identity[0],
                    "404",
                    *primary_identity[2:],
                )
                with self.assertRaises(ValueError):
                    sec_pipeline.expected_8k_event_rows(
                        inventory=[filing],
                        observation_identities=[rejected_identity],
                    )
                primary_only = sec_pipeline.expected_8k_event_rows(
                    inventory=[filing],
                    observation_identities=[primary_identity],
                )
                hdr_path = base_path / f"{filing['accession']}.hdr.sgml"
                hdr_path.write_text("<ITEMS>1.01", encoding="utf-8")
                hdr_identity = observation_identity(
                    path=hdr_path,
                    source_url=sec_pipeline.hdr_sgml_url(
                        cik=1,
                        accession=filing["accession"],
                    ),
                )
                old_primary_identity = (
                    primary_identity[0],
                    "200",
                    "3",
                    hashlib.sha256(b"old").hexdigest(),
                    primary_identity[4],
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "conflicting successful bodies",
                ):
                    sec_pipeline.expected_8k_event_rows(
                        inventory=[filing],
                        observation_identities=[
                            old_primary_identity,
                            primary_identity,
                            hdr_identity,
                        ],
                    )
                primary_path.unlink()
                with self.assertRaisesRegex(
                    ValueError,
                    "conflicting successful bodies",
                ):
                    sec_pipeline.expected_8k_event_rows(
                        inventory=[filing],
                        observation_identities=[
                            old_primary_identity,
                            primary_identity,
                            hdr_identity,
                        ],
                    )
                primary_path.write_text(
                    "<html><body>Item 5.02 Leadership.</body></html>",
                    encoding="utf-8",
                )
                hdr_404_identity = (
                    hdr_identity[0],
                    "404",
                    *hdr_identity[2:],
                )
                fallback_after_404 = sec_pipeline.expected_8k_event_rows(
                    inventory=[filing],
                    observation_identities=[
                        hdr_404_identity,
                        primary_identity,
                    ],
                )
                primary_path.unlink()
                hdr_path.unlink()
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.expected_8k_event_rows(
                        inventory=[filing],
                        observation_identities=[primary_identity],
                    )
                hdr_path.write_text("no item tags", encoding="utf-8")
                primary_path.write_text(
                    "<html><body>no item headings</body></html>",
                    encoding="utf-8",
                )
                empty_identities = [
                    observation_identity(
                        path=hdr_path,
                        source_url=sec_pipeline.hdr_sgml_url(
                            cik=1,
                            accession=filing["accession"],
                        ),
                    ),
                    observation_identity(
                        path=primary_path,
                        source_url=filing["source_url"],
                    ),
                ]
                with self.assertRaises(ValueError):
                    sec_pipeline.expected_8k_event_rows(
                        inventory=[filing],
                        observation_identities=empty_identities,
                    )
        self.assertEqual(
            [row["item_code"] for row in primary_only],
            ["5.02"],
        )
        self.assertEqual(
            [row["item_code"] for row in fallback_after_404],
            ["5.02"],
        )
        self.assertEqual(primary_only[0]["item_source"], "primary_document")

    def test_event_rebuild_uses_source_cik_for_raw_evidence(self) -> None:
        """A succession event evidence row retains the filing source CIK."""
        source_url = (
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000126000001/a.hdr.sgml"
        )
        events = [
            {
                "company": "Fixture Company",
                "cik": "1",
                "accession": "0000000001-26-000001",
                "filing_date": "2025-06-01",
                "item_code": "1.01",
                "confidence": "0.90",
                "brief": "Fixture event",
                "source_url": source_url,
                "repo_relative_path": "evidence/fixture/a.hdr.sgml",
                "document_name": "a.hdr.sgml",
            }
        ]
        inventory = [
            {
                "company": "Fixture Company",
                "source_role": "target_10k",
                "reportDate": "2025-12-31",
            },
            {
                "company": "Fixture Company",
                "source_role": "target_10k",
                "reportDate": "2024-12-31",
            },
            {
                "company": "Fixture Company",
                "cik": "1",
                "accession": "0000000001-26-000001",
                "filingDate": "2025-06-01",
                "source_role": "fy_8k",
            },
        ]
        with mock.patch.object(
            sec_pipeline,
            "load_company_registry",
            return_value=[{"company": "Fixture Company"}],
        ), mock.patch.object(
            sec_pipeline,
            "target_10k_for_company",
            return_value={"cik": "2", "reportDate": "2025-12-31"},
        ), mock.patch.object(
            sec_pipeline,
            "read_csv_file",
            return_value=inventory,
        ):
            _metrics, evidence = (
                sec_pipeline.apply_8k_event_metrics_from_events(
                    metrics=[],
                    evidence_rows=[],
                    events=events,
                    inventory=inventory,
                )
            )
        raw_rows = [
            row
            for row in evidence
            if row["extraction_method"] in {
                "eightk_item",
                "eightk_item_keyword",
            }
        ]
        aggregate_rows = [
            row
            for row in evidence
            if row["extraction_method"] == "eightk_zero_item_scan"
        ]
        self.assertTrue(raw_rows)
        self.assertEqual({row["cik"] for row in raw_rows}, {"1"})
        self.assertEqual(
            {row["period_end"] for row in raw_rows},
            {"2025-12-31"},
        )
        self.assertEqual({row["cik"] for row in aggregate_rows}, {"2"})

    def test_light_locator_rejects_malformed_hash_and_accession(self) -> None:
        """Light may skip raw bytes, but locator syntax must still fail."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            path = workspace / "outputs" / "metric_evidence.csv"
            path.parent.mkdir(parents=True)
            row = {field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES}
            row.update(
                {
                    "source_url": "https://data.sec.gov/mock/sample.json",
                    "repo_relative_path": "evidence/sample.json",
                    "content_sha256": "not-a-sha256",
                    "accession": "garbage-accession",
                    "document_name": "sample.json",
                }
            )
            write_rows(
                path=path,
                fieldnames=sec_pipeline.EVIDENCE_FIELDNAMES,
                rows=[row],
            )
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "portable_locator_artifact_specs",
                return_value=[(path, sec_pipeline.EVIDENCE_FIELDNAMES)],
            ):
                result = sec_pipeline.check_portable_artifact_locators(
                    mode="LIGHT_REVIEW_MODE",
                )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("content_sha256[0]=invalid", result["details"])
        self.assertIn("accession[0]=invalid", result["details"])

    def test_event_scan_keeps_url_accession_pairs_aligned(self) -> None:
        """Multi-CIK event locators must sort URL/accession as one identity."""
        events = [
            {
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/2/"
                    "000000000126000001/a.hdr.sgml"
                ),
                "accession": "0000000001-26-000001",
            },
            {
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000226000002/b.hdr.sgml"
                ),
                "accession": "0000000002-26-000002",
            },
        ]
        source_text, accession_text = sec_pipeline.event_scan_locators(
            events=events,
        )
        sources = source_text.split(";")
        accessions = accession_text.split(";")
        self.assertEqual(
            [sec_http.request_accession(source_url=url) for url in sources],
            accessions,
        )
        self.assertNotEqual(
            accession_text,
            ";".join(sorted(event["accession"] for event in events)),
        )

    def test_optional_sidecars_share_the_portable_gate_inventory(self) -> None:
        """Every migrated optional locator sidecar must remain gate-visible."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            sidecar = (
                workspace
                / "outputs"
                / "b06_debt_to_equity_candidates.csv"
            )
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text("fixture\n", encoding="utf-8")
            with patched_workspace(workspace=workspace):
                names = {
                    path.name
                    for path, _fieldnames in (
                        sec_pipeline.portable_locator_artifact_specs(
                            existing_optional_only=True,
                        )
                    )
                }
        self.assertIn("b06_debt_to_equity_candidates.csv", names)

    def test_legacy_absolute_path_cannot_escape_repository(self) -> None:
        """An anchored legacy hint containing parent traversal must fail."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()
            row = {
                "local_path": (
                    "/old/clone/outputs/../../../../../../etc/hosts"
                ),
                "content_sha256": "",
                "accession": "",
                "document_name": "hosts",
            }
            with patched_workspace(workspace=workspace):
                with self.assertRaises(ValueError):
                    sec_pipeline.resolve_artifact_path(row=row)

    def test_repo_relative_symlink_cannot_escape_repository(self) -> None:
        """A repository-relative symlink may not resolve to external bytes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            external = root / "external.txt"
            link = workspace / "evidence" / "external.txt"
            link.parent.mkdir(parents=True)
            external.write_text("external\n", encoding="utf-8")
            link.symlink_to(external)
            row = {
                "repo_relative_path": "evidence/external.txt",
                "content_sha256": "",
                "accession": "",
                "document_name": "external.txt",
            }
            with patched_workspace(workspace=workspace):
                with self.assertRaises(ValueError):
                    sec_pipeline.resolve_artifact_path(row=row)

    def test_legacy_absolute_path_relocates_without_string_replacement(self) -> None:
        """A clone B parser run must ignore clone A's obsolete absolute root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            clone_a = root / "evidence" / "clone_a"
            clone_b = root / "clone_b"
            artifact = clone_a / "evidence" / "sample.xml"
            artifact.parent.mkdir(parents=True)
            shutil.copy(
                src=(
                    REPO_ROOT
                    / "tests"
                    / "fixtures"
                    / "inline_scale_route"
                    / "mock_inline_scale.xml"
                ),
                dst=artifact,
            )
            material_row = {
                "company": "portable fixture",
                "cik": "0",
                "accession": "mock-accession",
                "document_name": artifact.name,
                "local_path": str(artifact),
            }
            clone_a.rename(clone_b)
            with patched_workspace(workspace=clone_b):
                rows = sec_pipeline.parse_instance_with_fallback(
                    material_row=material_row,
                )
        self.assertTrue(rows)

    def test_repeated_anchor_legacy_path_fails_when_identity_is_ambiguous(
        self,
    ) -> None:
        """Two repeated-anchor identity matches must fail closed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "clone_b"
            relative_path = Path("evidence", "raw", "sample.xml")
            nested_path = (
                workspace
                / "evidence"
                / "oldclone"
                / relative_path
            )
            direct_path = workspace / relative_path
            nested_path.parent.mkdir(parents=True)
            direct_path.parent.mkdir(parents=True, exist_ok=True)
            body = b"same-identity"
            nested_path.write_bytes(body)
            direct_path.write_bytes(body)
            row = {
                "local_path": str(
                    root / "evidence" / "oldclone" / relative_path
                ),
                "content_sha256": hashlib.sha256(body).hexdigest(),
                "document_name": "sample.xml",
            }
            with patched_workspace(workspace=workspace):
                with self.assertRaisesRegex(ValueError, "ambiguous"):
                    sec_pipeline.normalize_csv_row(
                        row=row,
                        fieldnames=sec_pipeline.MATERIAL_FIELDNAMES,
                    )

    def test_stage_11_runs_after_clone_root_change(self) -> None:
        """Stage 11 must consume clone A artifacts after moving them to clone B."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            clone_a = root / "evidence" / "clone_a"
            clone_b = root / "clone_b"
            relative_artifact = (
                Path("evidence")
                / "accession_materials"
                / "portable_fixture_1_000000000126000001"
                / "sample.xml"
            )
            artifact = clone_a / relative_artifact
            inventory = clone_a / "outputs" / "accession_materials_inventory.csv"
            artifact.parent.mkdir(parents=True)
            inventory.parent.mkdir(parents=True)
            shutil.copy(
                src=(
                    REPO_ROOT
                    / "tests"
                    / "fixtures"
                    / "inline_scale_route"
                    / "mock_inline_scale.xml"
                ),
                dst=artifact,
            )
            with patched_workspace(workspace=clone_a):
                sec_pipeline.write_csv_file(
                    path=inventory,
                    fieldnames=sec_pipeline.MATERIAL_FIELDNAMES,
                    rows=[
                        {
                            "company": "portable fixture",
                            "cik": "1",
                            "entity_role": "primary",
                            "form": "10-K",
                            "accession": "0000000001-26-000001",
                            "document_name": artifact.name,
                            "document_type": "xbrl_instance",
                            "source_url": (
                                "https://www.sec.gov/Archives/edgar/data/1/"
                                "000000000126000001/sample.xml"
                            ),
                            "local_path": str(artifact),
                            "status_code": "200",
                            "content_length": str(artifact.stat().st_size),
                        }
                    ],
                )
            clone_a.rename(clone_b)

            def verify_portable_repair() -> None:
                """Parse the moved artifact at the real stage-11 repair boundary."""
                material = sec_pipeline.read_csv_file(
                    path=(
                        clone_b
                        / "outputs"
                        / "accession_materials_inventory.csv"
                    )
                )[0]
                parsed = sec_pipeline.parse_instance_with_fallback(
                    material_row=material,
                )
                self.assertTrue(parsed)

            def deferred_validation(
                *,
                exit_on_failure: bool,
                manifest: dict | None = None,
            ) -> list[dict]:
                """Provide one deferred successful run to the stage."""
                if exit_on_failure or manifest is None:
                    raise AssertionError(
                        "stage must defer and reuse manifest success"
                    )
                manifest["mode"] = "FULL_VALIDATION"
                manifest["refreshed_artifacts"] = list(
                    sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
                )
                manifest["not_refreshed_artifacts"] = []
                sec_pipeline.write_validation_run_manifest(manifest=manifest)
                return [
                    sec_pipeline.validation_row(
                        check_id="validation_gate_result",
                        status="PASS",
                        details="all gates pass",
                    )
                ]

            def projected_report(*, validation_manifest: dict) -> str:
                """Return a minimal report bound to the deferred run."""
                return (
                    f"- run_id: `{validation_manifest['run_id']}`\n"
                    f"- result: `{validation_manifest['result']}`\n"
                )

            with patched_workspace(workspace=clone_b), mock.patch.object(
                sec_pipeline,
                "apply_p0_repairs",
                side_effect=verify_portable_repair,
            ), mock.patch.object(
                sec_pipeline,
                "build_coverage_matrix",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "build_companyfacts_crosscheck",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "build_exceptions_markdown",
                return_value="# exceptions\n",
            ), mock.patch.object(
                sec_pipeline,
                "run_repair_validation",
                side_effect=deferred_validation,
            ), mock.patch.object(
                sec_pipeline,
                "build_report_markdown",
                side_effect=projected_report,
            ), mock.patch.object(
                sec_pipeline,
                "build_readme",
                return_value="# readme\n",
            ):
                sec_pipeline.stage_build_report()

            inventory_text = (
                clone_b / "outputs" / "accession_materials_inventory.csv"
            ).read_text(encoding="utf-8")
        self.assertNotIn(str(clone_a), inventory_text)
        self.assertIn(relative_artifact.as_posix(), inventory_text)


class PortableRequestLogTest(unittest.TestCase):
    """Validate request observations never retain a clone-specific root."""

    def test_read_timeout_after_request_is_logged(self) -> None:
        """A response-body timeout must produce one attested observation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            response = mock.MagicMock()
            response.__enter__.return_value.read.side_effect = TimeoutError(
                "read timed out"
            )
            with mock.patch.object(
                sec_http,
                "urlopen",
                return_value=response,
            ) as transport:
                result = client.fetch(
                    url="https://www.sec.gov/mock/sample.json",
                    purpose="timeout fixture",
                    local_path=workspace / "evidence" / "raw" / "sample.json",
                )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "committed_request_observation_sequence",
                return_value=[],
            ):
                check = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result.status_code, 0)
        self.assertEqual(len(rows), 1)
        self.assertIn("TimeoutError", rows[0]["error"])
        self.assertEqual(check["status"], "PASS")

    def test_incomplete_read_after_request_is_logged(self) -> None:
        """A truncated HTTP body must produce one attested observation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            response = mock.MagicMock()
            response.__enter__.return_value.read.side_effect = IncompleteRead(
                partial=b"partial",
                expected=10,
            )
            with mock.patch.object(
                sec_http,
                "urlopen",
                return_value=response,
            ) as transport:
                result = client.fetch(
                    url="https://www.sec.gov/mock/sample.json",
                    purpose="incomplete read fixture",
                    local_path=workspace / "evidence" / "raw" / "sample.json",
                )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result.status_code, 0)
        self.assertEqual(len(rows), 1)
        self.assertIn("IncompleteRead", rows[0]["error"])

    def test_redirects_are_observed_without_following(self) -> None:
        """Keep redirect targets unrequested and log only the first hop."""
        source_url = "https://www.sec.gov/mock/source.json"
        target_urls = (
            "https://example.com/mock/target.json",
            "https://data.sec.gov/mock/target.json",
            "http://www.sec.gov/mock/target.json",
        )
        for target_url in target_urls:
            with self.subTest(target_url=target_url):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    workspace = Path(tmp_dir) / "workspace"
                    client = build_http_client(workspace=workspace)
                    transport_urls = []

                    class RedirectingHttpsHandler(HTTPSHandler):
                        """Return a redirect before target bytes."""

                        def https_open(self, request):
                            """Record URLs and return deterministic bytes."""
                            transport_urls.append(request.full_url)
                            headers = Message()
                            if request.full_url == source_url:
                                headers["Location"] = target_url
                                response = addinfourl(
                                    fp=io.BytesIO(b"redirect response"),
                                    headers=headers,
                                    url=request.full_url,
                                    code=302,
                                )
                                response.msg = "Found"
                                return response
                            response = addinfourl(
                                fp=io.BytesIO(b"target bytes"),
                                headers=headers,
                                url=request.full_url,
                                code=200,
                            )
                            response.msg = "OK"
                            return response

                    opener = build_opener(
                        sec_http.NoRedirectHandler(),
                        RedirectingHttpsHandler(),
                    )
                    with mock.patch.object(
                        sec_http,
                        "_NO_REDIRECT_OPENER",
                        opener,
                    ):
                        result = client.fetch(
                            url=source_url,
                            purpose="redirect fixture",
                            local_path=(
                                workspace
                                / "evidence"
                                / "raw"
                                / "source.json"
                            ),
                        )
                    rows = read_rows(path=client.log_path)
                    sec_http.validate_request_log_manifest(
                        log_path=client.log_path
                    )
                    saved_body = Path(result.local_path).read_bytes()
                    headers_payload = json.loads(
                        Path(result.headers_path).read_text(encoding="utf-8")
                    )
                    evidence_bytes = [
                        path.read_bytes()
                        for path in (workspace / "evidence").rglob("*")
                        if path.is_file()
                    ]
                    with patched_workspace(
                        workspace=workspace
                    ), mock.patch.object(
                        sec_pipeline,
                        "committed_request_observation_sequence",
                        return_value=[],
                    ):
                        check = sec_pipeline.check_requests_log_sec_only()
                self.assertEqual(transport_urls, [source_url])
                self.assertEqual(result.status_code, 302)
                self.assertEqual(saved_body, b"redirect response")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["source_url"], source_url)
                self.assertEqual(rows[0]["status_code"], "302")
                self.assertTrue(
                    rows[0]["error"].startswith(
                        sec_http.REDIRECT_DISABLED_ERROR_PREFIX
                    )
                )
                self.assertEqual(
                    headers_payload["headers"]["Location"],
                    target_url,
                )
                self.assertNotIn(b"target bytes", evidence_bytes)
                self.assertEqual(check["status"], "PASS")

    def test_initial_url_requires_exact_official_https_origin(self) -> None:
        """Invalid initial authorities must fail before transport."""
        invalid_urls = (
            "http://www.sec.gov/mock/sample.json",
            "https://user@www.sec.gov/mock/sample.json",
            "https://www.sec.gov.evil.example/mock/sample.json",
            "https://www.sec.gov:443/mock/sample.json",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            with mock.patch.object(sec_http, "urlopen") as transport:
                for invalid_url in invalid_urls:
                    with self.subTest(invalid_url=invalid_url):
                        with self.assertRaises(ValueError):
                            client.fetch(
                                url=invalid_url,
                                purpose="invalid URL fixture",
                                local_path=(
                                    workspace
                                    / "evidence"
                                    / "raw"
                                    / "sample.json"
                                ),
                            )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
        transport.assert_not_called()
        self.assertEqual(rows, [])

    def test_casefolded_snapshot_working_path_is_rejected_before_transport(
        self,
    ) -> None:
        """A case alias cannot overwrite immutable response bytes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            snapshot_path = (
                workspace
                / "evidence"
                / "request_attempts"
                / "aa"
                / "sample.json"
            )
            snapshot_path.parent.mkdir(parents=True)
            snapshot_path.write_bytes(b"first immutable response")
            raw_path = workspace / "evidence" / "raw"
            raw_path.mkdir()
            alias_path = (
                raw_path
                / ".."
                / "REQUEST_ATTEMPTS"
                / "aa"
                / "sample.json"
            )
            with mock.patch.object(sec_http, "urlopen") as transport:
                with self.assertRaises(ValueError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="casefold snapshot alias fixture",
                        local_path=alias_path,
                    )
            rows = read_rows(path=client.log_path)
            retained_bytes = snapshot_path.read_bytes()
            sec_http.validate_request_log_manifest(log_path=client.log_path)
        transport.assert_not_called()
        self.assertEqual(rows, [])
        self.assertEqual(retained_bytes, b"first immutable response")

    def test_request_attempts_symlink_is_rejected_before_transport(
        self,
    ) -> None:
        """A snapshot-root symlink cannot trigger transport or writes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            external = root / "external"
            client = build_http_client(workspace=workspace)
            external.mkdir()
            (workspace / "evidence" / "request_attempts").symlink_to(
                external,
                target_is_directory=True,
            )
            with mock.patch.object(sec_http, "urlopen") as transport:
                with self.assertRaises(ValueError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="symlink fixture",
                        local_path=(
                            workspace / "evidence" / "raw" / "sample.json"
                        ),
                    )
            transport.assert_not_called()
            self.assertEqual(list(external.iterdir()), [])

    def test_directory_working_path_is_rejected_before_transport(self) -> None:
        """A directory target must fail before the HTTP attempt is sent."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            response_path = workspace / "evidence" / "raw" / "sample.json"
            response_path.mkdir(parents=True)
            with mock.patch.object(sec_http, "urlopen") as transport:
                with self.assertRaises(IsADirectoryError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="directory fixture",
                        local_path=response_path,
                    )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
        transport.assert_not_called()
        self.assertEqual(rows, [])

    def test_working_symlink_cannot_alias_request_log(self) -> None:
        """An in-repository symlink cannot redirect body bytes into the log."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            response_path = workspace / "evidence" / "raw" / "sample.json"
            response_path.parent.mkdir(parents=True)
            response_path.symlink_to(client.log_path)
            log_bytes = client.log_path.read_bytes()
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            manifest_bytes = manifest_path.read_bytes()
            with mock.patch.object(sec_http, "urlopen") as transport:
                with self.assertRaises(ValueError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="internal symlink fixture",
                        local_path=response_path,
                    )
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            retained_log_bytes = client.log_path.read_bytes()
            retained_manifest_bytes = manifest_path.read_bytes()
        transport.assert_not_called()
        self.assertEqual(retained_log_bytes, log_bytes)
        self.assertEqual(retained_manifest_bytes, manifest_bytes)

    def test_working_body_hardlink_is_detached_before_write(self) -> None:
        """Response persistence cannot mutate an external hardlink inode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            client = build_http_client(workspace=workspace)
            external_path = root / "external.bin"
            external_path.write_bytes(b"outside")
            response_path = workspace / "evidence" / "raw" / "sample.json"
            response_path.parent.mkdir(parents=True)
            os.link(src=external_path, dst=response_path)
            response = mock.MagicMock()
            entered = response.__enter__.return_value
            entered.read.return_value = b"body"
            entered.status = 200
            entered.headers.items.return_value = [
                ("Content-Type", "application/json")
            ]
            with mock.patch.object(
                sec_http,
                "urlopen",
                return_value=response,
            ) as transport:
                result = client.fetch(
                    url="https://www.sec.gov/mock/sample.json",
                    purpose="working hardlink fixture",
                    local_path=response_path,
                )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            external_bytes = external_path.read_bytes()
            working_bytes = response_path.read_bytes()
            same_inode = response_path.samefile(external_path)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(rows), 1)
        self.assertEqual(external_bytes, b"outside")
        self.assertEqual(working_bytes, b"body")
        self.assertFalse(same_inode)

    def test_snapshot_result_cannot_be_reused_as_working_path(self) -> None:
        """A later fetch cannot overwrite an earlier immutable snapshot."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            response = mock.MagicMock()
            entered = response.__enter__.return_value
            entered.read.return_value = b"first"
            entered.status = 200
            entered.headers.items.return_value = [
                ("Content-Type", "application/json")
            ]
            with mock.patch.object(
                sec_http,
                "urlopen",
                return_value=response,
            ):
                first = client.fetch(
                    url="https://www.sec.gov/mock/sample.json",
                    purpose="first snapshot fixture",
                    local_path=(
                        workspace / "evidence" / "raw" / "sample.json"
                    ),
                )
            snapshot_path = Path(first.local_path)
            headers_path = Path(first.headers_path)
            snapshot_bytes = snapshot_path.read_bytes()
            headers_bytes = headers_path.read_bytes()
            with mock.patch.object(sec_http, "urlopen") as transport:
                with self.assertRaises(ValueError):
                    client.fetch(
                        url="https://www.sec.gov/mock/other.json",
                        purpose="snapshot reuse fixture",
                        local_path=snapshot_path,
                    )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            retained_snapshot_bytes = snapshot_path.read_bytes()
            retained_headers_bytes = headers_path.read_bytes()
        transport.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(retained_snapshot_bytes, snapshot_bytes)
        self.assertEqual(retained_headers_bytes, headers_bytes)

    def test_working_body_and_headers_cannot_alias(self) -> None:
        """Pairwise target identity is rejected before transport."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            response_path = workspace / "evidence" / "raw" / "sample.json"
            headers_path = response_path.with_suffix(".json.headers.json")
            response_path.parent.mkdir(parents=True)
            response_path.write_bytes(b"shared")
            os.link(src=response_path, dst=headers_path)
            with mock.patch.object(sec_http, "urlopen") as transport:
                with self.assertRaises(ValueError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="pairwise alias fixture",
                        local_path=response_path,
                    )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
        transport.assert_not_called()
        self.assertEqual(rows, [])

    def test_working_path_cannot_be_request_audit_state(self) -> None:
        """Direct body targets cannot overwrite the log or its manifest."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            protected_bytes = {
                client.log_path: client.log_path.read_bytes(),
                manifest_path: manifest_path.read_bytes(),
            }
            for protected_path in protected_bytes:
                with self.subTest(
                    protected_path=protected_path
                ), mock.patch.object(
                    sec_http,
                    "urlopen",
                ) as transport:
                    with self.assertRaises(ValueError):
                        client.fetch(
                            url="https://www.sec.gov/mock/sample.json",
                            purpose="audit alias fixture",
                            local_path=protected_path,
                        )
                    transport.assert_not_called()
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            retained_bytes = {
                path: path.read_bytes() for path in protected_bytes
            }
        self.assertEqual(retained_bytes, protected_bytes)

    def test_manifest_transaction_hardlink_collision_fails_closed(
        self,
    ) -> None:
        """A preoccupied UUID manifest path cannot truncate the old log."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            old_log_bytes = client.log_path.read_bytes()
            old_manifest_bytes = manifest_path.read_bytes()
            log_uuid = uuid.UUID(int=1)
            manifest_uuid = uuid.UUID(int=2)
            occupied_path = manifest_path.with_name(
                f".{manifest_path.name}.{manifest_uuid.hex}.tmp"
            )
            os.link(src=client.log_path, dst=occupied_path)
            result = sec_http.FetchResult(
                url="https://www.sec.gov/mock/sample.json",
                status_code=0,
                local_path="",
                sha256="",
                content_length=0,
                headers_path="",
                error="transport failure",
            )
            with mock.patch.object(
                sec_http.uuid,
                "uuid4",
                side_effect=[log_uuid, manifest_uuid],
            ):
                with self.assertRaises(FileExistsError):
                    client._append_log_row(
                        result=result,
                        purpose="transaction collision fixture",
                        attempt=0,
                    )
            rows = read_rows(path=client.log_path)
            occupied_bytes = occupied_path.read_bytes()
            retained_manifest_bytes = manifest_path.read_bytes()
            same_inode = client.log_path.samefile(occupied_path)
            with self.assertRaises(ValueError):
                sec_http.validate_request_log_manifest(
                    log_path=client.log_path
                )
        self.assertEqual(len(rows), 1)
        self.assertEqual(occupied_bytes, old_log_bytes)
        self.assertEqual(retained_manifest_bytes, old_manifest_bytes)
        self.assertFalse(same_inode)

    def test_log_hardlink_is_detached_before_append(self) -> None:
        """Replace the repository link without writing externally."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            client = build_http_client(workspace=workspace)
            external_path = root / "external_requests_log.csv"
            os.link(src=client.log_path, dst=external_path)
            external_bytes = external_path.read_bytes()
            result = sec_http.FetchResult(
                url="https://www.sec.gov/mock/sample.json",
                status_code=0,
                local_path="",
                sha256="",
                content_length=0,
                headers_path="",
                error="transport failure",
            )
            client._append_log_row(
                result=result,
                purpose="external hardlink fixture",
                attempt=0,
            )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            retained_external_bytes = external_path.read_bytes()
            same_inode = client.log_path.samefile(external_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(retained_external_bytes, external_bytes)
        self.assertFalse(same_inode)

    def test_two_clients_concurrently_append_without_loss(self) -> None:
        """Two clients serialize one ledger read-modify-write transaction."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            first_client = build_http_client(workspace=workspace)
            second_client = sec_http.SecHttpClient(
                workdir=workspace,
                config_path=workspace / "config" / "sec_config.json",
                log_path=first_client.log_path,
            )
            barrier = threading.Barrier(parties=2)
            original_writer = sec_http.write_repository_bytes_atomically
            errors = []

            def delayed_writer(
                *,
                workdir: Path,
                path: Path,
                content: bytes,
            ) -> None:
                """Widen the old lost-update window at log publication."""
                if path == first_client.log_path:
                    time.sleep(0.05)
                original_writer(
                    workdir=workdir,
                    path=path,
                    content=content,
                )

            def append(
                *,
                client: sec_http.SecHttpClient,
                purpose: str,
            ) -> None:
                """Release both clients together and retain thread failures."""
                barrier.wait(timeout=5)
                try:
                    client._append_log_row(
                        result=sec_http.FetchResult(
                            url="https://www.sec.gov/mock/sample.json",
                            status_code=0,
                            local_path="",
                            sha256="",
                            content_length=0,
                            headers_path="",
                            error="transport failure",
                        ),
                        purpose=purpose,
                        attempt=0,
                    )
                except (OSError, RuntimeError, TypeError, ValueError) as error:
                    errors.append(error)

            threads = [
                threading.Thread(
                    target=append,
                    kwargs={"client": first_client, "purpose": "first"},
                ),
                threading.Thread(
                    target=append,
                    kwargs={"client": second_client, "purpose": "second"},
                ),
            ]
            with mock.patch.object(
                sec_http,
                "write_repository_bytes_atomically",
                side_effect=delayed_writer,
            ):
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)
            rows = read_rows(path=first_client.log_path)
            sec_http.validate_request_log_manifest(
                log_path=first_client.log_path
            )
            alive = [thread.is_alive() for thread in threads]
        self.assertEqual(errors, [])
        self.assertEqual(alive, [False, False])
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["purpose"] for row in rows}, {"first", "second"})

    def test_two_processes_concurrently_append_without_loss(self) -> None:
        """The POSIX lock serializes independent ledger writer processes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            start_path = workspace / "start"
            script = (
                "import sys\n"
                "import time\n"
                "from pathlib import Path\n"
                f"sys.path.insert(0, {str(SCRIPTS_DIR)!r})\n"
                "import sec_http\n"
                "workspace = Path(sys.argv[1])\n"
                "purpose = sys.argv[2]\n"
                "ready_path = Path(sys.argv[3])\n"
                "start_path = Path(sys.argv[4])\n"
                "client = sec_http.SecHttpClient(\n"
                "    workdir=workspace,\n"
                "    config_path=workspace / 'config' / 'sec_config.json',\n"
                "    log_path=workspace / 'evidence' / 'requests_log.csv',\n"
                ")\n"
                "original = sec_http.write_repository_bytes_atomically\n"
                "def delayed(*, workdir, path, content):\n"
                "    \"\"\"Widen the cross-process lost-update window.\"\"\"\n"
                "    if path == client.log_path:\n"
                "        time.sleep(0.5)\n"
                "    original(workdir=workdir, path=path, content=content)\n"
                "sec_http.write_repository_bytes_atomically = delayed\n"
                "ready_path.write_text('ready', encoding='utf-8')\n"
                "while not start_path.exists():\n"
                "    time.sleep(0.01)\n"
                "client._append_log_row(\n"
                "    result=sec_http.FetchResult(\n"
                "        url='https://www.sec.gov/mock/sample.json',\n"
                "        status_code=0,\n"
                "        local_path='',\n"
                "        sha256='',\n"
                "        content_length=0,\n"
                "        headers_path='',\n"
                "        error='transport failure',\n"
                "    ),\n"
                "    purpose=purpose,\n"
                "    attempt=0,\n"
                ")\n"
            )
            ready_paths = [workspace / "ready-1", workspace / "ready-2"]
            processes = [
                subprocess.Popen(
                    args=[
                        sys.executable,
                        "-c",
                        script,
                        str(workspace),
                        purpose,
                        str(ready_path),
                        str(start_path),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for purpose, ready_path in zip(
                    ("first-process", "second-process"),
                    ready_paths,
                )
            ]
            deadline = time.monotonic() + 10
            while not all(path.exists() for path in ready_paths):
                if time.monotonic() > deadline:
                    self.fail("Child request-log writers did not become ready")
                time.sleep(0.01)
            start_path.write_text("start", encoding="utf-8")
            completed = [
                process.communicate(timeout=10) for process in processes
            ]
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
        self.assertEqual(
            [process.returncode for process in processes],
            [0, 0],
            msg=str(completed),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["purpose"] for row in rows},
            {"first-process", "second-process"},
        )

    def test_existing_log_initialization_validates_only_inside_migration(
        self,
    ) -> None:
        """Do not revalidate after releasing the ledger lock."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            first_client = build_http_client(workspace=workspace)
            original_validator = sec_http.validate_request_log_manifest
            with mock.patch.object(
                sec_http,
                "validate_request_log_manifest",
                wraps=original_validator,
            ) as validator:
                second_client = sec_http.SecHttpClient(
                    workdir=workspace,
                    config_path=workspace / "config" / "sec_config.json",
                    log_path=first_client.log_path,
                )
            sec_http.validate_request_log_manifest(
                log_path=second_client.log_path
            )
        self.assertEqual(validator.call_count, 1)

    def test_snapshot_bucket_symlink_failure_is_logged(self) -> None:
        """A post-response bucket escape must log without writing out."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            external = root / "external"
            client = build_http_client(workspace=workspace)
            body = b"body"
            digest = hashlib.sha256(body).hexdigest()
            snapshot_root = workspace / "evidence" / "request_attempts"
            snapshot_root.mkdir()
            external.mkdir()
            (snapshot_root / digest[:2]).symlink_to(
                external,
                target_is_directory=True,
            )
            response = mock.MagicMock()
            entered = response.__enter__.return_value
            entered.read.return_value = body
            entered.status = 200
            entered.headers.items.return_value = [
                ("Content-Type", "application/json")
            ]
            with mock.patch.object(
                sec_http,
                "urlopen",
                return_value=response,
            ) as transport:
                with self.assertRaises(ValueError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="bucket symlink fixture",
                        local_path=(
                            workspace / "evidence" / "raw" / "sample.json"
                        ),
                    )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            external_entries = list(external.iterdir())
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_code"], "0")
        self.assertIn("PersistenceError", rows[0]["error"])
        self.assertIn("response_status=200", rows[0]["error"])
        self.assertIn(digest, rows[0]["error"])
        self.assertEqual(external_entries, [])

    def test_persistence_oserror_is_logged_without_response_bytes(
        self,
    ) -> None:
        """A post-response disk failure must retain an attested observation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            body = b"body"
            digest = hashlib.sha256(body).hexdigest()
            response = mock.MagicMock()
            entered = response.__enter__.return_value
            entered.read.return_value = body
            entered.status = 200
            entered.headers.items.return_value = [
                ("Content-Type", "application/json")
            ]
            with mock.patch.object(
                sec_http,
                "urlopen",
                return_value=response,
            ) as transport, mock.patch.object(
                sec_http,
                "write_immutable_bytes",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaises(OSError):
                    client.fetch(
                        url="https://www.sec.gov/mock/sample.json",
                        purpose="disk failure fixture",
                        local_path=(
                            workspace / "evidence" / "raw" / "sample.json"
                        ),
                    )
            rows = read_rows(path=client.log_path)
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            snapshot_root = workspace / "evidence" / "request_attempts"
            snapshot_files = [
                path for path in snapshot_root.rglob("*") if path.is_file()
            ]
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_code"], "0")
        self.assertIn("PersistenceError: OSError", rows[0]["error"])
        self.assertIn("response_status=200", rows[0]["error"])
        self.assertIn(digest, rows[0]["error"])
        self.assertEqual(snapshot_files, [])

    def test_snapshot_final_name_alias_race_fails_without_overwrite(
        self,
    ) -> None:
        """A last-moment symlink or hardlink cannot redirect response bytes."""
        for alias_kind in ["symlink", "hardlink"]:
            for victim_scope in ["inside", "outside"]:
                with self.subTest(
                    alias_kind=alias_kind,
                    victim_scope=victim_scope,
                ), tempfile.TemporaryDirectory() as tmp_dir:
                    root = Path(tmp_dir)
                    workspace = root / "workspace"
                    client = build_http_client(workspace=workspace)
                    victim_root = (
                        workspace if victim_scope == "inside" else root
                    )
                    victim_path = victim_root / f"{victim_scope}-victim.bin"
                    victim_path.write_bytes(b"response body")
                    response = mock.MagicMock()
                    entered = response.__enter__.return_value
                    entered.read.return_value = b"response body"
                    entered.status = 200
                    entered.headers.items.return_value = [
                        ("Content-Type", "application/json")
                    ]
                    working_path = (
                        workspace / "evidence" / "raw" / "sample.json"
                    )
                    original_link = os.link
                    injected = False

                    def inject_alias(*, src, dst, follow_symlinks=True):
                        """Occupy the first immutable final name then link."""
                        nonlocal injected
                        if not injected:
                            injected = True
                            if alias_kind == "symlink":
                                Path(dst).symlink_to(victim_path)
                            else:
                                original_link(src=victim_path, dst=dst)
                        return original_link(
                            src=src,
                            dst=dst,
                            follow_symlinks=follow_symlinks,
                        )

                    with mock.patch.object(
                        sec_http,
                        "urlopen",
                        return_value=response,
                    ) as transport, mock.patch.object(
                        sec_http.os,
                        "link",
                        side_effect=inject_alias,
                    ):
                        with self.assertRaises(RuntimeError):
                            client.fetch(
                                url="https://www.sec.gov/mock/sample.json",
                                purpose="final-name alias race fixture",
                                local_path=working_path,
                            )
                    rows = read_rows(path=client.log_path)
                    sec_http.validate_request_log_manifest(
                        log_path=client.log_path
                    )
                    self.assertEqual(transport.call_count, 1)
                    self.assertEqual(
                        victim_path.read_bytes(),
                        b"response body",
                    )
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["status_code"], "0")
                    self.assertIn("PersistenceError", rows[0]["error"])
                    self.assertFalse(working_path.exists())
                    self.assertFalse(
                        working_path.with_suffix(
                            ".json.headers.json"
                        ).exists()
                    )

    def test_identical_concurrent_snapshot_publishers_both_succeed(
        self,
    ) -> None:
        """Cooperating writers cannot observe the winner's transient link."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bucket" / "snapshot.bin"
            path.parent.mkdir(parents=True)
            first_linked = threading.Event()
            release_first = threading.Event()
            second_done = threading.Event()
            errors = []
            original_link = os.link

            def pausing_link(*, src, dst, follow_symlinks=True):
                """Hold the winner while its temporary hardlink still exists."""
                original_link(
                    src=src,
                    dst=dst,
                    follow_symlinks=follow_symlinks,
                )
                first_linked.set()
                if not release_first.wait(timeout=5):
                    raise TimeoutError(
                        "concurrent publisher fixture timed out")

            def publish(*, done: threading.Event | None = None) -> None:
                """Capture one publisher result without losing its exception."""
                try:
                    sec_http.write_immutable_bytes(
                        path=path,
                        content=b"identical response",
                    )
                except (OSError, RuntimeError, TimeoutError) as error:
                    errors.append(error)
                finally:
                    if done is not None:
                        done.set()

            with mock.patch.object(
                sec_http.os,
                "link",
                side_effect=pausing_link,
            ):
                first = threading.Thread(
                    target=publish,
                    kwargs={},
                )
                first.start()
                self.assertTrue(first_linked.wait(timeout=5))
                second = threading.Thread(
                    target=publish,
                    kwargs={"done": second_done},
                )
                second.start()
                self.assertFalse(second_done.wait(timeout=0.1))
                release_first.set()
                first.join(timeout=5)
                second.join(timeout=5)
            content, metadata = sec_http.read_verified_immutable_bytes(
                path=path
            )
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(content, b"identical response")
        self.assertEqual(metadata.st_nlink, 1)

    def test_deleted_observation_invalidates_exact_set_manifest(self) -> None:
        """Deleting one valid row cannot turn the remaining row into PASS."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            log_path = workspace / "evidence" / "requests_log.csv"
            log_path.parent.mkdir(parents=True)
            base = {
                "timestamp_utc": "2026-07-22T00:00:00+00:00",
                "method": "GET",
                "source_url": "https://www.sec.gov/mock/sample.json",
                "status_code": "0",
                "purpose": "fixture",
                "repo_relative_path": "",
                "headers_repo_relative_path": "",
                "content_length": "0",
                "content_sha256": "",
                "accession": "",
                "document_name": "sample.json",
                "user_agent": "fixture fixture@example.com",
                "retry_attempt": "0",
                "error": "transport failure",
            }
            rows = [base, {**base, "purpose": "second fixture"}]
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows,
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows[:1],
            )
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("request_log_manifest_invalid", result["details"])

    def test_manifest_rejects_non_integer_and_duplicate_metadata(self) -> None:
        """Manifest schema types and keys must remain exact JSON evidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["schema_version"] = True
            payload["row_count"] = False
            manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                sec_http.validate_request_log_manifest(
                    log_path=client.log_path
                )
            valid = sec_http.request_log_manifest_payload(
                log_path=client.log_path
            )
            duplicate_json = (
                '{"schema_version":1,"schema_version":1,'
                f'"row_count":0,"content_sha256":'
                f'"{valid["content_sha256"]}"}}\n'
            )
            manifest_path.write_text(duplicate_json, encoding="utf-8")
            with self.assertRaises(ValueError):
                sec_http.validate_request_log_manifest(
                    log_path=client.log_path
                )

    def test_manifest_rejects_request_row_with_wrong_cell_count(self) -> None:
        """A signed CSV row must contain exactly the declared fields."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            client._append_log_row(
                result=sec_http.FetchResult(
                    url="https://www.sec.gov/mock/sample.json",
                    status_code=0,
                    local_path="",
                    sha256="",
                    content_length=0,
                    headers_path="",
                    error="transport failure",
                ),
                purpose="extra-cell fixture",
                attempt=0,
            )
            lines = client.log_path.read_text(encoding="utf-8").splitlines()
            invalid_rows = (
                lines[1] + ",INJECTED",
                lines[1].rsplit(",", maxsplit=1)[0],
            )
            for invalid_row in invalid_rows:
                with self.subTest(invalid_row=invalid_row):
                    client.log_path.write_text(
                        f"{lines[0]}\n{invalid_row}\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        sec_http.refresh_request_log_manifest(
                            workdir=workspace,
                            log_path=client.log_path,
                        )

    def test_resigned_shrink_cannot_orphan_stored_response(self) -> None:
        """A fresh manifest cannot hide a deleted response observation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            for name, body in [("one.json", b"one"), ("two.json", b"two")]:
                response = mock.MagicMock()
                entered = response.__enter__.return_value
                entered.read.return_value = body
                entered.status = 200
                entered.headers.items.return_value = [
                    ("Content-Type", "application/json")
                ]
                with mock.patch.object(
                    sec_http,
                    "urlopen",
                    return_value=response,
                ):
                    client.fetch(
                        url=f"https://www.sec.gov/mock/{name}",
                        purpose="resigned shrink fixture",
                        local_path=workspace / "evidence" / "raw" / name,
                    )
            rows = read_rows(path=client.log_path)
            write_rows(
                path=client.log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows[:1],
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=client.log_path,
            )
            sec_http.validate_request_log_manifest(log_path=client.log_path)
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn(
            "missing_stored_response_observations",
            result["details"],
        )

    def test_resigned_log_cannot_reorder_or_remove_committed_attempt(
        self,
    ) -> None:
        """The reviewed Git ledger remains an ordered append-only prefix."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            log_path = workspace / "evidence" / "requests_log.csv"
            log_path.parent.mkdir(parents=True)
            base = {
                "timestamp_utc": "2026-07-22T00:00:00+00:00",
                "method": "GET",
                "source_url": "https://www.sec.gov/mock/one.json",
                "status_code": "0",
                "purpose": "committed fixture",
                "repo_relative_path": "",
                "headers_repo_relative_path": "",
                "content_length": "0",
                "content_sha256": "",
                "accession": "",
                "document_name": "one.json",
                "user_agent": "fixture fixture@example.com",
                "retry_attempt": "0",
                "error": "transport failure",
            }
            rows = [
                base,
                {
                    **base,
                    "source_url": "https://www.sec.gov/mock/two.json",
                    "document_name": "two.json",
                },
            ]
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows,
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            contract_alignment.git_output(
                repo_root=workspace,
                arguments=["init"],
            )
            contract_alignment.git_output(
                repo_root=workspace,
                arguments=["add", "evidence"],
            )
            contract_alignment.git_output(
                repo_root=workspace,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=list(reversed(rows)),
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            with patched_workspace(workspace=workspace):
                reordered = sec_pipeline.check_requests_log_sec_only()
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows[:1],
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            with patched_workspace(workspace=workspace):
                removed = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(reordered["status"], "FAIL")
        self.assertIn(
            "committed_request_log_prefix_mismatch",
            reordered["details"],
        )
        self.assertEqual(removed["status"], "FAIL")
        self.assertIn(
            "committed_request_log_prefix_mismatch",
            removed["details"],
        )

    def test_request_log_without_git_history_is_not_evaluated(self) -> None:
        """A self-signed ledger cannot borrow history through Git variables."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            log_path = workspace / "evidence" / "requests_log.csv"
            log_path.parent.mkdir(parents=True)
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=[
                    {
                        "timestamp_utc": "2026-07-22T00:00:00+00:00",
                        "method": "GET",
                        "source_url": "https://www.sec.gov/mock/one.json",
                        "status_code": "0",
                        "purpose": "uncommitted fixture",
                        "repo_relative_path": "",
                        "headers_repo_relative_path": "",
                        "content_length": "0",
                        "content_sha256": "",
                        "accession": "",
                        "document_name": "one.json",
                        "user_agent": "fixture fixture@example.com",
                        "retry_attempt": "0",
                        "error": "transport failure",
                    }
                ],
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            overrides = {
                "GIT_DIR": str(REPO_ROOT / ".git"),
                "GIT_WORK_TREE": str(REPO_ROOT),
            }
            with patched_workspace(workspace=workspace), mock.patch.dict(
                os.environ,
                overrides,
                clear=False,
            ):
                result = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(
            result["status"],
            "NOT_EVALUATED_MISSING_EVIDENCE",
        )
        self.assertIn(
            "request_log_history_baseline_unavailable",
            result["details"],
        )

    def test_parent_repository_cannot_supply_request_history(self) -> None:
        """A nested workspace cannot borrow its parent repository ledger."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "parent"
            workspace = parent / "nested"
            parent_log = parent / "evidence" / "requests_log.csv"
            nested_log = workspace / "evidence" / "requests_log.csv"
            row = {
                "timestamp_utc": "2026-07-22T00:00:00+00:00",
                "method": "GET",
                "source_url": "https://www.sec.gov/mock/one.json",
                "status_code": "0",
                "purpose": "nested fixture",
                "repo_relative_path": "",
                "headers_repo_relative_path": "",
                "content_length": "0",
                "content_sha256": "",
                "accession": "",
                "document_name": "one.json",
                "user_agent": "fixture fixture@example.com",
                "retry_attempt": "0",
                "error": "transport failure",
            }
            parent.mkdir()
            contract_alignment.git_output(
                repo_root=parent,
                arguments=["init"],
            )
            parent_log.parent.mkdir()
            write_rows(
                path=parent_log,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=[row],
            )
            contract_alignment.git_output(
                repo_root=parent,
                arguments=["add", "evidence/requests_log.csv"],
            )
            contract_alignment.git_output(
                repo_root=parent,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            nested_log.parent.mkdir(parents=True)
            write_rows(
                path=nested_log,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=[row],
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=nested_log,
            )
            with patched_workspace(workspace=workspace):
                result = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(
            result["status"],
            "NOT_EVALUATED_MISSING_EVIDENCE",
        )
        self.assertIn(
            "request_log_history_baseline_unavailable",
            result["details"],
        )

    def test_migration_cannot_bless_deleted_observation(self) -> None:
        """Migration must validate the old exact set before normalizing it."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            result = sec_http.FetchResult(
                url="https://www.sec.gov/mock/sample.json",
                status_code=0,
                local_path="",
                sha256="",
                content_length=0,
                headers_path="",
                error="transport failure",
            )
            client._append_log_row(
                result=result,
                purpose="first fixture",
                attempt=0,
            )
            client._append_log_row(
                result=result,
                purpose="second fixture",
                attempt=1,
            )
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            manifest_bytes = manifest_path.read_bytes()
            rows = read_rows(path=client.log_path)
            rows[1]["repo_relative_path"] = str(
                workspace / "evidence" / "raw" / "sample.json"
            )
            write_rows(
                path=client.log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows[1:],
            )
            tampered_log_bytes = client.log_path.read_bytes()
            with self.assertRaises(ValueError):
                sec_http.migrate_request_log(
                    log_path=client.log_path,
                    workdir=workspace,
                    allow_legacy_bootstrap=False,
                )
            retained_log_bytes = client.log_path.read_bytes()
            retained_manifest_bytes = manifest_path.read_bytes()
        self.assertEqual(retained_log_bytes, tampered_log_bytes)
        self.assertEqual(retained_manifest_bytes, manifest_bytes)

    def test_downgraded_current_log_cannot_bootstrap_manifest(self) -> None:
        """A shrunk current log cannot masquerade as legacy data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            result = sec_http.FetchResult(
                url="https://www.sec.gov/mock/sample.json",
                status_code=0,
                local_path="",
                sha256="",
                content_length=0,
                headers_path="",
                error="transport failure",
            )
            client._append_log_row(
                result=result,
                purpose="first fixture",
                attempt=0,
            )
            client._append_log_row(
                result=result,
                purpose="second fixture",
                attempt=1,
            )
            survivor = read_rows(path=client.log_path)[1]
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            manifest_path.unlink()
            legacy_row = {
                "timestamp_utc": survivor["timestamp_utc"],
                "method": survivor["method"],
                "url": survivor["source_url"],
                "status_code": survivor["status_code"],
                "purpose": survivor["purpose"],
                "local_path": survivor["repo_relative_path"],
                "headers_path": survivor["headers_repo_relative_path"],
                "content_length": survivor["content_length"],
                "sha256": survivor["content_sha256"],
                "user_agent": survivor["user_agent"],
                "retry_attempt": survivor["retry_attempt"],
                "error": survivor["error"],
            }
            write_rows(
                path=client.log_path,
                fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                rows=[legacy_row],
            )
            downgraded_bytes = client.log_path.read_bytes()
            with self.assertRaises(PermissionError):
                sec_http.migrate_request_log(
                    log_path=client.log_path,
                    workdir=workspace,
                    allow_legacy_bootstrap=False,
                )
            with self.assertRaises(PermissionError):
                sec_http.SecHttpClient(
                    workdir=workspace,
                    config_path=workspace / "config" / "sec_config.json",
                    log_path=client.log_path,
                )
            retained_bytes = client.log_path.read_bytes()
            manifest_exists = manifest_path.exists()
        self.assertEqual(retained_bytes, downgraded_bytes)
        self.assertFalse(manifest_exists)

    def test_manifest_only_state_cannot_reset_request_history(self) -> None:
        """Deleting the CSV cannot reset a retained manifest to zero rows."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            result = sec_http.FetchResult(
                url="https://www.sec.gov/mock/sample.json",
                status_code=0,
                local_path="",
                sha256="",
                content_length=0,
                headers_path="",
                error="transport failure",
            )
            client._append_log_row(
                result=result,
                purpose="first fixture",
                attempt=0,
            )
            client._append_log_row(
                result=result,
                purpose="second fixture",
                attempt=1,
            )
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            manifest_bytes = manifest_path.read_bytes()
            client.log_path.unlink()
            with self.assertRaises(FileNotFoundError):
                sec_http.SecHttpClient(
                    workdir=workspace,
                    config_path=workspace / "config" / "sec_config.json",
                    log_path=client.log_path,
                )
            log_exists = client.log_path.exists()
            retained_manifest_bytes = manifest_path.read_bytes()
        self.assertFalse(log_exists)
        self.assertEqual(retained_manifest_bytes, manifest_bytes)

    def test_current_log_without_manifest_cannot_be_reinitialized(
        self,
    ) -> None:
        """A current-schema CSV without its manifest must fail closed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            client = build_http_client(workspace=workspace)
            log_bytes = client.log_path.read_bytes()
            manifest_path = sec_http.request_log_manifest_path(
                log_path=client.log_path
            )
            manifest_path.unlink()
            with self.assertRaises(FileNotFoundError):
                sec_http.SecHttpClient(
                    workdir=workspace,
                    config_path=workspace / "config" / "sec_config.json",
                    log_path=client.log_path,
                )
            retained_log_bytes = client.log_path.read_bytes()
            manifest_exists = manifest_path.exists()
        self.assertEqual(retained_log_bytes, log_bytes)
        self.assertFalse(manifest_exists)

    def test_body_url_cannot_be_resigned_to_another_document(self) -> None:
        """URL, sidecar, body name, and document name remain jointly bound."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            config_path = workspace / "config" / "sec_config.json"
            log_path = workspace / "evidence" / "requests_log.csv"
            response_path = workspace / "evidence" / "raw" / "sample.xml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "organization": "fixture",
                        "contact_email": "fixture@example.com",
                        "rate_limit_per_sec": 10,
                        "max_retries": 0,
                        "backoff_initial_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )
            client = sec_http.SecHttpClient(
                workdir=workspace,
                config_path=config_path,
                log_path=log_path,
            )
            result = client._persist_result(
                url=(
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000001/sample.xml"
                ),
                status_code=200,
                body=b"body",
                headers={"Content-Type": "application/xml"},
                local_path=response_path,
                error="",
            )
            client._append_log_row(result=result, purpose="fixture", attempt=0)
            rows = read_rows(path=log_path)
            headers_path = Path(result.headers_path)
            payload = json.loads(headers_path.read_text(encoding="utf-8"))
            payload["url"] = (
                "https://www.sec.gov/Archives/edgar/data/1/"
                "000000000126000001/other.xml"
            )
            changed_bytes = json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            changed_hash = hashlib.sha256(changed_bytes).hexdigest()
            changed_path = headers_path.with_name(
                f"{Path(result.local_path).name}.{changed_hash}.headers.json"
            )
            changed_path.write_bytes(changed_bytes)
            rows[0]["source_url"] = payload["url"]
            rows[0]["headers_repo_relative_path"] = str(
                changed_path.relative_to(workspace)
            )
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=rows,
            )
            sec_http.refresh_request_log_manifest(
                workdir=workspace,
                log_path=log_path,
            )
            with patched_workspace(workspace=workspace):
                check = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(check["status"], "FAIL")
        self.assertIn("document_name_mismatch", check["details"])

    def test_legacy_request_log_migrates_to_portable_schema(self) -> None:
        """Legacy URL/path/hash fields must migrate without losing identity."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            clone_a = root / "evidence" / "clone_a"
            clone_b = root / "clone_b"
            source_url = (
                "https://www.sec.gov/Archives/edgar/data/"
                "1108524/000110852426000060/sample.xml"
            )
            timestamp = "2026-07-22T00:00:00+00:00"
            body = b"data"
            body_path = clone_b / "evidence" / "raw" / "sample.xml"
            headers_path = body_path.with_name("sample.xml.headers.json")
            request_row = legacy_request_row(
                source_url=source_url,
                legacy_root=clone_a / "evidence" / "raw",
                document_name="sample.xml",
                headers_name="sample.xml.headers.json",
                body=body,
                timestamp_utc=timestamp,
            )
            digest = request_row["sha256"]
            log_path = clone_b / "evidence" / "requests_log.csv"
            log_path.parent.mkdir(parents=True)
            body_path.parent.mkdir(parents=True, exist_ok=True)
            body_path.write_bytes(body)
            headers_path.write_text(
                json.dumps(
                    {
                        "url": source_url,
                        "status_code": 200,
                        "headers": {},
                        "content_length": len(body),
                        "sha256": digest,
                        "saved_at_utc": timestamp,
                    }
                ),
                encoding="utf-8",
            )
            write_rows(
                path=log_path,
                fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                rows=[request_row],
            )
            with self.assertRaises(PermissionError):
                sec_http.migrate_request_log(
                    log_path=log_path,
                    workdir=clone_b,
                    allow_legacy_bootstrap=False,
                )
            external_path = root / "external.txt"
            external_path.write_bytes(b"outside")
            fixed_temporary_path = log_path.with_name(log_path.name + ".tmp")
            os.link(src=external_path, dst=fixed_temporary_path)
            sec_http.migrate_request_log(
                log_path=log_path,
                workdir=clone_b,
                allow_legacy_bootstrap=True,
            )
            sec_http.validate_request_log_manifest(log_path=log_path)
            contract_alignment.git_output(
                repo_root=clone_b,
                arguments=["init"],
            )
            contract_alignment.git_output(
                repo_root=clone_b,
                arguments=["add", "."],
            )
            contract_alignment.git_output(
                repo_root=clone_b,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            with patched_workspace(workspace=clone_b):
                check = sec_pipeline.check_requests_log_sec_only()
            rows = read_rows(path=log_path)
            header = list(rows[0])
            retained_external_bytes = external_path.read_bytes()
            retained_temporary_bytes = fixed_temporary_path.read_bytes()
        self.assertEqual(header, sec_http.REQUEST_LOG_FIELDNAMES)
        self.assertEqual(
            rows[0]["repo_relative_path"],
            "evidence/raw/sample.xml",
        )
        self.assertEqual(rows[0]["content_sha256"], digest)
        self.assertEqual(rows[0]["accession"], "0001108524-26-000060")
        self.assertEqual(rows[0]["document_name"], "sample.xml")
        self.assertNotIn(str(clone_a), str(rows[0]))
        self.assertEqual(retained_external_bytes, b"outside")
        self.assertEqual(retained_temporary_bytes, b"outside")
        self.assertEqual(check["status"], "PASS")

    def test_repeated_anchor_request_log_fails_when_identity_is_ambiguous(
        self,
    ) -> None:
        """Reject two matching request bodies under repeated anchors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "clone_b"
            direct_path = workspace / "evidence" / "raw" / "sample.xml"
            nested_path = (
                workspace
                / "evidence"
                / "oldclone"
                / "evidence"
                / "raw"
                / "sample.xml"
            )
            direct_path.parent.mkdir(parents=True)
            nested_path.parent.mkdir(parents=True)
            body = b"same-request"
            direct_path.write_bytes(body)
            nested_path.write_bytes(body)
            source_url = "https://www.sec.gov/Archives/sample.xml"
            log_path = workspace / "evidence" / "requests_log.csv"
            request_row = legacy_request_row(
                source_url=source_url,
                legacy_root=(
                    root / "evidence" / "oldclone" / "evidence" / "raw"
                ),
                document_name="sample.xml",
                headers_name="",
                body=body,
                timestamp_utc="2026-07-23T00:00:00+00:00",
            )
            write_rows(
                path=log_path,
                fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                rows=[request_row],
            )
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                sec_http.migrate_request_log(
                    log_path=log_path,
                    workdir=workspace,
                    allow_legacy_bootstrap=True,
                )

    def test_repeated_anchor_request_log_rejects_mixed_legacy_roots(
        self,
    ) -> None:
        """Body and headers must relocate from one former repository root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "clone_b"
            body = b"verified-body"
            source_url = "https://www.sec.gov/Archives/sample.xml"
            timestamp = "2026-07-23T00:00:00+00:00"
            request_row = legacy_request_row(
                source_url=source_url,
                legacy_root=(
                    root / "evidence" / "oldclone" / "evidence" / "raw"
                ),
                document_name="sample.xml",
                headers_name="sample.xml.headers.json",
                body=body,
                timestamp_utc=timestamp,
            )
            direct_body = workspace / "evidence" / "raw" / "sample.xml"
            nested_headers = (
                workspace
                / "evidence"
                / "oldclone"
                / "evidence"
                / "raw"
                / "sample.xml.headers.json"
            )
            direct_body.parent.mkdir(parents=True)
            nested_headers.parent.mkdir(parents=True)
            direct_body.write_bytes(body)
            nested_headers.write_text(
                json.dumps(
                    {
                        "url": source_url,
                        "status_code": 200,
                        "headers": {},
                        "content_length": len(body),
                        "sha256": request_row["sha256"],
                        "saved_at_utc": timestamp,
                    }
                ),
                encoding="utf-8",
            )
            log_path = workspace / "evidence" / "requests_log.csv"
            write_rows(
                path=log_path,
                fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                rows=[request_row],
            )
            with self.assertRaisesRegex(
                ValueError,
                "different legacy repository roots",
            ):
                sec_http.migrate_request_log(
                    log_path=log_path,
                    workdir=workspace,
                    allow_legacy_bootstrap=True,
                )

    def test_legacy_request_path_cannot_escape_repository(self) -> None:
        """Request-log migration must reject parent traversal in old hints."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()
            with self.assertRaises(ValueError):
                sec_http.repo_relative_request_path(
                    workdir=workspace,
                    path_text=(
                        "/old/clone/evidence/../../../../../../etc/hosts"
                    ),
                    content_sha256="fixture",
                    source_url="https://www.sec.gov/fixture",
                    status_code="200",
                    content_length="7",
                    document_name="hosts",
                    is_headers=False,
                )

    def test_repeated_request_paths_keep_each_response_bytes(self) -> None:
        """Two attempts at one logical path retain distinct immutable bytes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            config_path = workspace / "config" / "sec_config.json"
            log_path = workspace / "evidence" / "requests_log.csv"
            response_path = workspace / "evidence" / "raw" / "sample.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "organization": "fixture",
                        "contact_email": "fixture@example.com",
                        "rate_limit_per_sec": 10,
                        "max_retries": 0,
                        "backoff_initial_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )
            client = sec_http.SecHttpClient(
                workdir=workspace,
                config_path=config_path,
                log_path=log_path,
            )
            first = client._persist_result(
                url="https://www.sec.gov/mock/sample.json",
                status_code=503,
                body=b"first",
                headers={"Content-Type": "application/json"},
                local_path=response_path,
                error="retryable",
            )
            client._append_log_row(
                result=first,
                purpose="fixture",
                attempt=0,
            )
            second = client._persist_result(
                url="https://www.sec.gov/mock/sample.json",
                status_code=200,
                body=b"second",
                headers={"Content-Type": "application/json"},
                local_path=response_path,
                error="",
            )
            client._append_log_row(
                result=second,
                purpose="fixture",
                attempt=1,
            )
            rows = read_rows(path=log_path)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "committed_request_observation_sequence",
                return_value=[],
            ):
                check = sec_pipeline.check_requests_log_sec_only()
            first_bytes = Path(first.local_path).read_bytes()
            second_bytes = Path(second.local_path).read_bytes()
            current_bytes = response_path.read_bytes()
        self.assertNotEqual(first.local_path, second.local_path)
        self.assertEqual(first_bytes, b"first")
        self.assertEqual(second_bytes, b"second")
        self.assertEqual(current_bytes, b"second")
        self.assertNotEqual(
            rows[0]["repo_relative_path"],
            rows[1]["repo_relative_path"],
        )
        self.assertEqual(check["status"], "PASS")

    def test_immutable_headers_and_log_metadata_tampering_cannot_pass(
        self,
    ) -> None:
        """Each sidecar and metadata mutation reaches its intended gate."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            config_path = workspace / "config" / "sec_config.json"
            log_path = workspace / "evidence" / "requests_log.csv"
            response_path = workspace / "evidence" / "raw" / "sample.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "organization": "fixture",
                        "contact_email": "fixture@example.com",
                        "rate_limit_per_sec": 10,
                        "max_retries": 0,
                        "backoff_initial_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )
            client = sec_http.SecHttpClient(
                workdir=workspace,
                config_path=config_path,
                log_path=log_path,
            )
            result = client._persist_result(
                url="https://www.sec.gov/mock/sample.json",
                status_code=200,
                body=b"body",
                headers={"Content-Type": "application/json"},
                local_path=response_path,
                error="",
            )
            client._append_log_row(result=result, purpose="fixture", attempt=0)
            headers_path = Path(result.headers_path)
            original_headers = headers_path.read_bytes()
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "committed_request_observation_sequence",
                return_value=[],
            ):
                baseline = sec_pipeline.check_requests_log_sec_only()
                headers_path.write_bytes(original_headers + b" ")
                sidecar_check = sec_pipeline.check_requests_log_sec_only()
                headers_path.write_bytes(original_headers)
                rows = read_rows(path=log_path)
                headers_payload = json.loads(
                    original_headers.decode("utf-8")
                )
                headers_payload["content_length"] += 1
                changed_headers = json.dumps(
                    headers_payload,
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8")
                changed_headers_hash = hashlib.sha256(
                    changed_headers
                ).hexdigest()
                body_name = Path(result.local_path).name
                changed_headers_path = headers_path.with_name(
                    f"{body_name}.{changed_headers_hash}.headers.json"
                )
                changed_headers_path.write_bytes(changed_headers)
                rows[0]["headers_repo_relative_path"] = str(
                    changed_headers_path.relative_to(workspace)
                )
                write_rows(
                    path=log_path,
                    fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                    rows=rows,
                )
                sec_http.refresh_request_log_manifest(
                    workdir=workspace,
                    log_path=log_path,
                )
                crosscheck = sec_pipeline.check_requests_log_sec_only()
                original_row = rows[0]
                original_row["headers_repo_relative_path"] = str(
                    headers_path.relative_to(workspace)
                )
                metadata_checks = []
                for updates in [
                    {"method": "POST"},
                    {"status_code": "not-a-status"},
                    {"retry_attempt": "-1"},
                    {"error": "forged"},
                ]:
                    mutated_row = {**original_row, **updates}
                    write_rows(
                        path=log_path,
                        fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                        rows=[mutated_row],
                    )
                    sec_http.refresh_request_log_manifest(
                        workdir=workspace,
                        log_path=log_path,
                    )
                    metadata_checks.append(
                        sec_pipeline.check_requests_log_sec_only()
                    )
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(
            sidecar_check["status"],
            "NOT_EVALUATED_MISSING_EVIDENCE",
        )
        self.assertIn(
            "response_headers_hash_mismatch",
            sidecar_check["details"],
        )
        self.assertEqual(
            crosscheck["status"],
            "NOT_EVALUATED_MISSING_EVIDENCE",
        )
        self.assertIn(
            "response_headers_observation_mismatch",
            crosscheck["details"],
        )
        self.assertEqual(
            [check["status"] for check in metadata_checks],
            ["FAIL", "FAIL", "FAIL", "FAIL"],
        )
        self.assertIn("invalid_request_metadata",
                      metadata_checks[0]["details"])
        self.assertIn("invalid_numeric_metadata",
                      metadata_checks[1]["details"])
        self.assertIn("invalid_numeric_metadata",
                      metadata_checks[2]["details"])
        self.assertIn("status_error_mismatch", metadata_checks[3]["details"])

    def test_request_hash_mismatch_is_not_evaluated(self) -> None:
        """Changing proven response bytes emits the hash-mismatch diagnostic."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            config_path = workspace / "config" / "sec_config.json"
            log_path = workspace / "evidence" / "requests_log.csv"
            response_path = workspace / "evidence" / "raw" / "sample.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "organization": "fixture",
                        "contact_email": "fixture@example.com",
                        "rate_limit_per_sec": 10,
                        "max_retries": 0,
                        "backoff_initial_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )
            client = sec_http.SecHttpClient(
                workdir=workspace,
                config_path=config_path,
                log_path=log_path,
            )
            result = client._persist_result(
                url="https://www.sec.gov/mock/sample.json",
                status_code=200,
                body=b"body",
                headers={"Content-Type": "application/json"},
                local_path=response_path,
                error="",
            )
            client._append_log_row(
                result=result,
                purpose="fixture",
                attempt=0,
            )
            immutable_body = Path(result.local_path)
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "committed_request_observation_sequence",
                return_value=[],
            ):
                baseline = sec_pipeline.check_requests_log_sec_only()
                immutable_body.write_bytes(b"evil")
                mismatch = sec_pipeline.check_requests_log_sec_only()
                immutable_body.write_bytes(b"body")
                restored = sec_pipeline.check_requests_log_sec_only()
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(
            mismatch["status"],
            "NOT_EVALUATED_MISSING_EVIDENCE",
        )
        self.assertIn("response_body_hash_mismatch", mismatch["details"])
        self.assertEqual(restored["status"], "PASS")

    def test_transport_failure_still_validates_url_identity(self) -> None:
        """A bodyless attempt must retain URL-derived accession and name."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            log_path = workspace / "evidence" / "requests_log.csv"
            log_path.parent.mkdir(parents=True)
            source_url = (
                "https://www.sec.gov/Archives/edgar/data/1/"
                "000000000126000001/sample.xml"
            )
            base_row = {
                "timestamp_utc": "2026-07-22T00:00:00+00:00",
                "method": "GET",
                "source_url": source_url,
                "status_code": "0",
                "purpose": "fixture",
                "repo_relative_path": "",
                "headers_repo_relative_path": "",
                "content_length": "0",
                "content_sha256": "",
                "accession": "0000000001-26-000001",
                "document_name": "sample.xml",
                "user_agent": "fixture fixture@example.com",
                "retry_attempt": "0",
                "error": "transport failure",
            }
            checks = []
            for updates in [
                {"accession": "9999999999-99-999999"},
                {"document_name": "wrong.xml"},
            ]:
                write_rows(
                    path=log_path,
                    fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                    rows=[{**base_row, **updates}],
                )
                with patched_workspace(workspace=workspace):
                    checks.append(sec_pipeline.check_requests_log_sec_only())
        self.assertTrue(all(check["status"] == "FAIL" for check in checks))


class CapabilityContractAlignmentTest(unittest.TestCase):
    """Validate the persistent mechanical capability-contract checker."""

    def test_live_contract_alignment(self) -> None:
        """The current contract, Markdown anchors, paths, and symbols align."""
        payload = contract_alignment.read_contract(
            path=REPO_ROOT / "capability_contract.json",
        )
        tracked_paths = set(
            contract_alignment.git_committed_entries(repo_root=REPO_ROOT)
        )
        errors = contract_alignment.alignment_errors(
            repo_root=REPO_ROOT,
            payload=payload,
            tracked_paths=tracked_paths,
        )
        self.assertEqual(errors, [])

    def test_parent_repository_cannot_define_checker_head(self) -> None:
        """A nested directory cannot borrow its parent repository HEAD."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "parent"
            nested_root = repo_root / "nested"
            contract_text = json.dumps(
                {
                    "deprecated_anchor_ids": [],
                    "contracts": {"capabilities": []},
                }
            )
            repo_root.mkdir()
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            (repo_root / "capability_contract.json").write_text(
                contract_text,
                encoding="utf-8",
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "capability_contract.json"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            nested_root.mkdir()
            nested_contract = nested_root / "capability_contract.json"
            nested_contract.write_text(contract_text, encoding="utf-8")
            errors = contract_alignment.check_alignment(
                repo_root=nested_root,
                contract_path=nested_contract,
            )
        self.assertEqual(
            errors,
            [".git must be a local directory or linked-worktree gitfile"],
        )

    def test_git_environment_cannot_lend_head_to_non_repository(self) -> None:
        """Inherited Git selectors cannot make an archive look committed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "not-a-repository"
            repo_root.mkdir()
            overrides = {
                "GIT_DIR": str(REPO_ROOT / ".git"),
                "GIT_WORK_TREE": str(REPO_ROOT),
            }
            with mock.patch.dict(os.environ, overrides, clear=False):
                with self.assertRaises(RuntimeError):
                    contract_alignment.git_repository_toplevel(
                        repo_root=repo_root,
                    )

    def test_borrowed_dot_git_is_rejected_but_linked_worktree_passes(
        self,
    ) -> None:
        """Only Git's registered linked-worktree metadata may be indirect."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            borrowed = root / "borrowed"
            borrowed.mkdir()
            contract_path = borrowed / "capability_contract.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "deprecated_anchor_ids": [],
                        "contracts": {"capabilities": []},
                    }
                ),
                encoding="utf-8",
            )
            dot_git = borrowed / ".git"
            dot_git.symlink_to(REPO_ROOT / ".git", target_is_directory=True)
            symlink_errors = contract_alignment.check_alignment(
                repo_root=borrowed,
                contract_path=contract_path,
            )
            dot_git.unlink()
            dot_git.write_text(
                f"gitdir: {REPO_ROOT / '.git'}\n",
                encoding="utf-8",
            )
            gitfile_errors = contract_alignment.check_alignment(
                repo_root=borrowed,
                contract_path=contract_path,
            )

            main = root / "main"
            linked = root / "linked"
            main.mkdir()
            contract_alignment.git_output(
                repo_root=main,
                arguments=["init"],
            )
            (main / "capability_contract.json").write_text(
                contract_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            contract_alignment.git_output(
                repo_root=main,
                arguments=["add", "capability_contract.json"],
            )
            contract_alignment.git_output(
                repo_root=main,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            contract_alignment.git_output(
                repo_root=main,
                arguments=[
                    "worktree",
                    "add",
                    "--detach",
                    str(linked),
                    "HEAD",
                ],
            )
            linked_errors = contract_alignment.check_alignment(
                repo_root=linked,
                contract_path=linked / "capability_contract.json",
            )
            expected_head = contract_alignment.git_output(
                repo_root=main,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            dot_git = linked / ".git"
            gitdir = Path(
                dot_git.read_text(encoding="utf-8")
                .strip()
                .removeprefix("gitdir: ")
            )
            real_gitdir = gitdir.with_name(gitdir.name + "-real")
            gitdir.rename(real_gitdir)
            gitdir.symlink_to(real_gitdir.name, target_is_directory=True)
            alias_head = contract_alignment.git_output(
                repo_root=linked,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            alias_errors = contract_alignment.check_alignment(
                repo_root=linked,
                contract_path=linked / "capability_contract.json",
            )
            with mock.patch.object(sec_pipeline, "WORKDIR", linked):
                source_commit = sec_pipeline.current_source_commit()
                with self.assertRaises(FileNotFoundError):
                    sec_pipeline.committed_request_observation_sequence()
            gitdir.unlink()
            real_gitdir.rename(gitdir)

            registration_parent = gitdir.parent
            real_registration_parent = registration_parent.with_name(
                registration_parent.name + "-real"
            )
            registration_parent.rename(real_registration_parent)
            registration_parent.symlink_to(
                real_registration_parent.name,
                target_is_directory=True,
            )
            intermediate_head = contract_alignment.git_output(
                repo_root=linked,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            intermediate_errors = contract_alignment.check_alignment(
                repo_root=linked,
                contract_path=linked / "capability_contract.json",
            )
            registration_parent.unlink()
            real_registration_parent.rename(registration_parent)

            alias_root = root / "alias-root"
            alias_root.symlink_to(root, target_is_directory=True)
            (gitdir / "commondir").write_text(
                str(alias_root / "main" / ".git") + "\n",
                encoding="utf-8",
            )
            common_head = contract_alignment.git_output(
                repo_root=linked,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            common_errors = contract_alignment.check_alignment(
                repo_root=linked,
                contract_path=linked / "capability_contract.json",
            )
        self.assertEqual(symlink_errors, [".git must not be a symlink"])
        self.assertEqual(
            gitfile_errors,
            [".git file is not a valid linked-worktree registration"],
        )
        self.assertEqual(linked_errors, [])
        self.assertEqual(alias_head, expected_head)
        self.assertTrue(alias_errors)
        self.assertIn("symlink", alias_errors[0])
        self.assertEqual(source_commit, "UNAVAILABLE_NON_GIT_WORKSPACE")
        self.assertEqual(intermediate_head, expected_head)
        self.assertTrue(intermediate_errors)
        self.assertIn("symlink", intermediate_errors[0])
        self.assertEqual(common_head, expected_head)
        self.assertTrue(common_errors)
        self.assertIn("symlink", common_errors[0])

    def test_legacy_request_history_rejects_ambiguous_anchor_identity(
        self,
    ) -> None:
        """Independent checker must fail when two suffixes match the body."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "clone_b"
            direct_path = repo_root / "evidence" / "raw" / "sample.xml"
            nested_path = (
                repo_root
                / "evidence"
                / "oldclone"
                / "evidence"
                / "raw"
                / "sample.xml"
            )
            direct_path.parent.mkdir(parents=True)
            nested_path.parent.mkdir(parents=True)
            body = b"same-checker-body"
            direct_path.write_bytes(body)
            nested_path.write_bytes(body)
            row = legacy_request_row(
                source_url="https://www.sec.gov/Archives/sample.xml",
                legacy_root=(
                    root / "evidence" / "oldclone" / "evidence" / "raw"
                ),
                document_name="sample.xml",
                headers_name="",
                body=body,
                timestamp_utc="2026-07-23T00:00:00+00:00",
            )
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                contract_alignment.normalized_legacy_request_history_row(
                    repo_root=repo_root,
                    row=row,
                )

    def test_legacy_request_history_rejects_mixed_legacy_roots(
        self,
    ) -> None:
        """Independent history gate rejects cross-root body/header pairs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "clone_b"
            body = b"checker-body"
            source_url = "https://www.sec.gov/Archives/sample.xml"
            timestamp = "2026-07-23T00:00:00+00:00"
            row = legacy_request_row(
                source_url=source_url,
                legacy_root=(
                    root / "evidence" / "oldclone" / "evidence" / "raw"
                ),
                document_name="sample.xml",
                headers_name="sample.xml.headers.json",
                body=body,
                timestamp_utc=timestamp,
            )
            body_path = repo_root / "evidence" / "raw" / "sample.xml"
            headers_path = (
                repo_root
                / "evidence"
                / "oldclone"
                / "evidence"
                / "raw"
                / "sample.xml.headers.json"
            )
            body_path.parent.mkdir(parents=True)
            headers_path.parent.mkdir(parents=True)
            body_path.write_bytes(body)
            headers_path.write_text(
                json.dumps(
                    {
                        "url": source_url,
                        "status_code": 200,
                        "content_length": len(body),
                        "sha256": row["sha256"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "different legacy repository roots",
            ):
                contract_alignment.normalized_legacy_request_history_row(
                    repo_root=repo_root,
                    row=row,
                )

    def test_checker_rejects_borrowed_git_object_store(self) -> None:
        """A local `.git` cannot delegate HEAD objects to another repo."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            donor = root / "donor"
            donor.mkdir()
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {"capabilities": []},
            }
            donor_contract = donor / "capability_contract.json"
            donor_contract.write_text(json.dumps(payload), encoding="utf-8")
            contract_alignment.git_output(
                repo_root=donor,
                arguments=["init"],
            )
            contract_alignment.git_output(
                repo_root=donor,
                arguments=["add", "capability_contract.json"],
            )
            contract_alignment.git_output(
                repo_root=donor,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            donor_head = contract_alignment.git_output(
                repo_root=donor,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            errors_by_case = {}
            for case in ["objects_symlink", "objects_alternates"]:
                borrowed = root / case
                borrowed.mkdir()
                shutil.copy(
                    src=donor_contract,
                    dst=borrowed / "capability_contract.json",
                )
                contract_alignment.git_output(
                    repo_root=borrowed,
                    arguments=["init"],
                )
                object_dir = borrowed / ".git" / "objects"
                if case == "objects_symlink":
                    shutil.rmtree(object_dir)
                    object_dir.symlink_to(
                        donor / ".git" / "objects",
                        target_is_directory=True,
                    )
                else:
                    info_dir = object_dir / "info"
                    info_dir.mkdir(exist_ok=True)
                    (info_dir / "alternates").write_text(
                        str(donor / ".git" / "objects") + "\n",
                        encoding="utf-8",
                    )
                contract_alignment.git_output(
                    repo_root=borrowed,
                    arguments=["update-ref", "refs/heads/main", donor_head],
                )
                contract_alignment.git_output(
                    repo_root=borrowed,
                    arguments=["symbolic-ref", "HEAD", "refs/heads/main"],
                )
                errors_by_case[case] = contract_alignment.check_alignment(
                    repo_root=borrowed,
                    contract_path=borrowed / "capability_contract.json",
                )
        self.assertTrue(errors_by_case["objects_symlink"])
        self.assertTrue(errors_by_case["objects_alternates"])
        self.assertIn(
            "object store",
            errors_by_case["objects_symlink"][0],
        )
        self.assertIn(
            "alternates",
            errors_by_case["objects_alternates"][0],
        )

    def test_malformed_anchor_ids_and_directives_fail_closed(self) -> None:
        """Invalid grammar cannot disappear from the checker input set."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            markdown_path = repo_root / "proof.md"
            markdown_path.write_text(
                "<!-- capability-anchor: CAPABILITY.bad/id -->\n",
                encoding="utf-8",
            )
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [
                        {
                            "anchor_id": "CAPABILITY.bad/id",
                            "status": "active",
                            "type": "capability",
                            "test_anchor": None,
                            "untested_reason": "fixture",
                            "pending_since": "2026-07-23",
                        }
                    ]
                },
            }
            errors = contract_alignment.alignment_errors(
                repo_root=repo_root,
                payload=payload,
                tracked_paths={Path("proof.md")},
            )
            bad_registry = {
                "deprecated_anchor_ids": ["CAPABILITY.bad/id"],
                "contracts": {"capabilities": []},
            }
            with self.assertRaises(TypeError):
                contract_alignment.alignment_errors(
                    repo_root=repo_root,
                    payload=bad_registry,
                    tracked_paths={Path("proof.md")},
                )
        self.assertIn(
            "contract entry anchor_id must be a valid anchor id",
            errors,
        )
        self.assertTrue(
            any(
                "malformed capability-anchor directive" in error
                for error in errors
            )
        )

    def test_untracked_contract_evidence_is_rejected(self) -> None:
        """Untracked test, document, and Markdown cannot prove a claim."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            proof = repo_root / "proof.py"
            document = repo_root / "proof.md"
            proof.write_text("def proof():\n    pass\n", encoding="utf-8")
            document.write_text(
                "<!-- capability-anchor: UNKNOWN.untracked -->\n",
                encoding="utf-8",
            )
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [
                        {
                            "anchor_id": "CAPABILITY.test",
                            "status": "active",
                            "test_anchor": "proof.py::proof",
                        },
                        {
                            "anchor_id": "CAPABILITY.document",
                            "status": "active",
                            "type": "document",
                            "document_path": "proof.md",
                            "test_anchor": None,
                            "untested_reason": "fixture",
                            "pending_since": "2026-07-22",
                        },
                    ]
                },
            }
            errors = contract_alignment.alignment_errors(
                repo_root=repo_root,
                payload=payload,
                tracked_paths=set(),
            )
            references = contract_alignment.markdown_anchor_references(
                repo_root=repo_root,
                tracked_paths=set(),
            )
        self.assertIn(
            "CAPABILITY.test: test file is not committed in HEAD: proof.py",
            errors,
        )
        self.assertIn(
            (
                "CAPABILITY.document: document path is not committed in "
                "HEAD: proof.md"
            ),
            errors,
        )
        self.assertEqual(references, [])

    def test_staged_only_contract_evidence_is_rejected(self) -> None:
        """The Git index cannot substitute for the reviewed HEAD tree."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            committed = repo_root / "committed.txt"
            committed.write_text("fixture\n", encoding="utf-8")
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "committed.txt"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            staged = repo_root / "proof.py"
            staged.write_text("def proof():\n    pass\n", encoding="utf-8")
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "proof.py"],
            )
            committed_paths = set(
                contract_alignment.git_committed_entries(
                    repo_root=repo_root,
                )
            )
        self.assertIn(Path("committed.txt"), committed_paths)
        self.assertNotIn(Path("proof.py"), committed_paths)

    def test_dirty_tracked_evidence_cannot_prove_head(self) -> None:
        """Working-tree symbols cannot prove the reviewed HEAD contract."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            contract_path = repo_root / "capability_contract.json"
            proof_path = repo_root / "proof.py"
            base_payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [
                        {
                            "anchor_id": "CAPABILITY.proof",
                            "status": "active",
                            "test_anchor": "proof.py::old",
                        }
                    ]
                },
            }
            contract_path.write_text(
                json.dumps(base_payload),
                encoding="utf-8",
            )
            proof_path.write_text("def old():\n    pass\n", encoding="utf-8")
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "capability_contract.json", "proof.py"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["update-index", "--assume-unchanged", "proof.py"],
            )
            changed_payload = json.loads(json.dumps(base_payload))
            changed_payload["contracts"]["capabilities"][0][
                "test_anchor"
            ] = "proof.py::new"
            contract_path.write_text(
                json.dumps(changed_payload),
                encoding="utf-8",
            )
            proof_path.write_text(
                "def old():\n    pass\n\ndef new():\n    pass\n",
                encoding="utf-8",
            )
            hidden_diff = contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["diff", "--name-only", "HEAD", "--"],
            ).splitlines()
            errors = contract_alignment.check_alignment(
                repo_root=repo_root,
                contract_path=contract_path,
            )
            alternate_path = repo_root / "alternate.json"
            alternate_path.write_text(
                json.dumps(changed_payload),
                encoding="utf-8",
            )
            contract_path.unlink()
            contract_path.symlink_to("alternate.json")
            symlink_errors = contract_alignment.check_alignment(
                repo_root=repo_root,
                contract_path=contract_path,
            )
        self.assertIn(
            (
                "clean-clone evidence differs from HEAD: "
                "capability_contract.json"
            ),
            errors,
        )
        self.assertIn(
            "clean-clone evidence differs from HEAD: proof.py",
            errors,
        )
        self.assertNotIn("proof.py", hidden_diff)
        self.assertEqual(
            symlink_errors,
            ["capability_contract.json must not be a symlink"],
        )

    def test_git_replacement_ref_cannot_redefine_head_evidence(self) -> None:
        """Local replacement refs cannot rewrite clean-clone blob bytes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            contract_path = repo_root / "capability_contract.json"
            proof_path = repo_root / "proof.py"
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [
                        {
                            "anchor_id": "CAPABILITY.proof",
                            "type": "capability",
                            "status": "active",
                            "test_anchor": "proof.py::proof",
                        }
                    ]
                },
            }
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            proof_path.write_text(
                "def proof():\n    return False\n",
                encoding="utf-8",
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "capability_contract.json", "proof.py"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
            )
            proof_path.write_text(
                "def proof():\n    return True\n",
                encoding="utf-8",
            )
            old_object = contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["rev-parse", "HEAD:proof.py"],
            ).strip()
            new_object = contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["hash-object", "-w", "proof.py"],
            ).strip()
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["replace", old_object, new_object],
            )
            errors = contract_alignment.check_alignment(
                repo_root=repo_root,
                contract_path=contract_path,
            )
        self.assertIn(
            "clean-clone evidence differs from HEAD: proof.py",
            errors,
        )

    def test_symlink_contract_evidence_is_rejected(self) -> None:
        """A tracked symlink cannot borrow an uncommitted target's content."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "actual.py").write_text(
                "def proof():\n    pass\n",
                encoding="utf-8",
            )
            (repo_root / "actual.md").write_text(
                "fixture\n",
                encoding="utf-8",
            )
            (repo_root / "proof.py").symlink_to("actual.py")
            (repo_root / "proof.md").symlink_to("actual.md")
            entry = {
                "anchor_id": "CAPABILITY.symlink",
                "status": "active",
                "type": "document",
                "document_path": "proof.md",
                "test_anchor": "proof.py::proof",
            }
            tracked_paths = {Path("proof.py"), Path("proof.md")}
            test_errors = contract_alignment.test_anchor_errors(
                repo_root=repo_root,
                entry=entry,
                tracked_paths=tracked_paths,
            )
            document_errors = contract_alignment.document_path_errors(
                repo_root=repo_root,
                entry=entry,
                tracked_paths=tracked_paths,
            )
        self.assertEqual(
            test_errors,
            [
                "CAPABILITY.symlink: test file must not be a symlink: "
                "proof.py"
            ],
        )
        self.assertEqual(
            document_errors,
            [
                "CAPABILITY.symlink: document path must not be a symlink: "
                "proof.md"
            ],
        )

    def test_null_metadata_and_missing_document_path_fail(self) -> None:
        """JSON null cannot masquerade as text and documents need a path."""
        payload = {
            "deprecated_anchor_ids": [],
            "contracts": {
                "capabilities": [
                    {
                        "anchor_id": "CAPABILITY.null",
                        "status": "active",
                        "test_anchor": None,
                        "untested_reason": None,
                        "pending_since": None,
                    },
                    {
                        "anchor_id": "CAPABILITY.document",
                        "status": "active",
                        "type": "document",
                        "test_anchor": None,
                        "untested_reason": "fixture",
                        "pending_since": "2026-07-22",
                    },
                ]
            },
        }
        errors = contract_alignment.alignment_errors(
            repo_root=REPO_ROOT,
            payload=payload,
            tracked_paths=set(),
        )
        self.assertIn(
            "CAPABILITY.null: null test_anchor requires untested_reason",
            errors,
        )
        self.assertIn(
            "CAPABILITY.null: null test_anchor requires pending_since",
            errors,
        )
        self.assertIn(
            "CAPABILITY.document: document type requires document_path",
            errors,
        )

    def test_missing_or_unknown_type_and_status_fail(self) -> None:
        """Omitted or padded enum values cannot bypass document checks."""
        base_entry = {
            "anchor_id": "CAPABILITY.fixture",
            "test_anchor": None,
            "untested_reason": "fixture",
            "pending_since": "2026-07-22",
        }
        checks = []
        for updates in [
            {"status": "active"},
            {"status": "active", "type": "document "},
            {"status": "active ", "type": "capability"},
        ]:
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [{**base_entry, **updates}],
                },
            }
            checks.append(
                contract_alignment.alignment_errors(
                    repo_root=REPO_ROOT,
                    payload=payload,
                    tracked_paths=set(),
                )
            )
        self.assertIn(
            "CAPABILITY.fixture: type must be a non-empty string",
            checks[0],
        )
        self.assertTrue(
            any("type must be one of" in error for error in checks[1])
        )
        self.assertTrue(
            any("status must be one of" in error for error in checks[2])
        )

    def test_current_request_history_compares_every_schema_field(self) -> None:
        """Every current locator and observation field is immutable history."""
        base_row = {
            "timestamp_utc": "2026-07-22T00:00:00+00:00",
            "method": "GET",
            "source_url": "https://www.sec.gov/mock/one.json",
            "status_code": "200",
            "purpose": "fixture",
            "repo_relative_path": "evidence/one.json",
            "headers_repo_relative_path": "evidence/one.headers.json",
            "content_length": "7",
            "content_sha256": "abcd",
            "accession": "0000000001-26-000001",
            "document_name": "one.json",
            "user_agent": "fixture fixture@example.com",
            "retry_attempt": "0",
            "error": "",
        }
        base_text = rows_csv_text(
            fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
            rows=[base_row],
        )
        for field in sec_http.REQUEST_LOG_FIELDNAMES:
            with self.subTest(field=field):
                head_row = {**base_row, field: base_row[field] + "-changed"}
                head_text = rows_csv_text(
                    fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                    rows=[head_row],
                )
                with mock.patch.object(
                    contract_alignment,
                    "request_log_at_ref",
                    side_effect=[base_text, head_text],
                ):
                    errors = contract_alignment.request_log_history_errors(
                        repo_root=REPO_ROOT,
                        base_ref="fixture-base",
                    )
                self.assertTrue(
                    any(
                        "request ledger prefix changed since base" in error
                        for error in errors
                    )
                )

    def test_request_history_rejects_wrong_width_in_every_row(self) -> None:
        """Current and legacy prefix or tail rows require exact cell counts."""
        current_row = {
            field: f"{field}-value"
            for field in contract_alignment.CURRENT_REQUEST_HISTORY_FIELDS
        }
        current_row.update({
            "source_url": "https://www.sec.gov/mock/one.json",
            "purpose": "quoted, purpose",
            "error": "",
        })
        legacy_row = {
            field: f"{field}-value"
            for field in contract_alignment.LEGACY_REQUEST_HISTORY_FIELDS
        }
        legacy_row.update({
            "url": "https://www.sec.gov/mock/one.json",
            "purpose": "quoted, purpose",
            "local_path": "",
            "headers_path": "",
            "sha256": "",
            "error": "",
        })
        schemas = [
            (
                "current",
                contract_alignment.CURRENT_REQUEST_HISTORY_FIELDS,
                current_row,
            ),
            (
                "legacy",
                contract_alignment.LEGACY_REQUEST_HISTORY_FIELDS,
                legacy_row,
            ),
        ]
        for schema_name, fieldnames, row in schemas:
            valid_text = rows_csv_text(
                fieldnames=fieldnames,
                rows=[row, {**row, "timestamp_utc": "tail-row"}],
            )
            self.assertEqual(
                len(contract_alignment.request_history_sequence(
                    repo_root=REPO_ROOT,
                    text=valid_text,
                )),
                2,
            )
            for data_row_index in range(2):
                for extra_cell in (True, False):
                    with self.subTest(
                        schema=schema_name,
                        data_row_index=data_row_index,
                        extra_cell=extra_cell,
                    ):
                        malformed_text = csv_text_with_row_width_delta(
                            text=valid_text,
                            data_row_index=data_row_index,
                            extra_cell=extra_cell,
                        )
                        with self.assertRaisesRegex(
                            ValueError,
                            f"row shape at line {data_row_index + 2}",
                        ):
                            contract_alignment.request_history_sequence(
                                repo_root=REPO_ROOT,
                                text=malformed_text,
                            )

    def test_current_history_acceptance_is_not_broader_than_runtime(
        self,
    ) -> None:
        """Checker row-shape acceptance must equal the runtime manifest parser."""
        row = {
            field: f"{field}-value"
            for field in sec_http.REQUEST_LOG_FIELDNAMES
        }
        row.update({
            "source_url": "https://www.sec.gov/mock/one.json",
            "purpose": "quoted, purpose",
            "error": "",
        })
        valid_text = rows_csv_text(
            fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
            rows=[row, {**row, "timestamp_utc": "tail-row"}],
        )
        cases = [("valid", valid_text)]
        for data_row_index in range(2):
            for extra_cell in (True, False):
                cases.append((
                    f"row_{data_row_index}_extra_{extra_cell}",
                    csv_text_with_row_width_delta(
                        text=valid_text,
                        data_row_index=data_row_index,
                        extra_cell=extra_cell,
                    ),
                ))
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "requests_log.csv"
            for case_name, text in cases:
                with self.subTest(case=case_name):
                    # Preserve expected rejection details as data so the test
                    # fails only when the checker is broader than runtime.
                    checker_error = None
                    try:
                        contract_alignment.request_history_sequence(
                            repo_root=REPO_ROOT,
                            text=text,
                        )
                    except ValueError as error:
                        checker_error = error
                    log_path.write_text(text, encoding="utf-8")
                    runtime_error = None
                    try:
                        sec_http.request_log_manifest_payload(
                            log_path=log_path,
                        )
                    except ValueError as error:
                        runtime_error = error
                    self.assertFalse(
                        checker_error is None and runtime_error is not None,
                        (
                            "checker accepted a runtime-rejected row: "
                            f"case={case_name}; runtime_error={runtime_error}"
                        ),
                    )

    def test_base_aware_cli_rejects_malformed_appended_row(self) -> None:
        """The real checker CLI must reject a committed malformed tail row."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            contract_path = repo_root / "capability_contract.json"
            log_path = repo_root / "evidence" / "requests_log.csv"
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            contract_path.write_text(
                json.dumps({
                    "deprecated_anchor_ids": [],
                    "contracts": {"capabilities": []},
                }),
                encoding="utf-8",
            )
            log_path.parent.mkdir(parents=True)
            row = {
                field: f"{field}-value"
                for field in sec_http.REQUEST_LOG_FIELDNAMES
            }
            row.update({
                "source_url": "https://www.sec.gov/mock/one.json",
                "error": "",
            })
            base_text = rows_csv_text(
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=[row],
            )
            log_path.write_text(base_text, encoding="utf-8")
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "."],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "base",
                ],
            )
            base_ref = contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            tail_text = rows_csv_text(
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=[{**row, "timestamp_utc": "tail-row"}],
            )
            malformed_tail = csv_text_with_row_width_delta(
                text=tail_text,
                data_row_index=0,
                extra_cell=True,
            ).splitlines()[1]
            log_path.write_text(
                base_text + malformed_tail + "\n",
                encoding="utf-8",
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "evidence/requests_log.csv"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "malformed tail",
                ],
            )
            result = subprocess.run(
                args=[
                    sys.executable,
                    str(REPO_ROOT / "tools" /
                        "check_capability_contract_alignment.py"),
                    str(repo_root),
                    "--base-ref",
                    base_ref,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("row shape at line 3", result.stdout)

    def test_committed_request_history_rejects_extra_cells(self) -> None:
        """Runtime HEAD baseline parsing must reject overflow CSV cells."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            log_path = repo_root / "evidence" / "requests_log.csv"
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            log_path.parent.mkdir(parents=True)
            row = {
                field: f"{field}-value"
                for field in sec_http.REQUEST_LOG_FIELDNAMES
            }
            row.update({
                "source_url": "https://www.sec.gov/mock/one.json",
                "error": "",
            })
            text = rows_csv_text(
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=[row],
            )
            log_path.write_text(
                csv_text_with_row_width_delta(
                    text=text,
                    data_row_index=0,
                    extra_cell=True,
                ),
                encoding="utf-8",
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "."],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "malformed head",
                ],
            )
            with mock.patch.object(sec_pipeline, "WORKDIR", repo_root):
                with self.assertRaisesRegex(
                    ValueError,
                    "row shape at line 2",
                ):
                    sec_pipeline.committed_request_observation_sequence()

    def test_legacy_request_history_normalizes_without_shared_code(
        self,
    ) -> None:
        """Legacy path and URL identity match current-schema migration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "clone_b"
            body_path = repo_root / "evidence" / "one.json"
            headers_path = repo_root / "evidence" / "one.headers.json"
            body_path.parent.mkdir(parents=True)
            body = b"fixture"
            body_path.write_bytes(body)
            source_url = (
                "https://www.sec.gov/Archives/edgar/data/1/"
                "000000000126000001/one.json"
            )
            row = legacy_request_row(
                source_url=source_url,
                legacy_root=root / "evidence" / "oldclone" / "evidence",
                document_name="one.json",
                headers_name="one.headers.json",
                body=body,
                timestamp_utc="2026-07-22T00:00:00+00:00",
            )
            digest = row["sha256"]
            headers_path.write_text(
                json.dumps(
                    {
                        "url": source_url,
                        "status_code": 200,
                        "content_length": len(body),
                        "sha256": digest,
                    }
                ),
                encoding="utf-8",
            )
            sequence = contract_alignment.request_history_sequence(
                repo_root=repo_root,
                text=rows_csv_text(
                    fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                    rows=[row],
                ),
            )[0]
            bodyless_sequence = contract_alignment.request_history_sequence(
                repo_root=repo_root,
                text=rows_csv_text(
                    fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                    rows=[{**row, "sha256": ""}],
                ),
            )[0]
        self.assertEqual(sequence[5:11], (
            "evidence/one.json",
            "evidence/one.headers.json",
            "7",
            digest,
            "0000000001-26-000001",
            "one.json",
        ))
        self.assertEqual(bodyless_sequence[5:7], ("", ""))
        self.assertEqual(bodyless_sequence[10], "one.json")

    def test_base_request_ledger_cannot_reorder_or_shrink(self) -> None:
        """A PR can only append after the base ledger's ordered prefix."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["init"],
            )
            contract_path = repo_root / "capability_contract.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "deprecated_anchor_ids": [],
                        "contracts": {"capabilities": []},
                    }
                ),
                encoding="utf-8",
            )
            log_path = repo_root / "evidence" / "requests_log.csv"
            log_path.parent.mkdir(parents=True)
            base_row = {
                "timestamp_utc": "2026-07-22T00:00:00+00:00",
                "method": "GET",
                "url": "https://www.sec.gov/mock/one.json",
                "status_code": "0",
                "purpose": "fixture",
                "local_path": "",
                "headers_path": "",
                "content_length": "0",
                "sha256": "",
                "user_agent": "fixture fixture@example.com",
                "retry_attempt": "0",
                "error": "transport failure",
            }
            base_rows = [
                base_row,
                {
                    **base_row,
                    "url": "https://www.sec.gov/mock/two.json",
                },
            ]
            write_rows(
                path=log_path,
                fieldnames=sec_http.LEGACY_REQUEST_LOG_FIELDNAMES,
                rows=base_rows,
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "."],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "base",
                ],
            )
            base_ref = contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["rev-parse", "HEAD"],
            ).strip()
            legacy_text = log_path.read_text(encoding="utf-8")
            current_row = {
                "timestamp_utc": base_row["timestamp_utc"],
                "method": base_row["method"],
                "source_url": base_row["url"],
                "status_code": base_row["status_code"],
                "purpose": base_row["purpose"],
                "repo_relative_path": "",
                "headers_repo_relative_path": "",
                "content_length": base_row["content_length"],
                "content_sha256": base_row["sha256"],
                "accession": "",
                "document_name": "one.json",
                "user_agent": base_row["user_agent"],
                "retry_attempt": base_row["retry_attempt"],
                "error": base_row["error"],
            }
            current_rows = [
                current_row,
                {
                    **current_row,
                    "source_url": base_rows[1]["url"],
                    "document_name": "two.json",
                },
            ]
            with mock.patch.object(
                contract_alignment,
                "request_log_at_ref",
                side_effect=[
                    legacy_text,
                    rows_csv_text(
                        fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                        rows=current_rows,
                    ),
                ],
            ):
                migration_errors = (
                    contract_alignment.request_log_history_errors(
                        repo_root=repo_root,
                        base_ref=base_ref,
                    )
                )
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=list(reversed(current_rows)),
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "evidence/requests_log.csv"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "reordered head",
                ],
            )
            reordered_errors = contract_alignment.check_alignment(
                repo_root=repo_root,
                contract_path=contract_path,
                base_ref=base_ref,
            )
            write_rows(
                path=log_path,
                fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                rows=current_rows[:1],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=["add", "evidence/requests_log.csv"],
            )
            contract_alignment.git_output(
                repo_root=repo_root,
                arguments=[
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.com",
                    "commit",
                    "-m",
                    "shrunk head",
                ],
            )
            shrunk_errors = contract_alignment.check_alignment(
                repo_root=repo_root,
                contract_path=contract_path,
                base_ref=base_ref,
            )
        self.assertEqual(migration_errors, [])
        self.assertTrue(
            any(
                "request ledger prefix changed since base" in error
                for error in reordered_errors
            )
        )
        self.assertTrue(
            any(
                "request ledger observations removed since base" in error
                for error in shrunk_errors
            )
        )

    def test_base_history_prevents_tombstone_removal_and_reuse(self) -> None:
        """A deleted historical id remains permanently unavailable."""
        base_payload = {
            "deprecated_anchor_ids": ["CAPABILITY.retired"],
            "contracts": {"capabilities": []},
        }
        payload = {
            "deprecated_anchor_ids": [],
            "contracts": {
                "capabilities": [
                    {
                        "anchor_id": "CAPABILITY.retired",
                        "status": "active",
                        "test_anchor": None,
                        "untested_reason": "fixture",
                        "pending_since": "2026-07-22",
                    }
                ]
            },
        }
        errors = contract_alignment.alignment_errors(
            repo_root=REPO_ROOT,
            payload=payload,
            tracked_paths=set(),
            base_payload=base_payload,
        )
        self.assertIn(
            "deprecated registry id removed since base: CAPABILITY.retired",
            errors,
        )
        self.assertIn(
            "historically deprecated anchor reused: CAPABILITY.retired",
            errors,
        )

    def test_deprecated_anchor_cannot_be_reused(self) -> None:
        """An active entry cannot reuse an id in the deprecated registry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            payload = {
                "deprecated_anchor_ids": ["BEHAVIOR.retired"],
                "contracts": {
                    "agent_behaviors": [
                        {
                            "anchor_id": "BEHAVIOR.retired",
                            "status": "active",
                            "test_anchor": None,
                            "untested_reason": "fixture",
                        }
                    ]
                },
            }
            errors = contract_alignment.alignment_errors(
                repo_root=repo_root,
                payload=payload,
            )
        self.assertIn(
            "deprecated anchor reused by active entry: BEHAVIOR.retired",
            errors,
        )

    def test_test_anchor_cannot_escape_repository(self) -> None:
        """A symbol outside the submitted repository cannot satisfy a claim."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            (root / "external.py").write_text(
                "def proof():\n    pass\n",
                encoding="utf-8",
            )
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [
                        {
                            "anchor_id": "CAPABILITY.external",
                            "status": "active",
                            "test_anchor": "../external.py::proof",
                        }
                    ]
                },
            }
            errors = contract_alignment.alignment_errors(
                repo_root=repo_root,
                payload=payload,
            )
        self.assertIn(
            "CAPABILITY.external: test anchor path must be repository-relative",
            errors,
        )

    def test_ignored_pr_body_does_not_change_contract_gate(self) -> None:
        """The local ignored PR draft is not repository contract evidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            (repo_root / "PR_BODY.md").write_text(
                "<!-- capability-anchor: UNKNOWN.local -->\n",
                encoding="utf-8",
            )
            references = contract_alignment.markdown_anchor_references(
                repo_root=repo_root,
            )
        self.assertEqual(references, [])

    def test_nested_pr_body_name_remains_in_contract_scope(self) -> None:
        """Only the ignored root PR draft may be excluded from Markdown."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            nested = repo_root / "docs" / "PR_BODY.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                "<!-- capability-anchor: UNKNOWN.nested -->\n",
                encoding="utf-8",
            )
            references = contract_alignment.markdown_anchor_references(
                repo_root=repo_root,
            )
        self.assertEqual(references, [(nested, "UNKNOWN.nested")])

    def test_null_test_anchor_requires_pending_since(self) -> None:
        """Untested contracts must carry the date required by their rule."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            payload = {
                "deprecated_anchor_ids": [],
                "contracts": {
                    "capabilities": [
                        {
                            "anchor_id": "CAPABILITY.pending",
                            "status": "active",
                            "test_anchor": None,
                            "untested_reason": "fixture",
                        }
                    ]
                },
            }
            errors = contract_alignment.alignment_errors(
                repo_root=repo_root,
                payload=payload,
            )
        self.assertIn(
            "CAPABILITY.pending: null test_anchor requires pending_since",
            errors,
        )


class AuditorRepairBoundaryTest(unittest.TestCase):
    """Validate C04 fetches and retry inventory recovery stay bounded."""

    def test_request_bound_index_rejects_divergent_successful_bodies(
        self,
    ) -> None:
        """One immutable accession index cannot have two successful bodies."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            accession = "0000000001-26-000001"
            candidate = {
                "company": "Fixture Company",
                "cik": "1",
                "entity_role": "primary",
                "form": "10-K",
                "accession": accession,
                "reportDate": "2025-12-31",
            }
            with patched_workspace(workspace=workspace):
                base_dir = sec_pipeline.accession_dir_path(
                    company=candidate["company"],
                    cik=1,
                    accession=accession,
                )
                base_dir.mkdir(parents=True)
                index_path = base_dir / "index.json"
                old_body = json.dumps(
                    {
                        "directory": {
                            "item": [{"name": "a.xml"}, {"name": "b.xml"}]
                        }
                    }
                ).encode("utf-8")
                current_body = json.dumps(
                    {"directory": {"item": [{"name": "a.xml"}]}}
                ).encode("utf-8")
                index_path.write_bytes(current_body)
                index_url = sec_pipeline.accession_directory_url(
                    cik=1,
                    accession=accession,
                )
                request_rows = []
                for body in [old_body, current_body]:
                    request_rows.append(
                        {
                            "timestamp_utc": "2026-07-23T00:00:00+00:00",
                            "method": "GET",
                            "source_url": index_url,
                            "status_code": "200",
                            "purpose": "auditor index fixture",
                            "repo_relative_path": str(
                                index_path.relative_to(workspace)
                            ),
                            "headers_repo_relative_path": "",
                            "content_length": str(len(body)),
                            "content_sha256": hashlib.sha256(body).hexdigest(),
                            "accession": accession,
                            "document_name": index_path.name,
                            "user_agent": "fixture fixture@example.com",
                            "retry_attempt": "0",
                            "error": "",
                        }
                    )
                with self.assertRaisesRegex(
                    ValueError,
                    "conflicting successful bodies",
                ):
                    sec_pipeline.request_bound_xbrl_material_rows(
                        candidate=candidate,
                        observation_rows=request_rows,
                    )

    def test_immutable_response_allows_retry_and_prior_failure(self) -> None:
        """Same-body retries and an older non-200 do not create conflict."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            path = workspace / "evidence" / "fixture.xml"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"current filing body")
            source_url = (
                "https://www.sec.gov/Archives/edgar/data/1/"
                "000000000126000001/fixture.xml"
            )
            current = (
                source_url,
                "200",
                str(path.stat().st_size),
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.name,
            )
            failed = (
                source_url,
                "503",
                "3",
                hashlib.sha256(b"old").hexdigest(),
                path.name,
            )
            with patched_workspace(workspace=workspace):
                body = sec_pipeline.verified_immutable_response_bytes(
                    path=path,
                    source_url=source_url,
                    observation_identities=[failed, current, current],
                )
        self.assertEqual(body, b"current filing body")

    def test_c04_prefers_amendment_before_original_fallback(self) -> None:
        """C04 must inspect target 10-K/A before its original 10-K."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            inventory_path = workspace / "outputs" / "latest_filings_inventory.csv"
            inventory_path.parent.mkdir(parents=True)
            amendment = {
                field: "" for field in sec_pipeline.FILING_FIELDNAMES
            }
            amendment.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "entity_role": "primary",
                    "form": "10-K/A",
                    "accession": "0000000001-26-000002",
                    "filingDate": "2026-02-02",
                    "reportDate": "2025-12-31",
                    "source_role": "target_10k",
                }
            )
            original = {
                **amendment,
                "form": "10-K",
                "accession": "0000000001-26-000001",
                "filingDate": "2026-02-01",
                "source_role": "target_original_full_instance",
            }
            write_rows(
                path=inventory_path,
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=[amendment, original],
            )
            with patched_workspace(workspace=workspace):
                target = sec_pipeline.c04_target_filing(
                    company="Fixture Company",
                )
                candidates = sec_pipeline.auditor_current_filing_candidates(
                    company="Fixture Company",
                    target=target,
                )
        self.assertEqual(target["accession"], amendment["accession"])
        self.assertEqual(
            [row["accession"] for row in candidates],
            [amendment["accession"], original["accession"]],
        )

    def test_c04_period_start_does_not_cross_cik_boundary(self) -> None:
        """A predecessor filing cannot extend a successor C04 period."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            inventory_path = workspace / "outputs" / "latest_filings_inventory.csv"
            inventory_path.parent.mkdir(parents=True)
            prior = {field: "" for field in sec_pipeline.FILING_FIELDNAMES}
            prior.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "entity_role": "predecessor",
                    "form": "10-K",
                    "accession": "0000000001-24-000001",
                    "filingDate": "2024-02-01",
                    "reportDate": "2023-12-31",
                    "source_role": "prior_10k",
                }
            )
            write_rows(
                path=inventory_path,
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=[prior],
            )
            with patched_workspace(workspace=workspace):
                c04_period_start = sec_pipeline.c04_period_start(
                    prior=None,
                    target_cik=2,
                    period_end="2025-12-31",
                )
                same_cik_start = sec_pipeline.c04_period_start(
                    prior={"cik": "2", "reportDate": "2024-06-30"},
                    target_cik=2,
                    period_end="2025-12-31",
                )
                event_metric = sec_pipeline.text_metric_row(
                    company="Fixture Company",
                    cik=2,
                    metric_id="C01",
                    metric_name="Leadership changes",
                    value="1",
                    unit="count",
                    status="DIM_XBRL_OK",
                    source_class="8K_ITEM",
                    period_end="2025-12-31",
                    accession="fixture",
                    filed_date="2025-12-31",
                    concept_or_section="5.02",
                    context_or_dimension="item",
                    confidence="0.90",
                    notes="fixture",
                )
        self.assertEqual(c04_period_start, "2025-01-01")
        self.assertEqual(same_cik_start, "2024-07-01")
        self.assertEqual(event_metric["period_start"], "2024-01-01")

    def test_c04_repair_writes_same_cik_period_to_both_outputs(self) -> None:
        """The production repair must override both generic period builders."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            inventory_path = (
                workspace / "outputs" / "latest_filings_inventory.csv"
            )
            inventory_path.parent.mkdir(parents=True)
            target = {
                field: "" for field in sec_pipeline.FILING_FIELDNAMES
            }
            target.update(
                {
                    "company": "Fixture Company",
                    "cik": "2",
                    "entity_role": "successor",
                    "form": "10-K",
                    "accession": "0000000002-26-000001",
                    "filingDate": "2026-02-01",
                    "reportDate": "2025-12-31",
                    "source_role": "target_10k",
                }
            )
            predecessor = {
                **target,
                "cik": "1",
                "entity_role": "predecessor",
                "accession": "0000000001-25-000001",
                "filingDate": "2025-02-01",
                "reportDate": "2024-06-30",
                "source_role": "prior_10k",
            }
            write_rows(
                path=inventory_path,
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=[target, predecessor],
            )
            fact = {
                "accession": target["accession"],
                "concept": "AuditorName",
                "namespace": "http://xbrl.sec.gov/dei/2025",
                "period_end": target["reportDate"],
                "value": "Fixture LLP",
                "source_path": "evidence/current.xml",
            }
            component = {
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/2/"
                    "000000000226000001/current.xml"
                ),
                "local_path": "evidence/current.xml",
                "accession": target["accession"],
                "document_name": "current.xml",
            }
            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "load_company_registry",
                return_value=[{"company": "Fixture Company"}],
            ), mock.patch.object(
                sec_pipeline,
                "client",
                return_value=mock.Mock(),
            ), mock.patch.object(
                sec_pipeline,
                "auditor_facts_for_company",
                return_value=[fact],
            ), mock.patch.object(
                sec_pipeline,
                "auditor_fact_locator_component",
                return_value=component,
            ):
                generic_start = sec_pipeline.period_start_for_company_period(
                    company="Fixture Company",
                    period_end=target["reportDate"],
                )
                metrics, evidence = sec_pipeline.repair_c04_auditor_changes(
                    metrics=[],
                    evidence_rows=[],
                )
        self.assertEqual(generic_start, "2024-07-01")
        self.assertEqual(metrics[0]["period_start"], "2025-01-01")
        self.assertEqual(evidence[0]["period_start"], "2025-01-01")

    def test_c04_gate_reports_malformed_inventory_as_failure(self) -> None:
        """Damaged filing rows must produce a validation row, not crash."""
        metric = {field: "" for field in sec_pipeline.METRICS_FIELDNAMES}
        metric.update(
            {
                "company": "Fixture Company",
                "metric_id": "C04",
            }
        )
        inventory = [
            {
                "company": "Fixture Company",
                "source_role": "target_10k",
            }
        ]
        with mock.patch.object(
            sec_pipeline,
            "request_observation_rows",
            return_value=[],
        ), mock.patch.object(
            sec_pipeline,
            "load_company_registry",
            return_value=[{"company": "Fixture Company"}],
        ):
            result = sec_pipeline.check_c04_auditorname_all_companies(
                metrics=[metric],
                evidence_rows=[],
                inventory=inventory,
            )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("inventory row 1 missing fields", result["details"])

    def test_raw_auditor_replay_uses_request_bound_accession_index(
        self,
    ) -> None:
        """Deleting an XBRL material row cannot erase an existing fact."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            accession = "0000000001-26-000001"
            candidate = {
                "company": "Fixture Company",
                "cik": "1",
                "entity_role": "primary",
                "form": "10-K",
                "accession": accession,
                "reportDate": "2025-12-31",
            }
            with patched_workspace(workspace=workspace):
                base_dir = sec_pipeline.accession_dir_path(
                    company=candidate["company"],
                    cik=1,
                    accession=accession,
                )
                base_dir.mkdir(parents=True)
                index_path = base_dir / "index.json"
                instance_path = base_dir / "fixture.xml"
                index_path.write_text(
                    json.dumps(
                        {"directory": {"item": [{"name": "fixture.xml"}]}}
                    ),
                    encoding="utf-8",
                )
                instance_path.write_text(
                    "<xbrli:xbrl "
                    "xmlns:xbrli='http://www.xbrl.org/2003/instance' "
                    "xmlns:dei='http://xbrl.sec.gov/dei/2025'>"
                    "<xbrli:context id='c1'><xbrli:entity>"
                    "<xbrli:identifier scheme='fixture'>1</xbrli:identifier>"
                    "</xbrli:entity><xbrli:period>"
                    "<xbrli:instant>2025-12-31</xbrli:instant>"
                    "</xbrli:period></xbrli:context>"
                    "<dei:AuditorName contextRef='c1'>Fixture LLP"
                    "</dei:AuditorName></xbrli:xbrl>",
                    encoding="utf-8",
                )
                index_url = sec_pipeline.accession_directory_url(
                    cik=1,
                    accession=accession,
                )
                instance_url = sec_pipeline.accession_document_url(
                    cik=1,
                    accession=accession,
                    document_name=instance_path.name,
                )
                request_rows = []
                for path, source_url in [
                    (index_path, index_url),
                    (instance_path, instance_url),
                ]:
                    body = path.read_bytes()
                    request_rows.append(
                        {
                            "timestamp_utc": "2026-07-23T00:00:00+00:00",
                            "method": "GET",
                            "source_url": source_url,
                            "status_code": "200",
                            "purpose": "auditor fixture",
                            "repo_relative_path": str(
                                path.relative_to(workspace)
                            ),
                            "headers_repo_relative_path": "",
                            "content_length": str(len(body)),
                            "content_sha256": hashlib.sha256(body).hexdigest(),
                            "accession": accession,
                            "document_name": path.name,
                            "user_agent": "fixture fixture@example.com",
                            "retry_attempt": "0",
                            "error": "",
                        }
                    )
                log_path = workspace / "evidence" / "requests_log.csv"
                write_rows(
                    path=log_path,
                    fieldnames=sec_http.REQUEST_LOG_FIELDNAMES,
                    rows=request_rows,
                )
                sec_http.refresh_request_log_manifest(
                    workdir=workspace,
                    log_path=log_path,
                )
                index_material = {
                    field: "" for field in sec_pipeline.MATERIAL_FIELDNAMES
                }
                index_material.update(
                    {
                        "company": candidate["company"],
                        "cik": candidate["cik"],
                        "entity_role": candidate["entity_role"],
                        "form": candidate["form"],
                        "accession": candidate["accession"],
                        "document_name": "index.json",
                        "document_type": "accession_index",
                        "source_url": index_url,
                        "repo_relative_path": str(
                            index_path.relative_to(workspace)
                        ),
                        "status_code": "200",
                        "content_length": str(index_path.stat().st_size),
                        "content_sha256": hashlib.sha256(
                            index_path.read_bytes()
                        ).hexdigest(),
                    }
                )
                inventory_path = (
                    workspace
                    / "outputs"
                    / "accession_materials_inventory.csv"
                )
                inventory_path.parent.mkdir(parents=True)
                write_rows(
                    path=inventory_path,
                    fieldnames=sec_pipeline.MATERIAL_FIELDNAMES,
                    rows=[index_material],
                )
                facts = sec_pipeline.raw_auditor_facts_for_candidates(
                    candidates=[candidate],
                    observation_rows=request_rows,
                )
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["concept"], "AuditorName")
        self.assertEqual(facts[0]["value"], "Fixture LLP")

    def test_blank_and_conflicting_auditor_names_are_not_selected(
        self,
    ) -> None:
        """Only one nonblank canonical name can support C04 comparison."""
        candidate = {
            "accession": "0000000001-26-000001",
            "reportDate": "2025-12-31",
        }
        base_fact = {
            "accession": candidate["accession"],
            "concept": "AuditorName",
            "namespace": "http://xbrl.sec.gov/dei/2025",
            "period_end": candidate["reportDate"],
            "source_path": "evidence/fixture.xml",
        }
        blank, blank_reason = sec_pipeline.auditor_fact_for_accession(
            facts=[{**base_fact, "value": " -- "}],
            accession=candidate["accession"],
            period_end=candidate["reportDate"],
        )
        equivalent, equivalent_reason = (
            sec_pipeline.auditor_fact_for_accession(
                facts=[
                    {**base_fact, "value": "Fixture LLP"},
                    {**base_fact, "value": "Fixture, L.L.P."},
                ],
                accession=candidate["accession"],
                period_end=candidate["reportDate"],
            )
        )
        conflicting_facts = [
            {**base_fact, "value": "Fixture LLP"},
            {**base_fact, "value": "Other LLP"},
        ]
        custom_namespace, custom_reason = (
            sec_pipeline.auditor_fact_for_accession(
                facts=[
                    {
                        **base_fact,
                        "namespace": "https://example.com/custom",
                        "value": "Fake Audit LLP",
                    }
                ],
                accession=candidate["accession"],
                period_end=candidate["reportDate"],
            )
        )
        with mock.patch.object(
            sec_pipeline,
            "auditor_facts_for_company",
            return_value=conflicting_facts,
        ), mock.patch.object(
            sec_pipeline,
            "ensure_auditor_facts_for_filing",
        ) as ensure:
            conflict, source, conflict_reason = (
                sec_pipeline.ensure_auditor_fact_from_candidates(
                    http=mock.Mock(),
                    company="Fixture Company",
                    candidates=[candidate],
                )
            )
        self.assertIsNone(blank)
        self.assertEqual(blank_reason, "missing_or_blank")
        self.assertIsNotNone(equivalent)
        self.assertEqual(equivalent_reason, "")
        self.assertIsNone(conflict)
        self.assertEqual(source, candidate)
        self.assertEqual(conflict_reason, "conflicting_values")
        self.assertIsNone(custom_namespace)
        self.assertEqual(custom_reason, "missing_or_blank")
        ensure.assert_not_called()

    def test_existing_target_fact_does_not_fetch_fallback_candidate(
        self,
    ) -> None:
        """A local target AuditorName must stop before original 10-K fetch."""
        candidates = [
            {
                "accession": "0000000001-26-000002",
                "reportDate": "2025-12-31",
            },
            {
                "accession": "0000000001-26-000001",
                "reportDate": "2025-12-31",
            },
        ]
        fact = {
            "accession": candidates[0]["accession"],
            "concept": "AuditorName",
            "namespace": "http://xbrl.sec.gov/dei/2025",
            "period_end": candidates[0]["reportDate"],
            "value": "Fixture LLP",
            "source_path": "evidence/fixture.xml",
        }
        with mock.patch.object(
            sec_pipeline,
            "auditor_facts_for_company",
            return_value=[fact],
        ), mock.patch.object(
            sec_pipeline,
            "ensure_auditor_facts_for_filing",
        ) as ensure:
            selected, source, reason = (
                sec_pipeline.ensure_auditor_fact_from_candidates(
                    http=mock.Mock(),
                    company="fixture company",
                    candidates=candidates,
                )
            )
        self.assertEqual(selected, fact)
        self.assertEqual(source, candidates[0])
        self.assertEqual(reason, "")
        ensure.assert_not_called()

    def test_existing_fallback_fact_avoids_amendment_fetch(self) -> None:
        """A local original fact can satisfy a missing amendment offline."""
        candidates = [
            {
                "accession": "0000000001-26-000002",
                "reportDate": "2025-12-31",
            },
            {
                "accession": "0000000001-26-000001",
                "reportDate": "2025-12-31",
            },
        ]
        fact = {
            "accession": candidates[1]["accession"],
            "concept": "AuditorName",
            "namespace": "http://xbrl.sec.gov/dei/2025",
            "period_end": candidates[1]["reportDate"],
            "value": "Fixture LLP",
            "source_path": "evidence/fixture.xml",
        }
        with mock.patch.object(
            sec_pipeline,
            "auditor_facts_for_company",
            return_value=[fact],
        ), mock.patch.object(
            sec_pipeline,
            "ensure_auditor_facts_for_filing",
        ) as ensure:
            selected, source, reason = (
                sec_pipeline.ensure_auditor_fact_from_candidates(
                    http=mock.Mock(),
                    company="fixture company",
                    candidates=candidates,
                )
            )
        self.assertEqual(selected, fact)
        self.assertEqual(source, candidates[1])
        self.assertEqual(reason, "")
        ensure.assert_not_called()

    def test_c04_gate_recomputes_both_auditor_components(self) -> None:
        """Metric and quote tampering cannot replace current/prior DEI facts."""
        def build_outputs(
            *,
            current: dict,
            prior: dict,
            value: str,
            status: str,
        ) -> tuple[dict, dict]:
            """Build one independently specified C04 output fixture."""
            source_paths = [current["source_path"], prior["source_path"]]
            accessions = ";".join(
                [current["accession"], prior["accession"]]
            )
            notes = (
                f"auditor {'changed' if value == '1' else 'unchanged'}; "
                f"current_accession={current['accession']}; "
                f"prior_accession={prior['accession']}; "
                "manual confirmation required when changed."
            )
            metric = {
                field: "" for field in sec_pipeline.METRICS_FIELDNAMES
            }
            metric.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "metric_id": "C04",
                    "metric_name": "Auditor changes",
                    "value": value,
                    "unit": "flag",
                    "status": status,
                    "source_class": "DIM_XBRL",
                    "formula": "text/event extraction",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                    "fiscal_year": "",
                    "fiscal_period": "FY",
                    "accession": accessions,
                    "form": "",
                    "filed_date": "2026-02-01",
                    "concept_or_section": "AuditorName",
                    "context_or_dimension": "current/prior 10-K instance",
                    "confidence": "0.80",
                    "notes": notes,
                }
            )
            evidence = {
                field: "" for field in sec_pipeline.EVIDENCE_FIELDNAMES
            }
            evidence.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "metric_id": "C04",
                    "source_url": ";".join(
                        source_urls[path] for path in source_paths
                    ),
                    "repo_relative_path": ";".join(
                        str(Path(path).relative_to(workspace))
                        for path in source_paths
                    ),
                    "content_sha256": ";".join(
                        hashlib.sha256(Path(path).read_bytes()).hexdigest()
                        for path in source_paths
                    ),
                    "accession": accessions,
                    "document_name": ";".join(
                        Path(path).name for path in source_paths
                    ),
                    "concept_or_section": "AuditorName",
                    "context_or_dimension": "current/prior 10-K instance",
                    "unit": "flag",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                    "value_raw": value,
                    "value_normalized": value,
                    "evidence_quote": (
                        f"current={current['value']}; prior={prior['value']}"
                    ),
                    "extraction_method": "auditorname_repair",
                    "parser_version": "sec_pipeline_v1",
                }
            )
            return metric, evidence

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            current_path = (
                workspace
                / "evidence"
                / "accession_materials"
                / "fixture_1_000000000126000002"
                / "current.xml"
            )
            prior_path = (
                workspace
                / "evidence"
                / "accession_materials"
                / "fixture_1_000000000125000001"
                / "prior.xml"
            )
            current_path.parent.mkdir(parents=True)
            prior_path.parent.mkdir(parents=True)
            current_path.write_bytes(b"current")
            prior_path.write_bytes(b"prior")
            other_path = prior_path.parent / "other.xml"
            other_path.write_bytes(b"unrelated prior material")
            source_urls = {
                str(current_path): (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000126000002/current.xml"
                ),
                str(prior_path): (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000125000001/prior.xml"
                ),
            }
            target = {
                field: "" for field in sec_pipeline.FILING_FIELDNAMES
            }
            target.update(
                {
                    "company": "Fixture Company",
                    "cik": "1",
                    "entity_role": "primary",
                    "form": "10-K",
                    "accession": "0000000001-26-000002",
                    "filingDate": "2026-02-01",
                    "reportDate": "2025-12-31",
                    "source_url": source_urls[str(current_path)],
                }
            )
            prior_filing = {
                **target,
                "accession": "0000000001-25-000001",
                "filingDate": "2025-02-01",
                "reportDate": "2024-12-31",
                "source_url": source_urls[str(prior_path)],
            }
            inventory = [
                {**target, "source_role": "target_10k"},
                {**prior_filing, "source_role": "prior_10k"},
            ]
            inventory_path = (
                workspace / "outputs" / "latest_filings_inventory.csv"
            )
            inventory_path.parent.mkdir(parents=True)
            write_rows(
                path=inventory_path,
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=inventory,
            )
            base_fact = {
                "concept": "AuditorName",
                "namespace": "http://xbrl.sec.gov/dei/2025",
                "period_end": "",
                "source_path": "",
            }
            same_facts = [
                {
                    **base_fact,
                    "accession": target["accession"],
                    "period_end": target["reportDate"],
                    "value": "Same LLP",
                    "source_path": str(current_path),
                },
                {
                    **base_fact,
                    "accession": prior_filing["accession"],
                    "period_end": prior_filing["reportDate"],
                    "value": "Same LLP",
                    "source_path": str(prior_path),
                },
            ]
            changed_facts = [
                {**same_facts[0], "value": "New LLP"},
                {**same_facts[1], "value": "Old LLP"},
            ]
            path_by_accession = {
                target["accession"]: current_path,
                prior_filing["accession"]: prior_path,
            }
            active_facts = same_facts

            def request_bound_materials(
                *,
                candidate: dict,
                observation_rows: list[dict],
            ) -> list[dict]:
                """Return one request-bound material for the candidate."""
                del observation_rows
                path = path_by_accession[candidate["accession"]]
                return [
                    {
                        "company": candidate["company"],
                        "cik": candidate["cik"],
                        "entity_role": candidate["entity_role"],
                        "form": candidate["form"],
                        "accession": candidate["accession"],
                        "document_name": path.name,
                        "source_url": source_urls[str(path)],
                        "local_path": str(path),
                    }
                ]

            def parse_material(*, material_row: dict) -> list[dict]:
                """Return the active raw facts for one material accession."""
                return [
                    fact
                    for fact in active_facts
                    if fact["accession"] == material_row["accession"]
                ]

            with patched_workspace(workspace=workspace), mock.patch.object(
                sec_pipeline,
                "load_company_registry",
                return_value=[{"company": "Fixture Company"}],
            ), mock.patch.object(
                sec_pipeline,
                "request_observation_rows",
                return_value=[],
            ), mock.patch.object(
                sec_pipeline,
                "request_bound_xbrl_material_rows",
                side_effect=request_bound_materials,
            ), mock.patch.object(
                sec_pipeline,
                "parse_instance_with_fallback",
                side_effect=parse_material,
            ):
                same_metric, same_evidence = build_outputs(
                    current=same_facts[0],
                    prior=same_facts[1],
                    value="0",
                    status="DIM_XBRL_OK",
                )
                baseline = (
                    sec_pipeline.check_c04_auditorname_all_companies(
                        metrics=[same_metric],
                        evidence_rows=[same_evidence],
                        inventory=inventory,
                    )
                )
                tampered = (
                    sec_pipeline.check_c04_auditorname_all_companies(
                        metrics=[{**same_metric, "value": "1"}],
                        evidence_rows=[
                            {
                                **same_evidence,
                                "value_raw": "1",
                                "value_normalized": "1",
                                "evidence_quote": (
                                    "current=Fake New; prior=Fake Old"
                                ),
                            }
                        ],
                        inventory=inventory,
                    )
                )
                metadata_tampered = (
                    sec_pipeline.check_c04_auditorname_all_companies(
                        metrics=[
                            {
                                **same_metric,
                                "cik": "999",
                                "metric_name": "WRONG",
                                "formula": "WRONG",
                                "fiscal_period": "Q1",
                                "form": "10-Q",
                                "filed_date": "1900-01-01",
                                "confidence": "0.01",
                                "notes": "WRONG",
                            }
                        ],
                        evidence_rows=[same_evidence],
                        inventory=inventory,
                    )
                )
                changed_metric, changed_evidence = build_outputs(
                    current=changed_facts[0],
                    prior=changed_facts[1],
                    value="1",
                    status="NEEDS_REVIEW",
                )
                active_facts = changed_facts
                changed = sec_pipeline.check_c04_auditorname_all_companies(
                    metrics=[changed_metric],
                    evidence_rows=[changed_evidence],
                    inventory=inventory,
                )
                prior_issue = "missing or blank AuditorName"
                missing_name = prior_filing["accession"]
                missing_note = (
                    "需复核: current auditor read from dei:AuditorName, but "
                    f"prior 10-K has {prior_issue} ({missing_name})."
                )
                missing_quote = (
                    f"current dei:AuditorName={same_facts[0]['value']}; "
                    f"prior_issue={prior_issue};"
                    f"prior_accession={missing_name}"
                )
                missing_metric = {
                    **same_metric,
                    "value": "",
                    "unit": "",
                    "status": "NEEDS_REVIEW",
                    "accession": target["accession"],
                    "confidence": "0.45",
                    "notes": missing_note,
                }
                missing_evidence = {
                    **same_evidence,
                    "unit": "",
                    "value_raw": "",
                    "value_normalized": "",
                    "evidence_quote": missing_quote,
                }
                active_facts = [same_facts[0]]
                missing = sec_pipeline.check_c04_auditorname_all_companies(
                    metrics=[missing_metric],
                    evidence_rows=[missing_evidence],
                    inventory=inventory,
                )
                other_url = (
                    "https://www.sec.gov/Archives/edgar/data/1/"
                    "000000000125000001/other.xml"
                )
                tampered_missing_evidence = {
                    **missing_evidence,
                    "source_url": ";".join(
                        [source_urls[str(current_path)], other_url]
                    ),
                    "repo_relative_path": ";".join(
                        [
                            str(current_path.relative_to(workspace)),
                            str(other_path.relative_to(workspace)),
                        ]
                    ),
                    "content_sha256": ";".join(
                        [
                            hashlib.sha256(
                                current_path.read_bytes()
                            ).hexdigest(),
                            hashlib.sha256(
                                other_path.read_bytes()
                            ).hexdigest(),
                        ]
                    ),
                    "document_name": "current.xml;other.xml",
                }
                locator_errors = (
                    sec_pipeline.locator_component_alignment_errors(
                        row=tampered_missing_evidence,
                        verify_local_provenance=True,
                    )
                )
                missing_tampered = (
                    sec_pipeline.check_c04_auditorname_all_companies(
                        metrics=[missing_metric],
                        evidence_rows=[tampered_missing_evidence],
                        inventory=inventory,
                    )
                )
        self.assertEqual(baseline["status"], "PASS")
        self.assertEqual(tampered["status"], "FAIL")
        self.assertEqual(metadata_tampered["status"], "FAIL")
        self.assertEqual(changed["status"], "PASS")
        self.assertEqual(missing["status"], "PASS")
        self.assertEqual(locator_errors, [])
        self.assertEqual(missing_tampered["status"], "FAIL")

    def test_new_success_supersedes_old_failure_in_material_inventory(
        self,
    ) -> None:
        """A later 200 must replace the current identity's stale 503 row."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            path = workspace / "outputs" / "accession_materials_inventory.csv"
            recovered_path = (
                workspace
                / "evidence"
                / "accession_materials"
                / "fixture_1_000000000126000001"
                / "sample.xml"
            )
            path.parent.mkdir(parents=True)
            recovered_path.parent.mkdir(parents=True)
            recovered_path.write_bytes(b"new body")
            base = {field: "" for field in sec_pipeline.MATERIAL_FIELDNAMES}
            base.update(
                {
                    "company": "fixture company",
                    "cik": "1",
                    "entity_role": "primary",
                    "form": "10-K",
                    "accession": "0000000001-26-000001",
                    "document_name": "sample.xml",
                    "document_type": "xbrl_instance",
                    "source_url": (
                        "https://www.sec.gov/Archives/edgar/data/1/"
                        "000000000126000001/sample.xml"
                    ),
                    "repo_relative_path": "evidence/old/sample.xml",
                    "content_sha256": "0" * 64,
                    "status_code": "503",
                    "content_length": "3",
                }
            )
            write_rows(
                path=path,
                fieldnames=sec_pipeline.MATERIAL_FIELDNAMES,
                rows=[base],
            )
            recovered = {
                **base,
                "repo_relative_path": str(
                    recovered_path.relative_to(workspace)
                ),
                "content_sha256": hashlib.sha256(b"new body").hexdigest(),
                "status_code": "200",
                "content_length": str(len(b"new body")),
            }
            with patched_workspace(workspace=workspace):
                sec_pipeline.append_material_rows(rows=[recovered])
                selected = sec_pipeline.xbrl_material_rows_for_accession(
                    accession=base["accession"],
                )
            rows = read_rows(path=path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_code"], "200")
        self.assertEqual(
            rows[0]["content_sha256"],
            hashlib.sha256(b"new body").hexdigest(),
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["status_code"], "200")
        self.assertEqual(
            selected[0]["content_sha256"],
            rows[0]["content_sha256"],
        )


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
            self.assertEqual(fallback["source_role"],
                             "target_original_full_instance")
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
        self.assertTrue(
            sec_pipeline.scanner_constant_folding_tamper_detected())


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
