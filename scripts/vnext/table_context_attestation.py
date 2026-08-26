"""Derive and verify exact-request table context attestations offline.

The historical attestation remains immutable.  The same record type can also
attest the separately authorized sibling measurement without adding a
packet layer.  Each attestation is derived from one immutable plan, marker,
raw response, and evidence object.  The module rebuilds the provider request
from repository authority but never constructs a transport or opens a network
connection.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from .ai_adapter import approved_transport_policy, build_provider_request_body
from .canonical import atomic_write_json, content_hash, sha256_bytes
from .canonical import sha256_file, strict_json_file
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .requirements import ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY
from .requirements import ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS
from .requirements import ISSUE_15_D07_LIVE_QUALIFICATION_SCOPE
from .requirements import ISSUE_15_D07_MEASUREMENT_EXCEPTION
from .requirements import ISSUE_15_D07_REVISED_PROMPT_MEASUREMENT_POLICY
from .requirements import ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION
from .requirements import ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY
from .requirements import load_requirement_snapshot
from .sources import load_raw_blob_bytes, raw_blob_record
from .sources import source_reference_record
from .table_context_measurement import _source_binding, _usage_observation
from .table_context_measurement import build_table_context_measurement_plan
from .table_context_measurement import MEASUREMENT_EXECUTION_ROOT
from .table_context_measurement import MEASUREMENT_PLAN_ROOT
from .table_context_measurement import TableContextMeasurementError
from .table_context_measurement import validate_table_context_measurement_evidence
from .table_grid import build_table_grid
from .table_payload import TABLE_PAYLOAD_SERIALIZATION_VERSION
from .table_qualification_freeze import load_table_qualification_matrix
from .table_task_contracts import resolve_table_task_contract


STAGE_C_B_POINTER = Path(
    "artifacts/vnext/table_stage_c_evidence/current_stage_c_b_packet.json"
)
ATTESTATION_ROOT = Path(
    "artifacts/vnext/table_stage_c_evidence/"
    "context_feasibility_attestations"
)
ATTESTATION_POINTER = Path(
    "artifacts/vnext/table_stage_c_evidence/"
    "current_context_feasibility_attestation.json"
)
ATTESTATION_RECORD_TYPE = "TABLE_CONTEXT_FEASIBILITY_ATTESTATION"
ATTESTATION_POINTER_TYPE = "TABLE_CONTEXT_FEASIBILITY_ATTESTATION_POINTER"
ATTESTATION_FIELDS = {
    "actual_completion_tokens",
    "actual_prompt_tokens",
    "actual_total_tokens",
    "api",
    "attestation_id",
    "context_budget_tokens",
    "context_headroom_tokens",
    "exact_provider_request_body_bytes",
    "exact_provider_request_body_sha256",
    "family_id",
    "invalidation_policy",
    "measurement_authorization_consumed",
    "measurement_authorization_id",
    "measurement_cycle_id",
    "measurement_egress_marker_id",
    "measurement_evidence_path",
    "measurement_execution_id",
    "measurement_plan_id",
    "measurement_plan_path",
    "measurement_protected_closure_hash",
    "measurement_requirement_closure_hash",
    "model",
    "output_schema_hash",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "prompt_hash",
    "protected_closure",
    "protected_closure_hash",
    "provider",
    "provider_output_schema_sha256",
    "qualification_credit",
    "qualification_response_reuse_eligible",
    "raw_provider_response_id",
    "raw_provider_response_path",
    "record_type",
    "requirement_closure_hash",
    "schema_version",
    "serializer_hash",
    "serializer_identity",
    "serializer_version",
    "source_binding_hash",
    "source_id",
    "source_identity",
    "source_measurement_evidence_id",
    "source_repo_relative_path",
    "source_sha256",
    "source_stage_c_b_packet_id",
    "source_stage_c_b_packet_path",
    "task_contract_hash",
    "task_contract_id",
    "task_spec_semantic_hash",
    "usage_raw_field_hash",
}
POINTER_FIELDS = {
    "attestation_id",
    "attestation_path",
    "pointer_id",
    "record_type",
    "schema_version",
    "source_measurement_evidence_id",
}
EXACT_REQUEST_BINDING_FIELDS = (
    "provider_request_body_sha256",
    "family_id",
    "task_contract_id",
    "source_identity",
    "source_repo_relative_path",
    "source_sha256",
    "serializer_identity",
    "serializer_hash",
    "task_contract_hash",
    "prompt_hash",
    "output_schema_hash",
    "provider",
    "model",
    "api",
    "requirement_closure_hash",
    "protected_closure_hash",
)
OCCUPANCY_ATTESTATION_ID = (
    "sha256:dc8cb1d152cc42b5b438e4db33fe0360"
    "6766b8d7ec1b4bc11bd92273cbbd9e60"
)
OCCUPANCY_ATTESTATION_REQUIREMENT_CLOSURE_HASH = (
    "sha256:bfb1c137dea2e993b90ffc1db58f445e"
    "ec518c0b41743d54fb976e02815111f7"
)
OCCUPANCY_ATTESTATION_PROTECTED_CLOSURE_HASH = (
    "sha256:4054326dc82aa17d60cf8ff994cc8b1c"
    "5d2d17652fc132c4bd0639fe7d381686"
)
_OCCUPANCY_ADDITIVE_SUCCESSOR_PATHS = {
    "requirements/issue_15_v1/baseline_manifest.json",
    "requirements/issue_15_v1/decision_register.json",
    "scripts/vnext/requirements.py",
    "scripts/vnext/table_context_measurement.py",
}
CURRENT_TASK_ATTESTATION_ID = (
    "sha256:d3824ed29716596cbb4b997462d3974c8"
    "c36f429555dd35d84f62b8b137a9c42"
)
CURRENT_TASK_ATTESTATION_REQUIREMENT_CLOSURE_HASH = (
    "sha256:c224722f28d9c6f18b53838f3ae6cbaa"
    "1f5776420eaef31a57f0ed2f085a24f3"
)
CURRENT_TASK_ATTESTATION_PROTECTED_CLOSURE_HASH = (
    "sha256:dee2ffd0ef30f663c63159f7714e98f3a"
    "b7db075a0230e2bcfb07a3c5c200215"
)
_CURRENT_TASK_ADDITIVE_SUCCESSOR_PATHS = {
    "requirements/issue_15_v1/baseline_manifest.json",
    "requirements/issue_15_v1/decision_register.json",
    "scripts/vnext/requirements.py",
    "scripts/vnext/table_context_measurement.py",
}


class TableContextAttestationError(RuntimeError):
    """Report a malformed, stale, or non-exact context attestation."""


def _fail(message: str) -> None:
    """Raise one stable fail-closed attestation error."""
    raise TableContextAttestationError(message)


def _safe_relative(*, relative: object, label: str) -> Path:
    """Return one portable repository-relative path."""
    path = Path(str(relative))
    if path.is_absolute() or ".." in path.parts:
        _fail("{} path is unsafe".format(label))
    return path


def _read_object(*, repo_root: Path, relative: object, label: str) -> Dict[str, object]:
    """Read one strict JSON object from a safe regular file."""
    path = repo_root / _safe_relative(relative=relative, label=label)
    if path.is_symlink() or not path.is_file():
        _fail("{} is absent or unsafe".format(label))
    value = strict_json_file(path=path)
    if type(value) is not dict:
        _fail("{} root is not an object".format(label))
    return dict(value)


def _content_record(
    *, repo_root: Path, relative: object, id_field: str, label: str,
) -> Dict[str, object]:
    """Read and recompute one canonical content-addressed JSON record."""
    value = _read_object(repo_root=repo_root, relative=relative, label=label)
    identity = value.get(id_field)
    body = {key: item for key, item in value.items() if key != id_field}
    if identity != content_hash(value=body):
        _fail("{} identity differs".format(label))
    return value


def _current_protected_closure(
    *, repo_root: Path, measurement_plan: Mapping[str, object],
) -> Dict[str, object]:
    """Rebind the Stage C-B request-forming path set to current bytes."""
    protected = measurement_plan.get("protected_closure")
    files = protected.get("files") if type(protected) is dict else None
    if type(files) is not dict or not files:
        _fail("Measurement protected closure is invalid")
    measurement_body = {"files": files}
    if (
        protected.get("protected_closure_hash")
        != content_hash(value=measurement_body)
        or measurement_plan.get("protected_closure_hash")
        != protected.get("protected_closure_hash")
    ):
        _fail("Measurement protected closure identity differs")
    current = {}
    for relative_text in sorted(files):
        relative = _safe_relative(
            relative=relative_text, label="protected closure",
        )
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            _fail("Protected closure file is absent or unsafe")
        current[relative.as_posix()] = {
            "sha256": sha256_file(path=path),
            "size": path.stat().st_size,
        }
    body = {"files": current}
    return {**body, "protected_closure_hash": content_hash(value=body)}


def _stage_c_b_records(
    *, repo_root: Path,
) -> Tuple[Dict[str, object], ...]:
    """Load and cross-check the complete immutable Stage C-B record chain."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=STAGE_C_B_POINTER,
        id_field="pointer_id",
        label="Stage C-B pointer",
    )
    packet = _content_record(
        repo_root=repo_root,
        relative=pointer.get("packet_path"),
        id_field="stage_c_b_packet_id",
        label="Stage C-B packet",
    )
    if pointer.get("stage_c_b_packet_id") != packet.get("stage_c_b_packet_id"):
        _fail("Stage C-B pointer binding differs")
    terminal = packet.get("measurement_terminal")
    semantics = packet.get("measurement_semantics")
    if type(terminal) is not dict or type(semantics) is not dict:
        _fail("Stage C-B measurement records are invalid")
    plan = _content_record(
        repo_root=repo_root,
        relative=terminal.get("measurement_plan_path"),
        id_field="measurement_plan_id",
        label="Stage C-B measurement plan",
    )
    evidence = _content_record(
        repo_root=repo_root,
        relative=terminal.get("measurement_evidence_path"),
        id_field="measurement_evidence_id",
        label="Stage C-B measurement evidence",
    )
    try:
        validate_table_context_measurement_evidence(evidence=evidence)
    except TableContextMeasurementError as error:
        raise TableContextAttestationError(
            "Stage C-B measurement evidence is invalid"
        ) from error
    marker = _content_record(
        repo_root=repo_root,
        relative=terminal.get("egress_marker_path"),
        id_field="egress_marker_id",
        label="Stage C-B egress marker",
    )
    raw_relative = _safe_relative(
        relative=terminal.get("provider_response_path"),
        label="Stage C-B raw response",
    )
    raw_path = repo_root / raw_relative
    if raw_path.is_symlink() or not raw_path.is_file():
        _fail("Stage C-B raw response is absent or unsafe")
    raw = raw_path.read_bytes()
    raw_id = "sha256:" + sha256_bytes(content=raw)
    usage = _usage_observation(provider_response=raw)
    expected_evidence_id = ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY[
        "accepted_measurement_evidence_id"
    ]
    equality_checks = (
        pointer.get("stage_c_b_packet_id") == packet.get("stage_c_b_packet_id"),
        terminal.get("measurement_plan_id") == plan.get("measurement_plan_id"),
        terminal.get("measurement_evidence_id")
        == evidence.get("measurement_evidence_id"),
        terminal.get("egress_marker_id") == marker.get("egress_marker_id"),
        terminal.get("provider_response_sha256") == raw_id,
        packet.get("authority", {}).get("measurement_cycle_id")
        == evidence.get("measurement_cycle_id"),
        terminal.get("measurement_cycle_id") == evidence.get("measurement_cycle_id"),
        terminal.get("execution_id") == evidence.get("execution_id"),
        terminal.get("authorization_id") == evidence.get("authorization_id"),
        marker.get("authorization_id") == evidence.get("authorization_id"),
        marker.get("measurement_cycle_id") == evidence.get("measurement_cycle_id"),
        marker.get("execution_id") == evidence.get("execution_id"),
        marker.get("provider_request_body_sha256")
        == evidence.get("provider_request_body_sha256"),
        plan.get("provider_request_body_sha256")
        == evidence.get("provider_request_body_sha256"),
        evidence.get("measurement_evidence_id") == expected_evidence_id,
        usage.get("actual_prompt_tokens") == evidence.get("actual_prompt_tokens"),
        usage.get("actual_completion_tokens")
        == evidence.get("actual_completion_tokens"),
        usage.get("actual_total_tokens") == evidence.get("actual_total_tokens"),
        usage.get("prompt_cache_hit_tokens")
        == evidence.get("prompt_cache_hit_tokens"),
        usage.get("prompt_cache_miss_tokens")
        == evidence.get("prompt_cache_miss_tokens"),
        usage.get("usage_raw_field_hash") == evidence.get("usage_raw_field_hash"),
        semantics.get("authorization_permanently_consumed") is True,
        semantics.get("additional_measurement_egress_authorized") is False,
        semantics.get("qualification_credit") is False,
        semantics.get("qualification_evidence_eligible") is False,
        semantics.get("response_reuse_for_qualification") is False,
        evidence.get("qualification_credit") is False,
        evidence.get("response_reuse_for_qualification") is False,
        "ADDITIONAL_REAL_TOKEN_MEASUREMENT"
        in packet.get("STILL_UNAUTHORIZED", []),
        "LIVE_QUALIFICATION" in packet.get("STILL_UNAUTHORIZED", []),
    )
    if not all(equality_checks):
        _fail("Stage C-B terminal chain differs")
    return pointer, packet, plan, evidence, marker, usage


