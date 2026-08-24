"""Build and validate the content-addressed Issue #15 Stage C-A packet."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, Mapping, Sequence

from git_workspace import sanitized_git_environment
from validation_provenance import capture_source_snapshot
from validation_provenance import load_source_policy
from validation_provenance import pin_validation_publication_transaction
from validation_provenance import verify_validation_snapshot
from validation_provenance import ValidationProvenanceError
from validation_provenance import _git_paths as provenance_git_paths
from validation_provenance import _tree as provenance_tree

from .canonical import atomic_write_json, content_hash, sha256_file
from .canonical import strict_json_file
from .requirements import load_requirement_snapshot
from .stage_a_snapshot import _root_state, SOURCE_ONLY_ERRORS
from .table_context_measurement import build_table_context_measurement_plan
from .table_context_measurement import MEASUREMENT_EXECUTION_ROOT
from .table_context_measurement import MEASUREMENT_PLAN_ROOT


STAGE_C_ROOT = Path("artifacts/vnext/table_stage_c_evidence")
PACKET_ROOT = STAGE_C_ROOT / "stage_c_a_packets"
PACKET_POINTER = STAGE_C_ROOT / "current_stage_c_a_packet.json"
BENCHMARK_POINTER = (
    STAGE_C_ROOT / "financial_materialization_benchmark/current.json"
)
OWNER_DECISION_URL = (
    "https://github.com/wlvh/SEC_metrics/issues/15#issuecomment-5399126863"
)
EXPECTED_REQUIREMENT_CLOSURE = (
    "sha256:a5b0467d0df529a4c094107ee0430ea862d77e80f5a359ca6d407a806fb0367c"
)
EXPECTED_EFFECTIVE_D07 = (
    "sha256:200bb6feae25c5683260e2dd8a758f1ab3f0480b8694bb802ca44fd80835554f"
)
EXPECTED_ACTIVE_PUBLICATION = (
    "publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f"
)
EXPECTED_PUBLIC_MATRIX_ROWS = 309
_GIT_OID = re.compile(r"^[0-9a-f]{40}$")
_PACKET_FIELDS = {
    "BLOCKERS",
    "IMPLEMENTED_NOT_EXECUTED",
    "MEASURED_OFFLINE",
    "OWNER_APPROVED",
    "STILL_UNAUTHORIZED",
    "active_root_state",
    "authority",
    "egress_counts",
    "implementation_source_hashes",
    "measurement_authorization",
    "record_type",
    "schema_version",
    "source_snapshot",
    "stage_c_a_packet_id",
    "stage_c_a_status",
}


class StageCAPacketError(ValueError):
    """Report a stale, self-authorizing, or non-content-addressed packet."""


def _git(*, repo_root: Path, arguments: Sequence[str]) -> str:
    """Run one sanitized read-only Git command."""
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
        raise StageCAPacketError("Stage C-A Git identity is unavailable")
    return completed.stdout.strip()


def _candidate_source_snapshot(*, repo_root: Path) -> Dict[str, object]:
    """Hash a fully staged source candidate before its artifact-only commit."""
    policy = load_source_policy(workdir=repo_root)
    paths = provenance_git_paths(workdir=repo_root, policy=policy)
    unstaged = _git(
        repo_root=repo_root,
        arguments=["diff", "--name-only", "--", *policy.source_paths],
    ).splitlines()
    untracked = _git(
        repo_root=repo_root,
        arguments=[
            "ls-files", "--others", "--exclude-standard", "--",
            *policy.source_paths,
        ],
    ).splitlines()
    staged = _git(
        repo_root=repo_root,
        arguments=["diff", "--cached", "--name-only", "--", *policy.source_paths],
    ).splitlines()
    if unstaged or untracked or not staged:
        raise StageCAPacketError(
            "Stage C-A source candidate must be fully staged with no untracked source"
        )
    tree_hash, file_count = provenance_tree(
        workdir=repo_root, paths=paths,
    )
    head = _git(repo_root=repo_root, arguments=["rev-parse", "HEAD"])
    if _GIT_OID.fullmatch(head) is None:
        raise StageCAPacketError("Stage C-A base commit is invalid")
    staged_rows = sorted(set(staged))
    return {
        "candidate_status": "STAGED_SOURCE_CANDIDATE",
        "candidate_base_commit": head,
        "source_input_tree_sha256": tree_hash,
        "source_file_count": file_count,
        "staged_source_paths": staged_rows,
        "staged_source_path_set_hash": content_hash(value=staged_rows),
    }


def _historical_r2_source_errors(*, repo_root: Path) -> Sequence[str]:
    """Require every historical R2 non-source artifact to remain exact."""
    try:
        transaction = pin_validation_publication_transaction(workdir=repo_root)
        result = verify_validation_snapshot(
            workdir=repo_root,
            allow_equivalent_source_tree=True,
            publication_transaction=transaction,
        )
    except ValidationProvenanceError as error:
        raise StageCAPacketError(
            "Historical R2 validation snapshot is unavailable"
        ) from error
    if set(result.errors) != SOURCE_ONLY_ERRORS:
        raise StageCAPacketError(
            "Historical R2 snapshot has a non-source failure: {}".format(
                ";".join(result.errors),
            )
        )
    return sorted(result.errors)


def _content_record(
    *, repo_root: Path, relative: Path, id_field: str,
) -> Dict[str, object]:
    """Read one content-addressed JSON object and recompute its identity."""
    path = repo_root / relative
    if relative.is_absolute() or ".." in relative.parts:
        raise StageCAPacketError("Content record path is unsafe")
    if path.is_symlink() or not path.is_file():
        raise StageCAPacketError("Content record is absent or unsafe")
    value = strict_json_file(path=path)
    if type(value) is not dict or type(value.get(id_field)) is not str:
        raise StageCAPacketError("Content record identity is invalid")
    body = {key: value[key] for key in value if key != id_field}
    if value[id_field] != content_hash(value=body):
        raise StageCAPacketError("Content record bytes differ")
    return dict(value)


def _measurement_plan(*, repo_root: Path) -> Dict[str, object]:
    """Rebuild and compare the sole persisted Stage C-A measurement plan."""
    current = build_table_context_measurement_plan(repo_root=repo_root)
    digest = str(current["measurement_plan_id"]).split(":", maxsplit=1)[1]
    persisted = _content_record(
        repo_root=repo_root,
        relative=MEASUREMENT_PLAN_ROOT / (digest + ".json"),
        id_field="measurement_plan_id",
    )
    if persisted != current:
        raise StageCAPacketError("Persisted measurement plan differs")
    execution_root = repo_root / MEASUREMENT_EXECUTION_ROOT
    if execution_root.exists() or execution_root.is_symlink():
        raise StageCAPacketError(
            "Stage C-A must not contain a token-measurement execution namespace"
        )
    return current


def _benchmark_chain(*, repo_root: Path) -> Dict[str, object]:
    """Validate the current JPM semantic/run receipt pointer chain."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=BENCHMARK_POINTER,
        id_field="pointer_id",
    )
    semantic = _content_record(
        repo_root=repo_root,
        relative=Path(str(pointer["benchmark_receipt_path"])),
        id_field="benchmark_receipt_id",
    )
    run = _content_record(
        repo_root=repo_root,
        relative=Path(str(pointer["run_receipt_path"])),
        id_field="run_receipt_id",
    )
    if (
        pointer["benchmark_receipt_id"] != semantic["benchmark_receipt_id"]
        or pointer["run_receipt_id"] != run["run_receipt_id"]
        or run["benchmark_receipt_id"] != semantic["benchmark_receipt_id"]
        or semantic["status"] != "NOT_RUN_RSS_GUARD_UNAVAILABLE"
        or run["status"] != semantic["status"]
        or semantic["no_network_proof"]["benchmark_child_started"] is not False
        or semantic["materialization"]["completed"] is not False
    ):
        raise StageCAPacketError("JPM benchmark terminal chain differs")
    return {"pointer": pointer, "semantic": semantic, "run": run}


