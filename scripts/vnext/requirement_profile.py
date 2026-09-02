"""Load profile-driven Requirement snapshots without policy-content mirrors.

Historical Requirement adapters remain in :mod:`vnext.requirements`.  This
module owns the reusable safety layer for successor snapshots: strict files,
Decision chains, transfer classification, typed invariants, parent binding,
and explicit artifact Requirement identity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from .canonical import CanonicalError, content_hash, parse_utc_timestamp
from .canonical import sha256_file, strict_json_file


PROFILE_SEMANTIC_VERSION = "1"
PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V1"
EXPLICIT_ARTIFACT_GENERATION = "EXPLICIT_REQUIREMENT_V1"
LEGACY_ARTIFACT_GENERATION = "LEGACY_REQUIREMENT_HASHES_V1"
PROFILE_SNAPSHOT_FILES = {
    "CONTRACT.md",
    "baseline_manifest.json",
    "decision_register.json",
    "invariant_profile.json",
    "transfer_manifest.json",
}
PROFILE_BOUND_FILES = PROFILE_SNAPSHOT_FILES - {"baseline_manifest.json"}
TRANSFER_DISPOSITIONS = {
    "CARRY_FORWARD",
    "HISTORICAL_ONLY",
    "SUPERSEDED",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CONTENT_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
REQUIREMENT_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{2,63}")
DECISION_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9-]{1,63}")
INVARIANT_ID_PATTERN = re.compile(r"INV-[A-Z0-9-]{1,63}")
PUBLICATION_ID_PATTERN = re.compile(r"publication_[0-9a-f]{64}")
METRIC_ID_PATTERN = re.compile(r"[A-Z][0-9]{2}")


class RequirementProfileError(ValueError):
    """Report unsafe, ambiguous, or semantically invalid profile authority."""


def _exact_fields(
    *, value: Mapping[str, object], expected: set[str], label: str,
) -> None:
    """Require one mapping to expose exactly the named fields."""
    if set(value) != expected:
        raise RequirementProfileError("{} fields are not exact".format(label))


def _text(*, value: object, label: str) -> str:
    """Return one non-empty string or fail closed."""
    if type(value) is not str or not value:
        raise RequirementProfileError("{} must be non-empty text".format(label))
    return value


def _boolean(*, value: object, label: str) -> bool:
    """Return one exact JSON boolean."""
    if type(value) is not bool:
        raise RequirementProfileError("{} must be boolean".format(label))
    return value


def _integer(*, value: object, label: str, minimum: int = 0) -> int:
    """Return one bounded integer without accepting booleans."""
    if type(value) is not int or value < minimum:
        raise RequirementProfileError("{} is invalid".format(label))
    return value


def _string_list(
    *, value: object, label: str, allow_empty: bool = False,
) -> List[str]:
    """Return a sorted, unique string list."""
    if (
        type(value) is not list
        or (not allow_empty and not value)
        or any(type(item) is not str or not item for item in value)
        or value != sorted(set(value))
    ):
        raise RequirementProfileError("{} must be sorted unique text".format(label))
    return list(value)


def _mapping(*, value: object, label: str) -> Dict[str, object]:
    """Return an isolated mapping."""
    if type(value) is not dict:
        raise RequirementProfileError("{} must be an object".format(label))
    return dict(value)


def _regular_file(*, path: Path, label: str) -> Path:
    """Reject missing files and every symlink shape."""
    if path.is_symlink() or not path.is_file():
        raise RequirementProfileError("{} is missing or unsafe".format(label))
    return path


def read_requirement_object(*, path: Path) -> Dict[str, object]:
    """Read one strict regular JSON object."""
    _regular_file(path=path, label="Requirement JSON")
    try:
        parsed = strict_json_file(path=path)
    except (CanonicalError, OSError) as error:
        raise RequirementProfileError("Requirement JSON is invalid") from error
    if type(parsed) is not dict:
        raise RequirementProfileError("Requirement JSON root must be an object")
    return dict(parsed)


def decision_record_hash(*, decision: Mapping[str, object]) -> str:
    """Return the canonical identity used by a superseding Decision."""
    return content_hash(value=dict(decision))


def validate_decision_record(
    *, decision: Mapping[str, object]
) -> Dict[str, object]:
    """Validate one generic pending or terminal Decision record."""
    pending_fields = {
        "decision_id",
        "effect",
        "evidence",
        "required_choice_fields",
        "status",
    }
    if set(decision) == pending_fields:
        if decision["status"] != "PENDING_EXTERNAL_APPROVAL":
            raise RequirementProfileError("Pending Decision status is invalid")
        decision_id = _text(
            value=decision["decision_id"], label="Pending Decision decision_id"
        )
        if DECISION_ID_PATTERN.fullmatch(decision_id) is None:
            raise RequirementProfileError("Pending Decision identity is invalid")
        for field in ("effect", "evidence"):
            _text(value=decision[field], label="Pending Decision " + field)
        pending_choice_fields = decision["required_choice_fields"]
        if (
            type(pending_choice_fields) is not list
            or not pending_choice_fields
            or any(
                type(field) is not str or not field
                for field in pending_choice_fields
            )
            or len(pending_choice_fields) != len(set(pending_choice_fields))
        ):
            raise RequirementProfileError(
                "Pending Decision required fields are invalid"
            )
        return dict(decision)
    required = {
        "approved_at_utc",
        "approved_by",
        "choice",
        "decision_id",
        "evidence",
        "status",
        "supersedes_decision_id",
    }
    _exact_fields(value=decision, expected=required, label="Decision")
    decision_id = _text(value=decision["decision_id"], label="Decision id")
    if DECISION_ID_PATTERN.fullmatch(decision_id) is None:
        raise RequirementProfileError("Decision identity is invalid")
    for field in ("approved_at_utc", "approved_by", "evidence"):
        _text(value=decision[field], label="Decision " + field)
    try:
        parse_utc_timestamp(value=str(decision["approved_at_utc"]))
    except CanonicalError as error:
        raise RequirementProfileError("Decision timestamp must be UTC") from error
    if decision["status"] not in {"APPROVED", "REJECTED", "SUPERSEDED"}:
        raise RequirementProfileError("Decision status is invalid")
    if type(decision["choice"]) is not dict:
        raise RequirementProfileError("Decision choice must be an object")
    parent = decision["supersedes_decision_id"]
    if parent is not None and (
        type(parent) is not str
        or CONTENT_HASH_PATTERN.fullmatch(parent) is None
    ):
        raise RequirementProfileError("Decision supersedes identity is invalid")
    return dict(decision)


def _decision_parent(*, decision: Mapping[str, object]) -> Optional[str]:
    """Return the predecessor hash for a validated Decision record."""
    if decision["status"] == "PENDING_EXTERNAL_APPROVAL":
        return None
    parent = decision["supersedes_decision_id"]
    return None if parent is None else str(parent)


def resolve_decision_chains(
    *, decisions: Sequence[Mapping[str, object]]
) -> tuple[Dict[str, Dict[str, object]], Dict[str, List[Dict[str, object]]]]:
    """Resolve one non-forked, non-cyclic effective tip per Decision ID."""
    groups: Dict[str, List[Dict[str, object]]] = {}
    for candidate in decisions:
        decision = validate_decision_record(decision=candidate)
        groups.setdefault(str(decision["decision_id"]), []).append(decision)
    effective: Dict[str, Dict[str, object]] = {}
    chains: Dict[str, List[Dict[str, object]]] = {}
    for decision_id, records in groups.items():
        by_hash = {
            decision_record_hash(decision=record): record for record in records
        }
        if len(by_hash) != len(records):
            raise RequirementProfileError("Decision chain contains duplicate bytes")
        children: Dict[Optional[str], List[str]] = {}
        for record_hash, record in by_hash.items():
            parent = _decision_parent(decision=record)
            if parent is not None and parent not in by_hash:
                raise RequirementProfileError("Decision chain has a detached parent")
            children.setdefault(parent, []).append(record_hash)
        roots = children.get(None, [])
        if len(roots) != 1:
            raise RequirementProfileError("Decision chain must have one root")
        current = roots[0]
        visited: set[str] = set()
        ordered: List[Dict[str, object]] = []
        while True:
            if current in visited:
                raise RequirementProfileError("Decision chain contains a cycle")
            visited.add(current)
            ordered.append(by_hash[current])
            successors = children.get(current, [])
            if len(successors) > 1:
                raise RequirementProfileError(
                    "Parallel effective decisions fail closed"
                )
            if not successors:
                break
            current = successors[0]
        if len(visited) != len(records):
            raise RequirementProfileError("Decision chain is disconnected")
        tip = by_hash[current]
        if tip["status"] == "SUPERSEDED":
            raise RequirementProfileError("Effective decision cannot be SUPERSEDED")
        effective[decision_id] = tip
        chains[decision_id] = ordered
    return effective, chains


def _transport_retry_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    fields = {
        "actual_usage_required",
        "automatic_retry_count",
        "context_ceiling_tokens",
        "http_402_automatic_retry_count",
        "http_402_stops_batch",
        "http_402_stops_execution",
        "kind",
        "unknown_remote_outcome_retry_allowed",
    }
    _exact_fields(value=choice, expected=fields, label="Transport retry policy")
    if (
        _integer(
            value=choice["automatic_retry_count"],
            label="automatic retry count",
        )
        != 0
        or _integer(
            value=choice["http_402_automatic_retry_count"],
            label="HTTP 402 retry count",
        )
        != 0
        or _boolean(
            value=choice["unknown_remote_outcome_retry_allowed"],
            label="UNKNOWN retry flag",
        )
        or not _boolean(
            value=choice["http_402_stops_execution"],
            label="HTTP 402 execution stop",
        )
        or not _boolean(
            value=choice["http_402_stops_batch"],
            label="HTTP 402 batch stop",
        )
        or not _boolean(
            value=choice["actual_usage_required"],
            label="actual usage requirement",
        )
        or _integer(
            value=choice["context_ceiling_tokens"],
            label="context ceiling",
            minimum=1,
        )
        < 1
    ):
        raise RequirementProfileError("Transport retry safety invariant differs")
    return dict(choice)


def _ratchet_scope(*, choice: Mapping[str, object]) -> Dict[str, object]:
    fields = {
        "kind",
        "maximum_new_production_ratchets_per_pr",
        "metric_ids",
        "ratchet_id",
    }
    _exact_fields(value=choice, expected=fields, label="Ratchet scope")
    ratchet_id = _text(value=choice["ratchet_id"], label="ratchet id")
    metrics = _string_list(value=choice["metric_ids"], label="ratchet metrics")
    if (
        not ratchet_id.startswith("R")
        or any(METRIC_ID_PATTERN.fullmatch(metric_id) is None for metric_id in metrics)
        or _integer(
            value=choice["maximum_new_production_ratchets_per_pr"],
            label="ratchets per PR",
            minimum=1,
        )
        != 1
    ):
        raise RequirementProfileError("Ratchet scope invariant differs")
    return dict(choice)


def _live_call_bound(*, choice: Mapping[str, object]) -> Dict[str, object]:
    fields = {
        "hard_maximum_provider_calls",
        "historical_response_qualification_credit",
        "kind",
        "positive_fixture_classes",
        "ratchet_id",
        "response_reuse",
        "target_maximum_provider_calls",
        "target_minimum_provider_calls",
        "zero_call_fixture_classes",
    }
    _exact_fields(value=choice, expected=fields, label="Live call bound")
    minimum = _integer(
        value=choice["target_minimum_provider_calls"],
        label="target minimum calls",
    )
    maximum = _integer(
        value=choice["target_maximum_provider_calls"],
        label="target maximum calls",
        minimum=1,
    )
    hard = _integer(
        value=choice["hard_maximum_provider_calls"],
        label="hard maximum calls",
        minimum=1,
    )
    positive = set(_string_list(
        value=choice["positive_fixture_classes"],
        label="positive fixture classes",
    ))
    zero = set(_string_list(
        value=choice["zero_call_fixture_classes"],
        label="zero-call fixture classes",
    ))
    if (
        not minimum <= maximum <= hard
        or positive & zero
        or choice["historical_response_qualification_credit"] != "NONE"
        or choice["response_reuse"] != "NOT_AUTHORIZED"
    ):
        raise RequirementProfileError("Live call safety invariant differs")
    return dict(choice)


def _publication_predecessor(
    *, choice: Mapping[str, object]
) -> Dict[str, object]:
    fields = {
        "failure_active_publication",
        "immutable_read_back_required",
        "kind",
        "ratchet_id",
        "required_predecessor",
        "restore_required",
        "rollback_required",
    }
    _exact_fields(value=choice, expected=fields, label="Publication predecessor")
    predecessor = _text(
        value=choice["required_predecessor"], label="publication predecessor"
    )
    if (
        PUBLICATION_ID_PATTERN.fullmatch(predecessor) is None
        or choice["failure_active_publication"] != predecessor
        or not all(
            _boolean(value=choice[field], label=field)
            for field in (
                "immutable_read_back_required",
                "restore_required",
                "rollback_required",
            )
        )
    ):
        raise RequirementProfileError("Publication safety invariant differs")
    return dict(choice)


def _artifact_requirement_identity(
    *, choice: Mapping[str, object]
) -> Dict[str, object]:
    fields = {
        "generation",
        "kind",
        "legacy_requirement_ids",
        "required_artifact_types",
        "required_identity_fields",
        "successor_missing_identity_allowed",
    }
    _exact_fields(value=choice, expected=fields, label="Artifact identity policy")
    legacy = _string_list(
        value=choice["legacy_requirement_ids"],
        label="legacy requirement ids",
    )
    for requirement_id in legacy:
        if REQUIREMENT_ID_PATTERN.fullmatch(requirement_id) is None:
            raise RequirementProfileError("Legacy Requirement id is invalid")
    if (
        choice["generation"] != EXPLICIT_ARTIFACT_GENERATION
        or set(_string_list(
            value=choice["required_artifact_types"],
            label="identity artifact types",
        ))
        != {"PUBLICATION_MANIFEST", "RELEASE_PLAN", "RUN"}
        or set(_string_list(
            value=choice["required_identity_fields"],
            label="identity fields",
        ))
        != {
            "requirement_closure_hash",
            "requirement_hashes",
            "requirement_id",
        }
        or _boolean(
            value=choice["successor_missing_identity_allowed"],
            label="missing identity flag",
        )
    ):
        raise RequirementProfileError("Artifact identity invariant differs")
    return dict(choice)


def _historical_evidence_policy(
    *, choice: Mapping[str, object], requirement_id: str,
) -> Dict[str, object]:
    fields = {
        "archive_commit",
        "archive_ref",
        "classification",
        "current_execution_credit",
        "immutable_requirement_ids",
        "kind",
        "qualification_credit",
        "response_reuse",
    }
    _exact_fields(value=choice, expected=fields, label="Historical evidence policy")
    immutable = _string_list(
        value=choice["immutable_requirement_ids"],
        label="immutable requirement ids",
    )
    if (
        requirement_id in immutable
        or any(REQUIREMENT_ID_PATTERN.fullmatch(value) is None for value in immutable)
        or re.fullmatch(
            r"HISTORICAL_[A-Z0-9_]+_ONLY", str(choice["classification"])
        )
        is None
        or COMMIT_PATTERN.fullmatch(str(choice["archive_commit"])) is None
        or not str(choice["archive_ref"]).startswith("archive/")
        or choice["qualification_credit"] != "NONE"
        or choice["response_reuse"] != "NOT_AUTHORIZED"
        or choice["current_execution_credit"] != "NONE"
    ):
        raise RequirementProfileError("Historical evidence invariant differs")
    return dict(choice)


def _source_scope_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    fields = {
        "automatic_full_document_fallback",
        "forbidden_selector_classes",
        "kind",
        "maximum_continuous_windows",
        "minimum_continuous_windows",
        "positive_fixture_classes",
        "ratchet_id",
        "zero_call_fixture_classes",
    }
    _exact_fields(value=choice, expected=fields, label="Source scope policy")
    minimum = _integer(
        value=choice["minimum_continuous_windows"],
        label="minimum windows",
        minimum=1,
    )
    maximum = _integer(
        value=choice["maximum_continuous_windows"],
        label="maximum windows",
        minimum=1,
    )
    positive = set(_string_list(
        value=choice["positive_fixture_classes"],
        label="scope positive fixtures",
    ))
    zero = set(_string_list(
        value=choice["zero_call_fixture_classes"],
        label="scope zero-call fixtures",
    ))
    _string_list(
        value=choice["forbidden_selector_classes"],
        label="forbidden selector classes",
    )
    if (
        minimum > maximum
        or maximum > 2
        or positive & zero
        or _boolean(
            value=choice["automatic_full_document_fallback"],
            label="full document fallback",
        )
    ):
        raise RequirementProfileError("Source scope safety invariant differs")
    return dict(choice)


def _session_resource_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    fields = {
        "final_independent_disk_replays",
        "full_derived_asset_rebuilds_per_child_maximum",
        "full_parent_authority_constructions_per_session_maximum",
        "full_prior_run_replays_per_child_maximum",
        "full_source_materializations_per_session_maximum",
        "kind",
        "minimum_wall_time_improvement_factor",
        "offline_paid_calls",
        "offline_provider_calls",
        "offline_sec_calls",
        "source_issue_url",
    }
    _exact_fields(value=choice, expected=fields, label="Session resource policy")
    integer_values = {
        field: _integer(value=choice[field], label=field)
        for field in fields
        if field not in {
            "kind",
            "minimum_wall_time_improvement_factor",
            "source_issue_url",
        }
    }
    improvement = _integer(
        value=choice["minimum_wall_time_improvement_factor"],
        label="wall-time improvement",
        minimum=1,
    )
    if (
        integer_values["full_source_materializations_per_session_maximum"] > 1
        or integer_values[
            "full_parent_authority_constructions_per_session_maximum"
        ]
        > 1
        or integer_values["full_prior_run_replays_per_child_maximum"] != 0
        or integer_values[
            "full_derived_asset_rebuilds_per_child_maximum"
        ]
        != 0
        or integer_values["final_independent_disk_replays"] != 1
        or any(
            integer_values[field] != 0
            for field in (
                "offline_paid_calls",
                "offline_provider_calls",
                "offline_sec_calls",
            )
        )
        or improvement < 1
        or not str(choice["source_issue_url"]).startswith(
            "https://github.com/"
        )
    ):
        raise RequirementProfileError("Session resource invariant differs")
    return dict(choice)


def _delivery_separation_policy(
    *, choice: Mapping[str, object]
) -> Dict[str, object]:
    fields = {
        "implementation_and_live_release_prs_separate",
        "kind",
        "live_release_production_python_changes_allowed",
        "maximum_new_production_ratchets_per_pr",
        "planned_pr_sequence",
        "r5_metric_ids",
        "r6_scope_categories",
        "r4_start_requires_transition_merge",
        "rf_final_metric_count",
        "superseded_issue_close_status",
        "superseded_issue_numbers_after_transition_merge",
        "transition_allows_r4_implementation",
        "transition_paid_calls",
        "transition_provider_calls",
        "transition_sec_calls",
        "wb7_independent_pr",
    }
    _exact_fields(value=choice, expected=fields, label="Delivery separation policy")
    if (
        not _boolean(
            value=choice["implementation_and_live_release_prs_separate"],
            label="implementation/live separation",
        )
        or _boolean(
            value=choice["live_release_production_python_changes_allowed"],
            label="live release Python changes",
        )
        or _integer(
            value=choice["maximum_new_production_ratchets_per_pr"],
            label="ratchets per PR",
            minimum=1,
        )
        != 1
        or any(
            METRIC_ID_PATTERN.fullmatch(metric_id) is None
            for metric_id in _string_list(
                value=choice["r5_metric_ids"], label="R5 metric ids"
            )
        )
        or not _string_list(
            value=choice["r6_scope_categories"],
            label="R6 scope categories",
        )
        or _integer(
            value=choice["rf_final_metric_count"],
            label="Rf final metric count",
            minimum=1,
        )
        < 1
        or not _boolean(
            value=choice["wb7_independent_pr"],
            label="WB-7 independent PR",
        )
        or not _boolean(
            value=choice["r4_start_requires_transition_merge"],
            label="R4 transition prerequisite",
        )
        or _boolean(
            value=choice["transition_allows_r4_implementation"],
            label="transition R4 implementation",
        )
        or any(
            _integer(value=choice[field], label=field) != 0
            for field in (
                "transition_paid_calls",
                "transition_provider_calls",
                "transition_sec_calls",
            )
        )
    ):
        raise RequirementProfileError("Delivery separation invariant differs")
    sequence = choice["planned_pr_sequence"]
    if (
        type(sequence) is not list
        or not sequence
        or len(sequence) != len(set(sequence))
        or any(
            type(value) is not str
            or re.fullmatch(r"PR-[A-Z]", value) is None
            for value in sequence
        )
    ):
        raise RequirementProfileError("Delivery sequence invariant differs")
    issue_numbers = choice["superseded_issue_numbers_after_transition_merge"]
    if (
        type(issue_numbers) is not list
        or not issue_numbers
        or issue_numbers != sorted(set(issue_numbers))
        or any(type(value) is not int or value < 1 for value in issue_numbers)
        or re.fullmatch(
            r"SUPERSEDED_BY_ISSUE_[0-9]+",
            str(choice["superseded_issue_close_status"]),
        )
        is None
    ):
        raise RequirementProfileError("Superseded Issue policy differs")
    return dict(choice)


def _evidence_result_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    fields = {
        "dense_result_keys_required",
        "exact_locator_required",
        "immutable_source_binding_required",
        "kind",
        "mechanical_evidence_required",
        "raw_value_unit_period_scope_recovery_required",
        "result_closure_required",
        "review_required",
        "strict_compatibility_required",
    }
    _exact_fields(value=choice, expected=fields, label="Evidence result policy")
    if not all(
        _boolean(value=choice[field], label=field)
        for field in fields
        if field != "kind"
    ):
        raise RequirementProfileError("Evidence/result invariant differs")
    return dict(choice)


INVARIANT_EVALUATORS = {
    "ARTIFACT_REQUIREMENT_IDENTITY": _artifact_requirement_identity,
    "DELIVERY_SEPARATION_POLICY": _delivery_separation_policy,
    "EVIDENCE_RESULT_POLICY": _evidence_result_policy,
    "LIVE_CALL_BOUND": _live_call_bound,
    "PUBLICATION_PREDECESSOR": _publication_predecessor,
    "RATCHET_SCOPE": _ratchet_scope,
    "SESSION_RESOURCE_POLICY": _session_resource_policy,
    "SOURCE_SCOPE_POLICY": _source_scope_policy,
    "TRANSPORT_RETRY_POLICY": _transport_retry_policy,
}
SUPPORTED_INVARIANT_KINDS = set(INVARIANT_EVALUATORS) | {
    "HISTORICAL_EVIDENCE_POLICY"
}


def evaluate_invariant_profile(
    *, profile: Mapping[str, object], requirement_id: str,
    effective_decisions: Mapping[str, Mapping[str, object]],
) -> Dict[str, object]:
    """Execute the small closed set of typed successor invariants."""
    fields = {
        "invariants",
        "profile_semantic_version",
        "record_type",
        "requirement_id",
        "schema_version",
    }
    _exact_fields(value=profile, expected=fields, label="Invariant profile")
    if (
        profile["schema_version"] != 1
        or profile["record_type"] != "REQUIREMENT_INVARIANT_PROFILE"
        or profile["requirement_id"] != requirement_id
        or profile["profile_semantic_version"] != PROFILE_SEMANTIC_VERSION
        or type(profile["invariants"]) is not list
    ):
        raise RequirementProfileError("Invariant profile identity differs")
    entries = list(profile["invariants"])
    by_id: Dict[str, Dict[str, object]] = {}
    referenced: set[str] = set()
    for value in entries:
        entry = _mapping(value=value, label="Invariant entry")
        _exact_fields(
            value=entry,
            expected={"decision_id", "invariant_id"},
            label="Invariant entry",
        )
        invariant_id = _text(
            value=entry["invariant_id"], label="Invariant id"
        )
        decision_id = _text(value=entry["decision_id"], label="Decision id")
        if (
            INVARIANT_ID_PATTERN.fullmatch(invariant_id) is None
            or invariant_id in by_id
            or decision_id in referenced
            or decision_id not in effective_decisions
            or effective_decisions[decision_id]["status"] != "APPROVED"
        ):
            raise RequirementProfileError("Invariant decision binding differs")
        decision = effective_decisions[decision_id]
        choice = _mapping(value=decision["choice"], label="Invariant choice")
        kind = _text(value=choice.get("kind"), label="Invariant kind")
        if kind == "HISTORICAL_EVIDENCE_POLICY":
            normalized = _historical_evidence_policy(
                choice=choice, requirement_id=requirement_id,
            )
        else:
            evaluator = INVARIANT_EVALUATORS.get(kind)
            if evaluator is None:
                raise RequirementProfileError(
                    "Unknown invariant kind: {}".format(kind)
                )
            normalized = evaluator(choice=choice)
        by_id[invariant_id] = {
            "decision_id": decision_id,
            "decision_record_hash": decision_record_hash(decision=decision),
            "kind": kind,
            "value": normalized,
        }
        referenced.add(decision_id)
    if [entry["invariant_id"] for entry in entries] != sorted(by_id):
        raise RequirementProfileError("Invariant entries are not ordered")
    approved_ids = {
        decision_id
        for decision_id, decision in effective_decisions.items()
        if decision["status"] == "APPROVED"
    }
    if referenced != approved_ids:
        raise RequirementProfileError("Approved Decision lacks typed invariant")
    return {"by_invariant_id": by_id}


def _file_binding(*, value: object, label: str) -> Dict[str, object]:
    binding = _mapping(value=value, label=label)
    _exact_fields(
        value=binding, expected={"sha256", "size"}, label=label,
    )
    if (
        type(binding["sha256"]) is not str
        or SHA256_PATTERN.fullmatch(binding["sha256"]) is None
        or type(binding["size"]) is not int
        or binding["size"] < 0
    ):
        raise RequirementProfileError("{} is invalid".format(label))
    return binding


def _verify_bound_files(
    *, root: Path, bindings: object, expected_files: set[str], label: str,
) -> Dict[str, Dict[str, object]]:
    values = _mapping(value=bindings, label=label)
    if set(values) != expected_files:
        raise RequirementProfileError("{} file set differs".format(label))
    normalized: Dict[str, Dict[str, object]] = {}
    for relative in sorted(expected_files):
        if Path(relative).name != relative:
            raise RequirementProfileError("{} path is unsafe".format(label))
        binding = _file_binding(value=values[relative], label=label + " binding")
        path = _regular_file(path=root / relative, label=label + " file")
        if (
            binding["sha256"] != sha256_file(path=path)
            or binding["size"] != path.stat().st_size
        ):
            raise RequirementProfileError(
                "{} bytes differ: {}".format(label, relative)
            )
        normalized[relative] = binding
    return normalized


def _validate_transfer(
    *, transfer: Mapping[str, object], requirement_id: str,
    parent: Mapping[str, object], current_decisions: Mapping[str, object],
    parent_snapshot_dir: Path, parent_snapshot_files: Mapping[str, object],
) -> Dict[str, object]:
    fields = {
        "classification_counts",
        "dispositions",
        "historical_material",
        "parent_requirement_closure_hash",
        "parent_requirement_id",
        "parent_snapshot_binding_hash",
        "parent_snapshot_files",
        "record_type",
        "requirement_id",
        "schema_version",
    }
    _exact_fields(value=transfer, expected=fields, label="Transfer manifest")
    if (
        transfer["schema_version"] != 1
        or transfer["record_type"] != "REQUIREMENT_TRANSFER_MANIFEST"
        or transfer["requirement_id"] != requirement_id
        or transfer["parent_requirement_id"] != parent["requirement_id"]
        or transfer["parent_requirement_closure_hash"]
        != parent["requirement_closure_hash"]
        or transfer["parent_snapshot_files"] != parent_snapshot_files
        or transfer["parent_snapshot_binding_hash"]
        != content_hash(value=dict(parent_snapshot_files))
    ):
        raise RequirementProfileError("Transfer parent binding differs")
    _verify_bound_files(
        root=parent_snapshot_dir,
        bindings=transfer["parent_snapshot_files"],
        expected_files=set(parent_snapshot_files),
        label="Transfer parent snapshot",
    )
    raw_dispositions = transfer["dispositions"]
    if type(raw_dispositions) is not list:
        raise RequirementProfileError("Transfer dispositions must be an array")
    parent_decisions = parent["effective_decisions"]
    dispositions: Dict[str, Dict[str, object]] = {}
    counts = {value: 0 for value in sorted(TRANSFER_DISPOSITIONS)}
    for raw in raw_dispositions:
        row = _mapping(value=raw, label="Transfer disposition")
        _exact_fields(
            value=row,
            expected={
                "decision_id",
                "disposition",
                "parent_effective_record_hash",
                "rationale",
                "successor_decision_ids",
            },
            label="Transfer disposition",
        )
        decision_id = _text(value=row["decision_id"], label="parent decision id")
        successors = _string_list(
            value=row["successor_decision_ids"],
            label="successor decision ids",
            allow_empty=True,
        )
        if (
            decision_id in dispositions
            or decision_id not in parent_decisions
            or row["disposition"] not in TRANSFER_DISPOSITIONS
            or row["parent_effective_record_hash"]
            != decision_record_hash(decision=parent_decisions[decision_id])
            or any(value not in current_decisions for value in successors)
            or any(
                current_decisions[value]["status"] != "APPROVED"
                for value in successors
            )
            or (
                row["disposition"] != "HISTORICAL_ONLY"
                and not successors
            )
        ):
            raise RequirementProfileError("Transfer disposition differs")
        _text(value=row["rationale"], label="transfer rationale")
        dispositions[decision_id] = row
        counts[str(row["disposition"])] += 1
    if (
        set(dispositions) != set(parent_decisions)
        or [row["decision_id"] for row in raw_dispositions]
        != sorted(dispositions)
        or transfer["classification_counts"] != counts
    ):
        raise RequirementProfileError("Transfer classification is incomplete")
    historical = transfer["historical_material"]
    if type(historical) is not list or not historical:
        raise RequirementProfileError("Historical transfer material is absent")
    material_ids = []
    for raw in historical:
        row = _mapping(value=raw, label="Historical material")
        _exact_fields(
            value=row,
            expected={
                "archive_commit",
                "archive_ref",
                "current_execution_credit",
                "disposition",
                "material_id",
                "qualification_credit",
                "rationale",
                "response_reuse",
            },
            label="Historical material",
        )
        material_ids.append(_text(value=row["material_id"], label="material id"))
        if (
            row["disposition"] != "HISTORICAL_ONLY"
            or COMMIT_PATTERN.fullmatch(str(row["archive_commit"])) is None
            or not str(row["archive_ref"]).startswith("archive/")
            or row["qualification_credit"] != "NONE"
            or row["current_execution_credit"] != "NONE"
            or row["response_reuse"] != "NOT_AUTHORIZED"
        ):
            raise RequirementProfileError("Historical material policy differs")
        _text(value=row["rationale"], label="historical rationale")
    if material_ids != sorted(set(material_ids)):
        raise RequirementProfileError("Historical material identities differ")
    return {"dispositions": dispositions, "historical_material": historical}


def _validate_baseline(
    *, baseline: Mapping[str, object], snapshot_dir: Path,
) -> Dict[str, object]:
    fields = {
        "active_publication",
        "artifact_requirement_generation",
        "contract_revision",
        "created_at_utc",
        "historical_archive",
        "issue",
        "parent",
        "record_type",
        "repository",
        "requirement_generation",
        "requirement_id",
        "schema_version",
        "snapshot_files",
        "source_input_role",
        "validator",
    }
    _exact_fields(value=baseline, expected=fields, label="Profile baseline")
    requirement_id = _text(
        value=baseline["requirement_id"], label="Requirement id"
    )
    if (
        baseline["schema_version"] != 1
        or baseline["record_type"] != "REQUIREMENT_BASELINE_MANIFEST"
        or REQUIREMENT_ID_PATTERN.fullmatch(requirement_id) is None
        or baseline["requirement_generation"] != PROFILE_REQUIREMENT_GENERATION
        or baseline["artifact_requirement_generation"]
        != EXPLICIT_ARTIFACT_GENERATION
        or baseline["source_input_role"] != "SUCCESSOR_REQUIREMENT_AUTHORITY"
    ):
        raise RequirementProfileError("Profile baseline identity differs")
    _text(value=baseline["contract_revision"], label="contract revision")
    try:
        parse_utc_timestamp(value=str(baseline["created_at_utc"]))
    except CanonicalError as error:
        raise RequirementProfileError("Baseline timestamp must be UTC") from error
    issue = _mapping(value=baseline["issue"], label="Issue binding")
    _exact_fields(
        value=issue,
        expected={
            "identifier_comment_sha256",
            "identifier_comment_url",
            "number",
            "tracking_body_sha256",
            "tracking_body_size",
            "url",
        },
        label="Issue binding",
    )
    issue_number = _integer(
        value=issue["number"], label="Issue number", minimum=1,
    )
    repository = _mapping(value=baseline["repository"], label="repository binding")
    _exact_fields(
        value=repository,
        expected={"commit", "identity", "tree"},
        label="repository binding",
    )
    repository_identity = _text(
        value=repository["identity"], label="repository identity"
    )
    issue_url = "https://github.com/{}/issues/{}".format(
        repository_identity, issue_number,
    )
    if (
        requirement_id != "issue_{}_v1".format(issue_number)
        or issue["url"] != issue_url
        or SHA256_PATTERN.fullmatch(str(issue["tracking_body_sha256"])) is None
        or type(issue["tracking_body_size"]) is not int
        or issue["tracking_body_size"] <= 0
        or SHA256_PATTERN.fullmatch(str(issue["identifier_comment_sha256"])) is None
        or not str(issue["identifier_comment_url"]).startswith(
            issue_url + "#issuecomment-"
        )
    ):
        raise RequirementProfileError("Issue binding differs")
    if (
        "/" not in repository_identity
        or COMMIT_PATTERN.fullmatch(str(repository["commit"])) is None
        or COMMIT_PATTERN.fullmatch(str(repository["tree"])) is None
    ):
        raise RequirementProfileError("Repository baseline differs")
    parent = _mapping(value=baseline["parent"], label="parent binding")
    _exact_fields(
        value=parent,
        expected={
            "hashes",
            "requirement_closure_hash",
            "requirement_id",
            "snapshot_binding_hash",
            "snapshot_files",
            "snapshot_git_tree",
        },
        label="parent binding",
    )
    _text(value=parent["requirement_id"], label="parent requirement id")
    if (
        CONTENT_HASH_PATTERN.fullmatch(str(parent["requirement_closure_hash"]))
        is None
        or COMMIT_PATTERN.fullmatch(str(parent["snapshot_git_tree"])) is None
        or CONTENT_HASH_PATTERN.fullmatch(str(parent["snapshot_binding_hash"]))
        is None
        or type(parent["hashes"]) is not dict
        or type(parent["snapshot_files"]) is not dict
    ):
        raise RequirementProfileError("Parent binding identity differs")
    active = _mapping(
        value=baseline["active_publication"], label="active publication"
    )
    _exact_fields(
        value=active,
        expected={
            "bundle_manifest_sha256",
            "predecessor_publication_id",
            "publication_id",
            "status",
        },
        label="active publication",
    )
    if (
        active["status"] != "PASSED"
        or PUBLICATION_ID_PATTERN.fullmatch(str(active["publication_id"])) is None
        or PUBLICATION_ID_PATTERN.fullmatch(
            str(active["predecessor_publication_id"])
        )
        is None
        or SHA256_PATTERN.fullmatch(str(active["bundle_manifest_sha256"])) is None
    ):
        raise RequirementProfileError("Active publication baseline differs")
    archive = _mapping(value=baseline["historical_archive"], label="archive")
    _exact_fields(
        value=archive,
        expected={
            "commit",
            "qualification_credit",
            "ref",
            "response_reuse",
            "status",
        },
        label="archive",
    )
    if (
        re.fullmatch(r"HISTORICAL_[A-Z0-9_]+_ONLY", str(archive["status"]))
        is None
        or COMMIT_PATTERN.fullmatch(str(archive["commit"])) is None
        or not str(archive["ref"]).startswith("archive/")
        or archive["qualification_credit"] != "NONE"
        or archive["response_reuse"] != "NOT_AUTHORIZED"
    ):
        raise RequirementProfileError("Historical archive baseline differs")
    validator = _mapping(value=baseline["validator"], label="validator")
    _exact_fields(
        value=validator,
        expected={"path", "semantic_version", "sha256"},
        label="validator",
    )
    if (
        validator["path"] != "scripts/vnext/requirement_profile.py"
        or validator["semantic_version"] != PROFILE_SEMANTIC_VERSION
        or validator["sha256"] != sha256_file(path=Path(__file__).resolve())
    ):
        raise RequirementProfileError("Generic validator identity differs")
    _verify_bound_files(
        root=snapshot_dir,
        bindings=baseline["snapshot_files"],
        expected_files=PROFILE_BOUND_FILES,
        label="Profile snapshot",
    )
    return dict(baseline)


def load_profile_requirement_snapshot(
    *, snapshot_dir: Path,
    parent_loader: Callable[..., Mapping[str, object]],
) -> Dict[str, object]:
    """Load one profile-driven successor Requirement Snapshot."""
    if snapshot_dir.is_symlink() or not snapshot_dir.is_dir():
        raise RequirementProfileError("Requirement snapshot directory is unsafe")
    entries = list(snapshot_dir.iterdir())
    if (
        {path.name for path in entries} != PROFILE_SNAPSHOT_FILES
        or any(path.is_symlink() or not path.is_file() for path in entries)
    ):
        raise RequirementProfileError("Profile Requirement file set differs")
    baseline = _validate_baseline(
        baseline=read_requirement_object(
            path=snapshot_dir / "baseline_manifest.json"
        ),
        snapshot_dir=snapshot_dir,
    )
    requirement_id = str(baseline["requirement_id"])
    parent_binding = baseline["parent"]
    parent_dir = snapshot_dir.parent / str(parent_binding["requirement_id"])
    if parent_dir.is_symlink() or not parent_dir.is_dir():
        raise RequirementProfileError("Parent Requirement directory is unsafe")
    try:
        parent = dict(parent_loader(snapshot_dir=parent_dir))
    except ValueError as error:
        raise RequirementProfileError("Parent Requirement is invalid") from error
    if (
        parent["requirement_id"] != parent_binding["requirement_id"]
        or parent["requirement_closure_hash"]
        != parent_binding["requirement_closure_hash"]
        or parent["hashes"] != parent_binding["hashes"]
        or parent_binding["snapshot_binding_hash"]
        != content_hash(value=dict(parent_binding["snapshot_files"]))
    ):
        raise RequirementProfileError("Parent Requirement closure differs")
    _verify_bound_files(
        root=parent_dir,
        bindings=parent_binding["snapshot_files"],
        expected_files=set(parent_binding["snapshot_files"]),
        label="Parent snapshot",
    )

    register = read_requirement_object(
        path=snapshot_dir / "decision_register.json"
    )
    _exact_fields(
        value=register,
        expected={
            "decisions",
            "issue_contract_revision",
            "pending_decisions",
            "record_type",
            "requirement_id",
            "schema_version",
        },
        label="Profile Decision Register",
    )
    if (
        register["schema_version"] != 2
        or register["record_type"] != "REQUIREMENT_DECISION_REGISTER"
        or register["requirement_id"] != requirement_id
        or register["issue_contract_revision"] != baseline["contract_revision"]
        or type(register["decisions"]) is not list
        or type(register["pending_decisions"]) is not list
    ):
        raise RequirementProfileError("Profile Decision Register differs")
    decision_records = list(register["decisions"])
    decision_records.extend(register["pending_decisions"])
    decisions, chains = resolve_decision_chains(decisions=decision_records)
    pending_ids = sorted(
        decision_id
        for decision_id, decision in decisions.items()
        if decision["status"] == "PENDING_EXTERNAL_APPROVAL"
    )

    profile = read_requirement_object(
        path=snapshot_dir / "invariant_profile.json"
    )
    evaluated = evaluate_invariant_profile(
        profile=profile,
        requirement_id=requirement_id,
        effective_decisions=decisions,
    )
    transfer = read_requirement_object(
        path=snapshot_dir / "transfer_manifest.json"
    )
    transfer_result = _validate_transfer(
        transfer=transfer,
        requirement_id=requirement_id,
        parent=parent,
        current_decisions=decisions,
        parent_snapshot_dir=parent_dir,
        parent_snapshot_files=parent_binding["snapshot_files"],
    )

    evaluated_rows = list(evaluated["by_invariant_id"].values())
    values_by_kind = {
        value["kind"]: value["value"] for value in evaluated_rows
    }
    if (
        set(values_by_kind) != SUPPORTED_INVARIANT_KINDS
        or len(values_by_kind) != len(evaluated_rows)
    ):
        raise RequirementProfileError("Typed invariant kind set differs")
    publication = values_by_kind["PUBLICATION_PREDECESSOR"]
    historical = values_by_kind["HISTORICAL_EVIDENCE_POLICY"]
    artifact_identity = values_by_kind["ARTIFACT_REQUIREMENT_IDENTITY"]
    if (
        publication["required_predecessor"]
        != baseline["active_publication"]["publication_id"]
        or historical["archive_ref"] != baseline["historical_archive"]["ref"]
        or historical["archive_commit"]
        != baseline["historical_archive"]["commit"]
        or historical["classification"]
        != baseline["historical_archive"]["status"]
        or artifact_identity["generation"]
        != baseline["artifact_requirement_generation"]
    ):
        raise RequirementProfileError("Baseline invariant binding differs")

    hashes = {
        "baseline_sha256": sha256_file(
            path=snapshot_dir / "baseline_manifest.json"
        ),
        "contract_sha256": sha256_file(path=snapshot_dir / "CONTRACT.md"),
        "decision_register_sha256": sha256_file(
            path=snapshot_dir / "decision_register.json"
        ),
        "invariant_profile_sha256": sha256_file(
            path=snapshot_dir / "invariant_profile.json"
        ),
        "parent_requirement_closure_hash": parent[
            "requirement_closure_hash"
        ],
        "transfer_manifest_sha256": sha256_file(
            path=snapshot_dir / "transfer_manifest.json"
        ),
        "validator_sha256": baseline["validator"]["sha256"],
    }
    return {
        "artifact_requirement_generation": baseline[
            "artifact_requirement_generation"
        ],
        "baseline": baseline,
        "decision_chains": chains,
        "effective_decisions": decisions,
        "evaluated_invariants": evaluated,
        "hashes": hashes,
        "issue_contract_revision": register["issue_contract_revision"],
        "parent_requirement_closure_hash": parent[
            "requirement_closure_hash"
        ],
        "parent_requirement_id": parent["requirement_id"],
        "pending_decision_ids": pending_ids,
        "requirement_closure_hash": content_hash(value=hashes),
        "requirement_generation": PROFILE_REQUIREMENT_GENERATION,
        "requirement_id": requirement_id,
        "transfer": transfer_result,
    }


def validate_artifact_requirement_identity(
    *, artifact: Mapping[str, object], requirement: Mapping[str, object]
) -> Dict[str, object]:
    """Apply generation-specific Requirement identity to one artifact.

    Legacy artifacts remain byte-compatible and are accepted only under a
    legacy Requirement adapter.  A profile-driven successor requires all
    three explicit identity fields; missing fields cannot select legacy mode.
    """
    record_type = _text(value=artifact.get("record_type"), label="artifact type")
    generation = requirement.get(
        "artifact_requirement_generation", LEGACY_ARTIFACT_GENERATION,
    )
    explicit_fields = {
        "requirement_closure_hash",
        "requirement_hashes",
        "requirement_id",
    }
    if generation == LEGACY_ARTIFACT_GENERATION:
        if {"requirement_closure_hash", "requirement_id"} & set(artifact):
            raise RequirementProfileError(
                "Legacy artifact contains successor Requirement identity"
            )
        hashes = artifact.get("requirement_hashes")
        if type(hashes) is not dict or not hashes:
            raise RequirementProfileError("Legacy artifact hashes are invalid")
        return {
            "generation": LEGACY_ARTIFACT_GENERATION,
            "record_type": record_type,
        }
    if generation != EXPLICIT_ARTIFACT_GENERATION:
        raise RequirementProfileError("Artifact Requirement generation is unknown")
    if record_type not in {"PUBLICATION_MANIFEST", "RELEASE_PLAN", "RUN"}:
        raise RequirementProfileError("Successor artifact type is unsupported")
    missing = explicit_fields - set(artifact)
    if missing:
        raise RequirementProfileError("Successor artifact Requirement identity is missing")
    if (
        artifact["requirement_id"] != requirement["requirement_id"]
        or artifact["requirement_closure_hash"]
        != requirement["requirement_closure_hash"]
        or artifact["requirement_hashes"] != requirement["hashes"]
    ):
        raise RequirementProfileError("Successor artifact Requirement identity differs")
    return {
        "generation": EXPLICIT_ARTIFACT_GENERATION,
        "record_type": record_type,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_id": requirement["requirement_id"],
    }
