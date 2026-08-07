"""Failure-first tests for the vNext legacy-producer cutover boundary.

Purpose:
    Prove Stage 04/09/11 only build the non-migrated legacy candidate, every
    legacy write of B01/B03/B10/B11 fails with one stable code, committed
    active roots cannot be rewritten by legacy wrappers, and the public stage
    dispatcher remains successful when every retired resolver raises.

Call relationships:
    Tests call ``sec_pipeline.run_stage`` through the supported stage dispatch
    surface and patch only acquisition/report dependencies needed to keep the
    scenario deterministic and offline.
"""

from __future__ import annotations

import csv
import socket
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sec_pipeline  # noqa: E402
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS  # noqa: E402

from tests.vnext.test_report_read_only import publication_fixture  # noqa: E402


MIGRATED_METRIC_IDS = {"B01", "B03", "B10", "B11"}
RETIRED_RESOLVER_NAMES = {
    "apply_lodging_kpi_metrics",
    "compatible_component_hits",
    "custom_da_observation_note",
    "lodging_candidate_from_cells",
    "lodging_header_order",
    "lodging_identity_error",
    "lodging_kpi_fact_from_text",
    "lodging_metric_orders",
    "lodging_numeric_cells",
    "lodging_quote_text",
    "lodging_scope_matches",
    "lodging_scope_row_labels",
    "lodging_section_before",
    "lodging_table_segments",
    "non_fi_metric_rows",
    "normalized_scope_text",
    "repair_lodging_kpis",
    "resolve_da_component",
    "resolve_operating_income_component",
    "scope_pattern",
    "text_has_lodging_kpi_keywords",
    "upsert_lodging_text_metric",
}


def metric_row(*, metric_id: str) -> dict:
    """Return one schema-complete deterministic metric row for stage wiring."""
    row = {field: "" for field in sec_pipeline.METRICS_FIELDNAMES}
    row.update(
        {
            "company": "Fixture Company",
            "cik": "1",
            "metric_id": metric_id,
            "metric_name": metric_id,
            "status": "NOT_AVAILABLE_SEC",
            "source_class": "NOT_AVAILABLE",
            "period_end": "2025-12-31",
        }
    )
    return row


def non_migrated_metric_rows(
    *, company: str, target: dict
) -> tuple[list[dict], list[dict]]:
    """Return one non-migrated Stage 04 candidate row.

    Args:
        company: Company selected by the stage.
        target: Selected filing row.

    Returns:
        One B02 row and no evidence, keeping the test focused on stage wiring.
    """
    if company != "Fixture Company" or target["accession"] != "fixture-accession":
        raise AssertionError("Unexpected Stage 04 fixture identity")
    return [metric_row(metric_id="B02")], []


