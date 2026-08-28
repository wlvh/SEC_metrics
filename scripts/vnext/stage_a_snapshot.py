"""Bind Stage-A source changes without rewriting the historical R2 snapshot.

The legacy validation provenance remains the authority for its original R2
source/artifact snapshot.  This module creates a second, content-addressed
overlay only after that historical checker proves every non-source artifact is
still intact.  The overlay then binds the current clean Stage-A source tree,
the unchanged R2 root mirrors, and the current table-freeze receipt.

Call graph:
``write_stage_a_snapshot`` -> ``build_stage_a_snapshot`` ->
``validate_stage_a_snapshot``.  Both build and validate consume only local
Git/source/artifact bytes and never create SEC or provider egress.
"""

from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from validation_provenance import capture_source_snapshot
from validation_provenance import pin_validation_publication_transaction
from validation_provenance import verify_validation_snapshot
from validation_provenance import ValidationProvenanceError

from .canonical import atomic_write_json, content_hash, parse_utc_timestamp
from .canonical import sha256_file, strict_json_file
from .table_qualification_freeze import validate_table_qualification_freeze
from .table_qualification_freeze import TableQualificationFreezeError


STAGE_A_SNAPSHOT_ROOT = Path(
    "artifacts/vnext/table_qualification_freeze/stage_a_validation",
)
FREEZE_POINTER_PATH = Path("config/table_qualification_freeze.json")
ROOT_PATHS = (
    Path("outputs/active_publication.json"),
    Path("outputs/metrics_matrix.csv"),
    Path("outputs/metric_evidence.csv"),
    Path("REPORT_十公司财务指标.md"),
)
HISTORICAL_PATHS = (
    Path("outputs/validation_run_manifest.json"),
    Path("outputs/validation_snapshot_provenance.json"),
)
SNAPSHOT_FIELDS = {
    "freeze_receipt_id",
    "freeze_receipt_sha256",
    "frozen_at_utc",
    "historical_snapshot_sha256",
    "historical_validation_manifest_sha256",
    "record_type",
    "root_state",
    "schema_version",
    "source_snapshot",
    "stage_a_snapshot_id",
}
SOURCE_ONLY_ERRORS = {
    "source-input tree digest mismatch",
    "source-input file count mismatch",
    "source commit mismatch",
}
POST_SNAPSHOT_MUTABLE_POINTER = (
    "artifacts/vnext/table_stage_c_evidence/"
    "financial_materialization_benchmark/current.json"
)
POST_SNAPSHOT_APPEND_ROOTS = (
    "artifacts/vnext/table_stage_c_evidence/"
    "financial_materialization_benchmark/",
    "artifacts/vnext/table_qualification_freeze/",
)


class StageASnapshotError(ValueError):
    """Report a missing, stale, or non-Stage-A validation overlay."""


def _regular_file(*, repo_root: Path, relative: Path, label: str) -> Path:
    """Return one repository-contained regular file.

    Args:
        repo_root: Repository authority root.
        relative: Normalized repository-relative path.
        label: Stable diagnostic label.

    Returns:
        Existing non-symlink regular path.
    """
    if relative.is_absolute() or ".." in relative.parts:
        raise StageASnapshotError(label + " path is unsafe")
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        raise StageASnapshotError(label + " is absent or unsafe")
    return path


def _json_object(*, repo_root: Path, relative: Path, label: str) -> Dict[str, object]:
    """Read one strict JSON object from a regular repository file.

    Args:
        repo_root: Repository authority root.
        relative: Normalized repository-relative JSON path.
        label: Stable diagnostic label.

    Returns:
        Isolated JSON object.
    """
    path = _regular_file(repo_root=repo_root, relative=relative, label=label)
    value = strict_json_file(path=path)
    if type(value) is not dict:
        raise StageASnapshotError(label + " JSON root is invalid")
    return dict(value)


