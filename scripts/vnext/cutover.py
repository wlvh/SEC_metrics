"""Compose the formal release candidate and optional active publication.

The shared state machine builds repository-derived structured Runs, creates one
or three table-review Runs through the same workflow, stops for explicit HUMAN
decisions, freezes the exact Run set, projects the compatibility candidate, and
only then permits the live mode to prepare and commit a publication. Recorded
mode executes the same preparation phases but stops before formal publication.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from sec_http import SecIdentityError, parse_request_log_rows
from sec_http import request_log_manifest_payload
from sec_http import request_log_attempt_id, validate_request_log_manifest
from sec_http import request_log_prefix_bytes
from sec_http import validate_sec_identity

from .ai_adapter import AIAdapterError
from .ai_adapter import api_key_environment_name, api_key_required_error_code
from .ai_adapter import approved_transport_policy
from .ai_adapter import build_approved_transport_adapter
from .ai_adapter import build_recorded_adapter
from .batch_workflow import BatchWorkflowError, build_release_input_plan
from .batch_workflow import create_companyfacts_release_run
from .batch_workflow import create_structural_release_run
from .batch_workflow import validate_planned_request_binding
from .canonical import atomic_write_bytes, atomic_write_json
from .canonical import content_hash, parse_utc_timestamp, sha256_bytes
from .canonical import sha256_file, strict_json_file
from .fault_matrix import FaultMatrixError
from .fault_matrix import resume_formal_publication_fault_matrix
from .fault_matrix import run_cutover_publication_fault_matrix
from .projector import build_projection_manifest, load_release_plan
from .projector import write_projection_batch_manifest
from .projector import write_projection_candidate
from .publication import PublicationView, _commit_initial_publication_chain
from .publication import _commit_publication
from .publication import prepare_publication_bundle
from .publication import prepare_legacy_baseline_predecessor
from .publication import publication_state_snapshot
from .publication import write_latest_run_status
from .publication import _write_cutover_publication_validation_receipt
from .qualification import QualificationError
from .qualification import validate_cutover_qualifications
from .requirements import load_requirement_snapshot
from .run_store import fail_run, load_run_for_status
from .run_store import validate_and_freeze_run, write_validation_receipt
from .review import effective_review_decision
from .specs import parse_spec_document
from .workflow import create_review_run, finalize_reviewed_direct_results


_SEC_CONFIG_PATH = Path("config/sec_config.json")
_REQUEST_LOG_PATH = Path("evidence/requests_log.csv")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_LIVE_STABILITY_TARGET = 3
_LIVE_SEC_STAGE_PATHS = (
    "scripts/00_smoke_test_sec_access.py",
    "scripts/01_resolve_companies.py",
    "scripts/02_inventory_filings.py",
    "scripts/03_companyfacts_inventory.py",
    "scripts/05_fetch_accession_materials.py",
)
_LIVE_SEC_REQUIRED_OUTPUTS = (
    "outputs/company_resolution.csv",
    "outputs/latest_filings_inventory.csv",
    "outputs/accession_materials_inventory.csv",
)
_LIVE_SEC_COMMAND_FIELDS = {
    "argv",
    "duration_ms",
    "error_class",
    "return_code",
    "stderr_sha256",
    "stderr_size",
    "stdout_sha256",
    "stdout_size",
}
_LIVE_SEC_RECEIPT_FIELDS = {
    "commands",
    "executed_at_utc",
    "inventory_artifacts",
    "ledger_after",
    "ledger_before",
    "new_attempts",
    "receipt_id",
    "receipt_type",
    "runtime_bindings",
    "schema_version",
    "status",
}
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_LIVE_AUDIT_RELATIVE_ROOT = Path("outputs/vnext_cutover_audits")
_RELEASE_INPUT_PLAN_FIELDS = {
    "companies",
    "legacy_input_hashes",
    "release_id",
    "release_input_plan_id",
    "schema_version",
    "target_fiscal_year",
}
_LIVE_PLAN_RECEIPT_FIELDS = {
    "receipt_id",
    "receipt_type",
    "release_input_plan_id",
    "release_input_plan_path",
    "release_input_plan_sha256",
    "schema_version",
    "sec_acquisition_receipt_id",
    "sec_acquisition_receipt_path",
    "status",
}
_PREPARED_CUTOVER_FIELDS = {
    "batch_manifest_id",
    "commit_requested_at_utc",
    "expected_pointer_and_mirrors_after",
    "fault_injection_receipt_ids",
    "fault_matrix_id",
    "holdout_receipt_id",
    "initial_publication_id",
    "legacy_invariant_migration_receipt_id",
    "live_attempt_audit_closure_id",
    "live_stability_receipt_id",
    "previous_publication_id",
    "production_freeze_receipt_id",
    "publication_id",
    "publication_validation_receipt_id",
    "qualification_id",
    "receipt_id",
    "receipt_type",
    "release_input_plan_id",
    "schema_version",
    "sec_acquisition_receipt_id",
    "second_layout_receipt_id",
    "staging_parity_receipt_id",
    "status",
}


class CutoverError(RuntimeError):
    """Carry a stable Cutover code and structured recovery context."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Optional[Mapping[str, object]] = None,
    ) -> None:
        """Create one fail-closed workflow error.

        Args:
            code: Stable uppercase machine code.
            message: Concise operator-facing explanation.
            details: Optional JSON-compatible facts and recovery commands.
        """
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else dict(details)


def _sec_stage_environment() -> Dict[str, str]:
    """Return child environment without unrelated model authority.

    Returns:
        Current process environment retaining SEC identity but excluding every
        supported model credential from SEC-only child stages.
    """
    environment = dict(os.environ)
    for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        if name in environment:
            del environment[name]
    return environment


def _require_sha256_identity(*, value: object, field: str) -> str:
    """Validate one required canonical SHA-256 content identity.

    Args:
        value: Candidate ``sha256:<lower-hex>`` identity.
        field: Stable field name used in the failure detail.

    Returns:
        Validated identity text.

    Raises:
        CutoverError: When the identity is absent or malformed.
    """
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise CutoverError(
            code="CUTOVER_EVIDENCE_INCOMPLETE",
            message="Formal Cutover requires a canonical audit identity.",
            details={"field": field},
        )
    return value


def _live_retry_policy() -> Dict[str, object]:
    """Derive the live retry ceiling from the module-owned effective D-01.

    Returns:
        Decision identity, Requirement closure, and exact approved retry count.

    Why:
        A caller-supplied retry limit would create a second transport
        authority. The immutable repository Decision therefore owns both the
        count and its audit identity.
    """
    requirement = load_requirement_snapshot(
        snapshot_dir=(
            _REPOSITORY_ROOT / "requirements" / "ai_first_v3_3_1"
        ),
    )
    policy = approved_transport_policy(requirement=requirement)
    decision = requirement["effective_decisions"]["D-01"]
    return {
        "decision_id": "D-01",
        "decision_record_hash": content_hash(value=decision),
        "requirement_closure_hash": requirement[
            "requirement_closure_hash"
        ],
        "retry_count": policy.retry_count,
    }


def _validate_live_prerequisites(*, repo_root: Path) -> None:
    """Validate both remote identities before source planning or mutation.

    Args:
        repo_root: Fixed physical repository containing SEC configuration.

    Raises:
        CutoverError: With every missing or invalid prerequisite code.
    """
    if (
        repo_root.is_symlink()
        or repo_root.resolve(strict=True)
        != _REPOSITORY_ROOT.resolve(strict=True)
    ):
        raise CutoverError(
            code="LIVE_AUTHORITY_ROOT_MISMATCH",
            message="Live Cutover requires the module-owned repository root.",
        )
    error_codes = []
    try:
        requirement = load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1",
        )
        policy = approved_transport_policy(requirement=requirement)
        api_key_name = api_key_environment_name(policy=policy)
        api_key_error = api_key_required_error_code(policy=policy)
    except (AIAdapterError, ValueError) as error:
        raise CutoverError(
            code="LIVE_TRANSPORT_POLICY_INVALID",
            message="Live Cutover transport policy is invalid.",
        ) from error
    if api_key_name not in os.environ or not os.environ[api_key_name].strip():
        error_codes.append(api_key_error)
    config_path = repo_root / _SEC_CONFIG_PATH
    try:
        config = strict_json_file(path=config_path)
        if not isinstance(config, dict):
            raise CutoverError(
                code="SEC_CONFIGURATION_INVALID",
                message="SEC configuration root must be an object.",
            )
        validate_sec_identity(config=config)
    except SecIdentityError as error:
        error_codes.append(error.code)
    if error_codes:
        raise CutoverError(
            code="LIVE_PREREQUISITES_MISSING",
            message="Live Cutover prerequisites are missing or invalid.",
            details={"error_codes": sorted(error_codes)},
        )


def _validate_live_authority_roots(
    *, repo_root: Path, workspace_dir: Path,
    legacy_snapshot_dir: Path, publication_root: Path,
) -> None:
    """Require the one module-owned live authority graph before any I/O.

    Args:
        repo_root: Candidate semantic and SEC repository authority.
        workspace_dir: Candidate durable Cutover workspace.
        legacy_snapshot_dir: Candidate frozen compatibility snapshot.
        publication_root: Candidate formal pointer and mirror authority.

    Raises:
        CutoverError: When any live root differs lexically from the fixed
        module-owned path or is redirected by a symlink.
    """
    expected = {
        "repo_root": _REPOSITORY_ROOT,
        "workspace_dir": _REPOSITORY_ROOT / "artifacts/vnext/cutover",
        "legacy_snapshot_dir": _REPOSITORY_ROOT / "outputs",
        "publication_root": _REPOSITORY_ROOT,
    }
    actual = {
        "repo_root": repo_root,
        "workspace_dir": workspace_dir,
        "legacy_snapshot_dir": legacy_snapshot_dir,
        "publication_root": publication_root,
    }
    mismatches = sorted(
        field for field in expected if actual[field] != expected[field]
    )
    if mismatches or any(path.is_symlink() for path in actual.values()):
        raise CutoverError(
            code="LIVE_AUTHORITY_ROOT_INVALID",
            message="Live Cutover requires the fixed repository authority.",
            details={"fields": mismatches or ["symlink"]},
        )


def _request_ledger_state(*, repo_root: Path) -> Dict[str, object]:
    """Read one validated append-only request-ledger state.

    Args:
        repo_root: Fixed repository containing the ledger and manifest.

    Returns:
        Exact row sequence plus public manifest identities.
    """
    log_path = repo_root / _REQUEST_LOG_PATH
    validate_request_log_manifest(log_path=log_path)
    log_bytes = log_path.read_bytes()
    text = log_bytes.decode("utf-8")
    manifest = request_log_manifest_payload(log_path=log_path)
    rows = parse_request_log_rows(text=text)
    if (
        sha256_bytes(content=log_bytes) != manifest["content_sha256"]
        or len(rows) != manifest["row_count"]
    ):
        raise CutoverError(
            code="SEC_REQUEST_LEDGER_CHANGED_WHILE_READ",
            message="SEC request ledger changed during one observation.",
        )
    return {
        "rows": rows,
        "row_count": manifest["row_count"],
        "content_sha256": manifest["content_sha256"],
        "text": text,
    }


def _live_acquisition_artifacts(*, repo_root: Path) -> Dict[str, object]:
    """Hash the fixed inventory outputs produced by live SEC stages.

    Args:
        repo_root: Fixed repository containing the refreshed outputs.

    Returns:
        Sorted repository-relative byte bindings.
    """
    paths = [repo_root / relative for relative in _LIVE_SEC_REQUIRED_OUTPUTS]
    concept_root = repo_root / "outputs" / "concept_inventory"
    if concept_root.is_symlink() or not concept_root.is_dir():
        raise CutoverError(
            code="SEC_ACQUISITION_OUTPUT_INVALID",
            message="Company Facts concept inventory is unavailable.",
        )
    paths.extend(sorted(concept_root.glob("*_companyfacts.csv")))
    if len(paths) == len(_LIVE_SEC_REQUIRED_OUTPUTS):
        raise CutoverError(
            code="SEC_ACQUISITION_OUTPUT_INVALID",
            message="Company Facts inventory exact set is empty.",
        )
    artifacts = {}
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise CutoverError(
                code="SEC_ACQUISITION_OUTPUT_INVALID",
                message="A required SEC inventory artifact is unavailable.",
            )
        relative = path.relative_to(repo_root).as_posix()
        artifacts[relative] = {
            "sha256": sha256_file(path=path),
            "size": path.stat().st_size,
        }
    return {relative: artifacts[relative] for relative in sorted(artifacts)}


def _current_python_runtime_binding() -> Dict[str, str]:
    """Bind the executing interpreter bytes without persisting its host path.

    Returns:
        Portable executable name and exact binary SHA-256.

    Raises:
        CutoverError: When the interpreter cannot be resolved to a regular file.
    """
    try:
        executable = Path(sys.executable).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise CutoverError(
            code="SEC_ACQUISITION_RUNTIME_INVALID",
            message="SEC acquisition interpreter is unavailable.",
        ) from error
    if executable.is_symlink() or not executable.is_file():
        raise CutoverError(
            code="SEC_ACQUISITION_RUNTIME_INVALID",
            message="SEC acquisition interpreter is not a regular file.",
        )
    return {
        "name": executable.name,
        "sha256": sha256_file(path=executable),
    }


def _live_sec_attempt_rows(
    *, rows: Sequence[Mapping[str, str]], start: int, end: int,
) -> List[Dict[str, str]]:
    """Project one exact request-ledger slice into acquisition receipt rows.

    Args:
        rows: Current validated append-only request-ledger rows.
        start: Inclusive zero-based row offset before acquisition.
        end: Exclusive zero-based row offset after acquisition.

    Returns:
        Ordered attempt identities and source/artifact metadata used by receipt.
    """
    projected = []
    for row_index in range(start, end):
        row = rows[row_index]
        projected.append({
            "attempt_id": request_log_attempt_id(
                row_index=row_index, row=dict(row),
            ),
            "source_url": row["source_url"],
            "status_code": row["status_code"],
            "error": row["error"],
            "content_sha256": row["content_sha256"],
            "repo_relative_path": row["repo_relative_path"],
            "headers_repo_relative_path": row[
                "headers_repo_relative_path"
            ],
            "accession": row["accession"],
            "document_name": row["document_name"],
        })
    return projected


