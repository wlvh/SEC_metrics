"""Publish immutable complete bundles through one atomic active pointer."""

from __future__ import annotations

import csv
import fcntl
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

from .canonical import CanonicalError, atomic_write_bytes, atomic_write_json
from .canonical import canonical_json_bytes, content_hash, parse_utc_timestamp
from .canonical import sha256_bytes, sha256_file, strict_json_file
from .canonical import strict_json_loads
from .projector import LEGACY_INPUT_FILES, PROJECTION_CANDIDATE_FILES
from .projector import PROJECTION_GATE_FILES, PROJECTION_MANIFEST_FIELDS
from .projector import build_projection_manifest
from .projector import golden_row_passes
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
METRIC_FIELDS = (
    "company", "cik", "metric_id", "metric_name", "value", "unit",
    "status", "source_class", "formula", "period_start", "period_end",
    "fiscal_year", "fiscal_period", "accession", "form", "filed_date",
    "concept_or_section", "context_or_dimension", "confidence", "notes",
)
EVIDENCE_FIELDS = (
    "company", "cik", "metric_id", "source_url", "repo_relative_path",
    "content_sha256", "accession", "document_name", "concept_or_section",
    "context_or_dimension", "unit", "period_start", "period_end",
    "value_raw", "value_normalized", "evidence_quote",
    "extraction_method", "parser_version",
)
COVERAGE_FIELDS = (
    "company", "metric_id", "status", "source_class",
    "has_numeric_value", "has_evidence", "needs_text_extraction",
    "needs_review", "reason",
)
GOLDEN_FIELDS = (
    "assertion_id", "description", "expected", "actual", "status",
    "evidence_path", "notes",
)
REPAIR_FIELDS = ("check_id", "severity", "status", "details")
SCALABILITY_FIELDS = (
    "file", "line", "literal", "type", "allowed", "reason",
    "replacement_plan",
)
STRATIFIED_FIELDS = (
    "audit_id", "source_bucket", "company", "metric_id", "metric_name",
    "value", "unit", "status", "source_class", "period_start",
    "period_end", "accession", "concept_or_section",
    "context_or_dimension", "evidence_value", "evidence_unit",
    "evidence_quote", "audit_verdict", "audit_notes",
)


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


def _validate_publication_metadata(
    *,
    requirement_hashes: Mapping[str, object],
    batch_manifest_id: object,
    projection_manifest_id: object,
    validation_receipt_id: object,
    ledger_binding: Mapping[str, object],
    previous_publication_id: object,
) -> None:
    """Validate publication identities before hashing or reading.

    Args:
        requirement_hashes: Exact Requirement digest mapping.
        batch_manifest_id: Complete FROZEN Run collection identity.
        projection_manifest_id: Run-derived projection proof identity.
        validation_receipt_id: Execution-bound gate receipt identity.
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
    for identity, label in (
        (batch_manifest_id, "BatchManifest"),
        (projection_manifest_id, "ProjectionManifest"),
        (validation_receipt_id, "ValidationReceipt"),
    ):
        if (
            type(identity) is not str
            or CONTENT_ID_PATTERN.fullmatch(identity) is None
        ):
            raise PublicationError("{} identity is invalid".format(label))
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
    batch_manifest_path: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
) -> Dict[str, object]:
    """Derive publication identities through the Projector's single gate.

    Args:
        repo_root: Repository containing Requirement and release-plan bytes.
        batch_manifest_path: Complete persisted FROZEN Run collection.
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
            batch_manifest_path=batch_manifest_path,
            legacy_snapshot_dir=legacy_snapshot_dir,
            staging_dir=staging_dir,
        )
    except ValueError as error:
        raise PublicationError(
            "Publication requires a verified projection context"
        ) from error
    if projection["publication_candidate_status"] != "PUBLISHABLE":
        raise PublicationError("FROZEN batch results are not publishable")
    return {
        "batch_manifest_id": projection["batch_manifest_id"],
        "projection_manifest": projection,
        "projection_manifest_id": projection["projection_manifest_id"],
        "requirement_hashes": dict(projection["requirement_hashes"]),
    }


