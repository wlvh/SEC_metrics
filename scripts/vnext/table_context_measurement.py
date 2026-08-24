"""Acquire one exact table prompt-token measurement without qualification.

The Stage-C path is deliberately separate from catalog qualification.  It
rebuilds one Marriott lodging request from immutable repository authority,
issues an opaque execution capability only after an external exact-HEAD
authorization, and permanently consumes that capability at the first provider
socket marker.  It never creates a Run, Candidate, EvidenceCheck, ReviewUnit,
VerifiedObservation, qualification receipt, or publication candidate.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

from git_workspace import git_checkout_metadata_error
from git_workspace import sanitized_git_environment
from sec_http import parse_request_log_rows, request_log_attempt_id

from .ai_adapter import approved_transport_policy, build_provider_request_body
from .batch_workflow import BatchWorkflowError, validate_request_attempt_binding
from .canonical import atomic_write_json, canonical_json_bytes, content_hash
from .canonical import parse_utc_timestamp, sha256_bytes, sha256_file
from .canonical import strict_json_file, strict_json_loads
from .invocation_control import UnknownRemoteOutcomeError
from .provider_runtime import estimate_context_tokens
from .provider_runtime import load_provider_runtime_authority
from .reader_input import build_reader_input_manifest, prepare_live_reader_request
from .reader_input import prepare_reader_request
from .requirements import ISSUE_15_D07_MEASUREMENT_EXCEPTION
from .requirements import load_requirement_snapshot
from .sources import load_raw_blob_bytes, raw_blob_record
from .sources import source_reference_record
from .table_grid import build_table_grid
from .table_payload import TABLE_PAYLOAD_SERIALIZATION_VERSION
from .table_qualification_freeze import load_table_qualification_matrix
from .table_task_contracts import resolve_table_task_contract


MEASUREMENT_ROOT = Path(
    "artifacts/vnext/table_stage_c_evidence/token_measurement"
)
MEASUREMENT_PLAN_ROOT = MEASUREMENT_ROOT / "plans"
MEASUREMENT_EXECUTION_ROOT = MEASUREMENT_ROOT / "executions"
EXTERNAL_AUTHORIZATION_STATEMENT = "AUTHORIZE_ONE_TOKEN_MEASUREMENT"
MEASUREMENT_ORDINAL = 1
STAGE_C_BASELINE = {
    "requirement_closure_hash": (
        "sha256:fcd308ed51fe3b7cd6d4dcc82ba373d3"
        "1832f0f1f522c3b8b765e766693a5822"
    ),
    "effective_d07_record_hash": (
        "sha256:bc9830fc98a331ea54625b499665c3e2"
        "ef71a478194a9f066a31ac5c56de1ec8"
    ),
    "table_qualification_freeze_receipt_id": (
        "sha256:9c8ca60dc6fb97fcc693618694a96d009"
        "e110efc0ea2d28366022d2d8c0824b6"
    ),
    "qualification_cycle_id": (
        "sha256:df8deeac28b35fff526c5f0b66d7866f"
        "695c392a94d17cb05c45e5d81b42781c"
    ),
    "stage_a_snapshot_id": (
        "sha256:bf2d375dc966f2503582ab1d13c464fd"
        "9775cac213d4903884b3fbd437fb2888"
    ),
    "owner_decision_packet_id": (
        "sha256:09a9cc1933fc5d60efa00a183583e20dd"
        "59283b4397bfdb6b0cfcb4afd1b85a7"
    ),
}
_CURRENT_D07_HASH = (
    "sha256:200bb6feae25c5683260e2dd8a758f1a"
    "b3f0480b8694bb802ca44fd80835554f"
)
_AUTHORIZATION_CAPABILITY = object()
_GIT_OID = re.compile(r"^[0-9a-f]{40}$")
_ACCESSION = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_AUTHORIZATION_FIELDS = {
    "api",
    "authorization_id",
    "authorized_at_utc",
    "authorized_repository_head",
    "authorized_repository_tree",
    "effective_d07_record_hash",
    "external_authorization_statement",
    "family_id",
    "measurement_cycle_id",
    "measurement_ordinal",
    "measurement_plan_id",
    "model",
    "output_schema_hash",
    "protected_closure_hash",
    "provider",
    "provider_request_body_sha256",
    "requirement_closure_hash",
    "source_sha256",
    "system_prompt_hash",
    "task_contract_id",
}
_TRANSPORT_RESULT_FIELDS = {
    "error_class",
    "http_status",
    "provider_request_id",
    "provider_response_bytes",
    "transport_terminal_status",
}
_EVIDENCE_FIELDS = {
    "actual_completion_tokens",
    "actual_prompt_tokens",
    "actual_total_tokens",
    "api",
    "authorization_id",
    "bytes_per_actual_prompt_token",
    "estimated_input_tokens",
    "exact_estimator_identity",
    "execution_id",
    "http_status",
    "measurement_cycle_id",
    "measurement_evidence_id",
    "measurement_ordinal",
    "measurement_plan_id",
    "model",
    "paid_model_provider_call_count",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "provider",
    "provider_request_body_sha256",
    "provider_request_id",
    "provider_response_sha256",
    "publication_eligible",
    "qualification_credit",
    "real_SEC_egress_count",
    "real_model_provider_egress_count",
    "record_type",
    "response_reuse_for_qualification",
    "retry_performed",
    "schema_version",
    "status",
    "transport_terminal_status",
    "usage_raw_field_hash",
}
_PROTECTED_RUNTIME_PATHS = (
    Path("catalog/table_task_contracts.json"),
    Path("config/provider_model_runtime.json"),
    Path("config/table_qualification_matrix.json"),
    Path("evidence/requests_log.csv"),
    Path("evidence/requests_log_manifest.json"),
    Path("requirements/issue_15_v1/CONTRACT.md"),
    Path("requirements/issue_15_v1/baseline_manifest.json"),
    Path("requirements/issue_15_v1/decision_register.json"),
    Path("requirements/issue_15_v1/foundation_verification_receipt.json"),
    Path("requirements/issue_15_v1/legacy_semantic_producer_inventory.json"),
    Path("requirements/issue_15_v1/source_strategy_baseline_receipt.json"),
    Path("requirements/issue_15_v1/transfer_manifest.json"),
    Path("scripts/sec_http.py"),
    Path("scripts/vnext/ai_adapter.py"),
    Path("scripts/vnext/canonical.py"),
    Path("scripts/vnext/provider_runtime.py"),
    Path("scripts/vnext/reader_input.py"),
    Path("scripts/vnext/requirements.py"),
    Path("scripts/vnext/sources.py"),
    Path("scripts/vnext/table_context_measurement.py"),
    Path("scripts/vnext/table_grid.py"),
    Path("scripts/vnext/table_payload.py"),
    Path("scripts/vnext/table_task_contracts.py"),
)


class TableContextMeasurementError(RuntimeError):
    """Report a stable Stage-C authorization or execution failure."""

    def __init__(self, *, code: str, message: str) -> None:
        """Create an operator-visible failure without leaking credentials."""
        super().__init__("{}: {}".format(code, message))
        self.code = code


@dataclass(frozen=True, init=False)
class TableContextMeasurementAuthorization:
    """Carry one module-issued exact-HEAD measurement capability."""

    _binding: Dict[str, object]
    _capability: object

    def __init__(
        self, *, binding: Mapping[str, object], capability: object,
    ) -> None:
        """Reject construction outside the exact-head issuer."""
        if capability is not _AUTHORIZATION_CAPABILITY:
            raise TableContextMeasurementError(
                code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_REQUIRED",
                message="Measurement authorization is module-owned",
            )
        object.__setattr__(self, "_binding", copy.deepcopy(dict(binding)))
        object.__setattr__(self, "_capability", capability)

    def as_mapping(self) -> Dict[str, object]:
        """Return a detached audit copy of the authorization binding."""
        return copy.deepcopy(self._binding)


@dataclass(frozen=True)
class _PreparedMeasurement:
    """Hold exact non-persisted request objects beside the portable plan."""

    plan: Dict[str, object]
    live_prepared_request: object
    provider_request_body: bytes
    output_schema_bytes: bytes


_PREPARED_CACHE: Dict[str, _PreparedMeasurement] = {}


def _fail(*, code: str, message: str) -> None:
    """Raise one stable measurement error."""
    raise TableContextMeasurementError(code=code, message=message)


def _text(*, value: object, label: str) -> str:
    """Return one non-empty exact string."""
    if type(value) is not str or not value:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="{} is invalid".format(label),
        )
    return value


def _content_addressed_record(
    *, path: Path, id_field: str, expected_id: str,
) -> Dict[str, object]:
    """Read and recompute one immutable historical Stage-C dependency."""
    value = strict_json_file(path=path)
    if type(value) is not dict or value.get(id_field) != expected_id:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_BASELINE_DRIFT",
            message="Historical {} identity differs".format(id_field),
        )
    body = {key: value[key] for key in value if key != id_field}
    if content_hash(value=body) != expected_id:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_BASELINE_DRIFT",
            message="Historical {} bytes differ".format(id_field),
        )
    return dict(value)


def _stage_c_baseline(*, repo_root: Path) -> Dict[str, object]:
    """Verify the exact PR-19 freeze/snapshot/packet lineage without rebuilding."""
    pointer = strict_json_file(
        path=repo_root / "config/table_qualification_freeze.json",
    )
    freeze_id = STAGE_C_BASELINE["table_qualification_freeze_receipt_id"]
    if (
        type(pointer) is not dict
        or pointer.get("receipt_id") != freeze_id
        or pointer.get("qualification_cycle_id")
        != STAGE_C_BASELINE["qualification_cycle_id"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_BASELINE_DRIFT",
            message="Current table-freeze pointer differs",
        )
    freeze_digest = str(freeze_id).split(":", maxsplit=1)[1]
    freeze = _content_addressed_record(
        path=(
            repo_root
            / "artifacts/vnext/table_qualification_freeze/receipts"
            / (freeze_digest + ".json")
        ),
        id_field="table_qualification_freeze_receipt_id",
        expected_id=str(freeze_id),
    )
    stage_a = _content_addressed_record(
        path=(
            repo_root
            / "artifacts/vnext/table_qualification_freeze/stage_a_validation"
            / (freeze_digest + ".json")
        ),
        id_field="stage_a_snapshot_id",
        expected_id=str(STAGE_C_BASELINE["stage_a_snapshot_id"]),
    )
    owner_pointer = strict_json_file(
        path=(
            repo_root
            / "artifacts/vnext/table_qualification_freeze"
            / "current_owner_decision_packet.json"
        )
    )
    owner_id = STAGE_C_BASELINE["owner_decision_packet_id"]
    if (
        type(owner_pointer) is not dict
        or owner_pointer.get("owner_decision_packet_id") != owner_id
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_BASELINE_DRIFT",
            message="Owner packet pointer differs",
        )
    owner = _content_addressed_record(
        path=(
            repo_root
            / "artifacts/vnext/table_qualification_freeze/decision_packets"
            / (str(owner_id).split(":", maxsplit=1)[1] + ".json")
        ),
        id_field="owner_decision_packet_id",
        expected_id=str(owner_id),
    )
    if (
        freeze.get("qualification_cycle_id")
        != STAGE_C_BASELINE["qualification_cycle_id"]
        or freeze.get("identity", {}).get("requirement_closure_hash")
        != STAGE_C_BASELINE["requirement_closure_hash"]
        or stage_a.get("freeze_receipt_id") != freeze_id
        or owner.get("freeze_binding", {}).get("qualification_cycle_id")
        != STAGE_C_BASELINE["qualification_cycle_id"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_BASELINE_DRIFT",
            message="Stage-C historical dependency bindings differ",
        )
    return {
        "table_qualification_freeze_receipt_id": freeze_id,
        "qualification_cycle_id": STAGE_C_BASELINE["qualification_cycle_id"],
        "stage_a_snapshot_id": STAGE_C_BASELINE["stage_a_snapshot_id"],
        "owner_decision_packet_id": owner_id,
        "historical_requirement_closure_hash": STAGE_C_BASELINE[
            "requirement_closure_hash"
        ],
        "historical_effective_d07_record_hash": STAGE_C_BASELINE[
            "effective_d07_record_hash"
        ],
    }


def _source_url(*, declaration: Mapping[str, object]) -> str:
    """Derive one official SEC Archives URL from matrix-owned coordinates."""
    cik = _text(value=declaration.get("cik"), label="source CIK")
    accession = _text(
        value=declaration.get("accession"), label="source accession",
    )
    document = _text(
        value=declaration.get("document_name"), label="source document",
    )
    if not cik.isdigit() or _ACCESSION.fullmatch(accession) is None:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Source filing identity is invalid",
        )
    return "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(
        str(int(cik)), accession.replace("-", ""), document,
    )


def _source_binding(
    *, repo_root: Path, matrix_entry: Mapping[str, object],
    exception: Mapping[str, object],
) -> Dict[str, object]:
    """Rebuild the exact Marriott immutable-attempt binding from the ledger."""
    declaration = matrix_entry.get("development_source")
    fields = {
        "accession",
        "cik",
        "company_id",
        "document_name",
        "source_kind",
        "source_repo_relative_path",
        "source_sha256",
    }
    if type(declaration) is not dict or set(declaration) != fields:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Development source fields differ",
        )
    source = dict(declaration)
    if (
        source["source_kind"] != "IMMUTABLE_ATTEMPT"
        or source["company_id"] != exception["source_company_id"]
        or source["source_sha256"] != exception["source_sha256"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="D-07 measurement source differs from matrix",
        )
    relative = Path(_text(
        value=source["source_repo_relative_path"], label="source path",
    ))
    if relative.is_absolute() or ".." in relative.parts:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Measurement source path is unsafe",
        )
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Measurement source bytes are absent",
        )
    if sha256_file(path=path) != source["source_sha256"]:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Measurement source bytes differ",
        )
    source_url = _source_url(declaration=source)
    rows = parse_request_log_rows(
        text=(repo_root / "evidence/requests_log.csv").read_text(
            encoding="utf-8",
        )
    )
    matches = [
        (index, row)
        for index, row in enumerate(rows)
        if row["source_url"] == source_url
        and row["content_sha256"] == source["source_sha256"]
        and row["accession"] == source["accession"]
        and row["document_name"] == source["document_name"]
        and row["repo_relative_path"] == source["source_repo_relative_path"]
        and row["headers_repo_relative_path"].startswith(
            "evidence/request_attempts/"
        )
    ]
    if len(matches) != 1:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Measurement source ledger binding is ambiguous",
        )
    index, row = matches[0]
    attempt_id = request_log_attempt_id(row_index=index, row=row)
    try:
        proof = validate_request_attempt_binding(
            repo_root=repo_root,
            source_url=source_url,
            content_sha256=str(source["source_sha256"]),
            accession=str(source["accession"]),
            document_name=str(source["document_name"]),
            request_attempt_id=attempt_id,
            require_immutable=True,
        )
    except BatchWorkflowError as error:
        raise TableContextMeasurementError(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Immutable request-attempt proof differs",
        ) from error
    body = {
        "source_declaration": source,
        "source_url": source_url,
        "source_role": "target_primary",
        **proof,
    }
    return {**body, "source_binding_hash": content_hash(value=body)}


def _protected_file_bindings(
    *, repo_root: Path, source_binding: Mapping[str, object],
    task_contract: Mapping[str, object],
) -> Dict[str, object]:
    """Hash the execution-relevant closure without packet or runtime outputs."""
    paths = set(_PROTECTED_RUNTIME_PATHS)
    paths.add(Path(str(source_binding["request_repo_relative_path"])))
    paths.add(Path(str(source_binding["request_headers_repo_relative_path"])))
    for value in task_contract["metric_spec_paths"]:
        paths.add(Path(str(value)))
    bindings = {}
    for relative in sorted(paths, key=lambda value: value.as_posix()):
        if relative.is_absolute() or ".." in relative.parts:
            _fail(
                code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
                message="Protected path is unsafe",
            )
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            _fail(
                code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
                message="Protected path is absent",
            )
        bindings[relative.as_posix()] = {
            "sha256": sha256_file(path=path),
            "size": path.stat().st_size,
        }
    body = {"files": bindings}
    return {**body, "protected_closure_hash": content_hash(value=body)}


def _prepare_measurement(*, repo_root: Path) -> _PreparedMeasurement:
    """Rebuild the exact full-table provider request with no network action."""
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    d07 = requirement["effective_decisions"]["D-07"]
    exception = d07["choice"].get("measurement_exception")
    if (
        content_hash(value=d07) != _CURRENT_D07_HASH
        or exception != ISSUE_15_D07_MEASUREMENT_EXCEPTION
        or d07["choice"]["live_measurement_authorized"] is not False
        or d07["choice"]["live_qualification_authorized"] is not False
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Effective D-07 measurement exception differs",
        )
    family_id = str(exception["family_id"])
    task_id = str(exception["task_contract_id"])
    matrix = load_table_qualification_matrix(
        repo_root=repo_root, family_id=family_id,
    )
    entry = matrix["entries"].get(family_id)
    if (
        type(entry) is not dict
        or task_id not in entry["task_contract_ids"]
        or entry["token_context_limits"]["max_estimated_input_tokens"]
        != d07["choice"]["max_estimated_input_tokens"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="D-07 measurement target differs from matrix",
        )
    task = resolve_table_task_contract(
        repo_root=repo_root,
        task_contract_id=task_id,
        family_id=family_id,
    )
    if (
        task["reader_family_id"] != family_id
        or TABLE_PAYLOAD_SERIALIZATION_VERSION != exception["serializer_version"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="D-07 task or serializer binding differs",
        )
    source = _source_binding(
        repo_root=repo_root, matrix_entry=entry, exception=exception,
    )
    protected = _protected_file_bindings(
        repo_root=repo_root, source_binding=source, task_contract=task,
    )
    cache_key = content_hash(value={
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "effective_d07_record_hash": content_hash(value=d07),
        "matrix_sha256": matrix["matrix_sha256"],
        "task_contract": task,
        "source_binding": source,
        "protected_closure_hash": protected["protected_closure_hash"],
    })
    if cache_key in _PREPARED_CACHE:
        return _PREPARED_CACHE[cache_key]
    declaration = source["source_declaration"]
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=str(source["request_repo_relative_path"]),
        media_type=str(entry["source_media_type"]),
    )
    source_reference = source_reference_record(
        raw_blob=raw,
        company_id=str(declaration["company_id"]),
        source_url=str(source["source_url"]),
        accession=str(declaration["accession"]),
        document_name=str(declaration["document_name"]),
        source_role=str(source["source_role"]),
        request_attempt_id=str(source["request_attempt_id"]),
    )
    asset = build_table_grid(
        html_bytes=load_raw_blob_bytes(repo_root=repo_root, raw_blob=raw),
        parent_raw_asset_ids=[str(raw["raw_asset_id"])],
        storage_uri=(
            "artifacts/vnext/table_stage_c_evidence/"
            "lodging_measurement_derived_asset.json"
        ),
    )
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=[str(source_reference["source_reference_id"])],
    )
    prepared = prepare_reader_request(
        manifest=manifest,
        derived_asset=asset,
        repo_root=repo_root,
        task_contract_id=task_id,
    )
    live = prepare_live_reader_request(
        prepared_request=prepared,
        raw_blob=raw,
        source_reference=source_reference,
        derived_asset=asset,
        reader_manifest=manifest,
        disclosure_spec_path="catalog/table_task_contracts.json",
        immutable_source_repo_relative_path=str(
            source["request_repo_relative_path"]
        ),
    )
    policy = approved_transport_policy(requirement=requirement)
    provider_body, output_schema = build_provider_request_body(
        policy=policy, reader_request_bytes=prepared.request_bytes,
    )
    runtime = load_provider_runtime_authority(
        repo_root=repo_root,
        provider=policy.provider,
        model=policy.model,
        api=policy.api,
    )
    estimated = estimate_context_tokens(
        request_body=provider_body, authority=runtime,
    )
    if (
        estimated <= d07["choice"]["max_estimated_input_tokens"]
        or estimated > runtime["maximum_context_tokens"]
        or len(provider_body) > policy.maximum_payload_bytes
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORITY_INVALID",
            message="Exact exception is not the sole context bypass",
        )
    baseline = _stage_c_baseline(repo_root=repo_root)
    body = {
        "schema_version": 1,
        "record_type": "TABLE_CONTEXT_MEASUREMENT_PLAN",
        "purpose": exception["purpose"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "effective_d07_record_hash": content_hash(value=d07),
        "historical_stage_c_baseline": baseline,
        "family_id": family_id,
        "task_contract_id": task_id,
        "source_company_id": exception["source_company_id"],
        "source_sha256": exception["source_sha256"],
        "source_binding": source,
        "source_binding_hash": source["source_binding_hash"],
        "table_payload_serialization_version": (
            prepared.table_payload_serialization_version
        ),
        "reader_input_manifest_id": prepared.reader_input_manifest_id,
        "derived_asset_id": prepared.derived_asset_id,
        "expanded_grid_sha256": prepared.expanded_grid_sha256,
        "compact_payload_sha256": prepared.compact_payload_sha256,
        "round_trip_receipt_id": prepared.round_trip_receipt_id,
        "catalog_task_contract_hash": task["catalog_task_contract_hash"],
        "task_spec_semantic_hash": task["task_spec_semantic_hash"],
        "system_prompt_hash": task["system_prompt_hash"],
        "output_schema_hash": task["output_schema_hash"],
        "reader_request_body_sha256": sha256_bytes(
            content=prepared.request_bytes,
        ),
        "provider_request_body_sha256": sha256_bytes(
            content=provider_body,
        ),
        "provider_request_body_bytes": len(provider_body),
        "provider_output_schema_sha256": sha256_bytes(
            content=output_schema,
        ),
        "provider": policy.provider,
        "model": policy.model,
        "api": policy.api,
        "maximum_payload_bytes": policy.maximum_payload_bytes,
        "maximum_context_tokens": runtime["maximum_context_tokens"],
        "estimated_input_tokens": estimated,
        "exact_estimator_identity": {
            "estimator_id": runtime["estimator_id"],
            "estimator_version": runtime["estimator_version"],
            "estimator_method": runtime["estimator_method"],
            "context_authority_hash": runtime["context_authority_hash"],
        },
        "ordinary_qualification_max_estimated_input_tokens": d07[
            "choice"
        ]["max_estimated_input_tokens"],
        "ordinary_qualification_remains_blocked": True,
        "allowed_successful_provider_egress_count": exception[
            "allowed_successful_provider_egress_count"
        ],
        "automatic_retry_count": exception["automatic_retry_count"],
        "qualification_ordinal_credit": exception[
            "qualification_ordinal_credit"
        ],
        "qualification_evidence_eligible": exception[
            "qualification_evidence_eligible"
        ],
        "publication_eligible": exception["publication_eligible"],
        "response_reuse_for_qualification": exception[
            "response_reuse_for_qualification"
        ],
        "consumes_authorization_after_any_egress_marker": exception[
            "consumes_authorization_after_any_egress_marker"
        ],
        "execution_requires_external_exact_head_authorization": exception[
            "execution_requires_external_exact_head_authorization"
        ],
        "repository_head_binding": "REQUIRED_AT_EXTERNAL_AUTHORIZATION",
        "protected_closure": protected,
        "protected_closure_hash": protected["protected_closure_hash"],
        "forbidden_output_record_types": [
            "OBSERVATION_CANDIDATE",
            "EVIDENCE_CHECK",
            "REVIEW_UNIT",
            "VERIFIED_OBSERVATION",
            "TABLE_QUALIFICATION_EVIDENCE",
            "PUBLICATION_CANDIDATE",
        ],
    }
    plan = {**body, "measurement_plan_id": content_hash(value=body)}
    result = _PreparedMeasurement(
        plan=plan,
        live_prepared_request=live,
        provider_request_body=provider_body,
        output_schema_bytes=output_schema,
    )
    _PREPARED_CACHE[cache_key] = result
    return result


def build_table_context_measurement_plan(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Return the exact offline Stage-C measurement plan without issuing it."""
    return copy.deepcopy(_prepare_measurement(repo_root=repo_root).plan)