def _root_state(*, repo_root: Path) -> Dict[str, object]:
    """Return the unchanged R2 pointer and root business byte bindings.

    Args:
        repo_root: Repository authority root.

    Returns:
        Active publication identity, root file hashes, row count, and public
        company/metric key-set identity.
    """
    pointer = _json_object(
        repo_root=repo_root,
        relative=Path("outputs/active_publication.json"),
        label="active publication pointer",
    )
    if type(pointer["publication_id"]) is not str or not pointer[
        "publication_id"
    ]:
        raise StageASnapshotError("Active publication identity is invalid")
    metrics_path = _regular_file(
        repo_root=repo_root,
        relative=Path("outputs/metrics_matrix.csv"),
        label="root public matrix",
    )
    with metrics_path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    if not rows or any(
        "company" not in row or "metric_id" not in row for row in rows
    ):
        raise StageASnapshotError("Root public matrix keys are invalid")
    keys = [
        {"company": row["company"], "metric_id": row["metric_id"]}
        for row in rows
    ]
    identities = [(row["company"], row["metric_id"]) for row in keys]
    if len(identities) != len(set(identities)):
        raise StageASnapshotError("Root public matrix keys are duplicated")
    keys.sort(key=lambda row: (row["company"], row["metric_id"]))
    hashes = {}
    for relative in ROOT_PATHS:
        path = _regular_file(
            repo_root=repo_root,
            relative=relative,
            label="root business artifact",
        )
        hashes[relative.as_posix()] = {
            "sha256": sha256_file(path=path),
            "size": path.stat().st_size,
        }
    return {
        "active_publication_id": pointer["publication_id"],
        "root_hashes": hashes,
        "public_matrix_row_count": len(rows),
        "public_key_set_hash": content_hash(value=keys),
    }


def _committed_post_snapshot_artifacts(
    *, repo_root: Path, relative_paths: List[str],
) -> bool:
    """Verify each allowed post-snapshot artifact is exact in current HEAD."""
    for relative in relative_paths:
        path = Path(relative)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not any(relative.startswith(root) for root in POST_SNAPSHOT_APPEND_ROOTS)
        ):
            return False
        working = repo_root / path
        if working.is_symlink() or not working.is_file():
            return False
        committed = subprocess.run(
            ["git", "show", "HEAD:" + relative],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
        )
        if committed.returncode != 0 or committed.stdout != working.read_bytes():
            return False
    return True


def _post_snapshot_artifact_errors_are_allowed(
    *, repo_root: Path, errors: List[str],
) -> bool:
    """Allow only the committed financial pointer and append-only evidence."""
    remaining = set(errors) - SOURCE_ONLY_ERRORS
    pointer_error = (
        "artifact SHA-256 mismatch: " + POST_SNAPSHOT_MUTABLE_POINTER
    )
    if pointer_error not in remaining:
        return False
    remaining.remove(pointer_error)
    digest_errors = [
        error for error in remaining
        if error.startswith("artifact digest key set mismatch: ")
    ]
    if len(digest_errors) != 1 or len(remaining) != 1:
        return False
    match = re.fullmatch(
        r"artifact digest key set mismatch: missing=(\[.*\]) unexpected=(\[.*\])",
        digest_errors[0],
    )
    if match is None:
        return False
    try:
        missing = ast.literal_eval(match.group(1))
        unexpected = ast.literal_eval(match.group(2))
    except (SyntaxError, ValueError):
        return False
    if (
        type(missing) is not list
        or not missing
        or any(type(value) is not str for value in missing)
        or unexpected != []
        or not _committed_post_snapshot_artifacts(
            repo_root=repo_root, relative_paths=missing,
        )
    ):
        return False
    benchmark_check = subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools/benchmark_jpm_full_materialization.py"),
            "--validate",
        ],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    try:
        benchmark = json.loads(benchmark_check.stdout)
    except json.JSONDecodeError:
        return False
    return (
        benchmark_check.returncode == 0
        and type(benchmark) is dict
        and benchmark.get("status") == "COMPLETED"
    )


def _historical_source_errors(*, repo_root: Path) -> List[str]:
    """Verify R2 artifacts and return only its expected source-tree drift.

    Args:
        repo_root: Repository authority root.

    Returns:
        Sorted standard-checker source-only errors.

    Raises:
        StageASnapshotError: When R2 artifact/provenance evidence has any
        other failure and therefore cannot anchor a Stage-A overlay.
    """
    try:
        transaction = pin_validation_publication_transaction(workdir=repo_root)
        result = verify_validation_snapshot(
            workdir=repo_root,
            allow_equivalent_source_tree=True,
            publication_transaction=transaction,
        )
    except ValidationProvenanceError as error:
        raise StageASnapshotError("Historical validation is unavailable") from error
    errors = sorted(result.errors)
    if (
        set(errors) != SOURCE_ONLY_ERRORS
        and not _post_snapshot_artifact_errors_are_allowed(
            repo_root=repo_root, errors=errors,
        )
    ):
        raise StageASnapshotError(
            "Historical R2 snapshot has non-source failure: {}".format(
                ";".join(errors),
            )
        )
    return errors