def _rebuild_exact_request(
    *, repo_root: Path, requirement: Mapping[str, object],
    measurement_plan: Mapping[str, object],
    measurement_exception: Mapping[str, object],
) -> Dict[str, object]:
    """Rebuild one attested provider request without any transport object."""
    d07 = requirement["effective_decisions"]["D-07"]
    choice = d07["choice"]
    occupancy_exception = choice.get("measurement_exception")
    revpar_exception = choice.get("revpar_measurement_exception")
    policy = choice.get("context_feasibility_policy")
    revised_policy = choice.get("revised_prompt_measurement_policy")
    schema_policy = choice.get("schema_revised_measurement_policy")
    if (
        occupancy_exception != ISSUE_15_D07_MEASUREMENT_EXCEPTION
        or revpar_exception != ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION
        or policy != ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY
        or revised_policy != ISSUE_15_D07_REVISED_PROMPT_MEASUREMENT_POLICY
        or schema_policy != ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY
        or choice.get("live_measurement_authorized") is not False
        or choice.get("live_qualification_authorized") is not False
        or choice.get("accepted_context_attestations")
        != ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS
        or choice.get("live_qualification_scope")
        != ISSUE_15_D07_LIVE_QUALIFICATION_SCOPE
        or choice.get(
            "revpar_measurement_authorization_permanently_consumed"
        ) is not True
    ):
        _fail("Effective D-07 context authority differs")
    exception = dict(measurement_exception)
    if exception not in (occupancy_exception, revpar_exception):
        _fail("Measurement exception is not authorized by effective D-07")
    family_id = str(measurement_plan["family_id"])
    task_id = str(measurement_plan["task_contract_id"])
    if (
        family_id != exception["family_id"]
        or task_id != exception["task_contract_id"]
    ):
        _fail("Measurement target differs from effective D-07")
    matrix = load_table_qualification_matrix(
        repo_root=repo_root, family_id=family_id,
    )
    entry = matrix["entries"][family_id]
    task = resolve_table_task_contract(
        repo_root=repo_root,
        task_contract_id=task_id,
        family_id=family_id,
    )
    source = _source_binding(
        repo_root=repo_root,
        matrix_entry=entry,
        exception=exception,
    )
    if source != measurement_plan.get("source_binding"):
        _fail("Current source binding differs from Stage C-B")
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
    transport_policy = approved_transport_policy(requirement=requirement)
    provider_body, output_schema = build_provider_request_body(
        policy=transport_policy,
        reader_request_bytes=prepared.request_bytes,
    )
    serializer_path = repo_root / "scripts/vnext/table_payload.py"
    protected = _current_protected_closure(
        repo_root=repo_root, measurement_plan=measurement_plan,
    )
    return {
        "exact_provider_request_body_sha256": sha256_bytes(
            content=provider_body,
        ),
        "exact_provider_request_body_bytes": len(provider_body),
        "family_id": family_id,
        "task_contract_id": task_id,
        "source_identity": copy.deepcopy(dict(declaration)),
        "source_id": source_reference["source_reference_id"],
        "source_binding_hash": source["source_binding_hash"],
        "source_repo_relative_path": source["request_repo_relative_path"],
        "source_sha256": source["request_body_sha256"],
        "serializer_identity": "table_payload_serialization_v{}".format(
            prepared.table_payload_serialization_version
        ),
        "serializer_version": prepared.table_payload_serialization_version,
        "serializer_hash": sha256_file(path=serializer_path),
        "task_contract_hash": task["catalog_task_contract_hash"],
        "task_spec_semantic_hash": task["task_spec_semantic_hash"],
        "prompt_hash": task["system_prompt_hash"],
        "output_schema_hash": task["output_schema_hash"],
        "provider_output_schema_sha256": sha256_bytes(content=output_schema),
        "provider": transport_policy.provider,
        "model": transport_policy.model,
        "api": transport_policy.api,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "protected_closure": protected,
        "protected_closure_hash": protected["protected_closure_hash"],
    }