def write_table_context_measurement_plan(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Persist the content-addressed offline plan without provider execution."""
    plan = build_table_context_measurement_plan(repo_root=repo_root)
    digest = str(plan["measurement_plan_id"]).split(":", maxsplit=1)[1]
    path = repo_root / MEASUREMENT_PLAN_ROOT / (digest + ".json")
    if path.exists():
        if strict_json_file(path=path) != plan:
            _fail(
                code="TABLE_CONTEXT_MEASUREMENT_PLAN_COLLISION",
                message="Existing plan bytes differ",
            )
    else:
        atomic_write_json(path=path, value=plan)
    return {**plan, "measurement_plan_path": path.relative_to(repo_root).as_posix()}


def _git(*, repo_root: Path, arguments: Sequence[str]) -> str:
    """Run one sanitized read-only Git command against the exact checkout."""
    environment = sanitized_git_environment()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    completed = subprocess.run(
        ["git", *arguments],
        cwd=str(repo_root),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_REPOSITORY_INVALID",
            message="Git repository identity cannot be read",
        )
    return completed.stdout.strip()


def _repository_state(*, repo_root: Path, require_clean: bool) -> Dict[str, str]:
    """Return exact HEAD/tree only for this local checkout and clean worktree."""
    metadata_error = git_checkout_metadata_error(repo_root=repo_root)
    if metadata_error:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_REPOSITORY_INVALID",
            message=metadata_error,
        )
    top = _git(repo_root=repo_root, arguments=["rev-parse", "--show-toplevel"])
    if Path(top).resolve() != repo_root.resolve():
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_REPOSITORY_INVALID",
            message="Git toplevel differs from repository root",
        )
    head = _git(repo_root=repo_root, arguments=["rev-parse", "HEAD"])
    tree = _git(repo_root=repo_root, arguments=["rev-parse", "HEAD^{tree}"])
    if (
        _GIT_OID.fullmatch(head) is None
        or _GIT_OID.fullmatch(tree) is None
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_REPOSITORY_INVALID",
            message="Repository HEAD/tree identity is malformed",
        )
    status = _git(
        repo_root=repo_root,
        arguments=["status", "--porcelain=v1", "--untracked-files=all"],
    )
    if require_clean and status:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_REPOSITORY_NOT_CLEAN",
            message="Exact-head authorization requires a clean checkout",
        )
    return {"head": head, "tree": tree, "status": status}


def issue_table_context_measurement_authorization(
    *,
    repo_root: Path,
    external_authorization_statement: str,
    authorized_repository_head: str,
    authorized_at_utc: str,
) -> TableContextMeasurementAuthorization:
    """Issue the opaque one-shot capability only for an exact clean HEAD."""
    if external_authorization_statement != EXTERNAL_AUTHORIZATION_STATEMENT:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_EXTERNAL_AUTHORIZATION_REQUIRED",
            message="Independent exact-head authorization is absent",
        )
    try:
        parse_utc_timestamp(value=authorized_at_utc)
    except ValueError as error:
        raise TableContextMeasurementError(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_INVALID",
            message="Authorization timestamp is invalid",
        ) from error
    state = _repository_state(repo_root=repo_root, require_clean=True)
    if authorized_repository_head != state["head"]:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_HEAD_MISMATCH",
            message="External authorization does not bind current HEAD",
        )
    plan = build_table_context_measurement_plan(repo_root=repo_root)
    cycle_body = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "authorized_repository_head": state["head"],
        "authorized_repository_tree": state["tree"],
        "measurement_ordinal": MEASUREMENT_ORDINAL,
    }
    cycle_id = content_hash(value=cycle_body)
    body = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_cycle_id": cycle_id,
        "measurement_ordinal": MEASUREMENT_ORDINAL,
        "external_authorization_statement": external_authorization_statement,
        "authorized_at_utc": authorized_at_utc,
        "authorized_repository_head": state["head"],
        "authorized_repository_tree": state["tree"],
        "protected_closure_hash": plan["protected_closure_hash"],
        "requirement_closure_hash": plan["requirement_closure_hash"],
        "effective_d07_record_hash": plan["effective_d07_record_hash"],
        "family_id": plan["family_id"],
        "task_contract_id": plan["task_contract_id"],
        "source_sha256": plan["source_sha256"],
        "system_prompt_hash": plan["system_prompt_hash"],
        "output_schema_hash": plan["output_schema_hash"],
        "provider_request_body_sha256": plan[
            "provider_request_body_sha256"
        ],
        "provider": plan["provider"],
        "model": plan["model"],
        "api": plan["api"],
    }
    binding = {**body, "authorization_id": content_hash(value=body)}
    return TableContextMeasurementAuthorization(
        binding=binding, capability=_AUTHORIZATION_CAPABILITY,
    )


def _authorization_binding(
    *, authorization: object,
) -> Dict[str, object]:
    """Return exact fields only for the module-issued opaque object."""
    if (
        type(authorization) is not TableContextMeasurementAuthorization
        or authorization._capability is not _AUTHORIZATION_CAPABILITY
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_REQUIRED",
            message="Measurement executor requires an opaque authorization",
        )
    value = authorization.as_mapping()
    if set(value) != _AUTHORIZATION_FIELDS:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_INVALID",
            message="Measurement authorization fields differ",
        )
    body = {key: value[key] for key in value if key != "authorization_id"}
    if value["authorization_id"] != content_hash(value=body):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_INVALID",
            message="Measurement authorization identity differs",
        )
    return value


def _validate_authorization(
    *, repo_root: Path, authorization: object,
) -> Tuple[Dict[str, object], _PreparedMeasurement]:
    """Rebuild HEAD, closure, source, task, prompt, schema, and request bytes."""
    actual = _authorization_binding(authorization=authorization)
    state = _repository_state(repo_root=repo_root, require_clean=True)
    prepared = _prepare_measurement(repo_root=repo_root)
    plan = prepared.plan
    expected = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_ordinal": MEASUREMENT_ORDINAL,
        "external_authorization_statement": EXTERNAL_AUTHORIZATION_STATEMENT,
        "authorized_repository_head": state["head"],
        "authorized_repository_tree": state["tree"],
        "protected_closure_hash": plan["protected_closure_hash"],
        "requirement_closure_hash": plan["requirement_closure_hash"],
        "effective_d07_record_hash": plan["effective_d07_record_hash"],
        "family_id": plan["family_id"],
        "task_contract_id": plan["task_contract_id"],
        "source_sha256": plan["source_sha256"],
        "system_prompt_hash": plan["system_prompt_hash"],
        "output_schema_hash": plan["output_schema_hash"],
        "provider_request_body_sha256": plan[
            "provider_request_body_sha256"
        ],
        "provider": plan["provider"],
        "model": plan["model"],
        "api": plan["api"],
    }
    cycle_body = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "authorized_repository_head": state["head"],
        "authorized_repository_tree": state["tree"],
        "measurement_ordinal": MEASUREMENT_ORDINAL,
    }
    expected["measurement_cycle_id"] = content_hash(value=cycle_body)
    if any(actual.get(key) != expected[key] for key in expected):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_INVALID",
            message="Authorization differs from current exact plan or HEAD",
        )
    return actual, prepared


def validate_measurement_transport_authorization(
    *,
    repo_root: Path,
    authorization: object,
    provider_request_body_sha256: str,
    provider_output_schema_sha256: str,
) -> Dict[str, object]:
    """Validate the opaque object for the ai_adapter transport factory."""
    binding, prepared = _validate_authorization(
        repo_root=repo_root, authorization=authorization,
    )
    if (
        prepared.plan["provider_request_body_sha256"]
        != provider_request_body_sha256
        or prepared.plan["provider_output_schema_sha256"]
        != provider_output_schema_sha256
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_INVALID",
            message="Provider envelope or schema differs from plan",
        )
    return binding


def _execution_id(*, binding: Mapping[str, object]) -> str:
    """Derive the only execution identity for the one-shot authorization."""
    return content_hash(value={
        "authorization_id": binding["authorization_id"],
        "measurement_cycle_id": binding["measurement_cycle_id"],
        "provider_request_body_sha256": binding[
            "provider_request_body_sha256"
        ],
    })


def _cycle_directory(
    *, workspace_root: Path, binding: Mapping[str, object],
) -> Path:
    """Return one fixed content-addressed cycle directory."""
    return workspace_root / str(binding["measurement_cycle_id"]).split(
        ":", maxsplit=1,
    )[1]


def _exclusive_write_bytes(*, path: Path, content: bytes) -> None:
    """Create immutable bytes once, accepting only exact existing content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
        )
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            _fail(
                code="TABLE_CONTEXT_MEASUREMENT_STORAGE_COLLISION",
                message="Existing immutable bytes differ",
            )
        return
    try:
        offset = 0
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise OSError("immutable write stopped")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _marker_path(
    *, workspace_root: Path, binding: Mapping[str, object],
) -> Path:
    """Return the one permanent provider-egress marker path."""
    return _cycle_directory(
        workspace_root=workspace_root, binding=binding,
    ) / "provider_egress_marker.json"