def identity_three_rows(
    *, metrics: list[dict], evidence_rows: list[dict], governance_rows: list[dict]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Return three repair collections unchanged for offline stage wiring."""
    return metrics, evidence_rows, governance_rows


def identity_two_rows(
    *, metrics: list[dict], evidence_rows: list[dict], **_unused: object
) -> tuple[list[dict], list[dict]]:
    """Return metric and evidence collections unchanged for offline repairs."""
    return metrics, evidence_rows


def projected_manifests(*, rows: list[dict]) -> tuple[dict, dict]:
    """Return matching active and terminal manifests for Stage 11 publication."""
    if rows[-1]["check_id"] != "validation_gate_result":
        raise AssertionError("Stage 11 did not pass the validation gate row")
    active = {
        "run_id": "fixture-validation-run",
        "source_commit": "fixture-source",
        "started_at_utc": "2026-08-06T00:00:00+00:00",
        "mode": "FULL_VALIDATION",
        "refreshed_artifacts": [],
        "not_refreshed_artifacts": list(
            sec_pipeline.VALIDATION_TRACKED_ARTIFACTS
        ),
        "result": "IN_PROGRESS",
    }
    terminal = dict(active)
    terminal["result"] = "PASSED"
    return active, terminal


def report_text(*, validation_manifest: dict) -> str:
    """Return a terminal report bound to the supplied manifest identity."""
    return (
        "# REPORT_十公司财务指标\n\n"
        f"- run_id: `{validation_manifest['run_id']}`\n"
        f"- result: `{validation_manifest['result']}`\n"
    )


def read_metric_ids(*, path: Path) -> set[str]:
    """Read metric identifiers from a generated matrix CSV."""
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        return {row["metric_id"] for row in csv.DictReader(file_obj)}


class LegacyCutoverBoundaryTest(unittest.TestCase):
    """Prove retired producers cannot re-enter the formal candidate flow."""

    def test_legacy_upsert_rejects_every_migrated_metric(self) -> None:
        """Reject all four migrated metric IDs with one stable error code."""
        for metric_id in sorted(MIGRATED_METRIC_IDS):
            with self.subTest(metric_id=metric_id):
                with self.assertRaisesRegex(
                    sec_pipeline.LegacyPathStillActiveError,
                    r"^LEGACY_PATH_STILL_ACTIVE:",
                ):
                    sec_pipeline.upsert_metric(
                        rows=[],
                        new_row=metric_row(metric_id=metric_id),
                    )

    def test_legacy_persistence_helpers_reject_migrated_rows(self) -> None:
        """Reject migrated metrics at every legacy CSV persistence helper."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with mock.patch.object(sec_pipeline, "WORKDIR", workspace):
                for writer in [
                    sec_pipeline.save_metrics,
                    sec_pipeline.save_evidence,
                    sec_pipeline.append_evidence,
                ]:
                    with self.subTest(writer=writer.__name__):
                        with self.assertRaisesRegex(
                            sec_pipeline.LegacyPathStillActiveError,
                            r"^LEGACY_PATH_STILL_ACTIVE:",
                        ):
                            writer(rows=[metric_row(metric_id="B01")])
            self.assertFalse((workspace / "outputs").exists())

    def test_retired_public_resolvers_are_fail_closed_tombstones(self) -> None:
        """Keep old B03/lodging entrypoints non-oracular after Cutover."""
        calls = {
            "non_fi_metric_rows": {
                "company": "Fixture Company",
                "target": {"cik": "1"},
            },
            "resolve_da_component": {
                "cik": 1,
                "period_end": "2025-12-31",
                "accession": "fixture",
            },
            "resolve_operating_income_component": {
                "cik": 1,
                "period_end": "2025-12-31",
                "accession": "fixture",
                "revenue": None,
            },
            "apply_lodging_kpi_metrics": {
                "metrics": [],
                "evidence_rows": [],
                "company": "Fixture Company",
                "text": "",
                "source_url": "https://www.sec.gov/fixture",
                "local_path": "fixture.html",
            },
            "repair_lodging_kpis": {"metrics": [], "evidence_rows": []},
        }
        for name, arguments in calls.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    sec_pipeline.LegacyPathStillActiveError,
                    r"^LEGACY_PATH_STILL_ACTIVE:",
                ):
                    getattr(sec_pipeline, name)(**arguments)
        self.assertEqual(
            sec_pipeline.check_legacy_production_paths_retired()["status"],
            "PASS",
        )

    def test_active_root_rejects_legacy_stage_wrapper(self) -> None:
        """Prevent direct Stage 04 execution from replacing an active mirror."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "outputs").mkdir(parents=True)
            (workspace / "outputs" / "active_publication.json").write_text(
                "{}\n", encoding="utf-8"
            )
            with mock.patch.object(sec_pipeline, "WORKDIR", workspace):
                with self.assertRaisesRegex(
                    sec_pipeline.LegacyPathStillActiveError,
                    r"^LEGACY_PATH_STILL_ACTIVE:",
                ):
                    sec_pipeline.run_stage(
                        stage_name="04_compute_standard_metrics"
                    )
            self.assertFalse(
                (workspace / "outputs" / "metrics_matrix.csv").exists()
            )

    def test_repository_root_requires_isolated_legacy_candidate_workspace(self) -> None:
        """Block legacy stages from writing root even before first Cutover."""
        with self.assertRaisesRegex(
            sec_pipeline.LegacyPathStillActiveError,
            r"^LEGACY_PATH_STILL_ACTIVE:",
        ):
            sec_pipeline.assert_legacy_stage_workspace(
                stage_name="04_compute_standard_metrics"
            )

    def test_repository_descendant_is_not_a_legacy_candidate_workspace(
        self,
    ) -> None:
        """Keep legacy candidate writes outside every repository namespace."""
        candidate_parent = REPO_ROOT / "artifacts" / "vnext"
        candidate_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=candidate_parent,
            prefix="legacy-candidate-boundary-",
        ) as temp_dir:
            with self.assertRaisesRegex(
                sec_pipeline.LegacyPathStillActiveError,
                r"^LEGACY_PATH_STILL_ACTIVE:",
            ):
                sec_pipeline.configure_legacy_candidate_workspace(
                    workspace_dir=Path(temp_dir).resolve(),
                )

    def test_public_stage04_runs_in_explicit_isolated_candidate(self) -> None:
        """Retain non-migrated Stage 04 through the supported data boundary."""
        original_paths = {
            name: getattr(sec_pipeline, name)
            for name in (
                "WORKDIR",
                "CONFIG_PATH",
                "COMPANY_REGISTRY_PATH",
                "METRIC_APPLICABILITY_PATH",
                "REQUEST_LOG_PATH",
                "LIGHT_REVIEW_MARKER_PATH",
            )
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            # Why: macOS exposes the temporary root through a ``/var``
            # symlink, while the public candidate boundary intentionally
            # rejects every symlink component before it writes artifacts.
            workspace = Path(temp_dir).resolve()
            try:
                with mock.patch.object(
                    sec_pipeline, "load_company_registry", return_value=[]
                ):
                    sec_pipeline.run_legacy_candidate_stage(
                        stage_name="04_compute_standard_metrics",
                        workspace_dir=workspace,
                    )
                with (
                    workspace / "outputs" / "metrics_matrix.csv"
                ).open(encoding="utf-8", newline="") as stream:
                    self.assertEqual([], list(csv.DictReader(stream)))
                with (
                    workspace / "outputs" / "metric_evidence.csv"
                ).open(encoding="utf-8", newline="") as stream:
                    self.assertEqual([], list(csv.DictReader(stream)))
            finally:
                for name, path in original_paths.items():
                    setattr(sec_pipeline, name, path)

    def test_active_stage_10_11_12_use_one_read_only_view_each(
        self,
    ) -> None:
        """Route active validation around all legacy mutation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            view, files = publication_fixture(root=workspace)
            for relative in sorted(ROOT_MIRROR_RELATIVE_PATHS):
                mirror = workspace / ROOT_MIRROR_RELATIVE_PATHS[relative]
                mirror.parent.mkdir(parents=True, exist_ok=True)
                mirror.write_bytes(files[relative])

            forbidden = AssertionError("active stage invoked a legacy write")
            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(sec_pipeline, "WORKDIR", workspace)
                )
                open_view = stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "open_active_publication_view",
                        return_value=view,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        socket,
                        "socket",
                        side_effect=AssertionError(
                            "active stage opened a network socket"
                        ),
                    )
                )
                for name in [
                    "client",
                    "run_repair_validation",
                    "apply_p0_repairs",
                    "write_csv_file",
                    "write_terminal_report",
                    "write_validation_run_manifest",
                    "finish_validation_run_manifest",
                    "write_utf8_text_atomically",
                ]:
                    stack.enter_context(
                        mock.patch.object(
                            sec_pipeline,
                            name,
                            side_effect=forbidden,
                        )
                    )

                for stage_name in [
                    "10_run_golden_assertions",
                    "11_build_report",
                    "12_validate_repair",
                ]:
                    sec_pipeline.run_stage(stage_name=stage_name)

            self.assertEqual(3, open_view.call_count)

    def test_public_legacy_stage_flow_ignores_all_retired_resolvers(self) -> None:
        """Run Stage 04/09/11 while every retired resolver raises immediately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            outputs = workspace / "outputs"
            outputs.mkdir(parents=True)
            sec_pipeline.write_csv_file(
                path=outputs / "latest_filings_inventory.csv",
                fieldnames=sec_pipeline.FILING_FIELDNAMES,
                rows=[
                    {
                        "company": "Fixture Company",
                        "cik": "1",
                        "entity_role": "primary",
                        "form": "10-K",
                        "accession": "fixture-accession",
                        "filingDate": "2026-01-31",
                        "reportDate": "2025-12-31",
                        "primaryDocument": "fixture.html",
                        "isXBRL": "1",
                        "isInlineXBRL": "1",
                        "source_role": "target_10k",
                        "source_url": "https://www.sec.gov/fixture",
                    }
                ],
            )
            sec_pipeline.write_csv_file(
                path=outputs / "governance_signals.csv",
                fieldnames=sec_pipeline.GOVERNANCE_FIELDNAMES,
                rows=[],
            )
            sec_pipeline.write_csv_file(
                path=outputs / "events.csv",
                fieldnames=sec_pipeline.EVENT_FIELDNAMES,
                rows=[],
            )
            target = {
                "company": "Fixture Company",
                "cik": "1",
                "accession": "fixture-accession",
                "reportDate": "2025-12-31",
                "filingDate": "2026-01-31",
            }
            material = {
                "company": "Fixture Company",
                "cik": "1",
                "accession": "fixture-accession",
                "source_url": "https://www.sec.gov/fixture",
                "repo_relative_path": "evidence/fixture.html",
                "content_sha256": "0" * 64,
                "document_name": "fixture.html",
            }

            def retired_resolver(*_args: object, **_kwargs: object) -> object:
                """Fail if any retired resolver remains in the stage call graph."""
                raise AssertionError("retired legacy resolver was called")

            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(sec_pipeline, "WORKDIR", workspace)
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "load_company_registry",
                        return_value=[
                            {
                                "company": "Fixture Company",
                                "entity_continuity_status": "continuous",
                            }
                        ],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "target_10k_for_company",
                        return_value=target,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "company_extractors",
                        return_value=["LodgingKpiExtractor"],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "company_by_name",
                        return_value={"company": "Fixture Company"},
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "period_start_for_company_period",
                        return_value="2025-01-01",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "legacy_non_migrated_metric_rows",
                        side_effect=non_migrated_metric_rows,
                        create=True,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "material_primary_rows",
                        return_value=[material],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "artifact_reference_text",
                        return_value="evidence/fixture.html",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "resolve_artifact_path",
                        return_value=workspace / "evidence" / "fixture.html",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "html_file_to_text",
                        return_value="ordinary public 10-K text",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "repair_c03_compensation",
                        side_effect=identity_three_rows,
                    )
                )
                for name in [
                    "repair_c02_board_text_from_governance",
                    "repair_basel_capital_ratios",
                    "repair_rpo_crpo_metrics",
                    "repair_captive_finance_debt",
                    "apply_8k_event_metrics_from_events",
                    "repair_c04_auditor_changes",
                ]:
                    stack.enter_context(
                        mock.patch.object(
                            sec_pipeline,
                            name,
                            side_effect=identity_two_rows,
                        )
                    )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "refresh_repair_sensitive_golden_results",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "migrate_portable_artifact_inventories",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "validation_package_mode",
                        return_value=("FULL_VALIDATION", []),
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline, "current_source_commit", return_value="fixture"
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline, "build_coverage_matrix", return_value=[]
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "build_companyfacts_crosscheck",
                        return_value=[],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "build_exceptions_markdown",
                        return_value="# Fixture exceptions\n",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "run_repair_validation",
                        return_value=[
                            {
                                "check_id": "validation_gate_result",
                                "severity": "P0",
                                "status": "PASS",
                                "details": "fixture",
                            }
                        ],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "projected_terminal_validation_manifest",
                        side_effect=projected_manifests,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "build_report_markdown",
                        side_effect=report_text,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline,
                        "build_readme",
                        return_value="# README_RUN\n",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        sec_pipeline, "finish_validation_run_manifest"
                    )
                )
                for name in RETIRED_RESOLVER_NAMES:
                    stack.enter_context(
                        mock.patch.object(
                            sec_pipeline,
                            name,
                            side_effect=retired_resolver,
                            create=True,
                        )
                    )

                for stage_name in [
                    "04_compute_standard_metrics",
                    "09_extract_mda_and_risk_text",
                    "11_build_report",
                ]:
                    sec_pipeline.run_stage(stage_name=stage_name)

            metric_ids = read_metric_ids(
                path=outputs / "metrics_matrix.csv"
            )
            self.assertFalse(metric_ids & MIGRATED_METRIC_IDS)
            self.assertIn("B02", metric_ids)


if __name__ == "__main__":
    unittest.main()