def _pointer_occupancy_attestation(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Load the immutable historical attestation selected by its old pointer."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=ATTESTATION_POINTER,
        id_field="pointer_id",
        label="Context attestation pointer",
    )
    if set(pointer) != POINTER_FIELDS or pointer["record_type"] != (
        ATTESTATION_POINTER_TYPE
    ):
        _fail("Context attestation pointer fields differ")
    attestation = _content_record(
        repo_root=repo_root,
        relative=pointer["attestation_path"],
        id_field="attestation_id",
        label="Historical context attestation",
    )
    if (
        set(attestation) != ATTESTATION_FIELDS
        or attestation["record_type"] != ATTESTATION_RECORD_TYPE
        or pointer["attestation_id"] != attestation["attestation_id"]
        or pointer["source_measurement_evidence_id"]
        != attestation["source_measurement_evidence_id"]
    ):
        _fail("Historical attestation fields or pointer binding differ")
    return attestation


def _validate_preserved_occupancy_attestation(
    *, repo_root: Path,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Revalidate the accepted historical bytes under the additive successor.

    The new D-07 tip adds only the separately authorized sibling measurement.
    It does not rewrite the accepted attestation.  We therefore require the
    historical attestation identity, rebuild the exact historical provider
    request, and permit drift only in the four authority/executor files that
    implement this additive successor.  Every request-semantic field still
    has to match byte-for-byte.
    """
    attestation = _pointer_occupancy_attestation(repo_root=repo_root)
    if (
        attestation["attestation_id"] != OCCUPANCY_ATTESTATION_ID
        or attestation["requirement_closure_hash"]
        != OCCUPANCY_ATTESTATION_REQUIREMENT_CLOSURE_HASH
        or attestation["protected_closure_hash"]
        != OCCUPANCY_ATTESTATION_PROTECTED_CLOSURE_HASH
        or attestation["task_contract_id"]
        != ISSUE_15_D07_MEASUREMENT_EXCEPTION["task_contract_id"]
    ):
        _fail("Accepted historical attestation identity differs")
    _pointer, _packet, plan, evidence, _marker, _usage = _stage_c_b_records(
        repo_root=repo_root,
    )
    if (
        plan["measurement_plan_id"] != attestation["measurement_plan_id"]
        or evidence["measurement_evidence_id"]
        != attestation["source_measurement_evidence_id"]
    ):
        _fail("Historical measurement chain differs from attestation")
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    current = _rebuild_exact_request(
        repo_root=repo_root,
        requirement=requirement,
        measurement_plan=plan,
        measurement_exception=ISSUE_15_D07_MEASUREMENT_EXCEPTION,
    )
    exact_fields = {
        "exact_provider_request_body_sha256",
        "exact_provider_request_body_bytes",
        "family_id",
        "task_contract_id",
        "source_identity",
        "source_id",
        "source_binding_hash",
        "source_repo_relative_path",
        "source_sha256",
        "serializer_identity",
        "serializer_version",
        "serializer_hash",
        "task_contract_hash",
        "task_spec_semantic_hash",
        "prompt_hash",
        "output_schema_hash",
        "provider_output_schema_sha256",
        "provider",
        "model",
        "api",
    }
    if any(current[field] != attestation[field] for field in exact_fields):
        _fail("Current historical request differs from accepted attestation")
    previous_files = attestation["protected_closure"].get("files")
    current_files = current["protected_closure"].get("files")
    if type(previous_files) is not dict or type(current_files) is not dict:
        _fail("Historical protected closure is invalid")
    changed = {
        relative
        for relative in set(previous_files) | set(current_files)
        if previous_files.get(relative) != current_files.get(relative)
    }
    if changed != _OCCUPANCY_ADDITIVE_SUCCESSOR_PATHS:
        _fail("Additive successor changed unrelated protected files")
    return attestation, current


def _validate_preserved_current_task_attestation(
    *, repo_root: Path, task_contract_id: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Revalidate either revised proof under the additive acceptance tip."""
    accepted = next(
        (
            row for row in ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS
            if row["task_contract_id"] == task_contract_id
        ),
        None,
    )
    if accepted is None:
        _fail("Task has no accepted current context attestation")
    if task_contract_id == ISSUE_15_D07_MEASUREMENT_EXCEPTION[
        "task_contract_id"
    ]:
        attestation = _pointer_occupancy_attestation(repo_root=repo_root)
        measurement_exception = ISSUE_15_D07_MEASUREMENT_EXCEPTION
    elif task_contract_id == ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION[
        "task_contract_id"
    ]:
        digest = str(accepted["attestation_id"]).split(":", maxsplit=1)[1]
        attestation = _content_record(
            repo_root=repo_root,
            relative=ATTESTATION_ROOT / (digest + ".json"),
            id_field="attestation_id",
            label="Current-task context attestation",
        )
        measurement_exception = ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION
    else:
        _fail("Unsupported context attestation task")
    if (
        set(attestation) != ATTESTATION_FIELDS
        or attestation["attestation_id"] != accepted["attestation_id"]
        or attestation["task_contract_id"] != task_contract_id
        or attestation["source_measurement_evidence_id"]
        != accepted["measurement_evidence_id"]
        or attestation["actual_prompt_tokens"]
        != accepted["actual_prompt_tokens"]
        or attestation["context_budget_tokens"]
        != accepted["context_budget_tokens"]
        or attestation["actual_prompt_tokens"]
        > attestation["context_budget_tokens"]
    ):
        _fail("Accepted current-task attestation identity differs")
    plan = _content_record(
        repo_root=repo_root,
        relative=attestation["measurement_plan_path"],
        id_field="measurement_plan_id",
        label="Current-task measurement plan",
    )
    if (
        plan.get("task_contract_id") != task_contract_id
        or plan.get("measurement_plan_id")
        != attestation["measurement_plan_id"]
        or plan.get("revised_prompt_measurement_policy")
        != ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY
        or plan.get("requirement_closure_hash")
        != attestation["measurement_requirement_closure_hash"]
        or plan.get("protected_closure_hash")
        != attestation["measurement_protected_closure_hash"]
    ):
        _fail("Accepted current-task measurement plan differs")
    evidence = _content_record(
        repo_root=repo_root,
        relative=attestation["measurement_evidence_path"],
        id_field="measurement_evidence_id",
        label="Current-task measurement evidence",
    )
    try:
        validate_table_context_measurement_evidence(evidence=evidence)
    except TableContextMeasurementError as error:
        raise TableContextAttestationError(
            "Current-task measurement evidence is invalid"
        ) from error
    evidence_relative = _safe_relative(
        relative=attestation["measurement_evidence_path"],
        label="current-task measurement evidence",
    )
    marker_relative = (
        evidence_relative.parent.parent / "provider_egress_marker.json"
    )
    marker = _content_record(
        repo_root=repo_root,
        relative=marker_relative,
        id_field="egress_marker_id",
        label="Current-task egress marker",
    )
    raw_relative = _safe_relative(
        relative=attestation["raw_provider_response_path"],
        label="current-task raw response",
    )
    raw_path = repo_root / raw_relative
    if raw_path.is_symlink() or not raw_path.is_file():
        _fail("Current-task raw response is absent or unsafe")
    raw = raw_path.read_bytes()
    usage = _usage_observation(provider_response=raw)
    if (
        plan["measurement_plan_id"] != attestation["measurement_plan_id"]
        or evidence["measurement_evidence_id"]
        != attestation["source_measurement_evidence_id"]
        or marker["egress_marker_id"]
        != attestation["measurement_egress_marker_id"]
        or evidence["measurement_cycle_id"]
        != attestation["measurement_cycle_id"]
        or evidence["authorization_id"]
        != attestation["measurement_authorization_id"]
        or evidence["execution_id"]
        != attestation["measurement_execution_id"]
        or "sha256:" + sha256_bytes(content=raw)
        != attestation["raw_provider_response_id"]
        or usage["actual_prompt_tokens"] != attestation["actual_prompt_tokens"]
        or usage["usage_raw_field_hash"] != attestation["usage_raw_field_hash"]
    ):
        _fail("Current-task measurement chain differs from attestation")
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    current = _rebuild_exact_request(
        repo_root=repo_root,
        requirement=requirement,
        measurement_plan=plan,
        measurement_exception=measurement_exception,
    )
    exact_fields = {
        "exact_provider_request_body_sha256",
        "exact_provider_request_body_bytes",
        "family_id",
        "task_contract_id",
        "source_identity",
        "source_id",
        "source_binding_hash",
        "source_repo_relative_path",
        "source_sha256",
        "serializer_identity",
        "serializer_version",
        "serializer_hash",
        "task_contract_hash",
        "task_spec_semantic_hash",
        "prompt_hash",
        "output_schema_hash",
        "provider_output_schema_sha256",
        "provider",
        "model",
        "api",
    }
    if any(current[field] != attestation[field] for field in exact_fields):
        _fail("Current request differs from accepted current-task attestation")
    previous_files = attestation["protected_closure"].get("files")
    current_files = current["protected_closure"].get("files")
    if type(previous_files) is not dict or type(current_files) is not dict:
        _fail("Current-task protected closure is invalid")
    changed = {
        relative
        for relative in set(previous_files) | set(current_files)
        if previous_files.get(relative) != current_files.get(relative)
    }
    if changed != _CURRENT_TASK_ADDITIVE_SUCCESSOR_PATHS:
        _fail("Qualification successor changed unrelated protected files")
    return attestation, current


def _revpar_terminal_records(
    *, repo_root: Path, task_contract_id: str = "lodging_revpar_table_v2",
) -> Tuple[
    Dict[str, object], Dict[str, object], Dict[str, object], bytes, str, str, str,
]:
    """Discover the unique current plan/marker/evidence/raw terminal."""
    if task_contract_id not in ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY[
        "task_contract_ids"
    ]:
        _fail("Unsupported revised-prompt context attestation task")
    measurement_exception = (
        ISSUE_15_D07_MEASUREMENT_EXCEPTION
        if task_contract_id
        == ISSUE_15_D07_MEASUREMENT_EXCEPTION["task_contract_id"]
        else ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION
    )
    plan = build_table_context_measurement_plan(
        repo_root=repo_root, task_contract_id=task_contract_id,
    )
    digest = str(plan["measurement_plan_id"]).split(":", maxsplit=1)[1]
    plan_relative = MEASUREMENT_PLAN_ROOT / (digest + ".json")
    persisted_plan = _content_record(
        repo_root=repo_root,
        relative=plan_relative,
        id_field="measurement_plan_id",
        label="Current measurement plan",
    )
    if persisted_plan != plan:
        _fail("Persisted measurement plan differs from current plan")
    matches = []
    execution_root = repo_root / MEASUREMENT_EXECUTION_ROOT
    if execution_root.is_dir() and not execution_root.is_symlink():
        for evidence_path in sorted(execution_root.glob("*/evidence/*.json")):
            if evidence_path.is_symlink() or not evidence_path.is_file():
                _fail("Measurement evidence namespace contains an unsafe entry")
            value = strict_json_file(path=evidence_path)
            if type(value) is dict and value.get("measurement_plan_id") == (
                plan["measurement_plan_id"]
            ):
                matches.append((evidence_path, dict(value)))
    if len(matches) != 1:
        _fail("Exactly one current measurement terminal is required")
    evidence_path, evidence = matches[0]
    try:
        validate_table_context_measurement_evidence(evidence=evidence)
    except TableContextMeasurementError as error:
        raise TableContextAttestationError(
            "Current measurement evidence is invalid"
        ) from error
    cycle_dir = evidence_path.parent.parent
    marker_path = cycle_dir / "provider_egress_marker.json"
    marker_relative = marker_path.relative_to(repo_root).as_posix()
    marker = _content_record(
        repo_root=repo_root,
        relative=marker_relative,
        id_field="egress_marker_id",
        label="Current egress marker",
    )
    response_id = evidence.get("provider_response_sha256")
    if not isinstance(response_id, str) or not response_id.startswith("sha256:"):
        _fail("Current raw provider response identity is absent")
    response_relative = (
        cycle_dir.relative_to(repo_root)
        / "provider_responses"
        / (response_id.split(":", maxsplit=1)[1] + ".bin")
    )
    response_path = repo_root / response_relative
    if response_path.is_symlink() or not response_path.is_file():
        _fail("Current raw provider response is absent or unsafe")
    raw = response_path.read_bytes()
    usage = _usage_observation(provider_response=raw)
    equalities = (
        evidence.get("schema_version") == 2,
        evidence.get("status") == "COMPLETED",
        evidence.get("task_contract_id")
        == measurement_exception["task_contract_id"],
        evidence.get("family_id")
        == measurement_exception["family_id"],
        evidence.get("measurement_cycle_id")
        == marker.get("measurement_cycle_id"),
        evidence.get("authorization_id") == marker.get("authorization_id"),
        evidence.get("execution_id") == marker.get("execution_id"),
        evidence.get("measurement_plan_id") == marker.get("measurement_plan_id"),
        evidence.get("provider_request_body_sha256")
        == marker.get("provider_request_body_sha256"),
        evidence.get("authorized_repository_head")
        == marker.get("authorized_repository_head"),
        evidence.get("authorized_repository_tree")
        == marker.get("authorized_repository_tree"),
        evidence.get("external_review_comment_url")
        == marker.get("external_review_comment_url"),
        evidence.get("provider_response_sha256")
        == "sha256:" + sha256_bytes(content=raw),
        usage.get("actual_prompt_tokens") == evidence.get("actual_prompt_tokens"),
        usage.get("actual_completion_tokens")
        == evidence.get("actual_completion_tokens"),
        usage.get("actual_total_tokens") == evidence.get("actual_total_tokens"),
        usage.get("usage_raw_field_hash") == evidence.get("usage_raw_field_hash"),
    )
    if not all(equalities):
        _fail("Current plan, marker, raw response, and evidence differ")
    return (
        plan,
        evidence,
        marker,
        raw,
        plan_relative.as_posix(),
        evidence_path.relative_to(repo_root).as_posix(),
        response_relative.as_posix(),
    )


def build_table_context_feasibility_attestation(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Return the immutable historical attestation after exact revalidation."""
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    if requirement["effective_decisions"]["D-07"]["choice"].get(
        "revpar_measurement_exception"
    ) == ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION:
        attestation, _current = _validate_preserved_occupancy_attestation(
            repo_root=repo_root,
        )
        return copy.deepcopy(attestation)
    _pointer, packet, plan, evidence, marker, usage = _stage_c_b_records(
        repo_root=repo_root,
    )
    current = _rebuild_exact_request(
        repo_root=repo_root,
        requirement=requirement,
        measurement_plan=plan,
        measurement_exception=ISSUE_15_D07_MEASUREMENT_EXCEPTION,
    )
    plan_equalities = {
        "exact_provider_request_body_sha256": "provider_request_body_sha256",
        "exact_provider_request_body_bytes": "provider_request_body_bytes",
        "family_id": "family_id",
        "task_contract_id": "task_contract_id",
        "source_sha256": "source_sha256",
        "serializer_version": "table_payload_serialization_version",
        "task_contract_hash": "catalog_task_contract_hash",
        "task_spec_semantic_hash": "task_spec_semantic_hash",
        "prompt_hash": "system_prompt_hash",
        "output_schema_hash": "output_schema_hash",
        "provider_output_schema_sha256": "provider_output_schema_sha256",
        "provider": "provider",
        "model": "model",
        "api": "api",
    }
    if any(
        current[current_field] != plan[plan_field]
        for current_field, plan_field in plan_equalities.items()
    ):
        _fail("Current exact request differs from Stage C-B request")
    policy = ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY
    actual_prompt_tokens = evidence["actual_prompt_tokens"]
    context_budget = policy["context_budget_tokens"]
    if (
        actual_prompt_tokens != policy["accepted_actual_prompt_tokens"]
        or actual_prompt_tokens > context_budget
        or context_budget - actual_prompt_tokens
        != policy["context_headroom_tokens"]
    ):
        _fail("Accepted Stage C-B usage differs from D-07")
    packet_path = str(
        _read_object(
            repo_root=repo_root,
            relative=STAGE_C_B_POINTER,
            label="Stage C-B pointer",
        )["packet_path"]
    )
    terminal = packet["measurement_terminal"]
    body = {
        "schema_version": 1,
        "record_type": ATTESTATION_RECORD_TYPE,
        "source_measurement_evidence_id": evidence["measurement_evidence_id"],
        "measurement_evidence_path": terminal["measurement_evidence_path"],
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_plan_path": terminal["measurement_plan_path"],
        "measurement_cycle_id": evidence["measurement_cycle_id"],
        "measurement_execution_id": evidence["execution_id"],
        "measurement_egress_marker_id": marker["egress_marker_id"],
        "measurement_authorization_id": evidence["authorization_id"],
        "raw_provider_response_id": terminal["provider_response_sha256"],
        "raw_provider_response_path": terminal["provider_response_path"],
        "source_stage_c_b_packet_id": packet["stage_c_b_packet_id"],
        "source_stage_c_b_packet_path": packet_path,
        "measurement_requirement_closure_hash": plan[
            "requirement_closure_hash"
        ],
        "measurement_protected_closure_hash": plan[
            "protected_closure_hash"
        ],
        **current,
        "actual_prompt_tokens": actual_prompt_tokens,
        "actual_completion_tokens": evidence["actual_completion_tokens"],
        "actual_total_tokens": evidence["actual_total_tokens"],
        "prompt_cache_hit_tokens": evidence["prompt_cache_hit_tokens"],
        "prompt_cache_miss_tokens": evidence["prompt_cache_miss_tokens"],
        "usage_raw_field_hash": usage["usage_raw_field_hash"],
        "context_budget_tokens": context_budget,
        "context_headroom_tokens": context_budget - actual_prompt_tokens,
        "qualification_credit": False,
        "qualification_response_reuse_eligible": False,
        "measurement_authorization_consumed": True,
        "invalidation_policy": {
            "validation_phase": "BEFORE_PROVIDER_EGRESS",
            "required_exact_binding_fields": list(EXACT_REQUEST_BINDING_FIELDS),
            "any_required_binding_drift": "INVALIDATE_ATTESTATION",
            "approximate_or_family_equivalence": "FORBIDDEN",
            "attestation_scope": "ONE_EXACT_TASK_REQUEST",
            "attestation_semantics": "CONTEXT_FEASIBILITY_ONLY",
            "measurement_response_qualification_reuse": "FORBIDDEN",
            "qualification_execution_requires_separate_authorization": True,
        },
    }
    return {**body, "attestation_id": content_hash(value=body)}


def build_revpar_context_feasibility_attestation(
    *, repo_root: Path,
    task_contract_id: str = "lodging_revpar_table_v2",
) -> Dict[str, object]:
    """Derive one revised-prompt attestation from its unique terminal."""
    (
        plan,
        evidence,
        marker,
        raw,
        plan_path,
        evidence_path,
        raw_path,
    ) = _revpar_terminal_records(
        repo_root=repo_root, task_contract_id=task_contract_id,
    )
    actual_prompt_tokens = evidence["actual_prompt_tokens"]
    context_budget = ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY[
        "context_budget_tokens"
    ]
    if type(actual_prompt_tokens) is not int:
        _fail(
            "OWNER_DECISION_REQUIRED: current task provider usage is absent"
        )
    if actual_prompt_tokens > context_budget:
        _fail(
            "OWNER_DECISION_REQUIRED: current actual prompt tokens exceed 200000"
        )
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    exception = (
        ISSUE_15_D07_MEASUREMENT_EXCEPTION
        if task_contract_id
        == ISSUE_15_D07_MEASUREMENT_EXCEPTION["task_contract_id"]
        else ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION
    )
    if task_contract_id not in ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY[
        "task_contract_ids"
    ]:
        _fail("Unsupported revised-prompt context attestation task")
    current = _rebuild_exact_request(
        repo_root=repo_root,
        requirement=requirement,
        measurement_plan=plan,
        measurement_exception=exception,
    )
    plan_equalities = {
        "exact_provider_request_body_sha256": "provider_request_body_sha256",
        "exact_provider_request_body_bytes": "provider_request_body_bytes",
        "family_id": "family_id",
        "task_contract_id": "task_contract_id",
        "source_sha256": "source_sha256",
        "serializer_version": "table_payload_serialization_version",
        "task_contract_hash": "catalog_task_contract_hash",
        "task_spec_semantic_hash": "task_spec_semantic_hash",
        "prompt_hash": "system_prompt_hash",
        "output_schema_hash": "output_schema_hash",
        "provider_output_schema_sha256": "provider_output_schema_sha256",
        "provider": "provider",
        "model": "model",
        "api": "api",
        "requirement_closure_hash": "requirement_closure_hash",
        "protected_closure_hash": "protected_closure_hash",
    }
    if any(
        current[current_field] != plan[plan_field]
        for current_field, plan_field in plan_equalities.items()
    ):
        _fail("Current request differs from measured exact plan")
    usage = _usage_observation(provider_response=raw)
    body = {
        "schema_version": 1,
        "record_type": ATTESTATION_RECORD_TYPE,
        "source_measurement_evidence_id": evidence["measurement_evidence_id"],
        "measurement_evidence_path": evidence_path,
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_plan_path": plan_path,
        "measurement_cycle_id": evidence["measurement_cycle_id"],
        "measurement_execution_id": evidence["execution_id"],
        "measurement_egress_marker_id": marker["egress_marker_id"],
        "measurement_authorization_id": evidence["authorization_id"],
        "raw_provider_response_id": evidence["provider_response_sha256"],
        "raw_provider_response_path": raw_path,
        "source_stage_c_b_packet_id": None,
        "source_stage_c_b_packet_path": None,
        "measurement_requirement_closure_hash": plan[
            "requirement_closure_hash"
        ],
        "measurement_protected_closure_hash": plan[
            "protected_closure_hash"
        ],
        **current,
        "actual_prompt_tokens": actual_prompt_tokens,
        "actual_completion_tokens": evidence["actual_completion_tokens"],
        "actual_total_tokens": evidence["actual_total_tokens"],
        "prompt_cache_hit_tokens": evidence["prompt_cache_hit_tokens"],
        "prompt_cache_miss_tokens": evidence["prompt_cache_miss_tokens"],
        "usage_raw_field_hash": usage["usage_raw_field_hash"],
        "context_budget_tokens": context_budget,
        "context_headroom_tokens": context_budget - actual_prompt_tokens,
        "qualification_credit": False,
        "qualification_response_reuse_eligible": False,
        "measurement_authorization_consumed": True,
        "invalidation_policy": {
            "validation_phase": "BEFORE_PROVIDER_EGRESS",
            "required_exact_binding_fields": list(EXACT_REQUEST_BINDING_FIELDS),
            "any_required_binding_drift": "INVALIDATE_ATTESTATION",
            "approximate_or_family_equivalence": "FORBIDDEN",
            "attestation_scope": "ONE_EXACT_TASK_REQUEST",
            "attestation_semantics": "CONTEXT_FEASIBILITY_ONLY",
            "measurement_response_qualification_reuse": "FORBIDDEN",
            "qualification_execution_requires_separate_authorization": True,
        },
    }
    return {**body, "attestation_id": content_hash(value=body)}


def write_table_context_feasibility_attestation(
    *, repo_root: Path,
    task_contract_id: str = "lodging_occupancy_table_v2",
) -> Dict[str, object]:
    """Persist one immutable attestation without adding a packet layer."""
    if task_contract_id not in (
        ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY[
            "task_contract_ids"
        ]
    ):
        _fail("Unsupported context attestation task")
    attestation = build_revpar_context_feasibility_attestation(
        repo_root=repo_root,
        task_contract_id=task_contract_id,
    )
    digest = str(attestation["attestation_id"]).split(":", maxsplit=1)[1]
    relative = ATTESTATION_ROOT / (digest + ".json")
    path = repo_root / relative
    if path.exists():
        if strict_json_file(path=path) != attestation:
            _fail("Context attestation content-address collision")
    else:
        atomic_write_json(path=path, value=attestation)
    if task_contract_id == "lodging_occupancy_table_v2":
        pointer_body = {
            "schema_version": 1,
            "record_type": ATTESTATION_POINTER_TYPE,
            "attestation_id": attestation["attestation_id"],
            "attestation_path": relative.as_posix(),
            "source_measurement_evidence_id": attestation[
                "source_measurement_evidence_id"
            ],
        }
        pointer = {
            **pointer_body, "pointer_id": content_hash(value=pointer_body),
        }
        atomic_write_json(path=repo_root / ATTESTATION_POINTER, value=pointer)
        pointer_id = pointer["pointer_id"]
    else:
        pointer_id = None
    return {
        "attestation_id": attestation["attestation_id"],
        "attestation_path": relative.as_posix(),
        "pointer_id": pointer_id,
        "source_measurement_evidence_id": attestation[
            "source_measurement_evidence_id"
        ],
        "actual_prompt_tokens": attestation["actual_prompt_tokens"],
        "context_budget_tokens": attestation["context_budget_tokens"],
        "qualification_credit": attestation["qualification_credit"],
        "qualification_response_reuse_eligible": attestation[
            "qualification_response_reuse_eligible"
        ],
    }


def validate_table_context_feasibility_attestation(
    *, repo_root: Path,
    task_contract_id: str = "lodging_occupancy_table_v2",
) -> Dict[str, object]:
    """Rebuild and byte-validate one exact-request attestation."""
    if task_contract_id not in (
        "lodging_occupancy_table_v2",
        "lodging_revpar_table_v2",
    ):
        _fail("Unsupported context attestation task")
    attestation, _current = _validate_preserved_current_task_attestation(
        repo_root=repo_root, task_contract_id=task_contract_id,
    )
    return copy.deepcopy(attestation)


def exact_request_binding(
    *, attestation: Mapping[str, object],
) -> Dict[str, object]:
    """Project the fields that must all equal one future provider request."""
    if set(attestation) != ATTESTATION_FIELDS:
        _fail("Context attestation fields differ")
    return {
        field: copy.deepcopy(
            attestation[
                "exact_provider_request_body_sha256"
                if field == "provider_request_body_sha256" else field
            ]
        )
        for field in EXACT_REQUEST_BINDING_FIELDS
    }


def current_exact_request_binding(
    *, repo_root: Path, task_contract_id: str,
) -> Dict[str, object]:
    """Project the current exact request bound to one accepted attestation."""
    if task_contract_id not in (
        "lodging_occupancy_table_v2",
        "lodging_revpar_table_v2",
    ):
        _fail("Unsupported context request task")
    _attestation, current = _validate_preserved_current_task_attestation(
        repo_root=repo_root, task_contract_id=task_contract_id,
    )
    return {
        field: copy.deepcopy(
            current[
                "exact_provider_request_body_sha256"
                if field == "provider_request_body_sha256"
                else field
            ]
        )
        for field in EXACT_REQUEST_BINDING_FIELDS
    }


def evaluate_context_feasibility(
    *, repo_root: Path, estimated_input_tokens: int,
    max_estimated_input_tokens: int,
    request_binding: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    """Apply D-07's estimated bound or exact-attestation alternative.

    The alternative compares every field, including the complete provider
    request digest and current Requirement/protected closures.  It never uses
    byte similarity, a family/source match, or a historical bytes/token ratio.
    """
    if (
        type(estimated_input_tokens) is not int
        or estimated_input_tokens < 0
        or type(max_estimated_input_tokens) is not int
        or max_estimated_input_tokens < 1
    ):
        _fail("Context feasibility inputs are invalid")
    policy = ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY
    if max_estimated_input_tokens != policy["context_budget_tokens"]:
        _fail("Context feasibility budget differs from D-07")
    if estimated_input_tokens <= max_estimated_input_tokens:
        return {
            "status": "PASSED",
            "evidence_basis": "ESTIMATED_BOUND",
            "attestation_id": None,
            "attested_actual_prompt_tokens": None,
            "context_budget_tokens": max_estimated_input_tokens,
            "exact_binding_match": False,
            "drift_fields": [],
            "blocking_reason_code": None,
        }
    if type(request_binding) is not dict or set(request_binding) != set(
        EXACT_REQUEST_BINDING_FIELDS
    ):
        return {
            "status": "BLOCKED",
            "evidence_basis": None,
            "attestation_id": None,
            "attested_actual_prompt_tokens": None,
            "context_budget_tokens": max_estimated_input_tokens,
            "exact_binding_match": False,
            "drift_fields": list(EXACT_REQUEST_BINDING_FIELDS),
            "blocking_reason_code": "EXACT_CONTEXT_ATTESTATION_REQUIRED",
        }
    task_contract_id = request_binding["task_contract_id"]
    try:
        if task_contract_id in (
            "lodging_occupancy_table_v2",
            "lodging_revpar_table_v2",
        ):
            attestation, current = _validate_preserved_current_task_attestation(
                repo_root=repo_root, task_contract_id=task_contract_id,
            )
            expected = {
                field: copy.deepcopy(
                    current[
                        "exact_provider_request_body_sha256"
                        if field == "provider_request_body_sha256"
                        else field
                    ]
                )
                for field in EXACT_REQUEST_BINDING_FIELDS
            }
        else:
            attestation = validate_table_context_feasibility_attestation(
                repo_root=repo_root,
            )
            expected = exact_request_binding(attestation=attestation)
    except TableContextAttestationError:
        return {
            "status": "BLOCKED",
            "evidence_basis": None,
            "attestation_id": None,
            "attested_actual_prompt_tokens": None,
            "context_budget_tokens": max_estimated_input_tokens,
            "exact_binding_match": False,
            "drift_fields": list(EXACT_REQUEST_BINDING_FIELDS),
            "blocking_reason_code": (
                "EXACT_CONTEXT_ATTESTATION_REQUIRED"
                if task_contract_id == "lodging_revpar_table_v2"
                else "EXACT_CONTEXT_ATTESTATION_INVALID"
            ),
        }
    drift_fields = [
        field
        for field in EXACT_REQUEST_BINDING_FIELDS
        if request_binding[field] != expected[field]
    ]
    actual = attestation["actual_prompt_tokens"]
    if drift_fields or type(actual) is not int or actual > (
        max_estimated_input_tokens
    ):
        return {
            "status": "BLOCKED",
            "evidence_basis": None,
            "attestation_id": attestation["attestation_id"],
            "attested_actual_prompt_tokens": actual,
            "context_budget_tokens": max_estimated_input_tokens,
            "exact_binding_match": False,
            "drift_fields": drift_fields,
            "blocking_reason_code": (
                "EXACT_CONTEXT_BINDING_MISMATCH"
                if drift_fields
                else "ATTESTED_PROVIDER_CONTEXT_LIMIT"
            ),
        }
    return {
        "status": "PASSED",
        "evidence_basis": "PROVIDER_REPORTED_EXACT_BINDING",
        "attestation_id": attestation["attestation_id"],
        "attested_actual_prompt_tokens": actual,
        "context_budget_tokens": max_estimated_input_tokens,
        "exact_binding_match": True,
        "drift_fields": [],
        "blocking_reason_code": None,
    }