def _read_staging_files(
    *, staging_dir: Path, include_receipt: bool
) -> Dict[str, bytes]:
    """Read one exact regular-file staging candidate.

    Args:
        staging_dir: Dedicated candidate directory.
        include_receipt: Whether the execution receipt must already exist.

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
    expected_files = (
        REQUIRED_BUNDLE_FILES
        if include_receipt
        else REQUIRED_BUNDLE_FILES - {"publication_validation_receipt.json"}
    )
    if actual_files != expected_files or actual_directories:
        raise PublicationError("Publication staging exact set differs")
    return {
        relative: (staging_dir / relative).read_bytes()
        for relative in sorted(expected_files)
    }


def publication_validation_view_id(
    *,
    files: Mapping[str, bytes],
    requirement_hashes: Mapping[str, object],
    batch_manifest_id: str,
    projection_manifest_id: str,
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> str:
    """Hash the exact non-self-referential staging candidate view.

    Args:
        files: Required bundle bytes before or after adding the receipt.
        requirement_hashes: Exact Requirement Snapshot identities.
        batch_manifest_id: Complete FROZEN Run collection identity.
        projection_manifest_id: Exact Run-derived projection proof.
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
    _validate_publication_metadata(
        requirement_hashes=requirement_hashes,
        batch_manifest_id=batch_manifest_id,
        projection_manifest_id=projection_manifest_id,
        validation_receipt_id="sha256:" + "0" * 64,
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
            "batch_manifest_id": batch_manifest_id,
            "ledger_binding": dict(ledger_binding),
            "previous_publication_id": previous_publication_id,
            "projection_manifest_id": projection_manifest_id,
            "requirement_hashes": dict(requirement_hashes),
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
    batch_manifest_id: str,
    projection_manifest_id: str,
    gate_evidence: Mapping[str, object],
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> None:
    """Bind a staging receipt to the exact non-self-referential bundle bytes.

    Args:
        files: Complete required bundle bytes including the receipt.
        receipt: Strict PASSED ValidationReceipt.
        requirement_hashes: Exact Requirement Snapshot identities.
        batch_manifest_id: Complete FROZEN Run collection identity.
        projection_manifest_id: Exact Run-derived projection proof.
        gate_evidence: Independently recomputed check evidence.
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
        or any(
            set(check) != {"check", "evidence_hash", "status"}
            or check["evidence_hash"]
            != content_hash(value=gate_evidence[str(check["check"])])
            for check in checks
        )
    ):
        raise PublicationError(
            "Publication required gate execution did not PASS"
        )
    expected_view = publication_validation_view_id(
        files=files,
        requirement_hashes=requirement_hashes,
        batch_manifest_id=batch_manifest_id,
        projection_manifest_id=projection_manifest_id,
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
    batch_manifest_id: str,
    projection_manifest_id: str,
) -> Dict[str, object]:
    """Validate the bundled ProjectionManifest as candidate authority.

    Args:
        content: Exact bundled ``projection_manifest.json`` bytes.
        requirement_hashes: Publication Requirement binding.
        batch_manifest_id: Publication batch identity.
        projection_manifest_id: Publication projection identity.

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
        or manifest["schema_version"] != 2
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
    expected_entries = manifest["expected_result_keys"]
    result_bindings = manifest["result_bindings"]
    run_bindings = manifest["run_bindings"]
    expected_fields = {"applicability", "company_id", "metric_id"}
    result_fields = {
        "applicability", "company_id", "evidence_row_hashes", "metric_id",
        "metric_row_hash", "result_id", "trace_id", "unit", "value",
    }
    run_fields = {
        "audit_manifest_hash", "company_id", "content_manifest_hash",
        "result_ids", "run_id", "run_path", "validation_receipt_id",
    }
    if (
        type(expected_entries) is not list
        or type(result_bindings) is not list
        or type(run_bindings) is not list
        or not expected_entries
        or not result_bindings
        or not run_bindings
        or any(
            not isinstance(entry, dict) or set(entry) != expected_fields
            for entry in expected_entries
        )
        or any(
            not isinstance(binding, dict) or set(binding) != result_fields
            for binding in result_bindings
        )
        or any(
            not isinstance(binding, dict) or set(binding) != run_fields
            for binding in run_bindings
        )
        or any(
            type(entry["company_id"]) is not str
            or not entry["company_id"]
            or type(entry["metric_id"]) is not str
            or not entry["metric_id"]
            or entry["applicability"] not in {
                "APPLICABLE", "N_A_STRUCTURAL",
            }
            for entry in expected_entries
        )
        or any(
            type(binding["company_id"]) is not str
            or not binding["company_id"]
            or type(binding["metric_id"]) is not str
            or not binding["metric_id"]
            or binding["applicability"] not in {
                "APPLICABLE", "N_A_STRUCTURAL",
            }
            or not (
                binding["value"] is None
                or type(binding["value"]) is str
            )
            or not (
                binding["unit"] is None
                or type(binding["unit"]) is str
            )
            for binding in result_bindings
        )
        or any(
            type(binding["company_id"]) is not str
            or not binding["company_id"]
            or type(binding["run_id"]) is not str
            or not binding["run_id"]
            or type(binding["run_path"]) is not str
            or not binding["run_path"]
            for binding in run_bindings
        )
    ):
        raise PublicationError("Projection batch proof shape is invalid")
    expected_keys = [
        (entry["company_id"], entry["metric_id"])
        for entry in expected_entries
    ]
    result_keys = [
        (binding["company_id"], binding["metric_id"])
        for binding in result_bindings
    ]
    if (
        len(expected_keys) != len(set(expected_keys))
        or expected_keys != result_keys
        or any(
            expected_entries[index]["applicability"]
            != result_bindings[index]["applicability"]
            for index in range(len(expected_entries))
        )
        or any(
            entry["applicability"] not in {
                "APPLICABLE", "N_A_STRUCTURAL",
            }
            for entry in expected_entries
        )
    ):
        raise PublicationError("Projection batch exact set differs")
    for binding in result_bindings:
        _validate_id_list(
            values=binding["evidence_row_hashes"],
            label="Projection evidence_row_hashes",
            content_ids=True,
        )
        for field in ("metric_row_hash", "result_id", "trace_id"):
            if (
                type(binding[field]) is not str
                or CONTENT_ID_PATTERN.fullmatch(binding[field]) is None
            ):
                raise PublicationError("Projection Result proof is invalid")
    if sorted(
        binding["result_id"] for binding in result_bindings
    ) != sorted(manifest["result_ids"]):
        raise PublicationError("Projection Result identity order differs")
    bound_result_ids = []
    for binding in run_bindings:
        for field in (
            "audit_manifest_hash", "content_manifest_hash",
            "validation_receipt_id",
        ):
            if (
                type(binding[field]) is not str
                or CONTENT_ID_PATTERN.fullmatch(binding[field]) is None
            ):
                raise PublicationError("Projection Run proof is invalid")
        _validate_id_list(
            values=binding["result_ids"],
            label="Projection Run result_ids",
            content_ids=True,
        )
        bound_result_ids.extend(binding["result_ids"])
    if sorted(bound_result_ids) != sorted(manifest["result_ids"]):
        raise PublicationError("Projection Run Result binding differs")
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
    ):
        raise PublicationError("Projection release identity is invalid")
    for field in ("batch_manifest_id", "projection_manifest_id"):
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
    if (
        manifest["batch_manifest_id"] != batch_manifest_id
        or manifest["projection_manifest_id"] != projection_manifest_id
    ):
        raise PublicationError(
            "ProjectionManifest publication binding differs"
        )
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