def _validate_live_sec_acquisition_receipt(
    *, repo_root: Path, receipt: Mapping[str, object]
) -> Dict[str, object]:
    """Mechanically revalidate a reusable live SEC acquisition receipt.

    Args:
        repo_root: Current repository ledger, immutable attempts, and inventory.
        receipt: Content-addressed candidate dependency receipt.

    Returns:
        Plain receipt mapping after exact commands, runtime, ledger prefixes,
        new-attempt set, and inventory artifact bytes are rebuilt.

    Raises:
        CutoverError: When a caller self-signed status is not supported by the
        current append-only SEC authority and exact fixed-stage observations.
    """
    invalid = CutoverError(
        code="SEC_ACQUISITION_RECEIPT_INVALID",
        message="Pinned SEC acquisition receipt cannot be mechanically replayed.",
    )
    if (
        not isinstance(receipt, dict)
        or set(receipt) != _LIVE_SEC_RECEIPT_FIELDS
        or receipt["schema_version"] != 1
        or receipt["receipt_type"] != "LIVE_SEC_ACQUISITION"
        or receipt["status"] != "PASSED"
    ):
        raise invalid
    try:
        parse_utc_timestamp(value=str(receipt["executed_at_utc"]))
    except ValueError as error:
        raise invalid from error
    runtime = receipt["runtime_bindings"]
    if (
        not isinstance(runtime, dict)
        or set(runtime) != {"$PYTHON_CURRENT"}
        or not isinstance(runtime["$PYTHON_CURRENT"], dict)
        or set(runtime["$PYTHON_CURRENT"]) != {"name", "sha256"}
        or type(runtime["$PYTHON_CURRENT"]["name"]) is not str
        or not runtime["$PYTHON_CURRENT"]["name"]
        or Path(runtime["$PYTHON_CURRENT"]["name"]).name
        != runtime["$PYTHON_CURRENT"]["name"]
        or type(runtime["$PYTHON_CURRENT"]["sha256"]) is not str
        or _SHA256_HEX.fullmatch(
            runtime["$PYTHON_CURRENT"]["sha256"]
        ) is None
    ):
        raise invalid
    try:
        current_runtime = _current_python_runtime_binding()
    except CutoverError as error:
        raise invalid from error
    if runtime["$PYTHON_CURRENT"] != current_runtime:
        raise invalid
    commands = receipt["commands"]
    if not isinstance(commands, list) or len(commands) != len(
        _LIVE_SEC_STAGE_PATHS
    ):
        raise invalid
    for command, stage in zip(commands, _LIVE_SEC_STAGE_PATHS):
        if (
            not isinstance(command, dict)
            or set(command) != _LIVE_SEC_COMMAND_FIELDS
            or command["argv"] != ["$PYTHON_CURRENT", stage]
            or type(command["duration_ms"]) is not int
            or command["duration_ms"] < 0
            or command["return_code"] != 0
            or command["error_class"] != ""
            or type(command["stdout_size"]) is not int
            or command["stdout_size"] < 0
            or type(command["stderr_size"]) is not int
            or command["stderr_size"] < 0
            or _SHA256_HEX.fullmatch(str(command["stdout_sha256"])) is None
            or _SHA256_HEX.fullmatch(str(command["stderr_sha256"])) is None
        ):
            raise invalid
    before = receipt["ledger_before"]
    after = receipt["ledger_after"]
    if (
        not isinstance(before, dict)
        or set(before) != {"content_sha256", "row_count"}
        or not isinstance(after, dict)
        or set(after) != {"content_sha256", "row_count"}
        or type(before["row_count"]) is not int
        or type(after["row_count"]) is not int
        or before["row_count"] < 0
        or after["row_count"] <= before["row_count"]
        or _SHA256_HEX.fullmatch(str(before["content_sha256"])) is None
        or _SHA256_HEX.fullmatch(str(after["content_sha256"])) is None
    ):
        raise invalid
    try:
        current = _request_ledger_state(repo_root=repo_root)
        if current["row_count"] < after["row_count"]:
            raise invalid
        before_bytes = request_log_prefix_bytes(
            text=str(current["text"]), row_count=before["row_count"],
        )
        after_bytes = request_log_prefix_bytes(
            text=str(current["text"]), row_count=after["row_count"],
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise invalid from error
    if (
        sha256_bytes(content=before_bytes) != before["content_sha256"]
        or sha256_bytes(content=after_bytes) != after["content_sha256"]
    ):
        raise invalid
    expected_attempts = _live_sec_attempt_rows(
        rows=current["rows"],
        start=before["row_count"],
        end=after["row_count"],
    )
    if (
        receipt["new_attempts"] != expected_attempts
        or len(expected_attempts)
        != after["row_count"] - before["row_count"]
        or receipt["inventory_artifacts"]
        != _live_acquisition_artifacts(repo_root=repo_root)
    ):
        raise invalid
    return dict(receipt)


def _write_sec_acquisition_receipt(
    *, repo_root: Path, workspace_dir: Path, body: Mapping[str, object]
) -> Dict[str, object]:
    """Persist one content-addressed SEC acquisition observation.

    Args:
        repo_root: Fixed repository used to derive a portable receipt path.
        workspace_dir: Cutover-owned durable workspace.
        body: Exact command, ledger, and artifact evidence.

    Returns:
        Receipt identity and repository-relative locator.
    """
    receipt_id = content_hash(value=body)
    receipt = {**body, "receipt_id": receipt_id}
    path = workspace_dir / "receipts" / (
        "sec_acquisition_{}.json".format(
            receipt_id.split(":", maxsplit=1)[1]
        )
    )
    atomic_write_json(path=path, value=receipt)
    try:
        relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as error:
        raise CutoverError(
            code="SEC_ACQUISITION_RECEIPT_PATH_INVALID",
            message="SEC acquisition receipt escaped the repository.",
        ) from error
    return {"receipt_id": receipt_id, "receipt_path": relative}


def _write_workflow_receipt(
    *, workspace_dir: Path, receipt_name: str,
    body: Mapping[str, object]
) -> Dict[str, object]:
    """Persist one immutable content-addressed Cutover workflow receipt.

    Args:
        workspace_dir: Durable repository-owned Cutover workspace.
        receipt_name: Stable lowercase semantic receipt prefix.
        body: Canonical JSON-compatible receipt body without identity.

    Returns:
        Receipt identity, byte hash, and exact filesystem path.
    """
    receipt_id = content_hash(value=body)
    receipt = {**body, "receipt_id": receipt_id}
    path = workspace_dir / "receipts" / "{}_{}.json".format(
        receipt_name, receipt_id.split(":", maxsplit=1)[1],
    )
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise CutoverError(
                code="CUTOVER_RECEIPT_PATH_INVALID",
                message="Cutover receipt path is unsafe.",
            )
        existing = strict_json_file(path=path)
        if not isinstance(existing, dict) or existing != receipt:
            raise CutoverError(
                code="CUTOVER_RECEIPT_BYTES_DIFFER",
                message="Content-addressed Cutover receipt bytes differ.",
            )
    else:
        atomic_write_json(path=path, value=receipt)
    return {
        "receipt_id": receipt_id,
        "receipt_path": str(path),
        "receipt_sha256": sha256_file(path=path),
    }


def _validate_release_input_plan(
    *, plan: Mapping[str, object]
) -> Dict[str, object]:
    """Validate one exact content-addressed release plan mapping.

    Args:
        plan: Candidate plan produced from frozen repository authority.

    Returns:
        Plain exact plan mapping.

    Raises:
        CutoverError: When shape, company exact set, or self-hash differs.
    """
    if (
        set(plan) != _RELEASE_INPUT_PLAN_FIELDS
        or plan["schema_version"] != 1
        or not isinstance(plan["companies"], list)
        or not plan["companies"]
    ):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_INVALID",
            message="Release input plan fields are invalid.",
        )
    body = {
        field: plan[field]
        for field in plan
        if field != "release_input_plan_id"
    }
    if content_hash(value=body) != plan["release_input_plan_id"]:
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_INVALID",
            message="Release input plan identity differs from its bytes.",
        )
    return dict(plan)


def _pin_live_release_input_plan(
    *, repo_root: Path, workspace_dir: Path, plan: Mapping[str, object],
    sec_acquisition: Mapping[str, object],
) -> Dict[str, object]:
    """Persist the first live plan and acquisition as immutable resume state.

    Args:
        repo_root: Repository containing the addressed SEC receipt.
        workspace_dir: Durable live Cutover workspace.
        plan: Complete repository-derived input plan.
        sec_acquisition: Passed live SEC acquisition receipt reference.

    Returns:
        Content-addressed live plan receipt reference.
    """
    validated = _validate_release_input_plan(plan=plan)
    if not {"receipt_id", "receipt_path"}.issubset(sec_acquisition):
        raise CutoverError(
            code="SEC_ACQUISITION_RECEIPT_INVALID",
            message="SEC acquisition receipt reference is incomplete.",
        )
    sec_id = _require_sha256_identity(
        value=sec_acquisition["receipt_id"],
        field="sec_acquisition_receipt_id",
    )
    sec_relative = str(sec_acquisition["receipt_path"])
    sec_path = (repo_root / sec_relative).resolve()
    expected_sec_path = workspace_dir / "receipts" / (
        "sec_acquisition_{}.json".format(
            sec_id.split(":", maxsplit=1)[1]
        )
    )
    try:
        sec_path.relative_to(repo_root.resolve())
    except ValueError as error:
        raise CutoverError(
            code="SEC_ACQUISITION_RECEIPT_INVALID",
            message="SEC acquisition receipt path escaped the repository.",
        ) from error
    if (
        expected_sec_path.is_symlink()
        or sec_path != expected_sec_path.resolve(strict=False)
    ):
        raise CutoverError(
            code="SEC_ACQUISITION_RECEIPT_INVALID",
            message="SEC acquisition receipt path is not Cutover-owned.",
        )
    sec_receipt = _read_workflow_receipt(
        path=sec_path,
        receipt_id=sec_id,
        receipt_type="LIVE_SEC_ACQUISITION",
        status="PASSED",
    )
    _validate_live_sec_acquisition_receipt(
        repo_root=repo_root, receipt=sec_receipt,
    )
    plan_id = str(validated["release_input_plan_id"])
    plan_relative = "inputs/release_input_plan_{}.json".format(
        plan_id.split(":", maxsplit=1)[1]
    )
    plan_path = workspace_dir / plan_relative
    expected = validated
    if plan_path.exists():
        existing = strict_json_file(path=plan_path)
        if not isinstance(existing, dict) or existing != expected:
            raise CutoverError(
                code="RELEASE_INPUT_PLAN_BYTES_DIFFER",
                message="Pinned release input plan bytes differ.",
            )
    else:
        atomic_write_json(path=plan_path, value=expected)
    body = {
        "schema_version": 1,
        "receipt_type": "LIVE_RELEASE_INPUT_PLAN",
        "status": "PINNED",
        "release_input_plan_id": plan_id,
        "release_input_plan_path": plan_relative,
        "release_input_plan_sha256": sha256_file(path=plan_path),
        "sec_acquisition_receipt_id": sec_id,
        "sec_acquisition_receipt_path": sec_relative,
    }
    return _write_workflow_receipt(
        workspace_dir=workspace_dir,
        receipt_name="live_release_input_plan",
        body=body,
    )


def _load_pinned_live_release_input_plan(
    *, repo_root: Path, workspace_dir: Path,
) -> Optional[Dict[str, object]]:
    """Load and revalidate one prior live plan without reacquiring sources.

    Args:
        repo_root: Current append-only ledger and immutable SEC attempts.
        workspace_dir: Durable live Cutover workspace.

    Returns:
        Pinned plan and SEC receipt reference, or ``None`` before first live
        acquisition.

    Raises:
        CutoverError: On ambiguous/tampered state or changed pinned attempts.
    """
    receipt_root = workspace_dir / "receipts"
    if not receipt_root.exists():
        return None
    if receipt_root.is_symlink() or not receipt_root.is_dir():
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_RECEIPT_INVALID",
            message="Pinned release plan receipt root is unsafe.",
        )
    paths = sorted(receipt_root.glob("live_release_input_plan_*.json"))
    if not paths:
        return None
    if len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file():
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_RECEIPT_INVALID",
            message="Pinned release plan receipt is ambiguous or unsafe.",
        )
    payload = strict_json_file(path=paths[0])
    if not isinstance(payload, dict):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_RECEIPT_INVALID",
            message="Pinned release plan receipt root is invalid.",
        )
    receipt = dict(payload)
    if set(receipt) != _LIVE_PLAN_RECEIPT_FIELDS:
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_RECEIPT_INVALID",
            message="Pinned release plan receipt fields differ.",
        )
    _validate_addressed_receipt(
        receipt=receipt, identity_field="receipt_id",
    )
    plan_id = str(receipt["release_input_plan_id"])
    _require_sha256_identity(
        value=plan_id, field="release_input_plan_id",
    )
    expected_relative = "inputs/release_input_plan_{}.json".format(
        plan_id.split(":", maxsplit=1)[1]
    )
    if (
        receipt["schema_version"] != 1
        or receipt["receipt_type"] != "LIVE_RELEASE_INPUT_PLAN"
        or receipt["status"] != "PINNED"
        or receipt["release_input_plan_path"] != expected_relative
        or paths[0].name != "live_release_input_plan_{}.json".format(
            str(receipt["receipt_id"]).split(":", maxsplit=1)[1]
        )
    ):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_RECEIPT_INVALID",
            message="Pinned release plan receipt fields differ.",
        )
    plan_path = workspace_dir / expected_relative
    plan_payload = strict_json_file(path=plan_path)
    if not isinstance(plan_payload, dict):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_INVALID",
            message="Pinned release input plan root is invalid.",
        )
    plan = _validate_release_input_plan(plan=plan_payload)
    if (
        plan["release_input_plan_id"] != plan_id
        or sha256_file(path=plan_path)
        != receipt["release_input_plan_sha256"]
    ):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_INVALID",
            message="Pinned release input plan binding differs.",
        )
    for company in plan["companies"]:
        if not isinstance(company, dict):
            raise CutoverError(
                code="RELEASE_INPUT_PLAN_INVALID",
                message="Pinned company source plan is invalid.",
            )
        for source_field in ("companyfacts_source", "table_source"):
            if source_field in company:
                _source_request_attempt_id(
                    repo_root=repo_root,
                    source=company[source_field],
                    require_immutable=True,
                )
    sec_id = _require_sha256_identity(
        value=receipt["sec_acquisition_receipt_id"],
        field="sec_acquisition_receipt_id",
    )
    sec_relative = str(receipt["sec_acquisition_receipt_path"])
    sec_path = (repo_root / sec_relative).resolve()
    expected_sec_path = workspace_dir / "receipts" / (
        "sec_acquisition_{}.json".format(
            sec_id.split(":", maxsplit=1)[1]
        )
    )
    try:
        sec_path.relative_to(repo_root.resolve())
    except ValueError as error:
        raise CutoverError(
            code="SEC_ACQUISITION_RECEIPT_INVALID",
            message="SEC acquisition receipt path escaped the repository.",
        ) from error
    if (
        expected_sec_path.is_symlink()
        or sec_path != expected_sec_path.resolve(strict=False)
    ):
        raise CutoverError(
            code="SEC_ACQUISITION_RECEIPT_INVALID",
            message="Pinned SEC acquisition receipt path differs.",
        )
    sec_receipt = _read_workflow_receipt(
        path=sec_path,
        receipt_id=sec_id,
        receipt_type="LIVE_SEC_ACQUISITION",
        status="PASSED",
    )
    _validate_live_sec_acquisition_receipt(
        repo_root=repo_root, receipt=sec_receipt,
    )
    return {
        "plan": plan,
        "sec_acquisition": {
            "receipt_id": sec_id,
            "receipt_path": sec_relative,
        },
    }


def _write_staging_parity_receipt(
    *, workspace_dir: Path, staging_dir: Path,
    batch_manifest_id: str, candidate: Mapping[str, object],
    validation_receipt: Mapping[str, object],
) -> Dict[str, object]:
    """Bind the complete pinned candidate and strict compatibility ledger.

    Args:
        workspace_dir: Durable Cutover workspace owning addressed receipts.
        staging_dir: Candidate view after formal publication validation.
        batch_manifest_id: Complete same-period Batch identity.
        candidate: Projector summary for the exact staging view.
        validation_receipt: Formal receipt that validated every artifact.

    Returns:
        Content-addressed ten-company staging parity receipt reference.
    """
    migration_path = (
        staging_dir / "legacy_invariant_migration_receipt.json"
    )
    migration = strict_json_file(path=migration_path)
    if (
        not isinstance(migration, dict)
        or "receipt_id" not in migration
        or "status" not in migration
        or "metric_cells" not in migration
        or "evidence_reconciliations" not in migration
        or "migration_entries" not in migration
        or migration["status"] != "PASS"
        or candidate["compatibility_status"] != "PASS"
        or candidate["batch_manifest_id"] != batch_manifest_id
        or "validation_receipt_id" not in validation_receipt
        or "artifact_hashes" not in validation_receipt
    ):
        raise CutoverError(
            code="STAGING_PARITY_RECEIPT_INVALID",
            message="Pinned staging parity evidence is incomplete.",
        )
    body = {
        "schema_version": 1,
        "receipt_type": "TEN_COMPANY_STAGING_PARITY",
        "status": "PASS",
        "batch_manifest_id": batch_manifest_id,
        "publication_validation_receipt_id": validation_receipt[
            "validation_receipt_id"
        ],
        "legacy_invariant_migration_receipt_id": migration["receipt_id"],
        "legacy_invariant_migration_sha256": sha256_file(
            path=migration_path,
        ),
        "candidate_artifact_hashes": dict(
            validation_receipt["artifact_hashes"]
        ),
        "candidate_summary": dict(candidate),
        "metric_cell_comparisons_hash": content_hash(
            value=migration["metric_cells"],
        ),
        "evidence_reconciliations_hash": content_hash(
            value=migration["evidence_reconciliations"],
        ),
        "legacy_migration_entries_hash": content_hash(
            value=migration["migration_entries"],
        ),
    }
    reference = _write_workflow_receipt(
        workspace_dir=workspace_dir,
        receipt_name="staging_parity",
        body=body,
    )
    return {
        **reference,
        "legacy_invariant_migration_receipt_id": migration["receipt_id"],
    }


