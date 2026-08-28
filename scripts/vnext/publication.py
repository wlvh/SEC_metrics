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
from typing import Dict, Mapping, Optional, Sequence, Tuple

from git_workspace import sanitized_git_environment
from sec_http import REQUEST_LOG_MANIFEST_SCHEMA_VERSION
from sec_http import legacy_response_snapshot_paths, parse_request_log_rows
from sec_http import request_accession, request_log_attempt_id
from sec_http import request_headers_bytes_match_identity
from sec_http import request_log_prefix_bytes
from sec_http import validate_request_log_manifest
from validation_provenance import ValidationProvenanceError
from validation_provenance import capture_source_snapshot

from .canonical import CanonicalError, atomic_write_bytes, atomic_write_json
from .canonical import canonical_json_bytes, content_hash, parse_utc_timestamp
from .canonical import sha256_bytes, sha256_file, strict_json_file
from .canonical import strict_json_loads
from .invocation_control import INVOCATION_STATE_NAMESPACES
from .projector import LEGACY_BASELINE_SOURCE_FILES
from .projector import LEGACY_INPUT_FILES, PROJECTION_CANDIDATE_FILES
from .projector import LEGACY_MIGRATION_STATUSES, LEGACY_PROOF_MODES
from .projector import PROJECTION_GATE_FILES, PROJECTION_MANIFEST_FIELDS
from .projector import FrozenRunLoader
from .projector import ProjectionError, build_projection_manifest
from .projector import golden_row_passes
from .projector import load_projection_batch_manifest
from .projector import load_legacy_path_inventory
from .projector import load_projection_used_source_references
from .projector import projection_file_hashes
from .qualification import QualificationError, qualification_closure_paths
from .qualification import validate_cutover_qualifications
from .records import validate_record
from .requirements import RequirementError, SNAPSHOT_FILES
from .requirements import load_requirement_snapshot
from .run_store import RunStoreError, load_frozen_run, load_run_for_status
from .sources import SourceError, resolve_repository_file
from .states import PUBLISHABLE_VALIDATION_STATUSES
from .states import publication_candidate_status


RECORDED_VALIDATION_MODE = "RECORDED_VNEXT"
RECORDED_VALIDATION_RESULT = "PASSED_RECORDED_ONLY"
FORMAL_VALIDATION_MODE = "FULL_VALIDATION"
FORMAL_VALIDATION_RESULT = "PASSED"
RECORDED_SOURCE_COMMIT = "RECORDED_VNEXT_NO_SOURCE_COMMIT"
LEGACY_BASELINE_IMPORT_MANIFEST = (
    "internal/legacy_baseline_import.json"
)
LEGACY_BASELINE_MANIFEST = "internal/legacy_baseline_manifest.json"
LEGACY_BASELINE_SUPPORT_PREFIX = "internal/legacy_baseline_support/"
ZERO_AI_FORMAL_MANIFEST = "internal/zero_ai_release_receipt.json"
LEGACY_BASELINE_REQUIRED_ARTIFACTS = {
    "outputs/golden_results.csv",
    "outputs/metric_evidence.csv",
    "outputs/metrics_matrix.csv",
    "outputs/validation_run_manifest.json",
    "outputs/validation_snapshot_provenance.json",
}
LEGACY_SYNTHETIC_METADATA_FILES = {
    "legacy_invariant_migration_receipt.json",
    "projection_manifest.json",
    "publication_validation_receipt.json",
}
LEGACY_BASELINE_IMPORT_FIELDS = {
    "baseline_artifacts",
    "baseline_manifest_sha256",
    "baseline_repository_commit",
    "legacy_baseline_import_id",
    "record_type",
    "requirement_hashes",
    "root_artifacts",
    "schema_version",
    "supporting_artifacts",
}
LEGACY_BASELINE_ARTIFACT_FIELDS = {"sha256", "size"}
LEGACY_ROOT_ARTIFACT_FIELDS = {
    "origin", "root_path", "sha256", "size",
}
LEGACY_SUPPORT_ARTIFACT_FIELDS = {
    "bundle_path", "sha256", "size",
}
LEGACY_COMMIT_AUTHORITY = "LEGACY_BASELINE"
FORMAL_COMMIT_AUTHORITY = "FORMAL"
RECORDED_COMMIT_AUTHORITY = "RECORDED"


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
INTERNAL_CLOSURE_MANIFEST = "internal/closure_manifest.json"
INTERNAL_BATCH_MANIFEST = "internal/batch/batch_manifest.json"
INTERNAL_REQUEST_LOCATOR_PROVENANCE = (
    "internal/request_locator_provenance.json"
)
INTERNAL_AUTHORITY_ROOT = "internal/authority"
INTERNAL_PREFIX = "internal/"
CLOSURE_MANIFEST_FIELDS = {
    "authority_root",
    "batch_manifest_id",
    "batch_manifest_path",
    "closure_id",
    "files",
    "ledger_binding",
    "qualification_binding",
    "request_locator_provenance_id",
    "run_bindings",
    "schema_version",
}
CLOSURE_AUTHORITY_FILES = {
    "catalog/company_traits.yaml",
    "config/company_registry.csv",
    "config/metric_applicability.yaml",
    "config/vnext_release_plan.json",
} | {
    "requirements/ai_first_v3_3_1/{}".format(relative)
    for relative in SNAPSHOT_FILES.values()
}
ROOT_MIRROR_RELATIVE_PATHS = {
    relative: (
        relative
        if relative in {"README_RUN.md", "REPORT_十公司财务指标.md"}
        else "outputs/" + relative
    )
    for relative in REQUIRED_BUNDLE_FILES
}
REQUIRED_PUBLICATION_CHECKS = {
    "COVERAGE",
    "GOLDEN",
    "LEGACY_INVARIANT_MIGRATION",
    "PROJECTION_EXACT_SET",
    "REQUEST_LOCATOR_TIER",
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
    "r3_addendum_sha256",
    "release_plan_sha256",
    "semantic_runtime_versions_hash",
}
REQUIREMENT_CONTENT_HASH_FIELDS = {"semantic_runtime_versions_hash"}
LEDGER_BINDING_FIELDS = {
    "request_locator_classes",
    "request_locator_proof_id",
    "request_locator_tier",
    "requests_log_prefix_sha256",
    "row_count",
    "source_reference_ids",
    "used_request_attempt_ids",
}
REQUEST_LOCATOR_CLASSES = {
    "IMMUTABLE_ATTEMPT",
    "IMMUTABLE_GIT_BLOB",
    "LEGACY_WORKING_LOCATOR",
}
LEGACY_BASELINE_LOCATOR_TIER = "LEGACY_BASELINE_IMPORT"
REQUEST_LOCATOR_TIERS = {
    FORMAL_VALIDATION_MODE,
    LEGACY_BASELINE_LOCATOR_TIER,
    RECORDED_VALIDATION_MODE,
}
REQUEST_LOCATOR_PROVENANCE_FIELDS = {
    "record_type",
    "request_locator_classes",
    "request_locator_proof_id",
    "schema_version",
    "source_proofs",
    "validation_tier",
}
REQUEST_LOCATOR_SOURCE_PROOF_FIELDS = {
    "body_sha256",
    "body_size",
    "headers_sha256",
    "headers_size",
    "ledger_row_index",
    "locator_class",
    "original_body_locator",
    "original_headers_locator",
    "portable_body_locator",
    "portable_headers_locator",
    "request_attempt_id",
    "source_reference_id",
}
POINTER_FIELDS = {
    "bundle_manifest_sha256",
    "committed_at_utc",
    "previous_publication_id",
    "publication_id",
}
SWITCH_RECEIPT_FIELDS = {
    "pointer",
    "previous_switch_receipt_id",
    "record_type",
    "schema_version",
    "switch_mode",
    "switch_receipt_id",
}
SWITCH_INTENT_FIELDS = {
    "intent_id",
    "previous_mirror_state",
    "previous_pointer",
    "previous_switch_receipt_id",
    "proposed_pointer",
    "record_type",
    "schema_version",
    "switch_mode",
}
SWITCH_INTENT_MIRROR_FIELDS = {"sha256", "size"}
PUBLICATION_ID_PATTERN = re.compile(r"^publication_[0-9a-f]{64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CONTENT_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SWITCH_TEMP_PATTERN = re.compile(
    r"^\.[0-9a-f]{64}\.json\.[0-9a-f]{32}\.tmp$"
)
LATEST_STATUS_FILENAME = "latest_run_status.json"
FAULT_RECEIPT_OUTCOMES = {
    "ABORTED_ACTIVE_PRESERVED",
    "CAS_LOST_ACTIVE_PRESERVED",
    "EXACTLY_ONE_WINNER",
    "MIXED_FISCAL_YEAR_BLOCKED",
    "PINNED_VIEW_STABLE",
    "RECOVERED_FROM_ACTIVE",
    "TAMPER_REJECTED",
    "WITHHELD_BLOCKED",
}
FAULT_STATE_FIELDS = {"active_publication_id", "mirror_hashes"}
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
SEMANTIC_GATE_SOURCE_PATHS = {
    "scripts/sec_pipeline.py",
    "tools/check_no_company_literals.py",
    "tools/check_vnext_semantics.py",
}


class PublicationError(RuntimeError):
    """Report incomplete bundles, CAS loss, tamper, or commit failure."""


def _fault_injection_checkpoint(*, fault_point: str) -> None:
    """Expose a named no-op transaction boundary for dynamic fault tests.

    Args:
        fault_point: Stable checkpoint identity patched only by failure tests.

    Expected output:
        Production execution continues unchanged. Tests may replace this
        function with an exception at one named I/O boundary.
    """
    if not isinstance(fault_point, str) or not fault_point:
        raise PublicationError("Publication fault point is invalid")


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
    outputs_dir = publication_root / "outputs"
    artifacts_root = publication_root / "artifacts"
    artifacts_dir = artifacts_root / "vnext"
    for path, label in (
        (outputs_dir, "Publication outputs"),
        (artifacts_root, "Publication artifacts"),
        (artifacts_dir, "vNext artifacts"),
    ):
        if path.is_symlink() or (
            path.exists() and not path.is_dir()
        ):
            raise PublicationError("{} must be a real directory".format(label))
    publications_dir = outputs_dir / "publications"
    if publications_dir.is_symlink() or (
        publications_dir.exists() and not publications_dir.is_dir()
    ):
        raise PublicationError("Publication storage must be a real directory")
    switch_receipts_dir = outputs_dir / "publication_switch_receipts"
    if switch_receipts_dir.is_symlink() or (
        switch_receipts_dir.exists() and not switch_receipts_dir.is_dir()
    ):
        raise PublicationError(
            "Publication switch history must be a real directory"
        )
    switch_intents_dir = outputs_dir / "publication_switch_intents"
    if switch_intents_dir.is_symlink() or (
        switch_intents_dir.exists() and not switch_intents_dir.is_dir()
    ):
        raise PublicationError(
            "Publication switch intents must be a real directory"
        )
    pointer_path = outputs_dir / "active_publication.json"
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    latest_status_path = artifacts_dir / LATEST_STATUS_FILENAME
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
        "switch_receipts_dir": switch_receipts_dir,
        "switch_intents_dir": switch_intents_dir,
        "latest_status_path": latest_status_path,
        "mirror_paths": {
            relative: publication_root / ROOT_MIRROR_RELATIVE_PATHS[relative]
            for relative in sorted(REQUIRED_BUNDLE_FILES)
        },
    }
    _validate_mirror_paths(
        publication_root=publication_root,
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


def _request_row_for_source(
    *,
    repo_root: Path,
    source: Mapping[str, object],
    attempt_rows: Mapping[str, Tuple[int, Mapping[str, str]]],
    validation_tier: str,
) -> Tuple[int, Dict[str, object]]:
    """Validate one consumed SourceReference against its tiered request.

    Args:
        repo_root: Repository containing the independent request audit chain.
        source: SourceReference consumed by the verified batch.
        attempt_rows: Deterministic attempt identities mapped to row metadata.
        validation_tier: Recorded or formal publication evidence tier.

    Returns:
        Ordered request-ledger row index and exact portable locator proof.

    Raises:
        PublicationError: When the attempt, joined source identity, or
            allowed body/header pair is absent, ambiguous, or inconsistent.
    """
    if validation_tier not in {
        FORMAL_VALIDATION_MODE,
        RECORDED_VALIDATION_MODE,
    }:
        raise PublicationError("Publication request locator tier is invalid")
    attempt_id = str(source["request_attempt_id"])
    if attempt_id not in attempt_rows:
        raise PublicationError(
            "Consumed SourceReference request ledger attempt is absent"
        )
    row_index, row = attempt_rows[attempt_id]
    raw_asset_id = str(source["raw_asset_id"])
    content_sha256 = raw_asset_id.split(":", maxsplit=1)[-1]
    source_url = str(source["source_url"])
    archive_accession = request_accession(source_url=source_url)
    expected_accession = (
        archive_accession if archive_accession else str(row["accession"])
    )
    if (
        row["method"] != "GET"
        or row["status_code"] != "200"
        or row["error"]
        or row["source_url"] != source_url
        or row["content_sha256"] != content_sha256
        or row["document_name"] != source["document_name"]
        or expected_accession not in {"", str(source["accession"])}
        or (
            archive_accession
            and row["accession"] != archive_accession
        )
    ):
        raise PublicationError(
            "Consumed SourceReference differs from request ledger attempt"
        )
    body_locator = str(row["repo_relative_path"])
    headers_locator = str(row["headers_repo_relative_path"])
    body_claims_attempt = body_locator.startswith(
        "evidence/request_attempts/"
    )
    headers_claims_attempt = headers_locator.startswith(
        "evidence/request_attempts/"
    )
    if body_claims_attempt != headers_claims_attempt:
        raise PublicationError(
            "Consumed request ledger locator pair is incomplete"
        )
    try:
        declared_body_path = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=body_locator,
        )
        declared_headers_path = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=headers_locator,
        )
    except (OSError, SourceError) as error:
        raise PublicationError(
            (
                "Consumed request ledger immutable attempt is invalid"
                if body_claims_attempt
                else "Consumed request ledger locator is invalid"
            )
        ) from error
    if body_claims_attempt:
        try:
            body_path, headers_path = legacy_response_snapshot_paths(
                workdir=repo_root,
                content_sha256=content_sha256,
                source_url=source_url,
                status_code=str(row["status_code"]),
                content_length=str(row["content_length"]),
                document_name=str(row["document_name"]),
                timestamp_utc=str(row["timestamp_utc"]),
            )
        except (OSError, ValueError) as error:
            raise PublicationError(
                "Consumed request ledger immutable attempt is invalid"
            ) from error
        # Deriving a valid sibling by hash must not hide a stale row locator.
        if (
            declared_body_path.resolve() != body_path.resolve()
            or declared_headers_path.resolve() != headers_path.resolve()
        ):
            raise PublicationError(
                "Consumed request ledger locator differs from immutable "
                "attempt"
            )
        locator_class = "IMMUTABLE_ATTEMPT"
    else:
        if validation_tier != RECORDED_VALIDATION_MODE:
            raise PublicationError(
                "LIVE_SOURCE_ATTEMPT_INCOMPLETE: formal publication "
                "requires an immutable request attempt"
            )
        locator_class = "LEGACY_WORKING_LOCATOR"
    try:
        body_bytes = declared_body_path.read_bytes()
        headers_bytes = declared_headers_path.read_bytes()
        content_length = int(row["content_length"])
    except (OSError, ValueError) as error:
        raise PublicationError(
            "Consumed request ledger locator bytes are invalid"
        ) from error
    if (
        len(body_bytes) != content_length
        or sha256_bytes(content=body_bytes) != content_sha256
        or not request_headers_bytes_match_identity(
            content=headers_bytes,
            content_sha256=content_sha256,
            source_url=source_url,
            status_code=str(row["status_code"]),
            content_length=str(row["content_length"]),
        )
    ):
        raise PublicationError(
            "Consumed request ledger locator bytes are invalid"
        )
    proof = {
        "body_sha256": sha256_bytes(content=body_bytes),
        "body_size": len(body_bytes),
        "headers_sha256": sha256_bytes(content=headers_bytes),
        "headers_size": len(headers_bytes),
        "ledger_row_index": int(row_index),
        "locator_class": locator_class,
        "original_body_locator": body_locator,
        "original_headers_locator": headers_locator,
        # The closure preserves repository-relative topology below its own
        # authority root. These are therefore executable portable locators,
        # not rewritten claims that resemble immutable HTTP attempts.
        "portable_body_locator": body_locator,
        "portable_headers_locator": headers_locator,
        "request_attempt_id": attempt_id,
        "source_reference_id": str(source["source_reference_id"]),
    }
    return int(row_index), proof


def _request_locator_provenance(
    *, validation_tier: str,
    source_proofs: object,
) -> Dict[str, object]:
    """Bind one evidence tier to every exact original locator and byte hash.

    Args:
        validation_tier: Recorded, formal, or opaque legacy-import tier.
        source_proofs: Ordered source-to-ledger locator proof array.

    Returns:
        Content-addressed provenance record used by manifest and replay.
    """
    if validation_tier not in REQUEST_LOCATOR_TIERS:
        raise PublicationError("Request locator provenance tier is invalid")
    if type(source_proofs) is not list or any(
        not isinstance(proof, dict)
        or set(proof) != REQUEST_LOCATOR_SOURCE_PROOF_FIELDS
        for proof in source_proofs
    ):
        raise PublicationError("Request locator source proofs are invalid")
    classes = sorted({str(proof["locator_class"]) for proof in source_proofs})
    if any(locator not in REQUEST_LOCATOR_CLASSES for locator in classes):
        raise PublicationError("Request locator class is invalid")
    body = {
        "record_type": "REQUEST_LOCATOR_PROVENANCE",
        "request_locator_classes": classes,
        "schema_version": 1,
        "source_proofs": list(source_proofs),
        "validation_tier": validation_tier,
    }
    return {
        **body,
        "request_locator_proof_id": content_hash(value=body),
    }


def _empty_legacy_ledger_binding() -> Dict[str, object]:
    """Return the explicit no-request binding for an opaque predecessor."""
    provenance = _request_locator_provenance(
        validation_tier=LEGACY_BASELINE_LOCATOR_TIER,
        source_proofs=[],
    )
    return {
        "request_locator_classes": [],
        "request_locator_proof_id": provenance[
            "request_locator_proof_id"
        ],
        "request_locator_tier": LEGACY_BASELINE_LOCATOR_TIER,
        "requests_log_prefix_sha256": sha256_bytes(content=b""),
        "row_count": 0,
        "source_reference_ids": [],
        "used_request_attempt_ids": [],
    }