def _write_egress_marker(
    *,
    workspace_root: Path,
    binding: Mapping[str, object],
    execution_id: str,
    transport_kind: str,
    started_at_utc: str,
) -> Dict[str, object]:
    """Persist authorization consumption immediately before socket/mock egress."""
    if transport_kind not in {"MOCK", "REAL_MODEL_PROVIDER"}:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_TRANSPORT_INVALID",
            message="Measurement transport kind is invalid",
        )
    parse_utc_timestamp(value=started_at_utc)
    body = {
        "schema_version": 1,
        "record_type": "TABLE_CONTEXT_MEASUREMENT_EGRESS_MARKER",
        "measurement_cycle_id": binding["measurement_cycle_id"],
        "authorization_id": binding["authorization_id"],
        "execution_id": execution_id,
        "measurement_ordinal": MEASUREMENT_ORDINAL,
        "provider_request_body_sha256": binding[
            "provider_request_body_sha256"
        ],
        "transport_kind": transport_kind,
        "egress_started_at_utc": started_at_utc,
    }
    marker = {**body, "egress_marker_id": content_hash(value=body)}
    _exclusive_write_bytes(
        path=_marker_path(workspace_root=workspace_root, binding=binding),
        content=canonical_json_bytes(value=marker),
    )
    return marker