def _write_formal_cutover_receipt(
    *, workspace_dir: Path, release_input_plan_id: str,
    batch_manifest_id: str, sec_acquisition_receipt_id: str,
    live_stability_receipt_id: str,
    cutover_qualification: Mapping[str, object],
    staging_parity_receipt_id: str,
    legacy_invariant_migration_receipt_id: str,
    fault_matrix: Mapping[str, object], validation_receipt_id: str,
    initial_publication_id: Optional[str], previous_publication_id: str,
    publication_id: str, active_after: Mapping[str, object],
    committed_at_utc: str,
    live_attempt_audit_closure_id: str,
) -> Dict[str, object]:
    """Persist the PREPARED intent before the official pointer transition.

    Args:
        workspace_dir: Durable Cutover workspace owning addressed receipts.
        release_input_plan_id: Repository-derived ten-company release plan.
        batch_manifest_id: Complete same-period Batch identity.
        sec_acquisition_receipt_id: Live official SEC acquisition identity.
        live_stability_receipt_id: Three-success Reader stability identity.
        cutover_qualification: Freeze, second-layout, and holdout bindings.
        staging_parity_receipt_id: Strict CSV compatibility receipt identity.
        legacy_invariant_migration_receipt_id: Old-path migration ledger.
        fault_matrix: Successful precommit fault-matrix result.
        validation_receipt_id: Formal publication validation identity.
        initial_publication_id: Imported legacy predecessor for a first
            Cutover, otherwise ``None``.
        previous_publication_id: Committed rollback predecessor.
        publication_id: Prepared final publication identity.
        active_after: Isolated committed-chain state expected after official
            commit.
        committed_at_utc: Requested UTC commit timestamp, not an observation.
        live_attempt_audit_closure_id: Portable all-attempt audit identity.

    Returns:
        Content-addressed PREPARED intent receipt reference.
    """
    _require_sha256_identity(
        value=live_attempt_audit_closure_id,
        field="live_attempt_audit_closure_id",
    )
    references = fault_matrix["fault_receipt_references"]
    fault_ids = [
        reference["fault_receipt_id"] for reference in references
    ]
    if (
        fault_matrix["status"] != "PASSED"
        or not fault_ids
        or active_after["active_publication_id"] != publication_id
    ):
        raise CutoverError(
            code="CUTOVER_FINAL_STATE_INVALID",
            message="Formal Cutover final state or fault evidence differs.",
        )
    body = {
        "schema_version": 1,
        "receipt_type": "FORMAL_VNEXT_CUTOVER",
        "status": "PREPARED",
        "commit_requested_at_utc": committed_at_utc,
        "release_input_plan_id": release_input_plan_id,
        "batch_manifest_id": batch_manifest_id,
        "sec_acquisition_receipt_id": sec_acquisition_receipt_id,
        "live_stability_receipt_id": live_stability_receipt_id,
        "live_attempt_audit_closure_id": live_attempt_audit_closure_id,
        "qualification_id": cutover_qualification["qualification_id"],
        "production_freeze_receipt_id": cutover_qualification[
            "production_freeze_receipt_id"
        ],
        "second_layout_receipt_id": cutover_qualification[
            "second_layout"
        ]["receipt_id"],
        "holdout_receipt_id": cutover_qualification[
            "post_freeze_holdout"
        ]["receipt_id"],
        "staging_parity_receipt_id": staging_parity_receipt_id,
        "legacy_invariant_migration_receipt_id": (
            legacy_invariant_migration_receipt_id
        ),
        "fault_matrix_id": fault_matrix["fault_matrix_id"],
        "fault_injection_receipt_ids": fault_ids,
        "publication_validation_receipt_id": validation_receipt_id,
        "initial_publication_id": initial_publication_id,
        "previous_publication_id": previous_publication_id,
        "publication_id": publication_id,
        "expected_pointer_and_mirrors_after": dict(active_after),
    }
    return _write_workflow_receipt(
        workspace_dir=workspace_dir,
        receipt_name="formal_cutover",
        body=body,
    )


def _write_committed_cutover_receipt(
    *,
    workspace_dir: Path,
    prepared_receipt_id: str,
    release_input_plan_id: str,
    batch_manifest_id: str,
    sec_acquisition_receipt_id: str,
    live_stability_receipt_id: str,
    live_attempt_audit_closure_id: str,
    cutover_qualification: Mapping[str, object],
    staging_parity_receipt_id: str,
    legacy_invariant_migration_receipt_id: str,
    fault_matrix: Mapping[str, object],
    validation_receipt_id: str,
    initial_publication_id: Optional[str],
    previous_publication_id: str,
    publication_id: str,
    active_after: Mapping[str, object],
    committed_at_utc: str,
) -> Dict[str, object]:
    """Write PASSED only after the official pointer and mirrors read back.

    Args:
        workspace_dir: Durable official receipt root outside mutable Runs.
        prepared_receipt_id: Immutable PREPARED intent superseded here.
        release_input_plan_id: Repository-derived release plan identity.
        batch_manifest_id: Complete same-period Batch identity.
        sec_acquisition_receipt_id: Live SEC acquisition identity.
        live_stability_receipt_id: Final three-success stability identity.
        live_attempt_audit_closure_id: Portable all-attempt closure identity.
        cutover_qualification: Freeze, second-layout, and holdout bindings.
        staging_parity_receipt_id: Strict compatibility receipt identity.
        legacy_invariant_migration_receipt_id: Old-path migration ledger.
        fault_matrix: Successful exact fault matrix result.
        validation_receipt_id: Formal publication validation identity.
        initial_publication_id: Imported/bootstrap predecessor if first
            Cutover.
        previous_publication_id: Committed rollback predecessor.
        publication_id: Official newly active publication identity.
        active_after: Fresh official pointer and mirror read-back.
        committed_at_utc: Actual requested official commit timestamp.

    Returns:
        Content-addressed PASSED Cutover receipt reference.
    """
    _require_sha256_identity(
        value=live_attempt_audit_closure_id,
        field="live_attempt_audit_closure_id",
    )
    references = fault_matrix["fault_receipt_references"]
    fault_ids = [
        reference["fault_receipt_id"] for reference in references
    ]
    if (
        fault_matrix["status"] != "PASSED"
        or not fault_ids
        or active_after["active_publication_id"] != publication_id
    ):
        raise CutoverError(
            code="CUTOVER_FINAL_STATE_INVALID",
            message="Official Cutover read-back or fault evidence differs.",
        )
    body = {
        "schema_version": 1,
        "receipt_type": "FORMAL_VNEXT_CUTOVER",
        "status": "PASSED",
        "committed_at_utc": committed_at_utc,
        "prepared_receipt_id": prepared_receipt_id,
        "release_input_plan_id": release_input_plan_id,
        "batch_manifest_id": batch_manifest_id,
        "sec_acquisition_receipt_id": sec_acquisition_receipt_id,
        "live_stability_receipt_id": live_stability_receipt_id,
        "live_attempt_audit_closure_id": live_attempt_audit_closure_id,
        "qualification_id": cutover_qualification["qualification_id"],
        "production_freeze_receipt_id": cutover_qualification[
            "production_freeze_receipt_id"
        ],
        "second_layout_receipt_id": cutover_qualification[
            "second_layout"
        ]["receipt_id"],
        "holdout_receipt_id": cutover_qualification[
            "post_freeze_holdout"
        ]["receipt_id"],
        "staging_parity_receipt_id": staging_parity_receipt_id,
        "legacy_invariant_migration_receipt_id": (
            legacy_invariant_migration_receipt_id
        ),
        "fault_matrix_id": fault_matrix["fault_matrix_id"],
        "fault_injection_receipt_ids": fault_ids,
        "publication_validation_receipt_id": validation_receipt_id,
        "initial_publication_id": initial_publication_id,
        "previous_publication_id": previous_publication_id,
        "publication_id": publication_id,
        "active_pointer_and_mirrors_after": dict(active_after),
    }
    return _write_workflow_receipt(
        workspace_dir=workspace_dir,
        receipt_name="formal_cutover_committed",
        body=body,
    )


def _validate_addressed_receipt(
    *, receipt: Mapping[str, object], identity_field: str
) -> None:
    """Recompute one workflow receipt identity from its exact body.

    Args:
        receipt: Parsed addressed receipt including its identity field.
        identity_field: Exact identity field excluded from the body hash.

    Raises:
        CutoverError: When the identity field is absent or self-hash differs.
    """
    if identity_field not in receipt:
        raise CutoverError(
            code="CUTOVER_RECEIPT_INVALID",
            message="Cutover receipt identity field is absent.",
        )
    body = {
        field: receipt[field]
        for field in receipt
        if field != identity_field
    }
    if content_hash(value=body) != receipt[identity_field]:
        raise CutoverError(
            code="CUTOVER_RECEIPT_INVALID",
            message="Cutover receipt identity differs from its bytes.",
        )


def _validate_prepared_cutover_receipt(
    *, receipt: Mapping[str, object], path: Path
) -> None:
    """Validate one exact PREPARED Cutover intent and its addressed path.

    Args:
        receipt: Parsed candidate receipt.
        path: Persisted content-addressed receipt path.

    Raises:
        CutoverError: When fields, identity, status, or filename differ.
    """
    _validate_addressed_receipt(
        receipt=receipt,
        identity_field="receipt_id",
    )
    if (
        set(receipt) != _PREPARED_CUTOVER_FIELDS
        or receipt["schema_version"] != 1
        or receipt["receipt_type"] != "FORMAL_VNEXT_CUTOVER"
        or receipt["status"] != "PREPARED"
        or path.name != "formal_cutover_{}.json".format(
            str(receipt["receipt_id"]).split(":", maxsplit=1)[1]
        )
    ):
        raise CutoverError(
            code="CUTOVER_RECEIPT_INVALID",
            message="PREPARED Cutover receipt fields or path differ.",
        )
    for field in (
        "batch_manifest_id",
        "fault_matrix_id",
        "holdout_receipt_id",
        "legacy_invariant_migration_receipt_id",
        "live_attempt_audit_closure_id",
        "live_stability_receipt_id",
        "production_freeze_receipt_id",
        "publication_validation_receipt_id",
        "qualification_id",
        "release_input_plan_id",
        "sec_acquisition_receipt_id",
        "second_layout_receipt_id",
        "staging_parity_receipt_id",
    ):
        _require_sha256_identity(value=receipt[field], field=field)
    fault_ids = receipt["fault_injection_receipt_ids"]
    if (
        type(fault_ids) is not list
        or not fault_ids
        or len(fault_ids) != len(set(fault_ids))
    ):
        raise CutoverError(
            code="CUTOVER_RECEIPT_INVALID",
            message="PREPARED fault receipt exact set is invalid.",
        )
    for fault_id in fault_ids:
        _require_sha256_identity(
            value=fault_id,
            field="fault_injection_receipt_id",
        )


def _read_workflow_receipt(
    *, path: Path, receipt_id: str, receipt_type: str, status: str
) -> Dict[str, object]:
    """Read and rehash one exact workflow dependency receipt.

    Args:
        path: Expected deterministic receipt locator.
        receipt_id: Expected content-addressed identity.
        receipt_type: Expected semantic receipt type.
        status: Required terminal status.

    Returns:
        Verified receipt mapping.

    Raises:
        CutoverError: When bytes, identity, type, or status differ.
    """
    try:
        payload = strict_json_file(path=path)
    except (OSError, ValueError) as error:
        raise CutoverError(
            code="CUTOVER_DEPENDENCY_RECEIPT_INVALID",
            message="A Cutover dependency receipt is absent or invalid.",
        ) from error
    if not isinstance(payload, dict):
        raise CutoverError(
            code="CUTOVER_DEPENDENCY_RECEIPT_INVALID",
            message="A Cutover dependency receipt root is invalid.",
        )
    receipt = dict(payload)
    _validate_addressed_receipt(
        receipt=receipt,
        identity_field="receipt_id",
    )
    if (
        "receipt_type" not in receipt
        or "status" not in receipt
        or receipt["receipt_id"] != receipt_id
        or receipt["receipt_type"] != receipt_type
        or receipt["status"] != status
    ):
        raise CutoverError(
            code="CUTOVER_DEPENDENCY_RECEIPT_INVALID",
            message="A Cutover dependency receipt binding differs.",
        )
    return receipt


def _complete_prepared_cutover_receipt(
    *,
    receipt_root: Path,
    prepared: Mapping[str, object],
    active_after: Mapping[str, object],
    committed_at_utc: str,
) -> Dict[str, object]:
    """Convert one verified PREPARED intent after official read-back.

    Args:
        receipt_root: Durable official receipt root.
        prepared: Immutable PREPARED receipt bytes.
        active_after: Fresh official pointer and mirror read-back.
        committed_at_utc: Actual requested official commit timestamp.

    Returns:
        Existing or newly written PASSED receipt reference.
    """
    _validate_addressed_receipt(
        receipt=prepared, identity_field="receipt_id",
    )
    if (
        prepared["status"] != "PREPARED"
        or active_after["active_publication_id"]
        != prepared["publication_id"]
        or prepared["expected_pointer_and_mirrors_after"]
        != dict(active_after)
    ):
        raise CutoverError(
            code="CUTOVER_FINAL_STATE_INVALID",
            message="PREPARED intent differs from official active state.",
        )
    _require_sha256_identity(
        value=prepared["live_attempt_audit_closure_id"],
        field="live_attempt_audit_closure_id",
    )
    receipt_dir = receipt_root / "receipts"
    completed = []
    if receipt_dir.is_dir() and not receipt_dir.is_symlink():
        for path in sorted(
            receipt_dir.glob("formal_cutover_committed_*.json")
        ):
            receipt = strict_json_file(path=path)
            if not isinstance(receipt, dict):
                raise CutoverError(
                    code="CUTOVER_RECEIPT_INVALID",
                    message="Committed Cutover receipt root is invalid.",
                )
            _validate_addressed_receipt(
                receipt=receipt, identity_field="receipt_id",
            )
            if (
                receipt["status"] == "PASSED"
                and receipt["prepared_receipt_id"]
                == prepared["receipt_id"]
            ):
                completed.append((path, receipt))
    if len(completed) > 1:
        raise CutoverError(
            code="CUTOVER_RESUME_AMBIGUOUS",
            message="PREPARED intent has multiple PASSED completions.",
        )
    if completed:
        path, receipt = completed[0]
        if (
            receipt["publication_id"] != prepared["publication_id"]
            or receipt["active_pointer_and_mirrors_after"]
            != dict(active_after)
        ):
            raise CutoverError(
                code="CUTOVER_FINAL_STATE_INVALID",
                message="Existing PASSED receipt differs from official state.",
            )
        return {
            "receipt_id": receipt["receipt_id"],
            "receipt_path": str(path),
            "receipt_sha256": sha256_file(path=path),
        }
    body = {
        field: prepared[field]
        for field in prepared
        if field not in {
            "commit_requested_at_utc",
            "expected_pointer_and_mirrors_after",
            "receipt_id",
            "status",
        }
    }
    body.update({
        "status": "PASSED",
        "committed_at_utc": committed_at_utc,
        "prepared_receipt_id": prepared["receipt_id"],
        "active_pointer_and_mirrors_after": dict(active_after),
    })
    return _write_workflow_receipt(
        workspace_dir=receipt_root,
        receipt_name="formal_cutover_committed",
        body=body,
    )


def _receipt_path_for_id(
    *, workspace_dir: Path, prefix: str, receipt_id: str
) -> Path:
    """Resolve one deterministic local workflow receipt locator.

    Args:
        workspace_dir: Cutover workspace owning precommit receipts.
        prefix: Stable receipt filename prefix.
        receipt_id: Content identity used as the filename digest.

    Returns:
        Deterministic receipt path, whether or not it currently exists.
    """
    return workspace_dir / "receipts" / "{}_{}.json".format(
        prefix, receipt_id.split(":", 1)[1],
    )