def _publication_ledger_evidence(
    *, repo_root: Path, batch_manifest_path: Path,
    validation_tier: str,
    release_plan_root: Optional[Path] = None,
    run_loader: Optional[FrozenRunLoader] = None,
) -> Dict[str, object]:
    """Derive the exact request prefix and replayable locator provenance.

    Args:
        repo_root: Repository containing Batch and request authority.
        batch_manifest_path: Complete FROZEN Run collection.
        validation_tier: Recorded or formal publication tier.
        release_plan_root: Repository containing a named Issue #15 child plan.
        run_loader: Optional exact committed-Run validation boundary.

    Returns:
        A strict ledger binding plus its content-addressed source proofs.
    """
    if validation_tier not in {
        FORMAL_VALIDATION_MODE,
        RECORDED_VALIDATION_MODE,
    }:
        raise PublicationError("Publication request locator tier is invalid")
    try:
        log_path = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path="evidence/requests_log.csv",
        )
        manifest_path = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path="evidence/requests_log_manifest.json",
        )
        validate_request_log_manifest(log_path=log_path)
        log_bytes = log_path.read_bytes()
        log_text = log_bytes.decode("utf-8")
        manifest_bytes = manifest_path.read_bytes()
        rows = parse_request_log_rows(text=log_text)
        manifest = strict_json_loads(
            text=manifest_bytes.decode("utf-8")
        )
    except (OSError, SourceError, UnicodeDecodeError, ValueError) as error:
        raise PublicationError(
            "Publication request ledger is unavailable or invalid"
        ) from error
    expected_manifest = {
        "schema_version": REQUEST_LOG_MANIFEST_SCHEMA_VERSION,
        "row_count": len(rows),
        "content_sha256": sha256_bytes(content=log_bytes),
    }
    if type(manifest) is not dict or manifest != expected_manifest:
        raise PublicationError("Publication request ledger changed while read")
    attempt_rows = {}
    for row_index, row in enumerate(rows):
        attempt_id = request_log_attempt_id(
            row_index=row_index, row=row,
        )
        if attempt_id in attempt_rows:
            raise PublicationError(
                "Publication request ledger attempt identity is duplicated"
            )
        attempt_rows[attempt_id] = (row_index, row)
    try:
        sources = load_projection_used_source_references(
            repo_root=repo_root,
            batch_manifest_path=batch_manifest_path,
            release_plan_root=release_plan_root,
            run_loader=run_loader,
        )
    except ValueError as error:
        raise PublicationError(
            "Publication batch source membership is invalid"
        ) from error
    source_rows_and_proofs = [
        _request_row_for_source(
            repo_root=repo_root,
            source=source,
            attempt_rows=attempt_rows,
            validation_tier=validation_tier,
        )
        for source in sources
    ]
    used_attempt_rows = {
        (row_index, str(source["request_attempt_id"]))
        for source, (row_index, _proof) in zip(
            sources, source_rows_and_proofs
        )
    }
    source_proofs = [proof for _row_index, proof in source_rows_and_proofs]
    prefix_row_count = (
        max(row_index for row_index, _attempt_id in used_attempt_rows) + 1
        if used_attempt_rows
        else 0
    )
    try:
        prefix_bytes = request_log_prefix_bytes(
            text=log_text, row_count=prefix_row_count,
        )
    except ValueError as error:
        raise PublicationError(
            "Publication request ledger prefix is invalid"
        ) from error
    provenance = _request_locator_provenance(
        validation_tier=validation_tier,
        source_proofs=source_proofs,
    )
    binding = {
        "request_locator_classes": provenance["request_locator_classes"],
        "request_locator_proof_id": provenance[
            "request_locator_proof_id"
        ],
        "request_locator_tier": validation_tier,
        "requests_log_prefix_sha256": sha256_bytes(content=prefix_bytes),
        "row_count": prefix_row_count,
        "source_reference_ids": [
            str(source["source_reference_id"]) for source in sources
        ],
        "used_request_attempt_ids": [
            attempt_id
            for _row_index, attempt_id in sorted(used_attempt_rows)
        ],
    }
    return {"binding": binding, "provenance": provenance}


