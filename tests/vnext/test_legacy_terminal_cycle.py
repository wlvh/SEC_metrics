"""Rollback-terminal validation for the imported legacy predecessor."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.projection_fixture_support import scoped_repository
from tests.vnext.test_publication import complete_projection_fixture
from validation_provenance import _full_artifact_directory_paths, load_source_policy
from vnext.canonical import canonical_json_bytes
from vnext.publication import REQUIRED_BUNDLE_FILES
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import PublicationView
from vnext.publication import _commit_initial_publication_chain
from vnext.publication import _commit_publication
from vnext.publication import _write_cutover_publication_validation_receipt
from vnext.publication import prepare_legacy_baseline_predecessor
from vnext.publication import prepare_publication_bundle
from vnext.publication import rollback_publication
from vnext.report import validate_active_publication


OLD_LEGACY_SOURCE_COMMIT = "1" * 40


def _write_json(*, path: Path, value: object) -> None:
    """Write deterministic JSON fixture bytes.

    Args:
        path: Destination below the isolated repository.
        value: JSON-compatible fixture value.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value=value) + b"\n")


def _git(*, repo_root: Path, arguments: list[str]) -> str:
    """Run one deterministic Git command in the isolated repository.

    Args:
        repo_root: Temporary repository root.
        arguments: Git arguments excluding the executable and ``-C``.

    Returns:
        Stripped standard output.
    """
    completed = subprocess.run(
        args=["git", "-C", str(repo_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def _load_wrapper(*, path: Path, module_name: str) -> object:
    """Load one public stage wrapper from the isolated repository.

    Args:
        path: Exact wrapper path.
        module_name: Unique import name for the fixture.

    Returns:
        Imported wrapper module.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError("Public stage wrapper cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_legacy_terminal_artifacts(*, root: Path) -> None:
    """Create a historically passed legacy root without vNext metadata.

    Args:
        root: Future publication root and clean source checkout.

    Expected output:
        Every legacy-visible public artifact exists while the three vNext-only
        metadata roles remain absent for honest import synthesis.
    """
    if root.resolve() == REPO_ROOT.resolve():
        raise AssertionError("Legacy terminal artifacts require an isolated test fixture")
    readme = root / "README_RUN.md"
    if not readme.exists():
        shutil.copy2(REPO_ROOT / "README_RUN.md", readme)
    # This public mirror is also an immutable Issue #15 foundation receipt.
    # Keep the exact copied authority bytes while fabricating other legacy rows.
    scalability_relative = "outputs/scalability_audit.csv"
    scalability_bytes = (root / scalability_relative).read_bytes()
    foundation = json.loads((root / "requirements/issue_15_v1"
        / "foundation_verification_receipt.json").read_text(encoding="utf-8"))
    bindings = [binding for binding in foundation["receipt_bindings"]
                if binding["path"] == scalability_relative]
    if (len(bindings) != 1
            or scalability_bytes != (REPO_ROOT / scalability_relative).read_bytes()
            or bindings[0]["sha256"] != hashlib.sha256(scalability_bytes).hexdigest()
            or bindings[0]["size"] != len(scalability_bytes)):
        raise AssertionError("Legacy fixture must preserve exact foundation scalability bytes")
    manifest = {
        "run_id": "legacy-frozen-run",
        "source_commit": OLD_LEGACY_SOURCE_COMMIT,
        "started_at_utc": "2026-07-01T00:00:00+00:00",
        "mode": "FULL_VALIDATION",
        "refreshed_artifacts": [
            "repair_validation_results.csv",
            "stratified_audit.csv",
        ],
        "not_refreshed_artifacts": [],
        "result": "PASSED",
    }
    artifacts = {
        "REPORT_十公司财务指标.md": (
            "# Frozen legacy report\n\n"
            "- run_id: `legacy-frozen-run`\n"
            "- result: `PASSED`\n"
        ).encode("utf-8"),
        "coverage_matrix.csv": b"company,metric_id,status\nFixture,B01,OK\n",
        "golden_results.csv": (
            b"assertion_id,description,expected,actual,status,"
            b"evidence_path,notes\n"
            b"G1,legacy anchor,1,1,PASS,legacy.json,frozen\n"
        ),
        "metric_evidence.csv": b"company,metric_id\nFixture,B01\n",
        "metrics_matrix.csv": b"company,metric_id,value\nFixture,B01,1\n",
        "repair_validation_results.csv": b"check,status\nlegacy,PASS\n",
        "scalability_audit.csv": scalability_bytes,
        "semantic_audit_receipt.json": b'{"status":"PASSED"}\n',
        "stratified_audit.csv": b"check,status\nlegacy,PASS\n",
        "validation_run_manifest.json": (
            canonical_json_bytes(value=manifest) + b"\n"
        ),
    }
    for relative, content in artifacts.items():
        root_relative = ROOT_MIRROR_RELATIVE_PATHS[relative]
        destination = root / root_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    provenance = root / "outputs" / "validation_snapshot_provenance.json"
    provenance.write_bytes(b"frozen legacy provenance\n")
    (root / "outputs" / "events.csv").write_bytes(b"event\nlegacy\n")
    failure_dir = root / "outputs" / "failure_first_receipts"
    failure_dir.mkdir(parents=True, exist_ok=True)
    (failure_dir / "legacy.json").write_bytes(b'{"legacy":true}\n')
    attempt_dir = root / "evidence" / "request_attempts" / "legacy"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "attempt.bin").write_bytes(b"legacy attempt\n")
    policy = load_source_policy(workdir=root)
    for relative in policy.full_artifact_directories:
        audit_dir = root / relative
        audit_dir.mkdir(parents=True, exist_ok=True)
        if not any(path.is_file() for path in audit_dir.rglob("*")):
            # These bytes exercise the legacy snapshot file census only;
            # they are synthetic test fixtures with no qualification credit.
            (audit_dir / "legacy.json").write_bytes(
                b'{"legacy":true,"test_fixture_only":true,"qualification_credit":"NONE"}\n')
    _full_artifact_directory_paths(workdir=root,
        directories=policy.full_artifact_directories)


def _bind_legacy_authority(*, authority_root: Path, legacy_root: Path) -> None:
    """Bind a copied baseline manifest to the exact legacy root bytes.

    Args:
        authority_root: Independent Requirement authority used only by import.
        legacy_root: Frozen legacy public artifact root.
    """
    path = (
        authority_root
        / "requirements"
        / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    baseline = json.loads(path.read_text(encoding="utf-8"))
    for relative in sorted(baseline["artifact_digests"]):
        content = (legacy_root / relative).read_bytes()
        baseline["artifact_digests"][relative]["sha256"] = (
            hashlib.sha256(content).hexdigest()
        )
        baseline["artifact_digests"][relative]["size"] = len(content)
    _write_json(path=path, value=baseline)


class LegacyTerminalCycleTest(unittest.TestCase):
    """Prove A remains a terminal-readable predecessor without old producers."""

    def test_rollback_legacy_report_stage12_checker_then_restore(self) -> None:
        """Run B-to-A public terminal read-back and then restore B."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            successor_workspace = workspace / "successor"
            successor_workspace.mkdir()
            fixture = complete_projection_fixture(
                workspace=successor_workspace,
                tag="legacy-terminal-cycle",
            )
            root = Path(fixture["repo_root"])
            _write_legacy_terminal_artifacts(root=root)
            shutil.copy2(
                REPO_ROOT / "tools" / "check_validation_snapshot.py",
                root / "tools" / "check_validation_snapshot.py",
            )
            authority_workspace = workspace / "legacy-authority"
            authority_workspace.mkdir()
            authority = scoped_repository(workspace=authority_workspace)
            _bind_legacy_authority(
                authority_root=authority,
                legacy_root=root,
            )
            for arguments in (
                ["init", "--quiet"],
                ["config", "user.email", "fixture@example.test"],
                ["config", "user.name", "Fixture"],
                ["add", "."],
                ["commit", "--quiet", "-m", "legacy source closure"],
            ):
                _git(repo_root=root, arguments=arguments)
            legacy = prepare_legacy_baseline_predecessor(
                publication_root=root,
                repo_root=authority,
                legacy_root=root,
            )
            legacy_id = str(legacy["publication_id"])
            qualification = {"qualification_id": "sha256:" + "a" * 64}
            with mock.patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ), mock.patch(
                "vnext.publication.qualification_closure_paths",
                return_value=(),
            ):
                _write_cutover_publication_validation_receipt(
                    repo_root=root,
                    batch_manifest_path=Path(
                        fixture["batch_manifest_path"]
                    ),
                    legacy_snapshot_dir=Path(
                        fixture["legacy_snapshot_dir"]
                    ),
                    staging_dir=Path(fixture["staging_dir"]),
                    previous_publication_id=legacy_id,
                    validated_at_utc="2026-08-06T12:00:00Z",
                )
                successor = prepare_publication_bundle(
                    publication_root=root,
                    repo_root=root,
                    batch_manifest_path=Path(
                        fixture["batch_manifest_path"]
                    ),
                    legacy_snapshot_dir=Path(
                        fixture["legacy_snapshot_dir"]
                    ),
                    staging_dir=Path(fixture["staging_dir"]),
                    previous_publication_id=legacy_id,
                )
            successor_id = str(successor["publication_id"])
            with mock.patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ):
                _commit_initial_publication_chain(
                    publication_root=root,
                    legacy_predecessor_publication_id=legacy_id,
                    successor_publication_id=successor_id,
                    committed_at_utc="2026-08-06T12:01:00Z",
                )
            rollback_publication(
                publication_root=root,
                target_publication_id=legacy_id,
                expected_active_publication_id=successor_id,
                committed_at_utc="2026-08-06T12:02:00Z",
            )
            legacy_validation = validate_active_publication(
                publication_view=PublicationView.open(
                    publication_root=root
                ),
                publication_root=root,
            )
            self.assertEqual(
                "LEGACY_BASELINE_IMPORT",
                legacy_validation["publication_authority"],
            )
            self.assertEqual(
                "IMPORTED_FROZEN_LEGACY_BASELINE",
                legacy_validation["publication_validation_status"],
            )
            import sec_pipeline

            stage11 = _load_wrapper(
                path=root / "scripts" / "11_build_report.py",
                module_name="legacy_terminal_stage11",
            )
            stage12 = _load_wrapper(
                path=root / "scripts" / "12_validate_repair.py",
                module_name="legacy_terminal_stage12",
            )
            mirror_before = {
                relative: (root / mirror).read_bytes()
                for relative, mirror in ROOT_MIRROR_RELATIVE_PATHS.items()
            }
            with mock.patch.object(sec_pipeline, "WORKDIR", root):
                stage11.main(argv=[])
            with mock.patch.object(
                sec_pipeline, "WORKDIR", root,
            ), mock.patch.object(stage12, "WORKDIR", root):
                stage12.main()
            provenance = json.loads(
                (
                    root / "outputs" / "validation_snapshot_provenance.json"
                ).read_text(encoding="utf-8")
            )
            bundle_prefix = "outputs/publications/{}/".format(legacy_id)
            self.assertTrue(
                {
                    "outputs/active_publication.json",
                    bundle_prefix + "publication_manifest.json",
                    bundle_prefix + "validation_run_manifest.json",
                    bundle_prefix
                    + "internal/legacy_baseline_import.json",
                    bundle_prefix
                    + "internal/legacy_baseline_manifest.json",
                }.issubset(provenance["artifact_digests"])
            )
            mirror_after = {
                relative: (root / mirror).read_bytes()
                for relative, mirror in ROOT_MIRROR_RELATIVE_PATHS.items()
            }
            self.assertEqual(mirror_before, mirror_after)
            checker = subprocess.run(
                args=[
                    sys.executable,
                    str(root / "tools" / "check_validation_snapshot.py"),
                ],
                cwd=str(root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, checker.returncode, checker.stderr)
            with mock.patch(
                "vnext.publication.validate_cutover_qualifications",
                return_value=qualification,
            ):
                _commit_publication(
                    publication_root=root,
                    publication_id=successor_id,
                    expected_active_publication_id=legacy_id,
                    committed_at_utc="2026-08-06T12:03:00Z",
                )
                self.assertEqual(
                    successor_id,
                    PublicationView.open(
                        publication_root=root
                    ).publication_id,
                )


if __name__ == "__main__":
    unittest.main()
