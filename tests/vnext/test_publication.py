"""Immutable bundle, atomic pointer, pinned view, CAS, and rollback tests."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Mapping, Optional
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_replay import create_full_release_run, freeze_fixture
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.projector import LEGACY_INPUT_FILES, build_projection_manifest
from vnext.publication import REQUIRED_BUNDLE_FILES, PublicationError
from vnext.publication import PublicationView, commit_publication
from vnext.publication import prepare_publication_bundle
from vnext.publication import publication_layout
from vnext.publication import publication_staging_context
from vnext.publication import publication_validation_view_id
from vnext.publication import recover_publication_mirrors, rollback_publication
from vnext.publication import verify_publication_bundle
from vnext.publication import write_latest_run_status
from vnext.records import validate_record
from vnext.run_store import create_run, fail_run, write_validation_receipt


PUBLICATION_CHECKS = (
    "COVERAGE",
    "GOLDEN",
    "LEGACY_INVARIANT_MIGRATION",
    "PROJECTION_EXACT_SET",
    "REPAIR_VALIDATION",
    "SCALABILITY_AUDIT",
    "SEMANTIC_AUDIT",
    "STRATIFIED_AUDIT",
)


def validation_receipt(
    *,
    files: Mapping[str, bytes],
    requirement_hashes: Mapping[str, str],
    run_content_hash: str,
    run_bindings: Mapping[str, object],
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Build one PASSED receipt bound to every non-receipt artifact byte.

    Args:
        files: Candidate bundle bytes excluding the receipt itself.
        requirement_hashes: Exact Requirement Snapshot identities.
        run_content_hash: FROZEN Run content identity for the staging view.
        run_bindings: Run identities excluding the receipt's self-binding.
        ledger_binding: Exact request-ledger prefix used by the candidate.
        previous_publication_id: Prepared predecessor identity.

    Returns:
        Strict non-self-referential ValidationReceipt.
    """
    body = {
        "status": "PASSED",
        "view_id": publication_validation_view_id(
            files=files,
            requirement_hashes=requirement_hashes,
            run_content_hash=run_content_hash,
            run_bindings=run_bindings,
            ledger_binding=ledger_binding,
            previous_publication_id=previous_publication_id,
        ),
        "checks": [
            {"check": check, "status": "PASS"}
            for check in PUBLICATION_CHECKS
        ],
        "artifact_hashes": {
            relative: {
                "sha256": sha256_bytes(content=files[relative]),
                "size": len(files[relative]),
            }
            for relative in sorted(files)
        },
    }
    record = dict(body)
    record.update(
        {
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=body),
        }
    )
    return validate_record(record=record)


def write_json(*, path: Path, value: Mapping[str, object]) -> None:
    """Persist deterministic JSON fixture bytes.

    Args:
        path: Destination file.
        value: JSON mapping.
    """
    path.write_bytes(canonical_json_bytes(value=value) + b"\n")


def staging_files(*, inputs: Mapping[str, object]) -> Dict[str, bytes]:
    """Read every non-self-referential staging artifact.

    Args:
        inputs: Public preparation kwargs.

    Returns:
        Exact bytes excluding the validation receipt.
    """
    staging_dir = inputs["staging_dir"]
    return {
        relative: (staging_dir / relative).read_bytes()
        for relative in REQUIRED_BUNDLE_FILES
        if relative != "publication_validation_receipt.json"
    }


def replace_receipt(
    *, inputs: Mapping[str, object], body: Mapping[str, object]
) -> None:
    """Replace a fixture receipt while keeping its identity consistent.

    Args:
        inputs: Preparation kwargs naming the staging directory.
        body: Receipt body without record type or identity.
    """
    receipt = dict(body)
    receipt.update(
        {
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=body),
        }
    )
    write_json(
        path=(
            inputs["staging_dir"]
            / "publication_validation_receipt.json"
        ),
        value=receipt,
    )