def _resume_committed_cutover(
    *,
    repo_root: Path,
    workspace_dir: Path,
    publication_root: Path,
    committed_at_utc: str,
) -> Optional[Dict[str, object]]:
    """Resume a crash after official commit without remote work or new CAS.

    Args:
        repo_root: Repository authority used for portable Run read-back.
        workspace_dir: Existing Cutover workspace containing PREPARED intent.
        publication_root: Formal root containing the official active pointer.
        committed_at_utc: UTC observation used only if PASSED was not written.

    Returns:
        Reconstructed successful Cutover result, or ``None`` before commit.
    """
    receipt_dir = workspace_dir / "receipts"
    if receipt_dir.is_symlink() or not receipt_dir.is_dir():
        return None
    state = publication_state_snapshot(publication_root=publication_root)
    active_id = state["active_publication_id"]
    if active_id is None:
        return None
    prepared_matches = []
    for path in sorted(receipt_dir.glob("formal_cutover_*.json")):
        receipt = strict_json_file(path=path)
        if not isinstance(receipt, dict):
            raise CutoverError(
                code="CUTOVER_RECEIPT_INVALID",
                message="PREPARED receipt root is invalid.",
            )
        if (
            "status" in receipt
            and "publication_id" in receipt
            and receipt["status"] == "PREPARED"
            and receipt["publication_id"] == active_id
        ):
            _validate_prepared_cutover_receipt(
                receipt=receipt,
                path=path,
            )
            prepared_matches.append(receipt)
    if not prepared_matches:
        return None
    if len(prepared_matches) != 1:
        raise CutoverError(
            code="CUTOVER_RESUME_AMBIGUOUS",
            message="Official active matches multiple PREPARED intents.",
        )
    prepared = prepared_matches[0]
    view = PublicationView.open(publication_root=publication_root)
    if view.publication_id != active_id:
        raise CutoverError(
            code="CUTOVER_RESUME_READBACK_FAILED",
            message="Pinned PublicationView differs during resume.",
        )
    closure_id = prepared["live_attempt_audit_closure_id"]
    if not isinstance(closure_id, str):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="PREPARED intent lacks portable live audit identity.",
        )
    closure_dir = (
        publication_root / _LIVE_AUDIT_RELATIVE_ROOT
        / closure_id.split(":", 1)[1]
    )
    closure = _verify_live_attempt_audit_closure(
        closure_dir=closure_dir, repo_root=repo_root,
    )
    stability_path = closure_dir / "receipts/live_reader_stability.json"
    stability = strict_json_file(path=stability_path)
    if (
        not isinstance(stability, dict)
        or "stability_receipt_id" not in stability
        or "status" not in stability
        or stability["stability_receipt_id"]
        != prepared["live_stability_receipt_id"]
        or stability["status"] != "PASSED"
    ):
        raise CutoverError(
            code="LIVE_AUDIT_RECEIPT_INVALID",
            message="PREPARED stability receipt binding differs.",
        )
    run_paths = {
        str(binding["run_id"]): closure_dir / str(binding["path"])
        for binding in closure["run_bindings"]
    }
    live_attempts = []
    for attempt in stability["attempts"]:
        item = dict(attempt)
        item["run_dir"] = str(run_paths[str(item["run_id"])])
        live_attempts.append(item)
    batch_path = view.bundle_dir / "internal/batch/batch_manifest.json"
    batch = strict_json_file(path=batch_path)
    portable_closure = strict_json_file(
        path=view.bundle_dir / "internal/closure_manifest.json"
    )
    if (
        not isinstance(batch, dict)
        or "batch_manifest_id" not in batch
        or "release_input_plan_id" not in batch
        or batch["batch_manifest_id"] != prepared["batch_manifest_id"]
        or batch["release_input_plan_id"]
        != prepared["release_input_plan_id"]
        or view.manifest["batch_manifest_id"]
        != prepared["batch_manifest_id"]
        or view.manifest["validation_receipt_id"]
        != prepared["publication_validation_receipt_id"]
        or view.manifest["previous_publication_id"]
        != prepared["previous_publication_id"]
        or not isinstance(portable_closure, dict)
        or "qualification_binding" not in portable_closure
        or not isinstance(portable_closure["qualification_binding"], dict)
    ):
        raise CutoverError(
            code="CUTOVER_RESUME_READBACK_FAILED",
            message="PREPARED publication, Batch, or plan binding differs.",
        )
    qualification = portable_closure["qualification_binding"]
    if (
        "qualification_id" not in qualification
        or "production_freeze_receipt_id" not in qualification
        or "second_layout" not in qualification
        or "post_freeze_holdout" not in qualification
        or not isinstance(qualification["second_layout"], dict)
        or "receipt_id" not in qualification["second_layout"]
        or not isinstance(qualification["post_freeze_holdout"], dict)
        or "receipt_id" not in qualification["post_freeze_holdout"]
        or qualification["qualification_id"]
        != prepared["qualification_id"]
        or qualification["production_freeze_receipt_id"]
        != prepared["production_freeze_receipt_id"]
        or qualification["second_layout"]["receipt_id"]
        != prepared["second_layout_receipt_id"]
        or qualification["post_freeze_holdout"]["receipt_id"]
        != prepared["holdout_receipt_id"]
    ):
        raise CutoverError(
            code="CUTOVER_RESUME_READBACK_FAILED",
            message="PREPARED qualification binding differs from bundle.",
        )
    batch_run_dirs = [
        str(batch_path.parent / str(binding["run_path"]))
        for binding in batch["runs"]
    ]
    sec_path = _receipt_path_for_id(
        workspace_dir=workspace_dir,
        prefix="sec_acquisition",
        receipt_id=str(prepared["sec_acquisition_receipt_id"]),
    )
    staging_path = _receipt_path_for_id(
        workspace_dir=workspace_dir,
        prefix="staging_parity",
        receipt_id=str(prepared["staging_parity_receipt_id"]),
    )
    sec_receipt = _read_workflow_receipt(
        path=sec_path,
        receipt_id=str(prepared["sec_acquisition_receipt_id"]),
        receipt_type="LIVE_SEC_ACQUISITION",
        status="PASSED",
    )
    staging_receipt = _read_workflow_receipt(
        path=staging_path,
        receipt_id=str(prepared["staging_parity_receipt_id"]),
        receipt_type="TEN_COMPANY_STAGING_PARITY",
        status="PASS",
    )
    if (
        "batch_manifest_id" not in staging_receipt
        or "publication_validation_receipt_id" not in staging_receipt
        or "new_attempts" not in sec_receipt
        or staging_receipt["batch_manifest_id"]
        != prepared["batch_manifest_id"]
        or staging_receipt["publication_validation_receipt_id"]
        != prepared["publication_validation_receipt_id"]
        or not isinstance(sec_receipt["new_attempts"], list)
        or not sec_receipt["new_attempts"]
    ):
        raise CutoverError(
            code="CUTOVER_DEPENDENCY_RECEIPT_INVALID",
            message="SEC or staging receipt closure differs.",
        )
    try:
        fault_matrix = resume_formal_publication_fault_matrix(
            receipt_publication_root=publication_root,
            source_publication_root=workspace_dir / "fault_matrix_source",
            fault_workspace_root=(
                workspace_dir / "publication_fault_matrix"
            ),
        )
    except FaultMatrixError as error:
        raise CutoverError(
            code=error.code,
            message="PREPARED fault matrix cannot be revalidated.",
        ) from error
    fault_ids = sorted(
        str(reference["fault_receipt_id"])
        for reference in fault_matrix["fault_receipt_references"]
    )
    if (
        fault_matrix["status"] != "PASSED"
        or fault_matrix["fault_matrix_id"] != prepared["fault_matrix_id"]
        or fault_matrix["successor_publication_id"] != active_id
        or fault_ids != sorted(prepared["fault_injection_receipt_ids"])
    ):
        raise CutoverError(
            code="CUTOVER_DEPENDENCY_RECEIPT_INVALID",
            message="PREPARED fault matrix binding differs.",
        )
    # PASSED is the final fallible write after every referenced dependency and
    # official byte binding has been independently read back.
    passed = _complete_prepared_cutover_receipt(
        receipt_root=publication_root / _LIVE_AUDIT_RELATIVE_ROOT,
        prepared=prepared,
        active_after=state,
        committed_at_utc=committed_at_utc,
    )
    acceptance_evidence = {
        "cutover_receipt_id": passed["receipt_id"],
        "fault_injection_receipt_ids": list(
            prepared["fault_injection_receipt_ids"]
        ),
        "holdout_receipt_id": prepared["holdout_receipt_id"],
        "legacy_invariant_migration_receipt_id": prepared[
            "legacy_invariant_migration_receipt_id"
        ],
        "live_attempt_audit_closure_id": closure_id,
        "production_freeze_receipt_id": prepared[
            "production_freeze_receipt_id"
        ],
        "second_layout_receipt_id": prepared["second_layout_receipt_id"],
        "sec_acquisition_receipt_id": prepared[
            "sec_acquisition_receipt_id"
        ],
        "staging_parity_receipt_id": prepared[
            "staging_parity_receipt_id"
        ],
    }
    pointer_path = publication_root / "outputs/active_publication.json"
    return {
        "mode": "live",
        "status": "PUBLISHED",
        "resumed_after_commit": True,
        "release_input_plan_id": prepared["release_input_plan_id"],
        "batch_manifest_id": prepared["batch_manifest_id"],
        "batch_manifest_path": str(batch_path),
        "staging_dir": str(workspace_dir / "staging"),
        "run_dirs": batch_run_dirs,
        "live_attempts": live_attempts,
        "live_stability_receipt_id": prepared[
            "live_stability_receipt_id"
        ],
        "live_stability_receipt_path": str(stability_path),
        "live_attempt_audit_closure_id": closure_id,
        "live_attempt_audit_closure_path": str(closure_dir),
        "sec_acquisition_receipt_id": prepared[
            "sec_acquisition_receipt_id"
        ],
        "sec_acquisition_receipt_path": str(sec_path),
        "initial_publication_id": prepared["initial_publication_id"],
        "previous_publication_id": prepared["previous_publication_id"],
        "publication_id": prepared["publication_id"],
        "validation_receipt_id": prepared[
            "publication_validation_receipt_id"
        ],
        "committed_pointer": strict_json_file(path=pointer_path),
        "staging_parity_receipt_id": prepared[
            "staging_parity_receipt_id"
        ],
        "staging_parity_receipt_path": str(staging_path),
        "fault_matrix_id": prepared["fault_matrix_id"],
        "cutover_receipt_id": passed["receipt_id"],
        "cutover_receipt_path": passed["receipt_path"],
        "acceptance_evidence": acceptance_evidence,
    }


def _run_live_sec_acquisition(
    *, repo_root: Path, workspace_dir: Path, executed_at_utc: str
) -> Dict[str, object]:
    """Execute the fixed official SEC acquisition and inventory stage chain.

    Args:
        repo_root: Module-owned physical repository.
        workspace_dir: Durable Cutover workspace for the addressed receipt.
        executed_at_utc: Explicit UTC audit timestamp.

    Returns:
        Content-addressed receipt identity and portable path.

    Raises:
        CutoverError: On a nonzero stage, ledger rewrite, or missing inventory.
    """
    before = _request_ledger_state(repo_root=repo_root)
    runtime_bindings = {
        "$PYTHON_CURRENT": _current_python_runtime_binding(),
    }
    commands = []
    for relative in _LIVE_SEC_STAGE_PATHS:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [sys.executable, relative],
                cwd=str(repo_root),
                env=_sec_stage_environment(),
                check=False,
                capture_output=True,
                timeout=7200,
            )
            return_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            error_class = ""
        except (OSError, subprocess.TimeoutExpired) as error:
            return_code = -1
            stdout = b""
            stderr = str(error).encode("utf-8")
            error_class = type(error).__name__
        commands.append(
            {
                "argv": ["$PYTHON_CURRENT", relative],
                "duration_ms": int((time.monotonic() - started) * 1000),
                "return_code": return_code,
                "stdout_sha256": sha256_bytes(content=stdout),
                "stdout_size": len(stdout),
                "stderr_sha256": sha256_bytes(content=stderr),
                "stderr_size": len(stderr),
                "error_class": error_class,
            }
        )
        if return_code != 0:
            body = {
                "schema_version": 1,
                "receipt_type": "LIVE_SEC_ACQUISITION",
                "executed_at_utc": executed_at_utc,
                "status": "FAILED",
                "runtime_bindings": runtime_bindings,
                "commands": commands,
                "ledger_before": {
                    "row_count": before["row_count"],
                    "content_sha256": before["content_sha256"],
                },
            }
            receipt = _write_sec_acquisition_receipt(
                repo_root=repo_root,
                workspace_dir=workspace_dir,
                body=body,
            )
            raise CutoverError(
                code="SEC_ACQUISITION_FAILED",
                message="Official SEC acquisition stage failed closed.",
                details=receipt,
            )
    after = _request_ledger_state(repo_root=repo_root)
    before_rows = before["rows"]
    after_rows = after["rows"]
    if after_rows[:len(before_rows)] != before_rows:
        raise CutoverError(
            code="SEC_REQUEST_LEDGER_PREFIX_CHANGED",
            message="SEC acquisition rewrote the prior request-ledger prefix.",
        )
    new_attempts = _live_sec_attempt_rows(
        rows=after_rows,
        start=len(before_rows),
        end=len(after_rows),
    )
    if not new_attempts:
        raise CutoverError(
            code="SEC_ACQUISITION_NO_ATTEMPTS",
            message="SEC acquisition appended no request attempts.",
        )
    body = {
        "schema_version": 1,
        "receipt_type": "LIVE_SEC_ACQUISITION",
        "executed_at_utc": executed_at_utc,
        "status": "PASSED",
        "runtime_bindings": runtime_bindings,
        "commands": commands,
        "ledger_before": {
            "row_count": before["row_count"],
            "content_sha256": before["content_sha256"],
        },
        "ledger_after": {
            "row_count": after["row_count"],
            "content_sha256": after["content_sha256"],
        },
        "new_attempts": new_attempts,
        "inventory_artifacts": _live_acquisition_artifacts(
            repo_root=repo_root,
        ),
    }
    return _write_sec_acquisition_receipt(
        repo_root=repo_root,
        workspace_dir=workspace_dir,
        body=body,
    )


def _validate_recorded_input(
    *,
    recorded_response_path: Optional[Path],
    recorded_fixture_id: Optional[str],
) -> bytes:
    """Load one explicit immutable response for the offline workflow.

    Args:
        recorded_response_path: Existing regular response JSON file.
        recorded_fixture_id: Non-empty audit identity for those bytes.

    Returns:
        Exact response bytes.
    """
    if recorded_response_path is None or recorded_fixture_id is None:
        raise CutoverError(
            code="RECORDED_RESPONSE_REQUIRED",
            message="Recorded Cutover requires response bytes and fixture ID.",
        )
    if (
        recorded_response_path.is_symlink()
        or not recorded_response_path.is_file()
        or not recorded_fixture_id
    ):
        raise CutoverError(
            code="RECORDED_RESPONSE_INVALID",
            message="Recorded response or fixture identity is invalid.",
        )
    response_bytes = recorded_response_path.read_bytes()
    if not response_bytes:
        raise CutoverError(
            code="RECORDED_RESPONSE_INVALID",
            message="Recorded response bytes are empty.",
        )
    return response_bytes


def _disclosure_spec_path(*, repo_root: Path) -> str:
    """Derive the unique table disclosure from release-plan authority.

    Args:
        repo_root: Repository containing release plan and catalog Specs.

    Returns:
        Portable repository-relative disclosure Spec path.
    """
    release_plan, _release_hash = load_release_plan(repo_root=repo_root)
    release_ids = set(release_plan["migrated_metric_ids"])
    matches = []
    for path in sorted((repo_root / "catalog" / "disclosures").glob("*.md")):
        if path.is_symlink() or not path.is_file():
            raise CutoverError(
                code="DISCLOSURE_SPEC_INVALID",
                message="Disclosure Spec catalog contains an unsafe entry.",
            )
        try:
            front, _body = parse_spec_document(
                text=path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise CutoverError(
                code="DISCLOSURE_SPEC_INVALID",
                message="Disclosure Spec catalog cannot be parsed.",
            ) from error
        if (
            front["kind"] != "disclosure_group"
            or front["source_mode"] != "ai_table"
        ):
            continue
        role_ids = set(front["legacy_projection"]["role_metric_ids"].values())
        if role_ids and role_ids.issubset(release_ids):
            matches.append(path.relative_to(repo_root).as_posix())
    if len(matches) != 1:
        raise CutoverError(
            code="DISCLOSURE_SPEC_AMBIGUOUS",
            message="Release table disclosure Spec is absent or ambiguous.",
        )
    return matches[0]


def _source_request_attempt_id(
    *,
    repo_root: Path,
    source: Mapping[str, object],
    require_immutable: bool,
) -> str:
    """Revalidate a planned source and enforce the formal locator boundary.

    Args:
        repo_root: Repository containing the append-only request ledger.
        source: Release-plan Company Facts or table source identity.
        require_immutable: Whether formal live Cutover is authorized. Recorded
            fixture Runs may retain an explicitly labeled legacy locator, but
            formal preparation cannot consume one.

    Returns:
        Content-addressed request attempt ID.
    """
    try:
        attempt_id = validate_planned_request_binding(
            repo_root=repo_root, source=source,
        )
    except BatchWorkflowError as error:
        raise CutoverError(
            code="SOURCE_LEDGER_BINDING_AMBIGUOUS",
            message="Planned source request binding is invalid or stale.",
        ) from error
    if require_immutable and source["request_locator_kind"] != (
        "IMMUTABLE_ATTEMPT"
    ):
        raise CutoverError(
            code="LIVE_SOURCE_ATTEMPT_INCOMPLETE",
            message=(
                "Live Cutover source lacks a content-addressed immutable "
                "request attempt."
            ),
            details={
                "request_attempt_id": attempt_id,
                "source_url": str(source["source_url"]),
            },
        )
    return attempt_id


def _run_identity(
    *, release_input_plan_id: str, company_id: str, role: str, ordinal: int
) -> str:
    """Derive one stable opaque Run ID from repository-owned coordinates.

    Args:
        release_input_plan_id: Complete source-plan identity.
        company_id: Registry company identity.
        role: Generic structured or review role.
        ordinal: One-based attempt ordinal.

    Returns:
        Valid content-addressed Run identifier.
    """
    identity = content_hash(
        value={
            "release_input_plan_id": release_input_plan_id,
            "company_id": company_id,
            "role": role,
            "ordinal": ordinal,
        }
    ).split(":", maxsplit=1)[1]
    return "run:cutover:" + identity


def _validate_resumed_run_plan(
    *, repo_root: Path, manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]], company: Mapping[str, object],
    plan_id: str, role: str, ordinal: int, execute_live: bool,
    source_key: Optional[str], source_role: Optional[str]
) -> None:
    """Bind an existing workspace Run to the current release source plan.

    Args:
        repo_root: Repository authority for the current request ledger.
        manifest: Reloaded immutable Run manifest.
        records: Reloaded immutable Run record sequence.
        company: Current repository-derived company plan entry.
        plan_id: Current complete release input plan identity.
        role: Run identity role used at creation.
        ordinal: Run identity ordinal used at creation.
        execute_live: Whether immutable request-attempt locators are mandatory.
        source_key: Plan source field, or ``None`` for structural-only Runs.
        source_role: Required SourceReference role when a source exists.

    Raises:
        CutoverError: When a stable workspace name contains a Run from another
        plan or a source no longer matches the plan's current ledger binding.
    """
    expected_run_id = _run_identity(
        release_input_plan_id=plan_id,
        company_id=str(company["company_id"]),
        role=role,
        ordinal=ordinal,
    )
    if manifest["run_id"] != expected_run_id:
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_STALE",
            message="Existing Run belongs to a different release input plan.",
            details={
                "actual_run_id": manifest["run_id"],
                "expected_run_id": expected_run_id,
                "release_input_plan_id": plan_id,
            },
        )
    if source_key is None:
        return
    if source_role is None or source_key not in company:
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_INVALID",
            message="Current Run source-plan coordinates are incomplete.",
        )
    source = company[source_key]
    attempt_id = _source_request_attempt_id(
        repo_root=repo_root,
        source=source,
        require_immutable=execute_live,
    )
    references = [
        record
        for record in records
        if record["record_type"] == "SOURCE_REFERENCE"
        and record["source_role"] == source_role
    ]
    if (
        len(references) != 1
        or references[0]["request_attempt_id"] != attempt_id
        or references[0]["source_url"] != source["source_url"]
        or references[0]["accession"] != source["accession"]
        or references[0]["document_name"] != source["document_name"]
    ):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_STALE",
            message="Existing Run source differs from the current plan.",
            details={
                "expected_request_attempt_id": attempt_id,
                "release_input_plan_id": plan_id,
                "run_id": manifest["run_id"],
            },
        )