def _csv_rows(
    *, content: bytes, fieldnames: tuple, label: str
) -> list:
    """Parse one strict publication CSV artifact.

    Args:
        content: Complete candidate bytes.
        fieldnames: Required ordered header.
        label: Diagnostic artifact name.

    Returns:
        Ordered string-valued rows.

    Raises:
        PublicationError: On invalid UTF-8, header, or row width.
    """
    try:
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if tuple(reader.fieldnames or ()) != fieldnames:
            raise PublicationError("{} CSV schema differs".format(label))
        rows = []
        for row in reader:
            if None in row or any(row[field] is None for field in fieldnames):
                raise PublicationError(
                    "{} CSV row width differs".format(label)
                )
            rows.append({field: str(row[field]) for field in fieldnames})
    except (UnicodeDecodeError, csv.Error) as error:
        raise PublicationError("{} CSV is invalid".format(label)) from error
    return rows


def _csv_bytes(*, rows: list, fieldnames: tuple) -> bytes:
    """Serialize one exact publication CSV deterministically.

    Args:
        rows: Ordered exact-schema string mappings.
        fieldnames: Required output column order.

    Returns:
        UTF-8 CSV bytes with stable line endings.
    """
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(fieldnames),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        if set(row) != set(fieldnames):
            raise PublicationError("Generated publication CSV schema differs")
        writer.writerow({field: row[field] for field in fieldnames})
    return output.getvalue().encode("utf-8")


def _expected_coverage_rows(*, metrics: list, evidence: list) -> list:
    """Derive the complete coverage matrix from candidate rows.

    Args:
        metrics: Parsed full metrics matrix.
        evidence: Parsed full evidence rows.

    Returns:
        Ordered coverage rows with no caller-authored status fields.
    """
    evidence_keys = {
        (row["company"], row["metric_id"]) for row in evidence
    }
    output = []
    for metric in metrics:
        key = (metric["company"], metric["metric_id"])
        status = metric["status"]
        output.append(
            {
                "company": metric["company"],
                "metric_id": metric["metric_id"],
                "status": status,
                "source_class": metric["source_class"],
                "has_numeric_value": "1" if metric["value"] else "0",
                "has_evidence": "1" if key in evidence_keys else "0",
                "needs_text_extraction": (
                    "1"
                    if status in {"NOT_EXTRACTED", "NEEDS_REVIEW"}
                    else "0"
                ),
                "needs_review": "1" if status == "NEEDS_REVIEW" else "0",
                "reason": _coverage_reason(metric=metric),
            }
        )
    return output


def _expected_stratified_rows(
    *, metrics: list, evidence: list, migrated_ids: set
) -> list:
    """Audit every numeric migrated row against one bound evidence row.

    Args:
        metrics: Parsed full metrics matrix.
        evidence: Parsed full evidence rows.
        migrated_ids: Repository-owned migrated metric set.

    Returns:
        Deterministic comprehensive vNext audit rows.

    Raises:
        PublicationError: When a numeric migrated result lacks evidence.
    """
    evidence_by_key = {}
    for row in evidence:
        key = (row["company"], row["metric_id"])
        if key not in evidence_by_key:
            evidence_by_key[key] = []
        evidence_by_key[key].append(row)
    output = []
    for metric in metrics:
        if metric["metric_id"] not in migrated_ids or not metric["value"]:
            continue
        key = (metric["company"], metric["metric_id"])
        if key not in evidence_by_key or not evidence_by_key[key]:
            raise PublicationError("Migrated audit row lacks evidence")
        bound_evidence = evidence_by_key[key]
        output.append(
            {
                "audit_id": "AUDIT_{:02d}".format(len(output) + 1),
                "source_bucket": metric["source_class"],
                **{
                    field: metric[field]
                    for field in (
                        "company", "metric_id", "metric_name", "value",
                        "unit", "status", "source_class", "period_start",
                        "period_end", "accession", "concept_or_section",
                        "context_or_dimension",
                    )
                },
                "evidence_value": ";".join(
                    row["value_normalized"] for row in bound_evidence
                ),
                "evidence_unit": ";".join(
                    row["unit"] for row in bound_evidence
                ),
                "evidence_quote": " | ".join(
                    row["evidence_quote"] for row in bound_evidence
                ),
                "audit_verdict": "PASS",
                "audit_notes": (
                    "Candidate Result and all evidence rows are bound."
                ),
            }
        )
    if not output:
        raise PublicationError("Migrated stratified audit is empty")
    return output