def _existing_marker(
    *, workspace_root: Path, binding: Mapping[str, object],
) -> Optional[Dict[str, object]]:
    """Return and validate the permanent marker, if authorization was consumed."""
    path = _marker_path(workspace_root=workspace_root, binding=binding)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_STORAGE_INVALID",
            message="Measurement marker path is unsafe",
        )
    value = strict_json_loads(text=path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_STORAGE_INVALID",
            message="Measurement marker is invalid",
        )
    body = {key: value[key] for key in value if key != "egress_marker_id"}
    if (
        value.get("egress_marker_id") != content_hash(value=body)
        or value.get("authorization_id") != binding["authorization_id"]
        or value.get("measurement_cycle_id") != binding["measurement_cycle_id"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_STORAGE_INVALID",
            message="Measurement marker binding differs",
        )
    return dict(value)


def _nonnegative_usage_int(
    *, usage: Mapping[str, object], names: Sequence[str],
) -> Optional[int]:
    """Return one consistent provider-reported token field without inference."""
    values = [usage[name] for name in names if name in usage]
    if not values:
        return None
    if any(type(value) is not int or value < 0 for value in values):
        return None
    unique = {int(value) for value in values}
    return unique.pop() if len(unique) == 1 else None


def _usage_observation(*, provider_response: bytes) -> Dict[str, object]:
    """Read only raw provider usage fields; never estimate an actual count."""
    try:
        payload = strict_json_loads(text=provider_response.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        payload = None
    usage = payload.get("usage") if type(payload) is dict else None
    if type(usage) is not dict:
        return {
            "actual_prompt_tokens": None,
            "actual_completion_tokens": None,
            "actual_total_tokens": None,
            "prompt_cache_hit_tokens": None,
            "prompt_cache_miss_tokens": None,
            "usage_raw_field_hash": None,
        }
    prompt = _nonnegative_usage_int(
        usage=usage, names=("prompt_tokens", "input_tokens"),
    )
    completion = _nonnegative_usage_int(
        usage=usage, names=("completion_tokens", "output_tokens"),
    )
    total = _nonnegative_usage_int(usage=usage, names=("total_tokens",))
    cache_hit = _nonnegative_usage_int(
        usage=usage, names=("prompt_cache_hit_tokens",),
    )
    cache_miss = _nonnegative_usage_int(
        usage=usage, names=("prompt_cache_miss_tokens",),
    )
    details = usage.get("input_tokens_details")
    if type(details) is dict and "cached_tokens" in details:
        detail_hit = _nonnegative_usage_int(
            usage=details, names=("cached_tokens",),
        )
        if cache_hit is not None and detail_hit != cache_hit:
            cache_hit = None
        elif cache_hit is None:
            cache_hit = detail_hit
    return {
        "actual_prompt_tokens": prompt,
        "actual_completion_tokens": completion,
        "actual_total_tokens": total,
        "prompt_cache_hit_tokens": cache_hit,
        "prompt_cache_miss_tokens": cache_miss,
        "usage_raw_field_hash": "sha256:" + sha256_bytes(
            content=canonical_json_bytes(value=usage),
        ),
    }


def _validate_transport_result(*, value: object) -> Dict[str, object]:
    """Validate one exact terminal result returned by a mock/real wrapper."""
    if type(value) is not dict or set(value) != _TRANSPORT_RESULT_FIELDS:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_TRANSPORT_INVALID",
            message="Measurement transport result fields differ",
        )
    result = dict(value)
    if (
        type(result["http_status"]) is not int
        or result["http_status"] < 0
        or type(result["error_class"]) is not str
        or type(result["provider_request_id"]) is not str
        or type(result["provider_response_bytes"]) is not bytes
        or type(result["transport_terminal_status"]) is not str
        or not result["transport_terminal_status"]
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_TRANSPORT_INVALID",
            message="Measurement transport result is invalid",
        )
    return result


def _measurement_evidence(
    *,
    prepared: _PreparedMeasurement,
    binding: Mapping[str, object],
    execution_id: str,
    marker: Mapping[str, object],
    result: Optional[Mapping[str, object]],
    unknown: bool,
) -> Dict[str, object]:
    """Build one content-addressed terminal measurement-only evidence object."""
    response = b"" if result is None else bytes(result["provider_response_bytes"])
    usage = _usage_observation(provider_response=response)
    prompt = usage["actual_prompt_tokens"]
    http_status = 0 if result is None else int(result["http_status"])
    error_class = "UNKNOWN_REMOTE_OUTCOME" if unknown else (
        "" if result is None else str(result["error_class"])
    )
    if unknown:
        status = "UNKNOWN_REMOTE_OUTCOME"
        terminal = "UNKNOWN_REMOTE_OUTCOME"
    elif http_status != 200 or error_class:
        status = "FAILED_TRANSPORT"
        terminal = str(result["transport_terminal_status"])
    elif type(prompt) is not int or prompt <= 0:
        status = "FAILED_USAGE_UNAVAILABLE"
        terminal = str(result["transport_terminal_status"])
    else:
        status = "COMPLETED"
        terminal = str(result["transport_terminal_status"])
    ratio = None
    if type(prompt) is int and prompt > 0:
        ratio = format(
            (
                Decimal(prepared.plan["provider_request_body_bytes"])
                / Decimal(prompt)
            ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN),
            "f",
        )
    transport_kind = str(marker["transport_kind"])
    body = {
        "schema_version": 1,
        "record_type": "TABLE_CONTEXT_MEASUREMENT_EVIDENCE",
        "status": status,
        "measurement_plan_id": prepared.plan["measurement_plan_id"],
        "measurement_cycle_id": binding["measurement_cycle_id"],
        "measurement_ordinal": MEASUREMENT_ORDINAL,
        "authorization_id": binding["authorization_id"],
        "execution_id": execution_id,
        "provider_request_body_sha256": prepared.plan[
            "provider_request_body_sha256"
        ],
        "provider_request_id": (
            "" if result is None else result["provider_request_id"]
        ),
        "provider_response_sha256": (
            None if not response else "sha256:" + sha256_bytes(content=response)
        ),
        "http_status": http_status,
        "transport_terminal_status": terminal,
        **usage,
        "estimated_input_tokens": prepared.plan["estimated_input_tokens"],
        "exact_estimator_identity": prepared.plan["exact_estimator_identity"],
        "bytes_per_actual_prompt_token": ratio,
        "qualification_credit": False,
        "publication_eligible": False,
        "response_reuse_for_qualification": False,
        "retry_performed": False,
        "provider": prepared.plan["provider"],
        "model": prepared.plan["model"],
        "api": prepared.plan["api"],
        "real_model_provider_egress_count": (
            1 if transport_kind == "REAL_MODEL_PROVIDER" else 0
        ),
        "paid_model_provider_call_count": (
            1 if transport_kind == "REAL_MODEL_PROVIDER" else 0
        ),
        "real_SEC_egress_count": 0,
    }
    return {**body, "measurement_evidence_id": content_hash(value=body)}


def validate_table_context_measurement_evidence(
    *, evidence: Mapping[str, object],
) -> Dict[str, object]:
    """Validate exact measurement evidence without granting downstream credit."""
    if type(evidence) is not dict or set(evidence) != _EVIDENCE_FIELDS:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_EVIDENCE_INVALID",
            message="Measurement evidence fields differ",
        )
    value = copy.deepcopy(dict(evidence))
    body = {
        key: value[key] for key in value if key != "measurement_evidence_id"
    }
    if (
        value["record_type"] != "TABLE_CONTEXT_MEASUREMENT_EVIDENCE"
        or value["measurement_evidence_id"] != content_hash(value=body)
        or value["qualification_credit"] is not False
        or value["publication_eligible"] is not False
        or value["response_reuse_for_qualification"] is not False
        or value["retry_performed"] is not False
        or value["real_SEC_egress_count"] != 0
    ):
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_EVIDENCE_INVALID",
            message="Measurement evidence identity or non-credit status differs",
        )
    return value


