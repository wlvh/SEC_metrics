"""Requirement Snapshot, baseline, and Decision Register regressions."""

from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from vnext.requirements import (
    FSD_SHA256,
    RequirementError,
    effective_decisions,
    load_requirement_snapshot,
)


class RequirementBaselineTest(unittest.TestCase):
    """Prove exact requirement bytes and decision chains fail closed."""

    def test_exact_snapshot_binds_r2_r3_release_and_approved_d01(self) -> None:
        """Bind both contracts and resolve D-01 without erasing its pending root."""
        snapshot = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1"
        )
        self.assertEqual(FSD_SHA256, snapshot["hashes"]["fsd_sha256"])
        self.assertEqual(
            "R2_WITH_R3_ADDENDUM", snapshot["issue_contract_revision"]
        )
        self.assertEqual(
            "99da847c034aba9c206b480d79d510ca64f9c622a79e6366567151e692307ca3",
            snapshot["hashes"]["r3_addendum_sha256"],
        )
        self.assertIn("release_plan_sha256", snapshot["hashes"])
        self.assertIn("semantic_runtime_versions_hash", snapshot["hashes"])
        self.assertNotIn("D-01", snapshot["pending_decision_ids"])
        d01 = snapshot["effective_decisions"]["D-01"]
        self.assertEqual("APPROVED", d01["status"])
        self.assertEqual("openai", d01["choice"]["provider"])
        self.assertEqual("gpt-5.6-terra", d01["choice"]["model"])
        self.assertEqual("responses", d01["choice"]["api"])
        self.assertTrue(d01["supersedes_decision_id"].startswith("sha256:"))
        self.assertEqual(
            "PENDING_EXTERNAL_APPROVAL",
            snapshot["decision_chains"]["D-01"][0]["status"],
        )
        self.assertEqual(
            "0.01",
            snapshot["effective_decisions"]["D-08"]["choice"][
                "lodging_identity_relative_tolerance"
            ],
        )
        self.assertEqual(
            "PRESERVE_SELECTED_REPORTED_UNIT",
            snapshot["effective_decisions"]["D-05"]["choice"][
                "b01_result_unit"
            ],
        )
        self.assertEqual(
            "APPROVED_FAIL_CLOSED_DIVERGENCE_FROM_LEGACY",
            snapshot["effective_decisions"]["D-05"]["choice"][
                "b03_unit_parity"
            ],
        )
        self.assertEqual(
            "c37cecdfe88344d78172dd9dc24bd4c445763901",
            snapshot["baseline"]["repository_commit"],
        )
        d26 = snapshot["effective_decisions"]["D-26"]
        self.assertEqual("APPROVED", d26["status"])
        self.assertEqual(
            "R4_FAST_CONCURRENT_NON_ISOLATED",
            d26["choice"]["test_execution_policy"],
        )
        self.assertEqual(30, d26["choice"]["per_case_timeout_seconds"])
        self.assertEqual(
            60, d26["choice"]["recorded_gate_timeout_seconds"],
        )

    def test_requirement_byte_change_invalidates_snapshot(self) -> None:
        """Reject an FSD byte edit even when every other file is unchanged."""
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "snapshot"
            shutil.copytree(
                REPO_ROOT / "requirements/ai_first_v3_3_1", destination,
            )
            with (destination / "FSD.md").open(mode="ab") as file_obj:
                file_obj.write(b"\n")
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=destination)

    def test_r3_addendum_byte_change_invalidates_snapshot(self) -> None:
        """Reject mutable Issue drift after the exact R3 bytes are frozen."""
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "snapshot"
            shutil.copytree(
                REPO_ROOT / "requirements/ai_first_v3_3_1", destination,
            )
            with (destination / "ISSUE_CONTRACT_R3_ADDENDUM.md").open(
                mode="ab"
            ) as file_obj:
                file_obj.write(b"\n")
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=destination)

    def test_parallel_decision_children_fail_closed(self) -> None:
        """Reject two records that supersede the same effective parent."""
        root = {
            "decision_id": "D-99",
            "status": "APPROVED",
            "choice": {"value": "root"},
            "approved_by": "human:one",
            "approved_at_utc": "2026-07-29T13:00:00Z",
            "supersedes_decision_id": None,
            "evidence": "test",
        }
        from vnext.canonical import content_hash

        parent = content_hash(value=root)
        first = copy.deepcopy(root)
        first["choice"] = {"value": "first"}
        first["supersedes_decision_id"] = parent
        second = copy.deepcopy(root)
        second["choice"] = {"value": "second"}
        second["supersedes_decision_id"] = parent
        with self.assertRaises(RequirementError):
            effective_decisions(decisions=[root, first, second])

    def test_decision_timestamp_suffix_is_not_enough(self) -> None:
        """Parse the complete UTC timestamp instead of trusting its suffix."""
        decision = {
            "decision_id": "D-99",
            "status": "APPROVED",
            "choice": {"value": "fixture"},
            "approved_by": "human:one",
            "approved_at_utc": "not-a-timestampZ",
            "supersedes_decision_id": None,
            "evidence": "test",
        }
        with self.assertRaisesRegex(RequirementError, "timestamp"):
            effective_decisions(decisions=[decision])


if __name__ == "__main__":
    unittest.main()
