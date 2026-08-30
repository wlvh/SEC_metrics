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
import hashlib
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
from sec_http import parse_request_log_rows, validate_request_log_manifest

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
    "artifacts/vnext/qualification/cycles/",
    "evidence/request_attempts/",
)
QUALIFICATION_CYCLE_APPEND_ROOT = "artifacts/vnext/qualification/cycles/"
REQUEST_LOG_PATH = Path("evidence/requests_log.csv")
REQUEST_LOG_MANIFEST_PATH = Path("evidence/requests_log_manifest.json")
POST_SNAPSHOT_LEDGER_ERRORS = {
    "artifact SHA-256 mismatch: evidence/requests_log.csv",
    "artifact SHA-256 mismatch: evidence/requests_log_manifest.json",
    "artifact size mismatch: evidence/requests_log.csv",
}


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


def _git_blob(
    *, repo_root: Path, revision: str, relative: str,
) -> Optional[bytes]:
    """Read one exact committed blob without changing the worktree."""
    if (
        revision != "HEAD"
        and re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        return None
    completed = subprocess.run(
        ["git", "show", revision + ":" + relative],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
    )
    return completed.stdout if completed.returncode == 0 else None


def _request_ledger_append_is_valid(
    *, repo_root: Path, missing_artifact_paths: List[str],
) -> bool:
    """Prove current SEC evidence is one committed immutable ledger append."""
    try:
        validation_manifest = _json_object(
            repo_root=repo_root,
            relative=Path("outputs/validation_run_manifest.json"),
            label="historical validation manifest",
        )
        historical_commit = str(validation_manifest["source_commit"])
        historical_log = _git_blob(
            repo_root=repo_root,
            revision=historical_commit,
            relative=REQUEST_LOG_PATH.as_posix(),
        )
        historical_manifest_bytes = _git_blob(
            repo_root=repo_root,
            revision=historical_commit,
            relative=REQUEST_LOG_MANIFEST_PATH.as_posix(),
        )
        current_log_path = _regular_file(
            repo_root=repo_root,
            relative=REQUEST_LOG_PATH,
            label="current request ledger",
        )
        current_manifest_path = _regular_file(
            repo_root=repo_root,
            relative=REQUEST_LOG_MANIFEST_PATH,
            label="current request ledger manifest",
        )
        current_log = current_log_path.read_bytes()
        current_manifest = current_manifest_path.read_bytes()
        if (
            historical_log is None
            or historical_manifest_bytes is None
            or _git_blob(
                repo_root=repo_root,
                revision="HEAD",
                relative=REQUEST_LOG_PATH.as_posix(),
            ) != current_log
            or _git_blob(
                repo_root=repo_root,
                revision="HEAD",
                relative=REQUEST_LOG_MANIFEST_PATH.as_posix(),
            ) != current_manifest
            or not current_log.startswith(historical_log)
        ):
            return False
        historical_rows = parse_request_log_rows(
            text=historical_log.decode("utf-8"),
        )
        current_rows = parse_request_log_rows(
            text=current_log.decode("utf-8"),
        )
        historical_manifest = json.loads(
            historical_manifest_bytes.decode("utf-8"),
        )
        if historical_manifest != {
            "schema_version": 1,
            "row_count": len(historical_rows),
            "content_sha256": hashlib.sha256(historical_log).hexdigest(),
        } or len(current_rows) <= len(historical_rows):
            return False
        validate_request_log_manifest(log_path=current_log_path)
    except (
        KeyError, OSError, UnicodeDecodeError, ValueError,
        StageASnapshotError,
    ):
        return False
    appended_paths = set()
    for row in current_rows[len(historical_rows):]:
        body_relative = str(row["repo_relative_path"])
        headers_relative = str(row["headers_repo_relative_path"])
        if not (
            body_relative.startswith("evidence/request_attempts/")
            and headers_relative.startswith("evidence/request_attempts/")
        ):
            return False
        try:
            body_path = _regular_file(
                repo_root=repo_root,
                relative=Path(body_relative),
                label="appended SEC response body",
            )
            headers_path = _regular_file(
                repo_root=repo_root,
                relative=Path(headers_relative),
                label="appended SEC response headers",
            )
            header_match = re.search(
                r"\.([0-9a-f]{64})\.headers\.json$",
                headers_relative,
            )
            if (
                sha256_file(path=body_path) != row["content_sha256"]
                or body_path.stat().st_size != int(row["content_length"])
                or header_match is None
                or sha256_file(path=headers_path) != header_match.group(1)
            ):
                return False
        except (OSError, StageASnapshotError, ValueError):
            return False
        appended_paths.update({body_relative, headers_relative})
    declared_attempt_paths = {
        path for path in missing_artifact_paths
        if path.startswith("evidence/request_attempts/")
    }
    return appended_paths == declared_attempt_paths


def _qualification_evidence_append_is_valid(
    *, repo_root: Path, missing_artifact_paths: List[str],
) -> bool:
    """Verify each newly committed qualification cycle as one terminal DAG."""
    declared = {
        path for path in missing_artifact_paths
        if path.startswith(QUALIFICATION_CYCLE_APPEND_ROOT)
    }
    if not declared:
        return True
    try:
        from .invocation_control import qualification_remote_egress_terminals
        from .qualification import _parse_qualification_ledger
        from .qualification import (
            validate_table_qualification_provider_ledger_entry,
        )
        from .run_store import load_frozen_run_terminal_bytes
    except ImportError:
        return False
    cycle_pattern = re.compile(
        r"^" + re.escape(QUALIFICATION_CYCLE_APPEND_ROOT)
        + r"([0-9a-f]{64})/"
    )
    cycles: Dict[str, set[str]] = {}
    for relative in declared:
        match = cycle_pattern.match(relative)
        if match is None:
            return False
        cycles.setdefault(match.group(1), set()).add(relative)
    try:
        for cycle_digest, cycle_paths in cycles.items():
            cycle_relative = QUALIFICATION_CYCLE_APPEND_ROOT + cycle_digest
            tracked = subprocess.run(
                ["git", "ls-files", "--", cycle_relative],
                cwd=str(repo_root),
                check=True,
                capture_output=True,
                encoding="utf-8",
            )
            tracked_paths = {
                line for line in tracked.stdout.splitlines() if line
            }
            if tracked_paths != cycle_paths:
                return False
            cycle_root = repo_root / cycle_relative
            runs_root = cycle_root / "runs"
            invocation_root = cycle_root / "invocation_control"
            if (
                cycle_root.is_symlink()
                or runs_root.is_symlink()
                or invocation_root.is_symlink()
                or not runs_root.is_dir()
                or not invocation_root.is_dir()
            ):
                return False
            cycle_id = "sha256:" + cycle_digest
            ledger_path = (
                repo_root
                / "artifacts/vnext/table_qualification_freeze/cycles"
                / cycle_digest
                / "provider_ledger.jsonl"
            )
            if ledger_path.is_symlink() or not ledger_path.is_file():
                return False
            ledger_rows = _parse_qualification_ledger(
                content=ledger_path.read_bytes(),
            )
            ledger_by_id = {
                str(row["qualification_provider_ledger_entry_id"]): row
                for row in ledger_rows
            }
            if len(ledger_by_id) != len(ledger_rows):
                return False
            used_ledger_ids = set()
            used_workspaces = set()
            run_directories = sorted(
                path for path in runs_root.iterdir()
                if path.is_dir() and not path.is_symlink()
            )
            if not run_directories:
                return False
            for run_dir in run_directories:
                manifest, records, decisions = load_frozen_run_terminal_bytes(
                    run_dir=run_dir,
                )
                authorization = manifest.get("qualification_authorization")
                if type(authorization) is not dict:
                    return False
                body = {
                    key: authorization[key]
                    for key in authorization
                    if key != "qualification_authorization_id"
                }
                expected_run_relative = run_dir.relative_to(
                    repo_root
                ).as_posix()
                if (
                    authorization.get("qualification_authorization_id")
                    != content_hash(value=body)
                    or authorization.get("qualification_cycle_id") != cycle_id
                    or authorization.get("run_id") != manifest.get("run_id")
                    or authorization.get("run_directory_relative_path")
                    != expected_run_relative
                    or manifest.get("target_period")
                    != authorization.get("target_period")
                ):
                    return False
                freeze_id = authorization.get("freeze_receipt_id")
                if (
                    type(freeze_id) is not str
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", freeze_id)
                    is None
                ):
                    return False
                freeze_path = (
                    repo_root
                    / "artifacts/vnext/table_qualification_freeze/receipts"
                    / (freeze_id.split(":", maxsplit=1)[1] + ".json")
                )
                freeze = _json_object(
                    repo_root=repo_root,
                    relative=freeze_path.relative_to(repo_root),
                    label="historical qualification freeze receipt",
                )
                freeze_body = {
                    key: freeze[key]
                    for key in freeze
                    if key != "table_qualification_freeze_receipt_id"
                }
                if (
                    freeze.get("table_qualification_freeze_receipt_id")
                    != content_hash(value=freeze_body)
                    or freeze.get("table_qualification_freeze_receipt_id")
                    != freeze_id
                    or freeze.get("qualification_cycle_id") != cycle_id
                ):
                    return False
                attempts = [
                    record for record in records
                    if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                ]
                qualification_evidence = [
                    record for record in records
                    if record["record_type"]
                    == "TABLE_QUALIFICATION_EVIDENCE"
                ]
                checks = [
                    record for record in records
                    if record["record_type"] == "EVIDENCE_CHECK"
                ]
                results = [
                    record for record in records
                    if record["record_type"] == "METRIC_RESULT"
                ]
                if (
                    len(attempts) != 1
                    or attempts[0].get("status") != "SUCCEEDED"
                    or attempts[0].get("qualification_authorization")
                    != authorization
                    or len(qualification_evidence) != 1
                    or qualification_evidence[0].get(
                        "qualification_authorization"
                    ) != authorization
                    or qualification_evidence[0].get("attempt_id")
                    != attempts[0].get("attempt_id")
                    or not checks
                    or any(check.get("status") != "PASS" for check in checks)
                    or not results
                    or len(decisions) != 1
                    or decisions[0].get("decision") != "APPROVE"
                ):
                    return False
                ledger_id = qualification_evidence[0].get(
                    "provider_ledger_entry_id"
                )
                ledger = ledger_by_id.get(str(ledger_id))
                if ledger is None:
                    return False
                validate_table_qualification_provider_ledger_entry(
                    entry=ledger,
                    binding=authorization,
                    run_id=str(manifest["run_id"]),
                    attempt=attempts[0],
                )
                used_ledger_ids.add(str(ledger_id))
                workspace_relative = authorization.get(
                    "wb3_workspace_relative_path"
                )
                plan_id = authorization.get("qualification_task_plan_id")
                if (
                    type(workspace_relative) is not str
                    or type(plan_id) is not str
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", plan_id) is None
                    or workspace_relative in used_workspaces
                    or workspace_relative
                    != (
                        cycle_relative + "/invocation_control/"
                        + plan_id.split(":", maxsplit=1)[1]
                    )
                ):
                    return False
                used_workspaces.add(workspace_relative)
                terminals = qualification_remote_egress_terminals(
                    workspace_dir=repo_root / workspace_relative,
                )
                usage_limit = authorization.get(
                    "qualification_usage_policy", {}
                ).get("actual_prompt_tokens_max")
                if (
                    len(terminals) != 1
                    or terminals[0].get("status") != "SUCCEEDED"
                    or terminals[0].get("batch_terminal") is not False
                    or terminals[0].get("qualification_task_plan_id")
                    != plan_id
                    or terminals[0].get("provider_request_body_sha256")
                    != attempts[0].get("request_body_sha256")
                    or terminals[0].get("provider_request_ids")
                    != [attempts[0].get("provider_request_id")]
                    or len(terminals[0].get("egress_marker_ids", [])) != 1
                    or type(usage_limit) is not int
                    or not terminals[0].get("attempt_usages")
                    or type(terminals[0]["attempt_usages"][-1].get(
                        "input_tokens"
                    )) is not int
                    or terminals[0]["attempt_usages"][-1]["input_tokens"]
                    > usage_limit
                ):
                    return False
            actual_workspaces = {
                path.relative_to(repo_root).as_posix()
                for path in invocation_root.iterdir()
                if path.is_dir() and not path.is_symlink()
            }
            if (
                used_ledger_ids != set(ledger_by_id)
                or used_workspaces != actual_workspaces
            ):
                return False
    except (
        KeyError, OSError, RuntimeError, StageASnapshotError, ValueError,
        subprocess.SubprocessError,
    ):
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
    ledger_errors = remaining & POST_SNAPSHOT_LEDGER_ERRORS
    if ledger_errors and ledger_errors != POST_SNAPSHOT_LEDGER_ERRORS:
        return False
    remaining -= ledger_errors
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
        or not _qualification_evidence_append_is_valid(
            repo_root=repo_root,
            missing_artifact_paths=missing,
        )
        or (
            (ledger_errors or any(
                path.startswith("evidence/request_attempts/")
                for path in missing
            ))
            and (
                ledger_errors != POST_SNAPSHOT_LEDGER_ERRORS
                or not _request_ledger_append_is_valid(
                    repo_root=repo_root,
                    missing_artifact_paths=missing,
                )
            )
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