def _markdown_cell(*, value: object) -> str:
    """Render one untrusted scalar without changing Markdown table shape.

    Args:
        value: Candidate scalar rendered for a recorded report.

    Returns:
        Single-line pipe-safe text.
    """
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _expected_documents(
    *, metrics: list, projection: Mapping[str, object]
) -> Dict[str, bytes]:
    """Render deterministic recorded-only bundle documentation.

    Args:
        metrics: Parsed full candidate matrix.
        projection: Strict ProjectionManifest for the same view.

    Returns:
        README and report bytes derived only from verified candidate data.
    """
    report_lines = [
        "# vNext recorded publication report",
        "",
        (
            "> Recorded/shadow artifact; this is not active/full Cutover "
            "evidence."
        ),
        "",
        "- Batch: `{}`".format(projection["batch_manifest_id"]),
        "- Projection: `{}`".format(
            projection["projection_manifest_id"]
        ),
        "",
        "| Company | Metric | Value | Unit | Status |",
        "|---|---|---:|---|---|",
    ]
    report_lines.extend(
        "| {} | {} | {} | {} | {} |".format(
            _markdown_cell(value=row["company"]),
            _markdown_cell(value=row["metric_id"]),
            _markdown_cell(value=row["value"]),
            _markdown_cell(value=row["unit"]),
            _markdown_cell(value=row["status"]),
        )
        for row in metrics
    )
    readme = "\n".join(
        [
            "# vNext recorded publication bundle",
            "",
            "- batch_manifest_id: `{}`".format(
                projection["batch_manifest_id"]
            ),
            "- projection_manifest_id: `{}`".format(
                projection["projection_manifest_id"]
            ),
            "- rows: `{}`".format(len(metrics)),
            "- boundary: recorded/shadow only; full Cutover not proven",
            "",
        ]
    )
    return {
        "README_RUN.md": readme.encode("utf-8"),
        "REPORT_十公司财务指标.md": (
            "\n".join(report_lines) + "\n"
        ).encode("utf-8"),
    }


def _write_generated_artifact(
    *, path: Path, content: bytes, label: str
) -> None:
    """Create one generated artifact or reject divergent caller bytes.

    Args:
        path: Fixed staging destination.
        content: Exact production-derived bytes.
        label: Diagnostic artifact identity.

    Raises:
        PublicationError: When an existing entry is unsafe or differs.
    """
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise PublicationError("{} path is unsafe".format(label))
    if path.exists():
        if path.read_bytes() != content:
            raise PublicationError(
                "{} differs from gate execution".format(label)
            )
        return
    atomic_write_bytes(path=path, content=content)


def _json_mapping(*, content: bytes, label: str) -> Dict[str, object]:
    """Parse one strict UTF-8 JSON object from candidate bytes.

    Args:
        content: Complete JSON bytes.
        label: Diagnostic artifact name.

    Returns:
        Isolated mapping.
    """
    try:
        parsed = strict_json_loads(text=content.decode("utf-8"))
    except (UnicodeDecodeError, CanonicalError) as error:
        raise PublicationError("{} JSON is invalid".format(label)) from error
    if not isinstance(parsed, dict):
        raise PublicationError("{} JSON root must be object".format(label))
    return dict(parsed)


def _coverage_reason(*, metric: Mapping[str, str]) -> str:
    """Rebuild the legacy coverage reason for one metric row.

    Args:
        metric: Exact metrics-matrix row.

    Returns:
        Deterministic user-facing coverage reason.
    """
    status = metric["status"]
    notes = metric["notes"]
    if status == "NOT_AVAILABLE_SEC":
        return "SEC 未披露: " + notes
    if status == "NOT_EXTRACTED":
        return (
            notes
            if notes.startswith("本轮没抽到:")
            else "本轮没抽到: " + notes
        )
    if status == "NEEDS_REVIEW":
        return (
            notes
            if notes.startswith("需复核:")
            else "多事实需复核/需复核: " + notes
        )
    if status == "N_A_STRUCTURAL":
        return "结构不适用: " + notes
    return notes


def _semantic_gate_evidence(
    *, receipt: Mapping[str, object], repo_root: Optional[Path]
) -> Dict[str, object]:
    """Validate semantic-audit proof and optionally current source bytes.

    Args:
        receipt: Bundled semantic audit receipt.
        repo_root: Repository checked during preparation, or ``None`` during
            immutable read-back.

    Returns:
        Stable proof summary independent of repository availability.
    """
    if set(receipt) != {
        "failure_code", "hits", "schema_version", "source_hashes", "status",
    } or (
        receipt["schema_version"] != 1
        or receipt["status"] != "PASS"
        or receipt["failure_code"] != ""
        or receipt["hits"] != []
        or not isinstance(receipt["source_hashes"], dict)
        or not receipt["source_hashes"]
    ):
        raise PublicationError("Semantic audit did not PASS")
    source_hashes = receipt["source_hashes"]
    if any(
        type(relative) is not str
        or not relative
        or type(source_hashes[relative]) is not str
        or SHA256_PATTERN.fullmatch(source_hashes[relative]) is None
        for relative in source_hashes
    ):
        raise PublicationError("Semantic audit source binding is invalid")
    if repo_root is not None and receipt != _execute_semantic_audit(
        repo_root=repo_root,
    ):
        raise PublicationError("Semantic audit execution differs")
    return {
        "source_count": len(source_hashes),
        "source_hashes_id": content_hash(value=source_hashes),
    }


