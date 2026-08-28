"""Verify the Issue #15 R3 delta uses existing projection and CAS gates."""

from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from vnext.publication import REQUIRED_BUNDLE_FILES, publication_state_snapshot
from vnext.publication import verify_publication_bundle
from vnext.ratchet_release import RatchetReleaseError
from vnext.ratchet_release import _committed_run_origin
from vnext.ratchet_release import _validate_committed_qualification_run
from vnext.ratchet_release import prepare_r3_successor


class RatchetReleaseTest(unittest.TestCase):
    """Prove the R3 delta is complete, offline, monotonic, and replayable."""

    @classmethod
    def setUpClass(cls) -> None:
        """Prepare one real temporary successor for all read-only assertions."""
        cls.temporary = tempfile.TemporaryDirectory(prefix="r3-release-test-")
        cls.temp_root = Path(cls.temporary.name)
        cls.before_state = publication_state_snapshot(
            publication_root=REPO_ROOT,
        )
        cls.before_pointer = (
            REPO_ROOT / "outputs/active_publication.json"
        ).read_bytes()
        cls.before_roots = {
            relative: (REPO_ROOT / relative).read_bytes()
            for relative in (
                "outputs/metrics_matrix.csv",
                "outputs/metric_evidence.csv",
                "outputs/coverage_matrix.csv",
                "REPORT_十公司财务指标.md",
            )
        }
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
            encoding="utf-8",
        ).stdout.strip()
        cls.successor, cls.summary = prepare_r3_successor(
            repo_root=REPO_ROOT,
            publication_root=cls.temp_root / "publication-root",
            source_commit=source_commit,
            validated_at_utc="2026-08-28T10:00:00Z",
            workspace=cls.temp_root / "workspace",
        )
        cls.bundle = (
            cls.temp_root / "publication-root/outputs/publications"
            / str(cls.successor["publication_id"])
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_prepare_is_offline_complete_and_non_mutating(self) -> None:
        """Bind 20 results, 327 public keys, ten proofs, and unchanged active."""
        self.assertEqual(
            self.before_state,
            publication_state_snapshot(publication_root=REPO_ROOT),
        )
        self.assertEqual(
            self.before_pointer,
            (REPO_ROOT / "outputs/active_publication.json").read_bytes(),
        )
        for relative, content in self.before_roots.items():
            self.assertEqual(content, (REPO_ROOT / relative).read_bytes())
        manifest = verify_publication_bundle(bundle_dir=self.bundle)
        self.assertEqual(self.successor, manifest)
        self.assertEqual(
            self.before_state["active_publication_id"],
            manifest["previous_publication_id"],
        )
        self.assertEqual(327, self.summary["public_matrix_row_count"])
        self.assertEqual(10, self.summary["qualification"]["ledger_row_count"])
        self.assertEqual(
            10, len(self.summary["qualification"]["terminal_validations"]),
        )
        rows = list(csv.DictReader(io.StringIO(
            (self.bundle / "metrics_matrix.csv").read_text(encoding="utf-8")
        )))
        self.assertEqual(327, len(rows))
        delta = [row for row in rows if row["metric_id"] in {"B10", "B11"}]
        self.assertEqual(20, len(delta))
        self.assertEqual(18, sum(row["status"] == "N_A_STRUCTURAL" for row in delta))
        applicable = [row for row in delta if row["status"] != "N_A_STRUCTURAL"]
        self.assertEqual(
            [("B10", "69.3", "percent"), ("B11", "128.8", "USD")],
            sorted((row["metric_id"], row["value"], row["unit"]) for row in applicable),
        )
        projection = json.loads(
            (self.bundle / "projection_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(20, len(projection["expected_result_keys"]))
        self.assertEqual(20, len(projection["result_ids"]))
        self.assertEqual("PUBLISHABLE", projection["publication_candidate_status"])
        compatibility = json.loads(
            (self.bundle / "legacy_invariant_migration_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("PASS", compatibility["status"])
        validation = json.loads(
            (self.bundle / "publication_validation_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("PASSED", validation["status"])
        self.assertEqual(
            set(REQUIRED_BUNDLE_FILES) - {"publication_validation_receipt.json"},
            set(validation["artifact_hashes"]),
        )
        closure = json.loads(
            (self.bundle / "internal/closure_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        closure_paths = {row["path"] for row in closure["files"]}
        self.assertIn("internal/batch/batch_manifest.json", closure_paths)
        self.assertEqual(
            10, closure["qualification_binding"]["ledger_row_count"],
        )
        self.assertTrue(any(path.endswith("provider_ledger.jsonl") for path in closure_paths))
        self.assertTrue(any("qualification_runs" in path for path in closure_paths))

    def test_committed_qualification_tamper_is_rejected(self) -> None:
        """Reject a copied terminal whose bytes differ from its Git origin."""
        original = REPO_ROOT / (
            "artifacts/vnext/qualification/cycles/"
            "0c4569437b1bac3ad353394c8d8b1f59b1a1ee7c229c8fa5ee51a22269b6a448/"
            "runs/0d790e325de331d3d2213946611647cce06fd6dc843c6f18483c34492ff36995"
        )
        origin = _committed_run_origin(repo_root=REPO_ROOT, run_dir=original)
        with tempfile.TemporaryDirectory(prefix="r3-run-tamper-") as temporary:
            copied = Path(temporary) / "run"
            shutil.copytree(original, copied)
            decisions = copied / "review_decisions.jsonl"
            decisions.write_bytes(decisions.read_bytes() + b" ")
            with self.assertRaises(RatchetReleaseError):
                _validate_committed_qualification_run(
                    repo_root=REPO_ROOT,
                    run_dir=copied,
                    origin=origin,
                )


if __name__ == "__main__":
    unittest.main()
