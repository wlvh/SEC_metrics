"""Complete legacy projection, parity receipt, and write-gate tests."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from decimal import localcontext
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from tests.vnext.projection_fixture_support import scoped_repository
from vnext.projector import ProjectionError, compatibility_receipt
from vnext.projector import _joined_binding_field, _project_result
from vnext.projector import legacy_invariant_migration_receipt
from vnext.projector import load_legacy_path_inventory
from vnext.projector import _projection_value, golden_row_passes
from vnext.projector import project_evidence_rows, project_metric_rows
from vnext.projector import reconcile_component_evidence
from vnext.projector import reject_legacy_migrated_writes


class LegacyProjectorTest(unittest.TestCase):
    """Prove non-migrated preservation and explicit migrated deltas."""

    def test_repeated_component_form_collapses_to_frozen_scalar(self) -> None:
        """Keep B03 metric form scalar while evidence remains component grain."""
        self.assertEqual(
            "10-K",
            _joined_binding_field(
                bindings=({"form": "10-K"}, {"form": "10-K"}),
                field="form",
                fallback="10-K",
                collapse_equal=True,
            ),
        )
        with self.assertRaisesRegex(
            ProjectionError, "source binding values differ",
        ):
            _joined_binding_field(
                bindings=({"form": "10-K"}, {"form": "10-Q"}),
                field="form",
                fallback="10-K",
                collapse_equal=True,
            )

    def test_not_meaningful_result_preserves_frozen_compatibility_row(
        self,
    ) -> None:
        """Project a proven stub-period result without inventing source cells."""
        fields = (
            "company", "cik", "metric_id", "metric_name", "value", "unit",
            "status", "source_class", "formula", "period_start",
            "period_end", "fiscal_year", "fiscal_period", "accession",
            "form", "filed_date", "concept_or_section",
            "context_or_dimension", "confidence", "notes",
        )
        baseline = {field: "" for field in fields}
        baseline.update({
            "company": "Successor Stub",
            "cik": "42",
            "metric_id": "B01",
            "metric_name": "Revenue",
            "status": "NOT_MEANINGFUL",
            "source_class": "NOT_AVAILABLE",
            "formula": "direct companyfacts candidate chain",
            "period_start": "2025-08-08",
            "period_end": "2025-12-31",
            "accession": "0000000042-26-000001",
            "confidence": "0.00",
            "notes": "successor stub period; annual metric not comparable.",
        })
        row, evidence, contributor_count = _project_result(
            result={
                "applicability": "APPLICABLE",
                "metric_id": "B01",
                "period_start": "2025-08-08",
                "period_end": "2025-12-31",
                "quality": "NOT_MEANINGFUL",
                "unit": None,
                "value": None,
            },
            trace={},
            company={"display_name": "Successor Stub", "primary_cik": "42"},
            spec={
                "compiled": {
                    "legacy_projection": {},
                    "name": "Revenue",
                }
            },
            baseline_row=baseline,
            indexes={"observations": {}, "raw": {}, "sources": {}},
            fiscal_year="2025",
            metric_fields=fields,
        )
        self.assertEqual(baseline, row)
        self.assertEqual([], evidence)
        self.assertEqual(0, contributor_count)

    def test_legacy_migration_inventory_and_receipt_are_exact(self) -> None:
        """Bind every inventoried producer/check to one mechanical outcome."""
        inventory = load_legacy_path_inventory(repo_root=REPO_ROOT)
        receipt = legacy_invariant_migration_receipt(
            repo_root=REPO_ROOT,
            batch_manifest_id="sha256:" + "a" * 64,
            compatibility={
                "evidence_reconciliations": [],
                "legacy_input_hashes": {},
                "metric_cells": [],
                "status": "PASS",
            },
        )
        expected_ids = {
            entry["entry_id"] for entry in inventory["migration_entries"]
        }
        self.assertEqual(
            expected_ids,
            {entry["entry_id"] for entry in receipt["migration_entries"]},
        )
        self.assertEqual("PASS", receipt["status"])
        self.assertEqual(
            {"removed", "ported", "replaced", "obsolete-with-proof"},
            set(receipt["allowed_statuses"]),
        )
        self.assertTrue(
            {
                "special_metric_placeholders",
                "apply_stub_period_metric_semantics",
                "write_optional_b_sidecars",
                "prune_non_applicable_optional_b_metrics",
                "check_metrics_matrix_applicability_matches_02_04_spec",
                "check_no_unexpected_optional_b_metrics_in_main_matrix",
            }.issubset(
                {
                    entry["legacy_symbol"]
                    for entry in receipt["migration_entries"]
                }
            )
        )
        formal_writer_anchors = {
            "scripts/vnext/cutover.py::run_cutover",
            "scripts/vnext/publication.py::_commit_initial_publication_chain",
            "scripts/vnext/publication.py::_commit_publication",
        }
        migrated_writer_fields = {
            "additional_migrated_production_symbols",
            "legacy_write_entry_points",
        }
        for entry in receipt["migration_entries"]:
            self.assertIn(entry["status"], receipt["allowed_statuses"])
            if entry["inventory_field"] in migrated_writer_fields:
                self.assertTrue(
                    formal_writer_anchors.issubset(
                        set(entry["proof_anchors"])
                    ),
                    entry["entry_id"],
                )
                self.assertNotIn(
                    "scripts/vnext/publication.py::commit_publication",
                    entry["proof_anchors"],
                    entry["entry_id"],
                )

    def test_tombstone_proof_fails_when_retired_symbol_is_removed(
        self,
    ) -> None:
        """Reject an inventory claim after its fail-closed guard disappears."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(workspace=Path(directory))
            source_path = repo_root / "scripts" / "sec_pipeline.py"
            source = source_path.read_text(encoding="utf-8")
            needle = '    "lodging_header_order",\n'
            self.assertEqual(1, source.count(needle))
            source_path.write_text(
                source.replace(needle, "", 1), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ProjectionError, "lacks fail-closed tombstone"
            ):
                load_legacy_path_inventory(repo_root=repo_root)

    def test_migrated_writer_proof_rejects_public_commit_tombstone(
        self,
    ) -> None:
        """Require the migration receipt to name the real Cutover writer."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = scoped_repository(workspace=Path(directory))
            inventory_path = (
                repo_root
                / "requirements"
                / "ai_first_v3_3_1"
                / "legacy_path_inventory.json"
            )
            inventory = json.loads(
                inventory_path.read_text(encoding="utf-8")
            )
            for field in (
                "legacy_write_entry_points",
                "additional_migrated_production_symbols",
            ):
                inventory["migration_rules"][field]["proof_anchors"] = [
                    "scripts/sec_pipeline.py::assert_legacy_candidate_rows",
                    "scripts/vnext/projector.py::write_projection_candidate",
                    "scripts/vnext/publication.py::commit_publication",
                ]
            inventory_path.write_text(
                json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ProjectionError, "formal Cutover writer anchors"
            ):
                load_legacy_path_inventory(repo_root=repo_root)

    def test_projector_arithmetic_ignores_global_decimal_context(self) -> None:
        """Keep projection bytes and Golden verdict on contract precision."""
        with localcontext() as context:
            context.prec = 3
            projected = _projection_value(
                result={
                    "value": "0.12345678901234567890123456789",
                },
                projection={"value_multiplier": "100"},
            )
            golden_passed = golden_row_passes(
                row={
                    "expected": "0",
                    "actual": "0.00005004",
                    "notes": "diff=0.00005004 tolerance=0.00005",
                }
            )
        with self.subTest(boundary="projection"):
            self.assertEqual(
                "12.34567890123456789012345679",
                projected,
            )
        with self.subTest(boundary="golden"):
            self.assertFalse(golden_passed)

    def test_complete_metric_projection_preserves_nonmigrated_order(
        self,
    ) -> None:
        """Replace migrated keys and preserve every other row value."""
        fieldnames = ["company", "metric_id", "value", "status"]
        legacy = [
            {"company": "A", "metric_id": "B01", "value": "1", "status": "OK"},
            {"company": "A", "metric_id": "B02", "value": "2", "status": "OK"},
            {"company": "B", "metric_id": "B03", "value": "3", "status": "OK"},
        ]
        key = ("A", "B01")
        replacement = {
            key: {
                "company": "A",
                "metric_id": "B01",
                "value": "1",
                "status": "OK",
            }
        }
        projected = project_metric_rows(
            legacy_rows=legacy,
            migrated_keys={key},
            replacement_rows=replacement,
            fieldnames=fieldnames,
        )
        self.assertEqual(legacy, projected)
        self.assertEqual(legacy[1:], projected[1:])

    def test_component_evidence_replaces_one_legacy_aggregate(self) -> None:
        """Emit source-grain rows and rebuild the frozen aggregate."""
        fieldnames = [
            "company",
            "metric_id",
            "accession",
            "concept",
            "value_raw",
            "evidence_order",
        ]
        key = ("A", "B03")
        legacy = [
            {
                "company": "A",
                "metric_id": "B03",
                "accession": "a;a",
                "concept": "OperatingIncomeLoss+Depreciation",
                "value_raw": "100;20",
                "evidence_order": "legacy",
            }
        ]
        components = [
            {
                "company": "A",
                "metric_id": "B03",
                "accession": "a",
                "concept": "OperatingIncomeLoss",
                "value_raw": "100",
                "evidence_order": 0,
            },
            {
                "company": "A",
                "metric_id": "B03",
                "accession": "a",
                "concept": "Depreciation",
                "value_raw": "20",
                "evidence_order": 1,
            },
        ]
        projected = project_evidence_rows(
            legacy_rows=legacy,
            migrated_keys={key},
            replacement_rows={key: components},
            fieldnames=fieldnames,
        )
        self.assertEqual(2, len(projected))
        receipt = reconcile_component_evidence(
            component_rows=components,
            baseline_row=legacy[0],
            joined_fields=["accession", "value_raw"],
            concept_field="concept",
            value_separator=";",
            concept_separator="+",
        )
        self.assertEqual("PASS", receipt["status"])

    def test_exact_field_drift_fails_but_method_delta_is_recorded(
        self,
    ) -> None:
        """Separate parity from the approved declarative method delta."""
        key = ("Marriott International", "B10")
        baseline = {
            key: {"value": "69.3", "unit": "percent", "notes": "legacy"}
        }
        method_changed = {
            key: {"value": "69.3", "unit": "percent", "notes": "reviewed"}
        }
        receipt = compatibility_receipt(
            baseline_rows=baseline,
            projected_rows=method_changed,
            exact_fields=["value", "unit"],
            allowed_delta_fields=["notes"],
        )
        self.assertEqual("PASS", receipt["status"])
        changed_value = copy.deepcopy(method_changed)
        changed_value[key]["value"] = "73.1"
        failed = compatibility_receipt(
            baseline_rows=baseline,
            projected_rows=changed_value,
            exact_fields=["value", "unit"],
            allowed_delta_fields=["notes"],
        )
        self.assertEqual("FAIL", failed["status"])

    def test_legacy_migrated_write_gate_detects_any_mutation(self) -> None:
        """Raise a stable error on addition, deletion, or field drift."""
        before = [
            {"company": "A", "metric_id": "B01", "value": "1"},
            {"company": "A", "metric_id": "B02", "value": "2"},
        ]
        reject_legacy_migrated_writes(
            before_rows=before,
            after_rows=copy.deepcopy(before),
            migrated_keys={("A", "B01")},
        )
        after = copy.deepcopy(before)
        after[0]["value"] = "changed"
        with self.assertRaisesRegex(
            ProjectionError, "LEGACY_PATH_STILL_ACTIVE"
        ):
            reject_legacy_migrated_writes(
                before_rows=before,
                after_rows=after,
                migrated_keys={("A", "B01")},
            )
        duplicated = copy.deepcopy(before)
        duplicated.insert(1, copy.deepcopy(before[0]))
        with self.assertRaisesRegex(
            ProjectionError, "LEGACY_PATH_STILL_ACTIVE"
        ):
            reject_legacy_migrated_writes(
                before_rows=before,
                after_rows=duplicated,
                migrated_keys={("A", "B01")},
            )

    def test_replacement_mapping_key_must_match_row_identity(self) -> None:
        """Reject a replacement row stored under another company key."""
        fieldnames = ["company", "metric_id", "value", "status"]
        key = ("A", "B01")
        replacement = {
            key: {
                "company": "B",
                "metric_id": "B01",
                "value": "1",
                "status": "OK",
            }
        }
        with self.assertRaisesRegex(ProjectionError, "identity"):
            project_metric_rows(
                legacy_rows=[
                    {
                        "company": "A",
                        "metric_id": "B01",
                        "value": "1",
                        "status": "OK",
                    }
                ],
                migrated_keys={key},
                replacement_rows=replacement,
                fieldnames=fieldnames,
            )


if __name__ == "__main__":
    unittest.main()