def publication_ledger_binding(
    *, repo_root: Path, batch_manifest_path: Path,
    validation_tier: str = FORMAL_VALIDATION_MODE,
    release_plan_root: Optional[Path] = None,
    run_loader: Optional[FrozenRunLoader] = None,
) -> Dict[str, object]:
    """Derive exact publication provenance from batch and request ledger.

    Args:
        repo_root: Repository containing the request audit chain.
        batch_manifest_path: Complete verified FROZEN Run collection.
        validation_tier: Explicit evidence tier; the generic default remains
            formal and therefore never accepts a legacy working locator.
        release_plan_root: Repository containing a named Issue #15 child plan.
        run_loader: Optional exact committed-Run validation boundary.

    Returns:
        Minimal ordered ledger prefix through the latest consumed row, plus
        the exact consumed SourceReference and request-attempt identities.

    Raises:
        PublicationError: When the ledger, membership, or immutable attempt
            evidence cannot be verified from persisted authority.
    """
    evidence = _publication_ledger_evidence(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        validation_tier=validation_tier,
        release_plan_root=release_plan_root,
        run_loader=run_loader,
    )
    return dict(evidence["binding"])


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
        or (
            CONTENT_ID_PATTERN
            if field in REQUIREMENT_CONTENT_HASH_FIELDS
            else SHA256_PATTERN
        ).fullmatch(requirement_hashes[field]) is None
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
        type(ledger_binding["request_locator_tier"]) is not str
        or ledger_binding["request_locator_tier"] not in REQUEST_LOCATOR_TIERS
        or type(ledger_binding["request_locator_proof_id"]) is not str
        or CONTENT_ID_PATTERN.fullmatch(
            ledger_binding["request_locator_proof_id"]
        ) is None
        or type(ledger_binding["request_locator_classes"]) is not list
        or ledger_binding["request_locator_classes"]
        != sorted(set(ledger_binding["request_locator_classes"]))
        or any(
            type(locator) is not str
            or locator not in REQUEST_LOCATOR_CLASSES
            for locator in ledger_binding["request_locator_classes"]
        )
        or (
            ledger_binding["request_locator_tier"]
            == FORMAL_VALIDATION_MODE
            and "LEGACY_WORKING_LOCATOR"
            in ledger_binding["request_locator_classes"]
        )
        or (
            ledger_binding["request_locator_tier"]
            == LEGACY_BASELINE_LOCATOR_TIER
            and ledger_binding != _empty_legacy_ledger_binding()
        )
        or (
            bool(ledger_binding["source_reference_ids"])
            != bool(ledger_binding["request_locator_classes"])
        )
        or type(ledger_binding["requests_log_prefix_sha256"]) is not str
        or SHA256_PATTERN.fullmatch(
            ledger_binding["requests_log_prefix_sha256"]
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


def _write_prepared_publication_bundle(
    *, publications_dir: Path, files: Mapping[str, bytes],
    requirement_hashes: Mapping[str, object], batch_manifest_id: str,
    projection_manifest_id: str, validation_receipt_id: str,
    ledger_binding: Mapping[str, object],
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Write one immutable bundle from already verified exact bytes.

    Args:
        publications_dir: Fixed immutable publication storage.
        files: Complete public and internal bundle-relative byte mapping.
        requirement_hashes: Verified Requirement authority hashes.
        batch_manifest_id: Verified or legacy-import-derived Batch identity.
        projection_manifest_id: Verified or legacy-derived projection identity.
        validation_receipt_id: Verified or legacy-derived validation identity.
        ledger_binding: Exact consumed request-ledger prefix binding.
        previous_publication_id: Prepared predecessor or ``None``.

    Returns:
        Strict content-addressed PublicationManifest.
    """
    _validate_publication_metadata(
        requirement_hashes=requirement_hashes,
        batch_manifest_id=batch_manifest_id,
        projection_manifest_id=projection_manifest_id,
        validation_receipt_id=validation_receipt_id,
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
    identity = {
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
        "publication_" + content_hash(value=identity).split(":", 1)[1]
    )
    manifest = {
        "record_type": "PUBLICATION_MANIFEST",
        "publication_id": publication_id,
        **identity,
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
        ordered_files = sorted(files)
        midpoint = max(1, len(ordered_files) // 2)
        for index, relative in enumerate(ordered_files, start=1):
            destination = temporary / _safe_relative(value=relative)
            atomic_write_bytes(path=destination, content=files[relative])
            if index == midpoint:
                _fault_injection_checkpoint(fault_point="MID_BUNDLE_WRITE")
        atomic_write_json(
            path=temporary / "publication_manifest.json", value=manifest,
        )
        verify_publication_bundle(bundle_dir=temporary)
        os.replace(str(temporary), str(final_dir))
        _fsync_directory(path=publications_dir)
    except (OSError, CanonicalError, PublicationError) as error:
        raise PublicationError("Publication bundle write failed") from error
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    verify_publication_bundle(bundle_dir=final_dir)
    return manifest


def _optional_legacy_source_file(
    *, legacy_root: Path, relative_path: str,
) -> Optional[bytes]:
    """Read one optional regular legacy-root file without following aliases.

    Args:
        legacy_root: Frozen compatibility-root snapshot.
        relative_path: Root-relative POSIX locator.

    Returns:
        Exact immutable source bytes, or ``None`` when the path is absent.
    """
    relative = _safe_relative(value=relative_path)
    path = legacy_root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise PublicationError("Legacy baseline source is unsafe")
    if not path.exists():
        return None
    if not path.is_file():
        raise PublicationError("Legacy baseline source is unsafe")
    return path.read_bytes()


def _read_legacy_source_file(
    *, legacy_root: Path, relative_path: str,
) -> bytes:
    """Require one exact regular legacy-root source file.

    Args:
        legacy_root: Frozen compatibility-root snapshot.
        relative_path: Root-relative POSIX locator.

    Returns:
        Exact immutable source bytes.
    """
    content = _optional_legacy_source_file(
        legacy_root=legacy_root, relative_path=relative_path,
    )
    if content is None:
        raise PublicationError("Legacy baseline source is incomplete")
    return content


def _legacy_import_metadata_bytes(
    *, relative_path: str, baseline_manifest_sha256: str,
    requirement_hashes: Mapping[str, object],
) -> bytes:
    """Render an honest placeholder for one absent vNext-only root artifact.

    Args:
        relative_path: One of three fixed metadata bundle roles.
        baseline_manifest_sha256: Frozen baseline authority digest.
        requirement_hashes: Current exact Requirement closure.

    Returns:
        Canonical JSON declaring data import rather than executed validation.
    """
    if relative_path not in LEGACY_SYNTHETIC_METADATA_FILES:
        raise PublicationError("Legacy synthetic metadata role is invalid")
    payload = {
        "schema_version": 1,
        "record_type": "LEGACY_BASELINE_IMPORT_ARTIFACT",
        "artifact_role": relative_path,
        "status": "IMPORTED_FROZEN_LEGACY_BASELINE",
        "baseline_manifest_sha256": baseline_manifest_sha256,
        "requirement_hashes": dict(requirement_hashes),
        "producer_execution": "NOT_RUN_DATA_IMPORT_ONLY",
    }
    return canonical_json_bytes(value=payload) + b"\n"


def _baseline_artifact_records(
    *, baseline: Mapping[str, object], legacy_root: Path,
    root_files: Mapping[str, bytes],
) -> tuple[Dict[str, object], Dict[str, bytes], Dict[str, object]]:
    """Validate baseline-owned bytes and build portable support records.

    Args:
        baseline: Verified Requirement baseline manifest.
        legacy_root: Frozen source containing baseline artifact locators.
        root_files: Exact 14 public bundle bytes keyed by bundle path.

    Returns:
        Normalized baseline records, internal support bytes, and support index.
    """
    if "artifact_digests" not in baseline or type(
        baseline["artifact_digests"]
    ) is not dict:
        raise PublicationError("Legacy baseline artifact map is invalid")
    artifacts = baseline["artifact_digests"]
    if not LEGACY_BASELINE_REQUIRED_ARTIFACTS.issubset(artifacts):
        raise PublicationError("Legacy baseline artifact proof is incomplete")
    root_to_bundle = {
        root_relative: bundle_relative
        for bundle_relative, root_relative
        in ROOT_MIRROR_RELATIVE_PATHS.items()
    }
    normalized = {}
    support_files = {}
    support_index = {}
    for source_relative in sorted(artifacts):
        record = artifacts[source_relative]
        if (
            type(source_relative) is not str
            or not isinstance(record, dict)
            or "sha256" not in record
            or "size" not in record
            or type(record["sha256"]) is not str
            or SHA256_PATTERN.fullmatch(record["sha256"]) is None
            or type(record["size"]) is not int
            or record["size"] < 0
        ):
            raise PublicationError("Legacy baseline artifact proof is invalid")
        if source_relative in root_to_bundle:
            content = root_files[root_to_bundle[source_relative]]
            bundle_path = root_to_bundle[source_relative]
        else:
            content = _read_legacy_source_file(
                legacy_root=legacy_root,
                relative_path=source_relative,
            )
            bundle_path = LEGACY_BASELINE_SUPPORT_PREFIX + source_relative
            _safe_relative(value=bundle_path)
            if bundle_path in support_files:
                raise PublicationError(
                    "Legacy baseline support path is duplicated"
                )
            support_files[bundle_path] = content
            support_index[source_relative] = {
                "bundle_path": bundle_path,
                "sha256": sha256_bytes(content=content),
                "size": len(content),
            }
        actual = {
            "sha256": sha256_bytes(content=content),
            "size": len(content),
        }
        expected = {
            "sha256": record["sha256"],
            "size": record["size"],
        }
        if actual != expected:
            raise PublicationError("Legacy baseline artifact bytes differ")
        normalized[source_relative] = expected
        if source_relative in root_to_bundle and bundle_path not in root_files:
            raise PublicationError("Legacy baseline root binding differs")
    return normalized, support_files, support_index


def _legacy_import_identity(
    *, legacy_baseline_import_id: str, role: str,
) -> str:
    """Derive one standard content identity from the legacy import proof.

    Args:
        legacy_baseline_import_id: Content-addressed strict import identity.
        role: Batch, projection, or validation namespace.

    Returns:
        Standard ``sha256:`` identity accepted by PublicationManifest.
    """
    return content_hash(
        value={
            "legacy_baseline_import_id": legacy_baseline_import_id,
            "role": role,
        }
    )


def prepare_legacy_baseline_predecessor(
    *, publication_root: Path, repo_root: Path, legacy_root: Path,
) -> Dict[str, object]:
    """Import frozen legacy root bytes as an immutable rollback predecessor.

    Args:
        publication_root: Formal immutable bundle storage root.
        repo_root: Requirement authority containing the frozen baseline.
        legacy_root: Root with frozen legacy compatibility artifacts and every
            additional artifact named by the baseline manifest. Only the three
            fixed vNext metadata roles may be absent and synthesized honestly.

    Returns:
        Prepared legacy PublicationManifest with no predecessor.

    This function only reads and hashes data. It never invokes a legacy
    producer, repair function, report generator, network request, or parser.
    """
    if legacy_root.is_symlink() or not legacy_root.is_dir():
        raise PublicationError("Legacy baseline root is unsafe")
    try:
        requirement = load_requirement_snapshot(
            snapshot_dir=(
                repo_root / "requirements" / "ai_first_v3_3_1"
            )
        )
    except (OSError, RequirementError, ValueError) as error:
        raise PublicationError(
            "Legacy baseline Requirement authority is invalid"
        ) from error
    baseline = requirement["baseline"]
    baseline_path = (
        repo_root
        / "requirements"
        / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    baseline_bytes = baseline_path.read_bytes()
    baseline_sha256 = sha256_bytes(content=baseline_bytes)
    root_files = {}
    root_origins = {}
    for bundle_relative, root_relative in sorted(
        ROOT_MIRROR_RELATIVE_PATHS.items()
    ):
        content = _optional_legacy_source_file(
            legacy_root=legacy_root,
            relative_path=root_relative,
        )
        if content is None:
            content = _legacy_import_metadata_bytes(
                relative_path=bundle_relative,
                baseline_manifest_sha256=baseline_sha256,
                requirement_hashes=requirement["hashes"],
            )
            root_origins[bundle_relative] = (
                "SYNTHESIZED_LEGACY_BASELINE_IMPORT"
            )
        else:
            root_origins[bundle_relative] = "FROZEN_ROOT_BYTES"
        root_files[bundle_relative] = content
    root_records = {
        relative: {
            "origin": root_origins[relative],
            "root_path": ROOT_MIRROR_RELATIVE_PATHS[relative],
            "sha256": sha256_bytes(content=root_files[relative]),
            "size": len(root_files[relative]),
        }
        for relative in sorted(root_files)
    }
    baseline_records, support_files, support_index = (
        _baseline_artifact_records(
            baseline=baseline,
            legacy_root=legacy_root,
            root_files=root_files,
        )
    )
    marker_body = {
        "schema_version": 1,
        "record_type": "LEGACY_BASELINE_IMPORT",
        "baseline_manifest_sha256": baseline_sha256,
        "baseline_repository_commit": baseline["repository_commit"],
        "requirement_hashes": dict(requirement["hashes"]),
        "root_artifacts": root_records,
        "baseline_artifacts": baseline_records,
        "supporting_artifacts": support_index,
    }
    import_id = content_hash(value=marker_body)
    marker = {
        **marker_body,
        "legacy_baseline_import_id": import_id,
    }
    files = {
        **root_files,
        **support_files,
        LEGACY_BASELINE_MANIFEST: baseline_bytes,
        LEGACY_BASELINE_IMPORT_MANIFEST: (
            canonical_json_bytes(value=marker) + b"\n"
        ),
    }
    empty_ledger = _empty_legacy_ledger_binding()
    layout = publication_layout(publication_root=publication_root)
    return _write_prepared_publication_bundle(
        publications_dir=Path(layout["publications_dir"]),
        files=files,
        requirement_hashes=requirement["hashes"],
        batch_manifest_id=_legacy_import_identity(
            legacy_baseline_import_id=import_id, role="BATCH",
        ),
        projection_manifest_id=_legacy_import_identity(
            legacy_baseline_import_id=import_id, role="PROJECTION",
        ),
        validation_receipt_id=_legacy_import_identity(
            legacy_baseline_import_id=import_id, role="VALIDATION",
        ),
        ledger_binding=empty_ledger,
        previous_publication_id=None,
    )


def prepare_issue15_legacy_baseline_predecessor(
    *, publication_root: Path, repo_root: Path, legacy_root: Path,
) -> Dict[str, object]:
    """Import the Issue #15 frozen root as the zero-AI predecessor.

    Args:
        publication_root: Formal immutable bundle storage root.
        repo_root: Repository containing Issue #15 and parent authorities.
        legacy_root: Root whose business bytes must match the Issue #15
            ``root_business_artifacts`` exact set.

    Returns:
        Prepared legacy PublicationManifest A with no predecessor.

    Why:
        The inherited parent baseline predates WB-1's refreshed terminal
        manifest/provenance bytes.  Issue #15 froze their exact successors, so
        its zero-AI ratchet must import that later verified root without
        rewriting the immutable parent snapshot.
    """
    if legacy_root.is_symlink() or not legacy_root.is_dir():
        raise PublicationError("Issue #15 legacy baseline root is unsafe")
    try:
        issue = load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements" / "issue_15_v1"
        )
        parent = load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1"
        )
    except (OSError, RequirementError, ValueError) as error:
        raise PublicationError(
            "Issue #15 legacy Requirement authority is invalid"
        ) from error
    issue_baseline = issue["baseline"]
    artifacts = issue_baseline["root_business_artifacts"]
    if not isinstance(artifacts, dict) or not (
        LEGACY_BASELINE_REQUIRED_ARTIFACTS.issubset(artifacts)
    ):
        raise PublicationError(
            "Issue #15 frozen root artifact proof is incomplete"
        )
    # A portable derived baseline makes the later WB-1 root explicit while
    # retaining the standard legacy-import verifier and rollback authority.
    baseline = {
        "schema_version": 1,
        "record_type": "ISSUE15_LEGACY_ROOT_BASELINE",
        "requirement_id": "issue_15_v1",
        "repository_commit": issue_baseline["repository_commit"],
        "requirement_closure_hash": issue["requirement_closure_hash"],
        "issue_requirement_hashes": issue["hashes"],
        "artifact_digests": artifacts,
    }
    baseline_bytes = canonical_json_bytes(value=baseline) + b"\n"
    baseline_sha256 = sha256_bytes(content=baseline_bytes)
    root_files = {}
    root_origins = {}
    for bundle_relative, root_relative in sorted(
        ROOT_MIRROR_RELATIVE_PATHS.items()
    ):
        content = _optional_legacy_source_file(
            legacy_root=legacy_root, relative_path=root_relative,
        )
        if content is None:
            content = _legacy_import_metadata_bytes(
                relative_path=bundle_relative,
                baseline_manifest_sha256=baseline_sha256,
                requirement_hashes=parent["hashes"],
            )
            root_origins[bundle_relative] = (
                "SYNTHESIZED_LEGACY_BASELINE_IMPORT"
            )
        else:
            root_origins[bundle_relative] = "FROZEN_ROOT_BYTES"
        root_files[bundle_relative] = content
    root_records = {
        relative: {
            "origin": root_origins[relative],
            "root_path": ROOT_MIRROR_RELATIVE_PATHS[relative],
            "sha256": sha256_bytes(content=root_files[relative]),
            "size": len(root_files[relative]),
        }
        for relative in sorted(root_files)
    }
    baseline_records, support_files, support_index = (
        _baseline_artifact_records(
            baseline=baseline,
            legacy_root=legacy_root,
            root_files=root_files,
        )
    )
    marker_body = {
        "schema_version": 1,
        "record_type": "LEGACY_BASELINE_IMPORT",
        "baseline_manifest_sha256": baseline_sha256,
        "baseline_repository_commit": baseline["repository_commit"],
        "requirement_hashes": dict(parent["hashes"]),
        "root_artifacts": root_records,
        "baseline_artifacts": baseline_records,
        "supporting_artifacts": support_index,
    }
    import_id = content_hash(value=marker_body)
    marker = {**marker_body, "legacy_baseline_import_id": import_id}
    files = {
        **root_files,
        **support_files,
        LEGACY_BASELINE_MANIFEST: baseline_bytes,
        LEGACY_BASELINE_IMPORT_MANIFEST: (
            canonical_json_bytes(value=marker) + b"\n"
        ),
    }
    layout = publication_layout(publication_root=publication_root)
    return _write_prepared_publication_bundle(
        publications_dir=Path(layout["publications_dir"]),
        files=files,
        requirement_hashes=parent["hashes"],
        batch_manifest_id=_legacy_import_identity(
            legacy_baseline_import_id=import_id, role="BATCH",
        ),
        projection_manifest_id=_legacy_import_identity(
            legacy_baseline_import_id=import_id, role="PROJECTION",
        ),
        validation_receipt_id=_legacy_import_identity(
            legacy_baseline_import_id=import_id, role="VALIDATION",
        ),
        ledger_binding=_empty_legacy_ledger_binding(),
        previous_publication_id=None,
    )


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


def _closure_file_record(*, path: str, content: bytes) -> Dict[str, object]:
    """Describe one immutable portable-closure file.

    Args:
        path: Normalized bundle-relative locator.
        content: Exact file bytes.

    Returns:
        Strict path, SHA-256, and byte-size mapping.
    """
    _safe_relative(value=path)
    if not path.startswith(INTERNAL_PREFIX):
        raise PublicationError("Closure file must use the internal namespace")
    return {
        "path": path,
        "sha256": sha256_bytes(content=content),
        "size": len(content),
    }


def _validated_run_documents(*, run_dir: Path) -> Tuple[
    Dict[str, object], list
]:
    """Read the exact Run manifest and record sequence used by closure copy.

    Args:
        run_dir: Already batch-verified FROZEN Run directory.

    Returns:
        Validated Run manifest and ordered validated record mappings.

    Raises:
        PublicationError: When persisted Run JSON is malformed or unsafe.
    """
    manifest_path = run_dir / "manifest.json"
    records_path = run_dir / "records.jsonl"
    try:
        manifest_payload = strict_json_file(path=manifest_path)
        if not isinstance(manifest_payload, dict):
            raise PublicationError("Closure Run manifest root is invalid")
        manifest = validate_record(record=manifest_payload)
        records_text = records_path.read_text(encoding="utf-8")
        lines = records_text.splitlines()
        if any(not line for line in lines):
            raise PublicationError("Closure Run records contain a blank line")
        records = []
        for line in lines:
            payload = strict_json_loads(text=line)
            if not isinstance(payload, dict):
                raise PublicationError("Closure Run record root is invalid")
            records.append(validate_record(record=payload))
    except (CanonicalError, OSError, UnicodeDecodeError, ValueError) as error:
        raise PublicationError("Closure Run documents are invalid") from error
    if manifest["status"] != "FROZEN":
        raise PublicationError("Closure accepts only FROZEN Runs")
    return manifest, records


def _portable_frozen_run_loader(
    run_dir: Path, repo_root: Path,
) -> Tuple[Dict[str, object], list, list]:
    """Use receipt-bound replay for catalog qualification Runs in a bundle."""
    try:
        manifest_payload = strict_json_file(path=run_dir / "manifest.json")
    except CanonicalError as error:
        raise RunStoreError("Portable Run manifest is invalid") from error
    if not isinstance(manifest_payload, dict):
        raise RunStoreError("Portable Run manifest is malformed")
    if "qualification_authorization" not in manifest_payload:
        return load_frozen_run(run_dir=run_dir, repo_root=repo_root)
    # Late import avoids a publication/ratchet module initialization cycle.
    from .ratchet_release import load_portable_qualification_run

    return load_portable_qualification_run(run_dir, repo_root)


def _copy_tree_into_closure(
    *, source_root: Path, destination_root: Path,
    files: Dict[str, bytes]
) -> None:
    """Copy one exact regular-file tree into the in-memory closure.

    Args:
        source_root: Verified source directory.
        destination_root: Bundle-relative destination root.
        files: Mutable output byte mapping.

    Expected output:
        Every source file is represented once; aliases and special entries
        fail before any publication directory is written.
    """
    if source_root.is_symlink() or not source_root.is_dir():
        raise PublicationError("Closure source tree is unsafe")
    for source in sorted(source_root.rglob("*")):
        if source.is_symlink():
            raise PublicationError("Closure source tree contains a symlink")
        if source.is_dir():
            continue
        if not source.is_file():
            raise PublicationError("Closure source tree entry is unsafe")
        relative = source.relative_to(source_root)
        destination = (destination_root / relative).as_posix()
        _safe_relative(value=destination)
        if destination in files:
            raise PublicationError("Closure destination is duplicated")
        files[destination] = source.read_bytes()


def _portable_closure_files(
    *, repo_root: Path, batch_manifest_path: Path,
    ledger_binding: Mapping[str, object],
    include_cutover_qualification: bool, validation_tier: str,
    release_plan_root: Optional[Path] = None,
    run_loader: Optional[FrozenRunLoader] = None,
    additional_authority_paths: Sequence[str] = (),
) -> Dict[str, bytes]:
    """Build one self-contained Batch/Run/repository authority closure.

    Args:
        repo_root: Repository carrying the exact Run-bound authority bytes.
        batch_manifest_path: Verified complete FROZEN BatchManifest.
        ledger_binding: Previously derived minimal consumed ledger prefix.
        include_cutover_qualification: Whether formal Cutover layout evidence
            must be verified and carried into the portable authority tree.
        validation_tier: Recorded or formal request-locator evidence tier.
        release_plan_root: Repository containing a named Issue #15 child plan.
        run_loader: Optional exact committed-Run validation boundary.
        additional_authority_paths: Extra repository authority files required
            to replay a child ratchet and its complete qualification evidence.

    Returns:
        Bundle-relative closure files, including its content-addressed index.

    Raises:
        PublicationError: When Batch, Run, Spec, source, or authority bytes
            cannot be copied through safe portable locators.
    """
    try:
        batch = load_projection_batch_manifest(
            repo_root=repo_root,
            batch_manifest_path=batch_manifest_path,
            release_plan_root=release_plan_root,
            run_loader=run_loader,
        )
    except (OSError, ProjectionError) as error:
        raise PublicationError(
            "Publication closure requires a verified BatchManifest"
        ) from error
    ledger_evidence = _publication_ledger_evidence(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        validation_tier=validation_tier,
        release_plan_root=release_plan_root,
        run_loader=run_loader,
    )
    if ledger_evidence["binding"] != ledger_binding:
        raise PublicationError("Closure request locator binding differs")
    locator_provenance = ledger_evidence["provenance"]
    files = {
        INTERNAL_BATCH_MANIFEST: batch_manifest_path.read_bytes(),
        INTERNAL_REQUEST_LOCATOR_PROVENANCE: (
            canonical_json_bytes(value=locator_provenance) + b"\n"
        ),
    }
    authority_paths = set(CLOSURE_AUTHORITY_FILES)
    authority_paths.update(str(value) for value in additional_authority_paths)
    qualification_binding = None
    if include_cutover_qualification:
        # Formal publication must remain independently auditable after the
        # mutable qualification workspace and original checkout disappear.
        try:
            qualification_binding = validate_cutover_qualifications(
                repo_root=repo_root,
            )
            authority_paths.update(
                qualification_closure_paths(repo_root=repo_root)
            )
        except (OSError, QualificationError) as error:
            raise PublicationError(
                "Formal qualification closure is unavailable"
            ) from error
    metric_root = repo_root / "catalog" / "metrics"
    if metric_root.is_symlink() or not metric_root.is_dir():
        raise PublicationError("Closure MetricSpec catalog is unsafe")
    metric_paths = sorted(metric_root.glob("*.md"))
    if not metric_paths:
        raise PublicationError("Closure MetricSpec catalog is empty")
    for metric_path in metric_paths:
        try:
            authority_paths.add(
                metric_path.relative_to(repo_root).as_posix()
            )
        except ValueError as error:
            raise PublicationError(
                "Closure MetricSpec path escapes repository"
            ) from error

    # Preserve the BatchManifest's relative Run topology so its exact bytes
    # remain authoritative after the original mutable workspace is removed.
    for binding in batch["runs"]:
        relative_run = str(binding["run_path"])
        run_dir = batch_manifest_path.parent / relative_run
        manifest, records = _validated_run_documents(run_dir=run_dir)
        for relative in manifest["spec_file_hashes"]:
            authority_paths.add(str(relative))
        for record in records:
            if record["record_type"] == "RAW_BLOB":
                authority_paths.add(str(record["storage_uri"]))
        _copy_tree_into_closure(
            source_root=run_dir,
            destination_root=(
                Path(INTERNAL_BATCH_MANIFEST).parent / relative_run
            ),
            files=files,
        )

    # Carry the exact minimal legal request prefix and exact locator bytes
    # consumed by this Batch. A recorded legacy locator keeps its honest class
    # and original path; it is never copied into the immutable-attempt tree.
    try:
        log_path = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path="evidence/requests_log.csv",
        )
        log_text = log_path.read_text(encoding="utf-8")
        prefix_bytes = request_log_prefix_bytes(
            text=log_text,
            row_count=int(ledger_binding["row_count"]),
        )
        prefix_rows = parse_request_log_rows(
            text=prefix_bytes.decode("utf-8")
        )
    except (
        OSError, SourceError, UnicodeDecodeError, ValueError,
        KeyError, TypeError,
    ) as error:
        raise PublicationError("Closure request ledger is invalid") from error
    used_attempt_ids = set(ledger_binding["used_request_attempt_ids"])
    copied_attempt_ids = set()
    for row_index, row in enumerate(prefix_rows):
        attempt_id = request_log_attempt_id(
            row_index=row_index,
            row=row,
        )
        if attempt_id not in used_attempt_ids:
            continue
        copied_attempt_ids.add(attempt_id)
    if copied_attempt_ids != used_attempt_ids:
        raise PublicationError("Closure consumed ledger attempts differ")
    for proof in locator_provenance["source_proofs"]:
        authority_paths.add(str(proof["original_body_locator"]))
        authority_paths.add(str(proof["original_headers_locator"]))
    ledger_destination = (
        Path(INTERNAL_AUTHORITY_ROOT) / "evidence/requests_log.csv"
    ).as_posix()
    ledger_manifest_destination = (
        Path(INTERNAL_AUTHORITY_ROOT)
        / "evidence/requests_log_manifest.json"
    ).as_posix()
    files[ledger_destination] = prefix_bytes
    files[ledger_manifest_destination] = canonical_json_bytes(
        value={
            "schema_version": REQUEST_LOG_MANIFEST_SCHEMA_VERSION,
            "row_count": len(prefix_rows),
            "content_sha256": sha256_bytes(content=prefix_bytes),
        }
    ) + b"\n"

    # Repository paths are copied under a private root rather than rewritten;
    # the existing Run verifier can therefore reapply Spec, Requirement,
    # traits, source, Review, Trace, and receipt invariants without host paths.
    for relative in sorted(authority_paths):
        try:
            source = resolve_repository_file(
                repo_root=repo_root,
                repo_relative_path=relative,
            )
        except (OSError, SourceError) as error:
            raise PublicationError(
                "Closure authority file is unsafe or missing"
            ) from error
        destination = (Path(INTERNAL_AUTHORITY_ROOT) / relative).as_posix()
        if destination in files:
            raise PublicationError("Closure authority path is duplicated")
        files[destination] = source.read_bytes()

    file_records = [
        _closure_file_record(path=path, content=files[path])
        for path in sorted(files)
    ]
    body = {
        "authority_root": INTERNAL_AUTHORITY_ROOT,
        "batch_manifest_id": batch["batch_manifest_id"],
        "batch_manifest_path": INTERNAL_BATCH_MANIFEST,
        "files": file_records,
        "ledger_binding": dict(ledger_binding),
        "qualification_binding": qualification_binding,
        "request_locator_provenance_id": locator_provenance[
            "request_locator_proof_id"
        ],
        "run_bindings": list(batch["runs"]),
    }
    closure = {
        **body,
        "schema_version": 3,
        "closure_id": content_hash(value=body),
    }
    files[INTERNAL_CLOSURE_MANIFEST] = (
        canonical_json_bytes(value=closure) + b"\n"
    )
    return files


def _verify_portable_closure(
    *, bundle_dir: Path, manifest: Mapping[str, object],
    projection: Mapping[str, object]
) -> None:
    """Reapply Batch and every FROZEN Run verifier inside one bundle.

    Args:
        bundle_dir: Immutable publication directory under verification.
        manifest: Parsed PublicationManifest binding every file byte.
        projection: Parsed ProjectionManifest binding the consumed Runs.

    Raises:
        PublicationError: On closure schema, byte set, portable locator,
            Batch identity, or deep Run replay drift.
    """
    closure_path = bundle_dir / INTERNAL_CLOSURE_MANIFEST
    try:
        payload = strict_json_file(path=closure_path)
    except CanonicalError as error:
        raise PublicationError(
            "Publication closure manifest is invalid"
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != CLOSURE_MANIFEST_FIELDS
    ):
        raise PublicationError("Publication closure fields are not exact")
    closure = dict(payload)
    body = {
        key: closure[key]
        for key in closure
        if key not in {"closure_id", "schema_version"}
    }
    if (
        closure["schema_version"] != 3
        or type(closure["closure_id"]) is not str
        or closure["closure_id"] != content_hash(value=body)
        or closure["authority_root"] != INTERNAL_AUTHORITY_ROOT
        or closure["batch_manifest_path"] != INTERNAL_BATCH_MANIFEST
        or closure["batch_manifest_id"] != manifest["batch_manifest_id"]
        or closure["ledger_binding"] != manifest["ledger_binding"]
        or closure["request_locator_provenance_id"]
        != manifest["ledger_binding"]["request_locator_proof_id"]
        or closure["run_bindings"] != projection["run_bindings"]
    ):
        raise PublicationError("Publication closure identity differs")
    records = closure["files"]
    if type(records) is not list or any(
        not isinstance(record, dict)
        or set(record) != {"path", "sha256", "size"}
        for record in records
    ):
        raise PublicationError(
            "Publication closure file records are invalid"
        )
    closure_paths = [str(record["path"]) for record in records]
    if (
        not closure_paths
        or len(closure_paths) != len(set(closure_paths))
        or closure_paths != sorted(closure_paths)
        or any(
            not path.startswith(INTERNAL_PREFIX)
            or path == INTERNAL_CLOSURE_MANIFEST
            for path in closure_paths
        )
    ):
        raise PublicationError("Publication closure file exact set differs")
    publication_records = {
        str(record["path"]): record for record in manifest["files"]
    }
    expected_paths = (
        set(REQUIRED_BUNDLE_FILES)
        | {INTERNAL_CLOSURE_MANIFEST}
        | set(closure_paths)
    )
    if set(publication_records) != expected_paths:
        raise PublicationError("Publication closure namespace differs")
    for record in records:
        path = str(record["path"])
        if publication_records[path] != record:
            raise PublicationError(
                "Publication closure digest binding differs"
            )

    authority_root = bundle_dir / INTERNAL_AUTHORITY_ROOT
    batch_path = bundle_dir / INTERNAL_BATCH_MANIFEST
    try:
        batch = load_projection_batch_manifest(
            repo_root=authority_root,
            batch_manifest_path=batch_path,
            release_plan_root=authority_root,
            run_loader=_portable_frozen_run_loader,
        )
    except (OSError, ProjectionError) as error:
        raise PublicationError(
            "Publication closure Batch/Run replay failed"
        ) from error
    if (
        batch["batch_manifest_id"] != manifest["batch_manifest_id"]
        or batch["runs"] != projection["run_bindings"]
    ):
        raise PublicationError("Publication closure Batch binding differs")
    try:
        locator_payload = strict_json_file(
            path=bundle_dir / INTERNAL_REQUEST_LOCATOR_PROVENANCE
        )
        if (
            not isinstance(locator_payload, dict)
            or set(locator_payload) != REQUEST_LOCATOR_PROVENANCE_FIELDS
        ):
            raise PublicationError(
                "Publication request locator provenance fields differ"
            )
        locator_provenance = _request_locator_provenance(
            validation_tier=str(locator_payload["validation_tier"]),
            source_proofs=locator_payload["source_proofs"],
        )
        if locator_provenance != locator_payload:
            raise PublicationError(
                "Publication request locator provenance identity differs"
            )
        portable_evidence = _publication_ledger_evidence(
            repo_root=authority_root,
            batch_manifest_path=batch_path,
            validation_tier=str(
                manifest["ledger_binding"]["request_locator_tier"]
            ),
            release_plan_root=authority_root,
            run_loader=_portable_frozen_run_loader,
        )
    except (CanonicalError, PublicationError) as error:
        raise PublicationError(
            "Publication closure ledger replay failed"
        ) from error
    if (
        locator_provenance != portable_evidence["provenance"]
        or portable_evidence["binding"] != manifest["ledger_binding"]
    ):
        raise PublicationError("Publication closure ledger binding differs")
    qualification_binding = closure["qualification_binding"]
    if qualification_binding is not None:
        try:
            portable_qualification = validate_cutover_qualifications(
                repo_root=authority_root,
            )
        except (OSError, QualificationError, ValueError) as error:
            raise PublicationError(
                "Publication closure qualification replay failed"
            ) from error
        if portable_qualification != qualification_binding:
            raise PublicationError(
                "Publication closure qualification binding differs"
            )


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
    *, metrics: list, projection: Mapping[str, object], validation_mode: str
) -> Dict[str, bytes]:
    """Render deterministic documentation for one validation tier.

    Args:
        metrics: Parsed full candidate matrix.
        projection: Strict ProjectionManifest for the same view.
        validation_mode: Recorded evidence or formal Cutover candidate mode.

    Returns:
        README and report bytes derived only from verified candidate data.

    Raises:
        PublicationError: When the validation tier is unknown.
    """
    if validation_mode not in {
        RECORDED_VALIDATION_MODE,
        FORMAL_VALIDATION_MODE,
    }:
        raise PublicationError("Publication documentation mode is invalid")
    formal = validation_mode == FORMAL_VALIDATION_MODE
    report_title = (
        "# vNext formal publication report"
        if formal
        else "# vNext recorded publication report"
    )
    boundary = (
        (
            "> Immutable PUBLISHABLE Cutover candidate; it is official only "
            "while the verified active pointer names this bundle."
        )
        if formal
        else (
            "> Recorded/shadow artifact; this is not active/full Cutover "
            "evidence."
        )
    )
    report_lines = [
        report_title,
        "",
        boundary,
        "",
        "- Batch: `{}`".format(projection["batch_manifest_id"]),
        "- Projection: `{}`".format(
            projection["projection_manifest_id"]
        ),
        "- run_id: `validation:{}`".format(
            projection["projection_manifest_id"]
        ),
        "- result: `{}`".format(
            FORMAL_VALIDATION_RESULT
            if formal
            else RECORDED_VALIDATION_RESULT
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
    if formal:
        report_lines.extend(
            [
                "",
                "## Active 与 latest",
                "",
                (
                    "- active publication 是当前正式可读版本；latest run "
                    "可以失败或未发布，两者不能混同。"
                ),
                (
                    "- OpenAI 只处理公开 SEC table-grid，不是 SEC evidence "
                    "source；HUMAN review 负责批准 hash-bound claims。"
                ),
                "",
                "<!-- validation-snapshot-provenance:start -->",
                "## Validation snapshot provenance",
                "",
                (
                    "- 报告存在或显示 GO，不单独证明当前 checkout 可验收。"
                ),
                (
                    "- 必须同时满足 terminal manifest 成功，且 "
                    "`python3 tools/check_validation_snapshot.py` 通过。"
                ),
                (
                    "- checker 验证 source-input tree、active pointer、"
                    "immutable bundle 与关键 artifact SHA-256/size。"
                ),
                "<!-- validation-snapshot-provenance:end -->",
            ]
        )
    readme_title = (
        "# vNext formal publication bundle"
        if formal
        else "# vNext recorded publication bundle"
    )
    readme_boundary = (
        (
            "- boundary: formal PUBLISHABLE bundle; active only when the "
            "verified pointer names this publication"
        )
        if formal
        else "- boundary: recorded/shadow only; full Cutover not proven"
    )
    readme_lines = [
        readme_title,
        "",
        "- batch_manifest_id: `{}`".format(
            projection["batch_manifest_id"]
        ),
        "- projection_manifest_id: `{}`".format(
            projection["projection_manifest_id"]
        ),
        "- rows: `{}`".format(len(metrics)),
        readme_boundary,
    ]
    if formal:
        readme_lines.extend(
            [
                "",
                "## 正式读取入口",
                "",
                (
                    "业务用户继续读取 root `outputs/metrics_matrix.csv`、"
                    "`outputs/metric_evidence.csv` 与根报告；内部读取必须先"
                    "打开并 pin `PublicationView`。"
                ),
                (
                    "root mirrors 不向未持有 PublicationView 的任意并发"
                    "读取者承诺组原子。"
                ),
                (
                    "rollback 只切换 active pointer 并恢复 mirrors，不会"
                    "重新启用 legacy parser，也不会回滚 SEC request ledger。"
                ),
                "",
                "## 验收",
                "",
                "```bash",
                "python3 scripts/12_validate_repair.py",
                "python3 tools/check_validation_snapshot.py",
                "```",
            ]
        )
    readme = "\n".join(
        [*readme_lines, ""]
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


def _verify_semantic_source_hashes(
    *, source_hashes: Mapping[str, object], repo_root: Path
) -> None:
    """Verify declared semantic-gate sources independently of the checker.

    Args:
        source_hashes: Portable source path to exact SHA-256 mapping.
        repo_root: Repository authority containing those source files.

    Raises:
        PublicationError: When a path is unsafe or current bytes differ.
    """
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise PublicationError("Semantic audit repository is unsafe")
    for relative in sorted(source_hashes):
        path = repo_root
        for part in _safe_relative(value=relative).parts:
            path = path / part
            if path.is_symlink():
                raise PublicationError(
                    "Semantic audit source binding is unsafe"
                )
        try:
            actual = sha256_file(path=path)
        except CanonicalError as error:
            raise PublicationError(
                "Semantic audit source binding is unsafe"
            ) from error
        if actual != source_hashes[relative]:
            raise PublicationError(
                "Semantic audit source binding differs"
            )


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
    if not SEMANTIC_GATE_SOURCE_PATHS.issubset(source_hashes):
        raise PublicationError("Semantic audit source binding is incomplete")
    if repo_root is not None:
        _verify_semantic_source_hashes(
            source_hashes=source_hashes, repo_root=repo_root,
        )
        if receipt != _execute_semantic_audit(repo_root=repo_root):
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


def _execute_scalability_audit(*, repo_root: Path) -> list:
    """Run the real company-literal gate and return its exact CSV rows.

    Args:
        repo_root: Repository containing the scanner and production sources.

    Returns:
        Exact scalability audit rows; a successful gate normally returns none.

    Raises:
        PublicationError: When the executable or scan result is unsafe.
    """
    tool_path = repo_root / "tools" / "check_no_company_literals.py"
    if tool_path.is_symlink() or not tool_path.is_file():
        raise PublicationError("Scalability audit executable is unsafe")
    try:
        with tempfile.TemporaryDirectory(
            prefix="sec-metrics-scalability-"
        ) as directory:
            output_path = Path(directory) / "scalability_audit.csv"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(tool_path),
                    "--output",
                    str(output_path),
                ],
                cwd=str(repo_root),
                check=False,
                capture_output=True,
                timeout=60,
            )
            if completed.returncode != 0:
                raise PublicationError(
                    "Scalability audit execution failed"
                )
            if output_path.is_symlink() or not output_path.is_file():
                raise PublicationError(
                    "Scalability audit execution produced no safe CSV"
                )
            rows = _csv_rows(
                content=output_path.read_bytes(),
                fieldnames=SCALABILITY_FIELDS,
                label="Scalability audit",
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PublicationError(
            "Scalability audit execution failed"
        ) from error
    if rows:
        raise PublicationError("Scalability audit execution failed")
    return rows


def _validate_legacy_migration_receipt(
    *, receipt: Mapping[str, object], projection: Mapping[str, object],
    repo_root: Optional[Path]
) -> None:
    """Validate compatibility cells and the exact legacy migration ledger.

    Args:
        receipt: Parsed legacy invariant migration receipt.
        projection: Strict ProjectionManifest for the same candidate.
        repo_root: Repository authority during prepare, or ``None`` on
            immutable bundle read-back.

    Raises:
        PublicationError: On malformed parity, incomplete inventory coverage,
            invalid status/proof, repository drift, or receipt identity drift.
    """
    required_fields = {
        "allowed_statuses", "batch_manifest_id",
        "evidence_reconciliations", "legacy_input_hashes",
        "legacy_baseline_commit", "legacy_baseline_source_files",
        "legacy_path_inventory_sha256", "metric_cells",
        "migration_entries", "receipt_id", "schema_version", "status",
    }
    if (
        set(receipt) != required_fields
        or receipt["schema_version"] != 2
        or receipt["status"] != "PASS"
        or receipt["batch_manifest_id"] != projection["batch_manifest_id"]
        or receipt["legacy_input_hashes"]
        != projection["legacy_input_hashes"]
        or receipt["legacy_path_inventory_sha256"]
        != projection["requirement_hashes"][
            "legacy_path_inventory_sha256"
        ]
        or type(receipt["legacy_baseline_commit"]) is not str
        or re.fullmatch(r"[0-9a-f]{40}", receipt["legacy_baseline_commit"])
        is None
        or not isinstance(receipt["legacy_baseline_source_files"], dict)
        or set(receipt["legacy_baseline_source_files"])
        != set(LEGACY_BASELINE_SOURCE_FILES)
        or any(
            type(receipt["legacy_baseline_source_files"][relative])
            is not str
            or SHA256_PATTERN.fullmatch(
                receipt["legacy_baseline_source_files"][relative]
            ) is None
            for relative in LEGACY_BASELINE_SOURCE_FILES
        )
        or receipt["allowed_statuses"] != list(LEGACY_MIGRATION_STATUSES)
        or type(receipt["evidence_reconciliations"]) is not list
        or type(receipt["metric_cells"]) is not list
        or type(receipt["migration_entries"]) is not list
        or not receipt["migration_entries"]
    ):
        raise PublicationError("Compatibility execution did not PASS")
    if any(
        type(row) is not dict
        or set(row) != {
            "comparisons", "exact_cells", "key", "method_cells", "status",
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
        for row in receipt["evidence_reconciliations"]
    ) or any(
        not isinstance(cell, dict)
        or "status" not in cell
        or cell["status"] not in {"PASS", "RECORDED"}
        for cell in receipt["metric_cells"]
    ):
        raise PublicationError("Compatibility execution did not PASS")
    entry_fields = {
        "entry_id", "inventory_field", "kind", "legacy_symbol",
        "proof_anchors", "proof_hash", "proof_mode", "proof_sources",
        "reason", "status",
    }
    entry_ids = []
    for entry in receipt["migration_entries"]:
        if (
            type(entry) is not dict
            or set(entry) != entry_fields
            or type(entry["entry_id"]) is not str
            or type(entry["inventory_field"]) is not str
            or type(entry["legacy_symbol"]) is not str
            or entry["entry_id"]
            != "{}:{}".format(
                entry["inventory_field"], entry["legacy_symbol"]
            )
            or entry["kind"] not in {"CONFIGURATION", "INVARIANT", "PRODUCER"}
            or entry["status"] not in LEGACY_MIGRATION_STATUSES
            or entry["proof_mode"] not in LEGACY_PROOF_MODES
            or LEGACY_PROOF_MODES[entry["proof_mode"]] != entry["status"]
            or type(entry["reason"]) is not str
            or not entry["reason"]
            or type(entry["proof_anchors"]) is not list
            or not entry["proof_anchors"]
            or len(entry["proof_anchors"]) != len(set(entry["proof_anchors"]))
            or type(entry["proof_sources"]) is not list
            or len(entry["proof_sources"]) != len(entry["proof_anchors"])
        ):
            raise PublicationError("Legacy migration ledger entry is invalid")
        for index, source in enumerate(entry["proof_sources"]):
            if (
                type(source) is not dict
                or set(source) != {"anchor", "source_sha256"}
                or source["anchor"] != entry["proof_anchors"][index]
                or type(source["source_sha256"]) is not str
                or SHA256_PATTERN.fullmatch(source["source_sha256"]) is None
            ):
                raise PublicationError(
                    "Legacy migration proof source is invalid"
                )
        proof_body = {
            key: entry[key] for key in entry if key != "proof_hash"
        }
        if entry["proof_hash"] != content_hash(value=proof_body):
            raise PublicationError("Legacy migration proof identity differs")
        entry_ids.append(entry["entry_id"])
    if len(entry_ids) != len(set(entry_ids)):
        raise PublicationError("Legacy migration ledger entry is duplicated")
    if repo_root is not None:
        try:
            inventory = load_legacy_path_inventory(repo_root=repo_root)
        except ValueError as error:
            raise PublicationError(
                "Legacy migration inventory cannot be verified"
            ) from error
        if receipt["migration_entries"] != inventory["migration_entries"]:
            raise PublicationError(
                "Legacy migration ledger differs from inventory"
            )
        if (
            receipt["legacy_baseline_commit"]
            != inventory["baseline_commit"]
            or receipt["legacy_baseline_source_files"]
            != inventory["source_files"]
        ):
            raise PublicationError(
                "Legacy migration baseline differs from inventory"
            )
    body = {
        key: receipt[key]
        for key in receipt
        if key not in {"receipt_id", "schema_version"}
    }
    if receipt["receipt_id"] != content_hash(value=body):
        raise PublicationError("Compatibility execution identity differs")


def _publication_gate_evidence(
    *, files: Mapping[str, bytes], projection: Mapping[str, object],
    repo_root: Optional[Path], ledger_binding: Mapping[str, object],
) -> Dict[str, object]:
    """Execute all publication checks against one exact candidate view.

    Args:
        files: Required candidate artifacts, with or without the final receipt.
        projection: Strict ProjectionManifest bound to those bytes.
        repo_root: Repository authority during preparation, or ``None`` during
            immutable read-back.
        ledger_binding: Tier, locator class, proof, and minimal prefix binding.

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
    _validate_legacy_migration_receipt(
        receipt=compatibility,
        projection=projection,
        repo_root=repo_root,
    )

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
    validation_modes = {
        RECORDED_VALIDATION_MODE: RECORDED_VALIDATION_RESULT,
        FORMAL_VALIDATION_MODE: FORMAL_VALIDATION_RESULT,
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
        or validation["mode"] not in validation_modes
        or validation["result"] != validation_modes[validation["mode"]]
        or validation["run_id"]
        != "validation:" + projection["projection_manifest_id"]
        or (
            validation["mode"] == RECORDED_VALIDATION_MODE
            and validation["source_commit"] != RECORDED_SOURCE_COMMIT
        )
        or (
            validation["mode"] == FORMAL_VALIDATION_MODE
            and re.fullmatch(
                r"[0-9a-f]{40}", validation["source_commit"]
            )
            is None
        )
        or set(validation["refreshed_artifacts"]) != required_refreshed
        or validation["not_refreshed_artifacts"] != []
    ):
        raise PublicationError("Repair validation execution did not PASS")
    try:
        parse_utc_timestamp(value=validation["started_at_utc"])
    except CanonicalError as error:
        raise PublicationError(
            "Publication validation timestamp is invalid"
        ) from error
    if (
        type(ledger_binding) is not dict
        or set(ledger_binding) != LEDGER_BINDING_FIELDS
        or validation["mode"] != ledger_binding["request_locator_tier"]
        or (
            validation["mode"] == FORMAL_VALIDATION_MODE
            and "LEGACY_WORKING_LOCATOR"
            in ledger_binding["request_locator_classes"]
        )
    ):
        raise PublicationError(
            "Publication request locator tier differs from validation"
        )

    scalability = _csv_rows(
        content=files["scalability_audit.csv"],
        fieldnames=SCALABILITY_FIELDS,
        label="Scalability audit",
    )
    if scalability:
        raise PublicationError("Scalability audit contains forbidden literals")
    if (
        repo_root is not None
        and scalability != _execute_scalability_audit(repo_root=repo_root)
    ):
        raise PublicationError("Scalability audit execution differs")

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
        metrics=metrics,
        projection=projection,
        validation_mode=str(validation["mode"]),
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
        "REQUEST_LOCATOR_TIER": {
            "locator_classes": list(
                ledger_binding["request_locator_classes"]
            ),
            "locator_proof_id": ledger_binding[
                "request_locator_proof_id"
            ],
            "validation_tier": ledger_binding["request_locator_tier"],
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
    validated_at_utc: str, validation_mode: str, source_commit: str
) -> Dict[str, object]:
    """Generate every non-Projector artifact from one verified candidate.

    Args:
        repo_root: Repository authority used by the semantic executable.
        staging_dir: Candidate root already containing Projector artifacts.
        context: Recomputed Projector staging context.
        validated_at_utc: Explicit UTC execution timestamp.
        validation_mode: Recorded or formal full-validation tier.
        source_commit: Sentinel for recorded mode or exact Git commit for full.

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
            "Publication validation timestamp is invalid"
        ) from error
    expected_results = {
        RECORDED_VALIDATION_MODE: RECORDED_VALIDATION_RESULT,
        FORMAL_VALIDATION_MODE: FORMAL_VALIDATION_RESULT,
    }
    if validation_mode not in expected_results:
        raise PublicationError("Publication validation mode is invalid")
    if (
        validation_mode == RECORDED_VALIDATION_MODE
        and source_commit != RECORDED_SOURCE_COMMIT
    ) or (
        validation_mode == FORMAL_VALIDATION_MODE
        and re.fullmatch(r"[0-9a-f]{40}", source_commit) is None
    ):
        raise PublicationError("Publication source commit is invalid")
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
    scalability = _execute_scalability_audit(repo_root=repo_root)
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
            rows=scalability, fieldnames=SCALABILITY_FIELDS,
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
                "source_commit": source_commit,
                "started_at_utc": validated_at_utc,
                "mode": validation_mode,
                "refreshed_artifacts": refreshed,
                "not_refreshed_artifacts": [],
                "result": expected_results[validation_mode],
            }
        ) + b"\n",
    }
    generated.update(
        _expected_documents(
            metrics=metrics,
            projection=projection,
            validation_mode=validation_mode,
        )
    )
    for relative in generated:
        _write_generated_artifact(
            path=staging_dir / relative,
            content=generated[relative],
            label=relative,
        )
    return projection


def _repository_source_commit(*, repo_root: Path) -> str:
    """Return the clean repository HEAD used by a formal publication.

    Args:
        repo_root: Repository whose runtime and Requirement bytes are used.

    Returns:
        Exact forty-character Git commit.

    Raises:
        PublicationError: When Git identity is unavailable or tracked bytes are
            dirty. Generated untracked staging is deliberately outside this
            authority check and is bound separately by the receipt.
    """
    try:
        snapshot = capture_source_snapshot(workdir=repo_root)
    except (OSError, ValidationProvenanceError) as error:
        raise PublicationError(
            "Formal publication source-input closure is unavailable"
        ) from error
    if (
        snapshot.source_commit is None
        or re.fullmatch(r"[0-9a-f]{40}", snapshot.source_commit) is None
    ):
        raise PublicationError("Formal publication Git HEAD is invalid")
    return snapshot.source_commit


def _write_publication_validation_receipt(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path,
    previous_publication_id: Optional[str], validated_at_utc: str,
    validation_mode: str, source_commit: str
) -> Dict[str, object]:
    """Execute one tier of publication gates and persist its receipt.

    Args:
        repo_root: Repository authority used by Projector and semantic audit.
        batch_manifest_path: Complete FROZEN Run collection.
        legacy_snapshot_dir: Legacy inputs named by ProjectionManifest.
        staging_dir: Exact candidate view without a validation receipt.
        previous_publication_id: Prepared predecessor identity.
        validated_at_utc: Explicit UTC gate execution timestamp.
        validation_mode: Recorded or formal validation tier.
        source_commit: Tier-appropriate exact source identity.

    Returns:
        Strict persisted ValidationReceipt.
    """
    ledger_binding = publication_ledger_binding(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        validation_tier=validation_mode,
    )
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
        validation_mode=validation_mode,
        source_commit=source_commit,
    )
    files = _read_staging_files(
        staging_dir=staging_dir, include_receipt=False,
    )
    gate_evidence = _publication_gate_evidence(
        files=files,
        projection=projection,
        repo_root=repo_root,
        ledger_binding=ledger_binding,
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


def write_publication_validation_receipt(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path,
    previous_publication_id: Optional[str], validated_at_utc: str
) -> Dict[str, object]:
    """Execute the offline recorded gates without authorizing Cutover.

    Args:
        repo_root: Repository authority used by Projector and semantic audit.
        batch_manifest_path: Complete FROZEN Run collection.
        legacy_snapshot_dir: Legacy inputs named by ProjectionManifest.
        staging_dir: Exact candidate view without a validation receipt.
        previous_publication_id: Prepared predecessor identity.
        validated_at_utc: Explicit UTC gate execution timestamp.

    Returns:
        Recorded-only content-bound ValidationReceipt.
    """
    return _write_publication_validation_receipt(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
        previous_publication_id=previous_publication_id,
        validated_at_utc=validated_at_utc,
        validation_mode=RECORDED_VALIDATION_MODE,
        source_commit=RECORDED_SOURCE_COMMIT,
    )


def _write_cutover_publication_validation_receipt(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path,
    previous_publication_id: Optional[str], validated_at_utc: str
) -> Dict[str, object]:
    """Execute formal pre-commit gates against one clean Git authority.

    Args:
        repo_root: Repository authority used by Projector and semantic audit.
        batch_manifest_path: Complete FROZEN Run collection.
        legacy_snapshot_dir: Legacy inputs named by ProjectionManifest.
        staging_dir: Exact candidate view without a validation receipt.
        previous_publication_id: Prepared predecessor identity.
        validated_at_utc: Explicit UTC gate execution timestamp.

    Returns:
        Content-bound receipt whose generated documents and terminal manifest
        are eligible for formal pointer commit.
    """
    # Qualification is repository-owned release authority. Validate it before
    # creating a receipt that could make this candidate pointer-eligible.
    validate_cutover_qualifications(repo_root=repo_root)
    return _write_publication_validation_receipt(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
        previous_publication_id=previous_publication_id,
        validated_at_utc=validated_at_utc,
        validation_mode=FORMAL_VALIDATION_MODE,
        source_commit=_repository_source_commit(repo_root=repo_root),
    )


def write_cutover_publication_validation_receipt(
    *, repo_root: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path,
    previous_publication_id: Optional[str], validated_at_utc: str
) -> Dict[str, object]:
    """Reject direct formal-receipt creation outside Cutover orchestration.

    Args:
        repo_root: Ignored caller repository candidate.
        batch_manifest_path: Ignored caller Batch candidate.
        legacy_snapshot_dir: Ignored caller compatibility input.
        staging_dir: Ignored caller staging directory.
        previous_publication_id: Ignored caller predecessor.
        validated_at_utc: Ignored caller validation time.

    Raises:
        PublicationError: Always. Formal receipt authority is held by the
            single Cutover orchestrator, not this compatibility tombstone.
    """
    del (
        repo_root, batch_manifest_path, legacy_snapshot_dir, staging_dir,
        previous_publication_id, validated_at_utc,
    )
    raise PublicationError("FORMAL_CUTOVER_AUTHORITY_REQUIRED")


def prepare_publication_bundle(
    *,
    publication_root: Path,
    repo_root: Path,
    batch_manifest_path: Path,
    legacy_snapshot_dir: Path,
    staging_dir: Path,
    previous_publication_id: Optional[str],
) -> Dict[str, object]:
    """Create and verify one immutable complete PUBLISHABLE bundle.

    Args:
        publication_root: Single root from which bundle storage is derived.
        repo_root: Repository containing Requirement and release authority.
        batch_manifest_path: Complete persisted FROZEN Run collection.
        legacy_snapshot_dir: Legacy inputs named by ProjectionManifest.
        staging_dir: Exact candidate artifact directory.
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
    validation_manifest = _json_mapping(
        content=files["validation_run_manifest.json"],
        label="Validation manifest",
    )
    validation_mode = str(validation_manifest["mode"])
    if validation_mode not in {
        FORMAL_VALIDATION_MODE,
        RECORDED_VALIDATION_MODE,
    }:
        raise PublicationError("Publication validation mode is invalid")
    ledger_binding = publication_ledger_binding(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        validation_tier=validation_mode,
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
            files=files,
            projection=projection,
            repo_root=repo_root,
            ledger_binding=ledger_binding,
        ),
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )
    closure_files = _portable_closure_files(
        repo_root=repo_root,
        batch_manifest_path=batch_manifest_path,
        ledger_binding=ledger_binding,
        include_cutover_qualification=(
            validation_mode == FORMAL_VALIDATION_MODE
        ),
        validation_tier=validation_mode,
    )
    if set(files).intersection(closure_files):
        raise PublicationError("Publication closure overlaps user artifacts")
    files.update(closure_files)
    return _write_prepared_publication_bundle(
        publications_dir=Path(publications_dir),
        files=files,
        requirement_hashes=requirement_hashes,
        batch_manifest_id=str(batch_manifest_id),
        projection_manifest_id=str(projection_manifest_id),
        validation_receipt_id=str(validation_receipt_id),
        ledger_binding=ledger_binding,
        previous_publication_id=previous_publication_id,
    )


def _verify_legacy_baseline_import(
    *, bundle_dir: Path, manifest: Mapping[str, object],
    internal_paths: set,
) -> None:
    """Verify one opaque legacy predecessor without running old producers.

    Args:
        bundle_dir: Immutable imported predecessor directory.
        manifest: Strict outer PublicationManifest.
        internal_paths: Exact internal paths declared by the outer manifest.

    Raises:
        PublicationError: On marker, baseline, strict hash, or identity drift.
    """
    try:
        marker_payload = strict_json_file(
            path=bundle_dir / LEGACY_BASELINE_IMPORT_MANIFEST
        )
        baseline_payload = strict_json_file(
            path=bundle_dir / LEGACY_BASELINE_MANIFEST
        )
    except CanonicalError as error:
        raise PublicationError(
            "Legacy baseline import metadata is invalid"
        ) from error
    if (
        not isinstance(marker_payload, dict)
        or set(marker_payload) != LEGACY_BASELINE_IMPORT_FIELDS
        or not isinstance(baseline_payload, dict)
    ):
        raise PublicationError("Legacy baseline import fields are not exact")
    marker = dict(marker_payload)
    body = {
        field: marker[field]
        for field in marker
        if field != "legacy_baseline_import_id"
    }
    import_id = marker["legacy_baseline_import_id"]
    if (
        marker["schema_version"] != 1
        or marker["record_type"] != "LEGACY_BASELINE_IMPORT"
        or type(import_id) is not str
        or CONTENT_ID_PATTERN.fullmatch(import_id) is None
        or import_id != content_hash(value=body)
        or marker["requirement_hashes"] != manifest["requirement_hashes"]
    ):
        raise PublicationError("Legacy baseline import identity differs")
    baseline_path = bundle_dir / LEGACY_BASELINE_MANIFEST
    if (
        marker["baseline_manifest_sha256"]
        != sha256_file(path=baseline_path)
        or marker["baseline_repository_commit"]
        != baseline_payload["repository_commit"]
        or type(marker["baseline_repository_commit"]) is not str
        or re.fullmatch(
            r"[0-9a-f]{40}", marker["baseline_repository_commit"]
        ) is None
    ):
        raise PublicationError("Legacy baseline manifest binding differs")
    baseline_artifacts = baseline_payload["artifact_digests"]
    if (
        type(baseline_artifacts) is not dict
        or not LEGACY_BASELINE_REQUIRED_ARTIFACTS.issubset(
            baseline_artifacts
        )
    ):
        raise PublicationError("Legacy baseline artifact proof is incomplete")
    normalized_baseline = {}
    for relative in sorted(baseline_artifacts):
        record = baseline_artifacts[relative]
        if (
            type(relative) is not str
            or not isinstance(record, dict)
            or "sha256" not in record
            or "size" not in record
            or type(record["sha256"]) is not str
            or SHA256_PATTERN.fullmatch(record["sha256"]) is None
            or type(record["size"]) is not int
            or record["size"] < 0
        ):
            raise PublicationError(
                "Legacy baseline artifact proof is invalid"
            )
        normalized_baseline[relative] = {
            "sha256": record["sha256"],
            "size": record["size"],
        }
    if marker["baseline_artifacts"] != normalized_baseline:
        raise PublicationError("Legacy baseline artifact index differs")
    root_artifacts = marker["root_artifacts"]
    if (
        type(root_artifacts) is not dict
        or set(root_artifacts) != REQUIRED_BUNDLE_FILES
    ):
        raise PublicationError("Legacy root artifact exact set differs")
    for relative in sorted(root_artifacts):
        record = root_artifacts[relative]
        path = bundle_dir / relative
        origin = (
            record["origin"] if isinstance(record, dict) and
            "origin" in record else None
        )
        if (
            not isinstance(record, dict)
            or set(record) != LEGACY_ROOT_ARTIFACT_FIELDS
            or origin not in {
                "FROZEN_ROOT_BYTES",
                "SYNTHESIZED_LEGACY_BASELINE_IMPORT",
            }
            or record["root_path"]
            != ROOT_MIRROR_RELATIVE_PATHS[relative]
            or record["sha256"] != sha256_file(path=path)
            or record["size"] != path.stat().st_size
        ):
            raise PublicationError("Legacy root artifact binding differs")
        if origin == "SYNTHESIZED_LEGACY_BASELINE_IMPORT" and (
            relative not in LEGACY_SYNTHETIC_METADATA_FILES
            or path.read_bytes() != _legacy_import_metadata_bytes(
                relative_path=relative,
                baseline_manifest_sha256=marker[
                    "baseline_manifest_sha256"
                ],
                requirement_hashes=manifest["requirement_hashes"],
            )
        ):
            raise PublicationError(
                "Legacy synthetic metadata binding differs"
            )
    root_to_bundle = {
        root_relative: bundle_relative
        for bundle_relative, root_relative
        in ROOT_MIRROR_RELATIVE_PATHS.items()
    }
    expected_support = {}
    for source_relative in sorted(normalized_baseline):
        baseline_record = normalized_baseline[source_relative]
        if source_relative in root_to_bundle:
            root_record = root_artifacts[
                root_to_bundle[source_relative]
            ]
            if {
                "sha256": root_record["sha256"],
                "size": root_record["size"],
            } != baseline_record:
                raise PublicationError(
                    "Legacy baseline public artifact differs"
                )
            continue
        bundle_path = LEGACY_BASELINE_SUPPORT_PREFIX + source_relative
        support_path = bundle_dir / _safe_relative(value=bundle_path)
        expected_support[source_relative] = {
            "bundle_path": bundle_path,
            "sha256": sha256_file(path=support_path),
            "size": support_path.stat().st_size,
        }
        if {
            "sha256": expected_support[source_relative]["sha256"],
            "size": expected_support[source_relative]["size"],
        } != baseline_record:
            raise PublicationError(
                "Legacy baseline support artifact differs"
            )
    supporting = marker["supporting_artifacts"]
    if type(supporting) is not dict or supporting != expected_support:
        raise PublicationError("Legacy baseline support index differs")
    if any(
        not isinstance(supporting[relative], dict)
        or set(supporting[relative]) != LEGACY_SUPPORT_ARTIFACT_FIELDS
        for relative in supporting
    ):
        raise PublicationError("Legacy baseline support fields differ")
    expected_internal = {
        LEGACY_BASELINE_IMPORT_MANIFEST,
        LEGACY_BASELINE_MANIFEST,
        *(
            record["bundle_path"]
            for record in supporting.values()
        ),
    }
    if internal_paths != expected_internal:
        raise PublicationError("Legacy baseline internal exact set differs")
    expected_ledger = _empty_legacy_ledger_binding()
    if (
        manifest["batch_manifest_id"]
        != _legacy_import_identity(
            legacy_baseline_import_id=import_id, role="BATCH",
        )
        or manifest["projection_manifest_id"]
        != _legacy_import_identity(
            legacy_baseline_import_id=import_id, role="PROJECTION",
        )
        or manifest["validation_receipt_id"]
        != _legacy_import_identity(
            legacy_baseline_import_id=import_id, role="VALIDATION",
        )
        or manifest["ledger_binding"] != expected_ledger
        or manifest["previous_publication_id"] is not None
    ):
        raise PublicationError("Legacy baseline outer binding differs")


def _verify_zero_ai_projection_closure(
    *, bundle_dir: Path, receipt: Mapping[str, object],
) -> None:
    """Verify schema-v2 full-field projection and retirement evidence."""
    try:
        projection = strict_json_file(
            path=bundle_dir / "internal/public_projection_closure.json"
        )
        retirement = strict_json_file(
            path=bundle_dir / "internal/retirement_receipt.json"
        )
    except CanonicalError as error:
        raise PublicationError("Zero-AI projection closure is invalid") from error
    if not isinstance(projection, dict) or not isinstance(retirement, dict):
        raise PublicationError("Zero-AI projection closure must be objects")
    projection_body = {
        field: projection[field]
        for field in projection if field != "projection_closure_id"
    }
    retirement_body = {
        field: retirement[field]
        for field in retirement if field != "retirement_receipt_id"
    }
    compatibility = projection["compatibility"]
    if not isinstance(compatibility, dict):
        raise PublicationError("Zero-AI compatibility closure is invalid")
    compatibility_body = {
        field: compatibility[field]
        for field in compatibility if field != "strict_compatibility_hash"
    }
    expected_keys = 18 if receipt["release_stage"] == "R1" else 141
    independence = retirement["projection_independence"]
    if not isinstance(independence, dict):
        raise PublicationError("Zero-AI projection independence is invalid")
    independence_body = {
        field: independence[field]
        for field in independence
        if field != "projection_independence_receipt_id"
    }
    if (
        projection["projection_closure_id"]
        != content_hash(value=projection_body)
        or projection["projection_closure_id"]
        != receipt["projection_closure_id"]
        or compatibility["strict_compatibility_hash"]
        != content_hash(value=compatibility_body)
        or compatibility["strict_compatibility_hash"]
        != receipt["strict_compatibility_hash"]
        or compatibility["compared_key_count"] != expected_keys
        or compatibility["compared_field_count"]
        != expected_keys * len(METRIC_FIELDS)
        or compatibility["compared_field_exact_set"] != list(METRIC_FIELDS)
        or compatibility["unexpected_delta_exact_set"]
        or compatibility["approved_delta_exact_set"]
        or retirement["retirement_receipt_id"]
        != content_hash(value=retirement_body)
        or retirement["projection_closure_id"]
        != projection["projection_closure_id"]
        or independence["status"] != "PASSED"
        or independence["projection_independence_receipt_id"]
        != content_hash(value=independence_body)
    ):
        raise PublicationError("Zero-AI projection evidence differs")
    if receipt["release_stage"] != "R2":
        return
    try:
        event = strict_json_file(
            path=bundle_dir / "internal/event_key_compatibility.json"
        )
        acquisition = strict_json_file(
            path=bundle_dir / "internal/acquisition_event_source_sets.json"
        )
    except CanonicalError as error:
        raise PublicationError("R2 event projection closure is invalid") from error
    if not isinstance(event, dict) or not isinstance(acquisition, dict):
        raise PublicationError("R2 event projection closure must be objects")
    event_body = {
        field: event[field]
        for field in event if field != "event_compatibility_receipt_id"
    }
    acquisition_body = {
        field: acquisition[field]
        for field in acquisition
        if field != "acquisition_source_set_closure_id"
    }
    if (
        event["event_compatibility_receipt_id"]
        != content_hash(value=event_body)
        or acquisition["acquisition_source_set_closure_id"]
        != content_hash(value=acquisition_body)
        or projection["event_compatibility_receipt_id"]
        != event["event_compatibility_receipt_id"]
        or projection["acquisition_source_set_closure_id"]
        != acquisition["acquisition_source_set_closure_id"]
        or len(event["comparisons"]) != 10
    ):
        raise PublicationError("R2 event projection evidence differs")


def _verify_zero_ai_formal_release(
    *, bundle_dir: Path, manifest: Mapping[str, object], internal_paths: set,
) -> None:
    """Verify one Issue #15 zero-AI formal bundle and immutable run closure.

    Args:
        bundle_dir: Immutable successor bundle directory.
        manifest: Verified outer PublicationManifest.
        internal_paths: Exact manifest-listed internal paths.

    Raises:
        PublicationError: On receipt, counter, key-set, run-file, authority,
            or outer-manifest drift.
    """
    try:
        payload = strict_json_file(path=bundle_dir / ZERO_AI_FORMAL_MANIFEST)
    except CanonicalError as error:
        raise PublicationError("Zero-AI formal receipt is invalid") from error
    if not isinstance(payload, dict):
        raise PublicationError("Zero-AI formal receipt must be an object")
    receipt = dict(payload)
    required = {
        "batch_manifest_id",
        "counters",
        "cumulative_metric_ids",
        "internal_files",
        "invocation_observation_id",
        "issue15_release_plan_content_id",
        "issue15_release_plan_id",
        "issue15_release_plan_sha256",
        "new_public_key_count",
        "previous_publication_id",
        "projection_manifest_id",
        "public_artifact_hashes",
        "public_key_set_hash",
        "public_matrix_row_count",
        "record_type",
        "release_input_plan_id",
        "release_stage",
        "replaced_legacy_row_count",
        "requirement_closure_hash",
        "result_coordinate_count",
        "schema_version",
        "source_commit",
        "source_locator_classes",
        "source_tree_oid",
        "status",
        "strict_compatibility_hash",
        "validation_receipt_id",
        "zero_ai_release_receipt_id",
    }
    if receipt["schema_version"] == 2:
        required.add("projection_closure_id")
    if receipt["schema_version"] not in {1, 2} or set(receipt) != required:
        raise PublicationError("Zero-AI formal receipt fields differ")
    body = {
        field: receipt[field]
        for field in receipt
        if field != "zero_ai_release_receipt_id"
    }
    if (
        receipt["record_type"] != "ZERO_AI_FORMAL_RELEASE_RECEIPT"
        or receipt["status"] != "PASSED"
        or receipt["release_stage"] not in {"R1", "R2"}
        or receipt["zero_ai_release_receipt_id"] != content_hash(value=body)
        or receipt["batch_manifest_id"] != manifest["batch_manifest_id"]
        or receipt["projection_manifest_id"]
        != manifest["projection_manifest_id"]
        or receipt["validation_receipt_id"]
        != manifest["validation_receipt_id"]
        or receipt["previous_publication_id"]
        != manifest["previous_publication_id"]
        or not isinstance(receipt["source_commit"], str)
        or SHA1_PATTERN.fullmatch(receipt["source_commit"]) is None
        or not isinstance(receipt["source_tree_oid"], str)
        or SHA1_PATTERN.fullmatch(receipt["source_tree_oid"]) is None
    ):
        raise PublicationError("Zero-AI formal receipt identity differs")
    invocation_path = bundle_dir / "internal/structured_only_invocation.json"
    release_plan_path = bundle_dir / "internal/issue15_release_plan.json"
    release_input_path = bundle_dir / "internal/release_input_plan.json"
    try:
        invocation = strict_json_file(path=invocation_path)
        release_plan = strict_json_file(path=release_plan_path)
        release_input = strict_json_file(path=release_input_path)
    except CanonicalError as error:
        raise PublicationError("Zero-AI authority closure is invalid") from error
    invocation_fields = {
        "counters",
        "invocation_observation_id",
        "observed_ai_invocation_plan_ids",
        "observed_invocation_files",
        "observed_provider_request_identities",
        "record_type",
        "release_input_plan_id",
        "result_coordinate_count",
        "schema_version",
        "source_mode_by_metric",
        "status",
    }
    if not isinstance(invocation, dict) or set(invocation) != invocation_fields:
        raise PublicationError("Zero-AI invocation closure fields differ")
    invocation_body = {
        field: invocation[field]
        for field in invocation
        if field != "invocation_observation_id"
    }
    namespaces = set(INVOCATION_STATE_NAMESPACES)
    if receipt["schema_version"] == 1:
        namespaces.remove("acceptances")
    observed_files = invocation["observed_invocation_files"]
    if (
        invocation["schema_version"] != 1
        or invocation["record_type"]
        != "STRUCTURED_ONLY_INVOCATION_RESULT"
        or invocation["status"] != "SUCCEEDED_ZERO_PROVIDER"
        or invocation["invocation_observation_id"]
        != content_hash(value=invocation_body)
        or invocation["invocation_observation_id"]
        != receipt["invocation_observation_id"]
        or invocation["release_input_plan_id"]
        != receipt["release_input_plan_id"]
        or invocation["result_coordinate_count"]
        != receipt["result_coordinate_count"]
        or not isinstance(observed_files, dict)
        or set(observed_files) != namespaces
        or any(observed_files[namespace] for namespace in namespaces)
        or invocation["observed_ai_invocation_plan_ids"]
        or invocation["observed_provider_request_identities"]
        or not isinstance(invocation["source_mode_by_metric"], dict)
        or set(invocation["source_mode_by_metric"])
        != set(receipt["cumulative_metric_ids"])
        or set(invocation["source_mode_by_metric"].values())
        != {"structured_only"}
    ):
        raise PublicationError("Zero-AI invocation closure differs")
    derived_counters = {
        "mock_transport_invocation_count": 0,
        "paid_model_provider_call_count": 0,
        "real_model_provider_egress_count": 0,
    }
    if (
        invocation["counters"] != derived_counters
        or receipt["counters"] != invocation["counters"]
    ):
        raise PublicationError("Zero-AI derived provider counters differ")
    if not isinstance(release_plan, dict) or not isinstance(release_input, dict):
        raise PublicationError("Zero-AI ReleasePlan closure is invalid")
    release_plan_body = {
        field: release_plan[field]
        for field in release_plan
        if field != "release_plan_content_id"
    }
    if (
        release_plan["release_plan_content_id"]
        != content_hash(value=release_plan_body)
        or release_plan["release_plan_id"]
        != receipt["issue15_release_plan_id"]
        or release_plan["release_plan_content_id"]
        != receipt["issue15_release_plan_content_id"]
        or sha256_file(path=release_plan_path)
        != receipt["issue15_release_plan_sha256"]
        or release_input["release_plan_id"]
        != release_plan["release_plan_id"]
        or release_input["release_plan_content_id"]
        != release_plan["release_plan_content_id"]
        or release_input["release_input_plan_id"]
        != receipt["release_input_plan_id"]
    ):
        raise PublicationError("Zero-AI ReleasePlan binding differs")
    expected_locator_classes = {
        "R1": ["IMMUTABLE_ATTEMPT"],
        "R2": ["IMMUTABLE_ATTEMPT", "IMMUTABLE_GIT_BLOB"],
    }
    if receipt["source_locator_classes"] != expected_locator_classes[
        str(receipt["release_stage"])
    ]:
        raise PublicationError("Zero-AI source locator class differs")
    if (
        not isinstance(receipt["cumulative_metric_ids"], list)
        or receipt["cumulative_metric_ids"]
        != sorted(set(receipt["cumulative_metric_ids"]))
        or type(receipt["result_coordinate_count"]) is not int
        or receipt["result_coordinate_count"]
        != 10 * len(receipt["cumulative_metric_ids"])
        or type(receipt["public_matrix_row_count"]) is not int
        or type(receipt["new_public_key_count"]) is not int
        or type(receipt["replaced_legacy_row_count"]) is not int
    ):
        raise PublicationError("Zero-AI release counts are invalid")
    internal_files = receipt["internal_files"]
    if not isinstance(internal_files, dict) or internal_paths != {
        ZERO_AI_FORMAL_MANIFEST, *internal_files,
    }:
        raise PublicationError("Zero-AI internal file exact set differs")
    for relative, binding in internal_files.items():
        if (
            not isinstance(binding, dict)
            or set(binding) != {"sha256", "size"}
        ):
            raise PublicationError("Zero-AI internal binding fields differ")
        path = bundle_dir / _safe_relative(value=relative)
        if (
            path.is_symlink()
            or not path.is_file()
            or binding["sha256"] != sha256_file(path=path)
            or binding["size"] != path.stat().st_size
        ):
            raise PublicationError("Zero-AI internal bytes differ")
    if receipt["schema_version"] == 2:
        _verify_zero_ai_projection_closure(
            bundle_dir=bundle_dir, receipt=receipt,
        )
    artifact_hashes = receipt["public_artifact_hashes"]
    if not isinstance(artifact_hashes, dict) or set(artifact_hashes) != (
        REQUIRED_BUNDLE_FILES
    ):
        raise PublicationError("Zero-AI public artifact set differs")
    for relative in REQUIRED_BUNDLE_FILES:
        path = bundle_dir / relative
        if artifact_hashes[relative] != sha256_file(path=path):
            raise PublicationError("Zero-AI public artifact hash differs")
    try:
        validation_run = strict_json_file(
            path=bundle_dir / "validation_run_manifest.json"
        )
    except CanonicalError as error:
        raise PublicationError("Zero-AI validation manifest is invalid") from error
    if (
        not isinstance(validation_run, dict)
        or validation_run["source_commit"] != receipt["source_commit"]
    ):
        raise PublicationError("Zero-AI source provenance differs")
    metrics_bytes = (bundle_dir / "metrics_matrix.csv").read_bytes()
    try:
        rows = list(csv.DictReader(io.StringIO(metrics_bytes.decode("utf-8"))))
    except UnicodeDecodeError as error:
        raise PublicationError("Zero-AI metrics matrix is not UTF-8") from error
    keys = sorted(
        (
            {"company": row["company"], "metric_id": row["metric_id"]}
            for row in rows
        ),
        key=lambda row: (row["company"], row["metric_id"]),
    )
    if (
        len(rows) != receipt["public_matrix_row_count"]
        or content_hash(value=keys) != receipt["public_key_set_hash"]
    ):
        raise PublicationError("Zero-AI public key set differs")


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
    public_paths = {
        path for path in expected_paths if not path.startswith(INTERNAL_PREFIX)
    }
    internal_paths = expected_paths - public_paths
    legacy_import = LEGACY_BASELINE_IMPORT_MANIFEST in internal_paths
    zero_ai_formal = ZERO_AI_FORMAL_MANIFEST in internal_paths
    if (
        public_paths != REQUIRED_BUNDLE_FILES
        or any(not path.startswith(INTERNAL_PREFIX) for path in internal_paths)
        or (
            not legacy_import
            and not zero_ai_formal
            and INTERNAL_CLOSURE_MANIFEST not in internal_paths
        )
    ):
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
    if legacy_import:
        _verify_legacy_baseline_import(
            bundle_dir=bundle_dir,
            manifest=manifest,
            internal_paths=internal_paths,
        )
        return manifest
    if zero_ai_formal:
        _verify_zero_ai_formal_release(
            bundle_dir=bundle_dir,
            manifest=manifest,
            internal_paths=internal_paths,
        )
        return manifest
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
            files=bundle_files,
            projection=projection,
            repo_root=None,
            ledger_binding=manifest["ledger_binding"],
        ),
        ledger_binding=manifest["ledger_binding"],
        previous_publication_id=manifest["previous_publication_id"],
    )
    _verify_portable_closure(
        bundle_dir=bundle_dir,
        manifest=manifest,
        projection=projection,
    )
    return manifest


