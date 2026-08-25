"""Build the post-attestation Stage-C answer-first packet offline."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, Mapping

from .canonical import atomic_write_json, content_hash, strict_json_file
from .requirements import load_requirement_snapshot
from .stage_a_snapshot import validate_stage_a_snapshot
from .table_context_attestation import (
    validate_table_context_feasibility_attestation,
)
from .table_context_comparison import (
    validate_sibling_request_context_analysis,
)
from .table_qualification_freeze import (
    validate_table_qualification_freeze,
)


PACKET_ROOT = Path(
    "artifacts/vnext/table_stage_c_evidence/context_attestation_packets"
)
PACKET_POINTER = Path(
    "artifacts/vnext/table_stage_c_evidence/"
    "current_context_attestation_packet.json"
)
FREEZE_POINTER = Path("config/table_qualification_freeze.json")
STAGE_A_ROOT = Path(
    "artifacts/vnext/table_qualification_freeze/stage_a_validation"
)
OWNER_POINTER = Path(
    "artifacts/vnext/table_qualification_freeze/"
    "current_owner_decision_packet.json"
)
STAGE_C_B_POINTER = Path(
    "artifacts/vnext/table_stage_c_evidence/current_stage_c_b_packet.json"
)
PACKET_RECORD_TYPE = "ISSUE_15_STAGE_C_CONTEXT_ATTESTATION_PACKET"
PACKET_POINTER_TYPE = "ISSUE_15_STAGE_C_CONTEXT_ATTESTATION_PACKET_POINTER"


class StageCContextPacketError(RuntimeError):
    """Report incomplete or contradictory Stage-C context evidence."""


def _fail(message: str) -> None:
    """Raise one fail-closed packet error."""
    raise StageCContextPacketError(message)


def _read_object(*, repo_root: Path, relative: Path, label: str) -> Dict[str, object]:
    """Read one repository-relative strict JSON object."""
    if relative.is_absolute() or ".." in relative.parts:
        _fail("{} path is unsafe".format(label))
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        _fail("{} is absent or unsafe".format(label))
    value = strict_json_file(path=path)
    if type(value) is not dict:
        _fail("{} root is invalid".format(label))
    return dict(value)


def _content_record(
    *, repo_root: Path, relative: Path, id_field: str, label: str,
) -> Dict[str, object]:
    """Read and recompute one content-addressed object."""
    value = _read_object(repo_root=repo_root, relative=relative, label=label)
    body = {key: item for key, item in value.items() if key != id_field}
    if value.get(id_field) != content_hash(value=body):
        _fail("{} identity differs".format(label))
    return value


def _pointer_target(
    *, repo_root: Path, pointer_path: Path, pointer_id_field: str,
    target_path_field: str, target_id_field: str, label: str,
) -> tuple[Dict[str, object], Dict[str, object]]:
    """Load a pointer and its exact content-addressed target."""
    pointer = _read_object(
        repo_root=repo_root, relative=pointer_path, label=label + " pointer",
    )
    if pointer_id_field in pointer:
        body = {
            key: item for key, item in pointer.items()
            if key != pointer_id_field
        }
        if pointer[pointer_id_field] != content_hash(value=body):
            _fail("{} pointer identity differs".format(label))
    relative = Path(str(pointer.get(target_path_field, "")))
    target = _content_record(
        repo_root=repo_root,
        relative=relative,
        id_field=target_id_field,
        label=label,
    )
    if pointer.get(target_id_field) != target.get(target_id_field):
        _fail("{} pointer binding differs".format(label))
    return pointer, target


def _task_row(
    *, readiness: Mapping[str, object], task_contract_id: str,
) -> Dict[str, object]:
    """Return the unique task/request readiness row for one catalog task."""
    rows = [
        value for value in readiness.values()
        if type(value) is dict
        and value.get("task_contract_id") == task_contract_id
    ]
    if len(rows) != 1:
        _fail("Task/request readiness identity is ambiguous")
    return dict(rows[0])


def build_stage_c_context_attestation_packet(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Assemble current context feasibility without executing qualification."""
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    d07 = requirement["effective_decisions"]["D-07"]
    attestation = validate_table_context_feasibility_attestation(
        repo_root=repo_root,
    )
    sibling_analysis = validate_sibling_request_context_analysis(
        repo_root=repo_root,
    )
    freeze_status = validate_table_qualification_freeze(repo_root=repo_root)
    freeze_pointer = _read_object(
        repo_root=repo_root,
        relative=FREEZE_POINTER,
        label="table qualification freeze pointer",
    )
    freeze = _content_record(
        repo_root=repo_root,
        relative=Path(str(freeze_pointer["receipt_path"])),
        id_field="table_qualification_freeze_receipt_id",
        label="table qualification freeze receipt",
    )
    if (
        freeze["table_qualification_freeze_receipt_id"]
        != freeze_status["receipt_id"]
        or freeze["readiness_by_family"]
        != freeze_status["readiness_by_family"]
        or freeze["readiness_by_task_request"]
        != freeze_status["readiness_by_task_request"]
    ):
        _fail("Current freeze status differs from receipt")
    stage_a_status = validate_stage_a_snapshot(repo_root=repo_root)
    stage_a = _content_record(
        repo_root=repo_root,
        relative=(
            STAGE_A_ROOT
            / (
                freeze_status["receipt_id"].split(":", maxsplit=1)[1]
                + ".json"
            )
        ),
        id_field="stage_a_snapshot_id",
        label="Stage-A snapshot",
    )
    if stage_a["stage_a_snapshot_id"] != stage_a_status[
        "stage_a_snapshot_id"
    ]:
        _fail("Stage-A snapshot status differs")
    _owner_pointer, owner = _pointer_target(
        repo_root=repo_root,
        pointer_path=OWNER_POINTER,
        pointer_id_field="pointer_id",
        target_path_field="packet_path",
        target_id_field="owner_decision_packet_id",
        label="owner decision packet",
    )
    _stage_c_b_pointer, stage_c_b = _pointer_target(
        repo_root=repo_root,
        pointer_path=STAGE_C_B_POINTER,
        pointer_id_field="pointer_id",
        target_path_field="packet_path",
        target_id_field="stage_c_b_packet_id",
        label="Stage C-B packet",
    )
    attested_task_id = str(attestation["task_contract_id"])
    sibling_task_id = str(
        sibling_analysis["authority"]["sibling_task_contract_id"]
    )
    task_readiness = freeze["readiness_by_task_request"]
    attested_request = _task_row(
        readiness=task_readiness,
        task_contract_id=attested_task_id,
    )
    sibling_request = _task_row(
        readiness=task_readiness,
        task_contract_id=sibling_task_id,
    )
    family = freeze["readiness_by_family"]["lodging_kpi_table"]
    financial = freeze["readiness_by_family"]["financial_statement"]
    sibling_status_key = next(
        key for key in sibling_analysis if key.endswith("_CONTEXT_STATUS")
    )
    sibling_status = sibling_analysis[sibling_status_key]
    d07_choice = d07["choice"]
    historical_semantics = stage_c_b["measurement_semantics"]
    historical_counts = stage_c_b["measurement_terminal"]["egress_counts"]
    root_hashes = freeze["identity"]["root_hashes"]
    if (
        attested_request["context_gate"]["status"] != "PASSED"
        or attested_request["context_gate"]["evidence_basis"]
        != "PROVIDER_REPORTED_EXACT_BINDING"
        or attested_request["provider_request_body_sha256"]
        != attestation["exact_provider_request_body_sha256"]
        or attested_request["context_gate"]["attestation_id"]
        != attestation["attestation_id"]
        or sibling_request["context_gate"]["status"] != "BLOCKED"
        or sibling_request["live_ready"] is not False
        or sibling_status != "EXACT_CONTEXT_EVIDENCE_REQUIRED"
        or family["live_ready"] is not False
        or len(family["required_task_request_ids"]) != 2
        or len(family["ready_task_request_ids"]) != 1
        or freeze["live_ready_family_ids"] != []
        or financial["blocking_reason_codes"]
        != ["EXPANDED_GRID_RESOURCE_LIMIT"]
        or historical_semantics["authorization_permanently_consumed"]
        is not True
        or historical_semantics["qualification_credit"] is not False
        or historical_semantics["response_reuse_for_qualification"]
        is not False
        or d07_choice["live_qualification_authorized"] is not False
        or d07_choice["live_measurement_authorized"] is not False
        or attestation["actual_prompt_tokens"] > 200000
        or owner["current_readiness"]["readiness_by_task_request"]
        != task_readiness
        or stage_a["root_state"]["root_hashes"] != root_hashes
        or stage_c_b["active_root_state"]["root_hashes"] != root_hashes
    ):
        _fail("Stage-C context packet facts do not close")
    provider_state = freeze["provider_state"]
    current_counts = {
        "real_model_provider_egress_count": provider_state[
            "qualification_cycle_real_model_egress_count"
        ],
        "paid_model_provider_call_count": provider_state[
            "qualification_cycle_paid_model_call_count"
        ],
        "real_SEC_egress_count": provider_state[
            "qualification_cycle_sec_egress_count"
        ],
    }
    if set(current_counts.values()) != {0}:
        _fail("Current attestation cycle is not zero-egress")
    context_status = {
        "attested_request": {
            "task_contract_id": attested_task_id,
            "task_request_id": attested_request["task_request_id"],
            "provider_request_body_sha256": attestation[
                "exact_provider_request_body_sha256"
            ],
            "estimated_input_tokens": attested_request["context_gate"][
                "estimated_input_tokens"
            ],
            "actual_prompt_tokens": attestation["actual_prompt_tokens"],
            "context_budget_tokens": attestation["context_budget_tokens"],
            "context_headroom_tokens": attestation["context_headroom_tokens"],
            "status": "CONTEXT_FEASIBLE",
            "evidence_basis": "PROVIDER_REPORTED_EXACT_BINDING",
            "qualification_credit": False,
            "qualification_response_reuse_eligible": False,
        },
        "sibling_request": {
            "task_contract_id": sibling_task_id,
            "task_request_id": sibling_request["task_request_id"],
            "provider_request_body_sha256": sibling_request[
                "provider_request_body_sha256"
            ],
            "status": sibling_status,
            "reason": sibling_analysis["reason"],
        },
        sibling_status_key: sibling_status,
        "family_overall_live_ready": False,
    }
    body = {
        "schema_version": 1,
        "record_type": PACKET_RECORD_TYPE,
        "packet_status": (
            "EXACT_REQUEST_CONTEXT_FEASIBLE_SIBLING_EVIDENCE_REQUIRED"
        ),
        "authority": {
            "requirement_closure_hash": requirement[
                "requirement_closure_hash"
            ],
            "effective_d07_record_hash": content_hash(value=d07),
            "context_feasibility_attestation_id": attestation[
                "attestation_id"
            ],
            "sibling_request_context_analysis_id": sibling_analysis[
                "analysis_id"
            ],
            "freeze_receipt_id": freeze_status["receipt_id"],
            "qualification_cycle_id": freeze_status[
                "qualification_cycle_id"
            ],
            "stage_a_snapshot_id": stage_a["stage_a_snapshot_id"],
            "owner_decision_packet_id": owner[
                "owner_decision_packet_id"
            ],
        },
        "context_feasibility": context_status,
        "measurement_state": {
            "source_measurement_evidence_id": attestation[
                "source_measurement_evidence_id"
            ],
            "measurement_authorization_permanently_consumed": True,
            "additional_measurement_authorized": False,
            "historical_measurement_response_qualification_credit": False,
            "historical_measurement_response_reuse_for_qualification": False,
        },
        "qualification_state": {
            "live_qualification_authorized": False,
            "qualification_started": False,
            "qualification_fresh_ordinals_executed": 0,
            "future_response_usage_required": True,
            "future_actual_prompt_tokens_max": 200000,
            "missing_or_excess_usage_terminal_no_retry": True,
        },
        "readiness": {
            "readiness_by_family": freeze["readiness_by_family"],
            "readiness_by_task_request": task_readiness,
            "live_ready_family_ids": freeze["live_ready_family_ids"],
        },
        "financial_state": {
            "decision": "F3_NEED_MORE_EVIDENCE",
            "blocking_reason_codes": financial["blocking_reason_codes"],
            "production_resource_policy_changed": False,
        },
        "active_root_state": {
            "active_publication_id": freeze["identity"][
                "parent_r2_active_publication_id"
            ],
            "root_hashes": root_hashes,
            "root_business_artifacts_byte_equal": True,
            "publication_changed": False,
        },
        "historical_stage_c_b": {
            "stage_c_b_packet_id": stage_c_b["stage_c_b_packet_id"],
            "measurement_evidence_id": stage_c_b["measurement_terminal"][
                "measurement_evidence_id"
            ],
            "historical_egress_counts": historical_counts,
        },
        "current_pr_egress_counts": current_counts,
        "STILL_UNAUTHORIZED": [
            "ADDITIONAL_REAL_TOKEN_MEASUREMENT",
            "LIVE_QUALIFICATION",
            "QUALIFICATION_FRESH_ORDINALS",
            "R3",
            "R4",
            "FINANCIAL_PRODUCTION_RESOURCE_POLICY_CHANGE",
            "SELECTOR",
            "PUBLICATION",
        ],
        "BLOCKERS": [
            "SIBLING_EXACT_CONTEXT_EVIDENCE_REQUIRED",
            "F3_NEED_MORE_EVIDENCE",
            "LIVE_QUALIFICATION_UNAUTHORIZED",
        ],
    }
    return {**body, "stage_c_context_packet_id": content_hash(value=body)}