def _freeze_receipt_binding(
    *, repo_root: Path, family_id: Optional[str] = None,
) -> Dict[str, str]:
    """Return the configured current freeze receipt's immutable binding.

    Args:
        repo_root: Repository authority root.

    Returns:
        Freeze receipt ID and exact receipt file SHA-256.
    """
    try:
        freeze = validate_table_qualification_freeze(
            repo_root=repo_root,
            family_id=family_id,
        )
    except TableQualificationFreezeError as error:
        raise StageASnapshotError("Table qualification freeze is invalid") from error
    if family_id is not None:
        readiness = freeze["readiness_by_family"].get(family_id)
        if (
            type(readiness) is not dict
            or readiness.get("live_ready") is not True
        ):
            raise StageASnapshotError(
                "Requested family qualification freeze is not ready"
            )
    pointer = _json_object(
        repo_root=repo_root,
        relative=FREEZE_POINTER_PATH,
        label="table qualification freeze pointer",
    )
    receipt_relative = Path(str(pointer["receipt_path"]))
    receipt_path = _regular_file(
        repo_root=repo_root,
        relative=receipt_relative,
        label="table qualification freeze receipt",
    )
    if pointer["receipt_id"] != freeze["receipt_id"]:
        raise StageASnapshotError("Freeze pointer receipt identity differs")
    return {
        "freeze_receipt_id": str(freeze["receipt_id"]),
        "freeze_receipt_sha256": sha256_file(path=receipt_path),
    }