def _validate_pointer_mapping(*, pointer: Mapping[str, object]) -> None:
    """Validate one in-memory active pointer without trusting its origin.

    Args:
        pointer: Candidate exact pointer mapping.

    Raises:
        PublicationError: When fields, identities, or timestamp differ.
    """
    if set(pointer) != POINTER_FIELDS:
        raise PublicationError("Active pointer fields are not exact")
    for key in (
        "publication_id",
        "bundle_manifest_sha256",
        "committed_at_utc",
    ):
        if not isinstance(pointer[key], str) or not pointer[key]:
            raise PublicationError("Active pointer field is empty")
    previous = pointer["previous_publication_id"]
    if previous is not None and (
        not isinstance(previous, str) or not previous
    ):
        raise PublicationError("Active pointer predecessor is invalid")
    if PUBLICATION_ID_PATTERN.fullmatch(str(pointer["publication_id"])) is None:
        raise PublicationError("Active publication identity is invalid")
    if (
        previous is not None
        and PUBLICATION_ID_PATTERN.fullmatch(previous) is None
    ):
        raise PublicationError("Active predecessor identity is invalid")
    if SHA256_PATTERN.fullmatch(
        str(pointer["bundle_manifest_sha256"])
    ) is None:
        raise PublicationError("Active manifest digest is invalid")
    _validate_utc_timestamp(value=str(pointer["committed_at_utc"]))


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
    _validate_pointer_mapping(pointer=parsed)
    return dict(parsed)


