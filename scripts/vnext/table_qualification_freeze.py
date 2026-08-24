"""Freeze the table-family qualification authority without live egress.

The module binds WB-3 invocation protections, WB-4 compact transport
measurements, WB-5 scope semantics, WB-6 single-table task contracts, and the
unchanged R2 active/root state.  It writes only a content-addressed freeze
receipt and an empty qualification-cycle provider ledger; it never fetches SEC
bytes or invokes a model provider.
"""

from __future__ import annotations

import ast
import copy
import csv
import inspect
import json
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .ai_adapter import _open_provider_request, approved_transport_policy
from .ai_adapter import build_provider_request_body
from .canonical import atomic_write_json, canonical_json_bytes, content_hash
from .canonical import parse_utc_timestamp, sha256_bytes, sha256_file
from .canonical import strict_json_file
from .invocation_control import effective_invocation_policy
from .provider_runtime import estimate_context_tokens
from .provider_runtime import load_provider_runtime_authority
from .reader_input import READER_SYSTEM_CONTRACT
from .reader_input import build_reader_input_manifest, build_reader_payload
from .requirements import ISSUE_15_D07_EFFECTIVE_CHOICE
from .requirements import load_requirement_snapshot
from .scope_contract import scope_contract_hash, validate_scope_contract
from .table_grid import build_table_grid, TableGridError
from .table_payload import compact_payload_receipt
from .table_payload import DECODER_SEMANTIC_VERSION
from .table_payload import TABLE_PAYLOAD_SERIALIZATION_VERSION
from .table_task_contracts import load_table_task_contracts
from .table_task_contracts import RESOURCE_LIMIT_ESTIMATE
from .table_task_contracts import resolve_table_task_contract
from .table_task_contracts import TableTaskContractFamilyError
from .table_task_contracts import TableTaskContractError
from .table_task_contracts import table_task_execution_plan


MATRIX_PATH = Path("config/table_qualification_matrix.json")
FREEZE_POINTER_PATH = Path("config/table_qualification_freeze.json")
FREEZE_ROOT = Path("artifacts/vnext/table_qualification_freeze")
FREEZE_RECEIPT_ROOT = FREEZE_ROOT / "receipts"
FREEZE_CYCLE_ROOT = FREEZE_ROOT / "cycles"
MARRIOTT_PROVENANCE_PATH = Path(
    "fixtures/vnext/recorded/marriott_2025_fixture_provenance.json"
)
LAYOUT_FIXTURE_ROOT = Path("fixtures/vnext/layouts")
MATRIX_FIELDS = {"families", "requirement_id", "schema_version"}
MATRIX_ENTRY_FIELDS = {
    "development_source",
    "expected_claims",
    "expected_locator_range",
    "expected_output_status",
    "family_id",
    "fresh_samples_required",
    "materially_different_criteria",
    "negative_cases",
    "post_freeze_holdout_source",
    "reader_contract_id",
    "review_policy",
    "second_layout_policy",
    "second_layout_source",
    "source_media_type",
    "task_contract_ids",
    "target_period",
    "token_context_limits",
}
LOCATOR_RANGE_FIELDS = {
    "column_index_min",
    "row_index_min",
    "selected_competing_scope_evidence",
    "table_selection",
}
TOKEN_LIMIT_FIELDS = {"max_estimated_input_tokens", "maximum_context_tokens"}
IMMUTABLE_SOURCE_FIELDS = {
    "accession",
    "cik",
    "company_id",
    "document_name",
    "source_kind",
    "source_repo_relative_path",
    "source_sha256",
}
FUTURE_SOURCE_FIELDS = {
    "cik", "company_id", "fiscal_year", "form", "source_kind",
}
FIXTURE_SOURCE_FIELDS = {"fixture_id", "source_kind"}
POINTER_FIELDS = {
    "qualification_cycle_id",
    "receipt_id",
    "receipt_path",
    "schema_version",
}
RECEIPT_FIELDS = {
    "d07_decision_required",
    "freeze_commit",
    "frozen_at_utc",
    "identity",
    "monetary_policy",
    "protected_closure",
    "provider_state",
    "qualification_cycle_id",
    "live_ready_family_ids",
    "readiness_by_family",
    "record_type",
    "schema_version",
    "table_qualification_freeze_receipt_id",
    "wb3_protection",
    "wb4_compact_transport",
    "wb5_scope_contract",
    "wb6_task_contracts",
}
FAMILY_READINESS_FIELDS = {
    "blocking_reason_codes",
    "context_gate",
    "live_ready",
    "protected_closure_gate",
    "resource_gate",
}
CONTEXT_GATE_FIELDS = {
    "blocking_measurement_ids",
    "max_estimated_input_tokens",
    "maximum_observed_estimated_input_tokens",
    "status",
    "threshold_comparison",
}
RESOURCE_GATE_FIELDS = {"blocking_measurement_ids", "status"}
PROTECTED_CLOSURE_GATE_FIELDS = {
    "drift_labels",
    "family_local_drift",
    "shared_dependency_drift",
    "status",
}
ESTIMATED_CONTEXT_LIMIT = "ESTIMATED_CONTEXT_LIMIT"
PROVIDER_CONTEXT_LIMIT = "PROVIDER_CONTEXT_LIMIT"
PROVIDER_PAYLOAD_LIMIT = "PROVIDER_PAYLOAD_LIMIT"
EXPANDED_GRID_RESOURCE_LIMIT = "EXPANDED_GRID_RESOURCE_LIMIT"
SHARED_PROTECTED_CLOSURE_DRIFT = "SHARED_PROTECTED_CLOSURE_DRIFT"
FAMILY_LOCAL_AUTHORITY_DRIFT = "FAMILY_LOCAL_AUTHORITY_DRIFT"
MEASUREMENT_FIELDS = (
    "round_trip_receipts",
    "qualification_task_measurements",
    "family_maximum_estimated_input_tokens",
    "maximum_estimated_input_tokens",
    "maximum_successfully_estimated_input_tokens",
    "blocking_family_ids",
    "any_measurement_blocked",
)
D07_AUTHORITY_FIELDS = {
    "blocking_family_ids",
    "d07_decision_required",
    "effective_d07_choice",
    "effective_d07_record_hash",
    "estimator_authority_hashes",
    "matrix_sha256",
    "measurement_has_any_blocker",
    "measurement_receipts_hash",
}
SHARED_DRIFT_PREFIXES = (
    "r2_root:",
    "shared_engine:",
    "shared_measurement:",
)
WB3_TESTS = {
    "single_flight": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_concurrent_exact_request_has_one_mock_invocation"
    ),
    "http_402_batch_stop": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_http_402_calls_once_and_stops_batch"
    ),
    "unknown_remote_outcome": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_egress_crash_is_unknown_and_never_retried"
    ),
    "successful_exact_response_reuse": (
        "tests.vnext.test_invocation_control.InvocationControlTest."
        "test_successful_exact_response_resume_has_zero_mock_invocation"
    ),
}
QUALIFICATION_ENGINE_ROOTS = (
    Path("scripts/vnext/ai_adapter.py"),
    Path("scripts/vnext/evidence.py"),
    Path("scripts/vnext/invocation_control.py"),
    Path("scripts/vnext/provider_runtime.py"),
    Path("scripts/vnext/qualification.py"),
    Path("scripts/vnext/reader.py"),
    Path("scripts/vnext/reader_input.py"),
    Path("scripts/vnext/records.py"),
    Path("scripts/vnext/review.py"),
    Path("scripts/vnext/run_store.py"),
    Path("scripts/vnext/source_strategy.py"),
    Path("scripts/vnext/specs.py"),
    Path("scripts/vnext/stage_a_snapshot.py"),
    Path("scripts/vnext/table_grid.py"),
    Path("scripts/vnext/table_payload.py"),
    Path("scripts/vnext/table_qualification_freeze.py"),
    Path("scripts/vnext/table_task_contracts.py"),
    Path("scripts/vnext/workflow.py"),
    Path("tools/vnext_qualification.py"),
)
QUALIFICATION_SHARED_DATA_PATHS = (
    Path("config/company_registry.csv"),
    Path("config/issue_15_release_plan.json"),
    Path("config/provider_model_runtime.json"),
    Path("config/release_plans/issue_15_zero_ai_r1.json"),
    Path("config/release_plans/issue_15_zero_ai_r2.json"),
    Path("requirements/issue_15_v1/CONTRACT.md"),
    Path("requirements/issue_15_v1/decision_register.json"),
    Path("tools/check_validation_snapshot.py"),
    Path("tools/create_stage_a_validation_snapshot.py"),
)
MEASUREMENT_ENGINE_PATHS = (
    Path("scripts/vnext/ai_adapter.py"),
    Path("scripts/vnext/canonical.py"),
    Path("scripts/vnext/provider_runtime.py"),
    Path("scripts/vnext/reader_input.py"),
    Path("scripts/vnext/table_grid.py"),
    Path("scripts/vnext/table_payload.py"),
    Path("scripts/vnext/table_qualification_freeze.py"),
    Path("scripts/vnext/table_task_contracts.py"),
    Path("config/provider_model_runtime.json"),
)
_MEASUREMENT_CACHE: Dict[str, Dict[str, object]] = {}


class TableQualificationFreezeError(RuntimeError):
    """Report an unsafe or incomplete table qualification freeze."""


class TableQualificationFamilyError(TableQualificationFreezeError):
    """Report one family-local matrix/source authority failure."""

    def __init__(
        self, *, family_id: str, reason_code: str, message: str,
    ) -> None:
        super().__init__(message)
        self.family_id = family_id
        self.reason_code = reason_code


def _regular_file(*, repo_root: Path, relative: Path, label: str) -> Path:
    """Resolve one safe repository-relative regular file.

    Args:
        repo_root: Repository authority root.
        relative: Portable relative path.
        label: Stable diagnostic label.

    Returns:
        Existing non-symlink regular path.
    """
    if relative.is_absolute() or ".." in relative.parts:
        raise TableQualificationFreezeError(
            "{} is not repository-relative".format(label)
        )
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        raise TableQualificationFreezeError("{} is absent or unsafe".format(label))
    return path


def _file_binding(*, repo_root: Path, relative: Path) -> Dict[str, object]:
    """Return a portable byte binding for one protected regular file.

    Args:
        repo_root: Repository authority root.
        relative: Repository-relative file locator.

    Returns:
        SHA-256 and size fields suitable for freeze/revalidation receipts.
    """
    path = _regular_file(repo_root=repo_root, relative=relative, label="file")
    return {
        "sha256": sha256_file(path=path),
        "size": path.stat().st_size,
    }


def _json_object(*, repo_root: Path, relative: Path, label: str) -> Dict[str, object]:
    """Load one strict JSON object from a safe repository file.

    Args:
        repo_root: Repository authority root.
        relative: Repository-relative JSON locator.
        label: Stable diagnostic label.

    Returns:
        Strict JSON object.
    """
    path = _regular_file(repo_root=repo_root, relative=relative, label=label)
    value = strict_json_file(path=path)
    if type(value) is not dict:
        raise TableQualificationFreezeError("{} root is not an object".format(label))
    return value


def _source_binding(
    *, repo_root: Path, value: object, label: str,
) -> Dict[str, object]:
    """Validate one frozen development, second-layout, or holdout source.

    Args:
        repo_root: Repository authority root.
        value: Matrix source declaration.
        label: Stable matrix field label.

    Returns:
        Validated source declaration with exact bytes where they already exist.
    """
    if type(value) is not dict or "source_kind" not in value:
        raise TableQualificationFreezeError("{} source is invalid".format(label))
    source = dict(value)
    kind = source["source_kind"]
    if kind == "IMMUTABLE_ATTEMPT":
        if set(source) != IMMUTABLE_SOURCE_FIELDS:
            raise TableQualificationFreezeError("{} fields are not exact".format(label))
        path = _regular_file(
            repo_root=repo_root,
            relative=Path(str(source["source_repo_relative_path"])),
            label=label + " source",
        )
        if sha256_file(path=path) != source["source_sha256"]:
            raise TableQualificationFreezeError("{} bytes differ".format(label))
    elif kind == "FUTURE_LIVE_IMMUTABLE_ATTEMPT":
        if set(source) != FUTURE_SOURCE_FIELDS:
            raise TableQualificationFreezeError("{} fields are not exact".format(label))
        if (
            type(source["fiscal_year"]) is not int
            or source["fiscal_year"] < 2000
        ):
            raise TableQualificationFreezeError("{} fiscal year is invalid".format(label))
    elif kind == "RECORDED_LAYOUT_FIXTURE":
        if set(source) != FIXTURE_SOURCE_FIELDS:
            raise TableQualificationFreezeError("{} fields are not exact".format(label))
        fixture_id = source["fixture_id"]
        if type(fixture_id) is not str or not fixture_id:
            raise TableQualificationFreezeError("{} fixture ID is invalid".format(label))
        manifest_relative = (
            LAYOUT_FIXTURE_ROOT / fixture_id / "fixture_manifest.json"
        )
        manifest = _json_object(
            repo_root=repo_root,
            relative=manifest_relative,
            label=label + " fixture manifest",
        )
        if manifest["fixture_id"] != fixture_id:
            raise TableQualificationFreezeError("{} fixture differs".format(label))
        source["fixture_manifest_sha256"] = sha256_file(
            path=repo_root / manifest_relative,
        )
        source["fixture_source_sha256"] = manifest["source_sha256"]
    else:
        raise TableQualificationFreezeError("{} source kind is unsupported".format(label))
    return source