def _implementation_hashes(*, repo_root: Path) -> Dict[str, str]:
    """Hash the exact executor, guard, tests, and provider-call graph gate."""
    paths = (
        Path("scripts/vnext/table_context_measurement.py"),
        Path("scripts/vnext/ai_adapter.py"),
        Path("tools/vnext_table_context_measurement.py"),
        Path("tests/vnext/test_table_context_measurement.py"),
        Path("tools/benchmark_jpm_full_materialization.py"),
        Path("tests/vnext/test_table_stage_c_financial_materialization.py"),
        Path("tools/check_provider_egress.py"),
    )
    return {
        relative.as_posix(): sha256_file(path=repo_root / relative)
        for relative in paths
    }


def _egress_counts(
    *, repo_root: Path, plan: Mapping[str, object],
    benchmark: Mapping[str, object],
) -> Dict[str, int]:
    """Derive the Stage C-A zeroes from absent execution and benchmark receipts."""
    if (repo_root / MEASUREMENT_EXECUTION_ROOT).exists():
        raise StageCAPacketError("Token measurement execution exists in Stage C-A")
    network = benchmark["semantic"]["no_network_proof"]
    counts = {
        "real_model_provider_egress_count": int(
            network["real_model_provider_egress_count"]
        ),
        "paid_model_provider_call_count": int(
            network["paid_model_provider_call_count"]
        ),
        "real_SEC_egress_count": int(network["real_SEC_egress_count"]),
    }
    if counts != {
        "real_model_provider_egress_count": 0,
        "paid_model_provider_call_count": 0,
        "real_SEC_egress_count": 0,
    } or plan["provider_request_body_sha256"] == "":
        raise StageCAPacketError("Stage C-A egress closure differs")
    return counts


