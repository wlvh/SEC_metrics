"""Formal publication-tier generation tests."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.test_publication import complete_projection_fixture
from vnext.publication import PublicationError
from vnext.publication import _write_cutover_publication_validation_receipt
from vnext.publication import commit_initial_publication_chain
from vnext.publication import commit_publication
from vnext.publication import prepare_publication_bundle
from vnext.publication import write_cutover_publication_validation_receipt


class FormalPublicationTest(unittest.TestCase):
    """Prove active candidates cannot carry recorded-only declarations."""

    def test_public_formal_mutation_apis_require_cutover_orchestrator(
        self,
    ) -> None:
        """Reject formal writer and commits outside the single orchestrator."""
        with tempfile.TemporaryDirectory() as directory, patch(
            "vnext.publication.validate_cutover_qualifications",
            return_value={"qualification_id": "sha256:" + "a" * 64},
        ), patch(
            "vnext.publication._write_publication_validation_receipt",
            return_value={"status": "PASSED"},
        ):
            root = Path(directory)
            with self.assertRaisesRegex(
                PublicationError, "FORMAL_CUTOVER_AUTHORITY_REQUIRED",
            ):
                write_cutover_publication_validation_receipt(
                    repo_root=root,
                    batch_manifest_path=root / "batch.json",
                    legacy_snapshot_dir=root / "legacy",
                    staging_dir=root / "staging",
                    previous_publication_id=None,
                    validated_at_utc="2026-08-06T00:00:00Z",
                )
            with self.assertRaisesRegex(
                PublicationError, "FORMAL_CUTOVER_AUTHORITY_REQUIRED",
            ):
                commit_publication(
                    publication_root=root,
                    publication_id="publication_" + "b" * 64,
                    expected_active_publication_id="publication_" + "a" * 64,
                    committed_at_utc="2026-08-06T00:00:00Z",
                )
            with self.assertRaisesRegex(
                PublicationError, "FORMAL_CUTOVER_AUTHORITY_REQUIRED",
            ):
                commit_initial_publication_chain(
                    publication_root=root,
                    legacy_predecessor_publication_id=(
                        "publication_" + "a" * 64
                    ),
                    successor_publication_id="publication_" + "b" * 64,
                    committed_at_utc="2026-08-06T00:00:00Z",
                )

    def test_cutover_candidate_generates_full_manifest_and_documents(
        self,
    ) -> None:
        """Generate a formally attestable bundle from one clean Git tree."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            fixture_root = workspace / "fixture"
            fixture_root.mkdir()
            inputs = complete_projection_fixture(
                workspace=fixture_root,
                tag="formal-cutover-documents",
            )
            repo_root = inputs["repo_root"]
            for argv in (
                ["git", "init", "--quiet"],
                ["git", "config", "user.email", "fixture@example.com"],
                ["git", "config", "user.name", "Fixture"],
                ["git", "add", "."],
                ["git", "commit", "--quiet", "-m", "fixture"],
            ):
                completed = subprocess.run(
                    argv,
                    cwd=str(repo_root),
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
            qualification = {
                "qualification_id": "sha256:" + "a" * 64,
            }
            with patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ), patch(
                "vnext.publication.qualification_closure_paths",
                return_value=(),
            ):
                receipt = _write_cutover_publication_validation_receipt(
                    repo_root=repo_root,
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=None,
                    validated_at_utc="2026-08-06T00:00:00Z",
                )
                manifest = prepare_publication_bundle(
                    publication_root=workspace / "publication-root",
                    repo_root=repo_root,
                    batch_manifest_path=inputs["batch_manifest_path"],
                    legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
                    staging_dir=inputs["staging_dir"],
                    previous_publication_id=None,
                )
            validation = json.loads(
                (
                    inputs["staging_dir"]
                    / "validation_run_manifest.json"
                ).read_text(encoding="utf-8")
            )
            readme = (
                inputs["staging_dir"] / "README_RUN.md"
            ).read_text(encoding="utf-8")
            report = (
                inputs["staging_dir"] / "REPORT_十公司财务指标.md"
            ).read_text(encoding="utf-8")
        self.assertEqual("PASSED", receipt["status"])
        self.assertEqual("PUBLISHABLE", manifest["candidate_status"])
        self.assertEqual("FULL_VALIDATION", validation["mode"])
        self.assertEqual("PASSED", validation["result"])
        self.assertRegex(validation["source_commit"], r"^[0-9a-f]{40}$")
        self.assertIn("vNext formal publication bundle", readme)
        self.assertNotIn("recorded/shadow only", readme)
        self.assertIn("vNext formal publication report", report)
        self.assertIn("validation-snapshot-provenance:start", report)


if __name__ == "__main__":
    unittest.main()