def _execute_semantic_audit(*, repo_root: Path) -> Dict[str, object]:
    """Run the repository semantic gate and return its exact receipt.

    Args:
        repo_root: Repository containing the audited source and gate tool.

    Returns:
        Strict semantic-audit receipt produced by the real gate executable.

    Raises:
        PublicationError: When the gate is missing, times out, fails, or emits
            an unreadable receipt.
    """
    tool_path = repo_root / "tools" / "check_vnext_semantics.py"
    if tool_path.is_symlink() or not tool_path.is_file():
        raise PublicationError("Semantic audit executable is unsafe")
    try:
        with tempfile.TemporaryDirectory(
            prefix="sec-metrics-semantic-"
        ) as directory:
            output_path = Path(directory) / "receipt.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(tool_path),
                    "--repo-root",
                    str(repo_root),
                    "--output",
                    str(output_path),
                ],
                cwd=str(repo_root),
                check=False,
                capture_output=True,
                timeout=60,
            )
            if completed.returncode != 0:
                raise PublicationError("Semantic audit execution failed")
            payload = strict_json_file(path=output_path)
    except (OSError, subprocess.TimeoutExpired, CanonicalError) as error:
        raise PublicationError("Semantic audit execution failed") from error
    if not isinstance(payload, dict):
        raise PublicationError("Semantic audit receipt is malformed")
    return dict(payload)