def _current_git_commit(*, repo_root: Path) -> str:
    """Return current commit identity.

    Whole-tree cleanliness is deliberately not imposed at this boundary.
    """
    completed = subprocess.run(
        args=["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    commit = completed.stdout.strip()
    if (
        completed.returncode != 0
        or re.fullmatch(r"[0-9a-f]{40}", commit) is None
    ):
        raise StageASnapshotError("Stage-A current Git commit is unavailable")
    return commit


def _snapshot_path(*, repo_root: Path, freeze_receipt_id: str) -> Path:
    """Return the deterministic Stage-A overlay path for one freeze receipt.

    Args:
        repo_root: Repository authority root.
        freeze_receipt_id: Content-addressed freeze receipt identity.

    Returns:
        Repository-relative overlay path keyed by the frozen receipt.
    """
    if not freeze_receipt_id.startswith("sha256:"):
        raise StageASnapshotError("Freeze receipt identity is invalid")
    return STAGE_A_SNAPSHOT_ROOT / (
        freeze_receipt_id.split(":", maxsplit=1)[1] + ".json"
    )


def build_stage_a_snapshot(
    *, repo_root: Path, frozen_at_utc: str,
) -> Dict[str, object]:
    """Build a current-source Stage-A overlay without writing it.

    Args:
        repo_root: Repository authority root.
        frozen_at_utc: Explicit UTC construction timestamp.

    Returns:
        Content-addressed Stage-A overlay receipt.
    """
    try:
        parse_utc_timestamp(value=frozen_at_utc)
    except ValueError as error:
        raise StageASnapshotError("Stage-A snapshot timestamp is invalid") from error
    source = capture_source_snapshot(workdir=repo_root)
    if source.checkout_status != "GIT_CLEAN" or source.source_commit is None:
        raise StageASnapshotError("Stage-A snapshot requires clean Git source")
    _historical_source_errors(repo_root=repo_root)
    freeze = _freeze_receipt_binding(repo_root=repo_root)
    historical_hashes = {}
    for relative in HISTORICAL_PATHS:
        path = _regular_file(
            repo_root=repo_root,
            relative=relative,
            label="historical validation artifact",
        )
        historical_hashes[relative.as_posix()] = sha256_file(path=path)
    body = {
        "record_type": "ISSUE_15_STAGE_A_VALIDATION_SNAPSHOT",
        "schema_version": 1,
        "frozen_at_utc": frozen_at_utc,
        **freeze,
        "source_snapshot": {
            "checkout_status": source.checkout_status,
            "source_commit": source.source_commit,
            "source_input_tree_sha256": source.tree_sha256,
            "source_file_count": source.file_count,
        },
        "historical_validation_manifest_sha256": historical_hashes[
            "outputs/validation_run_manifest.json"
        ],
        "historical_snapshot_sha256": historical_hashes[
            "outputs/validation_snapshot_provenance.json"
        ],
        "root_state": _root_state(repo_root=repo_root),
    }
    return {
        "stage_a_snapshot_id": content_hash(value=body),
        **body,
    }


def write_stage_a_snapshot(
    *, repo_root: Path, frozen_at_utc: str,
) -> Dict[str, object]:
    """Write one content-addressed Stage-A overlay or verify an existing copy.

    Args:
        repo_root: Repository authority root.
        frozen_at_utc: Explicit UTC construction timestamp.

    Returns:
        Overlay receipt plus its portable repository-relative path.
    """
    receipt = build_stage_a_snapshot(
        repo_root=repo_root,
        frozen_at_utc=frozen_at_utc,
    )
    relative = _snapshot_path(
        repo_root=repo_root,
        freeze_receipt_id=str(receipt["freeze_receipt_id"]),
    )
    path = repo_root / relative
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise StageASnapshotError("Stage-A snapshot destination is unsafe")
        existing = strict_json_file(path=path)
        if existing != receipt:
            raise StageASnapshotError("Stage-A snapshot destination differs")
    else:
        atomic_write_json(path=path, value=receipt)
    return {**receipt, "snapshot_path": relative.as_posix()}


def validate_stage_a_snapshot(
    *, repo_root: Path, family_id: Optional[str] = None,
) -> Dict[str, object]:
    """Validate the Stage-A overlay globally or for one execution family.

    Args:
        repo_root: Repository authority root.
        family_id: Optional execution-family scope.  When absent, preserve the
            complete source-input tree check used by the offline snapshot
            checker.  When present, the table freeze has already revalidated
            the shared protected closure plus this family's local closure, so
            an unrelated family's local source drift is not promoted to a
            global authorization blocker.

    Returns:
        Overlay identity and a warning when only an artifact commit changed.
    """
    if family_id is not None and (type(family_id) is not str or not family_id):
        raise StageASnapshotError("Stage-A family identity is invalid")
    freeze = _freeze_receipt_binding(
        repo_root=repo_root,
        family_id=family_id,
    )
    relative = _snapshot_path(
        repo_root=repo_root,
        freeze_receipt_id=freeze["freeze_receipt_id"],
    )
    receipt = _json_object(
        repo_root=repo_root,
        relative=relative,
        label="Stage-A validation snapshot",
    )
    if set(receipt) != SNAPSHOT_FIELDS:
        raise StageASnapshotError("Stage-A snapshot fields are invalid")
    body = {
        key: receipt[key]
        for key in receipt
        if key != "stage_a_snapshot_id"
    }
    if receipt["stage_a_snapshot_id"] != content_hash(value=body):
        raise StageASnapshotError("Stage-A snapshot identity differs")
    if (
        receipt["freeze_receipt_id"] != freeze["freeze_receipt_id"]
        or receipt["freeze_receipt_sha256"] != freeze["freeze_receipt_sha256"]
    ):
        raise StageASnapshotError("Stage-A snapshot freeze binding differs")
    expected_source = receipt["source_snapshot"]
    if type(expected_source) is not dict or set(expected_source) != {
        "checkout_status",
        "source_commit",
        "source_file_count",
        "source_input_tree_sha256",
    } or expected_source["checkout_status"] != "GIT_CLEAN":
        raise StageASnapshotError("Stage-A source snapshot is invalid")
    if family_id is None:
        source = capture_source_snapshot(workdir=repo_root)
        if (
            source.checkout_status != "GIT_CLEAN"
            or source.tree_sha256
            != expected_source["source_input_tree_sha256"]
            or source.file_count != expected_source["source_file_count"]
        ):
            raise StageASnapshotError("Stage-A source tree differs")
        source_commit = source.source_commit
        equivalent_tree = (
            source.source_commit != expected_source["source_commit"]
        )
    else:
        # The freeze validator owns execution dependency scoping.  Requiring
        # the all-repository Stage-A tree here would undo that classification
        # before the requested family reaches its authorization gate.
        source_commit = _current_git_commit(repo_root=repo_root)
        equivalent_tree = source_commit != expected_source["source_commit"]
    historical = {
        relative.as_posix(): sha256_file(
            path=_regular_file(
                repo_root=repo_root,
                relative=relative,
                label="historical validation artifact",
            )
        )
        for relative in HISTORICAL_PATHS
    }
    if (
        historical["outputs/validation_run_manifest.json"]
        != receipt["historical_validation_manifest_sha256"]
        or historical["outputs/validation_snapshot_provenance.json"]
        != receipt["historical_snapshot_sha256"]
        or _root_state(repo_root=repo_root) != receipt["root_state"]
    ):
        raise StageASnapshotError("Stage-A historical R2 state differs")
    if family_id is None:
        _historical_source_errors(repo_root=repo_root)
    return {
        "stage_a_snapshot_id": receipt["stage_a_snapshot_id"],
        "source_commit": source_commit,
        "source_commit_equivalent_tree": equivalent_tree,
        "source_validation_scope": (
            "COMPLETE_SOURCE_INPUT_TREE"
            if family_id is None
            else "SHARED_AND_REQUESTED_FAMILY_PROTECTED_CLOSURE"
        ),
        "freeze_receipt_id": freeze["freeze_receipt_id"],
    }