def _matrix_family_index(
    *, repo_root: Path,
) -> Tuple[Dict[str, Dict[str, object]], str]:
    """Parse shared matrix structure without local source dereference."""
    payload = _json_object(
        repo_root=repo_root,
        relative=MATRIX_PATH,
        label="table qualification matrix",
    )
    if (
        set(payload) != MATRIX_FIELDS
        or payload["schema_version"] != 1
        or payload["requirement_id"] != "issue_15_v1"
        or type(payload["families"]) is not list
        or not payload["families"]
    ):
        raise TableQualificationFreezeError(
            "Table qualification matrix invalid"
        )
    entries = {}
    for value in payload["families"]:
        if type(value) is not dict:
            raise TableQualificationFreezeError(
                "Matrix family index is invalid"
            )
        family_id = value.get("family_id")
        if (
            type(family_id) is not str
            or not family_id
            or family_id in entries
        ):
            raise TableQualificationFreezeError(
                "Matrix family identity is invalid"
            )
        entries[family_id] = dict(value)
    return entries, sha256_file(path=repo_root / MATRIX_PATH)


def _matrix_family_reason(*, message: str) -> str:
    """Map one requested-family matrix failure to a stable reason code."""
    if "bytes differ" in message:
        return "LOCAL_SOURCE_BYTES_MISMATCH"
    if "source is absent or unsafe" in message:
        return "LOCAL_SOURCE_MISSING"
    if "source" in message or "fixture" in message:
        return "LOCAL_SOURCE_AUTHORITY_INVALID"
    return "LOCAL_MATRIX_AUTHORITY_INVALID"


def _validate_matrix_family_entry(
    *, repo_root: Path, family_id: str, value: Mapping[str, object],
) -> Dict[str, object]:
    """Validate and dereference exactly one family-local matrix row."""
    if set(value) != MATRIX_ENTRY_FIELDS:
        raise TableQualificationFreezeError(
            "Matrix entry fields are not exact"
        )
    entry = dict(value)
    if entry["family_id"] != family_id:
        raise TableQualificationFreezeError("Matrix family identity differs")
    if (
        type(entry["reader_contract_id"]) is not str
        or not entry["reader_contract_id"]
        or entry["second_layout_policy"] != "REQUIRED"
        or entry["expected_output_status"]
        != "REVIEW_REQUIRED_OR_CANDIDATE"
        or type(entry["fresh_samples_required"]) is not int
        or entry["fresh_samples_required"] < 1
        or type(entry["expected_claims"]) is not list
        or not entry["expected_claims"]
        or len(entry["expected_claims"])
        != len(set(entry["expected_claims"]))
        or any(
            type(item) is not str or not item
            for item in entry["expected_claims"]
        )
        or type(entry["task_contract_ids"]) is not list
        or not entry["task_contract_ids"]
        or any(
            type(item) is not str or not item
            for item in entry["task_contract_ids"]
        )
        or len(entry["task_contract_ids"])
        != len(set(entry["task_contract_ids"]))
        or entry["task_contract_ids"]
        != sorted(entry["task_contract_ids"])
        or type(entry["materially_different_criteria"]) is not list
        or len(entry["materially_different_criteria"]) < 2
        or type(entry["negative_cases"]) is not list
        or not entry["negative_cases"]
        or type(entry["review_policy"]) is not str
        or not entry["review_policy"]
        or type(entry["source_media_type"]) is not str
        or entry["source_media_type"] != "text/html"
    ):
        raise TableQualificationFreezeError("Matrix entry values are invalid")
    target_period = entry["target_period"]
    if (
        type(target_period) is not dict
        or set(target_period) != {
            "fiscal_year", "period_start", "period_end",
        }
        or type(target_period["fiscal_year"]) is not int
        or type(target_period["period_start"]) is not str
        or type(target_period["period_end"]) is not str
    ):
        raise TableQualificationFreezeError("Matrix target period is invalid")
    locator_range = entry["expected_locator_range"]
    limits = entry["token_context_limits"]
    if (
        type(locator_range) is not dict
        or set(locator_range) != LOCATOR_RANGE_FIELDS
        or locator_range["row_index_min"] != 0
        or locator_range["column_index_min"] != 0
        or locator_range["table_selection"]
        != "ONE_MODEL_SELECTED_TABLE_FROM_COMPLETE_DOCUMENT_SET"
        or locator_range["selected_competing_scope_evidence"]
        != "SAME_TARGET_TABLE_ONLY"
        or type(limits) is not dict
        or set(limits) != TOKEN_LIMIT_FIELDS
        or any(
            type(limits[field]) is not int or limits[field] < 1
            for field in limits
        )
    ):
        raise TableQualificationFreezeError("Matrix limits are invalid")
    entry["development_source"] = _source_binding(
        repo_root=repo_root,
        value=entry["development_source"],
        label=family_id + " development",
    )
    entry["second_layout_source"] = _source_binding(
        repo_root=repo_root,
        value=entry["second_layout_source"],
        label=family_id + " second layout",
    )
    entry["post_freeze_holdout_source"] = _source_binding(
        repo_root=repo_root,
        value=entry["post_freeze_holdout_source"],
        label=family_id + " holdout",
    )
    return entry


def load_table_qualification_matrix(
    *, repo_root: Path, family_id: Optional[str] = None,
) -> Dict[str, object]:
    """Load all matrix families or only one requested fault domain.

    Args:
        repo_root: Repository authority root.

    Returns:
        Validated matrix entries keyed by family ID and the full file hash.
    """
    indexed, matrix_sha256 = _matrix_family_index(repo_root=repo_root)
    selected = sorted(indexed) if family_id is None else [family_id]
    if any(value not in indexed for value in selected):
        raise TableQualificationFreezeError("Matrix family is absent")
    entries = {}
    for selected_family in selected:
        try:
            entries[selected_family] = _validate_matrix_family_entry(
                repo_root=repo_root,
                family_id=selected_family,
                value=indexed[selected_family],
            )
        except TableQualificationFreezeError as error:
            if family_id is None:
                raise
            raise TableQualificationFamilyError(
                family_id=selected_family,
                reason_code=_matrix_family_reason(message=str(error)),
                message=str(error),
            ) from error
    return {
        "entries": entries,
        "family_ids": sorted(indexed),
        "matrix_sha256": matrix_sha256,
    }


def _round_trip_sources(
    *, repo_root: Path,
) -> List[Tuple[str, Path, str]]:
    """Return the exact Marriott, Hilton, and Hyatt WB-4 source set.

    Args:
        repo_root: Repository authority root.

    Returns:
        Eleven fixture IDs with paths and declared raw SHA-256 values.
    """
    marriott = _json_object(
        repo_root=repo_root,
        relative=MARRIOTT_PROVENANCE_PATH,
        label="Marriott provenance",
    )
    sources = [
        (
            str(marriott["fixture_id"]),
            repo_root / str(marriott["source_repo_relative_path"]),
            str(marriott["source_sha256"]),
        )
    ]
    fixture_root = repo_root / LAYOUT_FIXTURE_ROOT
    if fixture_root.is_symlink() or not fixture_root.is_dir():
        raise TableQualificationFreezeError("Layout fixture root is unsafe")
    for root in sorted(path for path in fixture_root.iterdir() if path.is_dir()):
        manifest_relative = (
            LAYOUT_FIXTURE_ROOT / root.name / "fixture_manifest.json"
        )
        manifest = _json_object(
            repo_root=repo_root,
            relative=manifest_relative,
            label="layout fixture manifest",
        )
        fixture_id = str(manifest["fixture_id"])
        if not (
            fixture_id.startswith("hilton-")
            or fixture_id.startswith("hyatt-")
        ):
            continue
        sources.append(
            (
                fixture_id,
                repo_root / str(manifest["source_repo_relative_path"]),
                str(manifest["source_sha256"]),
            )
        )
    if len(sources) != 11:
        raise TableQualificationFreezeError("WB-4 source set is not eleven")
    return sources