def _persist_terminal(
    *,
    workspace_root: Path,
    binding: Mapping[str, object],
    evidence: Mapping[str, object],
    provider_response: bytes,
) -> Dict[str, object]:
    """Persist raw response and evidence without creating a qualification Run."""
    cycle_dir = _cycle_directory(
        workspace_root=workspace_root, binding=binding,
    )
    if provider_response:
        response_hash = sha256_bytes(content=provider_response)
        _exclusive_write_bytes(
            path=cycle_dir / "provider_responses" / (response_hash + ".bin"),
            content=provider_response,
        )
    validated = validate_table_context_measurement_evidence(evidence=evidence)
    digest = str(validated["measurement_evidence_id"]).split(":", maxsplit=1)[1]
    evidence_path = cycle_dir / "evidence" / (digest + ".json")
    if evidence_path.exists():
        if strict_json_file(path=evidence_path) != validated:
            _fail(
                code="TABLE_CONTEXT_MEASUREMENT_STORAGE_COLLISION",
                message="Existing measurement evidence bytes differ",
            )
    else:
        atomic_write_json(path=evidence_path, value=validated)
    return {
        **validated,
        "measurement_evidence_path": evidence_path.as_posix(),
    }


def _execute_with_transport(
    *,
    repo_root: Path,
    authorization: object,
    workspace_root: Path,
    transport: object,
    clock: Callable[[], str],
) -> Dict[str, object]:
    """Execute one mock/real terminal with exactly one marker and no retry."""
    initial = _authorization_binding(authorization=authorization)
    if _existing_marker(workspace_root=workspace_root, binding=initial) is not None:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
            message="The one-shot authorization already has an egress marker",
        )
    binding, prepared = _validate_authorization(
        repo_root=repo_root, authorization=authorization,
    )
    transport_kind = getattr(transport, "transport_kind", None)
    if transport_kind not in {"MOCK", "REAL_MODEL_PROVIDER"}:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_TRANSPORT_INVALID",
            message="Measurement transport is not repository-approved",
        )
    execution_id = _execution_id(binding=binding)
    marker: Optional[Dict[str, object]] = None

    def before_egress() -> None:
        nonlocal marker
        if marker is not None:
            _fail(
                code="TABLE_CONTEXT_MEASUREMENT_TRANSPORT_INVALID",
                message="Transport attempted a second egress",
            )
        marker = _write_egress_marker(
            workspace_root=workspace_root,
            binding=binding,
            execution_id=execution_id,
            transport_kind=str(transport_kind),
            started_at_utc=clock(),
        )

    result: Optional[Dict[str, object]] = None
    unknown = False
    try:
        raw_result = transport.send(
            request_body=prepared.provider_request_body,
            authorization_id=binding["authorization_id"],
            execution_id=execution_id,
            attempt_ordinal=MEASUREMENT_ORDINAL,
            before_egress=before_egress,
        )
        result = _validate_transport_result(value=raw_result)
    except UnknownRemoteOutcomeError:
        unknown = True
    except Exception as error:
        if marker is None:
            raise TableContextMeasurementError(
                code="TABLE_CONTEXT_MEASUREMENT_PRE_EGRESS_FAILED",
                message="Pre-egress validation failed; explicit rerun required",
            ) from error
        unknown = True
    if marker is None:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_PRE_EGRESS_FAILED",
            message="Transport stopped before socket marker; explicit rerun required",
        )
    evidence = _measurement_evidence(
        prepared=prepared,
        binding=binding,
        execution_id=execution_id,
        marker=marker,
        result=result,
        unknown=unknown,
    )
    response = b"" if result is None else bytes(result["provider_response_bytes"])
    return _persist_terminal(
        workspace_root=workspace_root,
        binding=binding,
        evidence=evidence,
        provider_response=response,
    )


