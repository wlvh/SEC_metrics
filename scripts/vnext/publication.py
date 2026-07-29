"""Publish immutable complete bundles through one atomic active pointer."""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

from .canonical import CanonicalError, atomic_write_bytes, atomic_write_json
from .canonical import content_hash, parse_utc_timestamp
from .canonical import sha256_bytes, sha256_file, strict_json_file
from .canonical import strict_json_loads
from .projector import LEGACY_INPUT_FILES, PROJECTION_CANDIDATE_FILES
from .projector import PROJECTION_GATE_FILES, build_projection_manifest
from .projector import projection_file_hashes
from .records import validate_record
from .run_store import RunStoreError, load_run_for_status
from .states import PUBLISHABLE_VALIDATION_STATUSES
from .states import publication_candidate_status


REQUIRED_BUNDLE_FILES = {
    "README_RUN.md",
    "REPORT_十公司财务指标.md",
    "coverage_matrix.csv",
    "golden_results.csv",
    "legacy_invariant_migration_receipt.json",
    "metric_evidence.csv",
    "metrics_matrix.csv",
    "projection_manifest.json",
    "publication_validation_receipt.json",
    "repair_validation_results.csv",
    "scalability_audit.csv",
    "semantic_audit_receipt.json",
    "stratified_audit.csv",
    "validation_run_manifest.json",
}
REQUIRED_PUBLICATION_CHECKS = {
    "COVERAGE",
    "GOLDEN",
    "LEGACY_INVARIANT_MIGRATION",
    "PROJECTION_EXACT_SET",
    "REPAIR_VALIDATION",
    "SCALABILITY_AUDIT",
    "SEMANTIC_AUDIT",
    "STRATIFIED_AUDIT",
}
REQUIREMENT_HASH_FIELDS = {
    "baseline_sha256",
    "decision_register_sha256",
    "fsd_sha256",
    "issue_body_sha256",
    "legacy_path_inventory_sha256",
}
RUN_BINDING_FIELDS = {
    "audit_manifest_hash",
    "derived_asset_ids",
    "migrated_metric_ids",
    "observation_ids",
    "release_id",
    "release_plan_sha256",
    "result_ids",
    "review_unit_hashes",
    "run_id",
    "trace_ids",
    "validation_receipt_id",
}
RUN_VALIDATION_VIEW_BINDING_FIELDS = RUN_BINDING_FIELDS - {
    "validation_receipt_id"
}
LEDGER_BINDING_FIELDS = {
    "requests_log_manifest_sha256",
    "row_count",
    "source_reference_ids",
    "used_request_attempt_ids",
}
POINTER_FIELDS = {
    "bundle_manifest_sha256",
    "committed_at_utc",
    "previous_publication_id",
    "publication_id",
}
PUBLICATION_ID_PATTERN = re.compile(r"^publication_[0-9a-f]{64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CONTENT_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
LATEST_STATUS_FILENAME = "latest_run_status.json"
PROJECTION_MANIFEST_FIELDS = {
    "candidate_artifact_hashes",
    "derived_asset_ids",
    "gate_receipt_hashes",
    "legacy_input_hashes",
    "migrated_metric_ids",
    "observation_ids",
    "projection_manifest_id",
    "publication_candidate_status",
    "release_id",
    "release_plan_sha256",
    "requirement_hashes",
    "result_ids",
    "review_unit_hashes",
    "run_audit_manifest_hash",
    "run_content_manifest_hash",
    "run_id",
    "schema_version",
    "trace_ids",
}


class PublicationError(RuntimeError):
    """Report incomplete bundles, CAS loss, tamper, or commit failure."""


def publication_layout(*, publication_root: Path) -> Dict[str, object]:
    """Derive every mutable and immutable publication path from one root.

    Args:
        publication_root: Root containing bundles, authorities, and legacy
            compatibility mirrors.

    Returns:
        Publications directory, pointer, status, and exact mirror mapping.

    Raises:
        PublicationError: When an existing root is not a real directory.
    """
    if publication_root.is_symlink() or (
        publication_root.exists() and not publication_root.is_dir()
    ):
        raise PublicationError("Publication root must be a real directory")
    publications_dir = publication_root / "publications"
    if publications_dir.is_symlink() or (
        publications_dir.exists() and not publications_dir.is_dir()
    ):
        raise PublicationError("Publication storage must be a real directory")
    pointer_path = publication_root / "active_publication.json"
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    latest_status_path = publication_root / LATEST_STATUS_FILENAME
    for path, label in (
        (pointer_path, "Active pointer"),
        (lock_path, "Publication lock"),
        (latest_status_path, "Latest status"),
    ):
        if path.is_symlink():
            raise PublicationError("{} must not be a symlink".format(label))
    layout = {
        "publications_dir": publications_dir,
        "pointer_path": pointer_path,
        "latest_status_path": latest_status_path,
        "mirror_paths": {
            relative: publication_root / relative
            for relative in REQUIRED_BUNDLE_FILES
        },
    }
    _validate_mirror_paths(
        publications_dir=layout["publications_dir"],
        pointer_path=layout["pointer_path"],
        latest_status_path=layout["latest_status_path"],
        mirror_paths=layout["mirror_paths"],
    )
    return layout


def _validate_id_list(
    *, values: object, label: str, content_ids: bool
) -> None:
    """Require one ordered unique identifier array.

    Args:
        values: Candidate JSON array.
        label: Diagnostic field name.
        content_ids: Whether members use the ``sha256:`` prefix.

    Raises:
        PublicationError: On wrong shape, duplicate, or invalid identity.
    """
    pattern = CONTENT_ID_PATTERN if content_ids else None
    if type(values) is not list:
        raise PublicationError("{} must be a unique array".format(label))
    if any(
        type(value) is not str
        or not value
        or (pattern is not None and pattern.fullmatch(value) is None)
        for value in values
    ):
        raise PublicationError("{} identity is invalid".format(label))
    if len(values) != len(set(values)):
        raise PublicationError("{} must be a unique array".format(label))


def _validate_publication_bindings(
    *,
    requirement_hashes: Mapping[str, object],
    run_content_hash: object,
    run_bindings: Mapping[str, object],
    ledger_binding: Mapping[str, object],
    previous_publication_id: object,
) -> None:
    """Validate nested publication provenance before hashing or reading.

    Args:
        requirement_hashes: Exact Requirement digest mapping.
        run_content_hash: FROZEN Run content identity.
        run_bindings: Run/review/trace/validation identities.
        ledger_binding: Used request-ledger prefix identities.
        previous_publication_id: Optional prepared predecessor.

    Raises:
        PublicationError: On any ambiguous nested shape or identifier.
    """
    if type(requirement_hashes) is not dict or set(
        requirement_hashes
    ) != REQUIREMENT_HASH_FIELDS or any(
        type(requirement_hashes[field]) is not str
        or SHA256_PATTERN.fullmatch(requirement_hashes[field]) is None
        for field in requirement_hashes
    ):
        raise PublicationError("Requirement hash fields/values are invalid")
    if (
        type(run_content_hash) is not str
        or CONTENT_ID_PATTERN.fullmatch(run_content_hash) is None
    ):
        raise PublicationError("Run content hash is invalid")
    if type(run_bindings) is not dict or set(
        run_bindings
    ) != RUN_BINDING_FIELDS:
        raise PublicationError("Run binding fields are not exact")
    for field in ("audit_manifest_hash", "validation_receipt_id"):
        if (
            type(run_bindings[field]) is not str
            or CONTENT_ID_PATTERN.fullmatch(run_bindings[field]) is None
        ):
            raise PublicationError("Run binding digest is invalid")
    if type(run_bindings["run_id"]) is not str or not run_bindings["run_id"]:
        raise PublicationError("Run identity is invalid")
    for field in (
        "derived_asset_ids",
        "observation_ids",
        "result_ids",
        "review_unit_hashes",
        "trace_ids",
    ):
        _validate_id_list(
            values=run_bindings[field], label=field, content_ids=True,
        )
    migrated = run_bindings["migrated_metric_ids"]
    if (
        type(migrated) is not list
        or not migrated
        or any(type(value) is not str or not value for value in migrated)
        or len(migrated) != len(set(migrated))
        or type(run_bindings["release_id"]) is not str
        or not run_bindings["release_id"]
        or type(run_bindings["release_plan_sha256"]) is not str
        or SHA256_PATTERN.fullmatch(
            run_bindings["release_plan_sha256"]
        ) is None
    ):
        raise PublicationError("Release/metric Run bindings are invalid")
    if type(ledger_binding) is not dict or set(
        ledger_binding
    ) != LEDGER_BINDING_FIELDS:
        raise PublicationError("Ledger binding fields are not exact")
    if (
        type(ledger_binding["requests_log_manifest_sha256"]) is not str
        or SHA256_PATTERN.fullmatch(
            ledger_binding["requests_log_manifest_sha256"]
        ) is None
        or type(ledger_binding["row_count"]) is not int
        or ledger_binding["row_count"] < 0
    ):
        raise PublicationError("Ledger digest/row count is invalid")
    _validate_id_list(
        values=ledger_binding["source_reference_ids"],
        label="ledger source_reference_ids",
        content_ids=True,
    )
    _validate_id_list(
        values=ledger_binding["used_request_attempt_ids"],
        label="ledger used_request_attempt_ids",
        content_ids=False,
    )
    if previous_publication_id is not None and (
        type(previous_publication_id) is not str
        or PUBLICATION_ID_PATTERN.fullmatch(previous_publication_id) is None
    ):
        raise PublicationError("Publication predecessor is invalid")


def publication_staging_context(
    *,
    repo_root: Path,
    run_dir: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
) -> Dict[str, object]:
    """Derive publication identities through the Projector's single gate.

    Args:
        repo_root: Repository containing Requirement and release-plan bytes.
        run_dir: Persisted Run reloaded through the full freeze verifier.
        legacy_snapshot_dir: Legacy inputs used by the projection.
        staging_dir: Candidate and gate artifacts used by the projection.

    Returns:
        Expected ProjectionManifest plus receipt-independent bindings.

    Raises:
        PublicationError: When the Projector cannot form a publishable view.
    """
    try:
        projection = build_projection_manifest(
            repo_root=repo_root,
            run_dir=run_dir,
            legacy_snapshot_dir=legacy_snapshot_dir,
            staging_dir=staging_dir,
        )
    except ValueError as error:
        raise PublicationError(
            "Publication requires a verified projection context"
        ) from error
    if projection["publication_candidate_status"] != "PUBLISHABLE":
        raise PublicationError("FROZEN Run results are not publishable")
    run_bindings = {
        "audit_manifest_hash": projection["run_audit_manifest_hash"],
        "derived_asset_ids": projection["derived_asset_ids"],
        "migrated_metric_ids": projection["migrated_metric_ids"],
        "observation_ids": projection["observation_ids"],
        "release_id": projection["release_id"],
        "release_plan_sha256": projection["release_plan_sha256"],
        "result_ids": projection["result_ids"],
        "review_unit_hashes": projection["review_unit_hashes"],
        "run_id": projection["run_id"],
        "trace_ids": projection["trace_ids"],
    }
    return {
        "projection_manifest": projection,
        "requirement_hashes": dict(projection["requirement_hashes"]),
        "run_bindings": run_bindings,
        "run_content_hash": projection["run_content_manifest_hash"],
    }


def _read_staging_files(*, staging_dir: Path) -> Dict[str, bytes]:
    """Read one exact regular-file staging candidate.

    Args:
        staging_dir: Dedicated candidate directory.

    Returns:
        Required bundle-relative paths to exact bytes.

    Raises:
        PublicationError: On a missing, extra, aliased, or unsafe entry.
    """
    if staging_dir.is_symlink() or not staging_dir.is_dir():
        raise PublicationError("Publication staging root is unsafe or missing")
    actual_files = set()
    actual_directories = set()
    for path in staging_dir.rglob("*"):
        relative = path.relative_to(staging_dir).as_posix()
        if path.is_symlink():
            raise PublicationError("Publication staging contains a symlink")
        if path.is_file():
            actual_files.add(relative)
        elif path.is_dir():
            actual_directories.add(relative)
        else:
            raise PublicationError("Publication staging entry is unsafe")
    if actual_files != REQUIRED_BUNDLE_FILES or actual_directories:
        raise PublicationError("Publication staging exact set differs")
    return {
        relative: (staging_dir / relative).read_bytes()
        for relative in sorted(REQUIRED_BUNDLE_FILES)
    }


def publication_validation_view_id(
    *,
    files: Mapping[str, bytes],
    requirement_hashes: Mapping[str, object],
    run_content_hash: str,
    run_bindings: Mapping[str, object],
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> str:
    """Hash the exact non-self-referential staging candidate view.

    Args:
        files: Required bundle bytes before or after adding the receipt.
        requirement_hashes: Exact Requirement Snapshot identities.
        run_content_hash: FROZEN Run content identity.
        run_bindings: Run identities, optionally including the receipt ID.
        ledger_binding: Exact request-ledger prefix used by the candidate.
        previous_publication_id: Prepared predecessor identity.

    Returns:
        Content-addressed staging view stable after adding its own receipt.

    Raises:
        PublicationError: On incomplete artifacts or malformed metadata.
    """
    expected_paths = REQUIRED_BUNDLE_FILES - {
        "publication_validation_receipt.json"
    }
    allowed_paths = expected_paths | {
        "publication_validation_receipt.json"
    }
    if frozenset(files) not in {
        frozenset(expected_paths),
        frozenset(allowed_paths),
    }:
        raise PublicationError("Publication validation view files differ")
    if any(
        not isinstance(files[relative], bytes)
        for relative in expected_paths
    ):
        raise PublicationError("Publication validation view requires bytes")
    if frozenset(run_bindings) not in {
        frozenset(RUN_VALIDATION_VIEW_BINDING_FIELDS),
        frozenset(RUN_BINDING_FIELDS),
    }:
        raise PublicationError("Run validation-view bindings are not exact")
    view_run_bindings = {
        field: run_bindings[field]
        for field in sorted(RUN_VALIDATION_VIEW_BINDING_FIELDS)
    }
    complete_run_bindings = dict(view_run_bindings)
    complete_run_bindings["validation_receipt_id"] = (
        run_bindings["validation_receipt_id"]
        if "validation_receipt_id" in run_bindings
        else "sha256:" + "0" * 64
    )
    _validate_publication_bindings(
        requirement_hashes=requirement_hashes,
        run_content_hash=run_content_hash,
        run_bindings=complete_run_bindings,
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )
    artifacts = {
        relative: {
            "sha256": sha256_bytes(content=files[relative]),
            "size": len(files[relative]),
        }
        for relative in sorted(expected_paths)
    }
    return "staging:" + content_hash(
        value={
            "artifact_hashes": artifacts,
            "ledger_binding": dict(ledger_binding),
            "previous_publication_id": previous_publication_id,
            "requirement_hashes": dict(requirement_hashes),
            "run_bindings": view_run_bindings,
            "run_content_hash": run_content_hash,
        }
    )


def _safe_relative(*, value: str) -> Path:
    """Return a normalized bundle-relative path.

    Args:
        value: Relative artifact path.

    Returns:
        Safe Path.

    Raises:
        PublicationError: On absolute, parent traversal, or empty path.
    """
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value in {"", "."}:
        raise PublicationError("Publication path is unsafe: {}".format(value))
    if path.as_posix() != value:
        raise PublicationError("Publication path is not normalized")
    return path


def _fsync_directory(*, path: Path) -> None:
    """Fsync a directory after namespace changes.

    Args:
        path: Existing directory.
    """
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_receipt_artifacts(
    *,
    files: Mapping[str, bytes],
    receipt: Mapping[str, object],
    requirement_hashes: Mapping[str, object],
    run_content_hash: str,
    run_bindings: Mapping[str, object],
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> None:
    """Bind a staging receipt to the exact non-self-referential bundle bytes.

    Args:
        files: Complete required bundle bytes including the receipt.
        receipt: Strict PASSED ValidationReceipt.
        requirement_hashes: Exact Requirement Snapshot identities.
        run_content_hash: FROZEN Run identity named by the staging view.
        run_bindings: Run/review/trace identities.
        ledger_binding: Exact request-ledger prefix identities.
        previous_publication_id: Prepared predecessor identity.

    Raises:
        PublicationError: On gate-set, view, path, digest, or size mismatch.
    """
    checks = receipt["checks"]
    check_names = [str(check["check"]) for check in checks]
    if (
        set(check_names) != REQUIRED_PUBLICATION_CHECKS
        or len(check_names) != len(set(check_names))
        or any(check["status"] != "PASS" for check in checks)
    ):
        raise PublicationError("Publication required gate set did not PASS")
    expected_view = publication_validation_view_id(
        files=files,
        requirement_hashes=requirement_hashes,
        run_content_hash=run_content_hash,
        run_bindings=run_bindings,
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )
    if receipt["view_id"] != expected_view:
        raise PublicationError("Publication receipt candidate view differs")
    expected_paths = REQUIRED_BUNDLE_FILES - {
        "publication_validation_receipt.json"
    }
    bindings = receipt["artifact_hashes"]
    if set(bindings) != expected_paths:
        raise PublicationError(
            "Publication receipt artifact exact set differs"
        )
    for relative in sorted(expected_paths):
        binding = bindings[relative]
        if not isinstance(binding, dict) or set(binding) != {"sha256", "size"}:
            raise PublicationError("Publication receipt artifact is malformed")
        content = files[relative]
        if (
            binding["sha256"] != sha256_bytes(content=content)
            or binding["size"] != len(content)
        ):
            raise PublicationError("Publication receipt artifact bytes differ")


def _validate_projection_manifest(
    *,
    content: bytes,
    requirement_hashes: Mapping[str, object],
    run_content_hash: str,
    run_bindings: Mapping[str, object],
) -> Dict[str, object]:
    """Validate the bundled ProjectionManifest as candidate authority.

    Args:
        content: Exact bundled ``projection_manifest.json`` bytes.
        requirement_hashes: Publication Requirement binding.
        run_content_hash: Publication Run content identity.
        run_bindings: Publication Run/review/trace/validation identities.

    Returns:
        Strict isolated ProjectionManifest.

    Raises:
        PublicationError: On malformed fields, identity drift, self-hash
            mismatch, or a BLOCKED candidate.
    """
    try:
        parsed = strict_json_loads(text=content.decode("utf-8"))
    except (UnicodeDecodeError, CanonicalError) as error:
        raise PublicationError(
            "Bundled ProjectionManifest is invalid"
        ) from error
    if (
        not isinstance(parsed, dict)
        or set(parsed) != PROJECTION_MANIFEST_FIELDS
    ):
        raise PublicationError("Bundled ProjectionManifest fields differ")
    manifest = dict(parsed)
    if (
        type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != 1
    ):
        raise PublicationError("Bundled ProjectionManifest version differs")
    for field in (
        "derived_asset_ids",
        "observation_ids",
        "result_ids",
        "review_unit_hashes",
        "trace_ids",
    ):
        _validate_id_list(
            values=manifest[field], label="Projection " + field,
            content_ids=True,
        )
    migrated = manifest["migrated_metric_ids"]
    if (
        type(migrated) is not list
        or not migrated
        or any(
            type(metric_id) is not str or not metric_id
            for metric_id in migrated
        )
        or len(migrated) != len(set(migrated))
    ):
        raise PublicationError("Projection migrated metrics are invalid")
    if not manifest["result_ids"]:
        raise PublicationError("Projection result set is empty")
    expected_hash_paths = {
        "candidate_artifact_hashes": set(PROJECTION_CANDIDATE_FILES),
        "gate_receipt_hashes": set(PROJECTION_GATE_FILES),
        "legacy_input_hashes": set(LEGACY_INPUT_FILES),
    }
    for field in expected_hash_paths:
        values = manifest[field]
        if (
            type(values) is not dict
            or set(values) != expected_hash_paths[field]
            or any(
                type(key) is not str
                or not key
                or type(values[key]) is not str
                or SHA256_PATTERN.fullmatch(values[key]) is None
                for key in values
            )
        ):
            raise PublicationError("Projection hash mapping is invalid")
    if (
        type(manifest["release_id"]) is not str
        or not manifest["release_id"]
        or type(manifest["release_plan_sha256"]) is not str
        or SHA256_PATTERN.fullmatch(manifest["release_plan_sha256"]) is None
        or type(manifest["run_id"]) is not str
        or not manifest["run_id"]
    ):
        raise PublicationError("Projection release/Run identity is invalid")
    for field in (
        "projection_manifest_id",
        "run_audit_manifest_hash",
        "run_content_manifest_hash",
    ):
        if (
            type(manifest[field]) is not str
            or CONTENT_ID_PATTERN.fullmatch(manifest[field]) is None
        ):
            raise PublicationError("Projection content identity is invalid")
    body = {
        key: manifest[key]
        for key in manifest
        if key not in {"projection_manifest_id", "schema_version"}
    }
    if manifest["projection_manifest_id"] != content_hash(value=body):
        raise PublicationError("ProjectionManifest identity differs")
    expected = {
        "derived_asset_ids": run_bindings["derived_asset_ids"],
        "migrated_metric_ids": run_bindings["migrated_metric_ids"],
        "observation_ids": run_bindings["observation_ids"],
        "release_id": run_bindings["release_id"],
        "release_plan_sha256": run_bindings["release_plan_sha256"],
        "result_ids": run_bindings["result_ids"],
        "review_unit_hashes": run_bindings["review_unit_hashes"],
        "run_audit_manifest_hash": run_bindings["audit_manifest_hash"],
        "run_content_manifest_hash": run_content_hash,
        "run_id": run_bindings["run_id"],
        "trace_ids": run_bindings["trace_ids"],
    }
    if any(manifest[field] != expected[field] for field in expected):
        raise PublicationError("ProjectionManifest Run binding differs")
    if manifest["requirement_hashes"] != dict(requirement_hashes):
        raise PublicationError("ProjectionManifest Requirement differs")
    if manifest["publication_candidate_status"] != "PUBLISHABLE":
        raise PublicationError("BLOCKED ProjectionManifest cannot publish")
    return manifest


def _validate_projection_artifact_bindings(
    *,
    projection: Mapping[str, object],
    files: Mapping[str, bytes],
    legacy_snapshot_dir: Optional[Path],
) -> None:
    """Bind ProjectionManifest hashes to actual legacy/staging bytes.

    Args:
        projection: Strict bundled ProjectionManifest.
        files: Exact candidate bundle bytes.
        legacy_snapshot_dir: Legacy input locator during preparation, or
            ``None`` while verifying an already immutable bundle.

    Raises:
        PublicationError: When any candidate, gate, or available legacy input
            digest differs from the ProjectionManifest.
    """
    candidate_hashes = {
        relative: sha256_bytes(content=files[relative])
        for relative in PROJECTION_CANDIDATE_FILES
    }
    gate_hashes = {
        relative: sha256_bytes(content=files[relative])
        for relative in PROJECTION_GATE_FILES
    }
    if projection["candidate_artifact_hashes"] != candidate_hashes:
        raise PublicationError("Projection candidate artifact bytes differ")
    if projection["gate_receipt_hashes"] != gate_hashes:
        raise PublicationError("Projection gate receipt bytes differ")
    if legacy_snapshot_dir is not None:
        try:
            legacy_hashes = projection_file_hashes(
                root=legacy_snapshot_dir,
                relative_paths=LEGACY_INPUT_FILES,
                label="Legacy input",
            )
        except ValueError as error:
            raise PublicationError(
                "Projection legacy input cannot be verified"
            ) from error
        if projection["legacy_input_hashes"] != legacy_hashes:
            raise PublicationError("Projection legacy input bytes differ")


def prepare_publication_bundle(
    *,
    publication_root: Path,
    repo_root: Path,
    run_dir: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Create and verify one immutable complete PUBLISHABLE bundle.

    Args:
        publication_root: Single root from which bundle storage is derived.
        repo_root: Repository containing Requirement and release authority.
        run_dir: Persisted FROZEN Run locator.
        legacy_snapshot_dir: Legacy inputs named by ProjectionManifest.
        staging_dir: Exact candidate artifact directory.
        ledger_binding: Exact used request-ledger prefix/source bindings.
        previous_publication_id: Active predecessor at preparation time.

    Returns:
        Strict PublicationManifest.

    Raises:
        PublicationError: On incomplete set, unsafe paths, existing divergent
            bundle, or write/hash failure.
    """
    layout = publication_layout(publication_root=publication_root)
    publications_dir = layout["publications_dir"]
    files = _read_staging_files(staging_dir=staging_dir)
    try:
        receipt_file = strict_json_loads(
            text=files["publication_validation_receipt.json"].decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise PublicationError(
            "Bundled validation receipt is invalid"
        ) from error
    try:
        validated_receipt = validate_record(record=receipt_file)
    except ValueError as error:
        raise PublicationError(
            "Publication staging validation receipt is invalid"
        ) from error
    if (
        validated_receipt["record_type"] != "VALIDATION_RECEIPT"
        or validated_receipt["status"] not in PUBLISHABLE_VALIDATION_STATUSES
    ):
        raise PublicationError("Publication staging validation is not PASSED")
    context = publication_staging_context(
        repo_root=repo_root,
        run_dir=run_dir,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
    )
    requirement_hashes = context["requirement_hashes"]
    run_content_hash = context["run_content_hash"]
    run_bindings = dict(context["run_bindings"])
    run_bindings["validation_receipt_id"] = validated_receipt[
        "validation_receipt_id"
    ]
    _validate_publication_bindings(
        requirement_hashes=requirement_hashes,
        run_content_hash=run_content_hash,
        run_bindings=run_bindings,
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )
    projection = _validate_projection_manifest(
        content=files["projection_manifest.json"],
        requirement_hashes=requirement_hashes,
        run_content_hash=run_content_hash,
        run_bindings=run_bindings,
    )
    if projection != context["projection_manifest"]:
        raise PublicationError(
            "ProjectionManifest differs from verified projection"
        )
    _validate_projection_artifact_bindings(
        projection=projection,
        files=files,
        legacy_snapshot_dir=legacy_snapshot_dir,
    )
    _validate_receipt_artifacts(
        files=files,
        receipt=validated_receipt,
        requirement_hashes=requirement_hashes,
        run_content_hash=run_content_hash,
        run_bindings=run_bindings,
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )
    file_records = []
    for relative in sorted(files):
        _safe_relative(value=relative)
        content = files[relative]
        if not isinstance(content, bytes):
            raise PublicationError("Publication file content must be bytes")
        file_records.append(
            {
                "path": relative,
                "sha256": sha256_bytes(content=content),
                "size": len(content),
            }
        )
    manifest_identity = {
        "candidate_status": "PUBLISHABLE",
        "requirement_hashes": dict(requirement_hashes),
        "run_content_hash": run_content_hash,
        "run_bindings": dict(run_bindings),
        "files": file_records,
        "ledger_binding": dict(ledger_binding),
        "previous_publication_id": previous_publication_id,
    }
    publication_id = (
        "publication_" + content_hash(value=manifest_identity).split(":", 1)[1]
    )
    manifest = {
        "record_type": "PUBLICATION_MANIFEST",
        "publication_id": publication_id,
        "candidate_status": "PUBLISHABLE",
        "requirement_hashes": dict(requirement_hashes),
        "run_content_hash": run_content_hash,
        "run_bindings": dict(run_bindings),
        "files": file_records,
        "ledger_binding": dict(ledger_binding),
        "previous_publication_id": previous_publication_id,
    }
    validate_record(record=manifest)
    publications_dir.mkdir(parents=True, exist_ok=True)
    final_dir = publications_dir / publication_id
    if final_dir.exists():
        existing = verify_publication_bundle(bundle_dir=final_dir)
        if existing != manifest:
            raise PublicationError(
                "Existing publication ID has divergent bytes"
            )
        return manifest
    temporary = publications_dir / ".{}.{}.tmp".format(
        publication_id, uuid.uuid4().hex
    )
    temporary.mkdir()
    try:
        for relative in sorted(files):
            destination = temporary / _safe_relative(value=relative)
            atomic_write_bytes(path=destination, content=files[relative])
        atomic_write_json(
            path=temporary / "publication_manifest.json", value=manifest,
        )
        verify_publication_bundle(bundle_dir=temporary)
        os.replace(str(temporary), str(final_dir))
        _fsync_directory(path=publications_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    verify_publication_bundle(bundle_dir=final_dir)
    return manifest


def verify_publication_bundle(*, bundle_dir: Path) -> Dict[str, object]:
    """Verify manifest identity and exact artifact bytes for one bundle.

    Args:
        bundle_dir: Immutable bundle directory.

    Returns:
        Strict PublicationManifest.

    Raises:
        PublicationError: On unsafe namespace, missing/extra file, digest/size
            mismatch, or publication ID mismatch.
    """
    if bundle_dir.is_symlink() or not bundle_dir.is_dir():
        raise PublicationError("Publication bundle must be a real directory")
    manifest_path = bundle_dir / "publication_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PublicationError("Publication manifest must be a real file")
    try:
        parsed = strict_json_file(path=manifest_path)
        if not isinstance(parsed, dict):
            raise PublicationError(
                "Publication manifest root must be object"
            )
        manifest = validate_record(record=parsed)
    except (CanonicalError, ValueError) as error:
        raise PublicationError(
            "Publication manifest record is invalid"
        ) from error
    if manifest[
        "publication_id"
    ] != bundle_dir.name and not bundle_dir.name.startswith("."):
        raise PublicationError("Publication directory identity differs")
    _validate_publication_bindings(
        requirement_hashes=manifest["requirement_hashes"],
        run_content_hash=manifest["run_content_hash"],
        run_bindings=manifest["run_bindings"],
        ledger_binding=manifest["ledger_binding"],
        previous_publication_id=manifest["previous_publication_id"],
    )
    if not isinstance(manifest["files"], list):
        raise PublicationError("Publication files must be an array")
    expected_paths = {str(record["path"]) for record in manifest["files"]}
    if len(expected_paths) != len(manifest["files"]):
        raise PublicationError("Publication file paths are duplicated")
    if expected_paths != REQUIRED_BUNDLE_FILES:
        raise PublicationError("Publication bundle file exact set differs")
    expected_files = expected_paths | {"publication_manifest.json"}
    expected_directories = {
        parent.as_posix()
        for relative in expected_files
        for parent in _safe_relative(value=relative).parents
        if parent.as_posix() != "."
    }
    actual_files = set()
    actual_directories = set()
    for path in bundle_dir.rglob("*"):
        relative = path.relative_to(bundle_dir).as_posix()
        if path.is_symlink():
            raise PublicationError("Publication namespace contains a symlink")
        if path.is_file():
            actual_files.add(relative)
        elif path.is_dir():
            actual_directories.add(relative)
        else:
            raise PublicationError("Publication namespace entry is unsafe")
    if (
        actual_files != expected_files
        or actual_directories != expected_directories
    ):
        raise PublicationError("Publication file exact set differs")
    for record in manifest["files"]:
        if not isinstance(record, dict) or set(record) != {
            "path",
            "sha256",
            "size",
        }:
            raise PublicationError(
                "Publication file record fields are not exact"
            )
        if (
            type(record["path"]) is not str
            or type(record["sha256"]) is not str
            or SHA256_PATTERN.fullmatch(record["sha256"]) is None
            or type(record["size"]) is not int
            or record["size"] < 0
        ):
            raise PublicationError("Publication file record is invalid")
        path = bundle_dir / _safe_relative(value=str(record["path"]))
        if path.is_symlink() or not path.is_file():
            raise PublicationError("Publication artifact is unsafe")
        if (
            path.stat().st_size != record["size"]
            or sha256_file(path=path) != record["sha256"]
        ):
            raise PublicationError("Publication artifact digest differs")
    projection = _validate_projection_manifest(
        content=(bundle_dir / "projection_manifest.json").read_bytes(),
        requirement_hashes=manifest["requirement_hashes"],
        run_content_hash=str(manifest["run_content_hash"]),
        run_bindings=manifest["run_bindings"],
    )
    bundle_files = {
        relative: (bundle_dir / relative).read_bytes()
        for relative in REQUIRED_BUNDLE_FILES
    }
    _validate_projection_artifact_bindings(
        projection=projection,
        files=bundle_files,
        legacy_snapshot_dir=None,
    )
    try:
        receipt_payload = strict_json_file(
            path=bundle_dir / "publication_validation_receipt.json"
        )
        if not isinstance(receipt_payload, dict):
            raise PublicationError(
                "Bundled validation receipt root is not object"
            )
        receipt = validate_record(record=receipt_payload)
    except (CanonicalError, ValueError) as error:
        raise PublicationError(
            "Bundled validation receipt record is invalid"
        ) from error
    if (
        receipt["record_type"] != "VALIDATION_RECEIPT"
        or receipt["status"] not in PUBLISHABLE_VALIDATION_STATUSES
        or receipt["validation_receipt_id"]
        != manifest["run_bindings"]["validation_receipt_id"]
    ):
        raise PublicationError("Bundled validation receipt binding differs")
    _validate_receipt_artifacts(
        files=bundle_files,
        receipt=receipt,
        requirement_hashes=manifest["requirement_hashes"],
        run_content_hash=str(manifest["run_content_hash"]),
        run_bindings=manifest["run_bindings"],
        ledger_binding=manifest["ledger_binding"],
        previous_publication_id=manifest["previous_publication_id"],
    )
    identity = {
        "candidate_status": manifest["candidate_status"],
        "requirement_hashes": manifest["requirement_hashes"],
        "run_content_hash": manifest["run_content_hash"],
        "run_bindings": manifest["run_bindings"],
        "files": manifest["files"],
        "ledger_binding": manifest["ledger_binding"],
        "previous_publication_id": manifest["previous_publication_id"],
    }
    expected_id = (
        "publication_" + content_hash(value=identity).split(":", 1)[1]
    )
    if manifest["publication_id"] != expected_id:
        raise PublicationError("Publication manifest identity differs")
    return manifest


def _read_pointer(*, pointer_path: Path) -> Optional[Dict[str, object]]:
    """Read the active pointer or return ``None`` before first publication.

    Args:
        pointer_path: Active pointer path.

    Returns:
        Exact pointer mapping or ``None``.
    """
    if pointer_path.is_symlink():
        raise PublicationError("Active pointer must be a real file")
    if not pointer_path.exists():
        return None
    if not pointer_path.is_file():
        raise PublicationError("Active pointer must be a real file")
    try:
        parsed = strict_json_file(
            path=pointer_path, allowed_fields=POINTER_FIELDS,
        )
    except CanonicalError as error:
        raise PublicationError("Active pointer JSON is invalid") from error
    if not isinstance(parsed, dict):
        raise PublicationError("Active pointer root must be object")
    if set(parsed) != POINTER_FIELDS:
        raise PublicationError("Active pointer fields are not exact")
    for key in (
        "publication_id",
        "bundle_manifest_sha256",
        "committed_at_utc",
    ):
        if not isinstance(parsed[key], str) or not parsed[key]:
            raise PublicationError("Active pointer field is empty")
    previous = parsed["previous_publication_id"]
    if previous is not None and (
        not isinstance(previous, str) or not previous
    ):
        raise PublicationError("Active pointer predecessor is invalid")
    if PUBLICATION_ID_PATTERN.fullmatch(str(parsed["publication_id"])) is None:
        raise PublicationError("Active publication identity is invalid")
    if (
        previous is not None
        and PUBLICATION_ID_PATTERN.fullmatch(previous) is None
    ):
        raise PublicationError("Active predecessor identity is invalid")
    if SHA256_PATTERN.fullmatch(str(parsed["bundle_manifest_sha256"])) is None:
        raise PublicationError("Active manifest digest is invalid")
    _validate_utc_timestamp(value=str(parsed["committed_at_utc"]))
    return dict(parsed)


def _validate_mirror_paths(
    *,
    publications_dir: Path,
    pointer_path: Path,
    latest_status_path: Path,
    mirror_paths: Mapping[str, Path],
) -> None:
    """Require distinct mirror destinations outside authority storage.

    Args:
        publications_dir: Immutable bundle parent.
        pointer_path: Unique active pointer.
        latest_status_path: Latest-run status authority path.
        mirror_paths: Required bundle-relative path to compatibility path.

    Raises:
        PublicationError: On an incomplete, aliased, or authoritative target.
    """
    if set(mirror_paths) != REQUIRED_BUNDLE_FILES:
        raise PublicationError("Compatibility mirror exact set differs")
    resolved = [path.resolve(strict=False) for path in mirror_paths.values()]
    if len(resolved) != len(set(resolved)):
        raise PublicationError("Compatibility mirrors must be distinct")
    publication_root = publications_dir.resolve(strict=False)
    pointer = pointer_path.resolve(strict=False)
    lock = pointer_path.with_suffix(
        pointer_path.suffix + ".lock"
    ).resolve(strict=False)
    latest_status = latest_status_path.resolve(strict=False)
    if pointer == publication_root or publication_root in pointer.parents:
        raise PublicationError(
            "Active pointer overlaps publication storage"
        )
    canonical_status = pointer_path.with_name(
        LATEST_STATUS_FILENAME
    ).resolve(strict=False)
    if latest_status != canonical_status:
        raise PublicationError("Latest status path is not canonical")
    if (
        latest_status in {pointer, lock, publication_root}
        or publication_root in latest_status.parents
    ):
        raise PublicationError(
            "Latest status path overlaps publication authority"
        )
    for target in resolved:
        if target in {pointer, lock}:
            raise PublicationError(
                "Compatibility mirror targets pointer authority"
            )
        if target == latest_status:
            raise PublicationError(
                "Compatibility mirror targets latest status path"
            )
        try:
            target.relative_to(publication_root)
        except ValueError:
            continue
        raise PublicationError("Compatibility mirror targets bundle storage")


def _restore_mirrors(*, snapshots: Mapping[Path, Optional[bytes]]) -> None:
    """Restore compatibility mirrors after a failed commit.

    Args:
        snapshots: Prior bytes or ``None`` for previously absent paths.
    """
    for path in snapshots:
        content = snapshots[path]
        if content is None:
            if path.exists() and path.is_file() and not path.is_symlink():
                path.unlink()
        else:
            atomic_write_bytes(path=path, content=content)


def _validate_utc_timestamp(*, value: str) -> None:
    """Require an exact timezone-aware UTC timestamp.

    Args:
        value: ISO-8601 timestamp using ``Z`` or zero offset.

    Raises:
        PublicationError: On malformed or non-UTC time.
    """
    try:
        parse_utc_timestamp(value=value)
    except CanonicalError as error:
        raise PublicationError("Publication timestamp is invalid") from error


def _switch_publication(
    *,
    publications_dir: Path,
    pointer_path: Path,
    publication_id: str,
    expected_previous_publication_id: Optional[str],
    committed_at_utc: str,
    mirror_paths: Mapping[str, Path],
    switch_mode: str,
) -> Dict[str, object]:
    """Switch the active pointer after preparing every compatibility mirror.

    Args:
        publications_dir: Bundle parent.
        pointer_path: Unique active commit point.
        publication_id: Prepared bundle to activate.
        expected_previous_publication_id: CAS predecessor.
        committed_at_utc: Explicit UTC timestamp.
        mirror_paths: Bundle-relative file to root compatibility mirror.
        switch_mode: ``COMMIT`` for a prepared successor or ``ROLLBACK`` for
            the current pointer's proven committed predecessor.

    Returns:
        New active pointer.

    Raises:
        PublicationError: On CAS loss, tamper, unsafe mirrors, or any commit
            failure. The previous pointer and mirror bytes are restored.
    """
    if switch_mode not in {"COMMIT", "ROLLBACK"}:
        raise PublicationError("Publication switch mode is invalid")
    _validate_utc_timestamp(value=committed_at_utc)
    bundle_dir = publications_dir / publication_id
    manifest = verify_publication_bundle(bundle_dir=bundle_dir)
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        previous_pointer = _read_pointer(pointer_path=pointer_path)
        current_id = (
            str(previous_pointer["publication_id"])
            if previous_pointer is not None
            else None
        )
        if current_id != expected_previous_publication_id:
            raise PublicationError("Publication CAS predecessor changed")
        if switch_mode == "COMMIT":
            if manifest["previous_publication_id"] != current_id:
                raise PublicationError("Prepared bundle predecessor differs")
        elif (
            previous_pointer is None
            or previous_pointer["previous_publication_id"] != publication_id
        ):
            raise PublicationError(
                "Rollback target is not the committed predecessor"
            )
        manifest_bytes = (
            bundle_dir / "publication_manifest.json"
        ).read_bytes()
        pointer = {
            "publication_id": publication_id,
            "bundle_manifest_sha256": sha256_bytes(content=manifest_bytes),
            "previous_publication_id": current_id,
            "committed_at_utc": committed_at_utc,
        }
        snapshots: Dict[Path, Optional[bytes]] = {}
        try:
            for relative in mirror_paths:
                source = bundle_dir / _safe_relative(value=relative)
                if not source.is_file() or source.is_symlink():
                    raise PublicationError("Mirror source is unavailable")
                target = mirror_paths[relative]
                if target.exists() and (
                    target.is_symlink() or not target.is_file()
                ):
                    raise PublicationError("Mirror target is unsafe")
                snapshots[target] = (
                    target.read_bytes() if target.exists() else None
                )
            for relative in mirror_paths:
                atomic_write_bytes(
                    path=mirror_paths[relative],
                    content=(bundle_dir / relative).read_bytes(),
                )
                if sha256_file(path=mirror_paths[relative]) != sha256_file(
                    path=bundle_dir / relative
                ):
                    raise PublicationError("Compatibility mirror hash differs")
            # The pointer is the unique official commit point; fixed-root
            # mirrors are prepared first and have no group-atomic guarantee.
            atomic_write_json(path=pointer_path, value=pointer)
            opened = PublicationView._open_paths(
                publications_dir=publications_dir, pointer_path=pointer_path,
            )
            if opened.publication_id != publication_id:
                raise PublicationError("Active pointer postcondition failed")
        except (OSError, ValueError, PublicationError) as error:
            _restore_mirrors(snapshots=snapshots)
            if previous_pointer is None:
                if (
                    pointer_path.exists()
                    and pointer_path.is_file()
                    and not pointer_path.is_symlink()
                ):
                    pointer_path.unlink()
            else:
                atomic_write_json(path=pointer_path, value=previous_pointer)
            raise PublicationError(
                "Publication commit aborted and rolled back"
            ) from error
        return pointer


def commit_publication(
    *,
    publication_root: Path,
    publication_id: str,
    expected_active_publication_id: Optional[str],
    committed_at_utc: str,
) -> Dict[str, object]:
    """Commit a forward-prepared bundle with lock and CAS.

    Args:
        publication_root: Root for bundles, pointer, status, and mirrors.
        publication_id: Prepared successor bundle.
        expected_active_publication_id: CAS predecessor.
        committed_at_utc: Explicit UTC timestamp.

    Returns:
        New active pointer.
    """
    layout = publication_layout(publication_root=publication_root)
    return _switch_publication(
        publications_dir=layout["publications_dir"],
        pointer_path=layout["pointer_path"],
        publication_id=publication_id,
        expected_previous_publication_id=expected_active_publication_id,
        committed_at_utc=committed_at_utc,
        mirror_paths=layout["mirror_paths"],
        switch_mode="COMMIT",
    )


def rollback_publication(
    *,
    publication_root: Path,
    target_publication_id: str,
    expected_active_publication_id: str,
    committed_at_utc: str,
) -> Dict[str, object]:
    """Atomically reactivate a verified prior bundle without old parsers.

    Args:
        publication_root: Root for bundles, pointer, status, and mirrors.
        target_publication_id: Previously committed bundle to reactivate.
        expected_active_publication_id: CAS identity currently active.
        committed_at_utc: Explicit rollback UTC timestamp.

    Returns:
        Pointer naming the prior bundle and the version rolled back from.
    """
    layout = publication_layout(publication_root=publication_root)
    return _switch_publication(
        publications_dir=layout["publications_dir"],
        pointer_path=layout["pointer_path"],
        publication_id=target_publication_id,
        expected_previous_publication_id=expected_active_publication_id,
        committed_at_utc=committed_at_utc,
        mirror_paths=layout["mirror_paths"],
        switch_mode="ROLLBACK",
    )


def recover_publication_mirrors(
    *,
    publication_root: Path,
) -> str:
    """Repair fixed-root mirrors from the single verified active pointer.

    Args:
        publication_root: Root for bundles, pointer, status, and mirrors.

    Returns:
        Active publication ID used for recovery.
    """
    layout = publication_layout(publication_root=publication_root)
    publications_dir = layout["publications_dir"]
    pointer_path = layout["pointer_path"]
    mirror_paths = layout["mirror_paths"]
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        view = PublicationView._open_paths(
            publications_dir=publications_dir, pointer_path=pointer_path,
        )
        for relative in mirror_paths:
            atomic_write_bytes(
                path=mirror_paths[relative],
                content=view.read_bytes(relative_path=relative),
            )
        return view.publication_id


@dataclass(frozen=True)
class PublicationView:
    """Pin one verified publication ID for the lifetime of a consumer."""

    publication_id: str
    bundle_dir: Path
    manifest: Mapping[str, object]

    @classmethod
    def open(
        cls, *, publication_root: Path
    ) -> "PublicationView":
        """Resolve one root-derived active pointer and verify its bundle.

        Args:
            publication_root: Single publication layout root.

        Returns:
            Pinned view unaffected by later pointer switches.

        Raises:
            PublicationError: On missing/tampered pointer or bundle.
        """
        layout = publication_layout(publication_root=publication_root)
        return cls._open_paths(
            publications_dir=layout["publications_dir"],
            pointer_path=layout["pointer_path"],
        )

    @classmethod
    def _open_paths(
        cls, *, publications_dir: Path, pointer_path: Path
    ) -> "PublicationView":
        """Open an already-derived layout for internal lock-held callers.

        Args:
            publications_dir: Root-derived immutable bundle parent.
            pointer_path: Root-derived active pointer.

        Returns:
            Verified pinned view.
        """
        pointer = _read_pointer(pointer_path=pointer_path)
        if pointer is None:
            raise PublicationError("Active publication pointer is missing")
        publication_id = str(pointer["publication_id"])
        bundle_dir = publications_dir / publication_id
        manifest = verify_publication_bundle(bundle_dir=bundle_dir)
        manifest_hash = sha256_file(
            path=bundle_dir / "publication_manifest.json"
        )
        if manifest_hash != pointer["bundle_manifest_sha256"]:
            raise PublicationError("Active pointer manifest hash differs")
        return cls(
            publication_id=publication_id,
            bundle_dir=bundle_dir,
            manifest=manifest,
        )

    def read_bytes(self, *, relative_path: str) -> bytes:
        """Read one file only from the pinned bundle.

        Args:
            relative_path: Manifest-listed artifact path.

        Returns:
            Exact verified bytes.

        Raises:
            PublicationError: When the path was not part of this publication.
        """
        listed = {str(record["path"]) for record in self.manifest["files"]}
        if relative_path not in listed:
            raise PublicationError("PublicationView path is not in manifest")
        path = self.bundle_dir / _safe_relative(value=relative_path)
        content = path.read_bytes()
        records = [
            record
            for record in self.manifest["files"]
            if record["path"] == relative_path
        ]
        if len(records) != 1:
            raise PublicationError("PublicationView file binding is ambiguous")
        if (
            len(content) != records[0]["size"]
            or sha256_bytes(content=content) != records[0]["sha256"]
        ):
            raise PublicationError("Pinned publication artifact changed")
        return content


def write_latest_run_status(
    *,
    publication_root: Path,
    repo_root: Path,
    latest_run_dir: Optional[Path],
    latest_publication_id: Optional[str],
    message: str,
    updated_at_utc: str,
) -> Dict[str, object]:
    """Publish latest attempt state separately from the active publication.

    Args:
        publication_root: Root for bundles, pointer, status, and mirrors.
        repo_root: Repository used to replay a latest persisted Run.
        latest_run_dir: Latest Run locator, or ``None`` when a prepared
            publication is the latest authority.
        latest_publication_id: Prepared publication locator, or ``None`` when
            the latest Run has no prepared publication.
        message: Non-empty user-facing explanation.
        updated_at_utc: Explicit UTC status publication time.
    Returns:
        Derived status mapping written to the root-derived status path.
    """
    if (latest_run_dir is None) == (latest_publication_id is None):
        raise PublicationError(
            "Latest status requires exactly one persisted authority"
        )
    layout = publication_layout(publication_root=publication_root)
    path = layout["latest_status_path"]
    publications_dir = layout["publications_dir"]
    pointer_path = layout["pointer_path"]
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    if not isinstance(message, str) or not message:
        raise PublicationError("Latest Run user message is required")
    _validate_utc_timestamp(value=updated_at_utc)
    if latest_publication_id is not None and (
        type(latest_publication_id) is not str
        or PUBLICATION_ID_PATTERN.fullmatch(latest_publication_id) is None
    ):
        raise PublicationError("Latest publication identity is invalid")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        latest_manifest = None
        if latest_run_dir is not None:
            try:
                latest_run, latest_records, _decisions = load_run_for_status(
                    run_dir=latest_run_dir, repo_root=repo_root,
                )
            except RunStoreError as error:
                raise PublicationError(
                    "Latest Run cannot be verified"
                ) from error
            latest_run_id = str(latest_run["run_id"])
            latest_run_status = str(latest_run["status"])
            results = [
                record
                for record in latest_records
                if record["record_type"] == "METRIC_RESULT"
            ]
            result_status = (
                publication_candidate_status(results=results)
                if latest_run_status == "FROZEN" and results
                else "NOT_EVALUATED"
            )
            candidate_status = (
                "BLOCKED" if result_status == "BLOCKED"
                else "NOT_EVALUATED"
            )
            expected_latest_id = None
        else:
            latest_manifest = verify_publication_bundle(
                bundle_dir=publications_dir / str(latest_publication_id),
            )
            latest_run_id = str(latest_manifest["run_bindings"]["run_id"])
            latest_run_status = "FROZEN"
            candidate_status = "PUBLISHABLE"
            expected_latest_id = latest_manifest["publication_id"]
        pointer = _read_pointer(pointer_path=pointer_path)
        if pointer is None:
            expected_active_id = None
            active_manifest = None
        else:
            active_view = PublicationView._open_paths(
                publications_dir=publications_dir,
                pointer_path=pointer_path,
            )
            expected_active_id = active_view.publication_id
            active_manifest = active_view.manifest
        if (
            active_manifest is not None
            and active_manifest["run_bindings"]["run_id"] == latest_run_id
        ):
            if latest_run_status != "FROZEN":
                raise PublicationError(
                    "Active Run identity conflicts with latest Run state"
                )
            if latest_run_dir is not None:
                if result_status != "PUBLISHABLE":
                    raise PublicationError(
                        "Active Run identity conflicts with latest Run state"
                    )
                if (
                    active_manifest["run_content_hash"]
                    != latest_run["content_manifest_hash"]
                    or active_manifest["run_bindings"][
                        "audit_manifest_hash"
                    ] != latest_run["audit_manifest_hash"]
                ):
                    raise PublicationError(
                        "Active and latest Run content identities differ"
                    )
                candidate_status = "PUBLISHABLE"
                expected_latest_id = expected_active_id
        expected_latest_success = (
            latest_run_status == "FROZEN"
            and candidate_status == "PUBLISHABLE"
            and expected_latest_id is not None
            and expected_latest_id == expected_active_id
        )
        status = {
            "active_is_latest_success": expected_latest_success,
            "active_publication_id": expected_active_id,
            "latest_publication_id": expected_latest_id,
            "latest_run_id": latest_run_id,
            "latest_run_status": latest_run_status,
            "message": message,
            "publication_candidate_status": candidate_status,
            "updated_at_utc": updated_at_utc,
        }
        atomic_write_json(path=path, value=status)
        return status