def _context_blocking_reason_codes(
    *, estimated_input_tokens: int, max_estimated_input_tokens: int,
    maximum_context_tokens: int, provider_envelope_bytes: int,
    maximum_payload_bytes: int,
) -> List[str]:
    """Return deterministic inclusive-threshold context/payload blockers."""
    values = (
        estimated_input_tokens,
        max_estimated_input_tokens,
        maximum_context_tokens,
        provider_envelope_bytes,
        maximum_payload_bytes,
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise TableQualificationFreezeError("Context gate inputs are invalid")
    reason_codes = []
    if estimated_input_tokens > max_estimated_input_tokens:
        reason_codes.append(ESTIMATED_CONTEXT_LIMIT)
    if estimated_input_tokens > maximum_context_tokens:
        reason_codes.append(PROVIDER_CONTEXT_LIMIT)
    if provider_envelope_bytes > maximum_payload_bytes:
        reason_codes.append(PROVIDER_PAYLOAD_LIMIT)
    return reason_codes


def _measure_reader_envelope(
    *,
    source_id: str,
    source_path: Path,
    source_sha256: str,
    task_contract: Mapping[str, object],
    token_limit: int,
    policy: object,
    runtime: Mapping[str, object],
) -> Dict[str, object]:
    """Measure one complete local table source and one fixed task envelope.

    Args:
        source_id: Stable fixture or development-source identity.
        source_path: Existing local source file; no remote acquisition occurs.
        source_sha256: Declared raw source digest without the ``sha256:`` tag.
        task_contract: One explicit catalog runtime task contract.
        token_limit: Family's non-monetary input/context hard limit.
        policy: Effective provider transport policy used only to form bytes.
        runtime: Local token-estimator authority.

    Returns:
        One content-addressed offline measurement receipt.

    Why:
        Every request repeats the full compact table set.  Measuring the exact
        task envelope rather than a generic payload makes D-07 and split cost
        evidence reproducible without creating a provider request.
    """
    if source_path.is_symlink() or not source_path.is_file():
        raise TableQualificationFreezeError("Measurement source is absent or unsafe")
    source_bytes = source_path.read_bytes()
    if sha256_bytes(content=source_bytes) != source_sha256:
        raise TableQualificationFreezeError("Measurement source hash differs")
    try:
        asset = build_table_grid(
            html_bytes=source_bytes,
            parent_raw_asset_ids=["sha256:" + source_sha256],
            storage_uri=(
                "artifacts/vnext/table_qualification_freeze/{}.json".format(
                    source_id
                )
            ),
        )
    except TableGridError as error:
        # The complete expanded grid is authoritative.  A resource refusal
        # must remain visible rather than being bypassed by a table selector,
        # partial parser, or synthetic compact estimate.
        body = {
            "source_id": source_id,
            "source_sha256": source_sha256,
            "task_contract_id": task_contract["task_contract_id"],
            "expanded_reader_payload_bytes": RESOURCE_LIMIT_ESTIMATE,
            "compact_reader_payload_bytes": RESOURCE_LIMIT_ESTIMATE,
            "compression_ratio": RESOURCE_LIMIT_ESTIMATE,
            "provider_envelope_estimated_bytes": RESOURCE_LIMIT_ESTIMATE,
            "estimated_input_tokens": RESOURCE_LIMIT_ESTIMATE,
            "actual_prompt_tokens": "NOT_RUN",
            "estimator_id": runtime["estimator_id"],
            "estimator_version": runtime["estimator_version"],
            "provider_context_authority_hash": runtime["context_authority_hash"],
            "round_trip_receipt_id": RESOURCE_LIMIT_ESTIMATE,
            "round_trip_hash": RESOURCE_LIMIT_ESTIMATE,
            "context_or_resource_limit_exceeded": True,
            "blocking_reason_codes": [EXPANDED_GRID_RESOURCE_LIMIT],
            "resource_limit_reason": str(error),
        }
        return {**body, "measurement_id": content_hash(value=body)}
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=["source:" + source_sha256],
    )
    compact_payload = build_reader_payload(
        manifest=manifest,
        derived_asset=asset,
        task_contract=task_contract,
    )
    expanded_body = {
        "system_contract": dict(READER_SYSTEM_CONTRACT),
        "task_contract": dict(task_contract),
        "reader_input_manifest": dict(manifest),
        "untrusted_table_data": list(asset["tables"]),
    }
    expanded_bytes = canonical_json_bytes(value=expanded_body)
    provider_envelope, _output_schema = build_provider_request_body(
        policy=policy,
        reader_request_bytes=compact_payload["request_bytes"],
    )
    estimated_tokens = estimate_context_tokens(
        request_body=provider_envelope,
        authority=runtime,
    )
    compact_transport = compact_payload["table_transport"]
    round_trip = compact_payload_receipt(transport=compact_transport)
    compression = (
        Decimal(len(compact_payload["request_bytes"]))
        / Decimal(len(expanded_bytes))
    ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
    blocking_reason_codes = _context_blocking_reason_codes(
        estimated_input_tokens=estimated_tokens,
        max_estimated_input_tokens=token_limit,
        maximum_context_tokens=runtime["maximum_context_tokens"],
        provider_envelope_bytes=len(provider_envelope),
        maximum_payload_bytes=policy.maximum_payload_bytes,
    )
    body = {
        "source_id": source_id,
        "source_sha256": source_sha256,
        "task_contract_id": task_contract["task_contract_id"],
        "expanded_reader_payload_bytes": len(expanded_bytes),
        "compact_reader_payload_bytes": len(compact_payload["request_bytes"]),
        "compression_ratio": format(compression, "f"),
        "provider_envelope_estimated_bytes": len(provider_envelope),
        "estimated_input_tokens": estimated_tokens,
        "actual_prompt_tokens": "NOT_RUN",
        "estimator_id": runtime["estimator_id"],
        "estimator_version": runtime["estimator_version"],
        "provider_context_authority_hash": runtime["context_authority_hash"],
        "round_trip_receipt_id": round_trip["round_trip_receipt_id"],
        "round_trip_hash": content_hash(value=round_trip),
        "context_or_resource_limit_exceeded": bool(blocking_reason_codes),
        "blocking_reason_codes": blocking_reason_codes,
    }
    return {**body, "measurement_id": content_hash(value=body)}


def _measurement_receipts(
    *,
    repo_root: Path,
    matrix: Mapping[str, object],
    task_contracts: Mapping[str, object],
) -> Dict[str, object]:
    """Measure WB-4 fixtures and every local family/task request offline.

    Args:
        repo_root: Repository authority root.
        matrix: Validated frozen family matrix.
        task_contracts: Validated catalog contracts grouped by family.

    Returns:
        Eleven WB-4 receipts, every local development-source/task envelope,
        family maxima, overall maximum, and a D-07 decision flag.
    """
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    policy = approved_transport_policy(requirement=requirement)
    runtime = load_provider_runtime_authority(
        repo_root=repo_root,
        provider=policy.provider,
        model=policy.model,
        api=policy.api,
    )
    round_trip_sources = _round_trip_sources(repo_root=repo_root)
    round_trip_entry = matrix["entries"].get("lodging_kpi_table")
    if type(round_trip_entry) is not dict:
        raise TableQualificationFreezeError("WB-4 lodging family is absent")
    round_trip_task = resolve_table_task_contract(
        repo_root=repo_root,
        task_contract_id=round_trip_entry["task_contract_ids"][0],
    )
    round_trip_receipts = []
    for fixture_id, source_path, expected_sha256 in round_trip_sources:
        round_trip_receipts.append(_measure_reader_envelope(
            source_id=fixture_id,
            source_path=source_path,
            source_sha256=expected_sha256,
            task_contract=round_trip_task,
            token_limit=round_trip_entry["token_context_limits"][
                "max_estimated_input_tokens"
            ],
            policy=policy,
            runtime=runtime,
        ))
    if len(round_trip_receipts) != 11:
        raise TableQualificationFreezeError("WB-4 measurement set is not eleven")
    task_measurements = []
    for family_id in sorted(matrix["entries"]):
        entry = matrix["entries"][family_id]
        development = entry["development_source"]
        if development["source_kind"] != "IMMUTABLE_ATTEMPT":
            continue
        source_path = repo_root / Path(
            str(development["source_repo_relative_path"])
        )
        for task_contract_id in entry["task_contract_ids"]:
            task_contract = resolve_table_task_contract(
                repo_root=repo_root,
                task_contract_id=task_contract_id,
            )
            measurement = _measure_reader_envelope(
                source_id="{}:{}".format(family_id, task_contract_id),
                source_path=source_path,
                source_sha256=str(development["source_sha256"]),
                task_contract=task_contract,
                token_limit=entry["token_context_limits"][
                    "max_estimated_input_tokens"
                ],
                policy=policy,
                runtime=runtime,
            )
            task_measurements.append({
                "family_id": family_id,
                "development_source_repo_relative_path": development[
                    "source_repo_relative_path"
                ],
                **measurement,
            })
    expected_task_ids = {
        str(contract["task_contract_id"])
        for contract in task_contracts["contracts"]
    }
    if {item["task_contract_id"] for item in task_measurements} != expected_task_ids:
        raise TableQualificationFreezeError("Development task measurement set differs")
    family_maxima = {}
    for family_id in matrix["entries"]:
        estimates = [
            item["estimated_input_tokens"]
            for item in task_measurements
            if item["family_id"] == family_id
        ]
        if any(estimate == RESOURCE_LIMIT_ESTIMATE for estimate in estimates):
            family_maxima[family_id] = RESOURCE_LIMIT_ESTIMATE
        else:
            family_maxima[family_id] = max(estimates)
    all_measurements = round_trip_receipts + task_measurements
    known_estimates = [
        item["estimated_input_tokens"]
        for item in all_measurements
        if item["estimated_input_tokens"] != RESOURCE_LIMIT_ESTIMATE
    ]
    maximum = (
        RESOURCE_LIMIT_ESTIMATE
        if any(
            item["estimated_input_tokens"] == RESOURCE_LIMIT_ESTIMATE
            for item in all_measurements
        )
        else max(known_estimates)
    )
    blocking_family_ids = sorted({
        str(item["family_id"])
        for item in task_measurements
        if item["blocking_reason_codes"]
    })
    return {
        "round_trip_receipts": round_trip_receipts,
        "qualification_task_measurements": task_measurements,
        "family_maximum_estimated_input_tokens": family_maxima,
        "maximum_estimated_input_tokens": maximum,
        "maximum_successfully_estimated_input_tokens": max(known_estimates),
        "blocking_family_ids": blocking_family_ids,
        "any_measurement_blocked": any(
            item["context_or_resource_limit_exceeded"]
            for item in all_measurements
        ),
    }


def _measurement_input_cache_key(
    *, repo_root: Path, matrix: Mapping[str, object],
    task_contracts: Mapping[str, object], requirement: Mapping[str, object],
) -> str:
    """Bind reusable local measurements to every byte that can affect them.

    The cache is process-local only; it never becomes receipt authority.  Each
    caller first rehashes the matrix, catalog/runtime closure, D-07 record, all
    complete source bytes, and the measurement engine.  A changed input gets a
    new key and necessarily rebuilds the full expanded-grid measurement.
    """
    round_trip_sources = [
        {
            "fixture_id": fixture_id,
            "declared_sha256": declared_sha256,
            "actual_sha256": sha256_file(path=source_path),
        }
        for fixture_id, source_path, declared_sha256 in _round_trip_sources(
            repo_root=repo_root,
        )
    ]
    development_sources = []
    for family_id, entry in sorted(matrix["entries"].items()):
        source = entry["development_source"]
        if source["source_kind"] != "IMMUTABLE_ATTEMPT":
            continue
        relative = Path(str(source["source_repo_relative_path"]))
        development_sources.append({
            "family_id": family_id,
            "declared_sha256": source["source_sha256"],
            "actual_sha256": sha256_file(path=repo_root / relative),
            "path": relative.as_posix(),
        })
    decisions = requirement.get("effective_decisions")
    if type(decisions) is not dict or type(decisions.get("D-07")) is not dict:
        raise TableQualificationFreezeError("Effective D-07 authority is absent")
    engine_files = {
        relative.as_posix(): sha256_file(path=repo_root / relative)
        for relative in MEASUREMENT_ENGINE_PATHS
    }
    return content_hash(value={
        "matrix": matrix["matrix_sha256"],
        "task_catalog": task_contracts["catalog_sha256"],
        "task_contracts": task_contracts["contracts"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "effective_d07_record_hash": content_hash(
            value=decisions["D-07"],
        ),
        "round_trip_sources": round_trip_sources,
        "development_sources": development_sources,
        "measurement_engine_files": engine_files,
    })


def _current_measurement_receipts(
    *, repo_root: Path, matrix: Mapping[str, object],
    task_contracts: Mapping[str, object], requirement: Mapping[str, object],
) -> Dict[str, object]:
    """Return a current-input-bound WB-4 measurement, rebuilding on any drift."""
    cache_key = _measurement_input_cache_key(
        repo_root=repo_root,
        matrix=matrix,
        task_contracts=task_contracts,
        requirement=requirement,
    )
    cached = _MEASUREMENT_CACHE.get(cache_key)
    if cached is None:
        cached = _measurement_receipts(
            repo_root=repo_root,
            matrix=matrix,
            task_contracts=task_contracts,
        )
        _MEASUREMENT_CACHE[cache_key] = copy.deepcopy(cached)
    return copy.deepcopy(cached)


def _family_measurement_receipts(
    *, repo_root: Path, family_id: str, matrix: Mapping[str, object],
    task_contracts: Mapping[str, object], requirement: Mapping[str, object],
) -> Dict[str, object]:
    """Measure only one requested family's local development envelopes."""
    entry = matrix["entries"].get(family_id)
    if type(entry) is not dict:
        raise TableQualificationFamilyError(
            family_id=family_id,
            reason_code="LOCAL_MATRIX_AUTHORITY_INVALID",
            message="Requested family matrix entry is absent",
        )
    development = entry["development_source"]
    if development["source_kind"] != "IMMUTABLE_ATTEMPT":
        raise TableQualificationFamilyError(
            family_id=family_id,
            reason_code="LOCAL_MEASUREMENT_AUTHORITY_INVALID",
            message="Requested family development source is not measurable",
        )
    source_path = repo_root / Path(
        str(development["source_repo_relative_path"])
    )
    decisions = requirement.get("effective_decisions")
    if type(decisions) is not dict or type(decisions.get("D-07")) is not dict:
        raise TableQualificationFreezeError(
            "Effective D-07 authority is absent"
        )
    cache_key = content_hash(value={
        "measurement_scope": "ONE_TABLE_FAMILY",
        "family_id": family_id,
        "matrix_entry": entry,
        "task_contracts": task_contracts["contracts"],
        "requirement_closure_hash": requirement[
            "requirement_closure_hash"
        ],
        "effective_d07_record_hash": content_hash(
            value=decisions["D-07"],
        ),
        "development_source_actual_sha256": sha256_file(
            path=source_path
        ),
        "measurement_engine_files": {
            relative.as_posix(): sha256_file(path=repo_root / relative)
            for relative in MEASUREMENT_ENGINE_PATHS
        },
    })
    cached = _MEASUREMENT_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    policy = approved_transport_policy(requirement=requirement)
    runtime = load_provider_runtime_authority(
        repo_root=repo_root,
        provider=policy.provider,
        model=policy.model,
        api=policy.api,
    )
    rows = []
    for task_contract_id in entry["task_contract_ids"]:
        task_contract = resolve_table_task_contract(
            repo_root=repo_root,
            task_contract_id=task_contract_id,
            family_id=family_id,
        )
        measurement = _measure_reader_envelope(
            source_id="{}:{}".format(family_id, task_contract_id),
            source_path=source_path,
            source_sha256=str(development["source_sha256"]),
            task_contract=task_contract,
            token_limit=entry["token_context_limits"][
                "max_estimated_input_tokens"
            ],
            policy=policy,
            runtime=runtime,
        )
        rows.append({
            "family_id": family_id,
            "development_source_repo_relative_path": development[
                "source_repo_relative_path"
            ],
            **measurement,
        })
    expected_ids = {
        str(contract["task_contract_id"])
        for contract in task_contracts["contracts"]
    }
    if {row["task_contract_id"] for row in rows} != expected_ids:
        raise TableQualificationFamilyError(
            family_id=family_id,
            reason_code="LOCAL_MEASUREMENT_AUTHORITY_INVALID",
            message="Requested family measurement task set differs",
        )
    estimates = [row["estimated_input_tokens"] for row in rows]
    maximum = (
        RESOURCE_LIMIT_ESTIMATE
        if RESOURCE_LIMIT_ESTIMATE in estimates
        else max(estimates)
    )
    result = {
        "qualification_task_measurements": rows,
        "family_maximum_estimated_input_tokens": {
            family_id: maximum,
        },
    }
    _MEASUREMENT_CACHE[cache_key] = copy.deepcopy(result)
    return result


def _current_estimator_authority_hash(
    *, repo_root: Path, requirement: Mapping[str, object],
) -> str:
    """Rebuild the shared estimator authority without any family source."""
    policy = approved_transport_policy(requirement=requirement)
    runtime = load_provider_runtime_authority(
        repo_root=repo_root,
        provider=policy.provider,
        model=policy.model,
        api=policy.api,
    )
    value = runtime.get("context_authority_hash")
    if type(value) is not str or not value.startswith("sha256:"):
        raise TableQualificationFreezeError(
            "D-07 estimator authority is invalid"
        )
    return value


def _d07_authority(
    *, requirement: Mapping[str, object], matrix: Mapping[str, object],
    measurements: Mapping[str, object],
) -> Dict[str, object]:
    """Derive D-07 state from current authority and current offline evidence.

    A freeze receipt records this derivation for audit, but it is never the
    authority for the boolean itself.  Revalidation reruns the same complete
    full-table measurement against the current matrix and estimator authority.
    """
    decisions = requirement.get("effective_decisions")
    if type(decisions) is not dict or type(decisions.get("D-07")) is not dict:
        raise TableQualificationFreezeError("Effective D-07 authority is absent")
    decision = dict(decisions["D-07"])
    choice = decision.get("choice")
    if (
        decision.get("decision_id") != "D-07"
        or decision.get("status") != "APPROVED"
        or type(choice) is not dict
        or choice != ISSUE_15_D07_EFFECTIVE_CHOICE
    ):
        raise TableQualificationFreezeError("Effective D-07 authority is invalid")
    if any(
        entry["token_context_limits"]["max_estimated_input_tokens"]
        != choice["max_estimated_input_tokens"]
        for entry in matrix["entries"].values()
    ):
        raise TableQualificationFreezeError("D-07 matrix threshold differs")
    if any(field not in measurements for field in MEASUREMENT_FIELDS) or type(
        measurements.get("any_measurement_blocked")
    ) is not bool or type(measurements.get("blocking_family_ids")) is not list:
        raise TableQualificationFreezeError("D-07 measurements are invalid")
    measurement_rows = (
        list(measurements["round_trip_receipts"])
        + list(measurements["qualification_task_measurements"])
    )
    allowed_reason_codes = {
        ESTIMATED_CONTEXT_LIMIT,
        PROVIDER_CONTEXT_LIMIT,
        PROVIDER_PAYLOAD_LIMIT,
        EXPANDED_GRID_RESOURCE_LIMIT,
    }
    for item in measurement_rows:
        reasons = item.get("blocking_reason_codes")
        estimate = item.get("estimated_input_tokens")
        if (
            type(reasons) is not list
            or reasons != sorted(set(reasons))
            or not set(reasons).issubset(allowed_reason_codes)
            or item.get("context_or_resource_limit_exceeded")
            != bool(reasons)
            or item.get("estimator_id") != choice["estimator_id"]
            or item.get("estimator_version") != choice["estimator_version"]
            or (
                estimate == RESOURCE_LIMIT_ESTIMATE
                and reasons != [EXPANDED_GRID_RESOURCE_LIMIT]
            )
            or (
                type(estimate) is int
                and (estimate > choice["max_estimated_input_tokens"])
                != (ESTIMATED_CONTEXT_LIMIT in reasons)
            )
        ):
            raise TableQualificationFreezeError(
                "D-07 measurement row is invalid"
            )
    derived_blocking_families = sorted({
        str(item["family_id"])
        for item in measurements["qualification_task_measurements"]
        if item["blocking_reason_codes"]
    })
    if (
        measurements["blocking_family_ids"] != derived_blocking_families
        or measurements["any_measurement_blocked"]
        != any(item["blocking_reason_codes"] for item in measurement_rows)
    ):
        raise TableQualificationFreezeError("D-07 measurement summary differs")
    estimator_hashes = sorted({
        str(item["provider_context_authority_hash"])
        for item in measurement_rows
    })
    if not estimator_hashes:
        raise TableQualificationFreezeError("D-07 estimator authority is absent")
    measurement_body = {
        field: measurements[field]
        for field in MEASUREMENT_FIELDS
    }
    return {
        "effective_d07_record_hash": content_hash(value=decision),
        "effective_d07_choice": choice,
        "matrix_sha256": matrix["matrix_sha256"],
        "estimator_authority_hashes": estimator_hashes,
        "measurement_receipts_hash": content_hash(value=measurement_body),
        "measurement_has_any_blocker": measurements[
            "any_measurement_blocked"
        ],
        "blocking_family_ids": derived_blocking_families,
        "d07_decision_required": False,
    }


def _measurement_body(*, value: Mapping[str, object]) -> Dict[str, object]:
    """Return the exact persisted/current measurement fields.

    Aggregate summaries remain receipt evidence, but they are not execution
    gates shared by otherwise independent table families.  Callers compare the
    family-addressable rows below and use the aggregate fields only to validate
    the frozen receipt's internal identity.
    """
    if any(field not in value for field in MEASUREMENT_FIELDS):
        raise TableQualificationFreezeError("D-07 measurements are incomplete")
    return {field: copy.deepcopy(value[field]) for field in MEASUREMENT_FIELDS}


def _frozen_readiness_matrix(
    *, readiness: Mapping[str, object], matrix_sha256: object,
) -> Dict[str, object]:
    """Reconstruct only the frozen per-family thresholds needed by D-07.

    The matrix file contains multiple families.  Using the current whole-file
    hash here would turn a local matrix edit back into a global receipt gate.
    The receipt already persists each family's threshold in its readiness
    record and binds the complete original matrix hash in D-07 evidence.
    """
    if type(matrix_sha256) is not str or not matrix_sha256:
        raise TableQualificationFreezeError(
            "Frozen D-07 matrix identity is invalid"
        )
    entries = {}
    for family_id, value in readiness.items():
        if (
            type(value) is not dict
            or type(value.get("context_gate")) is not dict
        ):
            raise TableQualificationFreezeError(
                "Frozen family readiness is invalid"
            )
        threshold = value["context_gate"].get("max_estimated_input_tokens")
        if type(threshold) is not int or threshold < 1:
            raise TableQualificationFreezeError(
                "Frozen family threshold is invalid"
            )
        entries[family_id] = {
            "token_context_limits": {
                "max_estimated_input_tokens": threshold,
            },
        }
    return {"entries": entries, "matrix_sha256": matrix_sha256}


def _validate_frozen_d07_evidence(
    *, requirement: Mapping[str, object], wb4: Mapping[str, object],
    readiness: Mapping[str, object],
) -> Dict[str, object]:
    """Validate frozen D-07 evidence without current family-local slices."""
    persisted = wb4.get("d07_authority")
    if type(persisted) is not dict or set(persisted) != D07_AUTHORITY_FIELDS:
        raise TableQualificationFreezeError("Frozen D-07 authority is invalid")
    frozen_measurements = _measurement_body(value=wb4)
    expected = _d07_authority(
        requirement=requirement,
        matrix=_frozen_readiness_matrix(
            readiness=readiness,
            matrix_sha256=persisted["matrix_sha256"],
        ),
        measurements=frozen_measurements,
    )
    if persisted != expected:
        raise TableQualificationFreezeError("Frozen D-07 authority differs")
    return frozen_measurements


def _is_shared_drift_label(*, label: str) -> bool:
    """Return whether one drift label invalidates every dependent family."""
    return label.startswith(SHARED_DRIFT_PREFIXES)


def _measurement_rows_by_family(
    *, measurements: Mapping[str, object], family_ids: Sequence[str],
) -> Dict[str, List[Dict[str, object]]]:
    """Group exact development-task measurements by their owning family."""
    rows = measurements.get("qualification_task_measurements")
    if type(rows) is not list:
        raise TableQualificationFreezeError(
            "D-07 task measurements are invalid"
        )
    grouped = {family_id: [] for family_id in family_ids}
    for row in rows:
        if type(row) is not dict or row.get("family_id") not in grouped:
            raise TableQualificationFreezeError(
                "D-07 task measurement family is invalid"
            )
        grouped[str(row["family_id"])].append(dict(row))
    if any(not family_rows for family_rows in grouped.values()):
        raise TableQualificationFreezeError(
            "D-07 family measurement is absent"
        )
    return grouped


def _measurement_estimator_hashes(
    *, measurements: Mapping[str, object],
) -> List[str]:
    """Derive shared estimator authority from exact measurement rows."""
    round_trips = measurements.get("round_trip_receipts")
    tasks = measurements.get("qualification_task_measurements")
    if type(round_trips) is not list or type(tasks) is not list:
        raise TableQualificationFreezeError(
            "D-07 measurement rows are invalid"
        )
    hashes = sorted({
        str(row.get("provider_context_authority_hash"))
        for row in round_trips + tasks
        if type(row) is dict
    })
    if not hashes or any(not value.startswith("sha256:") for value in hashes):
        raise TableQualificationFreezeError(
            "D-07 estimator authority is invalid"
        )
    return hashes


def _measurement_drift_by_family(
    *, frozen: Mapping[str, object], current: Mapping[str, object],
    current_matrix: Mapping[str, object],
    frozen_d07: Mapping[str, object],
    protected_drift: Mapping[str, Sequence[str]],
) -> Dict[str, List[str]]:
    """Classify current measurement drift before deriving family readiness.

    Development-source/task envelopes belong to their table family.  The
    eleven compact round-trip envelopes use the lodging task, so a concurrent
    lodging-local authority change owns their envelope drift; unexplained
    round-trip or estimator drift remains shared and invalidates every family.
    Aggregate maximum/any fields are derived summaries and never become a
    cross-family execution gate.
    """
    family_ids = sorted(current_matrix["entries"])
    frozen_rows = _measurement_rows_by_family(
        measurements=frozen,
        family_ids=family_ids,
    )
    current_rows = _measurement_rows_by_family(
        measurements=current,
        family_ids=family_ids,
    )
    drift = {
        family_id: list(protected_drift.get(family_id, []))
        for family_id in family_ids
        if protected_drift.get(family_id)
    }

    def add(*, family_id: str, label: str) -> None:
        drift[family_id] = sorted(set(drift.get(family_id, [])) | {label})

    for family_id in family_ids:
        if frozen_rows[family_id] != current_rows[family_id]:
            add(
                family_id=family_id,
                label="family_measurements:qualification_task_measurements",
            )
        frozen_maxima = frozen.get("family_maximum_estimated_input_tokens")
        current_maxima = current.get("family_maximum_estimated_input_tokens")
        if (
            type(frozen_maxima) is not dict
            or type(current_maxima) is not dict
            or frozen_maxima.get(family_id) != current_maxima.get(family_id)
        ):
            add(
                family_id=family_id,
                label="family_measurements:maximum_estimated_input_tokens",
            )
        threshold = current_matrix["entries"][family_id][
            "token_context_limits"
        ]["max_estimated_input_tokens"]
        if threshold != frozen_d07["effective_d07_choice"][
            "max_estimated_input_tokens"
        ]:
            add(family_id=family_id, label="family_d07_threshold")

    if frozen.get("round_trip_receipts") != current.get("round_trip_receipts"):
        task_owner = {}
        for rows in (frozen_rows, current_rows):
            for family_id, family_rows in rows.items():
                for row in family_rows:
                    task_owner[str(row.get("task_contract_id"))] = family_id
        round_trip_task_ids = {
            str(row.get("task_contract_id"))
            for rows in (
                frozen.get("round_trip_receipts"),
                current.get("round_trip_receipts"),
            )
            if type(rows) is list
            for row in rows
            if type(row) is dict
        }
        owners = {task_owner[task_id] for task_id in round_trip_task_ids
                  if task_id in task_owner}
        local_owners = {
            family_id
            for family_id in owners
            if any(
                not _is_shared_drift_label(label=label)
                for label in protected_drift.get(family_id, [])
            )
        }
        if len(owners) == 1 and owners == local_owners:
            add(
                family_id=next(iter(owners)),
                label="family_measurements:round_trip_envelopes",
            )
        else:
            for family_id in family_ids:
                add(
                    family_id=family_id,
                    label="shared_measurement:round_trip_receipts",
                )

    current_estimator_hashes = _measurement_estimator_hashes(
        measurements=current,
    )
    if current_estimator_hashes != frozen_d07["estimator_authority_hashes"]:
        for family_id in family_ids:
            add(
                family_id=family_id,
                label="shared_measurement:estimator_authority",
            )
    return drift


def _readiness_by_family(
    *, matrix: Mapping[str, object], measurements: Mapping[str, object],
    drift_by_family: Mapping[str, Sequence[str]],
) -> Dict[str, Dict[str, object]]:
    """Derive independent context/resource/closure gates for each family.

    Shared dependency drift is already propagated by
    :func:`_protected_closure_drift`; this function preserves that propagation
    while preventing one family's local measurement or authority failure from
    becoming a global execution gate.
    """
    family_ids = set(matrix["entries"])
    if not set(drift_by_family).issubset(family_ids):
        raise TableQualificationFreezeError(
            "Readiness drift family set differs"
        )
    rows = measurements.get("qualification_task_measurements")
    if type(rows) is not list:
        raise TableQualificationFreezeError(
            "Readiness measurements are invalid"
        )
    readiness = {}
    context_codes = {
        ESTIMATED_CONTEXT_LIMIT,
        PROVIDER_CONTEXT_LIMIT,
        PROVIDER_PAYLOAD_LIMIT,
    }
    for family_id in sorted(family_ids):
        family_rows = [
            item for item in rows if item.get("family_id") == family_id
        ]
        if not family_rows:
            raise TableQualificationFreezeError(
                "Family readiness measurement set is empty"
            )
        threshold = matrix["entries"][family_id]["token_context_limits"][
            "max_estimated_input_tokens"
        ]
        resource_rows = [
            item for item in family_rows
            if EXPANDED_GRID_RESOURCE_LIMIT in item["blocking_reason_codes"]
        ]
        context_rows = [
            item for item in family_rows
            if context_codes & set(item["blocking_reason_codes"])
        ]
        known_estimates = [
            item["estimated_input_tokens"]
            for item in family_rows
            if type(item["estimated_input_tokens"]) is int
        ]
        if context_rows:
            context_status = "BLOCKED"
        elif known_estimates:
            context_status = "PASSED"
        elif resource_rows:
            context_status = "NOT_EVALUATED_RESOURCE_LIMIT"
        else:
            raise TableQualificationFreezeError(
                "Family context readiness cannot be derived"
            )
        resource_status = "BLOCKED" if resource_rows else "PASSED"
        drift_labels = sorted(set(drift_by_family.get(family_id, [])))
        if any(type(label) is not str or not label for label in drift_labels):
            raise TableQualificationFreezeError(
                "Family readiness drift labels are invalid"
            )
        shared_drift = any(
            _is_shared_drift_label(label=label)
            for label in drift_labels
        )
        family_local_drift = any(
            not _is_shared_drift_label(label=label)
            for label in drift_labels
        )
        protected_status = "BLOCKED" if drift_labels else "PASSED"
        reason_codes = {
            reason
            for item in family_rows
            for reason in item["blocking_reason_codes"]
        }
        if shared_drift:
            reason_codes.add(SHARED_PROTECTED_CLOSURE_DRIFT)
        if family_local_drift:
            reason_codes.add(FAMILY_LOCAL_AUTHORITY_DRIFT)
        reason_codes.update(
            label.split(":", maxsplit=1)[1]
            for label in drift_labels
            if label.startswith("family_failure:")
            and len(label.split(":", maxsplit=1)) == 2
        )
        live_ready = (
            context_status == "PASSED"
            and resource_status == "PASSED"
            and protected_status == "PASSED"
        )
        readiness[family_id] = {
            "context_gate": {
                "status": context_status,
                "max_estimated_input_tokens": threshold,
                "threshold_comparison": (
                    "estimated_input_tokens <= {}".format(threshold)
                ),
                "maximum_observed_estimated_input_tokens": (
                    max(known_estimates)
                    if known_estimates else RESOURCE_LIMIT_ESTIMATE
                ),
                "blocking_measurement_ids": sorted(
                    str(item["measurement_id"])
                    for item in context_rows
                ),
            },
            "resource_gate": {
                "status": resource_status,
                "blocking_measurement_ids": sorted(
                    str(item["measurement_id"])
                    for item in resource_rows
                ),
            },
            "protected_closure_gate": {
                "status": protected_status,
                "drift_labels": drift_labels,
                "shared_dependency_drift": shared_drift,
                "family_local_drift": family_local_drift,
            },
            "live_ready": live_ready,
            "blocking_reason_codes": sorted(reason_codes),
        }
    return readiness


def _validate_readiness_shape(*, readiness: object) -> None:
    """Reject malformed persisted or current family readiness mappings."""
    if type(readiness) is not dict or not readiness:
        raise TableQualificationFreezeError("Family readiness is invalid")
    for family_id, value in readiness.items():
        if (
            type(family_id) is not str
            or not family_id
            or type(value) is not dict
            or set(value) != FAMILY_READINESS_FIELDS
            or type(value["context_gate"]) is not dict
            or set(value["context_gate"]) != CONTEXT_GATE_FIELDS
            or type(value["resource_gate"]) is not dict
            or set(value["resource_gate"]) != RESOURCE_GATE_FIELDS
            or type(value["protected_closure_gate"]) is not dict
            or set(value["protected_closure_gate"])
            != PROTECTED_CLOSURE_GATE_FIELDS
            or type(value["live_ready"]) is not bool
            or type(value["blocking_reason_codes"]) is not list
        ):
            raise TableQualificationFreezeError(
                "Family readiness fields are invalid"
            )


def _split_cost_receipts(
    *,
    task_contracts: Mapping[str, object],
    task_measurements: Sequence[Mapping[str, object]],
) -> List[Dict[str, object]]:
    """Bind declared split cost estimates to offline full-payload envelopes.

    Args:
        task_contracts: Validated catalog contracts.
        task_measurements: One development-source envelope estimate per task.

    Returns:
        Ordered split receipt rows with an explicit non-merged baseline.
    """
    measurements_by_id = {
        str(item["task_contract_id"]): item
        for item in task_measurements
    }
    rows = []
    for family_id in sorted({
        str(contract["reader_family_id"])
        for contract in task_contracts["contracts"]
    }):
        contracts = sorted(
            (
                contract
                for contract in task_contracts["contracts"]
                if contract["reader_family_id"] == family_id
            ),
            key=lambda contract: str(contract["task_contract_id"]),
        )
        for ordinal, contract in enumerate(contracts):
            task_contract_id = str(contract["task_contract_id"])
            if task_contract_id not in measurements_by_id:
                raise TableQualificationFreezeError("Split measurement is absent")
            measurement = measurements_by_id[task_contract_id]
            expected_incremental = (
                0
                if ordinal == 0
                else measurement["estimated_input_tokens"]
            )
            if contract["estimated_incremental_tokens"] != expected_incremental:
                raise TableQualificationFreezeError(
                    "Split estimated incremental tokens differ"
                )
            body = {
                "family_id": family_id,
                "task_contract_id": task_contract_id,
                "split_reason": contract["split_reason"],
                "baseline_kind": contract["split_baseline_kind"],
                "baseline_task_contract_id": contracts[0]["task_contract_id"],
                "estimated_incremental_tokens": expected_incremental,
                "actual_incremental_tokens": contract[
                    "actual_incremental_tokens"
                ],
                "offline_measurement_id": measurement["measurement_id"],
            }
            rows.append({**body, "split_receipt_id": content_hash(value=body)})
    return rows


def _run_wb3_test_receipts(*, repo_root: Path) -> Dict[str, object]:
    """Execute four deterministic WB-3 regression tests with no real egress.

    Args:
        repo_root: Repository authority root.

    Returns:
        Content-addressed test outcome receipt keyed by the required invariant.
    """
    rows = {}
    for label, test_id in WB3_TESTS.items():
        completed = subprocess.run(
            args=[sys.executable, "-m", "unittest", "-q", test_id],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            encoding="utf-8",
            env={"PYTHONDONTWRITEBYTECODE": "1", **dict()},
        )
        if completed.returncode != 0:
            raise TableQualificationFreezeError(
                "WB-3 regression failed: {}".format(label)
            )
        rows[label] = {
            "test_id": test_id,
            "return_code": completed.returncode,
            "test_source_sha256": sha256_file(
                path=repo_root / "tests/vnext/test_invocation_control.py",
            ),
            "outcome": "PASSED",
        }
    body = {"schema_version": 2, "tests": rows}
    return {**body, "wb3_regression_receipt_id": content_hash(value=body)}


def _validate_wb3_test_receipt(
    *, repo_root: Path, value: object,
) -> None:
    """Validate stable WB-3 regression evidence without timing-output hashes."""
    if type(value) is not dict or set(value) != {
        "schema_version", "tests", "wb3_regression_receipt_id",
    } or value["schema_version"] != 2:
        raise TableQualificationFreezeError("WB-3 regression receipt is invalid")
    tests = value["tests"]
    if type(tests) is not dict or set(tests) != set(WB3_TESTS):
        raise TableQualificationFreezeError("WB-3 regression test set differs")
    source_hash = sha256_file(
        path=repo_root / "tests/vnext/test_invocation_control.py",
    )
    for label, test_id in WB3_TESTS.items():
        row = tests[label]
        if type(row) is not dict or set(row) != {
            "test_id", "return_code", "test_source_sha256", "outcome",
        } or (
            row["test_id"] != test_id
            or row["return_code"] != 0
            or row["test_source_sha256"] != source_hash
            or row["outcome"] != "PASSED"
        ):
            raise TableQualificationFreezeError(
                "WB-3 regression test outcome differs"
            )
    body = {
        "schema_version": value["schema_version"],
        "tests": tests,
    }
    if value["wb3_regression_receipt_id"] != content_hash(value=body):
        raise TableQualificationFreezeError(
            "WB-3 regression receipt identity differs"
        )


def _root_state(*, repo_root: Path) -> Dict[str, object]:
    """Capture the exact unchanged R2 pointer and root compatibility mirrors.

    Args:
        repo_root: Repository authority root.

    Returns:
        Active publication identity and all protected root file byte hashes.
    """
    pointer = _json_object(
        repo_root=repo_root,
        relative=Path("outputs/active_publication.json"),
        label="active publication pointer",
    )
    if set(pointer) != {
        "bundle_manifest_sha256",
        "committed_at_utc",
        "previous_publication_id",
        "publication_id",
    }:
        raise TableQualificationFreezeError("Active publication pointer differs")
    root_paths = [
        Path("outputs/active_publication.json"),
        Path("outputs/metrics_matrix.csv"),
        Path("outputs/metric_evidence.csv"),
        Path("REPORT_十公司财务指标.md"),
    ]
    return {
        "active_publication_id": pointer["publication_id"],
        "active_pointer": _file_binding(
            repo_root=repo_root,
            relative=Path("outputs/active_publication.json"),
        ),
        "root_hashes": {
            path.as_posix(): _file_binding(repo_root=repo_root, relative=path)
            for path in root_paths
        },
    }


def _root_state_drift(
    *, frozen_identity: object, current_root: object,
) -> List[str]:
    """Return stable labels for R2 root drift bound by one freeze receipt.

    Root business artifacts deliberately stay outside the source-code import
    closure.  They therefore need an independent runtime comparison rather
    than relying on a freeze receipt's self-hash or hand-picked Python files.
    """
    if type(frozen_identity) is not dict or set(frozen_identity) != {
        "requirement_closure_hash",
        "parent_r2_active_publication_id",
        "active_pointer",
        "root_hashes",
    }:
        return ["r2_root:receipt_identity_invalid"]
    if type(current_root) is not dict:
        return ["r2_root:current_state_invalid"]
    drift = []
    if (
        current_root.get("active_publication_id")
        != frozen_identity["parent_r2_active_publication_id"]
    ):
        drift.append("r2_root:active_publication_id")
    if current_root.get("active_pointer") != frozen_identity["active_pointer"]:
        drift.append("r2_root:active_pointer")
    frozen_hashes = frozen_identity["root_hashes"]
    current_hashes = current_root.get("root_hashes")
    if type(frozen_hashes) is not dict or type(current_hashes) is not dict:
        drift.append("r2_root:root_hashes")
    else:
        for path in sorted(set(frozen_hashes) | set(current_hashes)):
            if frozen_hashes.get(path) != current_hashes.get(path):
                drift.append("r2_root:" + path)
    return drift


def _request_ledger_binding(*, repo_root: Path) -> Dict[str, object]:
    """Return the pre-freeze SEC ledger bytes without adding a request row.

    Args:
        repo_root: Repository authority root.

    Returns:
        Current ledger SHA-256 and data-row count.
    """
    path = _regular_file(
        repo_root=repo_root,
        relative=Path("evidence/requests_log.csv"),
        label="SEC request ledger",
    )
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        row_count = sum(1 for _row in csv.DictReader(file_obj))
    return {"sha256": sha256_file(path=path), "row_count": row_count}


def _local_import_targets(
    *, repo_root: Path, relative: Path,
) -> Set[Path]:
    """Resolve local Python imports made by one protected engine module.

    Args:
        repo_root: Repository authority root.
        relative: Repository-relative Python module path.

    Returns:
        Existing local module paths referenced by direct imports.

    Why:
        Qualification semantics are a transmission path, not a hand-picked
        list.  Parsing direct local imports lets the protected closure expand
        whenever the Workflow, replay, provider, or Spec engine gains a new
        repository dependency.
    """
    path = _regular_file(repo_root=repo_root, relative=relative, label="engine")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as error:
        raise TableQualificationFreezeError("Qualification engine is invalid") from error
    targets = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        module = node.module
        candidate = None
        if (
            node.level == 1
            and relative.parts[:2] == ("scripts", "vnext")
        ):
            candidate = Path("scripts/vnext") / (
                module.replace(".", "/") + ".py"
            )
        elif node.level == 0 and module.startswith("vnext."):
            candidate = Path("scripts") / (module.replace(".", "/") + ".py")
        elif node.level == 0 and module.startswith("scripts."):
            candidate = Path(module.replace(".", "/") + ".py")
        elif node.level == 0 and "." not in module:
            candidate = Path("scripts") / (module + ".py")
        if candidate is None:
            continue
        target = repo_root / candidate
        if target.exists():
            targets.add(candidate)
    return targets


def _requirement_closure_paths(*, repo_root: Path) -> Set[Path]:
    """Return the immutable Requirement bytes read by table qualification.

    Args:
        repo_root: Repository authority root.

    Returns:
        All regular Requirement files from the Issue #15 and inherited roots.
    """
    paths = set()
    for relative_root in (
        Path("requirements/issue_15_v1"),
        Path("requirements/ai_first_v3_3_1"),
    ):
        root = repo_root / relative_root
        if root.is_symlink() or not root.is_dir():
            raise TableQualificationFreezeError("Requirement closure is unsafe")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise TableQualificationFreezeError("Requirement closure has symlink")
            if path.is_file():
                paths.add(path.relative_to(repo_root))
    if not paths:
        raise TableQualificationFreezeError("Requirement closure is empty")
    return paths


def _shared_engine_closure(*, repo_root: Path) -> Dict[str, object]:
    """Derive the shared executable qualification dependency closure.

    Args:
        repo_root: Repository authority root.

    Returns:
        Portable file bindings for every transitive shared engine dependency.
    """
    pending = list(QUALIFICATION_ENGINE_ROOTS)
    paths = set(QUALIFICATION_SHARED_DATA_PATHS)
    paths.update(_requirement_closure_paths(repo_root=repo_root))
    while pending:
        relative = pending.pop()
        if relative in paths:
            continue
        paths.add(relative)
        for imported in _local_import_targets(
            repo_root=repo_root,
            relative=relative,
        ):
            if imported not in paths:
                pending.append(imported)
    return {
        path.as_posix(): _file_binding(repo_root=repo_root, relative=path)
        for path in sorted(paths)
    }


def _family_semantic_closure(
    *, repo_root: Path, family_id: str, matrix_entry: Mapping[str, object],
    task_contracts: Mapping[str, object],
) -> Dict[str, object]:
    """Derive one family's task, MetricSpec, and matrix dependency closure.

    Args:
        repo_root: Repository authority root.
        family_id: Authorized table family identity.
        matrix_entry: Exact validated matrix entry for the family.
        task_contracts: Exact catalog contracts derived from SourceStrategy.

    Returns:
        Family-local semantic hashes and source-file bindings only.

    Why:
        Matrix and catalog files contain several families.  Binding their whole
        file bytes as shared state would invalidate unrelated qualification;
        binding the validated per-family fragments preserves dependency-based
        invalidation without trusting a manually copied fragment.
    """
    contracts = [
        contract
        for contract in task_contracts["contracts"]
        if contract["reader_family_id"] == family_id
    ]
    if not contracts:
        raise TableQualificationFreezeError("Family task contract closure is empty")
    task_contracts_by_id = {}
    paths = set()
    for contract in contracts:
        task_contract_id = str(contract["task_contract_id"])
        try:
            plan = table_task_execution_plan(
                repo_root=repo_root,
                task_contract_id=task_contract_id,
                family_id=family_id,
            )
        except TableTaskContractFamilyError as error:
            raise TableQualificationFamilyError(
                family_id=family_id,
                reason_code=error.reason_code,
                message=str(error),
            ) from error
        except TableTaskContractError as error:
            raise TableQualificationFreezeError(
                "Family task cannot be rebuilt"
            ) from error
        runtime = plan["runtime_task_contract"]
        if runtime["reader_family_id"] != family_id:
            raise TableQualificationFreezeError("Family task route differs")
        task_contracts_by_id[task_contract_id] = {
            "catalog_task_contract_hash": runtime[
                "catalog_task_contract_hash"
            ],
            "task_spec_semantic_hash": runtime["task_spec_semantic_hash"],
            "output_schema_hash": runtime["output_schema_hash"],
            "system_prompt_hash": runtime["system_prompt_hash"],
            "metric_spec_paths": list(runtime["metric_spec_paths"]),
            "metric_spec_semantic_hashes": list(
                runtime["metric_spec_semantic_hashes"]
            ),
            "metric_spec_closure_hashes": list(
                runtime["metric_spec_closure_hashes"]
            ),
        }
        paths.update(Path(path) for path in runtime["metric_spec_paths"])
    if set(task_contracts_by_id) != set(matrix_entry["task_contract_ids"]):
        raise TableQualificationFreezeError("Family matrix task set differs")
    return {
        "matrix_entry_hash": content_hash(value=dict(matrix_entry)),
        "task_contracts": task_contracts_by_id,
        "semantic_files": {
            path.as_posix(): _file_binding(repo_root=repo_root, relative=path)
            for path in sorted(paths)
        },
    }


def _protected_closure(
    *, repo_root: Path, matrix: Mapping[str, object],
    task_contracts: Mapping[str, object],
) -> Dict[str, object]:
    """Bind shared engine and family-local semantic qualification closures.

    Args:
        repo_root: Repository authority root.
        matrix: Validated matrix entry mapping.
        task_contracts: Exact catalog contracts derived from SourceStrategy.

    Returns:
        Shared transitive engine files plus per-family semantic fragments.
    """
    families = {
        family_id: _family_semantic_closure(
            repo_root=repo_root,
            family_id=family_id,
            matrix_entry=matrix["entries"][family_id],
            task_contracts=task_contracts,
        )
        for family_id in sorted(matrix["entries"])
    }
    return {
        "shared_engine_files": _shared_engine_closure(repo_root=repo_root),
        "families": families,
    }


def _protected_closure_drift(
    *, frozen: Mapping[str, object], current: Mapping[str, object],
) -> Dict[str, List[str]]:
    """Return dependency-scoped drift labels between two protected closures.

    Args:
        frozen: Receipt-owned protected closure.
        current: Freshly derived protected closure from current source bytes.

    Returns:
        Family ID to sorted drift labels; shared engine drift is propagated to
        every authorized family, while task/matrix/MetricSpec drift is local.
    """
    required = {"families", "shared_engine_files"}
    if set(frozen) != required or set(current) != required:
        raise TableQualificationFreezeError("Protected closure fields differ")
    frozen_families = frozen["families"]
    current_families = current["families"]
    if (
        not isinstance(frozen_families, dict)
        or not isinstance(current_families, dict)
        or set(frozen_families) != set(current_families)
    ):
        raise TableQualificationFreezeError("Protected family set differs")
    frozen_shared = frozen["shared_engine_files"]
    current_shared = current["shared_engine_files"]
    if not isinstance(frozen_shared, dict) or not isinstance(current_shared, dict):
        raise TableQualificationFreezeError("Shared engine closure is invalid")
    missing = object()
    shared_drift = []
    for relative in sorted(set(frozen_shared) | set(current_shared)):
        frozen_value = (
            frozen_shared[relative]
            if relative in frozen_shared
            else missing
        )
        current_value = (
            current_shared[relative]
            if relative in current_shared
            else missing
        )
        if frozen_value != current_value:
            shared_drift.append("shared_engine:" + relative)
    drift_by_family = {}
    for family_id in sorted(frozen_families):
        frozen_family = frozen_families[family_id]
        current_family = current_families[family_id]
        if (
            not isinstance(frozen_family, dict)
            or not isinstance(current_family, dict)
            or set(frozen_family)
            != {"matrix_entry_hash", "semantic_files", "task_contracts"}
            or set(current_family) != set(frozen_family)
        ):
            raise TableQualificationFreezeError("Family protected closure is invalid")
        drift = list(shared_drift)
        if frozen_family["matrix_entry_hash"] != current_family[
            "matrix_entry_hash"
        ]:
            drift.append("family_matrix_entry")
        for label in ("task_contracts", "semantic_files"):
            frozen_values = frozen_family[label]
            current_values = current_family[label]
            if (
                not isinstance(frozen_values, dict)
                or not isinstance(current_values, dict)
            ):
                raise TableQualificationFreezeError("Family closure mapping invalid")
            for key in sorted(set(frozen_values) | set(current_values)):
                frozen_value = (
                    frozen_values[key]
                    if key in frozen_values
                    else missing
                )
                current_value = (
                    current_values[key]
                    if key in current_values
                    else missing
                )
                if frozen_value != current_value:
                    drift.append("{}:{}".format(label, key))
        if drift:
            drift_by_family[family_id] = sorted(drift)
    return drift_by_family


def _family_scope_closure(
    *, task_contracts: Mapping[str, object],
) -> Dict[str, object]:
    """Bind each family to its actual MetricSpec scope alias closure.

    Args:
        task_contracts: Exact contracts already derived from SourceStrategy.

    Returns:
        Per-family task/MetricSpec/scope identity mappings.

    Why:
        A single lodging disclosure scope cannot authorize financial table
        tasks.  Each selected task owns its own MetricSpec scope authority.
    """
    families = {}
    for family_id in task_contracts["authorized_family_ids"]:
        rows = []
        for contract in task_contracts["contracts"]:
            if contract["reader_family_id"] != family_id:
                continue
            metric_specs = contract["metric_specs"]
            if len(metric_specs) != 1:
                raise TableQualificationFreezeError("Task MetricSpec set is invalid")
            metric = metric_specs[0]
            scope_contract = metric["compiled"]["scope_contract"]
            rows.append({
                "task_contract_id": contract["task_contract_id"],
                "metric_id": metric["metric_id"],
                "metric_spec_path": metric["path"],
                "metric_spec_semantic_hash": metric["spec_semantic_hash"],
                "scope_contract_hash": scope_contract_hash(
                    contract=scope_contract,
                ),
                "exact_enum_alias_closure_hash": content_hash(
                    value=validate_scope_contract(value=scope_contract)[
                        "exact_enum_aliases"
                    ],
                ),
            })
        if not rows:
            raise TableQualificationFreezeError("Family scope closure is empty")
        families[family_id] = {"tasks": rows}
    return families


def _freeze_commit(*, repo_root: Path, freeze_commit: str) -> str:
    """Verify a caller-supplied Git commit before binding it in a receipt.

    Args:
        repo_root: Repository authority root.
        freeze_commit: Exact commit SHA that freezes protected source bytes.

    Returns:
        Full commit SHA resolved by local Git only.
    """
    completed = subprocess.run(
        args=["git", "rev-parse", "{}^{{commit}}".format(freeze_commit)],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise TableQualificationFreezeError("Freeze commit is not resolvable")
    resolved = completed.stdout.strip()
    clean = subprocess.run(
        args=["git", "diff", "--quiet", resolved, "--"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if clean.returncode != 0:
        raise TableQualificationFreezeError(
            "Tracked source differs from requested freeze commit"
        )
    return resolved


def build_table_qualification_freeze_receipt(
    *, repo_root: Path, freeze_commit: str, frozen_at_utc: str,
) -> Dict[str, object]:
    """Build one complete table qualification freeze receipt without writes.

    Args:
        repo_root: Repository authority root.
        freeze_commit: Exact committed source freeze identity.
        frozen_at_utc: Explicit UTC freeze timestamp.

    Returns:
        Complete content-addressed receipt body and identity.
    """
    try:
        parse_utc_timestamp(value=frozen_at_utc)
    except ValueError as error:
        raise TableQualificationFreezeError("Freeze timestamp is invalid") from error
    commit = _freeze_commit(repo_root=repo_root, freeze_commit=freeze_commit)
    task_contracts = load_table_task_contracts(repo_root=repo_root)
    matrix = load_table_qualification_matrix(repo_root=repo_root)
    if sorted(matrix["entries"]) != task_contracts["authorized_family_ids"]:
        raise TableQualificationFreezeError("Matrix family set differs from tasks")
    for family_id in task_contracts["authorized_family_ids"]:
        entry = matrix["entries"][family_id]
        matching_contracts = [
            contract for contract in task_contracts["contracts"]
            if contract["reader_family_id"] == family_id
        ]
        if (
            entry["reader_contract_id"]
            != matching_contracts[0]["reader_contract_id"]
            or entry["task_contract_ids"]
            != sorted(
                str(contract["task_contract_id"])
                for contract in matching_contracts
            )
            or sorted(entry["expected_claims"])
            != sorted(
                role
                for contract in matching_contracts
                for role in contract["required_roles"]
            )
        ):
            raise TableQualificationFreezeError("Matrix task binding differs")
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    measurements = _current_measurement_receipts(
        repo_root=repo_root,
        matrix=matrix,
        task_contracts=task_contracts,
        requirement=requirement,
    )
    d07_authority = _d07_authority(
        requirement=requirement,
        matrix=matrix,
        measurements=measurements,
    )
    decision_required = d07_authority["d07_decision_required"]
    readiness = _readiness_by_family(
        matrix=matrix,
        measurements=measurements,
        drift_by_family={},
    )
    live_ready_family_ids = sorted(
        family_id
        for family_id, value in readiness.items()
        if value["live_ready"]
    )
    split_cost_receipts = _split_cost_receipts(
        task_contracts=task_contracts,
        task_measurements=measurements["qualification_task_measurements"],
    )
    policy = approved_transport_policy(requirement=requirement)
    root_state = _root_state(repo_root=repo_root)
    invocation_policy = effective_invocation_policy()
    wb3_tests = _run_wb3_test_receipts(repo_root=repo_root)
    opener_source = inspect.getsource(_open_provider_request).encode("utf-8")
    cycle_body = {
        "freeze_commit": commit,
        "requirement_closure_hash": task_contracts["requirement_closure_hash"],
        "active_publication_id": root_state["active_publication_id"],
        "matrix_sha256": matrix["matrix_sha256"],
    }
    cycle_id = content_hash(value=cycle_body)
    provider_ledger = {
        "sha256": sha256_bytes(content=b""),
        "row_count": 0,
        "path": (
            FREEZE_CYCLE_ROOT / cycle_id.split(":", maxsplit=1)[1]
            / "provider_ledger.jsonl"
        ).as_posix(),
    }
    family_scope_closure = _family_scope_closure(
        task_contracts=task_contracts,
    )
    body = {
        "record_type": "TABLE_QUALIFICATION_FREEZE_RECEIPT",
        "schema_version": 3,
        "freeze_commit": commit,
        "frozen_at_utc": frozen_at_utc,
        "qualification_cycle_id": cycle_id,
        "d07_decision_required": decision_required,
        "readiness_by_family": readiness,
        "live_ready_family_ids": live_ready_family_ids,
        "identity": {
            "requirement_closure_hash": task_contracts[
                "requirement_closure_hash"
            ],
            "parent_r2_active_publication_id": root_state[
                "active_publication_id"
            ],
            "active_pointer": root_state["active_pointer"],
            "root_hashes": root_state["root_hashes"],
        },
        "wb3_protection": {
            "invocation_control_semantic_hashes": invocation_policy,
            "provider_opener_identity": {
                "path": "scripts/vnext/ai_adapter.py",
                "symbol": "_open_provider_request",
                "source_sha256": sha256_bytes(content=opener_source),
            },
            "regression_receipt": wb3_tests,
        },
        "wb4_compact_transport": {
            "table_payload_serialization_version": (
                TABLE_PAYLOAD_SERIALIZATION_VERSION
            ),
            "encoder_source_sha256": sha256_file(
                path=repo_root / "scripts/vnext/table_payload.py",
            ),
            "decoder_source_sha256": sha256_file(
                path=repo_root / "scripts/vnext/table_payload.py",
            ),
            "decoder_semantic_version": DECODER_SEMANTIC_VERSION,
            "expanded_compact_identity_schema_hash": content_hash(
                value=[
                    "table_payload_serialization_version",
                    "expanded_derived_asset_id",
                    "expanded_grid_sha256",
                    "compact_payload_sha256",
                    "decoder_semantic_version",
                    "round_trip_receipt_id",
                ]
            ),
            "round_trip_receipts": measurements["round_trip_receipts"],
            "qualification_task_measurements": measurements[
                "qualification_task_measurements"
            ],
            "family_maximum_estimated_input_tokens": measurements[
                "family_maximum_estimated_input_tokens"
            ],
            "d07_full_table_no_prefilter_proof": {
                "table_grid_source_sha256": sha256_file(
                    path=repo_root / "scripts/vnext/table_grid.py",
                ),
                "reader_input_source_sha256": sha256_file(
                    path=repo_root / "scripts/vnext/reader_input.py",
                ),
                "all_fixture_count": len(measurements["round_trip_receipts"]),
                "qualification_task_measurement_count": len(
                    measurements["qualification_task_measurements"]
                ),
                "selection_parameters": [],
            },
            "maximum_estimated_input_tokens": measurements[
                "maximum_estimated_input_tokens"
            ],
            "maximum_successfully_estimated_input_tokens": measurements[
                "maximum_successfully_estimated_input_tokens"
            ],
            "blocking_family_ids": measurements["blocking_family_ids"],
            "any_measurement_blocked": measurements[
                "any_measurement_blocked"
            ],
            "d07_authority": d07_authority,
        },
        "wb5_scope_contract": {
            "scope_contract_version": "2",
            "families": family_scope_closure,
            "evidence_binding_hash": sha256_file(
                path=repo_root / "scripts/vnext/evidence.py",
            ),
            "review_binding_hash": sha256_file(
                path=repo_root / "scripts/vnext/review.py",
            ),
        },
        "wb6_task_contracts": {
            "catalog_sha256": task_contracts["catalog_sha256"],
            "fallback_representation_sha256": task_contracts[
                "fallback_representation_sha256"
            ],
            "expected_table_metric_ids": task_contracts["table_metric_ids"],
            "expected_table_family_ids": task_contracts["table_family_ids"],
            "authorized_family_ids": task_contracts["authorized_family_ids"],
            "families": {
                family_id: {
                    "matrix_entry_hash": content_hash(
                        value=matrix["entries"][family_id],
                    ),
                    "contracts": [
                        {
                            key: contract[key]
                            for key in (
                                "task_contract_id",
                                "task_contract_hash",
                                "output_schema_hash",
                                "system_prompt_hash",
                            )
                        }
                        | {
                            "metric_specs": [
                                {
                                    key: metric[key]
                                    for key in (
                                        "metric_id",
                                        "path",
                                        "spec_semantic_hash",
                                        "spec_closure_hash",
                                    )
                                }
                                for metric in contract["metric_specs"]
                            ]
                        }
                        for contract in task_contracts["contracts"]
                        if contract["reader_family_id"] == family_id
                    ],
                }
                for family_id in task_contracts["authorized_family_ids"]
            },
            "split_cost_receipts": split_cost_receipts,
        },
        "provider_state": {
            "provider": policy.provider,
            "model": policy.model,
            "api": policy.api,
            "provider_ledger_before": provider_ledger,
            "qualification_cycle_real_model_egress_count": 0,
            "qualification_cycle_paid_model_call_count": 0,
            "qualification_cycle_sec_egress_count": 0,
            "sec_ledger_before": _request_ledger_binding(repo_root=repo_root),
        },
        "monetary_policy": {
            "repository_monetary_budget_enforcement": False,
            "monetary_cost_observability_only": True,
            "forbidden_monetary_fields_present": [],
        },
        "protected_closure": _protected_closure(
            repo_root=repo_root,
            matrix=matrix,
            task_contracts=task_contracts,
        ),
    }
    receipt_id = content_hash(value=body)
    return {
        "table_qualification_freeze_receipt_id": receipt_id,
        **body,
    }


def write_table_qualification_freeze_receipt(
    *, repo_root: Path, freeze_commit: str, frozen_at_utc: str,
) -> Dict[str, object]:
    """Write one content-addressed freeze receipt and empty local cycle ledger.

    Args:
        repo_root: Repository authority root.
        freeze_commit: Exact committed source freeze identity.
        frozen_at_utc: Explicit UTC freeze timestamp.

    Returns:
        Receipt plus its portable repository-relative path.
    """
    receipt = build_table_qualification_freeze_receipt(
        repo_root=repo_root,
        freeze_commit=freeze_commit,
        frozen_at_utc=frozen_at_utc,
    )
    digest = receipt["table_qualification_freeze_receipt_id"].split(
        ":", maxsplit=1,
    )[1]
    receipt_relative = FREEZE_RECEIPT_ROOT / (digest + ".json")
    receipt_path = repo_root / receipt_relative
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path=receipt_path, value=receipt)
    ledger_relative = Path(receipt["provider_state"]["provider_ledger_before"]["path"])
    ledger_path = repo_root / ledger_relative
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists() and ledger_path.read_bytes() != b"":
        raise TableQualificationFreezeError("Qualification provider ledger differs")
    if not ledger_path.exists():
        ledger_path.write_bytes(b"")
    return {**receipt, "receipt_path": receipt_relative.as_posix()}


def _provider_ledger_before_binding(
    *, repo_root: Path, receipt: Mapping[str, object],
) -> Dict[str, object]:
    """Verify and return the receipt-owned provider-ledger before prefix.

    Qualification may append later rows, so validation deliberately compares
    only the frozen row-count prefix.  This prevents either a parallel runtime
    ledger or a rewritten historical prefix from becoming evidence authority.
    """
    state = receipt.get("provider_state")
    if type(state) is not dict or type(state.get("provider_ledger_before")) is not dict:
        raise TableQualificationFreezeError("Qualification provider ledger binding is invalid")
    binding = dict(state["provider_ledger_before"])
    if (
        set(binding) != {"path", "row_count", "sha256"}
        or type(binding["path"]) is not str
        or type(binding["row_count"]) is not int
        or binding["row_count"] < 0
        or type(binding["sha256"]) is not str
        or len(binding["sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in binding["sha256"]
        )
    ):
        raise TableQualificationFreezeError("Qualification provider ledger binding is invalid")
    cycle_id = receipt.get("qualification_cycle_id")
    if type(cycle_id) is not str or not cycle_id.startswith("sha256:"):
        raise TableQualificationFreezeError("Qualification cycle identity is invalid")
    expected = (
        FREEZE_CYCLE_ROOT
        / cycle_id.split(":", maxsplit=1)[1]
        / "provider_ledger.jsonl"
    ).as_posix()
    if binding["path"] != expected:
        raise TableQualificationFreezeError("Qualification provider ledger path differs")
    path = repo_root / Path(binding["path"])
    if path.is_symlink() or not path.is_file():
        raise TableQualificationFreezeError("Qualification provider ledger is absent")
    content = path.read_bytes()
    lines = content.splitlines(keepends=True)
    if (
        any(not line.endswith(b"\n") for line in lines)
        or len(lines) < binding["row_count"]
    ):
        raise TableQualificationFreezeError("Qualification provider ledger prefix is invalid")
    if sha256_bytes(content=b"".join(lines[:binding["row_count"]])) != binding["sha256"]:
        raise TableQualificationFreezeError("Qualification provider ledger prefix differs")
    return binding


def _frozen_family_measurements(
    *, frozen: Mapping[str, object], family_id: str,
) -> Dict[str, object]:
    """Project immutable all-family evidence to one family fault domain."""
    rows = frozen.get("qualification_task_measurements")
    maxima = frozen.get("family_maximum_estimated_input_tokens")
    if type(rows) is not list or type(maxima) is not dict:
        raise TableQualificationFreezeError(
            "Frozen family measurement evidence is invalid"
        )
    family_rows = [
        copy.deepcopy(row)
        for row in rows
        if type(row) is dict and row.get("family_id") == family_id
    ]
    if not family_rows or family_id not in maxima:
        raise TableQualificationFreezeError(
            "Frozen family measurement evidence is absent"
        )
    return {
        "qualification_task_measurements": family_rows,
        "family_maximum_estimated_input_tokens": {
            family_id: maxima[family_id],
        },
    }


def _family_status_result(
    *, receipt: Mapping[str, object], receipt_id: str, family_id: str,
    matrix: Mapping[str, object], measurements: Mapping[str, object],
    drift_labels: Sequence[str], provider_ledger_before: Mapping[str, object],
) -> Dict[str, object]:
    """Build one public result from one family-local fault domain."""
    drift_by_family = (
        {family_id: sorted(set(drift_labels))}
        if drift_labels else {}
    )
    readiness = _readiness_by_family(
        matrix=matrix,
        measurements=measurements,
        drift_by_family=drift_by_family,
    )
    _validate_readiness_shape(readiness=readiness)
    ready = readiness[family_id]["live_ready"] is True
    return {
        "receipt_id": receipt_id,
        "qualification_cycle_id": receipt["qualification_cycle_id"],
        "d07_decision_required": receipt["d07_decision_required"],
        "readiness_by_family": readiness,
        "live_ready_family_ids": [family_id] if ready else [],
        "blocked_family_ids": [] if ready else [family_id],
        "provider_ledger_before": dict(provider_ledger_before),
        "invalidated_family_ids": [family_id] if drift_labels else [],
        "drift_by_family": drift_by_family,
    }


def _validate_requested_family(
    *, repo_root: Path, receipt: Mapping[str, object], receipt_id: str,
    family_id: str, requirement: Mapping[str, object],
    frozen_measurements: Mapping[str, object],
    frozen_d07: Mapping[str, object],
    provider_ledger_before: Mapping[str, object],
) -> Dict[str, object]:
    """Rebuild shared authority plus exactly one family-local fault domain."""
    frozen_readiness = receipt["readiness_by_family"]
    protected = receipt["protected_closure"]
    if (
        family_id not in frozen_readiness
        or type(protected) is not dict
        or type(protected.get("families")) is not dict
        or family_id not in protected["families"]
    ):
        raise TableQualificationFreezeError(
            "TABLE_QUALIFICATION_FAMILY_UNKNOWN:{}".format(family_id)
        )
    frozen_matrix_all = _frozen_readiness_matrix(
        readiness=frozen_readiness,
        matrix_sha256=frozen_d07["matrix_sha256"],
    )
    frozen_matrix = {
        "entries": {
            family_id: frozen_matrix_all["entries"][family_id],
        },
        "matrix_sha256": frozen_matrix_all["matrix_sha256"],
    }
    frozen_family_measurements = _frozen_family_measurements(
        frozen=frozen_measurements,
        family_id=family_id,
    )
    frozen_subset = {
        "shared_engine_files": protected["shared_engine_files"],
        "families": {
            family_id: protected["families"][family_id],
        },
    }
    current_shared = _shared_engine_closure(repo_root=repo_root)
    shared_only_current = {
        "shared_engine_files": current_shared,
        "families": {
            family_id: protected["families"][family_id],
        },
    }
    drift = _protected_closure_drift(
        frozen=frozen_subset,
        current=shared_only_current,
    ).get(family_id, [])
    try:
        root_drift = _root_state_drift(
            frozen_identity=receipt["identity"],
            current_root=_root_state(repo_root=repo_root),
        )
    except TableQualificationFreezeError:
        root_drift = ["r2_root:current_state_unreadable"]
    drift = sorted(set(drift) | set(root_drift))
    estimator_hash = _current_estimator_authority_hash(
        repo_root=repo_root,
        requirement=requirement,
    )
    if [estimator_hash] != frozen_d07["estimator_authority_hashes"]:
        drift = sorted(
            set(drift) | {"shared_measurement:estimator_authority"}
        )
    if drift:
        return _family_status_result(
            receipt=receipt,
            receipt_id=receipt_id,
            family_id=family_id,
            matrix=frozen_matrix,
            measurements=frozen_family_measurements,
            drift_labels=drift,
            provider_ledger_before=provider_ledger_before,
        )
    try:
        matrix = load_table_qualification_matrix(
            repo_root=repo_root,
            family_id=family_id,
        )
        task_contracts = load_table_task_contracts(
            repo_root=repo_root,
            family_id=family_id,
        )
        entry = matrix["entries"][family_id]
        if (
            task_contracts["authorized_family_ids"] != [family_id]
            or set(entry["task_contract_ids"])
            != {
                contract["task_contract_id"]
                for contract in task_contracts["contracts"]
            }
        ):
            raise TableQualificationFamilyError(
                family_id=family_id,
                reason_code="LOCAL_TASK_AUTHORITY_INVALID",
                message="Requested matrix/task binding differs",
            )
        current_family_closure = _family_semantic_closure(
            repo_root=repo_root,
            family_id=family_id,
            matrix_entry=entry,
            task_contracts=task_contracts,
        )
        current_measurements = _family_measurement_receipts(
            repo_root=repo_root,
            family_id=family_id,
            matrix=matrix,
            task_contracts=task_contracts,
            requirement=requirement,
        )
    except (TableQualificationFamilyError,
            TableTaskContractFamilyError) as error:
        return _family_status_result(
            receipt=receipt,
            receipt_id=receipt_id,
            family_id=family_id,
            matrix=frozen_matrix,
            measurements=frozen_family_measurements,
            drift_labels=["family_failure:" + error.reason_code],
            provider_ledger_before=provider_ledger_before,
        )
    except TableTaskContractError as error:
        raise TableQualificationFreezeError(
            "Shared table task authority is invalid"
        ) from error
    current_subset = {
        "shared_engine_files": current_shared,
        "families": {family_id: current_family_closure},
    }
    drift = _protected_closure_drift(
        frozen=frozen_subset,
        current=current_subset,
    ).get(family_id, [])
    frozen_rows = frozen_family_measurements[
        "qualification_task_measurements"
    ]
    current_rows = current_measurements[
        "qualification_task_measurements"
    ]
    if frozen_rows != current_rows:
        drift.append(
            "family_measurements:qualification_task_measurements"
        )
    if (
        frozen_family_measurements[
            "family_maximum_estimated_input_tokens"
        ][family_id]
        != current_measurements[
            "family_maximum_estimated_input_tokens"
        ][family_id]
    ):
        drift.append(
            "family_measurements:maximum_estimated_input_tokens"
        )
    if matrix["entries"][family_id]["token_context_limits"][
        "max_estimated_input_tokens"
    ] != frozen_d07["effective_d07_choice"][
        "max_estimated_input_tokens"
    ]:
        drift.append("family_d07_threshold")
    return _family_status_result(
        receipt=receipt,
        receipt_id=receipt_id,
        family_id=family_id,
        matrix=matrix,
        measurements=current_measurements,
        drift_labels=drift,
        provider_ledger_before=provider_ledger_before,
    )


def validate_table_qualification_freeze(
    *, repo_root: Path, family_id: Optional[str] = None,
) -> Dict[str, object]:
    """Revalidate the configured freeze and return only affected family IDs.

    Args:
        repo_root: Repository authority root.

    Returns:
        Receipt identity and the exact family IDs invalidated by current drift.
    """
    pointer = _json_object(
        repo_root=repo_root,
        relative=FREEZE_POINTER_PATH,
        label="table qualification freeze pointer",
    )
    if set(pointer) != POINTER_FIELDS or pointer["schema_version"] != 1:
        raise TableQualificationFreezeError("Freeze pointer fields are invalid")
    receipt_relative = Path(str(pointer["receipt_path"]))
    receipt = _json_object(
        repo_root=repo_root,
        relative=receipt_relative,
        label="table qualification freeze receipt",
    )
    if set(receipt) != RECEIPT_FIELDS or receipt["schema_version"] != 3:
        raise TableQualificationFreezeError("Freeze receipt fields are invalid")
    receipt_id = receipt["table_qualification_freeze_receipt_id"]
    body = {
        key: receipt[key]
        for key in receipt
        if key != "table_qualification_freeze_receipt_id"
    }
    if (
        receipt_id != content_hash(value=body)
        or pointer["receipt_id"] != receipt_id
        or pointer["qualification_cycle_id"]
        != receipt["qualification_cycle_id"]
    ):
        raise TableQualificationFreezeError("Freeze receipt identity differs")
    wb3_protection = receipt["wb3_protection"]
    if type(wb3_protection) is not dict or "regression_receipt" not in (
        wb3_protection
    ):
        raise TableQualificationFreezeError("WB-3 freeze protection is invalid")
    _validate_wb3_test_receipt(
        repo_root=repo_root,
        value=wb3_protection["regression_receipt"],
    )
    provider_ledger_before = _provider_ledger_before_binding(
        repo_root=repo_root,
        receipt=receipt,
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    wb4 = receipt["wb4_compact_transport"]
    if type(wb4) is not dict:
        raise TableQualificationFreezeError("WB-4 freeze evidence is invalid")
    _validate_readiness_shape(readiness=receipt["readiness_by_family"])
    frozen_measurements = _validate_frozen_d07_evidence(
        requirement=requirement,
        wb4=wb4,
        readiness=receipt["readiness_by_family"],
    )
    frozen_d07 = wb4["d07_authority"]
    if (
        receipt["d07_decision_required"]
        != frozen_d07["d07_decision_required"]
    ):
        raise TableQualificationFreezeError(
            "Frozen D-07 decision state differs"
        )
    frozen_matrix = _frozen_readiness_matrix(
        readiness=receipt["readiness_by_family"],
        matrix_sha256=frozen_d07["matrix_sha256"],
    )
    expected_frozen_readiness = _readiness_by_family(
        matrix=frozen_matrix,
        measurements=frozen_measurements,
        drift_by_family={},
    )
    if receipt["readiness_by_family"] != expected_frozen_readiness:
        raise TableQualificationFreezeError("Frozen family readiness differs")
    expected_frozen_live = sorted(
        family_id
        for family_id, value in expected_frozen_readiness.items()
        if value["live_ready"]
    )
    if receipt["live_ready_family_ids"] != expected_frozen_live:
        raise TableQualificationFreezeError(
            "Frozen live-ready family set differs"
        )
    if family_id is not None:
        return _validate_requested_family(
            repo_root=repo_root,
            receipt=receipt,
            receipt_id=receipt_id,
            family_id=family_id,
            requirement=requirement,
            frozen_measurements=frozen_measurements,
            frozen_d07=frozen_d07,
            provider_ledger_before=provider_ledger_before,
        )
    protected = receipt["protected_closure"]
    task_contracts = load_table_task_contracts(repo_root=repo_root)
    matrix = load_table_qualification_matrix(repo_root=repo_root)
    if sorted(matrix["entries"]) != task_contracts["authorized_family_ids"]:
        raise TableQualificationFreezeError(
            "Matrix family set differs from tasks"
        )
    measurements = _current_measurement_receipts(
        repo_root=repo_root,
        matrix=matrix,
        task_contracts=task_contracts,
        requirement=requirement,
    )
    current = _protected_closure(
        repo_root=repo_root,
        matrix=matrix,
        task_contracts=task_contracts,
    )
    drift_by_family = _protected_closure_drift(
        frozen=protected,
        current=current,
    )
    try:
        root_drift = _root_state_drift(
            frozen_identity=receipt["identity"],
            current_root=_root_state(repo_root=repo_root),
        )
    except TableQualificationFreezeError:
        root_drift = ["r2_root:current_state_unreadable"]
    if root_drift:
        for family_id in task_contracts["authorized_family_ids"]:
            existing = drift_by_family.get(family_id, [])
            drift_by_family[family_id] = sorted(set(existing) | set(root_drift))
    drift_by_family = _measurement_drift_by_family(
        frozen=frozen_measurements,
        current=measurements,
        current_matrix=matrix,
        frozen_d07=frozen_d07,
        protected_drift=drift_by_family,
    )
    readiness = _readiness_by_family(
        matrix=matrix,
        measurements=measurements,
        drift_by_family=drift_by_family,
    )
    _validate_readiness_shape(readiness=readiness)
    live_ready_family_ids = sorted(
        family_id
        for family_id, value in readiness.items()
        if value["live_ready"]
    )
    return {
        "receipt_id": receipt_id,
        "qualification_cycle_id": receipt["qualification_cycle_id"],
        "d07_decision_required": receipt["d07_decision_required"],
        "readiness_by_family": readiness,
        "live_ready_family_ids": live_ready_family_ids,
        "blocked_family_ids": sorted(
            family_id
            for family_id, value in readiness.items()
            if not value["live_ready"]
        ),
        "provider_ledger_before": provider_ledger_before,
        "invalidated_family_ids": sorted(drift_by_family),
        "drift_by_family": drift_by_family,
    }


def require_table_qualification_freeze(
    *, repo_root: Path, family_id: str,
) -> Dict[str, object]:
    """Fail closed from only the requested family's three readiness gates.

    Args:
        repo_root: Repository authority root.
        family_id: Reader family planned for qualification.

    Returns:
        Validated freeze status for an unaffected authorized family.
    """
    status = validate_table_qualification_freeze(
        repo_root=repo_root,
        family_id=family_id,
    )
    readiness = status["readiness_by_family"].get(family_id)
    if type(readiness) is not dict:
        raise TableQualificationFreezeError(
            "TABLE_QUALIFICATION_FAMILY_UNKNOWN:{}".format(family_id)
        )
    if readiness["live_ready"] is not True:
        reasons = ",".join(readiness["blocking_reason_codes"])
        raise TableQualificationFreezeError(
            "TABLE_QUALIFICATION_FAMILY_NOT_READY:{}:{}".format(
                family_id, reasons,
            )
        )
    return status