def _switch_receipts_dir(*, pointer_path: Path) -> Path:
    """Derive persistent switch-history storage from the fixed pointer path.

    Args:
        pointer_path: Root-derived active pointer path.

    Returns:
        Sibling content-addressed switch-receipt directory.
    """
    return pointer_path.parent / "publication_switch_receipts"


def _switch_intents_dir(*, pointer_path: Path) -> Path:
    """Derive the single-writer recovery journal from the fixed pointer.

    Args:
        pointer_path: Root-derived active pointer path.

    Returns:
        Sibling content-addressed switch-intent directory.
    """
    return pointer_path.parent / "publication_switch_intents"


def _validate_switch_mirror_state(*, state: object) -> None:
    """Require an exact pre-switch hash/size record for every root mirror.

    Args:
        state: Candidate mirror-state mapping from a switch intent.

    Raises:
        PublicationError: On missing paths, boolean sizes, or invalid hashes.
    """
    if not isinstance(state, dict) or set(state) != REQUIRED_BUNDLE_FILES:
        raise PublicationError("Publication switch mirror state differs")
    for record in state.values():
        if record is None:
            continue
        if (
            not isinstance(record, dict)
            or set(record) != SWITCH_INTENT_MIRROR_FIELDS
            or type(record["size"]) is not int
            or record["size"] < 0
            or type(record["sha256"]) is not str
            or SHA256_PATTERN.fullmatch(record["sha256"]) is None
        ):
            raise PublicationError(
                "Publication switch mirror state is invalid"
            )


