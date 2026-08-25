"""Build and validate the authorized Issue #15 Stage C-B terminal packet.

The packet is deliberately post-egress and read-only with respect to the
provider.  It validates the immutable Stage C-A plan, the external exact-head
review receipt, the one permanent egress marker, the raw provider response,
and the non-qualification measurement evidence without rebuilding or sending
the provider request.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from validation_provenance import capture_source_snapshot

from .canonical import atomic_write_json, canonical_json_bytes, content_hash
from .canonical import parse_utc_timestamp, sha256_bytes, sha256_file
from .canonical import strict_json_file, strict_json_loads
from .stage_a_snapshot import _root_state
from .stage_c_packet import _benchmark_chain, _candidate_source_snapshot
from .stage_c_packet import _content_record, _git
from .stage_c_packet import _historical_r2_source_errors
from .stage_c_packet import EXPECTED_ACTIVE_PUBLICATION
from .stage_c_packet import EXPECTED_PUBLIC_MATRIX_ROWS
from .stage_c_packet import PACKET_POINTER as STAGE_C_A_PACKET_POINTER
from .table_context_measurement import MEASUREMENT_EXECUTION_ROOT
from .table_context_measurement import MEASUREMENT_PLAN_ROOT
from .table_context_measurement import validate_table_context_measurement_evidence


STAGE_C_ROOT = Path("artifacts/vnext/table_stage_c_evidence")
PACKET_ROOT = STAGE_C_ROOT / "stage_c_b_packets"
PACKET_POINTER = STAGE_C_ROOT / "current_stage_c_b_packet.json"

APPROVAL_REVIEW = {
    "review_id": 5014622571,
    "state": "COMMENTED",
    "reviewed_head": "451dd693175bea6c1196a09989c60017e96d63e7",
    "reviewed_tree": "78af0116b23e72afe02707aa7209e81d904c83f1",
    "submitted_at": "2026-08-25T03:17:49Z",
    "review_url": (
        "https://github.com/wlvh/SEC_metrics/pull/20"
        "#pullrequestreview-5014622571"
    ),
    "code_verdict": "APPROVE_STAGE_C_MEASUREMENT_PATH",
    "token_measurement_authorization": (
        "AUTHORIZE_ONE_TOKEN_MEASUREMENT"
    ),
    "financial_decision": "F3_NEED_MORE_EVIDENCE",
}
AUTHORIZED_AT_UTC = "2026-08-25T03:16:33Z"
EXPECTED_PLAN_ID = (
    "sha256:89d90019e929566df8e3d7a93c4c8a360067cdc0e3977fa9e4a8ece00a9dbceb"
)
EXPECTED_CYCLE_ID = (
    "sha256:17700ed40fa679c95815956da55a14d8062c2a8e022bb779e48958a328c1c1d2"
)
EXPECTED_AUTHORIZATION_ID = (
    "sha256:0878cfe58623f07ad3e706afb03af0ed96c6de9752c5caf0c904e26e60d2524d"
)
EXPECTED_PROVIDER_REQUEST_SHA256 = (
    "5ffa7b16d54ff9e3c2bdbc10d468f84b9aaae2ac029b5fc63e459d895eb8109a"
)
MEASUREMENT_ORDINAL = 1

_MARKER_FIELDS = {
    "authorization_id",
    "egress_marker_id",
    "egress_started_at_utc",
    "execution_id",
    "measurement_cycle_id",
    "measurement_ordinal",
    "provider_request_body_sha256",
    "record_type",
    "schema_version",
    "transport_kind",
}
_PACKET_FIELDS = {
    "BLOCKERS",
    "STILL_UNAUTHORIZED",
    "active_root_state",
    "authority",
    "financial_evidence",
    "measurement_semantics",
    "measurement_terminal",
    "record_type",
    "schema_version",
    "source_snapshot",
    "stage_c_b_packet_id",
    "stage_c_b_status",
}


class StageCBPacketError(ValueError):
    """Report a stale, incomplete, or credit-polluting Stage C-B packet."""


def _fail(message: str) -> None:
    """Raise the stable packet error at the current validation boundary."""
    raise StageCBPacketError(message)


def _validate_plan(*, repo_root: Path) -> Dict[str, object]:
    """Load the immutable authorized plan and revalidate protected bytes."""
    digest = EXPECTED_PLAN_ID.split(":", maxsplit=1)[1]
    plan = _content_record(
        repo_root=repo_root,
        relative=MEASUREMENT_PLAN_ROOT / (digest + ".json"),
        id_field="measurement_plan_id",
    )
    expected = {
        "measurement_plan_id": EXPECTED_PLAN_ID,
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_occupancy_table_v2",
        "source_company_id": "marriott_international",
        "source_sha256": (
            "c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547"
        ),
        "table_payload_serialization_version": "2",
        "provider_request_body_sha256": EXPECTED_PROVIDER_REQUEST_SHA256,
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "api": "chat_completions",
        "estimated_input_tokens": 392447,
        "ordinary_qualification_max_estimated_input_tokens": 200000,
        "ordinary_qualification_remains_blocked": True,
        "allowed_successful_provider_egress_count": 1,
        "automatic_retry_count": 0,
        "qualification_ordinal_credit": False,
        "qualification_evidence_eligible": False,
        "publication_eligible": False,
        "response_reuse_for_qualification": False,
        "consumes_authorization_after_any_egress_marker": True,
        "execution_requires_external_exact_head_authorization": True,
    }
    if any(plan.get(key) != value for key, value in expected.items()):
        _fail("Authorized Stage C-B measurement plan differs")

    protected = plan.get("protected_closure")
    if type(protected) is not dict or type(protected.get("files")) is not dict:
        _fail("Authorized protected closure is invalid")
    protected_body = {
        key: protected[key]
        for key in protected
        if key != "protected_closure_hash"
    }
    if (
        protected.get("protected_closure_hash") != content_hash(
            value=protected_body,
        )
        or plan.get("protected_closure_hash")
        != protected.get("protected_closure_hash")
    ):
        _fail("Authorized protected closure identity differs")
    for relative_text, expected_file in protected["files"].items():
        relative = Path(str(relative_text))
        path = repo_root / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or path.is_symlink()
            or not path.is_file()
            or type(expected_file) is not dict
            or path.stat().st_size != expected_file.get("size")
            or sha256_file(path=path) != expected_file.get("sha256")
        ):
            _fail("Authorized protected file bytes differ: {}".format(relative))
    return plan


def _authorization_binding(*, plan: Mapping[str, object]) -> Dict[str, object]:
    """Recompute the reviewer-bound cycle and authorization identities."""
    cycle_body = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "authorized_repository_head": APPROVAL_REVIEW["reviewed_head"],
        "authorized_repository_tree": APPROVAL_REVIEW["reviewed_tree"],
        "measurement_ordinal": MEASUREMENT_ORDINAL,
    }
    cycle_id = content_hash(value=cycle_body)
    body = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_cycle_id": cycle_id,
        "measurement_ordinal": MEASUREMENT_ORDINAL,
        "external_authorization_statement": APPROVAL_REVIEW[
            "token_measurement_authorization"
        ],
        "authorized_at_utc": AUTHORIZED_AT_UTC,
        "authorized_repository_head": APPROVAL_REVIEW["reviewed_head"],
        "authorized_repository_tree": APPROVAL_REVIEW["reviewed_tree"],
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
    if (
        cycle_id != EXPECTED_CYCLE_ID
        or binding["authorization_id"] != EXPECTED_AUTHORIZATION_ID
    ):
        _fail("Reviewer authorization identity differs")
    return binding


def _validate_authorized_commit(*, repo_root: Path) -> None:
    """Require the reviewed commit/tree to remain in current history."""
    reviewed_head = str(APPROVAL_REVIEW["reviewed_head"])
    reviewed_tree = _git(
        repo_root=repo_root,
        arguments=["rev-parse", reviewed_head + "^{tree}"],
    )
    if reviewed_tree != APPROVAL_REVIEW["reviewed_tree"]:
        _fail("Reviewed exact tree differs")
    try:
        _git(
            repo_root=repo_root,
            arguments=["merge-base", "--is-ancestor", reviewed_head, "HEAD"],
        )
    except Exception as error:
        raise StageCBPacketError(
            "Reviewed exact head is not an ancestor of current HEAD"
        ) from error


def _usage_int(
    *, usage: Mapping[str, object], names: Sequence[str], required: bool,
) -> Optional[int]:
    """Return one consistent nonnegative provider usage value."""
    values = [usage[name] for name in names if name in usage]
    if not values:
        if required:
            _fail("Provider usage field is absent")
        return None
    if any(type(value) is not int or value < 0 for value in values):
        _fail("Provider usage field is invalid")
    unique = {int(value) for value in values}
    if len(unique) != 1:
        _fail("Provider usage aliases conflict")
    return unique.pop()


def _validate_terminal(
    *, repo_root: Path, plan: Mapping[str, object],
    binding: Mapping[str, object],
) -> Dict[str, object]:
    """Validate the sole marker, raw response, and measurement evidence."""
    cycle_digest = EXPECTED_CYCLE_ID.split(":", maxsplit=1)[1]
    cycle_relative = MEASUREMENT_EXECUTION_ROOT / cycle_digest
    cycle_dir = repo_root / cycle_relative
    if cycle_dir.is_symlink() or not cycle_dir.is_dir():
        _fail("Stage C-B execution directory is absent or unsafe")
    expected_top = {"provider_egress_marker.json", "evidence", "provider_responses"}
    if {path.name for path in cycle_dir.iterdir()} != expected_top:
        _fail("Stage C-B execution path set differs")

    marker_relative = cycle_relative / "provider_egress_marker.json"
    marker = strict_json_file(path=repo_root / marker_relative)
    if type(marker) is not dict or set(marker) != _MARKER_FIELDS:
        _fail("Stage C-B egress marker fields differ")
    marker_body = {
        key: marker[key] for key in marker if key != "egress_marker_id"
    }
    execution_id = content_hash(value={
        "authorization_id": binding["authorization_id"],
        "measurement_cycle_id": binding["measurement_cycle_id"],
        "provider_request_body_sha256": binding[
            "provider_request_body_sha256"
        ],
    })
    try:
        parse_utc_timestamp(value=str(marker["egress_started_at_utc"]))
    except ValueError as error:
        raise StageCBPacketError("Stage C-B marker timestamp is invalid") from error
    if (
        marker["egress_marker_id"] != content_hash(value=marker_body)
        or marker["record_type"]
        != "TABLE_CONTEXT_MEASUREMENT_EGRESS_MARKER"
        or marker["measurement_cycle_id"] != binding["measurement_cycle_id"]
        or marker["authorization_id"] != binding["authorization_id"]
        or marker["execution_id"] != execution_id
        or marker["measurement_ordinal"] != MEASUREMENT_ORDINAL
        or marker["provider_request_body_sha256"]
        != plan["provider_request_body_sha256"]
        or marker["transport_kind"] != "REAL_MODEL_PROVIDER"
    ):
        _fail("Stage C-B egress marker binding differs")

    evidence_dir = cycle_dir / "evidence"
    response_dir = cycle_dir / "provider_responses"
    if (
        evidence_dir.is_symlink()
        or response_dir.is_symlink()
        or not evidence_dir.is_dir()
        or not response_dir.is_dir()
    ):
        _fail("Stage C-B terminal directories are unsafe")
    evidence_paths = list(evidence_dir.iterdir())
    response_paths = list(response_dir.iterdir())
    if (
        len(evidence_paths) != 1
        or len(response_paths) != 1
        or evidence_paths[0].is_symlink()
        or response_paths[0].is_symlink()
        or not evidence_paths[0].is_file()
        or not response_paths[0].is_file()
        or evidence_paths[0].suffix != ".json"
        or response_paths[0].suffix != ".bin"
    ):
        _fail("Stage C-B must contain exactly one evidence and response file")

    evidence = validate_table_context_measurement_evidence(
        evidence=strict_json_file(path=evidence_paths[0]),
    )
    evidence_digest = str(evidence["measurement_evidence_id"]).split(
        ":", maxsplit=1,
    )[1]
    response_bytes = response_paths[0].read_bytes()
    response_sha256 = "sha256:" + sha256_bytes(content=response_bytes)
    if (
        evidence_paths[0].name != evidence_digest + ".json"
        or response_paths[0].name
        != response_sha256.split(":", maxsplit=1)[1] + ".bin"
        or evidence["provider_response_sha256"] != response_sha256
    ):
        _fail("Stage C-B terminal content-addressed paths differ")

    try:
        provider_payload = strict_json_loads(
            text=response_bytes.decode("utf-8"),
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise StageCBPacketError("Provider response is not strict JSON") from error
    usage = provider_payload.get("usage") if type(provider_payload) is dict else None
    if type(usage) is not dict:
        _fail("Provider response lacks authoritative usage")
    prompt = _usage_int(
        usage=usage, names=("prompt_tokens", "input_tokens"), required=True,
    )
    completion = _usage_int(
        usage=usage,
        names=("completion_tokens", "output_tokens"),
        required=True,
    )
    total = _usage_int(
        usage=usage, names=("total_tokens",), required=True,
    )
    cache_hit = _usage_int(
        usage=usage, names=("prompt_cache_hit_tokens",), required=False,
    )
    cache_miss = _usage_int(
        usage=usage, names=("prompt_cache_miss_tokens",), required=False,
    )
    if (
        prompt is None
        or completion is None
        or total != prompt + completion
        or (
            cache_hit is not None
            and cache_miss is not None
            and cache_hit + cache_miss != prompt
        )
    ):
        _fail("Provider usage arithmetic differs")
    usage_hash = "sha256:" + sha256_bytes(
        content=canonical_json_bytes(value=usage),
    )
    ratio = format(
        (
            Decimal(int(plan["provider_request_body_bytes"]))
            / Decimal(prompt)
        ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN),
        "f",
    )
    expected_evidence = {
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_cycle_id": binding["measurement_cycle_id"],
        "measurement_ordinal": MEASUREMENT_ORDINAL,
        "authorization_id": binding["authorization_id"],
        "execution_id": execution_id,
        "provider_request_body_sha256": plan[
            "provider_request_body_sha256"
        ],
        "provider_response_sha256": response_sha256,
        "http_status": 200,
        "status": "COMPLETED",
        "transport_terminal_status": "SUCCEEDED",
        "actual_prompt_tokens": prompt,
        "actual_completion_tokens": completion,
        "actual_total_tokens": total,
        "prompt_cache_hit_tokens": cache_hit,
        "prompt_cache_miss_tokens": cache_miss,
        "usage_raw_field_hash": usage_hash,
        "estimated_input_tokens": plan["estimated_input_tokens"],
        "bytes_per_actual_prompt_token": ratio,
        "qualification_credit": False,
        "publication_eligible": False,
        "response_reuse_for_qualification": False,
        "retry_performed": False,
        "provider": plan["provider"],
        "model": plan["model"],
        "api": plan["api"],
        "real_model_provider_egress_count": 1,
        "paid_model_provider_call_count": 1,
        "real_SEC_egress_count": 0,
    }
    if any(evidence.get(key) != value for key, value in expected_evidence.items()):
        _fail("Stage C-B evidence differs from raw provider usage")
    if not evidence.get("provider_request_id"):
        _fail("Stage C-B provider request ID is absent")

    return {
        "measurement_plan_id": plan["measurement_plan_id"],
        "measurement_plan_path": (
            MEASUREMENT_PLAN_ROOT
            / (EXPECTED_PLAN_ID.split(":", maxsplit=1)[1] + ".json")
        ).as_posix(),
        "measurement_cycle_id": binding["measurement_cycle_id"],
        "authorization_id": binding["authorization_id"],
        "execution_id": execution_id,
        "egress_marker_id": marker["egress_marker_id"],
        "egress_marker_path": marker_relative.as_posix(),
        "egress_started_at_utc": marker["egress_started_at_utc"],
        "measurement_evidence_id": evidence["measurement_evidence_id"],
        "measurement_evidence_path": evidence_paths[0].relative_to(
            repo_root,
        ).as_posix(),
        "provider_request_body_sha256": plan[
            "provider_request_body_sha256"
        ],
        "provider_request_id": evidence["provider_request_id"],
        "provider_response_sha256": response_sha256,
        "provider_response_path": response_paths[0].relative_to(
            repo_root,
        ).as_posix(),
        "usage_raw_field_hash": usage_hash,
        "status": evidence["status"],
        "http_status": evidence["http_status"],
        "transport_terminal_status": evidence["transport_terminal_status"],
        "actual_prompt_tokens": prompt,
        "actual_completion_tokens": completion,
        "actual_total_tokens": total,
        "prompt_cache_hit_tokens": cache_hit,
        "prompt_cache_miss_tokens": cache_miss,
        "estimated_input_tokens": evidence["estimated_input_tokens"],
        "bytes_per_actual_prompt_token": evidence[
            "bytes_per_actual_prompt_token"
        ],
        "retry_performed": evidence["retry_performed"],
        "egress_counts": {
            "real_model_provider_egress_count": evidence[
                "real_model_provider_egress_count"
            ],
            "paid_model_provider_call_count": evidence[
                "paid_model_provider_call_count"
            ],
            "real_SEC_egress_count": evidence["real_SEC_egress_count"],
        },
    }


def _stage_c_a_packet_id(*, repo_root: Path) -> str:
    """Bind the preserved historical Stage C-A packet without re-signing it."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=STAGE_C_A_PACKET_POINTER,
        id_field="pointer_id",
    )
    packet = _content_record(
        repo_root=repo_root,
        relative=Path(str(pointer["packet_path"])),
        id_field="stage_c_a_packet_id",
    )
    if pointer["stage_c_a_packet_id"] != packet["stage_c_a_packet_id"]:
        _fail("Historical Stage C-A packet binding differs")
    return str(packet["stage_c_a_packet_id"])