def _publication_gate_evidence(
    *, files: Mapping[str, bytes], projection: Mapping[str, object],
    repo_root: Optional[Path]
) -> Dict[str, object]:
    """Execute all publication checks against one exact candidate view.

    Args:
        files: Required candidate artifacts, with or without the final receipt.
        projection: Strict ProjectionManifest bound to those bytes.
        repo_root: Repository authority during preparation, or ``None`` during
            immutable read-back.

    Returns:
        One deterministic evidence object per required publication check.

    Raises:
        PublicationError: When any check cannot prove its invariant.
    """
    metrics = _csv_rows(
        content=files["metrics_matrix.csv"],
        fieldnames=METRIC_FIELDS,
        label="Metrics",
    )
    evidence = _csv_rows(
        content=files["metric_evidence.csv"],
        fieldnames=EVIDENCE_FIELDS,
        label="Evidence",
    )
    metric_keys = [(row["company"], row["metric_id"]) for row in metrics]
    if len(metric_keys) != len(set(metric_keys)):
        raise PublicationError("Metrics compatibility key is duplicated")
    evidence_keys = {(row["company"], row["metric_id"]) for row in evidence}
    if any(
        row["value"]
        and (row["company"], row["metric_id"]) not in evidence_keys
        for row in metrics
    ):
        raise PublicationError("Numeric metric lacks matching evidence")

    coverage = _csv_rows(
        content=files["coverage_matrix.csv"],
        fieldnames=COVERAGE_FIELDS,
        label="Coverage",
    )
    expected_coverage = _expected_coverage_rows(
        metrics=metrics, evidence=evidence,
    )
    if coverage != expected_coverage:
        raise PublicationError("Coverage does not match candidate rows")

    golden = _csv_rows(
        content=files["golden_results.csv"],
        fieldnames=GOLDEN_FIELDS,
        label="Golden",
    )
    golden_ids = [row["assertion_id"] for row in golden]
    if (
        not golden
        or len(golden_ids) != len(set(golden_ids))
        or any(
            row["status"] != "PASS" or not golden_row_passes(row=row)
            for row in golden
        )
    ):
        raise PublicationError("Golden execution did not PASS")

    compatibility = _json_mapping(
        content=files["legacy_invariant_migration_receipt.json"],
        label="Compatibility receipt",
    )
    if (
        set(compatibility) != {
            "batch_manifest_id", "evidence_reconciliations",
            "legacy_input_hashes", "metric_cells", "receipt_id",
            "schema_version", "status",
        }
        or compatibility["schema_version"] != 1
        or compatibility["status"] != "PASS"
        or compatibility["batch_manifest_id"]
        != projection["batch_manifest_id"]
        or compatibility["legacy_input_hashes"]
        != projection["legacy_input_hashes"]
        or type(compatibility["evidence_reconciliations"]) is not list
        or type(compatibility["metric_cells"]) is not list
        or any(
            type(row) is not dict
            or set(row) != {
                "comparisons", "exact_cells", "key", "method_cells",
                "status",
            }
            or row["status"] != "PASS"
            or type(row["comparisons"]) is not dict
            or type(row["exact_cells"]) is not list
            or type(row["method_cells"]) is not list
            or any(
                type(cell) is not dict
                or set(cell) != {
                    "class", "field", "key", "new", "old", "status",
                }
                or cell["class"] != "EXACT"
                or cell["status"] != "PASS"
                for cell in row["exact_cells"]
            )
            or any(
                type(cell) is not dict
                or set(cell) != {
                    "class", "field", "key", "new", "old", "status",
                }
                or cell["class"] != "DECLARATIVE_METHOD_DELTA"
                or cell["status"] != "RECORDED"
                for cell in row["method_cells"]
            )
            for row in compatibility["evidence_reconciliations"]
        )
        or any(
            not isinstance(cell, dict)
            or "status" not in cell
            or cell["status"] not in {"PASS", "RECORDED"}
            for cell in compatibility["metric_cells"]
        )
    ):
        raise PublicationError("Compatibility execution did not PASS")
    compatibility_body = {
        key: compatibility[key]
        for key in compatibility
        if key not in {"receipt_id", "schema_version"}
    }
    if compatibility["receipt_id"] != content_hash(
        value=compatibility_body
    ):
        raise PublicationError("Compatibility execution identity differs")

    migrated_ids = set(projection["migrated_metric_ids"])
    migrated_metric_hashes = sorted(
        content_hash(value=row)
        for row in metrics
        if row["metric_id"] in migrated_ids
    )
    bound_metric_hashes = sorted(
        binding["metric_row_hash"]
        for binding in projection["result_bindings"]
    )
    migrated_evidence_hashes = sorted(
        content_hash(value=row)
        for row in evidence
        if row["metric_id"] in migrated_ids
    )
    bound_evidence_hashes = sorted(
        identity
        for binding in projection["result_bindings"]
        for identity in binding["evidence_row_hashes"]
    )
    if (
        migrated_metric_hashes != bound_metric_hashes
        or migrated_evidence_hashes != bound_evidence_hashes
    ):
        raise PublicationError("Projection rows differ from Result proof")

    repair = _csv_rows(
        content=files["repair_validation_results.csv"],
        fieldnames=REPAIR_FIELDS,
        label="Repair validation",
    )
    repair_ids = [row["check_id"] for row in repair]
    validation = _json_mapping(
        content=files["validation_run_manifest.json"],
        label="Validation manifest",
    )
    required_refreshed = {
        "coverage_matrix.csv", "golden_results.csv",
        "legacy_invariant_migration_receipt.json",
        "repair_validation_results.csv", "scalability_audit.csv",
        "semantic_audit_receipt.json", "stratified_audit.csv",
    }
    validation_fields = {
        "mode", "not_refreshed_artifacts", "refreshed_artifacts",
        "result", "run_id", "source_commit", "started_at_utc",
    }
    if (
        not repair
        or len(repair_ids) != len(set(repair_ids))
        or any(row["status"] != "PASS" for row in repair)
        or set(validation) != validation_fields
        or any(
            type(validation[field]) is not str or not validation[field]
            for field in (
                "mode", "result", "run_id", "source_commit",
                "started_at_utc",
            )
        )
        or any(
            type(validation[field]) is not list
            or any(
                type(relative) is not str or not relative
                for relative in validation[field]
            )
            or len(validation[field]) != len(set(validation[field]))
            for field in (
                "refreshed_artifacts", "not_refreshed_artifacts",
            )
        )
        or validation["mode"] != "RECORDED_VNEXT"
        or validation["result"] != "PASSED_RECORDED_ONLY"
        or validation["run_id"]
        != "validation:" + projection["projection_manifest_id"]
        or validation["source_commit"]
        != "RECORDED_VNEXT_NO_SOURCE_COMMIT"
        or set(validation["refreshed_artifacts"]) != required_refreshed
        or validation["not_refreshed_artifacts"] != []
    ):
        raise PublicationError("Repair validation execution did not PASS")
    try:
        parse_utc_timestamp(value=validation["started_at_utc"])
    except CanonicalError as error:
        raise PublicationError(
            "Recorded validation timestamp is invalid"
        ) from error

    scalability = _csv_rows(
        content=files["scalability_audit.csv"],
        fieldnames=SCALABILITY_FIELDS,
        label="Scalability audit",
    )
    if scalability:
        raise PublicationError("Scalability audit contains forbidden literals")

    semantic = _semantic_gate_evidence(
        receipt=_json_mapping(
            content=files["semantic_audit_receipt.json"],
            label="Semantic audit",
        ),
        repo_root=repo_root,
    )

    stratified = _csv_rows(
        content=files["stratified_audit.csv"],
        fieldnames=STRATIFIED_FIELDS,
        label="Stratified audit",
    )
    expected_stratified = _expected_stratified_rows(
        metrics=metrics, evidence=evidence, migrated_ids=migrated_ids,
    )
    if stratified != expected_stratified:
        raise PublicationError("Stratified audit execution did not PASS")

    expected_documents = _expected_documents(
        metrics=metrics, projection=projection,
    )
    if any(
        files[relative] != expected_documents[relative]
        for relative in expected_documents
    ):
        raise PublicationError("Publication document differs from candidate")
    return {
        "COVERAGE": {"rows_id": content_hash(value=coverage)},
        "GOLDEN": {"rows_id": content_hash(value=golden)},
        "LEGACY_INVARIANT_MIGRATION": {
            "receipt_id": compatibility["receipt_id"],
        },
        "PROJECTION_EXACT_SET": {
            "evidence_rows_id": content_hash(value=migrated_evidence_hashes),
            "metric_rows_id": content_hash(value=migrated_metric_hashes),
        },
        "REPAIR_VALIDATION": {
            "manifest_id": content_hash(value=validation),
            "rows_id": content_hash(value=repair),
        },
        "SCALABILITY_AUDIT": {"rows_id": content_hash(value=scalability)},
        "SEMANTIC_AUDIT": semantic,
        "STRATIFIED_AUDIT": {"rows_id": content_hash(value=stratified)},
    }