def _load_switch_intent(
    *, pointer_path: Path
) -> Optional[Dict[str, object]]:
    """Load the sole content-addressed incomplete switch transaction.

    Args:
        pointer_path: Root-derived active pointer path.

    Returns:
        Exact pending intent, or ``None`` when no recovery is required.

    Raises:
        PublicationError: On multiple, unsafe, malformed, or tampered intents.
    """
    intent_dir = _switch_intents_dir(pointer_path=pointer_path)
    if not intent_dir.exists():
        return None
    if intent_dir.is_symlink() or not intent_dir.is_dir():
        raise PublicationError("Publication switch recovery intent is unsafe")
    paths = list(intent_dir.iterdir())
    if not paths:
        return None
    if len(paths) != 1:
        raise PublicationError(
            "Publication switch recovery intent is ambiguous"
        )
    path = paths[0]
    if path.is_symlink() or not path.is_file():
        raise PublicationError("Publication switch recovery intent is unsafe")
    try:
        payload = strict_json_file(
            path=path, allowed_fields=SWITCH_INTENT_FIELDS,
        )
    except CanonicalError as error:
        raise PublicationError(
            "Publication switch recovery intent is invalid"
        ) from error
    if not isinstance(payload, dict) or set(payload) != SWITCH_INTENT_FIELDS:
        raise PublicationError(
            "Publication switch recovery intent fields differ"
        )
    intent = dict(payload)
    previous_pointer = intent["previous_pointer"]
    proposed_pointer = intent["proposed_pointer"]
    if previous_pointer is not None:
        if not isinstance(previous_pointer, dict):
            raise PublicationError(
                "Publication switch prior pointer is invalid"
            )
        _validate_pointer_mapping(pointer=previous_pointer)
    if not isinstance(proposed_pointer, dict):
        raise PublicationError("Publication switch proposed pointer is invalid")
    _validate_pointer_mapping(pointer=proposed_pointer)
    _validate_switch_mirror_state(state=intent["previous_mirror_state"])
    previous_switch = intent["previous_switch_receipt_id"]
    body = {
        field: intent[field]
        for field in intent
        if field != "intent_id"
    }
    intent_id = intent["intent_id"]
    if (
        intent["schema_version"] != 1
        or intent["record_type"] != "PUBLICATION_SWITCH_INTENT"
        or intent["switch_mode"] not in {"COMMIT", "ROLLBACK"}
        or type(intent_id) is not str
        or CONTENT_ID_PATTERN.fullmatch(intent_id) is None
        or intent_id != content_hash(value=body)
        or path.name != "{}.json".format(intent_id.split(":", 1)[1])
        or (
            previous_switch is not None
            and (
                type(previous_switch) is not str
                or CONTENT_ID_PATTERN.fullmatch(previous_switch) is None
            )
        )
        or ((previous_pointer is None) != (previous_switch is None))
    ):
        raise PublicationError(
            "Publication switch recovery intent identity differs"
        )
    return intent


def _write_switch_intent(
    *, pointer_path: Path, previous_pointer: Optional[Mapping[str, object]],
    proposed_pointer: Mapping[str, object], switch_mode: str,
    previous_switch_receipt_id: Optional[str],
    previous_mirror_state: Mapping[str, object],
) -> Dict[str, object]:
    """Persist recovery authority before the first mirror mutation.

    Args:
        pointer_path: Root-derived active pointer path.
        previous_pointer: Exact pointer observed under the exclusive lock.
        proposed_pointer: Complete pointer that this transaction will commit.
        switch_mode: ``COMMIT`` or ``ROLLBACK``.
        previous_switch_receipt_id: Current immutable history tip.
        previous_mirror_state: Exact present/absent root mirror digest state.

    Returns:
        Content-addressed switch intent kept until commit or rollback closes.
    """
    _validate_switch_mirror_state(state=dict(previous_mirror_state))
    body = {
        "schema_version": 1,
        "record_type": "PUBLICATION_SWITCH_INTENT",
        "switch_mode": switch_mode,
        "previous_pointer": (
            dict(previous_pointer) if previous_pointer is not None else None
        ),
        "proposed_pointer": dict(proposed_pointer),
        "previous_switch_receipt_id": previous_switch_receipt_id,
        "previous_mirror_state": dict(previous_mirror_state),
    }
    intent = {**body, "intent_id": content_hash(value=body)}
    intent_dir = _switch_intents_dir(pointer_path=pointer_path)
    if intent_dir.is_symlink() or (
        intent_dir.exists() and not intent_dir.is_dir()
    ):
        raise PublicationError("Publication switch recovery intent is unsafe")
    intent_dir.mkdir(parents=True, exist_ok=True)
    if list(intent_dir.iterdir()):
        raise PublicationError("Publication switch recovery intent is pending")
    path = intent_dir / "{}.json".format(
        str(intent["intent_id"]).split(":", 1)[1]
    )
    atomic_write_bytes(
        path=path, content=canonical_json_bytes(value=intent) + b"\n",
    )
    return intent


def _remove_switch_intent(
    *, pointer_path: Path, intent: Mapping[str, object]
) -> None:
    """Remove only the exact transaction-owned intent after closure.

    Args:
        pointer_path: Root-derived active pointer path.
        intent: Previously content-verified intent mapping.

    Raises:
        PublicationError: When the journal changed before removal.
    """
    path = _switch_intents_dir(pointer_path=pointer_path) / "{}.json".format(
        str(intent["intent_id"]).split(":", 1)[1]
    )
    expected = canonical_json_bytes(value=dict(intent)) + b"\n"
    if (
        path.is_symlink()
        or not path.is_file()
        or path.read_bytes() != expected
    ):
        raise PublicationError("Publication switch recovery intent changed")
    path.unlink()


def _assert_no_pending_switch_intent(*, pointer_path: Path) -> None:
    """Keep every read-only consumer out of an incomplete transaction.

    Args:
        pointer_path: Root-derived active pointer path.

    Raises:
        PublicationError: Whenever a verified recovery intent remains.
    """
    if _load_switch_intent(pointer_path=pointer_path) is not None:
        raise PublicationError("Publication switch recovery intent is pending")


def _load_switch_receipts(
    *, switch_receipts_dir: Path
) -> Dict[str, Dict[str, object]]:
    """Load and content-verify every persisted publication switch edge.

    Args:
        switch_receipts_dir: Root-derived switch history directory.

    Returns:
        Switch receipt identity to exact mapping.

    Raises:
        PublicationError: On unsafe namespace, schema, hash, or chain values.
    """
    if switch_receipts_dir.is_symlink() or not switch_receipts_dir.is_dir():
        raise PublicationError("Committed publication switch history is missing")
    receipts: Dict[str, Dict[str, object]] = {}
    for path in sorted(switch_receipts_dir.iterdir()):
        # Atomic writers expose this exact hidden name only while fsyncing a
        # future receipt. It is not a committed history member and readers
        # must not turn normal concurrent preparation into a false failure.
        if SWITCH_TEMP_PATTERN.fullmatch(path.name) is not None:
            continue
        if path.is_symlink() or not path.is_file():
            raise PublicationError("Publication switch history is unsafe")
        try:
            payload = strict_json_file(
                path=path,
                allowed_fields=SWITCH_RECEIPT_FIELDS,
            )
        except CanonicalError as error:
            raise PublicationError(
                "Publication switch receipt is invalid"
            ) from error
        if not isinstance(payload, dict) or set(payload) != (
            SWITCH_RECEIPT_FIELDS
        ):
            raise PublicationError("Publication switch fields are not exact")
        receipt = dict(payload)
        pointer = receipt["pointer"]
        if not isinstance(pointer, dict):
            raise PublicationError("Publication switch pointer is invalid")
        _validate_pointer_mapping(pointer=pointer)
        previous_switch = receipt["previous_switch_receipt_id"]
        body = {
            field: receipt[field]
            for field in receipt
            if field != "switch_receipt_id"
        }
        switch_id = receipt["switch_receipt_id"]
        if (
            receipt["schema_version"] != 1
            or receipt["record_type"] != "PUBLICATION_SWITCH"
            or receipt["switch_mode"] not in {"COMMIT", "ROLLBACK"}
            or type(switch_id) is not str
            or CONTENT_ID_PATTERN.fullmatch(switch_id) is None
            or switch_id != content_hash(value=body)
            or path.name != "{}.json".format(switch_id.split(":", 1)[1])
            or (
                previous_switch is not None
                and (
                    type(previous_switch) is not str
                    or CONTENT_ID_PATTERN.fullmatch(previous_switch) is None
                )
            )
        ):
            raise PublicationError("Publication switch identity differs")
        if switch_id in receipts:
            raise PublicationError("Publication switch identity is duplicated")
        receipts[str(switch_id)] = receipt
    if not receipts:
        raise PublicationError("Committed publication switch history is empty")
    return receipts


def _switch_receipt_for_pointer(
    *, pointer_path: Path, pointer: Mapping[str, object]
) -> Dict[str, object]:
    """Prove one pointer and predecessor through an immutable switch chain.

    Args:
        pointer_path: Root-derived active pointer path.
        pointer: Already shape-validated pointer mapping.

    Returns:
        Unique committed switch edge whose pointer bytes match exactly.

    Raises:
        PublicationError: When no unique edge or linked predecessor exists.
    """
    receipts = _load_switch_receipts(
        switch_receipts_dir=_switch_receipts_dir(pointer_path=pointer_path)
    )
    predecessor_ids = {
        str(receipt["previous_switch_receipt_id"])
        for receipt in receipts.values()
        if receipt["previous_switch_receipt_id"] is not None
    }
    if not predecessor_ids.issubset(receipts):
        raise PublicationError(
            "Publication switch predecessor receipt is missing"
        )
    tip_ids = set(receipts) - predecessor_ids
    if len(tip_ids) != 1:
        raise PublicationError(
            "Publication switch history lacks one committed switch tip"
        )
    current = receipts[tip_ids.pop()]
    if current["pointer"] != dict(pointer):
        raise PublicationError(
            "Active pointer is not the committed switch history tip"
        )
    tip = current
    visited = set()
    while True:
        switch_id = str(current["switch_receipt_id"])
        if switch_id in visited:
            raise PublicationError("Publication switch history contains a cycle")
        visited.add(switch_id)
        current_pointer = current["pointer"]
        previous_publication = current_pointer["previous_publication_id"]
        previous_switch = current["previous_switch_receipt_id"]
        if previous_switch is None:
            if previous_publication is not None:
                raise PublicationError(
                    "Publication switch predecessor proof is missing"
                )
            break
        if previous_switch not in receipts:
            raise PublicationError(
                "Publication switch predecessor receipt is missing"
            )
        previous = receipts[str(previous_switch)]
        if previous["pointer"]["publication_id"] != previous_publication:
            raise PublicationError(
                "Publication switch predecessor identity differs"
            )
        current = previous
    if visited != set(receipts):
        raise PublicationError(
            "Publication switch history is not one committed chain"
        )
    return tip


def _write_switch_receipt(
    *, pointer_path: Path, pointer: Mapping[str, object], switch_mode: str,
    previous_switch_receipt_id: Optional[str]
) -> Dict[str, object]:
    """Persist one content-addressed edge after the pointer commit point.

    Args:
        pointer_path: Root-derived active pointer path. The caller holds its
            exclusive lock across pointer replacement and this write.
        pointer: Complete proposed pointer mapping.
        switch_mode: ``COMMIT`` or ``ROLLBACK``.
        previous_switch_receipt_id: Current committed edge, or ``None`` for the
            first pointer.

    Returns:
        Exact switch receipt mapping.

    Raises:
        PublicationError: On invalid values or divergent addressed reuse.
    """
    _validate_pointer_mapping(pointer=pointer)
    if switch_mode not in {"COMMIT", "ROLLBACK"}:
        raise PublicationError("Publication switch mode is invalid")
    if previous_switch_receipt_id is not None and (
        CONTENT_ID_PATTERN.fullmatch(previous_switch_receipt_id) is None
    ):
        raise PublicationError("Previous publication switch identity is invalid")
    body = {
        "schema_version": 1,
        "record_type": "PUBLICATION_SWITCH",
        "switch_mode": switch_mode,
        "previous_switch_receipt_id": previous_switch_receipt_id,
        "pointer": dict(pointer),
    }
    receipt = {**body, "switch_receipt_id": content_hash(value=body)}
    receipt_dir = _switch_receipts_dir(pointer_path=pointer_path)
    if receipt_dir.is_symlink() or (
        receipt_dir.exists() and not receipt_dir.is_dir()
    ):
        raise PublicationError("Publication switch history is unsafe")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / "{}.json".format(
        str(receipt["switch_receipt_id"]).split(":", 1)[1]
    )
    expected = canonical_json_bytes(value=receipt) + b"\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise PublicationError("Publication switch receipt is unsafe")
        if path.read_bytes() != expected:
            raise PublicationError("Publication switch receipt bytes differ")
    else:
        atomic_write_bytes(path=path, content=expected)
    return receipt


def _switch_receipt_from_intent(
    *, intent: Mapping[str, object]
) -> Dict[str, object]:
    """Derive the exact history edge owned by one pending intent.

    Args:
        intent: Content-verified switch intent.

    Returns:
        Exact content-addressed switch receipt mapping.
    """
    body = {
        "schema_version": 1,
        "record_type": "PUBLICATION_SWITCH",
        "switch_mode": intent["switch_mode"],
        "previous_switch_receipt_id": intent[
            "previous_switch_receipt_id"
        ],
        "pointer": dict(intent["proposed_pointer"]),
    }
    return {**body, "switch_receipt_id": content_hash(value=body)}


