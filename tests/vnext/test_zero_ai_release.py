"""Verify the committed Issue #15 zero-AI R1 publication evidence."""

from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, sha256_file
from vnext.publication import PublicationError, PublicationView
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import ZERO_AI_FORMAL_MANIFEST
from vnext.publication import verify_publication_bundle


ZERO_COUNTERS = {
    "mock_transport_invocation_count": 0,
    "paid_model_provider_call_count": 0,
    "real_model_provider_egress_count": 0,
}


class ZeroAiReleaseTest(unittest.TestCase):
    """Prove R1 is active evidence rather than a recorded-only claim."""

    def test_r1_active_rollback_restore_and_read_back_are_bound(self) -> None:
        """Verify final B, predecessor A, seven receipt roles, and mirrors."""
        view = PublicationView.open(publication_root=REPO_ROOT)
        marker = json.loads(
            view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode("utf-8")
        )
        self.assertEqual("R1", marker["release_stage"])
        self.assertEqual("PASSED", marker["status"])
        self.assertEqual(ZERO_COUNTERS, marker["counters"])
        self.assertEqual(["B01", "B03"], marker["cumulative_metric_ids"])
        self.assertEqual(20, marker["result_coordinate_count"])
        self.assertEqual(18, marker["replaced_legacy_row_count"])
        self.assertEqual(2, marker["new_public_key_count"])
        self.assertEqual(232, marker["public_matrix_row_count"])

        predecessor_dir = (
            REPO_ROOT
            / "outputs"
            / "publications"
            / marker["previous_publication_id"]
        )
        predecessor = verify_publication_bundle(bundle_dir=predecessor_dir)
        self.assertIsNone(predecessor["previous_publication_id"])
        self.assertTrue(
            (predecessor_dir / "internal/legacy_baseline_import.json").is_file()
        )

        index = json.loads(
            (
                REPO_ROOT
                / "outputs"
                / "zero_ai_release_receipts"
                / "r1"
                / "index.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual("PASSED", index["status"])
        self.assertEqual(ZERO_COUNTERS, index["counters"])
        self.assertEqual(
            {
                "active_terminal",
                "initial_read_back",
                "predecessor",
                "restore_read_back",
                "restore_terminal",
                "retirement",
                "rollback_terminal",
                "successor_publication",
            },
            set(index["receipts"]),
        )
        for binding in index["receipts"].values():
            path = REPO_ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

        for relative, mirror_relative in ROOT_MIRROR_RELATIVE_PATHS.items():
            self.assertEqual(
                view.read_bytes(relative_path=relative),
                (REPO_ROOT / mirror_relative).read_bytes(),
            )

    def test_r1_public_key_set_and_structural_additions_are_exact(self) -> None:
        """Prove 232 unique keys and only two new structural coordinates."""
        view = PublicationView.open(publication_root=REPO_ROOT)
        marker = json.loads(
            view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode("utf-8")
        )
        rows = list(
            csv.DictReader(
                io.StringIO(
                    view.read_bytes(relative_path="metrics_matrix.csv").decode(
                        "utf-8"
                    )
                )
            )
        )
        keys = sorted(
            (
                {"company": row["company"], "metric_id": row["metric_id"]}
                for row in rows
            ),
            key=lambda row: (row["company"], row["metric_id"]),
        )
        self.assertEqual(232, len(keys))
        self.assertEqual(232, len({(row["company"], row["metric_id"]) for row in keys}))
        self.assertEqual(marker["public_key_set_hash"], content_hash(value=keys))
        additions = [
            row
            for row in rows
            if row["company"] == "JPMorgan Chase"
            and row["metric_id"] in {"B01", "B03"}
        ]
        self.assertEqual(2, len(additions))
        self.assertTrue(
            all(
                row["status"] == "N_A_STRUCTURAL"
                and row["source_class"] == "STRUCTURAL"
                and not row["value"]
                for row in additions
            )
        )

    def test_r1_marker_tamper_fails_closed(self) -> None:
        """Reject a forged nonzero egress counter in an otherwise copied B."""
        view = PublicationView.open(publication_root=REPO_ROOT)
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "bundle"
            shutil.copytree(view.bundle_dir, copied)
            marker_path = copied / ZERO_AI_FORMAL_MANIFEST
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["counters"]["real_model_provider_egress_count"] = 1
            body = {
                field: marker[field]
                for field in marker
                if field != "zero_ai_release_receipt_id"
            }
            marker["zero_ai_release_receipt_id"] = content_hash(value=body)
            marker_path.write_text(
                json.dumps(
                    marker,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(PublicationError):
                verify_publication_bundle(bundle_dir=copied)


if __name__ == "__main__":
    unittest.main()