def _finalize_staging_view(
    *, repo_root: Path, staging_dir: Path, context: Mapping[str, object],
    validated_at_utc: str
) -> Dict[str, object]:
    """Generate every non-Projector artifact from one verified candidate.

    Args:
        repo_root: Repository authority used by the semantic executable.
        staging_dir: Candidate root already containing Projector artifacts.
        context: Recomputed Projector staging context.
        validated_at_utc: Explicit UTC execution timestamp.

    Returns:
        Strict staged ProjectionManifest.

    Raises:
        PublicationError: When caller-authored bytes differ from generated
            coverage, audits, validation metadata, or documentation.
    """
    try:
        parse_utc_timestamp(value=validated_at_utc)
    except CanonicalError as error:
        raise PublicationError(
            "Recorded validation timestamp is invalid"
        ) from error
    projection_path = staging_dir / "projection_manifest.json"
    if projection_path.is_symlink() or not projection_path.is_file():
        raise PublicationError("Staged ProjectionManifest is unsafe")
    projection = _validate_projection_manifest(
        content=projection_path.read_bytes(),
        requirement_hashes=context["requirement_hashes"],
        batch_manifest_id=str(context["batch_manifest_id"]),
        projection_manifest_id=str(context["projection_manifest_id"]),
    )
    if projection != context["projection_manifest"]:
        raise PublicationError("Staged ProjectionManifest differs")
    metrics = _csv_rows(
        content=(staging_dir / "metrics_matrix.csv").read_bytes(),
        fieldnames=METRIC_FIELDS,
        label="Metrics",
    )
    evidence = _csv_rows(
        content=(staging_dir / "metric_evidence.csv").read_bytes(),
        fieldnames=EVIDENCE_FIELDS,
        label="Evidence",
    )
    migrated_ids = set(projection["migrated_metric_ids"])
    semantic = _execute_semantic_audit(repo_root=repo_root)
    refreshed = sorted(
        {
            "coverage_matrix.csv", "golden_results.csv",
            "legacy_invariant_migration_receipt.json",
            "repair_validation_results.csv", "scalability_audit.csv",
            "semantic_audit_receipt.json", "stratified_audit.csv",
        }
    )
    generated = {
        "coverage_matrix.csv": _csv_bytes(
            rows=_expected_coverage_rows(
                metrics=metrics, evidence=evidence,
            ),
            fieldnames=COVERAGE_FIELDS,
        ),
        "scalability_audit.csv": _csv_bytes(
            rows=[], fieldnames=SCALABILITY_FIELDS,
        ),
        "semantic_audit_receipt.json": (
            canonical_json_bytes(value=semantic) + b"\n"
        ),
        "stratified_audit.csv": _csv_bytes(
            rows=_expected_stratified_rows(
                metrics=metrics,
                evidence=evidence,
                migrated_ids=migrated_ids,
            ),
            fieldnames=STRATIFIED_FIELDS,
        ),
        "validation_run_manifest.json": canonical_json_bytes(
            value={
                "run_id": (
                    "validation:" + projection["projection_manifest_id"]
                ),
                "source_commit": "RECORDED_VNEXT_NO_SOURCE_COMMIT",
                "started_at_utc": validated_at_utc,
                "mode": "RECORDED_VNEXT",
                "refreshed_artifacts": refreshed,
                "not_refreshed_artifacts": [],
                "result": "PASSED_RECORDED_ONLY",
            }
        ) + b"\n",
    }
    generated.update(
        _expected_documents(metrics=metrics, projection=projection)
    )
    for relative in generated:
        _write_generated_artifact(
            path=staging_dir / relative,
            content=generated[relative],
            label=relative,
        )
    return projection


def write_publication_validation_receipt(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path,
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str], validated_at_utc: str
) -> Dict[str, object]:
    """Execute publication gates and persist their content-bound receipt.

    Args:
        repo_root: Repository authority used by Projector and semantic audit.
        batch_manifest_path: Complete FROZEN Run collection.
        legacy_snapshot_dir: Legacy inputs named by ProjectionManifest.
        staging_dir: Exact candidate view without a validation receipt.
        ledger_binding: Used request-ledger prefix identities.
        previous_publication_id: Prepared predecessor identity.
        validated_at_utc: Explicit UTC gate execution timestamp.

    Returns:
        Strict persisted ValidationReceipt.
    """
    context = publication_staging_context(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
    )
    projection = _finalize_staging_view(
        repo_root=repo_root,
        staging_dir=staging_dir,
        context=context,
        validated_at_utc=validated_at_utc,
    )
    files = _read_staging_files(
        staging_dir=staging_dir, include_receipt=False,
    )
    gate_evidence = _publication_gate_evidence(
        files=files, projection=projection, repo_root=repo_root,
    )
    body = {
        "status": "PASSED",
        "view_id": publication_validation_view_id(
            files=files,
            requirement_hashes=context["requirement_hashes"],
            batch_manifest_id=context["batch_manifest_id"],
            projection_manifest_id=context["projection_manifest_id"],
            ledger_binding=ledger_binding,
            previous_publication_id=previous_publication_id,
        ),
        "checks": [
            {
                "check": check,
                "evidence_hash": content_hash(value=gate_evidence[check]),
                "status": "PASS",
            }
            for check in sorted(REQUIRED_PUBLICATION_CHECKS)
        ],
        "artifact_hashes": {
            relative: {
                "sha256": sha256_bytes(content=files[relative]),
                "size": len(files[relative]),
            }
            for relative in sorted(files)
        },
    }
    receipt = validate_record(
        record={
            **body,
            "record_type": "VALIDATION_RECEIPT",
            "validation_receipt_id": content_hash(value=body),
        }
    )
    atomic_write_json(
        path=staging_dir / "publication_validation_receipt.json",
        value=receipt,
    )
    return receipt