def _remove_intent_switch_receipt(
    *, pointer_path: Path, intent: Mapping[str, object]
) -> None:
    """Remove an exact post-pointer edge when recovery rolls back the intent.

    Args:
        pointer_path: Root-derived active pointer path.
        intent: Content-verified pending switch transaction.

    Raises:
        PublicationError: When the transaction-owned receipt bytes changed.
    """
    receipt = _switch_receipt_from_intent(intent=intent)
    path = _switch_receipts_dir(pointer_path=pointer_path) / "{}.json".format(
        str(receipt["switch_receipt_id"]).split(":", 1)[1]
    )
    if not path.exists():
        return
    expected = canonical_json_bytes(value=receipt) + b"\n"
    if (
        path.is_symlink()
        or not path.is_file()
        or path.read_bytes() != expected
    ):
        raise PublicationError("Publication switch receipt recovery differs")
    path.unlink()


def _sync_mirrors_from_bundle(
    *, bundle_dir: Path, mirror_paths: Mapping[str, Path]
) -> None:
    """Replace every root mirror from one already verified bundle.

    Args:
        bundle_dir: Immutable active or predecessor bundle.
        mirror_paths: Root-derived exact compatibility mirror mapping.

    Expected output:
        Every mirror byte equals its bundle source before recovery closes.
    """
    verify_publication_bundle(bundle_dir=bundle_dir)
    for relative, target in mirror_paths.items():
        source = bundle_dir / _safe_relative(value=relative)
        if source.is_symlink() or not source.is_file():
            raise PublicationError("Recovery mirror source is unavailable")
        if target.exists() and (target.is_symlink() or not target.is_file()):
            raise PublicationError("Recovery mirror target is unsafe")
        atomic_write_bytes(path=target, content=source.read_bytes())


def _restore_pre_switch_mirrors(
    *, publications_dir: Path, mirror_paths: Mapping[str, Path],
    intent: Mapping[str, object]
) -> None:
    """Reconstruct the exact pre-pointer mirror presence and bytes.

    Args:
        publications_dir: Root-derived immutable bundle parent.
        mirror_paths: Root-derived compatibility mirror mapping.
        intent: Content-verified switch intent with pre-switch digests.

    Raises:
        PublicationError: When no immutable bundle can reproduce prior bytes.
    """
    previous_pointer = intent["previous_pointer"]
    source_pointer = (
        previous_pointer
        if previous_pointer is not None
        else intent["proposed_pointer"]
    )
    bundle_dir = publications_dir / str(source_pointer["publication_id"])
    verify_publication_bundle(bundle_dir=bundle_dir)
    state = intent["previous_mirror_state"]
    for relative, target in mirror_paths.items():
        record = state[relative]
        if record is None:
            if target.exists():
                if target.is_symlink() or not target.is_file():
                    raise PublicationError("Recovery mirror target is unsafe")
                target.unlink()
            continue
        source = bundle_dir / _safe_relative(value=relative)
        if source.is_symlink() or not source.is_file():
            raise PublicationError("Recovery mirror source is unavailable")
        content = source.read_bytes()
        if (
            len(content) != record["size"]
            or sha256_bytes(content=content) != record["sha256"]
        ):
            raise PublicationError(
                "Recovery bundle cannot reproduce pre-switch mirrors"
            )
        if target.exists() and (target.is_symlink() or not target.is_file()):
            raise PublicationError("Recovery mirror target is unsafe")
        atomic_write_bytes(path=target, content=content)


def _recover_switch_intent_locked(
    *, publications_dir: Path, pointer_path: Path,
    mirror_paths: Mapping[str, Path]
) -> Optional[str]:
    """Complete or roll back one persisted switch under the exclusive lock.

    Args:
        publications_dir: Root-derived immutable bundle parent.
        pointer_path: Root-derived official pointer.
        mirror_paths: Root-derived compatibility mirrors.

    Returns:
        Recovered publication ID, or ``None`` when no intent existed.

    Raises:
        PublicationError: On tamper or a state outside previous/proposed bytes.

    Why:
        Pointer replacement is the commit point. A crash after it completes
        the history edge; a crash before it restores the prior mirror view.
    """
    intent = _load_switch_intent(pointer_path=pointer_path)
    if intent is None:
        return None
    previous_pointer = intent["previous_pointer"]
    proposed_pointer = intent["proposed_pointer"]
    current_pointer = _read_pointer(pointer_path=pointer_path)
    if current_pointer == proposed_pointer:
        bundle_dir = publications_dir / str(
            proposed_pointer["publication_id"]
        )
        manifest = verify_publication_bundle(bundle_dir=bundle_dir)
        manifest_hash = sha256_file(
            path=bundle_dir / "publication_manifest.json"
        )
        if manifest_hash != proposed_pointer["bundle_manifest_sha256"]:
            raise PublicationError(
                "Pending switch pointer manifest hash differs"
            )
        _write_switch_receipt(
            pointer_path=pointer_path,
            pointer=proposed_pointer,
            switch_mode=str(intent["switch_mode"]),
            previous_switch_receipt_id=intent[
                "previous_switch_receipt_id"
            ],
        )
        _switch_receipt_for_pointer(
            pointer_path=pointer_path, pointer=proposed_pointer,
        )
        _sync_mirrors_from_bundle(
            bundle_dir=bundle_dir, mirror_paths=mirror_paths,
        )
        _remove_switch_intent(pointer_path=pointer_path, intent=intent)
        return str(manifest["publication_id"])
    if current_pointer != previous_pointer:
        raise PublicationError(
            "Pending switch pointer is neither previous nor proposed"
        )
    _remove_intent_switch_receipt(
        pointer_path=pointer_path, intent=intent,
    )
    if previous_pointer is not None:
        _switch_receipt_for_pointer(
            pointer_path=pointer_path, pointer=previous_pointer,
        )
    _restore_pre_switch_mirrors(
        publications_dir=publications_dir,
        mirror_paths=mirror_paths,
        intent=intent,
    )
    _remove_switch_intent(pointer_path=pointer_path, intent=intent)
    return (
        str(previous_pointer["publication_id"])
        if previous_pointer is not None
        else None
    )