def _packet_body(
    *, repo_root: Path, source_snapshot: Mapping[str, object],
) -> Dict[str, object]:
    """Build the answer-first Stage C-B terminal packet body."""
    _validate_authorized_commit(repo_root=repo_root)
    plan = _validate_plan(repo_root=repo_root)
    binding = _authorization_binding(plan=plan)
    terminal = _validate_terminal(
        repo_root=repo_root, plan=plan, binding=binding,
    )
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
        _fail("Stage C-B active/root state differs")
    semantic = benchmark["semantic"]
    run = benchmark["run"]
    return {
        "schema_version": 1,
        "record_type": "ISSUE_15_STAGE_C_B_MEASUREMENT_PACKET",
        "stage_c_b_status": (
            "TOKEN_MEASUREMENT_COMPLETED_FINANCIAL_EVIDENCE_BLOCKED"
        ),
        "authority": {
            "issue_number": 15,
            "pull_request_number": 20,
            "approval_review": dict(APPROVAL_REVIEW),
            "authorized_at_utc": AUTHORIZED_AT_UTC,
            "measurement_plan_id": plan["measurement_plan_id"],
            "measurement_cycle_id": binding["measurement_cycle_id"],
            "authorization_id": binding["authorization_id"],
            "historical_stage_c_a_packet_id": _stage_c_a_packet_id(
                repo_root=repo_root,
            ),
        },
        "measurement_terminal": terminal,
        "measurement_semantics": {
            "purpose": "ACTUAL_PROMPT_TOKEN_USAGE_ONLY",
            "family_id": plan["family_id"],
            "task_contract_id": plan["task_contract_id"],
            "source_company_id": plan["source_company_id"],
            "source_sha256": plan["source_sha256"],
            "serializer_version": plan[
                "table_payload_serialization_version"
            ],
            "ordinary_qualification_max_estimated_input_tokens": plan[
                "ordinary_qualification_max_estimated_input_tokens"
            ],
            "ordinary_qualification_remains_blocked": plan[
                "ordinary_qualification_remains_blocked"
            ],
            "qualification_credit": False,
            "qualification_evidence_eligible": False,
            "publication_eligible": False,
            "response_reuse_for_qualification": False,
            "authorization_permanently_consumed": True,
            "additional_measurement_egress_authorized": False,
        },
        "financial_evidence": {
            "financial_decision": "F3_NEED_MORE_EVIDENCE",
            "benchmark_receipt_id": semantic["benchmark_receipt_id"],
            "benchmark_run_receipt_id": run["run_receipt_id"],
            "status": semantic["status"],
            "completion_result": semantic["materialization"]["completed"],
            "peak_rss_bytes": run["peak_rss_bytes"],
            "wall_time_seconds": run["wall_time_seconds"],
            "canonical_json_bytes": semantic["materialization"][
                "canonical_json_bytes"
            ],
            "derived_asset_id": semantic["materialization"][
                "derived_asset_id"
            ],
            "blocking_reason": semantic["safety_ceilings"]["guard_status"],
        },
        "active_root_state": root,
        "source_snapshot": dict(source_snapshot),
        "STILL_UNAUTHORIZED": [
            "ADDITIONAL_REAL_TOKEN_MEASUREMENT",
            "LIVE_QUALIFICATION",
            "R3",
            "R4",
            "PRODUCTION_MAX_TOTAL_CELLS_CHANGE",
            "SHARDING",
            "SERIALIZER_CANDIDATE",
            "SELECTOR",
            "PUBLICATION",
        ],
        "BLOCKERS": ["JPM_RSS_GUARD_UNAVAILABLE"],
    }