def prepare_publication_bundle(
    *,
    publication_root: Path,
    repo_root: Path,
    batch_manifest_path: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Create and verify one immutable complete PUBLISHABLE bundle.

    Args:
        publication_root: Single root from which bundle storage is derived.
        repo_root: Repository containing Requirement and release authority.
        batch_manifest_path: Complete persisted FROZEN Run collection.
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
    files = _read_staging_files(
        staging_dir=staging_dir, include_receipt=True,
    )
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
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
    )
    requirement_hashes = context["requirement_hashes"]
    batch_manifest_id = context["batch_manifest_id"]
    projection_manifest_id = context["projection_manifest_id"]
    validation_receipt_id = validated_receipt["validation_receipt_id"]
    _validate_publication_metadata(
        requirement_hashes=requirement_hashes,
        batch_manifest_id=batch_manifest_id,
        projection_manifest_id=projection_manifest_id,
        validation_receipt_id=validation_receipt_id,
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )
    projection = _validate_projection_manifest(
        content=files["projection_manifest.json"],
        requirement_hashes=requirement_hashes,
        batch_manifest_id=batch_manifest_id,
        projection_manifest_id=projection_manifest_id,
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
        batch_manifest_id=batch_manifest_id,
        projection_manifest_id=projection_manifest_id,
        gate_evidence=_publication_gate_evidence(
            files=files, projection=projection, repo_root=repo_root,
        ),
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
        "batch_manifest_id": batch_manifest_id,
        "projection_manifest_id": projection_manifest_id,
        "validation_receipt_id": validation_receipt_id,
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
        "batch_manifest_id": batch_manifest_id,
        "projection_manifest_id": projection_manifest_id,
        "validation_receipt_id": validation_receipt_id,
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
    _validate_publication_metadata(
        requirement_hashes=manifest["requirement_hashes"],
        batch_manifest_id=manifest["batch_manifest_id"],
        projection_manifest_id=manifest["projection_manifest_id"],
        validation_receipt_id=manifest["validation_receipt_id"],
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
        batch_manifest_id=str(manifest["batch_manifest_id"]),
        projection_manifest_id=str(manifest["projection_manifest_id"]),
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
        != manifest["validation_receipt_id"]
    ):
        raise PublicationError("Bundled validation receipt binding differs")
    _validate_receipt_artifacts(
        files=bundle_files,
        receipt=receipt,
        requirement_hashes=manifest["requirement_hashes"],
        batch_manifest_id=str(manifest["batch_manifest_id"]),
        projection_manifest_id=str(manifest["projection_manifest_id"]),
        gate_evidence=_publication_gate_evidence(
            files=bundle_files, projection=projection, repo_root=None,
        ),
        ledger_binding=manifest["ledger_binding"],
        previous_publication_id=manifest["previous_publication_id"],
    )
    identity = {
        "candidate_status": manifest["candidate_status"],
        "requirement_hashes": manifest["requirement_hashes"],
        "batch_manifest_id": manifest["batch_manifest_id"],
        "projection_manifest_id": manifest["projection_manifest_id"],
        "validation_receipt_id": manifest["validation_receipt_id"],
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
            latest_run_id = "batch:" + str(
                latest_manifest["batch_manifest_id"]
            ).split(":", maxsplit=1)[1]
            latest_run_status = "FROZEN"
            candidate_status = "PUBLISHABLE"
            expected_latest_id = latest_manifest["publication_id"]
        pointer = _read_pointer(pointer_path=pointer_path)
        if pointer is None:
            expected_active_id = None
            active_projection = None
        else:
            active_view = PublicationView._open_paths(
                publications_dir=publications_dir,
                pointer_path=pointer_path,
            )
            expected_active_id = active_view.publication_id
            active_projection = _json_mapping(
                content=active_view.read_bytes(
                    relative_path="projection_manifest.json"
                ),
                label="Active ProjectionManifest",
            )
        matching_active_runs = (
            []
            if active_projection is None
            else [
                binding
                for binding in active_projection["run_bindings"]
                if binding["run_id"] == latest_run_id
            ]
        )
        if len(matching_active_runs) > 1:
            raise PublicationError("Active batch Run identity is duplicated")
        if matching_active_runs:
            if latest_run_status != "FROZEN":
                raise PublicationError(
                    "Active Run identity conflicts with latest Run state"
                )
            if latest_run_dir is not None:
                active_run = matching_active_runs[0]
                if active_run["content_manifest_hash"] != latest_run[
                    "content_manifest_hash"
                ] or active_run["audit_manifest_hash"] != latest_run[
                    "audit_manifest_hash"
                ]:
                    raise PublicationError(
                        "Active and latest Run content identities differ"
                    )
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