def resign_staging(*, inputs: Mapping[str, object]) -> None:
    """Regenerate a PASSED receipt after an intentional staging mutation.

    Args:
        inputs: Preparation kwargs naming Run, staging, ledger, and CAS state.
    """
    context = publication_staging_context(
        repo_root=inputs["repo_root"],
        run_dir=inputs["run_dir"],
        legacy_snapshot_dir=inputs["legacy_snapshot_dir"],
        staging_dir=inputs["staging_dir"],
    )
    receipt = validation_receipt(
        files=staging_files(inputs=inputs),
        requirement_hashes=context["requirement_hashes"],
        run_content_hash=context["run_content_hash"],
        run_bindings=context["run_bindings"],
        ledger_binding=inputs["ledger_binding"],
        previous_publication_id=inputs["previous_publication_id"],
    )
    write_json(
        path=(
            inputs["staging_dir"]
            / "publication_validation_receipt.json"
        ),
        value=receipt,
    )


def replace_projection(
    *, inputs: Mapping[str, object], changes: Mapping[str, object]
) -> None:
    """Re-sign a ProjectionManifest after one deliberate semantic mutation.

    Args:
        inputs: Preparation kwargs naming the staging directory.
        changes: Top-level ProjectionManifest fields to replace.
    """
    path = inputs["staging_dir"] / "projection_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(changes)
    body = {
        key: manifest[key]
        for key in manifest
        if key not in {"projection_manifest_id", "schema_version"}
    }
    manifest["projection_manifest_id"] = content_hash(value=body)
    write_json(path=path, value=manifest)


def publication_inputs(
    *, root: Path, tag: str, previous_publication_id: Optional[str]
) -> Dict[str, object]:
    """Create real FROZEN Run and persisted staging preparation inputs.

    Args:
        root: Publication test root used to isolate fixture locators.
        tag: Distinguishing artifact tag.
        previous_publication_id: Prepared CAS predecessor.

    Returns:
        Keyword-compatible preparation input mapping.
    """
    workspace = root / ".fixture-{}".format(tag)
    run_dir = workspace / "run"
    legacy_dir = workspace / "legacy"
    staging_dir = workspace / "staging"
    workspace.mkdir()
    legacy_dir.mkdir()
    staging_dir.mkdir()
    create_full_release_run(
        run_dir=run_dir,
        run_id="run:publication:" + tag,
    )
    freeze_fixture(run_dir=run_dir)
    for relative in LEGACY_INPUT_FILES:
        (legacy_dir / relative).write_bytes(
            "legacy:{}:{}\n".format(tag, relative).encode("utf-8")
        )
    for relative in REQUIRED_BUNDLE_FILES - {
        "projection_manifest.json",
        "publication_validation_receipt.json",
    }:
        (staging_dir / relative).write_bytes(
            "{}:{}\n".format(tag, relative).encode("utf-8")
        )
    projection = build_projection_manifest(
        repo_root=REPO_ROOT,
        run_dir=run_dir,
        legacy_snapshot_dir=legacy_dir,
        staging_dir=staging_dir,
    )
    write_json(
        path=staging_dir / "projection_manifest.json", value=projection,
    )
    inputs = {
        "repo_root": REPO_ROOT,
        "run_dir": run_dir,
        "legacy_snapshot_dir": legacy_dir,
        "staging_dir": staging_dir,
        "ledger_binding": {
            "requests_log_manifest_sha256": "a" * 64,
            "row_count": 1,
            "source_reference_ids": ["sha256:" + "b" * 64],
            "used_request_attempt_ids": ["request:attempt:fixture"],
        },
        "previous_publication_id": previous_publication_id,
    }
    resign_staging(inputs=inputs)
    return inputs


def mirror_paths(*, root: Path) -> Dict[str, Path]:
    """Map every required bundle file to one fixed-root compatibility mirror.

    Args:
        root: Mirror root.

    Returns:
        Exact mirror mapping.
    """
    return {relative: root / relative for relative in REQUIRED_BUNDLE_FILES}