def _review_summary(
    *,
    run_dir: Path,
    manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Return substantive and audit identities for one review attempt.

    Args:
        run_dir: Persisted Run directory.
        manifest: Verified Run manifest.
        records: Verified Run record sequence.
        decisions: Verified immutable HUMAN decision chain.

    Returns:
        Attempt, Candidate, Evidence, and ReviewUnit identity summary.
    """
    attempts = [
        record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    candidates = [
        record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
    ]
    evidence = [
        record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
    ]
    units = [
        record
        for record in records
        if record["record_type"] == "REVIEW_UNIT"
    ]
    groups = (attempts, candidates, evidence, units)
    if not all(len(values) == 1 for values in groups):
        raise CutoverError(
            code="READER_ATTEMPT_NOT_REVIEWABLE",
            message="Reader attempt lacks one complete review record graph.",
            details={"run_id": manifest["run_id"], "run_dir": str(run_dir)},
        )
    attempt = attempts[0]
    candidate = candidates[0]
    evidence_check = evidence[0]
    unit = units[0]
    results = sorted(
        (
            dict(record)
            for record in records
            if record["record_type"] == "METRIC_RESULT"
        ),
        key=lambda record: (
            str(record["metric_id"]),
            str(record["scope_key"]),
            str(record["result_id"]),
        ),
    )
    review_path = (
        run_dir / "review" / str(unit["review_unit_hash"]) / "review.md"
    )
    command = " ".join(
        shlex.quote(value)
        for value in (
            "python3",
            "tools/vnext_review.py",
            "decide",
            "--run-dir",
            str(run_dir),
            "--review-unit-hash",
            str(unit["review_unit_hash"]),
            "--decision",
            "APPROVE",
            "--reviewer-id",
            "<human-id>",
            "--decided-at-utc",
            "<UTC>",
            "--reason",
            "<reason>",
        )
    )
    summary = {
        "run_id": manifest["run_id"],
        "run_dir": str(run_dir),
        "attempt_id": attempt["attempt_id"],
        "request_body_sha256": attempt["request_body_sha256"],
        "assistant_output_sha256": attempt["assistant_output_sha256"],
        "raw_response_sha256": attempt["raw_response_sha256"],
        "model_requested": attempt["model_requested"],
        "model_returned": attempt["model_returned"],
        "provider_request_id": attempt["provider_request_id"],
        "error_class": attempt["error_class"],
        "transport_observation_hash": content_hash(
            value=attempt["transport_observation"]
        ),
        "candidate_hash": candidate["candidate_hash"],
        "evidence_check_id": evidence_check["evidence_check_id"],
        "review_unit_hash": unit["review_unit_hash"],
        "review_context_hash": unit["review_context_hash"],
        "rendered_review_hash": unit["rendered_review_hash"],
        "selected_values_locators_claims": dict(candidate["selected"]),
        "required_claims": dict(unit["required_claims"]),
        "metric_results": results,
        "review_path": str(review_path.resolve()),
        "review_command": command,
    }
    if decisions:
        try:
            effective = effective_review_decision(
                review_unit=unit, decisions=decisions,
            )
        except ValueError as error:
            raise CutoverError(
                code="PARALLEL_EFFECTIVE_DECISIONS",
                message="Review decision chain has no unique effective tip.",
                details={"run_id": manifest["run_id"]},
            ) from error
        summary["effective_decision"] = {
            "approval_effect_hash": effective["approval_effect_hash"],
            "approved_claims": dict(effective["approved_claims"]),
            "decision": effective["decision"],
            "review_unit_hash": effective["review_unit_hash"],
        }
    return summary


def _failed_review_summary(
    *,
    run_dir: Path,
    manifest: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    failure_status: str,
) -> Dict[str, object]:
    """Return the portable audit identity of one immutable failed Run.

    Args:
        run_dir: Failed attempt directory used only for operator resumption.
        manifest: Verified terminal FAILED Run manifest.
        records: Verified Run records containing exactly one AI attempt.
        decisions: Verified decision sequence, normally empty for a failure.
        failure_status: Workflow outcome that caused the Run to fail.

    Returns:
        Failed attempt summary with content/audit identities and no payload.
    """
    attempts = [
        record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    if len(attempts) != 1 or manifest["status"] != "FAILED":
        raise CutoverError(
            code="FAILED_READER_RUN_INVALID",
            message="Failed Reader Run lacks one immutable AI attempt.",
            details={"run_id": manifest["run_id"]},
        )
    attempt = attempts[0]
    error_class = str(attempt["error_class"])
    if not error_class:
        error_class = failure_status
    summary = {
        "run_id": manifest["run_id"],
        "run_dir": str(run_dir),
        "attempt_id": attempt["attempt_id"],
        "request_body_sha256": attempt["request_body_sha256"],
        "assistant_output_sha256": attempt["assistant_output_sha256"],
        "raw_response_sha256": attempt["raw_response_sha256"],
        "model_requested": attempt["model_requested"],
        "model_returned": attempt["model_returned"],
        "provider_request_id": attempt["provider_request_id"],
        "error_class": error_class,
        "transport_observation_hash": content_hash(
            value=attempt["transport_observation"]
        ),
        "failure_status": failure_status,
        "status": "FAILED",
        "decision_count": len(decisions),
        "run_content_manifest_hash": manifest["content_manifest_hash"],
        "run_audit_manifest_hash": manifest["audit_manifest_hash"],
    }
    candidates = [
        record
        for record in records
        if record["record_type"] == "OBSERVATION_CANDIDATE"
    ]
    evidence = [
        record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
    ]
    if len(candidates) == 1:
        summary["candidate_hash"] = candidates[0]["candidate_hash"]
    if len(evidence) == 1:
        summary["evidence_check_id"] = evidence[0]["evidence_check_id"]
    return summary


def _failed_status_from_records(
    *, records: Sequence[Mapping[str, object]]
) -> str:
    """Recover the stable workflow failure class from immutable records.

    Args:
        records: Verified records from an already FAILED review Run.

    Returns:
        ``FAILED_ATTEMPT`` or ``EVIDENCE_REJECTED``.
    """
    attempts = [
        record
        for record in records
        if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
    ]
    evidence = [
        record
        for record in records
        if record["record_type"] == "EVIDENCE_CHECK"
    ]
    if len(attempts) == 1 and attempts[0]["status"] == "FAILED":
        return "FAILED_ATTEMPT"
    if len(evidence) == 1 and evidence[0]["status"] == "FAIL":
        return "EVIDENCE_REJECTED"
    raise CutoverError(
        code="FAILED_READER_RUN_INVALID",
        message="Failed Reader Run has no supported terminal failure record.",
    )


def _seal_failed_review_run(
    *, repo_root: Path, run_dir: Path, failure_status: str
) -> Dict[str, object]:
    """Seal one failed Reader attempt before any retry starts.

    Args:
        repo_root: Repository authority used to reload the terminal Run.
        run_dir: OPEN Run that already contains one terminal AI attempt.
        failure_status: Exact workflow failure returned by
            ``create_review_run``.

    Returns:
        Immutable FAILED Run attempt summary.

    Why:
        Reusing an OPEN Run for a retry would collapse multiple provider calls
        into one mutable audit object. Each failure is therefore validated and
        terminally sealed first.
    """
    manifest, records, decisions = load_run_for_status(
        run_dir=run_dir, repo_root=repo_root,
    )
    if manifest["status"] == "OPEN":
        attempts = [
            record
            for record in records
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
        ]
        if len(attempts) != 1:
            raise CutoverError(
                code="FAILED_READER_RUN_INVALID",
                message="Reader failure lacks one auditable AI attempt.",
                details={"run_id": manifest["run_id"]},
            )
        evidence_hash = content_hash(
            value={
                "attempt_id": attempts[0]["attempt_id"],
                "failure_status": failure_status,
                "run_id": manifest["run_id"],
            }
        )
        write_validation_receipt(
            run_dir=run_dir,
            status="FAILED",
            checks=[
                {
                    "check": "READER_" + failure_status,
                    "evidence_hash": evidence_hash,
                    "status": "FAIL",
                }
            ],
        )
        fail_run(run_dir=run_dir)
        manifest, records, decisions = load_run_for_status(
            run_dir=run_dir, repo_root=repo_root,
        )
    if manifest["status"] != "FAILED":
        raise CutoverError(
            code="FAILED_READER_RUN_INVALID",
            message="Reader failure did not reach immutable FAILED state.",
            details={"run_id": manifest["run_id"]},
        )
    return _failed_review_summary(
        run_dir=run_dir,
        manifest=manifest,
        records=records,
        decisions=decisions,
        failure_status=failure_status,
    )


def _freeze_structured_run(
    *,
    repo_root: Path,
    run_dir: Path,
    company: Mapping[str, object],
    plan_id: str,
    execute_live: bool,
) -> Path:
    """Create or resume one mechanically replayed structured release Run.

    Args:
        repo_root: Repository authority for exact source and semantics.
        run_dir: Stable Run directory below the Cutover workspace.
        company: One validated source-plan company entry.
        plan_id: Release input plan identity.
        execute_live: Whether immutable live-attempt locators are mandatory.

    Returns:
        Verified FROZEN Run directory.
    """
    if not run_dir.exists():
        run_id = _run_identity(
            release_input_plan_id=plan_id,
            company_id=str(company["company_id"]),
            role="structured",
            ordinal=1,
        )
        if company["mode"] == "COMPANYFACTS":
            source = company["companyfacts_source"]
            request_attempt_id = _source_request_attempt_id(
                repo_root=repo_root,
                source=source,
                require_immutable=execute_live,
            )
            create_companyfacts_release_run(
                repo_root=repo_root,
                run_dir=run_dir,
                run_id=run_id,
                company_id=str(company["company_id"]),
                target_period=company["target_period"],
                source_repo_relative_path=str(source["repo_relative_path"]),
                source_url=str(source["source_url"]),
                accession=str(source["accession"]),
                document_name=str(source["document_name"]),
                request_attempt_id=request_attempt_id,
            )
        elif company["mode"] == "STRUCTURAL_ONLY":
            create_structural_release_run(
                repo_root=repo_root,
                run_dir=run_dir,
                run_id=run_id,
                company_id=str(company["company_id"]),
                target_period=company["target_period"],
            )
        else:
            raise CutoverError(
                code="RELEASE_INPUT_MODE_INVALID",
                message="Release input plan contains an unsupported mode.",
            )
    manifest, records, _decisions = load_run_for_status(
        run_dir=run_dir, repo_root=repo_root,
    )
    _validate_resumed_run_plan(
        repo_root=repo_root,
        manifest=manifest,
        records=records,
        company=company,
        plan_id=plan_id,
        role="structured",
        ordinal=1,
        execute_live=execute_live,
        source_key=(
            "companyfacts_source"
            if company["mode"] == "COMPANYFACTS"
            else None
        ),
        source_role=(
            "companyfacts" if company["mode"] == "COMPANYFACTS" else None
        ),
    )
    if manifest["status"] == "OPEN":
        manifest = validate_and_freeze_run(
            run_dir=run_dir, repo_root=repo_root,
        )
    if manifest["status"] != "FROZEN":
        raise CutoverError(
            code="STRUCTURED_RUN_NOT_FROZEN",
            message="Structured release Run did not reach FROZEN.",
            details={
                "run_id": manifest["run_id"],
                "status": manifest["status"],
            },
        )
    return run_dir


def _prepare_review_run(
    *,
    repo_root: Path,
    run_dir: Path,
    company: Mapping[str, object],
    plan_id: str,
    stability_ordinal: int,
    attempt_ordinal: int,
    disclosure_spec_path: str,
    execute_live: bool,
    recorded_response_bytes: Optional[bytes],
    recorded_fixture_id: Optional[str],
) -> Dict[str, object]:
    """Create or resume one table-review Run through the D-06 review policy.

    Args:
        repo_root: Repository authority for source, Requirement, and Specs.
        run_dir: Stable attempt directory.
        company: One plan entry carrying an applicable table source.
        plan_id: Complete release input plan identity.
        stability_ordinal: One-based successful stability slot.
        attempt_ordinal: One-based attempt within the D-01 retry budget.
        disclosure_spec_path: Derived disclosure Spec locator.
        execute_live: Whether the approved remote adapter is authorized.
        recorded_response_bytes: Offline response bytes or ``None``.
        recorded_fixture_id: Offline fixture ID or ``None``.

    Returns:
        Verified attempt summary with state and decision count.
    """
    if not run_dir.exists():
        source = company["table_source"]
        if execute_live:
            adapter = build_approved_transport_adapter()
        else:
            if recorded_response_bytes is None or recorded_fixture_id is None:
                raise CutoverError(
                    code="RECORDED_RESPONSE_REQUIRED",
                    message="Recorded review adapter inputs are absent.",
                )
            adapter = build_recorded_adapter(
                response_bytes=recorded_response_bytes,
                fixture_id="{}-{}-{}".format(
                    recorded_fixture_id,
                    stability_ordinal,
                    attempt_ordinal,
                ),
            )
        result = create_review_run(
            repo_root=repo_root,
            run_dir=run_dir,
            run_id=_run_identity(
                release_input_plan_id=plan_id,
                company_id=str(company["company_id"]),
                role="review-stability-{}".format(stability_ordinal),
                ordinal=attempt_ordinal,
            ),
            company_id=str(company["company_id"]),
            target_period=company["target_period"],
            source_repo_relative_path=str(source["repo_relative_path"]),
            source_media_type="text/html",
            source_url=str(source["source_url"]),
            accession=str(source["accession"]),
            document_name=str(source["document_name"]),
            source_role="target_primary",
            request_attempt_id=_source_request_attempt_id(
                repo_root=repo_root,
                source=source,
                require_immutable=execute_live,
            ),
            disclosure_spec_path=disclosure_spec_path,
            adapter=adapter,
            clock=None,
        )
        if result["status"] != "PENDING_HUMAN_REVIEW":
            return _seal_failed_review_run(
                repo_root=repo_root,
                run_dir=run_dir,
                failure_status=str(result["status"]),
            )
    manifest, records, decisions = load_run_for_status(
        run_dir=run_dir, repo_root=repo_root,
    )
    _validate_resumed_run_plan(
        repo_root=repo_root,
        manifest=manifest,
        records=records,
        company=company,
        plan_id=plan_id,
        role="review-stability-{}".format(stability_ordinal),
        ordinal=attempt_ordinal,
        execute_live=execute_live,
        source_key="table_source",
        source_role="target_primary",
    )
    if manifest["status"] == "FAILED":
        return _failed_review_summary(
            run_dir=run_dir,
            manifest=manifest,
            records=records,
            decisions=decisions,
            failure_status=_failed_status_from_records(records=records),
        )
    units = [
        record
        for record in records
        if record["record_type"] == "REVIEW_UNIT"
    ]
    if manifest["status"] == "OPEN" and not units:
        return _seal_failed_review_run(
            repo_root=repo_root,
            run_dir=run_dir,
            failure_status=_failed_status_from_records(records=records),
        )
    summary = _review_summary(
        run_dir=run_dir,
        manifest=manifest,
        records=records,
        decisions=decisions,
    )
    if manifest["status"] == "OPEN":
        results = [
            record
            for record in records
            if record["record_type"] == "METRIC_RESULT"
        ]
        if not results:
            finalize_reviewed_direct_results(
                run_dir=run_dir, repo_root=repo_root,
            )
        manifest = validate_and_freeze_run(
            run_dir=run_dir, repo_root=repo_root,
        )
    if manifest["status"] != "FROZEN":
        raise CutoverError(
            code="REVIEW_RUN_NOT_FROZEN",
            message="Reviewed release Run did not reach FROZEN.",
            details={
                "run_id": manifest["run_id"],
                "status": manifest["status"],
            },
        )
    # Finalization appends Result/Trace bytes, so the stability summary must be
    # rebuilt from the terminal immutable graph rather than its OPEN snapshot.
    manifest, records, decisions = load_run_for_status(
        run_dir=run_dir, repo_root=repo_root,
    )
    summary = _review_summary(
        run_dir=run_dir,
        manifest=manifest,
        records=records,
        decisions=decisions,
    )
    summary["status"] = "FROZEN"
    summary["decision_count"] = len(decisions)
    summary["run_content_manifest_hash"] = manifest[
        "content_manifest_hash"
    ]
    summary["run_audit_manifest_hash"] = manifest["audit_manifest_hash"]
    return summary


def _validate_stability_fields(
    *, attempts: Sequence[Mapping[str, object]], fields: Sequence[str]
) -> None:
    """Compare one explicit exact set of substantive attempt fields.

    Args:
        attempts: Exactly three ordered successful Reader summaries.
        fields: Exact semantic fields required at the current workflow phase.

    Raises:
        CutoverError: When a field is absent or its canonical value differs.
    """
    missing = sorted({
        field
        for attempt in attempts
        for field in fields
        if field not in attempt
    })
    if missing:
        raise CutoverError(
            code="LIVE_READER_STABILITY_INCOMPLETE",
            message="Live attempts lack required substantive semantics.",
            details={"missing_fields": missing},
        )
    expected = {
        field: content_hash(value=attempts[0][field]) for field in fields
    }
    differing = sorted({
        field
        for attempt in attempts[1:]
        for field in fields
        if content_hash(value=attempt[field]) != expected[field]
    })
    if differing:
        raise CutoverError(
            code="LIVE_READER_UNSTABLE",
            message="Live attempts differ in substantive review identity.",
            details={
                "attempt_ids": [attempt["attempt_id"] for attempt in attempts],
                "differing_fields": differing,
            },
        )


def _validate_reader_stability(
    *, attempts: Sequence[Mapping[str, object]]
) -> None:
    """Compare Reader output and ReviewUnit claims before HUMAN completion.

    Args:
        attempts: Exactly three successful Reader summaries.

    Raises:
        CutoverError: When Reader-selected values, locators, or claims differ.
    """
    if len(attempts) != _LIVE_STABILITY_TARGET:
        raise CutoverError(
            code="LIVE_READER_STABILITY_INCOMPLETE",
            message=(
                "Live stability requires exactly three independent attempts."
            ),
        )
    _validate_stability_fields(
        attempts=attempts,
        fields=(
            "candidate_hash",
            "evidence_check_id",
            "review_unit_hash",
            "review_context_hash",
            "rendered_review_hash",
            "request_body_sha256",
            "model_requested",
            "model_returned",
            "selected_values_locators_claims",
            "required_claims",
        ),
    )


def _validate_live_stability(
    *, attempts: Sequence[Mapping[str, object]]
) -> None:
    """Require three live attempts to share the complete business outcome.

    Args:
        attempts: Ordered review summaries for one frozen source and contract.

    Raises:
        CutoverError: When Reader, Result, HUMAN, or compatibility differs.
    """
    _validate_reader_stability(attempts=attempts)
    _validate_stability_fields(
        attempts=attempts,
        fields=(
            "metric_results",
            "effective_decision",
            "strict_compatibility",
        ),
    )


def _live_attempt_receipt_entry(
    *, attempt: Mapping[str, object]
) -> Dict[str, object]:
    """Remove operator paths while retaining one attempt's audit identity.

    Args:
        attempt: Verified Cutover attempt summary with retry coordinates.

    Returns:
        Exact path-free fields safe for a persistent receipt.
    """
    required = (
        "assistant_output_sha256",
        "attempt_id",
        "attempt_ordinal",
        "company_id",
        "decision_count",
        "error_class",
        "model_requested",
        "model_returned",
        "provider_request_id",
        "raw_response_sha256",
        "request_body_sha256",
        "run_id",
        "stability_ordinal",
        "status",
        "transport_observation_hash",
    )
    if any(field not in attempt for field in required):
        raise CutoverError(
            code="LIVE_ATTEMPT_AUDIT_INCOMPLETE",
            message="Live Reader attempt summary lacks audit identity fields.",
        )
    entry = {field: attempt[field] for field in required}
    for field in (
        "candidate_hash",
        "effective_decision",
        "evidence_check_id",
        "failure_status",
        "metric_results",
        "required_claims",
        "review_context_hash",
        "review_unit_hash",
        "rendered_review_hash",
        "run_audit_manifest_hash",
        "run_content_manifest_hash",
        "selected_values_locators_claims",
        "strict_compatibility",
    ):
        if field in attempt:
            entry[field] = attempt[field]
    return entry


def _write_live_stability_receipt(
    *,
    workspace_dir: Path,
    release_input_plan_id: str,
    retry_policy: Mapping[str, object],
    cutover_qualification: Mapping[str, object],
    attempts: Sequence[Mapping[str, object]],
    status: str,
) -> Dict[str, object]:
    """Persist one content-addressed, path-free live attempt receipt.

    Args:
        workspace_dir: Durable Cutover workspace owning receipt storage.
        release_input_plan_id: Exact source-plan identity.
        retry_policy: Repository-derived D-01 audit fields.
        cutover_qualification: Verified second-layout and holdout identities.
        attempts: Every failed and successful attempt in invocation order.
        status: PASSED, pending, unstable, or retry-exhausted conclusion.

    Returns:
        Receipt identity and local path for operator handoff.
    """
    entries = [
        _live_attempt_receipt_entry(attempt=attempt)
        for attempt in attempts
    ]
    successful = [
        entry for entry in entries if entry["status"] != "FAILED"
    ]
    body = {
        "schema_version": 1,
        "receipt_type": "LIVE_READER_STABILITY",
        "release_input_plan_id": release_input_plan_id,
        "retry_policy": dict(retry_policy),
        "cutover_qualification": dict(cutover_qualification),
        "stability_target": _LIVE_STABILITY_TARGET,
        "attempts": entries,
        "successful_attempt_ids": [
            entry["attempt_id"] for entry in successful
        ],
        "status": status,
    }
    receipt = dict(body)
    receipt_id = content_hash(value=body)
    receipt["stability_receipt_id"] = receipt_id
    digest = receipt_id.split(":", maxsplit=1)[1]
    receipt_dir = workspace_dir / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / (
        "live_reader_stability_{}.json".format(digest)
    )
    if receipt_path.exists():
        existing = strict_json_file(path=receipt_path)
        if not isinstance(existing, dict) or existing != receipt:
            raise CutoverError(
                code="LIVE_STABILITY_RECEIPT_COLLISION",
                message="Content-addressed stability receipt bytes differ.",
            )
    else:
        atomic_write_json(path=receipt_path, value=receipt)
    return {
        "stability_receipt_id": receipt_id,
        "stability_receipt_path": str(receipt_path),
    }


def _bind_live_strict_compatibility(
    *,
    workspace_dir: Path,
    staging_dir: Path,
    candidate: Mapping[str, object],
    release_input_plan_id: str,
    retry_policy: Mapping[str, object],
    cutover_qualification: Mapping[str, object],
    attempts: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Bind strict Projector compatibility to every successful live attempt.

    Args:
        workspace_dir: Durable Cutover workspace owning addressed receipts.
        staging_dir: Exact pinned candidate view produced from stable Results.
        candidate: Projector summary for that same candidate view.
        release_input_plan_id: Complete source-plan identity.
        retry_policy: Effective D-01 retry authority.
        cutover_qualification: Verified second-layout and holdout authority.
        attempts: All failed retries and three successful terminal Runs.

    Returns:
        Updated attempt summaries and the final stability receipt reference.

    Why:
        Identical Reader claims alone are insufficient. The final Result graph,
        effective HUMAN outcome, and strict legacy compatibility must remain
        identical before any publication can become pointer-eligible.
    """
    receipt_path = staging_dir / "legacy_invariant_migration_receipt.json"
    compatibility = strict_json_file(path=receipt_path)
    if (
        not isinstance(compatibility, dict)
        or "receipt_id" not in compatibility
        or "status" not in compatibility
        or compatibility["status"] != candidate["compatibility_status"]
    ):
        raise CutoverError(
            code="STRICT_COMPATIBILITY_BINDING_INVALID",
            message=(
                "Pinned strict compatibility receipt differs from staging."
            ),
        )
    strict_binding = {
        "receipt_id": compatibility["receipt_id"],
        "sha256": sha256_file(path=receipt_path),
        "status": compatibility["status"],
    }
    updated = []
    for attempt in attempts:
        item = dict(attempt)
        if item["status"] == "FROZEN":
            item["strict_compatibility"] = dict(strict_binding)
        updated.append(item)
    company_ids = sorted({
        str(attempt["company_id"])
        for attempt in updated
        if attempt["status"] == "FROZEN"
    })
    if not company_ids:
        raise CutoverError(
            code="LIVE_READER_STABILITY_INCOMPLETE",
            message="Strict compatibility has no successful live attempts.",
        )
    for company_id in company_ids:
        successes = [
            attempt
            for attempt in updated
            if attempt["status"] == "FROZEN"
            and attempt["company_id"] == company_id
        ]
        _validate_live_stability(attempts=successes)
    final_receipt = _write_live_stability_receipt(
        workspace_dir=workspace_dir,
        release_input_plan_id=release_input_plan_id,
        retry_policy=retry_policy,
        cutover_qualification=cutover_qualification,
        attempts=updated,
        status="PASSED",
    )
    return {"attempts": updated, **final_receipt}


def _tree_file_records(
    *, source_root: Path, destination_root: Path
) -> List[Dict[str, object]]:
    """Describe every regular file copied from one terminal Run.

    Args:
        source_root: Verified terminal Run directory.
        destination_root: Closure-relative destination directory.

    Returns:
        Sorted path, SHA-256, and size records.

    Raises:
        CutoverError: When a source entry is a symlink or special file.
    """
    if source_root.is_symlink() or not source_root.is_dir():
        raise CutoverError(
            code="LIVE_AUDIT_RUN_INVALID",
            message="Live audit Run root is unavailable or unsafe.",
        )
    records = []
    for source in sorted(source_root.rglob("*")):
        if source.is_symlink() or not (source.is_dir() or source.is_file()):
            raise CutoverError(
                code="LIVE_AUDIT_RUN_INVALID",
                message="Live audit Run contains an unsafe entry.",
            )
        if source.is_dir():
            continue
        relative = destination_root / source.relative_to(source_root)
        records.append({
            "path": relative.as_posix(),
            "sha256": sha256_file(path=source),
            "size": source.stat().st_size,
        })
    if not records:
        raise CutoverError(
            code="LIVE_AUDIT_RUN_INVALID",
            message="Live audit Run exact file set is empty.",
        )
    return records


def _verify_live_attempt_audit_closure(
    *, closure_dir: Path, repo_root: Path
) -> Dict[str, object]:
    """Read back one portable all-attempt closure without its workspace.

    Args:
        closure_dir: Content-addressed audit closure directory.
        repo_root: Repository authority used for terminal Run verification.

    Returns:
        Verified closure manifest.

    Raises:
        CutoverError: On identity, exact-set, byte, Run, or receipt drift.
    """
    if closure_dir.is_symlink() or not closure_dir.is_dir():
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit closure root is unavailable or unsafe.",
        )
    manifest_path = closure_dir / "audit_manifest.json"
    manifest = strict_json_file(path=manifest_path)
    if (
        not isinstance(manifest, dict)
        or "audit_closure_id" not in manifest
        or "attempt_ids" not in manifest
        or "files" not in manifest
        or "run_bindings" not in manifest
        or "stability_receipt_id" not in manifest
    ):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit closure manifest fields are incomplete.",
        )
    body = {
        field: manifest[field]
        for field in manifest
        if field != "audit_closure_id"
    }
    if content_hash(value=body) != manifest["audit_closure_id"]:
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit closure identity differs from its bytes.",
        )
    closure_digest = str(manifest["audit_closure_id"]).split(":", 1)[-1]
    if closure_dir.name != closure_digest:
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit closure directory differs from its identity.",
        )
    expected_files = {
        str(record["path"]): record for record in manifest["files"]
    }
    actual_paths = set()
    for path in closure_dir.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise CutoverError(
                code="LIVE_AUDIT_CLOSURE_INVALID",
                message="Live audit closure contains an unsafe entry.",
            )
        if path.is_file():
            relative = path.relative_to(closure_dir).as_posix()
            if relative != "audit_manifest.json":
                actual_paths.add(relative)
    if actual_paths != set(expected_files):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit closure exact file set differs.",
        )
    for relative in sorted(expected_files):
        path = closure_dir / relative
        record = expected_files[relative]
        if (
            path.stat().st_size != record["size"]
            or sha256_file(path=path) != record["sha256"]
        ):
            raise CutoverError(
                code="LIVE_AUDIT_CLOSURE_INVALID",
                message="Live audit closure file bytes differ.",
            )
    receipt_path = closure_dir / "receipts/live_reader_stability.json"
    receipt = strict_json_file(path=receipt_path)
    receipt_body = {
        field: receipt[field]
        for field in receipt
        if field != "stability_receipt_id"
    } if isinstance(receipt, dict) else {}
    if (
        not isinstance(receipt, dict)
        or "stability_receipt_id" not in receipt
        or "attempts" not in receipt
        or "status" not in receipt
        or receipt["stability_receipt_id"]
        != manifest["stability_receipt_id"]
        or content_hash(value=receipt_body)
        != receipt["stability_receipt_id"]
        or receipt["status"] != "PASSED"
    ):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit stability receipt binding differs.",
        )
    receipt_attempts = receipt["attempts"]
    if not isinstance(receipt_attempts, list) or any(
        not isinstance(attempt, dict)
        or "attempt_id" not in attempt
        or "run_id" not in attempt
        or "status" not in attempt
        for attempt in receipt_attempts
    ):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit attempt records are incomplete.",
        )
    receipt_attempt_ids = [
        str(attempt["attempt_id"]) for attempt in receipt_attempts
    ]
    if (
        receipt_attempt_ids != manifest["attempt_ids"]
        or len(set(receipt_attempt_ids)) != len(receipt_attempt_ids)
    ):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit attempt exact set or order differs.",
        )
    successes = [
        attempt
        for attempt in receipt_attempts
        if attempt["status"] == "FROZEN"
    ]
    failures = [
        attempt
        for attempt in receipt_attempts
        if attempt["status"] == "FAILED"
    ]
    if (
        len(successes) != _LIVE_STABILITY_TARGET
        or len(successes) + len(failures) != len(receipt_attempts)
        or any("failure_status" not in attempt for attempt in failures)
    ):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Live audit terminal attempt states differ.",
        )
    _validate_live_stability(attempts=successes)
    observed_run_ids = set()
    for binding in manifest["run_bindings"]:
        run_dir = closure_dir / str(binding["path"])
        run, _records, _decisions = load_run_for_status(
            run_dir=run_dir, repo_root=repo_root,
        )
        if (
            run["run_id"] != binding["run_id"]
            or run["status"] != binding["status"]
            or run["content_manifest_hash"]
            != binding["content_manifest_hash"]
            or run["audit_manifest_hash"] != binding["audit_manifest_hash"]
        ):
            raise CutoverError(
                code="LIVE_AUDIT_CLOSURE_INVALID",
                message="Portable live Run identity differs.",
            )
        observed_run_ids.add(run["run_id"])
    receipt_run_ids = [
        str(attempt["run_id"]) for attempt in receipt_attempts
    ]
    if (
        observed_run_ids != set(receipt_run_ids)
        or len(observed_run_ids) != len(receipt_run_ids)
        or len(manifest["run_bindings"]) != len(receipt_run_ids)
    ):
        raise CutoverError(
            code="LIVE_AUDIT_CLOSURE_INVALID",
            message="Portable Run and stability receipt exact sets differ.",
        )
    return manifest