def _validate_mirror_paths(
    *,
    publication_root: Path,
    publications_dir: Path,
    pointer_path: Path,
    latest_status_path: Path,
    mirror_paths: Mapping[str, Path],
) -> None:
    """Require distinct mirror destinations outside authority storage.

    Args:
        publication_root: Repository root owning formal output locations.
        publications_dir: Immutable bundle parent.
        pointer_path: Unique active pointer.
        latest_status_path: Latest-run status authority path.
        mirror_paths: Required bundle-relative path to compatibility path.

    Raises:
        PublicationError: On an incomplete, aliased, or authoritative target.
    """
    if set(mirror_paths) != REQUIRED_BUNDLE_FILES:
        raise PublicationError("Compatibility mirror exact set differs")
    expected_mirrors = {
        relative: publication_root / ROOT_MIRROR_RELATIVE_PATHS[relative]
        for relative in REQUIRED_BUNDLE_FILES
    }
    if dict(mirror_paths) != expected_mirrors:
        raise PublicationError("Compatibility mirror mapping differs")
    resolved = [path.resolve(strict=False) for path in mirror_paths.values()]
    if len(resolved) != len(set(resolved)):
        raise PublicationError("Compatibility mirrors must be distinct")
    publication_storage = publications_dir.resolve(strict=False)
    pointer = pointer_path.resolve(strict=False)
    lock = pointer_path.with_suffix(
        pointer_path.suffix + ".lock"
    ).resolve(strict=False)
    latest_status = latest_status_path.resolve(strict=False)
    if (
        pointer == publication_storage
        or publication_storage in pointer.parents
    ):
        raise PublicationError(
            "Active pointer overlaps publication storage"
        )
    canonical_status = (
        publication_root / "artifacts" / "vnext" / LATEST_STATUS_FILENAME
    ).resolve(strict=False)
    if latest_status != canonical_status:
        raise PublicationError("Latest status path is not canonical")
    if (
        latest_status in {pointer, lock, publication_storage}
        or publication_storage in latest_status.parents
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
            target.relative_to(publication_storage)
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


def _publication_commit_authority(*, bundle_dir: Path) -> str:
    """Classify one verified bundle's only legal forward-commit authority.

    Args:
        bundle_dir: Already verified immutable bundle directory.

    Returns:
        ``FORMAL``, ``RECORDED``, or ``LEGACY_BASELINE``.
    """
    if (bundle_dir / LEGACY_BASELINE_IMPORT_MANIFEST).is_file():
        return LEGACY_COMMIT_AUTHORITY
    if (bundle_dir / ZERO_AI_FORMAL_MANIFEST).is_file():
        manifest = verify_publication_bundle(bundle_dir=bundle_dir)
        if manifest["previous_publication_id"] is None:
            raise PublicationError(
                "Zero-AI formal successor requires a predecessor"
            )
        return FORMAL_COMMIT_AUTHORITY
    try:
        validation = strict_json_file(
            path=bundle_dir / "validation_run_manifest.json"
        )
        receipt = strict_json_file(
            path=bundle_dir / "publication_validation_receipt.json"
        )
        closure = strict_json_file(
            path=bundle_dir / INTERNAL_CLOSURE_MANIFEST
        )
    except CanonicalError as error:
        raise PublicationError(
            "Publication commit authority is invalid"
        ) from error
    if (
        not isinstance(validation, dict)
        or not isinstance(receipt, dict)
        or not isinstance(closure, dict)
    ):
        raise PublicationError("Publication commit authority is invalid")
    authority = {
        (FORMAL_VALIDATION_MODE, FORMAL_VALIDATION_RESULT): (
            FORMAL_COMMIT_AUTHORITY
        ),
        (RECORDED_VALIDATION_MODE, RECORDED_VALIDATION_RESULT): (
            RECORDED_COMMIT_AUTHORITY
        ),
    }
    key = (validation["mode"], validation["result"])
    if key not in authority:
        raise PublicationError("Publication commit authority is invalid")
    ledger_binding = closure["ledger_binding"]
    if (
        not isinstance(ledger_binding, dict)
        or ledger_binding["request_locator_tier"] != validation["mode"]
        or (
            validation["mode"] == FORMAL_VALIDATION_MODE
            and "LEGACY_WORKING_LOCATOR"
            in ledger_binding["request_locator_classes"]
        )
    ):
        raise PublicationError(
            "Publication commit request locator authority is invalid"
        )
    if key == (FORMAL_VALIDATION_MODE, FORMAL_VALIDATION_RESULT) and (
        receipt["status"] != FORMAL_VALIDATION_RESULT
        or closure["qualification_binding"] is None
    ):
        raise PublicationError(
            "Formal publication qualification authority is absent"
        )
    return authority[key]


def _require_formal_forward_commit(*, authority: str) -> None:
    """Reject every non-formal bundle at the public forward-commit boundary.

    Args:
        authority: Classification returned from immutable bundle bytes.

    Raises:
        PublicationError: Recorded and legacy-import bundles need different
            workflows and can never use ordinary forward commit.
    """
    if authority == RECORDED_COMMIT_AUTHORITY:
        raise PublicationError(
            "recorded-only publication cannot become active"
        )
    if authority == LEGACY_COMMIT_AUTHORITY:
        raise PublicationError(
            "legacy baseline publication requires initial chain commit"
        )
    if authority != FORMAL_COMMIT_AUTHORITY:
        raise PublicationError("Publication commit authority is invalid")


def _require_existing_active_for_forward_commit(
    *, pointer_path: Path,
) -> None:
    """Require ordinary forward commits to extend a committed chain.

    Args:
        pointer_path: Unique active publication commit point.

    Raises:
        PublicationError: When no active predecessor exists and the caller
            attempts to bypass the atomic initial legacy-to-vNext chain.
    """
    if _read_pointer(pointer_path=pointer_path) is None:
        raise PublicationError(
            "first formal publication requires initial publication chain"
        )


def _switch_publication_locked(
    *,
    publications_dir: Path,
    pointer_path: Path,
    bundle_dir: Path,
    manifest: Mapping[str, object],
    publication_id: str,
    expected_previous_publication_id: Optional[str],
    committed_at_utc: str,
    mirror_paths: Mapping[str, Path],
    switch_mode: str,
) -> Dict[str, object]:
    """Switch one verified bundle while the caller holds the pointer lock.

    Args:
        publications_dir: Bundle parent.
        pointer_path: Unique active commit point.
        bundle_dir: Verified immutable bundle directory.
        manifest: Verified PublicationManifest.
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
    previous_pointer = _read_pointer(pointer_path=pointer_path)
    previous_switch = (
        _switch_receipt_for_pointer(
            pointer_path=pointer_path,
            pointer=previous_pointer,
        )
        if previous_pointer is not None
        else None
    )
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
    manifest_bytes = (bundle_dir / "publication_manifest.json").read_bytes()
    pointer = {
        "publication_id": publication_id,
        "bundle_manifest_sha256": sha256_bytes(content=manifest_bytes),
        "previous_publication_id": current_id,
        "committed_at_utc": committed_at_utc,
    }
    snapshots: Dict[Path, Optional[bytes]] = {}
    previous_mirror_state: Dict[str, object] = {}
    ordered_mirrors = list(mirror_paths)
    for relative in ordered_mirrors:
        source = bundle_dir / _safe_relative(value=relative)
        if not source.is_file() or source.is_symlink():
            raise PublicationError("Mirror source is unavailable")
        target = mirror_paths[relative]
        if target.exists() and (
            target.is_symlink() or not target.is_file()
        ):
            raise PublicationError("Mirror target is unsafe")
        content = target.read_bytes() if target.exists() else None
        snapshots[target] = content
        previous_mirror_state[relative] = (
            {
                "sha256": sha256_bytes(content=content),
                "size": len(content),
            }
            if content is not None
            else None
        )
    intent = _write_switch_intent(
        pointer_path=pointer_path,
        previous_pointer=previous_pointer,
        proposed_pointer=pointer,
        switch_mode=switch_mode,
        previous_switch_receipt_id=(
            str(previous_switch["switch_receipt_id"])
            if previous_switch is not None
            else None
        ),
        previous_mirror_state=previous_mirror_state,
    )
    switch_receipt: Optional[Dict[str, object]] = None
    try:
        midpoint = max(1, len(ordered_mirrors) // 2)
        for index, relative in enumerate(ordered_mirrors, start=1):
            atomic_write_bytes(
                path=mirror_paths[relative],
                content=(bundle_dir / relative).read_bytes(),
            )
            if sha256_file(path=mirror_paths[relative]) != sha256_file(
                path=bundle_dir / relative
            ):
                raise PublicationError("Compatibility mirror hash differs")
            if index == midpoint:
                _fault_injection_checkpoint(fault_point="MID_MIRROR_WRITE")
        # The pointer is the unique official commit point; fixed-root mirrors
        # are prepared first and recovered from the pointer after a crash.
        _fault_injection_checkpoint(
            fault_point="MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT"
        )
        atomic_write_json(path=pointer_path, value=pointer)
        _fault_injection_checkpoint(
            fault_point="POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT"
        )
        # The pointer is the unique commit point. Persisting its history edge
        # beforehand would let a pre-pointer crash leave an orphan that later
        # pointer tamper could misrepresent as committed.
        switch_receipt = _write_switch_receipt(
            pointer_path=pointer_path,
            pointer=pointer,
            switch_mode=switch_mode,
            previous_switch_receipt_id=(
                str(previous_switch["switch_receipt_id"])
                if previous_switch is not None
                else None
            ),
        )
        opened = PublicationView._open_paths(
            publications_dir=publications_dir, pointer_path=pointer_path,
        )
        if opened.publication_id != publication_id:
            raise PublicationError("Active pointer postcondition failed")
        _remove_switch_intent(
            pointer_path=pointer_path, intent=intent,
        )
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
        if switch_receipt is not None:
            receipt_path = _switch_receipts_dir(
                pointer_path=pointer_path,
            ) / "{}.json".format(
                str(switch_receipt["switch_receipt_id"]).split(":", 1)[1]
            )
            if (
                receipt_path.is_file()
                and not receipt_path.is_symlink()
                and receipt_path.read_bytes()
                == canonical_json_bytes(value=switch_receipt) + b"\n"
            ):
                receipt_path.unlink()
        _remove_switch_intent(
            pointer_path=pointer_path, intent=intent,
        )
        raise PublicationError(
            "Publication commit aborted and rolled back"
        ) from error
    return pointer


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
    """Verify authority, lock, and switch one publication.

    Args:
        publications_dir: Bundle parent.
        pointer_path: Unique active commit point.
        publication_id: Prepared bundle to activate.
        expected_previous_publication_id: CAS predecessor.
        committed_at_utc: Explicit UTC timestamp.
        mirror_paths: Bundle-relative file to root compatibility mirror.
        switch_mode: ``COMMIT`` or ``ROLLBACK``.

    Returns:
        New active pointer.
    """
    if switch_mode not in {"COMMIT", "ROLLBACK"}:
        raise PublicationError("Publication switch mode is invalid")
    _validate_utc_timestamp(value=committed_at_utc)
    bundle_dir = publications_dir / publication_id
    manifest = verify_publication_bundle(bundle_dir=bundle_dir)
    if switch_mode == "COMMIT":
        _require_formal_forward_commit(
            authority=_publication_commit_authority(bundle_dir=bundle_dir)
        )
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        _recover_switch_intent_locked(
            publications_dir=publications_dir,
            pointer_path=pointer_path,
            mirror_paths=mirror_paths,
        )
        if switch_mode == "COMMIT":
            # Only the initial-chain primitive may create the first pointer;
            # ordinary commits must extend the rollback-capable chain.
            _require_existing_active_for_forward_commit(
                pointer_path=pointer_path
            )
        return _switch_publication_locked(
            publications_dir=publications_dir,
            pointer_path=pointer_path,
            bundle_dir=bundle_dir,
            manifest=manifest,
            publication_id=publication_id,
            expected_previous_publication_id=(
                expected_previous_publication_id
            ),
            committed_at_utc=committed_at_utc,
            mirror_paths=mirror_paths,
            switch_mode=switch_mode,
        )


def _commit_initial_publication_chain(
    *, publication_root: Path,
    legacy_predecessor_publication_id: str,
    successor_publication_id: str,
    committed_at_utc: str,
) -> Dict[str, object]:
    """Atomically establish legacy predecessor and first formal successor.

    Args:
        publication_root: Root containing both prepared immutable bundles.
        legacy_predecessor_publication_id: Imported opaque legacy baseline A.
        successor_publication_id: Formally validated first vNext publication
            B.
        committed_at_utc: Explicit UTC observation time for both pointer
            writes.

    Returns:
        The committed predecessor pointer and final active pointer.

    Raises:
        PublicationError: Unless the root has no active pointer, A is a strict
            legacy import, B is formal and binds A, and both writes succeed.
            A failed second write restores the original no-pointer root bytes.
    """
    _validate_utc_timestamp(value=committed_at_utc)
    layout = publication_layout(publication_root=publication_root)
    publications_dir = Path(layout["publications_dir"])
    pointer_path = Path(layout["pointer_path"])
    mirror_paths = layout["mirror_paths"]
    legacy_dir = publications_dir / legacy_predecessor_publication_id
    successor_dir = publications_dir / successor_publication_id
    legacy_manifest = verify_publication_bundle(bundle_dir=legacy_dir)
    successor_manifest = verify_publication_bundle(bundle_dir=successor_dir)
    if (
        _publication_commit_authority(bundle_dir=legacy_dir)
        != LEGACY_COMMIT_AUTHORITY
        or legacy_manifest["previous_publication_id"] is not None
    ):
        raise PublicationError(
            "Initial predecessor is not an imported legacy baseline"
        )
    _require_formal_forward_commit(
        authority=_publication_commit_authority(bundle_dir=successor_dir)
    )
    if successor_manifest["previous_publication_id"] != (
        legacy_predecessor_publication_id
    ):
        raise PublicationError(
            "Initial successor does not bind legacy predecessor"
        )
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        _recover_switch_intent_locked(
            publications_dir=publications_dir,
            pointer_path=pointer_path,
            mirror_paths=mirror_paths,
        )
        if _read_pointer(pointer_path=pointer_path) is not None:
            raise PublicationError(
                "Initial publication chain requires no active pointer"
            )
        receipt_dir = _switch_receipts_dir(pointer_path=pointer_path)
        if receipt_dir.is_symlink() or (
            receipt_dir.exists() and not receipt_dir.is_dir()
        ):
            raise PublicationError("Initial switch history is unsafe")
        existing_receipts = (
            list(receipt_dir.iterdir()) if receipt_dir.exists() else []
        )
        if existing_receipts:
            raise PublicationError(
                "Initial publication chain found orphan switch history"
            )
        original_mirrors: Dict[Path, Optional[bytes]] = {}
        for target in mirror_paths.values():
            if target.exists() and (
                target.is_symlink() or not target.is_file()
            ):
                raise PublicationError("Initial legacy root is unsafe")
            original_mirrors[target] = (
                target.read_bytes() if target.exists() else None
            )
        try:
            predecessor_pointer = _switch_publication_locked(
                publications_dir=publications_dir,
                pointer_path=pointer_path,
                bundle_dir=legacy_dir,
                manifest=legacy_manifest,
                publication_id=legacy_predecessor_publication_id,
                expected_previous_publication_id=None,
                committed_at_utc=committed_at_utc,
                mirror_paths=mirror_paths,
                switch_mode="COMMIT",
            )
            active_pointer = _switch_publication_locked(
                publications_dir=publications_dir,
                pointer_path=pointer_path,
                bundle_dir=successor_dir,
                manifest=successor_manifest,
                publication_id=successor_publication_id,
                expected_previous_publication_id=(
                    legacy_predecessor_publication_id
                ),
                committed_at_utc=committed_at_utc,
                mirror_paths=mirror_paths,
                switch_mode="COMMIT",
            )
        except PublicationError as error:
            _restore_mirrors(snapshots=original_mirrors)
            if pointer_path.exists() and (
                pointer_path.is_symlink() or not pointer_path.is_file()
            ):
                raise PublicationError(
                    "Initial publication pointer recovery is unsafe"
                ) from error
            if pointer_path.exists():
                pointer_path.unlink()
            if receipt_dir.exists():
                for path in list(receipt_dir.iterdir()):
                    if path.is_symlink() or not path.is_file():
                        raise PublicationError(
                            "Initial switch history recovery is unsafe"
                        ) from error
                    path.unlink()
            raise PublicationError(
                "initial publication chain aborted and restored legacy root"
            ) from error
    return {
        "predecessor_pointer": predecessor_pointer,
        "active_pointer": active_pointer,
    }


def commit_initial_publication_chain(
    *, publication_root: Path,
    legacy_predecessor_publication_id: str,
    successor_publication_id: str,
    committed_at_utc: str,
) -> Dict[str, object]:
    """Reject a direct initial-chain mutation outside Cutover orchestration.

    Args:
        publication_root: Ignored caller publication root.
        legacy_predecessor_publication_id: Ignored imported predecessor.
        successor_publication_id: Ignored formal successor.
        committed_at_utc: Ignored caller commit time.

    Raises:
        PublicationError: Always. Only the Cutover orchestrator may invoke the
            private atomic initial-chain primitive after all release evidence.
    """
    del (
        publication_root, legacy_predecessor_publication_id,
        successor_publication_id, committed_at_utc,
    )
    raise PublicationError("FORMAL_CUTOVER_AUTHORITY_REQUIRED")


def _commit_publication(
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


def _commit_recorded_sandbox_publication(
    *, publication_root: Path, publication_id: str,
    expected_active_publication_id: Optional[str], committed_at_utc: str,
) -> Dict[str, object]:
    """Commit one RECORDED bundle only inside a prevalidated sandbox root.

    Args:
        publication_root: Internally derived recorded sandbox root.
        publication_id: Prepared RECORDED bundle identity.
        expected_active_publication_id: Sandbox pointer observed before prepare.
        committed_at_utc: Explicit UTC transaction time.

    Returns:
        Complete sandbox pointer produced by the shared transaction primitive.

    Raises:
        PublicationError: Unless the bundle is exactly RECORDED and the
            sandbox CAS predecessor still matches.
    """
    _validate_utc_timestamp(value=committed_at_utc)
    layout = publication_layout(publication_root=publication_root)
    bundle_dir = Path(layout["publications_dir"]) / publication_id
    manifest = verify_publication_bundle(bundle_dir=bundle_dir)
    if _publication_commit_authority(bundle_dir=bundle_dir) != (
        RECORDED_COMMIT_AUTHORITY
    ):
        raise PublicationError(
            "Recorded sandbox accepts only RECORDED publication bundles"
        )
    pointer_path = Path(layout["pointer_path"])
    lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open(mode="a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        _recover_switch_intent_locked(
            publications_dir=Path(layout["publications_dir"]),
            pointer_path=pointer_path,
            mirror_paths=layout["mirror_paths"],
        )
        return _switch_publication_locked(
            publications_dir=Path(layout["publications_dir"]),
            pointer_path=pointer_path,
            bundle_dir=bundle_dir,
            manifest=manifest,
            publication_id=publication_id,
            expected_previous_publication_id=(
                expected_active_publication_id
            ),
            committed_at_utc=committed_at_utc,
            mirror_paths=layout["mirror_paths"],
            switch_mode="COMMIT",
        )


def commit_publication(
    *,
    publication_root: Path,
    publication_id: str,
    expected_active_publication_id: Optional[str],
    committed_at_utc: str,
) -> Dict[str, object]:
    """Reject direct formal forward mutation outside Cutover orchestration.

    Args:
        publication_root: Ignored caller publication root.
        publication_id: Ignored prepared publication identity.
        expected_active_publication_id: Ignored caller CAS predecessor.
        committed_at_utc: Ignored caller commit time.

    Raises:
        PublicationError: Always. The public API cannot mint formal Cutover
            authority from a caller-supplied bundle or predecessor.
    """
    del (
        publication_root, publication_id, expected_active_publication_id,
        committed_at_utc,
    )
    raise PublicationError("FORMAL_CUTOVER_AUTHORITY_REQUIRED")


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
        _recover_switch_intent_locked(
            publications_dir=publications_dir,
            pointer_path=pointer_path,
            mirror_paths=mirror_paths,
        )
        view = PublicationView._open_paths(
            publications_dir=publications_dir, pointer_path=pointer_path,
        )
        for relative in mirror_paths:
            atomic_write_bytes(
                path=mirror_paths[relative],
                content=view.read_bytes(relative_path=relative),
            )
        return view.publication_id


def publication_state_snapshot(
    *, publication_root: Path
) -> Dict[str, object]:
    """Read the official pointer identity and every root mirror digest.

    Args:
        publication_root: Repository root owning the formal publication layout.

    Returns:
        Exact active publication ID plus one SHA-256 or ``None`` per required
        compatibility mirror.

    Raises:
        PublicationError: When pointer, bundle, or a present mirror is unsafe.
    """
    layout = publication_layout(publication_root=publication_root)
    pointer = _read_pointer(pointer_path=layout["pointer_path"])
    active_id = None
    if pointer is not None:
        active_id = PublicationView._open_paths(
            publications_dir=layout["publications_dir"],
            pointer_path=layout["pointer_path"],
        ).publication_id
    mirror_hashes: Dict[str, Optional[str]] = {}
    for relative, path in layout["mirror_paths"].items():
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise PublicationError("Compatibility mirror is unsafe")
        mirror_hashes[relative] = (
            sha256_file(path=path) if path.exists() else None
        )
    return {
        "active_publication_id": active_id,
        "mirror_hashes": mirror_hashes,
    }


def _validate_fault_state(*, state: Mapping[str, object]) -> None:
    """Validate one independently observed pointer and mirror state.

    Args:
        state: Snapshot returned by :func:`publication_state_snapshot`.

    Raises:
        PublicationError: On an incomplete identity or digest mapping.
    """
    if type(state) is not dict or set(state) != FAULT_STATE_FIELDS:
        raise PublicationError("Publication fault state fields differ")
    active_id = state["active_publication_id"]
    if active_id is not None and (
        type(active_id) is not str
        or PUBLICATION_ID_PATTERN.fullmatch(active_id) is None
    ):
        raise PublicationError("Publication fault active identity is invalid")
    hashes = state["mirror_hashes"]
    if type(hashes) is not dict or set(hashes) != REQUIRED_BUNDLE_FILES:
        raise PublicationError("Publication fault mirror exact set differs")
    if any(
        digest is not None
        and (
            type(digest) is not str
            or SHA256_PATTERN.fullmatch(digest) is None
        )
        for digest in hashes.values()
    ):
        raise PublicationError("Publication fault mirror digest is invalid")


def write_publication_fault_receipt(
    *,
    publication_root: Path,
    scenario_id: str,
    prepared_publication_id: Optional[str],
    fault_point: str,
    before: Mapping[str, object],
    after: Mapping[str, object],
    outcome: str,
    temporary_workspace_cleaned: bool,
) -> Dict[str, object]:
    """Persist one content-addressed publication fault observation.

    Args:
        publication_root: Repository root owning formal receipt storage.
        scenario_id: Stable failure-matrix scenario identity.
        prepared_publication_id: Candidate exercised by the scenario, or
            ``None`` when a pre-prepare gate correctly blocked it.
        fault_point: Exact transaction checkpoint that failed or raced.
        before: Independently observed pre-attempt publication state.
        after: Independently observed terminal publication state.
        outcome: Stable classified fault outcome.
        temporary_workspace_cleaned: Whether no temporary bundle remains.

    Returns:
        Strict receipt whose identity and filename derive from its body.

    Raises:
        PublicationError: On malformed observation data or divergent reuse.
    """
    publication_layout(publication_root=publication_root)
    _validate_fault_state(state=before)
    _validate_fault_state(state=after)
    if not isinstance(scenario_id, str) or not scenario_id:
        raise PublicationError("Publication fault scenario is required")
    if prepared_publication_id is not None and (
        type(prepared_publication_id) is not str
        or PUBLICATION_ID_PATTERN.fullmatch(prepared_publication_id) is None
    ):
        raise PublicationError("Prepared publication identity is invalid")
    if not isinstance(fault_point, str) or not fault_point:
        raise PublicationError("Publication fault point is required")
    if outcome not in FAULT_RECEIPT_OUTCOMES:
        raise PublicationError("Publication fault outcome is invalid")
    if type(temporary_workspace_cleaned) is not bool:
        raise PublicationError(
            "Publication temporary-workspace result must be boolean"
        )
    body = {
        "schema_version": 1,
        "scenario_id": scenario_id,
        "active_before": before["active_publication_id"],
        "prepared_publication_id": prepared_publication_id,
        "fault_point": fault_point,
        "active_after": after["active_publication_id"],
        "mirror_hashes_before": dict(before["mirror_hashes"]),
        "mirror_hashes_after": dict(after["mirror_hashes"]),
        "outcome": outcome,
        "temporary_workspace_cleaned": temporary_workspace_cleaned,
    }
    receipt = {
        **body,
        "fault_receipt_id": content_hash(value=body),
    }
    receipt_dir = (
        publication_root / "outputs" / "publication_fault_receipts"
    )
    if receipt_dir.is_symlink() or (
        receipt_dir.exists() and not receipt_dir.is_dir()
    ):
        raise PublicationError("Publication fault receipt root is unsafe")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / "{}.json".format(
        str(receipt["fault_receipt_id"]).split(":", maxsplit=1)[1]
    )
    expected = canonical_json_bytes(value=receipt) + b"\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise PublicationError("Publication fault receipt is unsafe")
        if path.read_bytes() != expected:
            raise PublicationError("Publication fault receipt bytes differ")
    else:
        atomic_write_json(path=path, value=receipt)
    return receipt


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
        pointer_path = Path(layout["pointer_path"])
        lock_path = pointer_path.with_suffix(pointer_path.suffix + ".lock")
        if (
            lock_path.is_symlink()
            or not lock_path.exists()
            or not lock_path.is_file()
        ):
            raise PublicationError(
                "Publication authority lock is missing or unsafe"
            )
        # A forward switch holds this same file exclusively from mirror
        # preparation through pointer and committed-edge persistence. Readers
        # therefore observe either complete transaction, never the deliberate
        # pointer-before-edge interval.
        with lock_path.open(mode="rb") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
            _assert_no_pending_switch_intent(
                pointer_path=pointer_path,
            )
            return cls._open_paths(
                publications_dir=layout["publications_dir"],
                pointer_path=pointer_path,
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
        _switch_receipt_for_pointer(
            pointer_path=pointer_path,
            pointer=pointer,
        )
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


def complete_recorded_publication_sandbox(
    *, repo_root: Path, workspace_dir: Path, batch_manifest_path: Path,
    legacy_snapshot_dir: Path, staging_dir: Path, validated_at_utc: str,
    committed_at_utc: str,
) -> Dict[str, object]:
    """Validate, commit, and read back one isolated RECORDED publication.

    Args:
        repo_root: Repository authority and formal publication root.
        workspace_dir: Repository-contained recorded workflow workspace.
        batch_manifest_path: Complete recorded FROZEN BatchManifest.
        legacy_snapshot_dir: Frozen compatibility inputs for projection.
        staging_dir: Candidate view produced by the recorded Cutover path.
        validated_at_utc: Explicit UTC time for recorded gates.
        committed_at_utc: Explicit UTC time for the sandbox pointer switch.

    Returns:
        Sandbox publication identity, pointer digest, exact read-back hashes,
        mirror hashes, predecessor, and portable sandbox root.

    Raises:
        PublicationError: On an unsafe/overlapping workspace, non-RECORDED
            bundle, CAS loss, formal-state change, or read-back mismatch.

    Why:
        Recorded UAT needs the real publication transaction and pinned read
        path without accepting caller-selected authority or touching the
        repository's formal pointer and root compatibility mirrors.
    """
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise PublicationError("Recorded sandbox repository is unsafe")
    if workspace_dir.is_symlink() or (
        workspace_dir.exists() and not workspace_dir.is_dir()
    ):
        raise PublicationError("Recorded sandbox workspace is unsafe")
    repository_lexical = Path(os.path.abspath(str(repo_root)))
    workspace_lexical = Path(os.path.abspath(str(workspace_dir)))
    lexical_allowed_root = repository_lexical / "artifacts" / "vnext"
    try:
        allowed_relative = workspace_lexical.relative_to(
            lexical_allowed_root
        )
    except ValueError as error:
        raise PublicationError(
            "Recorded sandbox workspace must be under artifacts/vnext"
        ) from error
    if allowed_relative == Path("."):
        raise PublicationError(
            "Recorded sandbox workspace must be under artifacts/vnext"
        )
    workspace_relative = workspace_lexical.relative_to(repository_lexical)
    current = repository_lexical
    for part in workspace_relative.parts:
        current = current / part
        if current.is_symlink() or (
            current.exists() and not current.is_dir()
        ):
            raise PublicationError(
                "Recorded sandbox workspace contains a symlink"
            )
    repository = repository_lexical.resolve()
    workspace = workspace_lexical.resolve(strict=False)
    allowed_root = repository / "artifacts" / "vnext"
    try:
        resolved_relative = workspace.relative_to(allowed_root)
    except ValueError as error:
        raise PublicationError(
            "Recorded sandbox workspace contains a symlink"
        ) from error
    if resolved_relative == Path("."):
        raise PublicationError(
            "Recorded sandbox workspace must be under artifacts/vnext"
        )
    # Authority and containment are proven before the first filesystem write.
    workspace.mkdir(parents=True, exist_ok=True)
    sandbox_root = workspace / "recorded-publication"
    formal_layout = publication_layout(publication_root=repository)
    protected_paths = {
        Path(formal_layout["pointer_path"]).resolve(),
        Path(formal_layout["publications_dir"]).resolve(),
        *(
            Path(path).resolve()
            for path in formal_layout["mirror_paths"].values()
        ),
    }
    if any(
        sandbox_root == protected
        or sandbox_root in protected.parents
        or protected in sandbox_root.parents
        for protected in protected_paths
    ):
        raise PublicationError(
            "Recorded sandbox overlaps formal publication authority"
        )
    for candidate in (
        batch_manifest_path, legacy_snapshot_dir, staging_dir,
    ):
        resolved = candidate.resolve()
        if (
            resolved == sandbox_root
            or resolved in sandbox_root.parents
            or sandbox_root in resolved.parents
        ):
            raise PublicationError(
                "Recorded sandbox overlaps a publication input"
            )
    formal_before = publication_state_snapshot(
        publication_root=repository,
    )
    layout = publication_layout(publication_root=sandbox_root)
    existing_pointer = _read_pointer(pointer_path=layout["pointer_path"])
    previous_publication_id = None
    if existing_pointer is not None:
        previous_publication_id = PublicationView.open(
            publication_root=sandbox_root,
        ).publication_id
    write_publication_validation_receipt(
        repo_root=repository,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
        previous_publication_id=previous_publication_id,
        validated_at_utc=validated_at_utc,
    )
    manifest = prepare_publication_bundle(
        publication_root=sandbox_root,
        repo_root=repository,
        batch_manifest_path=batch_manifest_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
        previous_publication_id=previous_publication_id,
    )
    pointer = _commit_recorded_sandbox_publication(
        publication_root=sandbox_root,
        publication_id=str(manifest["publication_id"]),
        expected_active_publication_id=previous_publication_id,
        committed_at_utc=committed_at_utc,
    )
    view = PublicationView.open(publication_root=sandbox_root)
    readback_hashes = {
        relative: sha256_bytes(
            content=view.read_bytes(relative_path=relative)
        )
        for relative in sorted(REQUIRED_BUNDLE_FILES)
    }
    state = publication_state_snapshot(publication_root=sandbox_root)
    if (
        view.publication_id != manifest["publication_id"]
        or pointer["publication_id"] != manifest["publication_id"]
        or state["active_publication_id"] != manifest["publication_id"]
        or state["mirror_hashes"] != readback_hashes
    ):
        raise PublicationError("Recorded sandbox read-back differs")
    if publication_state_snapshot(publication_root=repository) != formal_before:
        raise PublicationError("Recorded sandbox changed formal publication")
    return {
        "previous_publication_id": previous_publication_id,
        "publication_id": view.publication_id,
        "pointer_sha256": sha256_file(path=layout["pointer_path"]),
        "readback_hashes": readback_hashes,
        "root_mirror_hashes": state["mirror_hashes"],
        "publication_root": (
            workspace_relative / "recorded-publication"
        ).as_posix(),
    }


def verified_legacy_baseline_identity(
    *, publication_view: PublicationView,
) -> Optional[Dict[str, object]]:
    """Return the verified legacy-import identity for one pinned view.

    Args:
        publication_view: Pinned view whose listed marker, when present, must
            survive a fresh complete bundle verification.

    Returns:
        ``None`` for a normal formal publication; otherwise the content-bound
        import, baseline, Requirement, and frozen validation-manifest identity.

    Raises:
        PublicationError: When a marker-bearing view is not the exact verified
            bundle represented by its publication identity and manifest.
    """
    listed = {
        str(record["path"])
        for record in publication_view.manifest["files"]
    }
    if LEGACY_BASELINE_IMPORT_MANIFEST not in listed:
        return None
    verified = verify_publication_bundle(
        bundle_dir=publication_view.bundle_dir,
    )
    if (
        verified["publication_id"] != publication_view.publication_id
        or dict(verified) != dict(publication_view.manifest)
    ):
        raise PublicationError("Pinned legacy publication identity differs")
    marker_bytes = publication_view.read_bytes(
        relative_path=LEGACY_BASELINE_IMPORT_MANIFEST,
    )
    try:
        marker = strict_json_loads(text=marker_bytes.decode("utf-8"))
    except (CanonicalError, UnicodeDecodeError) as error:
        raise PublicationError(
            "Verified legacy import marker cannot be decoded"
        ) from error
    if not isinstance(marker, dict):
        raise PublicationError("Verified legacy import marker is not object")
    validation_record = marker["baseline_artifacts"][
        "outputs/validation_run_manifest.json"
    ]
    return {
        "record_type": marker["record_type"],
        "publication_id": publication_view.publication_id,
        "legacy_baseline_import_id": marker[
            "legacy_baseline_import_id"
        ],
        "baseline_manifest_sha256": marker[
            "baseline_manifest_sha256"
        ],
        "baseline_repository_commit": marker[
            "baseline_repository_commit"
        ],
        "requirement_hashes": marker["requirement_hashes"],
        "validation_manifest_sha256": validation_record["sha256"],
        "validation_manifest_size": validation_record["size"],
    }


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