def create_failed_run(*, run_dir: Path, run_id: str) -> None:
    """Persist one minimal hash-bound FAILED Run for latest-status tests.

    Args:
        run_dir: New Run directory.
        run_id: Stable Run identity, including adversarial identity reuse.
    """
    create_run(
        run_dir=run_dir,
        run_id=run_id,
        company_id="company_fixture",
        company_traits=["non_financial"],
        target_period={
            "fiscal_year": 2025,
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
        },
        source_references=[],
        missing_required_source_roles=[],
        spec_file_hashes={},
        requirement_hashes={},
    )
    write_validation_receipt(
        run_dir=run_dir,
        status="FAILED",
        checks=[{"check": "LATEST_FIXTURE", "status": "FAIL"}],
    )
    fail_run(run_dir=run_dir)


class PublicationTest(unittest.TestCase):
    """Prove only complete verified bundles become active."""

    def test_withheld_or_incomplete_bundle_cannot_prepare(self) -> None:
        """Block publication on applicable WITHHELD or missing files."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root,
                tag="blocked",
                previous_publication_id=None,
            )
            replace_projection(
                inputs=inputs,
                changes={"publication_candidate_status": "BLOCKED"},
            )
            resign_staging(inputs=inputs)
            with self.assertRaisesRegex(PublicationError, "BLOCKED"):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )
            inputs = publication_inputs(
                root=root, tag="missing", previous_publication_id=None,
            )
            (
                inputs["staging_dir"] / "REPORT_十公司财务指标.md"
            ).unlink()
            with self.assertRaisesRegex(PublicationError, "exact set"):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_projection_cannot_forge_run_or_release_identity(self) -> None:
        """Bind staged Result IDs and release bytes to the verified Run."""
        mutations = (
            {"result_ids": ["sha256:" + "f" * 64]},
            {"release_plan_sha256": "e" * 64},
        )
        for index, changes in enumerate(mutations):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                inputs = publication_inputs(
                    root=root,
                    tag="forged-projection-{}".format(index),
                    previous_publication_id=None,
                )
                replace_projection(inputs=inputs, changes=changes)
                resign_staging(inputs=inputs)

                with self.assertRaisesRegex(
                    PublicationError, "Run binding differs"
                ):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )

    def test_symlinked_publication_storage_cannot_escape_root(self) -> None:
        """Reject a publications directory redirected outside its root."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "publication"
            external = workspace / "external-publications"
            root.mkdir()
            external.mkdir()
            inputs = publication_inputs(
                root=root,
                tag="storage-symlink",
                previous_publication_id=None,
            )
            (root / "publications").symlink_to(
                external, target_is_directory=True,
            )

            with self.assertRaisesRegex(
                PublicationError, "storage must be a real directory"
            ):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_invalid_nested_ledger_binding_cannot_prepare(self) -> None:
        """Reject ambiguous row counts, digests, and duplicate source IDs."""
        invalid_values = (
            ("row_count", True),
            ("requests_log_manifest_sha256", "not-a-digest"),
            (
                "source_reference_ids",
                ["sha256:" + "b" * 64, "sha256:" + "b" * 64],
            ),
        )
        for field, value in invalid_values:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                inputs = publication_inputs(
                    root=root,
                    tag="invalid-ledger-" + field,
                    previous_publication_id=None,
                )
                inputs["ledger_binding"][field] = value
                with self.assertRaises(PublicationError):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )

    def test_latest_failed_attempt_is_visible_without_moving_active(
        self,
    ) -> None:
        """Keep a failed latest Run distinct from the usable active bundle."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-visible-active",
                    previous_publication_id=None,
                ),
            )
            commit_publication(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            path = root / "latest_run_status.json"
            failed_run = root / "failed-run"
            create_failed_run(
                run_dir=failed_run, run_id="run:failed:fixture",
            )
            status = write_latest_run_status(
                repo_root=REPO_ROOT,
                latest_run_dir=failed_run,
                latest_publication_id=None,
                message="Latest attempt failed; active is unchanged.",
                updated_at_utc="2026-07-29T13:00:00Z",
                publication_root=root,
            )
            self.assertEqual("FAILED", status["latest_run_status"])
            self.assertEqual(
                "NOT_EVALUATED", status["publication_candidate_status"],
            )
            self.assertEqual(
                status, json.loads(path.read_text(encoding="utf-8")),
            )

    def test_bundled_validation_receipt_must_match_run_binding(self) -> None:
        """Reject a PASS record paired with different bundled bytes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = publication_inputs(
                root=root, tag="receipt", previous_publication_id=None
            )
            (
                inputs["staging_dir"]
                / "publication_validation_receipt.json"
            ).write_bytes(b"{}\n")
            with self.assertRaisesRegex(
                PublicationError, "validation receipt"
            ):
                prepare_publication_bundle(
                    publication_root=root, **inputs,
                )

    def test_nonpassed_validation_receipt_cannot_prepare(self) -> None:
        """Keep FAILED and NOT_RUN audit Runs outside publication staging."""
        for status in ("FAILED", "NOT_RUN"):
            with self.subTest(status=status), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                inputs = publication_inputs(
                    root=root,
                    tag="validation-{}".format(status.lower()),
                    previous_publication_id=None,
                )
                receipt = json.loads(
                    (
                        inputs["staging_dir"]
                        / "publication_validation_receipt.json"
                    ).read_text(encoding="utf-8")
                )
                body = {
                    key: receipt[key]
                    for key in (
                        "status",
                        "view_id",
                        "checks",
                        "artifact_hashes",
                    )
                }
                body["status"] = status
                if status == "FAILED":
                    body["checks"][0] = {
                        "check": body["checks"][0]["check"],
                        "status": "FAIL",
                    }
                else:
                    body["checks"] = []
                    body["artifact_hashes"] = {}
                replace_receipt(inputs=inputs, body=body)
                with self.assertRaisesRegex(
                    PublicationError, "validation is not PASSED"
                ):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )

    def test_receipt_binds_exact_artifacts_checks_and_view(self) -> None:
        """Reject every receipt that did not validate this exact view."""
        mutations = (
            "hash",
            "size",
            "missing",
            "extra",
            "failed_check",
            "missing_check",
            "old_view",
            "requirement_hash",
            "run_binding",
            "ledger_binding",
            "predecessor",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                pointer = root / "active_publication.json"
                mirrors = mirror_paths(root=root)
                active = prepare_publication_bundle(
                    publication_root=root,
                    **publication_inputs(
                        root=root,
                        tag="active-" + mutation,
                        previous_publication_id=None,
                    ),
                )
                commit_publication(
                    publication_root=root,
                    publication_id=str(active["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-07-29T13:00:00Z",
                )
                pointer_before = pointer.read_bytes()
                mirrors_before = {
                    relative: mirrors[relative].read_bytes()
                    for relative in mirrors
                }
                inputs = publication_inputs(
                    root=root,
                    tag="receipt-" + mutation,
                    previous_publication_id=str(active["publication_id"]),
                )
                receipt = json.loads(
                    (
                        inputs["staging_dir"]
                        / "publication_validation_receipt.json"
                    ).read_text(encoding="utf-8")
                )
                body = {
                    key: receipt[key]
                    for key in (
                        "status",
                        "view_id",
                        "checks",
                        "artifact_hashes",
                    )
                }
                if mutation == "hash":
                    body["artifact_hashes"]["metrics_matrix.csv"][
                        "sha256"
                    ] = "0" * 64
                elif mutation == "size":
                    body["artifact_hashes"]["metrics_matrix.csv"]["size"] += 1
                elif mutation == "missing":
                    del body["artifact_hashes"]["metrics_matrix.csv"]
                elif mutation == "extra":
                    body["artifact_hashes"]["extra.csv"] = {
                        "sha256": "0" * 64,
                        "size": 0,
                    }
                elif mutation == "failed_check":
                    body["checks"][0]["status"] = "FAIL"
                elif mutation == "missing_check":
                    body["checks"] = body["checks"][1:]
                elif mutation == "old_view":
                    body["view_id"] = "staging:sha256:" + "0" * 64
                elif mutation == "requirement_hash":
                    projection = json.loads(
                        (
                            inputs["staging_dir"]
                            / "projection_manifest.json"
                        ).read_text(encoding="utf-8")
                    )
                    requirement_hashes = dict(
                        projection["requirement_hashes"]
                    )
                    requirement_hashes["baseline_sha256"] = "f" * 64
                    replace_projection(
                        inputs=inputs,
                        changes={
                            "requirement_hashes": requirement_hashes,
                        },
                    )
                    resign_staging(inputs=inputs)
                elif mutation == "run_binding":
                    replace_projection(
                        inputs=inputs,
                        changes={
                            "run_audit_manifest_hash": (
                                "sha256:" + "e" * 64
                            ),
                        },
                    )
                    resign_staging(inputs=inputs)
                elif mutation == "ledger_binding":
                    inputs["ledger_binding"]["row_count"] += 1
                elif mutation == "predecessor":
                    inputs["previous_publication_id"] = (
                        "publication_" + "d" * 64
                    )
                if mutation not in {
                    "requirement_hash",
                    "run_binding",
                    "ledger_binding",
                    "predecessor",
                }:
                    replace_receipt(inputs=inputs, body=body)
                with self.assertRaises(PublicationError):
                    prepare_publication_bundle(
                        publication_root=root, **inputs,
                    )
                self.assertEqual(pointer_before, pointer.read_bytes())
                self.assertEqual(
                    mirrors_before,
                    {
                        relative: mirrors[relative].read_bytes()
                        for relative in mirrors
                    },
                )

    def test_active_run_cannot_be_rebranded_failed_in_latest_status(
        self,
    ) -> None:
        """Reject one Run identity claiming active success and FAILED state."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-conflict",
                    previous_publication_id=None,
                ),
            )
            commit_publication(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            failed_run = root / "failed-run"
            create_failed_run(
                run_dir=failed_run,
                run_id=str(active["run_bindings"]["run_id"]),
            )
            with self.assertRaisesRegex(PublicationError, "conflicts"):
                write_latest_run_status(
                    repo_root=REPO_ROOT,
                    latest_run_dir=failed_run,
                    latest_publication_id=None,
                    message="Latest attempt failed.",
                    updated_at_utc="2026-07-29T13:01:00Z",
                    publication_root=root,
                )

    def test_latest_success_binds_corresponding_publication(self) -> None:
        """Derive latest-success from the latest and active bundle IDs."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-identity-active",
                    previous_publication_id=None,
                ),
            )
            commit_publication(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            latest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-identity-candidate",
                    previous_publication_id=str(active["publication_id"]),
                ),
            )
            status = write_latest_run_status(
                repo_root=REPO_ROOT,
                latest_run_dir=None,
                latest_publication_id=str(latest["publication_id"]),
                message="Latest candidate has not become active.",
                updated_at_utc="2026-07-29T13:00:00Z",
                publication_root=root,
            )
            self.assertFalse(status["active_is_latest_success"])
            self.assertEqual(
                active["publication_id"], status["active_publication_id"],
            )
            commit_publication(
                publication_root=root,
                publication_id=str(latest["publication_id"]),
                expected_active_publication_id=str(active["publication_id"]),
                committed_at_utc="2026-07-29T13:01:00Z",
            )
            status = write_latest_run_status(
                repo_root=REPO_ROOT,
                latest_run_dir=None,
                latest_publication_id=str(latest["publication_id"]),
                message="Latest publication is active.",
                updated_at_utc="2026-07-29T13:02:00Z",
                publication_root=root,
            )
            self.assertTrue(status["active_is_latest_success"])

    def test_publication_layout_is_derived_from_one_root(self) -> None:
        """Make pointer, status, storage, and mirror aliases inexpressible."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = publication_layout(publication_root=root)
            self.assertEqual(root / "publications", layout["publications_dir"])
            self.assertEqual(
                root / "active_publication.json", layout["pointer_path"],
            )
            self.assertEqual(
                root / "latest_run_status.json",
                layout["latest_status_path"],
            )
            self.assertEqual(
                {
                    relative: root / relative
                    for relative in REQUIRED_BUNDLE_FILES
                },
                layout["mirror_paths"],
            )
            self.assertEqual(
                {
                    "committed_at_utc",
                    "expected_active_publication_id",
                    "publication_id",
                    "publication_root",
                },
                set(inspect.signature(commit_publication).parameters),
            )
            self.assertEqual(
                {
                    "committed_at_utc",
                    "expected_active_publication_id",
                    "publication_root",
                    "target_publication_id",
                },
                set(inspect.signature(rollback_publication).parameters),
            )
            self.assertEqual(
                {"publication_root"},
                set(
                    inspect.signature(
                        recover_publication_mirrors
                    ).parameters
                ),
            )
            self.assertEqual(
                {"publication_root"},
                set(inspect.signature(PublicationView.open).parameters),
            )
            self.assertEqual(
                {
                    "latest_publication_id",
                    "latest_run_dir",
                    "message",
                    "publication_root",
                    "repo_root",
                    "updated_at_utc",
                },
                set(inspect.signature(write_latest_run_status).parameters),
            )

    def test_latest_status_revalidates_candidate_inside_pointer_lock(
        self,
    ) -> None:
        """Reject latest bundle drift at the serialized status boundary."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publications = root / "publications"
            active = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-lock-active",
                    previous_publication_id=None,
                ),
            )
            commit_publication(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            latest = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="latest-lock-candidate",
                    previous_publication_id=str(active["publication_id"]),
                ),
            )
            latest_metric = (
                publications
                / str(latest["publication_id"])
                / "metrics_matrix.csv"
            )

            def corrupt_latest(_descriptor: int, _operation: int) -> None:
                """Simulate concurrent byte drift exactly as the lock lands."""
                latest_metric.write_bytes(b"corrupt-after-precheck")

            with mock.patch(
                "vnext.publication.fcntl.flock", side_effect=corrupt_latest,
            ), self.assertRaises(PublicationError):
                write_latest_run_status(
                    repo_root=REPO_ROOT,
                    latest_run_dir=None,
                    latest_publication_id=str(latest["publication_id"]),
                    message="Latest candidate is still staging.",
                    updated_at_utc="2026-07-29T13:01:00Z",
                    publication_root=root,
                )

    def test_pinned_view_survives_forward_commit_and_rollback(self) -> None:
        """Read a pinned version while pointer and mirrors move."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirrors = mirror_paths(root=root)
            first_inputs = publication_inputs(
                root=root, tag="first", previous_publication_id=None,
            )
            first = prepare_publication_bundle(
                publication_root=root, **first_inputs,
            )
            commit_publication(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            pinned_first = PublicationView.open(
                publication_root=root,
            )
            second_inputs = publication_inputs(
                root=root,
                tag="second",
                previous_publication_id=str(first["publication_id"]),
            )
            second = prepare_publication_bundle(
                publication_root=root, **second_inputs,
            )
            commit_publication(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-07-29T13:01:00Z",
            )
            pinned_second = PublicationView.open(
                publication_root=root,
            )
            self.assertTrue(
                pinned_first.read_bytes(
                    relative_path="metrics_matrix.csv"
                ).startswith(b"first:")
            )
            self.assertTrue(
                pinned_second.read_bytes(
                    relative_path="metrics_matrix.csv"
                ).startswith(b"second:")
            )
            self.assertEqual(
                pinned_second.read_bytes(relative_path="metrics_matrix.csv"),
                mirrors["metrics_matrix.csv"].read_bytes(),
            )
            rollback_publication(
                publication_root=root,
                target_publication_id=str(first["publication_id"]),
                expected_active_publication_id=str(second["publication_id"]),
                committed_at_utc="2026-07-29T13:02:00Z",
            )
            rolled_back = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(
                first["publication_id"], rolled_back.publication_id
            )
            self.assertTrue(
                mirrors["metrics_matrix.csv"]
                .read_bytes()
                .startswith(b"first:")
            )

    def test_rollback_rejects_prepared_never_committed_sibling(self) -> None:
        """Allow rollback only to the committed predecessor."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirrors = mirror_paths(root=root)
            first = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root, tag="first", previous_publication_id=None,
                ),
            )
            commit_publication(
                publication_root=root,
                publication_id=str(first["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            second = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="second",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            sibling = prepare_publication_bundle(
                publication_root=root,
                **publication_inputs(
                    root=root,
                    tag="never-committed",
                    previous_publication_id=str(first["publication_id"]),
                ),
            )
            commit_publication(
                publication_root=root,
                publication_id=str(second["publication_id"]),
                expected_active_publication_id=str(first["publication_id"]),
                committed_at_utc="2026-07-29T13:01:00Z",
            )
            before = mirrors["metrics_matrix.csv"].read_bytes()
            with self.assertRaises(PublicationError):
                rollback_publication(
                    publication_root=root,
                    target_publication_id=str(sibling["publication_id"]),
                    expected_active_publication_id=str(
                        second["publication_id"]
                    ),
                    committed_at_utc="2026-07-29T13:02:00Z",
                )
            active = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(second["publication_id"], active.publication_id)
            self.assertEqual(
                before, mirrors["metrics_matrix.csv"].read_bytes(),
            )

    def test_mirror_recovery_and_cas_loss_preserve_active(self) -> None:
        """Repair mirrors from active and reject a stale publisher."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirrors = mirror_paths(root=root)
            inputs = publication_inputs(
                root=root, tag="active", previous_publication_id=None
            )
            active = prepare_publication_bundle(
                publication_root=root, **inputs,
            )
            commit_publication(
                publication_root=root,
                publication_id=str(active["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            mirrors["metrics_matrix.csv"].write_bytes(b"corrupt")
            recovered_id = recover_publication_mirrors(
                publication_root=root,
            )
            self.assertEqual(active["publication_id"], recovered_id)
            self.assertTrue(
                mirrors["metrics_matrix.csv"]
                .read_bytes()
                .startswith(b"active:")
            )
            with self.assertRaisesRegex(PublicationError, "CAS predecessor"):
                commit_publication(
                    publication_root=root,
                    publication_id=str(active["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-07-29T13:01:00Z",
                )
            current = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(active["publication_id"], current.publication_id)

    def test_symlinked_pointer_or_manifest_is_not_authoritative(self) -> None:
        """Reject authority files that resolve outside their named path."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publications = root / "publications"
            real_pointer = root / "real_pointer.json"
            pointer_alias = root / "active_publication.json"
            inputs = publication_inputs(
                root=root, tag="symlink", previous_publication_id=None,
            )
            manifest = prepare_publication_bundle(
                publication_root=root, **inputs,
            )
            commit_publication(
                publication_root=root,
                publication_id=str(manifest["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-07-29T13:00:00Z",
            )
            real_pointer.write_bytes(pointer_alias.read_bytes())
            pointer_alias.unlink()
            pointer_alias.symlink_to(real_pointer)
            with self.assertRaisesRegex(PublicationError, "pointer.*symlink"):
                PublicationView.open(publication_root=root)
            bundle_dir = publications / str(manifest["publication_id"])
            manifest_path = bundle_dir / "publication_manifest.json"
            redirected = root / "redirected_manifest.json"
            redirected.write_bytes(manifest_path.read_bytes())
            manifest_path.unlink()
            manifest_path.symlink_to(redirected)
            with self.assertRaisesRegex(PublicationError, "manifest.*real"):
                verify_publication_bundle(bundle_dir=bundle_dir)

    def test_two_concurrent_publishers_have_one_winner(self) -> None:
        """Serialize commits so a stale CAS publisher cannot win."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = [
                prepare_publication_bundle(
                    publication_root=root,
                    **publication_inputs(
                        root=root, tag=tag, previous_publication_id=None,
                    ),
                )
                for tag in ("publisher-a", "publisher-b")
            ]

            def publish(manifest: Mapping[str, object]) -> str:
                """Attempt one first-publication CAS commit."""
                commit_publication(
                    publication_root=root,
                    publication_id=str(manifest["publication_id"]),
                    expected_active_publication_id=None,
                    committed_at_utc="2026-07-29T13:00:00Z",
                )
                return str(manifest["publication_id"])

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(publish, manifest)
                    for manifest in manifests
                ]
                successes = []
                failures = []
                for future in futures:
                    try:
                        successes.append(future.result())
                    except PublicationError as error:
                        failures.append(str(error))
            self.assertEqual(1, len(successes))
            self.assertEqual(1, len(failures))
            active = PublicationView.open(
                publication_root=root,
            )
            self.assertEqual(successes[0], active.publication_id)


if __name__ == "__main__":
    unittest.main()
