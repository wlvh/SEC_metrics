"""Complete legacy projection, parity receipt, and write-gate tests."""

from __future__ import annotations

import copy
import unittest

from vnext.projector import ProjectionError, compatibility_receipt
from vnext.projector import project_evidence_rows, project_metric_rows
from vnext.projector import reconcile_component_evidence
from vnext.projector import reject_legacy_migrated_writes


class LegacyProjectorTest(unittest.TestCase):
    """Prove non-migrated preservation and explicit migrated deltas."""

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