def _write_live_attempt_audit_closure(
    *,
    publication_root: Path,
    repo_root: Path,
    attempts: Sequence[Mapping[str, object]],
    stability_receipt_id: str,
    stability_receipt_path: Path,
) -> Dict[str, object]:
    """Copy every live success/retry Run into one addressed durable closure.

    Args:
        publication_root: Formal root owning durable audit storage.
        repo_root: Repository authority used to verify each terminal Run.
        attempts: Every failed retry and successful stability attempt.
        stability_receipt_id: Final complete stability receipt identity.
        stability_receipt_path: Mutable-workspace source receipt path.

    Returns:
        Portable closure identity, locator, and verified manifest.
    """
    receipt = strict_json_file(path=stability_receipt_path)
    receipt_body = {
        field: receipt[field]
        for field in receipt
        if field != "stability_receipt_id"
    } if isinstance(receipt, dict) else {}
    if (
        not isinstance(receipt, dict)
        or "stability_receipt_id" not in receipt
        or "status" not in receipt
        or "attempts" not in receipt
        or receipt["stability_receipt_id"] != stability_receipt_id
        or content_hash(value=receipt_body) != stability_receipt_id
        or receipt["status"] != "PASSED"
    ):
        raise CutoverError(
            code="LIVE_AUDIT_RECEIPT_INVALID",
            message="Final live stability receipt is not portable.",
        )
    successful_attempts = [
        attempt for attempt in attempts if attempt["status"] == "FROZEN"
    ]
    if (
        len(successful_attempts) != _LIVE_STABILITY_TARGET
        or [attempt["attempt_id"] for attempt in attempts]
        != [attempt["attempt_id"] for attempt in receipt["attempts"]]
    ):
        raise CutoverError(
            code="LIVE_AUDIT_ATTEMPT_SET_INVALID",
            message="Portable live audit requires exactly three successes.",
        )
    run_bindings = []
    files = []
    observed_run_ids = set()
    for attempt in attempts:
        run_id = str(attempt["run_id"])
        if run_id in observed_run_ids:
            raise CutoverError(
                code="LIVE_AUDIT_RUN_DUPLICATED",
                message="Live audit Run identity is duplicated.",
            )
        observed_run_ids.add(run_id)
        run_dir = Path(str(attempt["run_dir"]))
        manifest, _records, _decisions = load_run_for_status(
            run_dir=run_dir, repo_root=repo_root,
        )
        if (
            manifest["status"] not in {"FAILED", "FROZEN"}
            or manifest["run_id"] != run_id
            or manifest["status"] != attempt["status"]
            or manifest["content_manifest_hash"]
            != attempt["run_content_manifest_hash"]
            or manifest["audit_manifest_hash"]
            != attempt["run_audit_manifest_hash"]
        ):
            raise CutoverError(
                code="LIVE_AUDIT_RUN_INVALID",
                message="Live audit Run summary differs from immutable bytes.",
            )
        run_key = content_hash(value={"run_id": run_id}).split(":", 1)[1]
        destination = Path("runs") / run_key
        run_bindings.append({
            "audit_manifest_hash": manifest["audit_manifest_hash"],
            "content_manifest_hash": manifest["content_manifest_hash"],
            "path": destination.as_posix(),
            "run_id": run_id,
            "status": manifest["status"],
        })
        files.extend(
            _tree_file_records(
                source_root=run_dir, destination_root=destination,
            )
        )
    receipt_relative = "receipts/live_reader_stability.json"
    files.append({
        "path": receipt_relative,
        "sha256": sha256_file(path=stability_receipt_path),
        "size": stability_receipt_path.stat().st_size,
    })
    body = {
        "schema_version": 1,
        "closure_type": "LIVE_READER_ATTEMPT_AUDIT",
        "stability_receipt_id": stability_receipt_id,
        "attempt_ids": [str(attempt["attempt_id"]) for attempt in attempts],
        "run_bindings": sorted(
            run_bindings, key=lambda binding: str(binding["run_id"]),
        ),
        "files": sorted(files, key=lambda record: str(record["path"])),
    }
    closure_id = content_hash(value=body)
    digest = closure_id.split(":", 1)[1]
    audit_root = publication_root / _LIVE_AUDIT_RELATIVE_ROOT
    if audit_root.is_symlink() or (
        audit_root.exists() and not audit_root.is_dir()
    ):
        raise CutoverError(
            code="LIVE_AUDIT_ROOT_INVALID",
            message="Durable live audit root is unsafe.",
        )
    audit_root.mkdir(parents=True, exist_ok=True)
    destination = audit_root / digest
    manifest = {**body, "audit_closure_id": closure_id}
    if not destination.exists():
        sources = {
            str(attempt["run_id"]): Path(str(attempt["run_dir"]))
            for attempt in attempts
        }
        temporary = audit_root / (".pending-" + uuid.uuid4().hex)
        temporary.mkdir()
        try:
            for binding in body["run_bindings"]:
                shutil.copytree(
                    sources[str(binding["run_id"])],
                    temporary / str(binding["path"]),
                )
            atomic_write_bytes(
                path=temporary / receipt_relative,
                content=stability_receipt_path.read_bytes(),
            )
            atomic_write_json(
                path=temporary / "audit_manifest.json", value=manifest,
            )
            os.replace(temporary, destination)
        except OSError:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
    verified = _verify_live_attempt_audit_closure(
        closure_dir=destination, repo_root=repo_root,
    )
    return {
        "audit_closure_id": closure_id,
        "audit_closure_path": str(destination),
        "audit_closure_locator": (
            _LIVE_AUDIT_RELATIVE_ROOT / digest
        ).as_posix(),
        "manifest": verified,
        "portable_run_paths": {
            str(binding["run_id"]): str(
                destination / str(binding["path"])
            )
            for binding in verified["run_bindings"]
        },
    }