def execute_table_context_measurement(
    *,
    repo_root: Path,
    authorization: object,
    clock: Callable[[], str],
) -> Dict[str, object]:
    """Execute the real one-shot path; Stage C-A must never call this function."""
    initial = _authorization_binding(authorization=authorization)
    if _existing_marker(
        workspace_root=repo_root / MEASUREMENT_EXECUTION_ROOT,
        binding=initial,
    ) is not None:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
            message="The one-shot authorization already has an egress marker",
        )
    binding, prepared = _validate_authorization(
        repo_root=repo_root, authorization=authorization,
    )
    from .ai_adapter import build_table_context_measurement_transport

    transport = build_table_context_measurement_transport(
        authorization=authorization,
        prepared_request=prepared.live_prepared_request,
        provider_request_body=prepared.provider_request_body,
        output_schema_bytes=prepared.output_schema_bytes,
    )
    if binding["authorization_id"] != authorization.as_mapping()[
        "authorization_id"
    ]:
        _fail(
            code="TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_INVALID",
            message="Authorization changed during transport construction",
        )
    return _execute_with_transport(
        repo_root=repo_root,
        authorization=authorization,
        workspace_root=repo_root / MEASUREMENT_EXECUTION_ROOT,
        transport=transport,
        clock=clock,
    )