def build_stage_c_b_packet(*, repo_root: Path) -> Dict[str, object]:
    """Build the packet from a fully staged post-measurement source candidate."""
    source = _candidate_source_snapshot(repo_root=repo_root)
    body = _packet_body(repo_root=repo_root, source_snapshot=source)
    return {**body, "stage_c_b_packet_id": content_hash(value=body)}


def write_stage_c_b_packet(*, repo_root: Path) -> Dict[str, object]:
    """Persist the content-addressed Stage C-B packet and current pointer."""
    packet = build_stage_c_b_packet(repo_root=repo_root)
    digest = str(packet["stage_c_b_packet_id"]).split(":", maxsplit=1)[1]
    packet_relative = PACKET_ROOT / (digest + ".json")
    packet_path = repo_root / packet_relative
    if packet_path.exists():
        if strict_json_file(path=packet_path) != packet:
            _fail("Stage C-B packet collision")
    else:
        atomic_write_json(path=packet_path, value=packet)
    pointer_body = {
        "schema_version": 1,
        "record_type": "ISSUE_15_STAGE_C_B_PACKET_POINTER",
        "stage_c_b_packet_id": packet["stage_c_b_packet_id"],
        "packet_path": packet_relative.as_posix(),
    }
    pointer = {**pointer_body, "pointer_id": content_hash(value=pointer_body)}
    atomic_write_json(path=repo_root / PACKET_POINTER, value=pointer)
    return {
        "stage_c_b_packet_id": packet["stage_c_b_packet_id"],
        "packet_path": packet_relative.as_posix(),
        "pointer_id": pointer["pointer_id"],
        "status": packet["stage_c_b_status"],
        "measurement_evidence_id": packet["measurement_terminal"][
            "measurement_evidence_id"
        ],
        "actual_prompt_tokens": packet["measurement_terminal"][
            "actual_prompt_tokens"
        ],
        "egress_counts": packet["measurement_terminal"]["egress_counts"],
        "blockers": packet["BLOCKERS"],
    }


