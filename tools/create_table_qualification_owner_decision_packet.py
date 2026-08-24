#!/usr/bin/env python3
"""Create the Stage-B owner-approved/undecided evidence packet offline.

The packet binds the same-ID D-07 decision, family readiness, the two
decision-neutral investigation receipts, unchanged R2 root state, and zero
egress.  It does not choose a serializer/resource option or authorize live
measurement, qualification, model, or SEC activity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.canonical import atomic_write_json, content_hash  # noqa: E402
from vnext.canonical import parse_utc_timestamp, sha256_file  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402
from vnext.stage_a_snapshot import StageASnapshotError  # noqa: E402
from vnext.stage_a_snapshot import validate_stage_a_snapshot  # noqa: E402
from vnext.table_qualification_freeze import (  # noqa: E402
    TableQualificationFreezeError,
)
from vnext.table_qualification_freeze import (  # noqa: E402
    validate_table_qualification_freeze,
)


PACKET_ROOT = Path(
    "artifacts/vnext/table_qualification_freeze/decision_packets"
)
PACKET_POINTER = Path(
    "artifacts/vnext/table_qualification_freeze/"
    "current_owner_decision_packet.json"
)
OWNER_DECISION_URL = (
    "https://github.com/wlvh/SEC_metrics/issues/15#issuecomment-5390663414"
)
CONTEXT_RECEIPT_ID = (
    "sha256:2dd551a5613cf6980644ae8f9a99c9231456c736ae29969f613d4c8cedd1e3a1"
)
CONTEXT_RECEIPT_PATH = Path(
    "artifacts/vnext/table_stage_b_investigation/context_minimization/"
    "2dd551a5613cf6980644ae8f9a99c9231456c736ae29969f613d4c8cedd1e3a1.json"
)
CENSUS_RECEIPT_ID = (
    "sha256:ea3d796f256a43ac5a6079de753d7d5456fc6d7485bb794ef4c9e27276ca6f2c"
)
CENSUS_RECEIPT_PATH = Path(
    "artifacts/vnext/table_stage_b_investigation/financial_grid_census/"
    "ea3d796f256a43ac5a6079de753d7d5456fc6d7485bb794ef4c9e27276ca6f2c.json"
)


def _packet_history(
    *, repo_root: Path, generated_at_utc: str,
) -> list[str]:
    """Return history, excluding only this exact packet rebuild."""
    root = repo_root / PACKET_ROOT
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Owner decision packet namespace is unsafe")
    values = []
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Owner decision packet history entry is unsafe")
        value = strict_json_file(path=path)
        if (
            type(value) is not dict
            or value.get("record_type")
            != "TABLE_QUALIFICATION_OWNER_DECISION_PACKET"
            or type(value.get("owner_decision_packet_id")) is not str
        ):
            raise ValueError("Owner decision packet history entry is invalid")
        body = {
            field: value[field]
            for field in value
            if field != "owner_decision_packet_id"
        }
        if value["owner_decision_packet_id"] != content_hash(value=body):
            raise ValueError("Owner decision packet history identity differs")
        if (
            value.get("schema_version") == 3
            and value.get("generated_at_utc") == generated_at_utc
        ):
            continue
        values.append(str(value["owner_decision_packet_id"]))
    return values


def _freeze_receipt(*, repo_root: Path) -> Dict[str, object]:
    """Load the current freeze only after full family-scoped revalidation."""
    status = validate_table_qualification_freeze(repo_root=repo_root)
    pointer = strict_json_file(
        path=repo_root / "config/table_qualification_freeze.json",
    )
    if (
        type(pointer) is not dict
        or type(pointer.get("receipt_path")) is not str
    ):
        raise ValueError("Table qualification freeze pointer is invalid")
    path = repo_root / str(pointer["receipt_path"])
    if path.is_symlink() or not path.is_file():
        raise ValueError("Table qualification freeze receipt is unsafe")
    receipt = strict_json_file(path=path)
    if (
        type(receipt) is not dict
        or receipt.get("table_qualification_freeze_receipt_id")
        != status["receipt_id"]
        or receipt.get("qualification_cycle_id")
        != status["qualification_cycle_id"]
        or receipt.get("readiness_by_family")
        != status["readiness_by_family"]
        or receipt.get("live_ready_family_ids")
        != status["live_ready_family_ids"]
    ):
        raise ValueError("Table qualification freeze receipt differs")
    return dict(receipt)


def _addressed_receipt(
    *, repo_root: Path, relative: Path, expected_id: str,
    expected_record_type: str,
) -> Dict[str, object]:
    """Load and recompute one exact Stage-B investigation receipt."""
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("Stage-B investigation receipt is absent or unsafe")
    value = strict_json_file(path=path)
    if (
        type(value) is not dict
        or value.get("receipt_id") != expected_id
        or value.get("record_type") != expected_record_type
        or value.get("status") != "DECISION_NEUTRAL_OFFLINE_EVIDENCE"
    ):
        raise ValueError("Stage-B investigation receipt identity differs")
    body = {key: value[key] for key in value if key != "receipt_id"}
    if content_hash(value=body) != expected_id:
        raise ValueError("Stage-B investigation receipt content hash differs")
    return dict(value)


def _stage_a_receipt(
    *, repo_root: Path, freeze_receipt_id: str,
) -> Dict[str, object]:
    """Validate Stage-A publicly, then load its addressed full receipt."""
    status = validate_stage_a_snapshot(repo_root=repo_root)
    if status["freeze_receipt_id"] != freeze_receipt_id:
        raise ValueError("Stage-A summary freeze binding differs")
    digest = freeze_receipt_id.split(":", maxsplit=1)[1]
    relative = (
        Path("artifacts/vnext/table_qualification_freeze/stage_a_validation")
        / (digest + ".json")
    )
    value = strict_json_file(path=repo_root / relative)
    if (
        type(value) is not dict
        or value.get("stage_a_snapshot_id") != status["stage_a_snapshot_id"]
        or value.get("freeze_receipt_id") != freeze_receipt_id
    ):
        raise ValueError("Stage-A full receipt identity differs")
    body = {key: value[key] for key in value if key != "stage_a_snapshot_id"}
    if content_hash(value=body) != value["stage_a_snapshot_id"]:
        raise ValueError("Stage-A full receipt content hash differs")
    return dict(value)


def _investigation_binding(
    *, repo_root: Path, relative: Path, receipt: Mapping[str, object],
) -> Dict[str, object]:
    """Return one packet-ready path/hash/ID binding."""
    return {
        "receipt_id": receipt["receipt_id"],
        "receipt_path": relative.as_posix(),
        "receipt_file_sha256": sha256_file(path=repo_root / relative),
        "record_type": receipt["record_type"],
        "status": receipt["status"],
    }


def build_owner_decision_packet(
    *, repo_root: Path, generated_at_utc: str,
) -> Dict[str, object]:
    """Assemble approved decisions and still-undecided evidence separately."""
    parse_utc_timestamp(value=generated_at_utc)
    receipt = _freeze_receipt(repo_root=repo_root)
    stage_a = _stage_a_receipt(
        repo_root=repo_root,
        freeze_receipt_id=receipt["table_qualification_freeze_receipt_id"],
    )
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    context = _addressed_receipt(
        repo_root=repo_root,
        relative=CONTEXT_RECEIPT_PATH,
        expected_id=CONTEXT_RECEIPT_ID,
        expected_record_type="TABLE_STAGE_B_CONTEXT_MINIMIZATION_RECEIPT",
    )
    census = _addressed_receipt(
        repo_root=repo_root,
        relative=CENSUS_RECEIPT_PATH,
        expected_id=CENSUS_RECEIPT_ID,
        expected_record_type="TABLE_STAGE_B_FINANCIAL_GRID_CENSUS_RECEIPT",
    )
    d07 = requirement["effective_decisions"]["D-07"]
    d07_hash = content_hash(value=d07)
    readiness = receipt["readiness_by_family"]
    lodging = readiness["lodging_kpi_table"]
    financial = readiness["financial_statement"]
    if (
        receipt["d07_decision_required"] is not False
        or receipt["live_ready_family_ids"] != []
        or lodging["context_gate"]["maximum_observed_estimated_input_tokens"]
        != 392447
        or lodging["blocking_reason_codes"] != ["ESTIMATED_CONTEXT_LIMIT"]
        or financial["blocking_reason_codes"]
        != ["EXPANDED_GRID_RESOURCE_LIMIT"]
    ):
        raise ValueError("Current family readiness differs from Stage-B facts")
    provider = receipt["provider_state"]
    if (
        provider["qualification_cycle_real_model_egress_count"] != 0
        or provider["qualification_cycle_paid_model_call_count"] != 0
        or provider["qualification_cycle_sec_egress_count"] != 0
    ):
        raise ValueError("Stage-B packet requires zero egress")
    frozen_root = receipt["identity"]["root_hashes"]
    for investigation in (context, census):
        if (
            investigation["root_business_artifacts_before"] != frozen_root
            or investigation["root_business_artifacts_after"] != frozen_root
            or investigation["root_business_artifacts_byte_equal"] is not True
        ):
            raise ValueError("Stage-B investigation root state differs")
    if stage_a["root_state"]["root_hashes"] != frozen_root:
        raise ValueError("Stage-A root state differs from freeze")
    history = _packet_history(
        repo_root=repo_root,
        generated_at_utc=generated_at_utc,
    )
    pointer = strict_json_file(
        path=repo_root / "config/table_qualification_freeze.json",
    )
    freeze_path = repo_root / str(pointer["receipt_path"])
    body = {
        "schema_version": 3,
        "record_type": "TABLE_QUALIFICATION_OWNER_DECISION_PACKET",
        "generated_at_utc": generated_at_utc,
        "decision_register_modified": True,
        "owner_approved_decisions_implemented": True,
        "undecided_product_choice_made": False,
        "supersedes_owner_decision_packet_ids": sorted(history),
        "authority": {
            "requirement_closure_hash": requirement[
                "requirement_closure_hash"
            ],
            "effective_d07_record_hash": d07_hash,
            "effective_d07_supersedes_record_hash": d07[
                "supersedes_decision_id"
            ],
            "owner_decision_comment_url": OWNER_DECISION_URL,
            "owner_decision_evidence_matches_d07": (
                d07["evidence"] == OWNER_DECISION_URL
            ),
        },
        "freeze_binding": {
            "freeze_receipt_id": receipt[
                "table_qualification_freeze_receipt_id"
            ],
            "freeze_receipt_sha256": sha256_file(path=freeze_path),
            "qualification_cycle_id": receipt["qualification_cycle_id"],
            "semantic_freeze_commit": receipt["freeze_commit"],
            "matrix_sha256": receipt["wb4_compact_transport"][
                "d07_authority"
            ]["matrix_sha256"],
            "catalog_sha256": receipt["wb6_task_contracts"][
                "catalog_sha256"
            ],
            "stage_a_snapshot_id": stage_a["stage_a_snapshot_id"],
        },
        "OWNER_APPROVED": {
            "estimated_input_threshold": {
                "estimator_id": "utf8_byte_upper_bound",
                "estimator_version": "1",
                "old_max_estimated_input_tokens": 100000,
                "new_max_estimated_input_tokens": 200000,
                "inclusive": True,
                "scope": "PER_FAMILY_PER_REQUEST",
            },
            "reader_table_set": (
                "ALL_DOCUMENT_TABLE_GRIDS_IN_DOCUMENT_ORDER"
            ),
            "semantic_prefilter": False,
            "selector_authorized": False,
            "family_scoped_readiness": True,
            "shared_dependency_drift_policy": (
                "INVALIDATE_ALL_DEPENDENT_FAMILIES"
            ),
            "family_local_drift_policy": (
                "INVALIDATE_OWNER_FAMILY_ONLY"
            ),
            "live_measurement_authorized": False,
            "live_qualification_authorized": False,
        },
        "STILL_UNDECIDED": [
            {
                "decision": "adopt_any_lossless_serializer_candidate",
                "selected_value": None,
            },
            {
                "decision": "authorize_actual_token_live_measurement",
                "selected_value": None,
            },
            {
                "decision": "financial_raise_cap_or_per_table_shard",
                "selected_value": None,
            },
            {
                "decision": "replace_financial_development_source",
                "selected_value": None,
            },
            {
                "decision": "authorize_or_require_selector",
                "selected_value": None,
            },
        ],
        "current_readiness": {
            "readiness_by_family": readiness,
            "live_ready_family_ids": receipt["live_ready_family_ids"],
            "actual_prompt_tokens": "NOT_RUN",
            "lodging_summary": "BLOCKED_BY_392447_GT_200000",
            "financial_summary": "BLOCKED_BY_EXPANDED_GRID_RESOURCE_LIMIT",
        },
        "investigation_bindings": {
            "context_minimization": _investigation_binding(
                repo_root=repo_root,
                relative=CONTEXT_RECEIPT_PATH,
                receipt=context,
            ),
            "financial_grid_census": _investigation_binding(
                repo_root=repo_root,
                relative=CENSUS_RECEIPT_PATH,
                receipt=census,
            ),
        },
        "context_candidate_comparison": context[
            "candidate_comparison_table"
        ],
        "financial_grid_census_summary": {
            "exact_total_rectangular_expanded_cell_count": census["census"][
                "exact_total_rectangular_expanded_cell_count"
            ],
            "synthetic_blank_ratio": census["census"][
                "synthetic_blank_ratio"
            ],
            "span_duplicate_ratio": census["census"][
                "span_duplicate_ratio"
            ],
            "full_materialization_benchmark": census[
                "full_materialization_benchmark"
            ],
            "option_matrix": census["decision_neutral_option_matrix"],
            "selected_option": census["selected_option"],
        },
        "unchanged_active_root": {
            "active_publication_id": stage_a["root_state"][
                "active_publication_id"
            ],
            "public_matrix_row_count": stage_a["root_state"][
                "public_matrix_row_count"
            ],
            "public_key_set_hash": stage_a["root_state"][
                "public_key_set_hash"
            ],
            "root_hashes": frozen_root,
            "before_after_byte_equal": True,
        },
        "egress_counts": {
            "real_model_provider_egress_count": provider[
                "qualification_cycle_real_model_egress_count"
            ],
            "paid_model_provider_call_count": provider[
                "qualification_cycle_paid_model_call_count"
            ],
            "real_sec_egress_count": provider[
                "qualification_cycle_sec_egress_count"
            ],
        },
        "completion_boundary": {
            "any_family_qualified": False,
            "issue_15_complete": False,
            "r3_r4_r5_started": False,
            "active_publication_changed": False,
        },
    }
    if body["financial_grid_census_summary"]["selected_option"] is not None:
        raise ValueError("Owner packet cannot select a financial option")
    return {**body, "owner_decision_packet_id": content_hash(value=body)}


def write_owner_decision_packet(
    *, repo_root: Path, generated_at_utc: str,
) -> Dict[str, object]:
    """Write one content-addressed packet and update only its pointer."""
    packet = build_owner_decision_packet(
        repo_root=repo_root,
        generated_at_utc=generated_at_utc,
    )
    packet_path = repo_root / PACKET_ROOT / (
        packet["owner_decision_packet_id"].split(":", maxsplit=1)[1]
        + ".json"
    )
    if packet_path.exists():
        if (
            packet_path.is_symlink()
            or not packet_path.is_file()
            or strict_json_file(path=packet_path) != packet
        ):
            raise ValueError("Owner decision packet destination differs")
    else:
        atomic_write_json(path=packet_path, value=packet)
    pointer_body = {
        "schema_version": 1,
        "record_type": "TABLE_QUALIFICATION_OWNER_DECISION_PACKET_POINTER",
        "owner_decision_packet_id": packet["owner_decision_packet_id"],
        "packet_path": packet_path.relative_to(repo_root).as_posix(),
        "superseded_owner_decision_packet_ids": packet[
            "supersedes_owner_decision_packet_ids"
        ],
    }
    atomic_write_json(path=repo_root / PACKET_POINTER, value=pointer_body)
    return {
        **packet,
        "packet_path": packet_path.relative_to(repo_root).as_posix(),
        "pointer_path": PACKET_POINTER.as_posix(),
    }


def main(*, argv: Sequence[str]) -> int:
    """Parse local-only packet generation arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-at-utc", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        packet = write_owner_decision_packet(
            repo_root=REPO_ROOT,
            generated_at_utc=arguments.generated_at_utc,
        )
    except (
        StageASnapshotError,
        TableQualificationFreezeError,
        ValueError,
    ) as error:
        print(json.dumps({
            "status": "BLOCKED",
            "message": str(error),
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "OWNER_DECISION_PACKET_WRITTEN",
        "owner_decision_packet_id": packet["owner_decision_packet_id"],
        "packet_path": packet["packet_path"],
        "qualification_cycle_id": packet["freeze_binding"][
            "qualification_cycle_id"
        ],
        "live_ready_family_ids": packet["current_readiness"][
            "live_ready_family_ids"
        ],
        "egress_counts": packet["egress_counts"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