def _packet_body(
    *, repo_root: Path, source_snapshot: Mapping[str, object],
) -> Dict[str, object]:
    """Build the answer-first Stage C-A owner/reviewer packet body."""
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    d07 = requirement["effective_decisions"]["D-07"]
    if (
        requirement["requirement_closure_hash"] != EXPECTED_REQUIREMENT_CLOSURE
        or content_hash(value=d07) != EXPECTED_EFFECTIVE_D07
    ):
        raise StageCAPacketError("Stage C-A Requirement authority differs")
    plan = _measurement_plan(repo_root=repo_root)
    benchmark = _benchmark_chain(repo_root=repo_root)
    root = _root_state(repo_root=repo_root)
    if (
        root["active_publication_id"] != EXPECTED_ACTIVE_PUBLICATION
        or root["public_matrix_row_count"] != EXPECTED_PUBLIC_MATRIX_ROWS
        or benchmark["semantic"]["root_business_artifacts_after"]
        != {
            key: root["root_hashes"][key]
            for key in benchmark["semantic"][
                "root_business_artifacts_after"
            ]
        }
    ):
        raise StageCAPacketError("Stage C-A active/root state differs")
    counts = _egress_counts(
        repo_root=repo_root, plan=plan, benchmark=benchmark,
    )
    benchmark_semantic = benchmark["semantic"]
    benchmark_run = benchmark["run"]
    return {
        "schema_version": 1,
        "record_type": "ISSUE_15_STAGE_C_A_DECISION_EVIDENCE_PACKET",
        "stage_c_a_status": "BLOCKED_OFFLINE_BENCHMARK_NOT_RUN",
        "authority": {
            "issue_number": 15,
            "owner_decision_comment_url": OWNER_DECISION_URL,
            "requirement_closure_hash": requirement[
                "requirement_closure_hash"
            ],
            "effective_d07_record_hash": content_hash(value=d07),
            "historical_stage_c_baseline": plan[
                "historical_stage_c_baseline"
            ],
        },
        "OWNER_APPROVED": {
            "exact_lodging_token_measurement_path_implementation": True,
            "jpm_test_only_full_materialization_benchmark": True,
            "repository_monetary_caps": "DISABLED",
            "spending_control": "EXTERNAL_API_ACCOUNT_BALANCE",
            "safety_limit": "EXACTLY_ONE_PROVIDER_EGRESS_ZERO_RETRY",
        },
        "IMPLEMENTED_NOT_EXECUTED": {
            "lodging_actual_token_measurement_executor": True,
            "external_exact_head_authorization_received": False,
            "opaque_execution_authorization_issued": False,
            "provider_egress_executed": False,
            "measurement_evidence_status": "NOT_RUN",
        },
        "MEASURED_OFFLINE": {
            "benchmark_receipt_id": benchmark_semantic[
                "benchmark_receipt_id"
            ],
            "benchmark_run_receipt_id": benchmark_run["run_receipt_id"],
            "status": benchmark_semantic["status"],
            "completion_result": benchmark_semantic["materialization"][
                "completed"
            ],
            "peak_rss_bytes": benchmark_run["peak_rss_bytes"],
            "wall_time_seconds": benchmark_run["wall_time_seconds"],
            "canonical_json_bytes": benchmark_semantic["materialization"][
                "canonical_json_bytes"
            ],
            "derived_asset_id": benchmark_semantic["materialization"][
                "derived_asset_id"
            ],
            "blocking_reason": benchmark_semantic["safety_ceilings"][
                "guard_status"
            ],
        },
        "STILL_UNAUTHORIZED": [
            "REAL_TOKEN_MEASUREMENT",
            "LIVE_QUALIFICATION",
            "R3",
            "R4",
            "PRODUCTION_MAX_TOTAL_CELLS_CHANGE",
            "SHARDING",
            "SERIALIZER_CANDIDATE",
            "SELECTOR",
            "PUBLICATION",
        ],
        "measurement_authorization": {
            "measurement_plan_id": plan["measurement_plan_id"],
            "measurement_plan_path": (
                MEASUREMENT_PLAN_ROOT
                / (
                    str(plan["measurement_plan_id"]).split(
                        ":", maxsplit=1,
                    )[1] + ".json"
                )
            ).as_posix(),
            "authorization_id": "NOT_ISSUED",
            "repository_head_binding": plan["repository_head_binding"],
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "ordinary_qualification_max_estimated_input_tokens": plan[
                "ordinary_qualification_max_estimated_input_tokens"
            ],
        },
        "active_root_state": {
            **root,
            "root_business_artifacts_before": benchmark_semantic[
                "root_business_artifacts_before"
            ],
            "root_business_artifacts_after": benchmark_semantic[
                "root_business_artifacts_after"
            ],
            "root_business_artifacts_byte_equal": benchmark_semantic[
                "root_business_artifacts_byte_equal"
            ],
        },
        "egress_counts": counts,
        "implementation_source_hashes": _implementation_hashes(
            repo_root=repo_root,
        ),
        "source_snapshot": dict(source_snapshot),
        "BLOCKERS": ["JPM_RSS_GUARD_UNAVAILABLE"],
    }