def validate_stage_c_b_packet(*, repo_root: Path) -> Dict[str, object]:
    """Validate packet, terminal bytes, clean source overlay, and R2 root."""
    pointer = _content_record(
        repo_root=repo_root,
        relative=PACKET_POINTER,
        id_field="pointer_id",
    )
    packet = _content_record(
        repo_root=repo_root,
        relative=Path(str(pointer["packet_path"])),
        id_field="stage_c_b_packet_id",
    )
    if set(packet) != _PACKET_FIELDS:
        _fail("Stage C-B packet fields differ")
    if pointer["stage_c_b_packet_id"] != packet["stage_c_b_packet_id"]:
        _fail("Stage C-B pointer binding differs")
    source = capture_source_snapshot(workdir=repo_root)
    expected_source = packet["source_snapshot"]
    if (
        source.checkout_status != "GIT_CLEAN"
        or source.source_commit is None
        or source.tree_sha256
        != expected_source["source_input_tree_sha256"]
        or source.file_count != expected_source["source_file_count"]
    ):
        _fail("Stage C-B source overlay differs")
    _historical_r2_source_errors(repo_root=repo_root)
    rebuilt_body = _packet_body(
        repo_root=repo_root, source_snapshot=expected_source,
    )
    if packet != {
        **rebuilt_body,
        "stage_c_b_packet_id": content_hash(value=rebuilt_body),
    }:
        _fail("Stage C-B packet rebuild differs")
    return {
        "stage_c_b_packet_id": packet["stage_c_b_packet_id"],
        "source_commit": source.source_commit,
        "source_commit_equivalent_tree": (
            source.source_commit != expected_source["candidate_base_commit"]
        ),
        "status": packet["stage_c_b_status"],
        "measurement_evidence_id": packet["measurement_terminal"][
            "measurement_evidence_id"
        ],
        "actual_prompt_tokens": packet["measurement_terminal"][
            "actual_prompt_tokens"
        ],
        "egress_counts": packet["measurement_terminal"]["egress_counts"],
        "blockers": packet["BLOCKERS"],
    }