def write_stage_c_context_attestation_packet(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Persist the immutable packet and update only its current pointer."""
    packet = build_stage_c_context_attestation_packet(repo_root=repo_root)
    digest = str(packet["stage_c_context_packet_id"]).split(":", maxsplit=1)[1]
    relative = PACKET_ROOT / (digest + ".json")
    path = repo_root / relative
    if path.exists():
        if strict_json_file(path=path) != packet:
            _fail("Stage-C context packet content-address collision")
    else:
        atomic_write_json(path=path, value=packet)
    pointer_body = {
        "schema_version": 1,
        "record_type": PACKET_POINTER_TYPE,
        "stage_c_context_packet_id": packet["stage_c_context_packet_id"],
        "packet_path": relative.as_posix(),
    }
    pointer = {**pointer_body, "pointer_id": content_hash(value=pointer_body)}
    atomic_write_json(path=repo_root / PACKET_POINTER, value=pointer)
    return {
        "stage_c_context_packet_id": packet["stage_c_context_packet_id"],
        "packet_path": relative.as_posix(),
        "pointer_id": pointer["pointer_id"],
        "packet_status": packet["packet_status"],
        "live_ready_family_ids": packet["readiness"][
            "live_ready_family_ids"
        ],
        "current_pr_egress_counts": packet["current_pr_egress_counts"],
        "blockers": packet["BLOCKERS"],
    }


def validate_stage_c_context_attestation_packet(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Rebuild and validate the current packet without any provider action."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=PACKET_POINTER,
        id_field="pointer_id",
        label="Stage-C context packet pointer",
    )
    packet = _content_record(
        repo_root=repo_root,
        relative=Path(str(pointer["packet_path"])),
        id_field="stage_c_context_packet_id",
        label="Stage-C context packet",
    )
    historical_id = (
        "sha256:4dd0c536cb5cb746e5746c76ed69c337"
        "b98780d3d6d7a310d1c1bee5b3a8e64c"
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    revpar_exception = requirement["effective_decisions"]["D-07"][
        "choice"
    ].get("revpar_measurement_exception")
    if packet.get("stage_c_context_packet_id") == historical_id and (
        type(revpar_exception) is dict
        and revpar_exception.get("task_contract_id")
        == "lodging_revpar_table_v2"
    ):
        attestation = validate_table_context_feasibility_attestation(
            repo_root=repo_root,
        )
        comparison = validate_sibling_request_context_analysis(
            repo_root=repo_root,
        )
        authority = packet.get("authority", {})
        if (
            pointer["stage_c_context_packet_id"] != historical_id
            or authority.get("context_feasibility_attestation_id")
            != attestation["attestation_id"]
            or authority.get("sibling_request_context_analysis_id")
            != comparison["analysis_id"]
        ):
            _fail("Historical Stage-C packet dependency differs")
        return copy.deepcopy(packet)
    if (
        pointer["stage_c_context_packet_id"]
        != packet["stage_c_context_packet_id"]
        or packet != build_stage_c_context_attestation_packet(
            repo_root=repo_root,
        )
    ):
        _fail("Stage-C context packet differs from current authority")
    return copy.deepcopy(packet)