def build_stage_c_a_packet(*, repo_root: Path) -> Dict[str, object]:
    """Build the packet from a fully staged source candidate."""
    source = _candidate_source_snapshot(repo_root=repo_root)
    body = _packet_body(repo_root=repo_root, source_snapshot=source)
    return {**body, "stage_c_a_packet_id": content_hash(value=body)}


def write_stage_c_a_packet(*, repo_root: Path) -> Dict[str, object]:
    """Persist the content-addressed packet and current pointer."""
    packet = build_stage_c_a_packet(repo_root=repo_root)
    digest = str(packet["stage_c_a_packet_id"]).split(":", maxsplit=1)[1]
    packet_relative = PACKET_ROOT / (digest + ".json")
    packet_path = repo_root / packet_relative
    if packet_path.exists():
        if strict_json_file(path=packet_path) != packet:
            raise StageCAPacketError("Stage C-A packet collision")
    else:
        atomic_write_json(path=packet_path, value=packet)
    pointer_body = {
        "schema_version": 1,
        "record_type": "ISSUE_15_STAGE_C_A_PACKET_POINTER",
        "stage_c_a_packet_id": packet["stage_c_a_packet_id"],
        "packet_path": packet_relative.as_posix(),
    }
    pointer = {**pointer_body, "pointer_id": content_hash(value=pointer_body)}
    atomic_write_json(path=repo_root / PACKET_POINTER, value=pointer)
    return {
        "stage_c_a_packet_id": packet["stage_c_a_packet_id"],
        "packet_path": packet_relative.as_posix(),
        "pointer_id": pointer["pointer_id"],
        "status": packet["stage_c_a_status"],
        "measurement_plan_id": packet["measurement_authorization"][
            "measurement_plan_id"
        ],
        "measurement_authorization_id": packet[
            "measurement_authorization"
        ]["authorization_id"],
        "benchmark_receipt_id": packet["MEASURED_OFFLINE"][
            "benchmark_receipt_id"
        ],
    }


def validate_stage_c_a_packet(*, repo_root: Path) -> Dict[str, object]:
    """Validate packet content, clean source overlay, R2 bytes, and zero egress."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=PACKET_POINTER,
        id_field="pointer_id",
    )
    packet = _content_record(
        repo_root=repo_root,
        relative=Path(str(pointer["packet_path"])),
        id_field="stage_c_a_packet_id",
    )
    if set(packet) != _PACKET_FIELDS:
        raise StageCAPacketError("Stage C-A packet fields differ")
    if pointer["stage_c_a_packet_id"] != packet["stage_c_a_packet_id"]:
        raise StageCAPacketError("Stage C-A pointer binding differs")
    source = capture_source_snapshot(workdir=repo_root)
    expected_source = packet["source_snapshot"]
    if (
        source.checkout_status != "GIT_CLEAN"
        or source.source_commit is None
        or source.tree_sha256
        != expected_source["source_input_tree_sha256"]
        or source.file_count != expected_source["source_file_count"]
    ):
        raise StageCAPacketError("Stage C-A source overlay differs")
    _historical_r2_source_errors(repo_root=repo_root)
    rebuilt_body = _packet_body(
        repo_root=repo_root, source_snapshot=expected_source,
    )
    if packet != {
        **rebuilt_body,
        "stage_c_a_packet_id": content_hash(value=rebuilt_body),
    }:
        raise StageCAPacketError("Stage C-A packet rebuild differs")
    return {
        "stage_c_a_packet_id": packet["stage_c_a_packet_id"],
        "source_commit": source.source_commit,
        "source_commit_equivalent_tree": (
            source.source_commit != expected_source["candidate_base_commit"]
        ),
        "measurement_plan_id": packet["measurement_authorization"][
            "measurement_plan_id"
        ],
        "measurement_authorization_id": packet[
            "measurement_authorization"
        ]["authorization_id"],
        "benchmark_receipt_id": packet["MEASURED_OFFLINE"][
            "benchmark_receipt_id"
        ],
        "status": packet["stage_c_a_status"],
        "blockers": packet["BLOCKERS"],
        "egress_counts": packet["egress_counts"],
    }