def _prepare_runs(
    *,
    repo_root: Path,
    workspace_dir: Path,
    plan: Mapping[str, object],
    execute_live: bool,
    recorded_response_bytes: Optional[bytes],
    recorded_fixture_id: Optional[str],
    cutover_qualification: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    """Create/resume every release Run through one mode-neutral state machine.

    Args:
        repo_root: Repository authority.
        workspace_dir: Durable Cutover workspace.
        plan: Repository-derived exact company/source plan.
        execute_live: Whether remote Reader execution is authorized.
        recorded_response_bytes: Offline Reader bytes or ``None``.
        recorded_fixture_id: Offline fixture ID or ``None``.
        cutover_qualification: Live-only repository-verified layout evidence.

    Returns:
        Batch Run directories, all Reader attempts, and pending reviews.
    """
    if (
        "companies" not in plan
        or not isinstance(plan["companies"], list)
        or "release_input_plan_id" not in plan
    ):
        raise CutoverError(
            code="RELEASE_INPUT_PLAN_INVALID",
            message="Release input plan fields are incomplete.",
        )
    runs_root = workspace_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    plan_id = str(plan["release_input_plan_id"])
    batch_run_dirs: List[Path] = []
    attempts = []
    pending = []
    semantic_stability_complete = True
    disclosure_path: Optional[str] = None
    retry_policy = _live_retry_policy() if execute_live else None
    if execute_live and cutover_qualification is None:
        raise CutoverError(
            code="CUTOVER_QUALIFICATION_REQUIRED",
            message="Live Cutover qualification evidence is absent.",
        )
    for company in plan["companies"]:
        if not isinstance(company, dict) or "company_id" not in company:
            raise CutoverError(
                code="RELEASE_INPUT_PLAN_INVALID",
                message="Release company plan is invalid.",
            )
        company_id = str(company["company_id"])
        structured_dir = runs_root / (company_id + "-structured")
        batch_run_dirs.append(
            _freeze_structured_run(
                repo_root=repo_root,
                run_dir=structured_dir,
                company=company,
                plan_id=plan_id,
                execute_live=execute_live,
            )
        )
        if "table_source" not in company:
            continue
        if disclosure_path is None:
            disclosure_path = _disclosure_spec_path(repo_root=repo_root)
        company_pending = []
        if not execute_live:
            review_dir = runs_root / (company_id + "-review-1")
            summary = _prepare_review_run(
                repo_root=repo_root,
                run_dir=review_dir,
                company=company,
                plan_id=plan_id,
                stability_ordinal=1,
                attempt_ordinal=1,
                disclosure_spec_path=disclosure_path,
                execute_live=False,
                recorded_response_bytes=recorded_response_bytes,
                recorded_fixture_id=recorded_fixture_id,
            )
            if summary["status"] == "FAILED":
                raise CutoverError(
                    code="RECORDED_READER_ATTEMPT_FAILED",
                    message="Recorded Reader attempt failed without fallback.",
                    details={
                        "attempt_id": summary["attempt_id"],
                        "failure_status": summary["failure_status"],
                        "run_id": summary["run_id"],
                    },
                )
            if summary["status"] == "PENDING_HUMAN_REVIEW":
                blocker = {
                    "run_id": summary["run_id"],
                    "run_dir": summary["run_dir"],
                    "review_unit_hash": summary["review_unit_hash"],
                    "review_path": summary["review_path"],
                    "review_command": summary["review_command"],
                }
                company_pending.append(blocker)
                pending.append(blocker)
            if not company_pending:
                batch_run_dirs.append(Path(str(summary["run_dir"])))
            continue
        if retry_policy is None:
            raise CutoverError(
                code="LIVE_RETRY_POLICY_MISSING",
                message="Live retry policy was not derived from D-01.",
            )
        company_successes = []
        for stability_ordinal in range(1, _LIVE_STABILITY_TARGET + 1):
            success = None
            for attempt_ordinal in range(
                1, int(retry_policy["retry_count"]) + 2
            ):
                review_dir = runs_root / (
                    "{}-review-{}-attempt-{}".format(
                        company_id,
                        stability_ordinal,
                        attempt_ordinal,
                    )
                )
                summary = _prepare_review_run(
                    repo_root=repo_root,
                    run_dir=review_dir,
                    company=company,
                    plan_id=plan_id,
                    stability_ordinal=stability_ordinal,
                    attempt_ordinal=attempt_ordinal,
                    disclosure_spec_path=disclosure_path,
                    execute_live=True,
                    recorded_response_bytes=None,
                    recorded_fixture_id=None,
                )
                summary = dict(summary)
                summary.update(
                    {
                        "attempt_ordinal": attempt_ordinal,
                        "company_id": company_id,
                        "stability_ordinal": stability_ordinal,
                    }
                )
                attempts.append(summary)
                if summary["status"] == "FAILED":
                    continue
                if summary["status"] not in {
                    "FROZEN", "PENDING_HUMAN_REVIEW"
                }:
                    raise CutoverError(
                        code="LIVE_READER_ATTEMPT_STATE_INVALID",
                        message="Live Reader attempt state is unsupported.",
                        details={
                            "run_id": summary["run_id"],
                            "status": summary["status"],
                        },
                    )
                success = summary
                company_successes.append(summary)
                if summary["status"] == "PENDING_HUMAN_REVIEW":
                    blocker = {
                        "run_id": summary["run_id"],
                        "run_dir": summary["run_dir"],
                        "review_unit_hash": summary["review_unit_hash"],
                        "review_path": summary["review_path"],
                        "review_command": summary["review_command"],
                    }
                    company_pending.append(blocker)
                    pending.append(blocker)
                break
            if success is None:
                receipt = _write_live_stability_receipt(
                    workspace_dir=workspace_dir,
                    release_input_plan_id=plan_id,
                    retry_policy=retry_policy,
                    cutover_qualification=cutover_qualification,
                    attempts=attempts,
                    status="FAILED_RETRIES_EXHAUSTED",
                )
                raise CutoverError(
                    code="LIVE_READER_RETRIES_EXHAUSTED",
                    message=(
                        "Live Reader exhausted the D-01 retry budget without "
                        "fallback."
                    ),
                    details={
                        "company_id": company_id,
                        "latest_run_dir": attempts[-1]["run_dir"],
                        "stability_ordinal": stability_ordinal,
                        **receipt,
                    },
                )
        complete_fields = (
            "selected_values_locators_claims",
            "required_claims",
            "metric_results",
            "effective_decision",
        )
        complete_semantics = all(
            field in attempt
            for attempt in company_successes
            for field in complete_fields
        )
        if company_pending:
            _validate_reader_stability(attempts=company_successes)
            semantic_stability_complete = False
        elif complete_semantics:
            try:
                _validate_reader_stability(attempts=company_successes)
                _validate_stability_fields(
                    attempts=company_successes,
                    fields=("metric_results", "effective_decision"),
                )
            except CutoverError as error:
                receipt = _write_live_stability_receipt(
                    workspace_dir=workspace_dir,
                    release_input_plan_id=plan_id,
                    retry_policy=retry_policy,
                    cutover_qualification=cutover_qualification,
                    attempts=attempts,
                    status="FAILED_UNSTABLE",
                )
                details = dict(error.details)
                details["latest_run_dir"] = attempts[-1]["run_dir"]
                details.update(receipt)
                raise CutoverError(
                    code=error.code,
                    message=str(error),
                    details=details,
                ) from error
        else:
            receipt = _write_live_stability_receipt(
                workspace_dir=workspace_dir,
                release_input_plan_id=plan_id,
                retry_policy=retry_policy,
                cutover_qualification=cutover_qualification,
                attempts=attempts,
                status="FAILED_SEMANTICS_INCOMPLETE",
            )
            missing_fields = sorted({
                field
                for attempt in company_successes
                for field in complete_fields
                if field not in attempt
            })
            raise CutoverError(
                code="LIVE_READER_STABILITY_INCOMPLETE",
                message="Terminal live attempts lack required semantics.",
                details={
                    "latest_run_dir": attempts[-1]["run_dir"],
                    "missing_fields": missing_fields,
                    **receipt,
                },
            )
        # Only the first stable Run supplies batch coordinates. The remaining
        # successes and every failed retry stay immutable audit evidence.
        if not company_pending:
            batch_run_dirs.append(
                Path(str(company_successes[0]["run_dir"]))
            )
    receipt = None
    if execute_live:
        if retry_policy is None or not attempts:
            raise CutoverError(
                code="LIVE_READER_STABILITY_INCOMPLETE",
                message="Live Cutover produced no Reader stability attempts.",
            )
        receipt = _write_live_stability_receipt(
            workspace_dir=workspace_dir,
            release_input_plan_id=plan_id,
            retry_policy=retry_policy,
            cutover_qualification=cutover_qualification,
            attempts=attempts,
            status=(
                "STABLE_PENDING_HUMAN_REVIEW"
                if pending
                else "SEMANTICS_STABLE_PENDING_COMPATIBILITY"
                if semantic_stability_complete
                else "PASSED"
            ),
        )
    return {
        "batch_run_dirs": batch_run_dirs,
        "live_attempts": attempts if execute_live else [],
        "pending_reviews": pending,
        "live_stability_receipt_id": (
            receipt["stability_receipt_id"] if receipt is not None else None
        ),
        "live_stability_receipt_path": (
            receipt["stability_receipt_path"] if receipt is not None else None
        ),
        "cutover_qualification": (
            dict(cutover_qualification)
            if cutover_qualification is not None
            else None
        ),
        "semantic_stability_complete": (
            execute_live and not pending and semantic_stability_complete
        ),
        "retry_policy": (
            dict(retry_policy) if retry_policy is not None else None
        ),
    }


def run_cutover(
    *,
    repo_root: Path,
    workspace_dir: Path,
    legacy_snapshot_dir: Path,
    publication_root: Path,
    execute_live: bool,
    recorded_response_path: Optional[Path],
    recorded_fixture_id: Optional[str],
    commit: bool,
    validated_at_utc: str,
    committed_at_utc: Optional[str],
) -> Dict[str, object]:
    """Run the formal preparation state machine and optional live publication.

    Args:
        repo_root: Fixed repository containing source and semantic authority.
        workspace_dir: Durable Runs, BatchManifest, and staging directory.
        legacy_snapshot_dir: Frozen legacy compatibility inputs.
        publication_root: Formal root containing active pointer and mirrors.
        execute_live: Explicit authority for remote Reader and publication.
        recorded_response_path: Offline response path when live is false.
        recorded_fixture_id: Offline response audit identity.
        commit: Whether live mode commits the prepared bundle.
        validated_at_utc: Explicit publication-gate time.
        committed_at_utc: Explicit commit time or ``None`` when not committing.

    Returns:
        Mode, state, Run, Batch, staging, and optional publication identities.
    """
    if type(execute_live) is not bool or type(commit) is not bool:
        raise CutoverError(
            code="CUTOVER_AUTHORITY_INVALID",
            message="Cutover authority flags must be explicit booleans.",
        )
    if execute_live:
        _validate_live_authority_roots(
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            legacy_snapshot_dir=legacy_snapshot_dir,
            publication_root=publication_root,
        )
        if (
            recorded_response_path is not None
            or recorded_fixture_id is not None
        ):
            raise CutoverError(
                code="LIVE_RECORDED_INPUT_FORBIDDEN",
                message="Live Cutover cannot consume a recorded response.",
            )
        _validate_live_prerequisites(repo_root=repo_root)
        try:
            cutover_qualification = validate_cutover_qualifications(
                repo_root=repo_root,
            )
        except QualificationError as error:
            raise CutoverError(
                code=error.code,
                message="Live Cutover qualification failed closed.",
            ) from error
        recorded_bytes = None
    else:
        if commit:
            raise CutoverError(
                code="RECORDED_PUBLICATION_FORBIDDEN",
                message="Recorded Cutover cannot mutate formal publication.",
            )
        recorded_bytes = _validate_recorded_input(
            recorded_response_path=recorded_response_path,
            recorded_fixture_id=recorded_fixture_id,
        )
        cutover_qualification = None
    if workspace_dir.is_symlink() or (
        workspace_dir.exists() and not workspace_dir.is_dir()
    ):
        raise CutoverError(
            code="CUTOVER_WORKSPACE_INVALID",
            message="Cutover workspace must be one real directory.",
        )
    workspace_dir.mkdir(parents=True, exist_ok=True)
    sec_acquisition = (
        _run_live_sec_acquisition(
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            executed_at_utc=validated_at_utc,
        )
        if execute_live else None
    )
    if execute_live and commit and committed_at_utc is not None:
        resumed = _resume_committed_cutover(
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            publication_root=publication_root,
            committed_at_utc=committed_at_utc,
        )
        if resumed is not None:
            resumed["invocation_sec_acquisition_receipt_id"] = (
                sec_acquisition["receipt_id"]
            )
            resumed["invocation_sec_acquisition_receipt_path"] = (
                sec_acquisition["receipt_path"]
            )
            write_latest_run_status(
                publication_root=publication_root,
                repo_root=repo_root,
                latest_run_dir=None,
                latest_publication_id=str(resumed["publication_id"]),
                message=(
                    "已从 official read-back 恢复 Cutover；"
                    "已执行本次 SEC acquisition，未重跑 OpenAI，"
                    "active 未再次切换。"
                ),
                updated_at_utc=committed_at_utc,
            )
            return resumed
    pinned_live_plan = (
        _load_pinned_live_release_input_plan(
            repo_root=repo_root, workspace_dir=workspace_dir,
        )
        if execute_live else None
    )
    if pinned_live_plan is not None:
        plan = pinned_live_plan["plan"]
    else:
        plan = build_release_input_plan(
            repo_root=repo_root, legacy_snapshot_dir=legacy_snapshot_dir,
        )
        # Unit seams may substitute a minimal plan, while the production
        # builder always emits the exact complete shape pinned for HUMAN
        # resume. Never mint resume state from a partial test double.
        if execute_live and set(plan) == _RELEASE_INPUT_PLAN_FIELDS:
            _pin_live_release_input_plan(
                repo_root=repo_root,
                workspace_dir=workspace_dir,
                plan=plan,
                sec_acquisition=sec_acquisition,
            )
    try:
        prepared = _prepare_runs(
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            plan=plan,
            execute_live=execute_live,
            recorded_response_bytes=recorded_bytes,
            recorded_fixture_id=recorded_fixture_id,
            cutover_qualification=cutover_qualification,
        )
    except CutoverError as error:
        if execute_live and "latest_run_dir" in error.details:
            write_latest_run_status(
                publication_root=publication_root,
                repo_root=repo_root,
                latest_run_dir=Path(str(error.details["latest_run_dir"])),
                latest_publication_id=None,
                message=(
                    "更新尝试未发布：live Reader 失败；上一 active 保持不变。"
                ),
                updated_at_utc=validated_at_utc,
            )
        raise
    live_stability_receipt_id = None
    live_stability_receipt_path = None
    if execute_live:
        if (
            "live_stability_receipt_id" not in prepared
            or "live_stability_receipt_path" not in prepared
            or prepared["live_stability_receipt_id"] is None
            or prepared["live_stability_receipt_path"] is None
        ):
            raise CutoverError(
                code="LIVE_STABILITY_RECEIPT_MISSING",
                message="Live Reader attempts lack a persistent receipt.",
            )
        live_stability_receipt_id = prepared[
            "live_stability_receipt_id"
        ]
        live_stability_receipt_path = prepared[
            "live_stability_receipt_path"
        ]
    if prepared["pending_reviews"]:
        details = {
            "release_input_plan_id": plan["release_input_plan_id"],
            "pending_reviews": prepared["pending_reviews"],
            "live_attempts": prepared["live_attempts"],
        }
        if execute_live:
            latest_pending = prepared["pending_reviews"][-1]
            if "run_dir" in latest_pending:
                write_latest_run_status(
                    publication_root=publication_root,
                    repo_root=repo_root,
                    latest_run_dir=Path(str(latest_pending["run_dir"])),
                    latest_publication_id=None,
                    message=(
                        "更新尝试未发布：等待显式 HUMAN Review；"
                        "上一 active 保持不变。"
                    ),
                    updated_at_utc=validated_at_utc,
                )
            details.update(
                {
                    "live_stability_receipt_id": (
                        live_stability_receipt_id
                    ),
                    "live_stability_receipt_path": (
                        live_stability_receipt_path
                    ),
                    "cutover_qualification": cutover_qualification,
                    "sec_acquisition_receipt_id": (
                        sec_acquisition["receipt_id"]
                    ),
                    "sec_acquisition_receipt_path": (
                        sec_acquisition["receipt_path"]
                    ),
                }
            )
        raise CutoverError(
            code="HUMAN_REVIEW_REQUIRED",
            message=(
                "Cutover remains OPEN until explicit HUMAN decisions exist."
            ),
            details=details,
        )
    batch_path = workspace_dir / "batch_manifest.json"
    staging_dir = workspace_dir / "staging"
    batch = write_projection_batch_manifest(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        run_dirs=prepared["batch_run_dirs"],
        release_input_plan_id=str(plan["release_input_plan_id"]),
    )
    candidate = write_projection_candidate(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
    )
    # The Projector manifest is the single proof that candidate and gate
    # bytes were mechanically rebuilt from this exact FROZEN Batch. Persist it
    # before either recorded completion or formal publication validation.
    projection = build_projection_manifest(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
    )
    atomic_write_json(
        path=staging_dir / "projection_manifest.json",
        value=projection,
    )
    live_attempt_audit = None
    live_semantics_verified = (
        execute_live
        and "semantic_stability_complete" in prepared
        and prepared["semantic_stability_complete"] is True
    )
    if live_semantics_verified:
        final_stability = _bind_live_strict_compatibility(
            workspace_dir=workspace_dir,
            staging_dir=staging_dir,
            candidate=candidate,
            release_input_plan_id=str(plan["release_input_plan_id"]),
            retry_policy=prepared["retry_policy"],
            cutover_qualification=cutover_qualification,
            attempts=prepared["live_attempts"],
        )
        prepared["live_attempts"] = final_stability["attempts"]
        live_stability_receipt_id = final_stability[
            "stability_receipt_id"
        ]
        live_stability_receipt_path = final_stability[
            "stability_receipt_path"
        ]
        live_attempt_audit = _write_live_attempt_audit_closure(
            publication_root=publication_root,
            repo_root=repo_root,
            attempts=prepared["live_attempts"],
            stability_receipt_id=str(live_stability_receipt_id),
            stability_receipt_path=Path(str(live_stability_receipt_path)),
        )
        live_stability_receipt_path = str(
            Path(str(live_attempt_audit["audit_closure_path"]))
            / "receipts"
            / "live_reader_stability.json"
        )
        portable_paths = live_attempt_audit["portable_run_paths"]
        portable_attempts = []
        for attempt in prepared["live_attempts"]:
            run_id = str(attempt["run_id"])
            if run_id not in portable_paths:
                raise CutoverError(
                    code="LIVE_AUDIT_CLOSURE_INVALID",
                    message="Portable live Run path is absent.",
                )
            item = dict(attempt)
            item["run_dir"] = portable_paths[run_id]
            portable_attempts.append(item)
        prepared["live_attempts"] = portable_attempts
    common = {
        "mode": "live" if execute_live else "recorded",
        "release_input_plan_id": plan["release_input_plan_id"],
        "batch_manifest_id": batch["batch_manifest_id"],
        "batch_manifest_path": str(batch_path),
        "staging_dir": str(staging_dir),
        "candidate": candidate,
        "projection_manifest_id": projection["projection_manifest_id"],
        "projection_status": projection["publication_candidate_status"],
        "run_dirs": [str(path) for path in prepared["batch_run_dirs"]],
        "live_attempts": prepared["live_attempts"],
        "live_stability_receipt_id": live_stability_receipt_id,
        "live_stability_receipt_path": live_stability_receipt_path,
        "live_attempt_audit_closure_id": (
            live_attempt_audit["audit_closure_id"]
            if live_attempt_audit is not None else None
        ),
        "live_attempt_audit_closure_path": (
            live_attempt_audit["audit_closure_path"]
            if live_attempt_audit is not None else None
        ),
        "cutover_qualification": cutover_qualification,
        "sec_acquisition_receipt_id": (
            sec_acquisition["receipt_id"]
            if sec_acquisition is not None else None
        ),
        "sec_acquisition_receipt_path": (
            sec_acquisition["receipt_path"]
            if sec_acquisition is not None else None
        ),
        "invocation_sec_acquisition_receipt_id": (
            sec_acquisition["receipt_id"]
            if sec_acquisition is not None else None
        ),
        "invocation_sec_acquisition_receipt_path": (
            sec_acquisition["receipt_path"]
            if sec_acquisition is not None else None
        ),
    }
    if (
        candidate["compatibility_status"] != "PASS"
        or projection["publication_candidate_status"] != "PUBLISHABLE"
    ):
        previous_blocked = None
        if execute_live:
            blocked_state = publication_state_snapshot(
                publication_root=publication_root,
            )
            previous_blocked = blocked_state["active_publication_id"]
            successful_attempts = [
                attempt
                for attempt in prepared["live_attempts"]
                if attempt["status"] == "FROZEN"
            ]
            if not successful_attempts:
                raise CutoverError(
                    code="LIVE_READER_STABILITY_INCOMPLETE",
                    message="Blocked candidate has no terminal live Run.",
                )
            write_latest_run_status(
                publication_root=publication_root,
                repo_root=repo_root,
                latest_run_dir=Path(
                    str(successful_attempts[-1]["run_dir"])
                ),
                latest_publication_id=None,
                message=(
                    "更新尝试未发布：strict compatibility BLOCKED；"
                    "上一 active 保持不变。"
                ),
                updated_at_utc=validated_at_utc,
            )
        return {
            **common,
            "status": "BLOCKED",
            "previous_publication_id": previous_blocked,
            "publication_id": None,
            "validation_receipt_id": None,
            "committed_pointer": None,
        }
    if not execute_live:
        return {
            **common,
            "status": "PASSED_RECORDED_ONLY",
            "previous_publication_id": None,
            "publication_id": None,
            "validation_receipt_id": None,
            "committed_pointer": None,
        }
    if commit:
        if (
            not live_semantics_verified
            or not isinstance(live_attempt_audit, dict)
            or "audit_closure_id" not in live_attempt_audit
        ):
            raise CutoverError(
                code="CUTOVER_EVIDENCE_INCOMPLETE",
                message=(
                    "Formal commit requires verified live semantics and "
                    "portable attempt audit closure."
                ),
            )
        _require_sha256_identity(
            value=live_attempt_audit["audit_closure_id"],
            field="live_attempt_audit_closure_id",
        )
    state = publication_state_snapshot(publication_root=publication_root)
    previous = state["active_publication_id"]
    initial_publication_id = None
    first_cutover_uses_imported_legacy = previous is None
    if first_cutover_uses_imported_legacy:
        legacy_predecessor = prepare_legacy_baseline_predecessor(
            publication_root=publication_root,
            repo_root=repo_root,
            legacy_root=repo_root,
        )
        initial_publication_id = legacy_predecessor["publication_id"]
        previous = str(initial_publication_id)
    receipt = _write_cutover_publication_validation_receipt(
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
        previous_publication_id=previous,
        validated_at_utc=validated_at_utc,
    )
    publication = prepare_publication_bundle(
        publication_root=publication_root,
        repo_root=repo_root,
        batch_manifest_path=batch_path,
        legacy_snapshot_dir=legacy_snapshot_dir,
        staging_dir=staging_dir,
        previous_publication_id=previous,
    )
    if live_semantics_verified:
        write_latest_run_status(
            publication_root=publication_root,
            repo_root=repo_root,
            latest_run_dir=None,
            latest_publication_id=str(publication["publication_id"]),
            message=(
                "更新尝试尚未发布：formal candidate 已准备；"
                "上一 active 保持不变。"
            ),
            updated_at_utc=validated_at_utc,
        )
    staging_parity = _write_staging_parity_receipt(
        workspace_dir=workspace_dir,
        staging_dir=staging_dir,
        batch_manifest_id=str(batch["batch_manifest_id"]),
        candidate=candidate,
        validation_receipt=receipt,
    )
    pointer = None
    fault_matrix = None
    cutover_receipt = None
    acceptance_evidence = None
    status = "PREPARED"
    if commit:
        if committed_at_utc is None:
            raise CutoverError(
                code="PUBLICATION_COMMIT_TIME_REQUIRED",
                message="Formal publication commit requires a UTC timestamp.",
            )
        try:
            fault_matrix = run_cutover_publication_fault_matrix(
                repo_root=repo_root,
                cutover_workspace_dir=workspace_dir,
                legacy_snapshot_dir=legacy_snapshot_dir,
                prepared_successor_publication_id=str(
                    publication["publication_id"]
                ),
                executed_at_utc=committed_at_utc,
            )
        except FaultMatrixError as error:
            raise CutoverError(
                code=error.code,
                message="Formal precommit publication fault matrix failed.",
            ) from error
        if (
            sec_acquisition is None
            or live_stability_receipt_id is None
            or cutover_qualification is None
            or fault_matrix is None
        ):
            raise CutoverError(
                code="CUTOVER_EVIDENCE_INCOMPLETE",
                message="Formal Cutover evidence is incomplete before commit.",
            )
        # The retained matrix source is a fully committed isolated A -> B
        # chain. Its read-back predicts the exact official post-CAS mirrors,
        # allowing every fallible receipt write to finish before mutation.
        active_after = publication_state_snapshot(
            publication_root=workspace_dir / "fault_matrix_source",
        )
        prepared_cutover_receipt = _write_formal_cutover_receipt(
            workspace_dir=workspace_dir,
            release_input_plan_id=str(plan["release_input_plan_id"]),
            batch_manifest_id=str(batch["batch_manifest_id"]),
            sec_acquisition_receipt_id=str(
                sec_acquisition["receipt_id"]
            ),
            live_stability_receipt_id=str(live_stability_receipt_id),
            cutover_qualification=cutover_qualification,
            staging_parity_receipt_id=str(
                staging_parity["receipt_id"]
            ),
            legacy_invariant_migration_receipt_id=str(
                staging_parity[
                    "legacy_invariant_migration_receipt_id"
                ]
            ),
            fault_matrix=fault_matrix,
            validation_receipt_id=str(receipt["validation_receipt_id"]),
            initial_publication_id=(
                str(initial_publication_id)
                if initial_publication_id is not None else None
            ),
            previous_publication_id=str(previous),
            publication_id=str(publication["publication_id"]),
            active_after=active_after,
            committed_at_utc=committed_at_utc,
            live_attempt_audit_closure_id=str(
                live_attempt_audit["audit_closure_id"]
            ),
        )
        if first_cutover_uses_imported_legacy:
            chain = _commit_initial_publication_chain(
                publication_root=publication_root,
                legacy_predecessor_publication_id=str(
                    initial_publication_id
                ),
                successor_publication_id=str(publication["publication_id"]),
                committed_at_utc=committed_at_utc,
            )
            pointer = chain["active_pointer"]
        else:
            if initial_publication_id is not None:
                _commit_publication(
                    publication_root=publication_root,
                    publication_id=str(initial_publication_id),
                    expected_active_publication_id=None,
                    committed_at_utc=committed_at_utc,
                )
            pointer = _commit_publication(
                publication_root=publication_root,
                publication_id=str(publication["publication_id"]),
                expected_active_publication_id=previous,
                committed_at_utc=committed_at_utc,
            )
        # Only a fresh official read-back can convert PREPARED into PASSED.
        official_active_after = publication_state_snapshot(
            publication_root=publication_root,
        )
        if official_active_after != active_after:
            raise CutoverError(
                code="CUTOVER_FINAL_STATE_INVALID",
                message=(
                    "Official pointer and mirrors differ from precommit proof."
                ),
            )
        cutover_receipt = _write_committed_cutover_receipt(
            workspace_dir=publication_root / _LIVE_AUDIT_RELATIVE_ROOT,
            prepared_receipt_id=str(
                prepared_cutover_receipt["receipt_id"]
            ),
            release_input_plan_id=str(plan["release_input_plan_id"]),
            batch_manifest_id=str(batch["batch_manifest_id"]),
            sec_acquisition_receipt_id=str(
                sec_acquisition["receipt_id"]
            ),
            live_stability_receipt_id=str(live_stability_receipt_id),
            live_attempt_audit_closure_id=str(
                live_attempt_audit["audit_closure_id"]
            ),
            cutover_qualification=cutover_qualification,
            staging_parity_receipt_id=str(staging_parity["receipt_id"]),
            legacy_invariant_migration_receipt_id=str(
                staging_parity[
                    "legacy_invariant_migration_receipt_id"
                ]
            ),
            fault_matrix=fault_matrix,
            validation_receipt_id=str(receipt["validation_receipt_id"]),
            initial_publication_id=(
                str(initial_publication_id)
                if initial_publication_id is not None else None
            ),
            previous_publication_id=str(previous),
            publication_id=str(publication["publication_id"]),
            active_after=official_active_after,
            committed_at_utc=committed_at_utc,
        )
        acceptance_evidence = {
            "cutover_receipt_id": cutover_receipt["receipt_id"],
            "fault_injection_receipt_ids": [
                reference["fault_receipt_id"]
                for reference in fault_matrix[
                    "fault_receipt_references"
                ]
            ],
            "holdout_receipt_id": cutover_qualification[
                "post_freeze_holdout"
            ]["receipt_id"],
            "legacy_invariant_migration_receipt_id": staging_parity[
                "legacy_invariant_migration_receipt_id"
            ],
            "live_attempt_audit_closure_id": live_attempt_audit[
                "audit_closure_id"
            ],
            "production_freeze_receipt_id": cutover_qualification[
                "production_freeze_receipt_id"
            ],
            "second_layout_receipt_id": cutover_qualification[
                "second_layout"
            ]["receipt_id"],
            "sec_acquisition_receipt_id": sec_acquisition["receipt_id"],
            "staging_parity_receipt_id": staging_parity["receipt_id"],
        }
        if live_semantics_verified:
            write_latest_run_status(
                publication_root=publication_root,
                repo_root=repo_root,
                latest_run_dir=None,
                latest_publication_id=str(publication["publication_id"]),
                message="最新 formal publication 已发布并完成官方 read-back。",
                updated_at_utc=committed_at_utc,
            )
        status = "PUBLISHED"
    return {
        **common,
        "status": status,
        "initial_publication_id": initial_publication_id,
        "previous_publication_id": previous,
        "publication_id": publication["publication_id"],
        "validation_receipt_id": receipt["validation_receipt_id"],
        "committed_pointer": pointer,
        "staging_parity_receipt_id": staging_parity["receipt_id"],
        "staging_parity_receipt_path": staging_parity["receipt_path"],
        "fault_matrix_id": (
            fault_matrix["fault_matrix_id"]
            if fault_matrix is not None else None
        ),
        "cutover_receipt_id": (
            cutover_receipt["receipt_id"]
            if cutover_receipt is not None else None
        ),
        "cutover_receipt_path": (
            cutover_receipt["receipt_path"]
            if cutover_receipt is not None else None
        ),
        "acceptance_evidence": acceptance_evidence,
    }
