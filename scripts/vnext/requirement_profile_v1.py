"""Immutable PROFILE_DRIVEN_V1 engine; retain this file for historical replay.

Historical Requirement adapters remain in :mod:`vnext.requirements`.  This
module owns the reusable safety layer for successor snapshots: strict files,
Decision chains, transfer classification, typed invariants, parent binding,
and explicit artifact Requirement identity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from .canonical import CanonicalError, SEMANTIC_VERSIONS, content_hash
from .canonical import parse_utc_timestamp, sha256_bytes, sha256_file
from .canonical import strict_json_file, strict_json_loads


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
SUCCESSOR_RECORD_TYPES = {
    "SUCCESSOR_RUN": "RUN",
    "SUCCESSOR_RELEASE_PLAN": "RELEASE_PLAN",
    "SUCCESSOR_PUBLICATION_MANIFEST": "PUBLICATION_MANIFEST",
}
R4_METRIC_IDS = {"A03", "A04", "A09", "A11", "A12", "A13"}
POSITIVE_FIXTURE_CLASSES = {"POSITIVE_PRODUCTION", "POSITIVE_ALTERNATE_LAYOUT"}
FORBIDDEN_SELECTOR_CLASSES = {
    "AI_SELECTOR",
    "EMBEDDING_FUZZY_TOP_K_SELECTOR",
    "LITERAL_ONLY_SELECTOR",
    "RUNTIME_TOC_GUESSER",
    "SPARSE_RANKER",
}
REQUIRED_ZERO_CALL_CLASSES = {
    "NEGATIVE_EXPECTED",
    "NOT_APPLICABLE",
    "QUALITATIVE_ONLY",
    "AMBIGUOUS_EXCLUDED",
}
SOURCE_SCOPE_BINDING_FIELDS = {
    "source_sha256",
    "full_derived_asset_id",
    "task_contract_hash",
    "ordered_table_ids",
    "ordered_grid_hashes",
}
SCOPED_INVARIANT_KINDS = {
    "RATCHET_SCOPE",
    "LIVE_CALL_BOUND",
    "PUBLICATION_PREDECESSOR",
    "SOURCE_SCOPE_POLICY",
}


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


def _string_list(*, value: object, label: str, allow_empty: bool = False,) -> List[str]:
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


def _ordered_text_list(*, value: object, label: str) -> List[str]:
    if (
        type(value) is not list
        or not value
        or any(type(item) is not str or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise RequirementProfileError(label + " must be unique text")
    return list(value)


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


def validate_decision_record(*, decision: Mapping[str, object]) -> Dict[str, object]:
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
                type(field) is not str or not field for field in pending_choice_fields
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
    if "policy_provenance" in decision:
        required.add("policy_provenance")
        _mapping(value=decision["policy_provenance"], label="Policy provenance")
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
        type(parent) is not str or CONTENT_HASH_PATTERN.fullmatch(parent) is None
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
        by_hash = {decision_record_hash(decision=record): record for record in records}
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
        _integer(value=choice["automatic_retry_count"], label="automatic retry count",)
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
            value=choice["http_402_stops_execution"], label="HTTP 402 execution stop",
        )
        or not _boolean(
            value=choice["http_402_stops_batch"], label="HTTP 402 batch stop",
        )
        or not _boolean(
            value=choice["actual_usage_required"], label="actual usage requirement",
        )
        or _integer(
            value=choice["context_ceiling_tokens"], label="context ceiling", minimum=1,
        )
        != 200000
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
        or (ratchet_id == "R4" and set(metrics) != R4_METRIC_IDS)
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
        value=choice["target_minimum_provider_calls"], label="target minimum calls",
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
    positive = set(
        _string_list(
            value=choice["positive_fixture_classes"], label="positive fixture classes",
        )
    )
    zero = set(
        _string_list(
            value=choice["zero_call_fixture_classes"],
            label="zero-call fixture classes",
        )
    )
    if (
        not 12 <= minimum <= maximum <= 18
        or not maximum <= hard <= 24
        or positive & zero
        or positive != POSITIVE_FIXTURE_CLASSES
        or not REQUIRED_ZERO_CALL_CLASSES.issubset(zero)
        or choice["historical_response_qualification_credit"] != "NONE"
        or choice["response_reuse"] != "NOT_AUTHORIZED"
    ):
        raise RequirementProfileError("Live call safety invariant differs")
    return dict(choice)


def _publication_predecessor(*, choice: Mapping[str, object]) -> Dict[str, object]:
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
        value=choice["legacy_requirement_ids"], label="legacy requirement ids",
    )
    for requirement_id in legacy:
        if REQUIREMENT_ID_PATTERN.fullmatch(requirement_id) is None:
            raise RequirementProfileError("Legacy Requirement id is invalid")
    if (
        choice["generation"] != EXPLICIT_ARTIFACT_GENERATION
        or set(
            _string_list(
                value=choice["required_artifact_types"],
                label="identity artifact types",
            )
        )
        != {"PUBLICATION_MANIFEST", "RELEASE_PLAN", "RUN"}
        or set(
            _string_list(
                value=choice["required_identity_fields"], label="identity fields",
            )
        )
        != {"requirement_closure_hash", "requirement_hashes", "requirement_id",}
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
        value=choice["immutable_requirement_ids"], label="immutable requirement ids",
    )
    if (
        requirement_id in immutable
        or any(REQUIREMENT_ID_PATTERN.fullmatch(value) is None for value in immutable)
        or re.fullmatch(r"HISTORICAL_[A-Z0-9_]+_ONLY", str(choice["classification"]))
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
        "required_manifest_binding_fields",
        "zero_call_fixture_classes",
    }
    _exact_fields(value=choice, expected=fields, label="Source scope policy")
    minimum = _integer(
        value=choice["minimum_continuous_windows"], label="minimum windows", minimum=1,
    )
    maximum = _integer(
        value=choice["maximum_continuous_windows"], label="maximum windows", minimum=1,
    )
    positive = set(
        _string_list(
            value=choice["positive_fixture_classes"], label="scope positive fixtures",
        )
    )
    zero = set(
        _string_list(
            value=choice["zero_call_fixture_classes"], label="scope zero-call fixtures",
        )
    )
    forbidden_selectors = set(
        _string_list(
            value=choice["forbidden_selector_classes"],
            label="forbidden selector classes",
        )
    )
    if (
        minimum > maximum
        or maximum > 2
        or positive & zero
        or positive != POSITIVE_FIXTURE_CLASSES
        or not FORBIDDEN_SELECTOR_CLASSES.issubset(forbidden_selectors)
        or not REQUIRED_ZERO_CALL_CLASSES.issubset(zero)
        or set(
            _string_list(
                value=choice["required_manifest_binding_fields"],
                label="SourceScopeManifest binding fields",
            )
        )
        != SOURCE_SCOPE_BINDING_FIELDS
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
        if field
        not in {"kind", "minimum_wall_time_improvement_factor", "source_issue_url",}
    }
    improvement = _integer(
        value=choice["minimum_wall_time_improvement_factor"],
        label="wall-time improvement",
        minimum=1,
    )
    if (
        integer_values["full_source_materializations_per_session_maximum"] > 1
        or integer_values["full_parent_authority_constructions_per_session_maximum"] > 1
        or integer_values["full_prior_run_replays_per_child_maximum"] != 0
        or integer_values["full_derived_asset_rebuilds_per_child_maximum"] != 0
        or integer_values["final_independent_disk_replays"] != 1
        or any(
            integer_values[field] != 0
            for field in (
                "offline_paid_calls",
                "offline_provider_calls",
                "offline_sec_calls",
            )
        )
        or improvement < 10
        or not str(choice["source_issue_url"]).startswith("https://github.com/")
    ):
        raise RequirementProfileError("Session resource invariant differs")
    return dict(choice)


def _delivery_separation_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
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
            value=choice["r6_scope_categories"], label="R6 scope categories",
        )
        or _integer(
            value=choice["rf_final_metric_count"],
            label="Rf final metric count",
            minimum=1,
        )
        < 1
        or not _boolean(
            value=choice["wb7_independent_pr"], label="WB-7 independent PR",
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
            type(value) is not str or re.fullmatch(r"PR-[A-Z]", value) is None
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
            r"SUPERSEDED_BY_ISSUE_[0-9]+", str(choice["superseded_issue_close_status"]),
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


def _provider_transport_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    """Preserve the complete transport claim, not merely retry policy."""
    _exact_fields(
        value=choice,
        expected={
            "kind",
            "provider",
            "model",
            "api",
            "endpoint_host",
            "region",
            "retention",
            "data_use",
            "timeout_seconds",
            "retry_count",
            "maximum_payload_bytes",
            "filing_egress_policy",
        },
        label="Provider transport policy",
    )
    for field in (
        "provider",
        "model",
        "api",
        "endpoint_host",
        "region",
        "retention",
        "data_use",
        "filing_egress_policy",
    ):
        _text(value=choice[field], label="Provider " + field)
    if (
        not 0 < _integer(value=choice["timeout_seconds"], label="timeout") <= 120
        or not 0
        < _integer(value=choice["maximum_payload_bytes"], label="payload ceiling")
        <= 8388608
        or _integer(value=choice["retry_count"], label="provider retry") != 0
    ):
        raise RequirementProfileError("Provider transport safety bound differs")
    return dict(choice)


def _security_boundary_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    _exact_fields(
        value=choice,
        expected={"kind", "security_claim", "same_process_strong_sandbox_claim",},
        label="Security boundary policy",
    )
    if choice[
        "security_claim"
    ] != "DEPENDENCY_CALL_GRAPH_EGRESS_AND_WRITE_CONSTRAINTS_ONLY" or _boolean(
        value=choice["same_process_strong_sandbox_claim"],
        label="same-process sandbox claim",
    ):
        raise RequirementProfileError("Security boundary claim differs")
    return dict(choice)


def _test_policy(*, choice: Mapping[str, object]) -> Dict[str, object]:
    _exact_fields(
        value=choice,
        expected={
            "kind",
            "test_execution_policy",
            "applies_to",
            "required_fast_command",
            "per_case_timeout_seconds",
            "recorded_gate_timeout_seconds",
            "prohibited_required_test_classes",
            "required_short_deterministic_invariants",
            "evidence_tier",
            "may_claim_ci_pass",
        },
        label="Test policy",
    )
    if (
        choice["required_fast_command"] != "python3 tools/run_fast_tests.py --jobs 4"
        or not 0
        < _integer(value=choice["per_case_timeout_seconds"], label="fast timeout")
        <= 30
        or not 0
        < _integer(
            value=choice["recorded_gate_timeout_seconds"], label="recorded timeout"
        )
        <= 60
        or choice["evidence_tier"] != "FAST_LOCAL_ONLY"
        or _boolean(value=choice["may_claim_ci_pass"], label="local CI claim")
        or not {"development", "pull_request", "final_acceptance"}.issubset(
            set(_ordered_text_list(value=choice["applies_to"], label="test phases"))
        )
        or not {
            "broad_repository_regression",
            "isolated_repository_or_worktree",
            "long_running_serial_suite",
        }.issubset(
            set(
                _ordered_text_list(
                    value=choice["prohibited_required_test_classes"],
                    label="fast prohibited test classes",
                )
            )
        )
    ):
        raise RequirementProfileError("Test policy safety bound differs")
    _text(value=choice["test_execution_policy"], label="test execution policy")
    _ordered_text_list(
        value=choice["required_short_deterministic_invariants"],
        label="short deterministic invariants",
    )
    return dict(choice)


def _parent_policy_carry_forward(*, choice: Mapping[str, object]) -> Dict[str, object]:
    """Keep inherited semantic values by immutable reference, not Python mirrors."""
    _exact_fields(
        value=choice,
        expected={"kind", "obligations"},
        label="Inherited semantic obligations",
    )
    rows = choice["obligations"]
    if type(rows) is not list or not rows:
        raise RequirementProfileError("Inherited obligations are absent")
    keys = []
    for raw in rows:
        row = _mapping(value=raw, label="Inherited obligation")
        _exact_fields(
            value=row,
            expected={"decision_id", "source_path", "source_value_hash",},
            label="Inherited obligation",
        )
        keys.append((str(row["decision_id"]), str(row["source_path"])))
        if CONTENT_HASH_PATTERN.fullmatch(str(row["source_value_hash"])) is None:
            raise RequirementProfileError("Inherited obligation hash is invalid")
    if keys != sorted(set(keys)):
        raise RequirementProfileError("Inherited obligations are duplicated")
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
    "PROVIDER_TRANSPORT_POLICY": _provider_transport_policy,
    "SECURITY_BOUNDARY_POLICY": _security_boundary_policy,
    "TEST_POLICY": _test_policy,
    "PARENT_POLICY_CARRY_FORWARD": _parent_policy_carry_forward,
}
SUPPORTED_INVARIANT_KINDS = set(INVARIANT_EVALUATORS) | {"HISTORICAL_EVIDENCE_POLICY"}


def evaluate_invariant_profile(
    *,
    profile: Mapping[str, object],
    requirement_id: str,
    effective_decisions: Mapping[str, Mapping[str, object]],
    semantic_version: str = PROFILE_SEMANTIC_VERSION,
    evaluators: Optional[Mapping[str, Callable]] = None,
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
        or profile["profile_semantic_version"] != semantic_version
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
        invariant_id = _text(value=entry["invariant_id"], label="Invariant id")
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
            evaluator = (
                INVARIANT_EVALUATORS if evaluators is None else evaluators
            ).get(kind)
            if evaluator is None:
                raise RequirementProfileError("Unknown invariant kind: {}".format(kind))
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
            raise RequirementProfileError("{} bytes differ: {}".format(label, relative))
        normalized[relative] = binding
    return normalized


def choice_fragments(*, value: object, path: str = "") -> Dict[str, object]:
    """Enumerate every leaf obligation; paths are locators, never expressions."""
    if isinstance(value, dict) and value:
        result = {}
        for key in sorted(value):
            token = str(key).replace("~", "~0").replace("/", "~1")
            result.update(choice_fragments(value=value[key], path=path + "/" + token))
        return result
    if isinstance(value, list) and value:
        result = {}
        for index, item in enumerate(value):
            result.update(choice_fragments(value=item, path=path + "/" + str(index)))
        return result
    return {path: value}


def _fragment_value(*, choice: Mapping[str, object], path: object) -> object:
    """Resolve a concrete JSON pointer only for transfer equality checks."""
    if type(path) is not str or not path.startswith("/"):
        raise RequirementProfileError("Transfer target path is invalid")
    value: object = choice
    try:
        for raw in path[1:].split("/"):
            token = raw.replace("~1", "/").replace("~0", "~")
            if type(value) is list:
                if not token.isdigit() or str(int(token)) != token:
                    raise RequirementProfileError("Transfer list index is invalid")
                value = value[int(token)]
            elif type(value) is dict:
                value = value[token]
            else:
                raise RequirementProfileError("Transfer target is not a container")
    except (KeyError, IndexError) as error:
        raise RequirementProfileError("Transfer target path is absent") from error
    return value


def _validate_transfer(
    *,
    transfer: Mapping[str, object],
    requirement_id: str,
    parent: Mapping[str, object],
    current_decisions: Mapping[str, object],
    parent_snapshot_dir: Path,
    parent_snapshot_files: Mapping[str, object],
) -> Dict[str, object]:
    fields = {
        "fragment_classification_counts",
        "fragments",
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
        transfer["schema_version"] != 2
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
    raw_dispositions = transfer["fragments"]
    if type(raw_dispositions) is not list:
        raise RequirementProfileError("Transfer dispositions must be an array")
    parent_decisions = parent["effective_decisions"]
    expected_fragments = {
        (decision_id, path): value
        for decision_id, decision in parent_decisions.items()
        for path, value in choice_fragments(value=decision["choice"]).items()
    }
    dispositions: Dict[tuple, Dict[str, object]] = {}
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
                "source_path",
                "source_value_hash",
                "successor_decision_id",
                "successor_path",
                "transfer_mode",
            },
            label="Transfer disposition",
        )
        decision_id = _text(value=row["decision_id"], label="parent decision id")
        source_path = _text(
            value=row["source_path"], label="Parent policy fragment path"
        )
        key = (decision_id, source_path)
        if (
            key in dispositions
            or decision_id not in parent_decisions
            or key not in expected_fragments
            or row["disposition"] not in TRANSFER_DISPOSITIONS
            or row["parent_effective_record_hash"]
            != decision_record_hash(decision=parent_decisions[decision_id])
            or row["source_value_hash"] != content_hash(value=expected_fragments[key])
        ):
            raise RequirementProfileError("Transfer disposition differs")
        _text(value=row["rationale"], label="transfer rationale")
        target_id = row["successor_decision_id"]
        if row["disposition"] == "HISTORICAL_ONLY":
            if (
                target_id is not None
                or row["successor_path"] is not None
                or row["transfer_mode"] != "HISTORY_ONLY"
            ):
                raise RequirementProfileError("Historical fragment has current credit")
        else:
            if (
                target_id not in current_decisions
                or current_decisions[target_id]["status"] != "APPROVED"
            ):
                raise RequirementProfileError(
                    "Transfer target Decision is not approved"
                )
            target = _fragment_value(
                choice=current_decisions[target_id]["choice"],
                path=row["successor_path"],
            )
            parent_choice = parent_decisions[decision_id]["choice"]
            required_kind = None
            if {"provider", "model", "api", "endpoint_host"}.issubset(parent_choice):
                required_kind = "PROVIDER_TRANSPORT_POLICY"
            elif {"security_claim", "same_process_strong_sandbox_claim"}.issubset(
                parent_choice
            ):
                required_kind = "SECURITY_BOUNDARY_POLICY"
            elif {
                "required_fast_command",
                "per_case_timeout_seconds",
                "evidence_tier",
            }.issubset(parent_choice):
                required_kind = "TEST_POLICY"
            if required_kind is not None and (
                current_decisions[target_id]["choice"].get("kind") != required_kind
                or row["successor_path"] != source_path
            ):
                raise RequirementProfileError(
                    "Transport/security/test obligation was misclassified"
                )
            if row["disposition"] == "CARRY_FORWARD":
                if row["transfer_mode"] == "EXACT_VALUE":
                    if target != expected_fragments[key]:
                        raise RequirementProfileError("Carried policy value differs")
                elif row["transfer_mode"] == "IMMUTABLE_REFERENCE":
                    if target != {
                        "decision_id": decision_id,
                        "source_path": row["source_path"],
                        "source_value_hash": row["source_value_hash"],
                    }:
                        raise RequirementProfileError(
                            "Carried policy reference differs"
                        )
                else:
                    raise RequirementProfileError("Carry-forward mode is invalid")
            elif row["transfer_mode"] != "REPLACED_POLICY":
                raise RequirementProfileError("Superseded policy mode is invalid")
        dispositions[key] = row
        counts[str(row["disposition"])] += 1
    if (
        set(dispositions) != set(expected_fragments)
        or [(row["decision_id"], row["source_path"]) for row in raw_dispositions]
        != sorted(dispositions)
        or transfer["fragment_classification_counts"] != counts
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
    return {
        "fragments": list(dispositions.values()),
        "fragment_classification_counts": counts,
        "historical_material": historical,
    }


def _validate_baseline(
    *,
    baseline: Mapping[str, object],
    snapshot_dir: Path,
    generation: str = PROFILE_REQUIREMENT_GENERATION,
    semantic_version: str = PROFILE_SEMANTIC_VERSION,
    engine_file: Path = Path(__file__),
    engine_dependencies: Sequence[Path] = (),
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
        "policy_evidence",
        "execution_authority",
        "activation_state",
        "supersedes_requirement",
    }
    _exact_fields(value=baseline, expected=fields, label="Profile baseline")
    requirement_id = _text(value=baseline["requirement_id"], label="Requirement id")
    if (
        baseline["schema_version"] != 1
        or baseline["record_type"] != "REQUIREMENT_BASELINE_MANIFEST"
        or REQUIREMENT_ID_PATTERN.fullmatch(requirement_id) is None
        or baseline["requirement_generation"] != generation
        or baseline["artifact_requirement_generation"] != EXPLICIT_ARTIFACT_GENERATION
        or baseline["source_input_role"] != "SUCCESSOR_REQUIREMENT_AUTHORITY"
        or baseline["activation_state"] != "NOT_ACTIVATED"
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
    issue_number = _integer(value=issue["number"], label="Issue number", minimum=1,)
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
        re.fullmatch(r"issue_{}_v[1-9][0-9]*".format(issue_number), requirement_id)
        is None
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
        CONTENT_HASH_PATTERN.fullmatch(str(parent["requirement_closure_hash"])) is None
        or COMMIT_PATTERN.fullmatch(str(parent["snapshot_git_tree"])) is None
        or CONTENT_HASH_PATTERN.fullmatch(str(parent["snapshot_binding_hash"])) is None
        or type(parent["hashes"]) is not dict
        or type(parent["snapshot_files"]) is not dict
    ):
        raise RequirementProfileError("Parent binding identity differs")
    active = _mapping(value=baseline["active_publication"], label="active publication")
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
        or PUBLICATION_ID_PATTERN.fullmatch(str(active["predecessor_publication_id"]))
        is None
        or SHA256_PATTERN.fullmatch(str(active["bundle_manifest_sha256"])) is None
    ):
        raise RequirementProfileError("Active publication baseline differs")
    archive = _mapping(value=baseline["historical_archive"], label="archive")
    _exact_fields(
        value=archive,
        expected={"commit", "qualification_credit", "ref", "response_reuse", "status",},
        label="archive",
    )
    if (
        re.fullmatch(r"HISTORICAL_[A-Z0-9_]+_ONLY", str(archive["status"])) is None
        or COMMIT_PATTERN.fullmatch(str(archive["commit"])) is None
        or not str(archive["ref"]).startswith("archive/")
        or archive["qualification_credit"] != "NONE"
        or archive["response_reuse"] != "NOT_AUTHORIZED"
    ):
        raise RequirementProfileError("Historical archive baseline differs")
    validator = _mapping(value=baseline["validator"], label="validator")
    _exact_fields(
        value=validator,
        expected={"path", "semantic_version", "sha256", "dependencies"},
        label="validator",
    )
    if (
        validator["path"] != "scripts/vnext/" + engine_file.name
        or validator["semantic_version"] != semantic_version
        or validator["sha256"]
        != sha256_file(path=_regular_file(path=engine_file, label="Versioned engine"))
        or validator["dependencies"]
        != {
            "scripts/vnext/"
            + path.name: {
                "sha256": sha256_file(
                    path=_regular_file(path=path, label="Engine dependency")
                ),
                "size": path.stat().st_size,
            }
            for path in engine_dependencies
        }
    ):
        raise RequirementProfileError("Generic validator identity differs")
    local_engine = _regular_file(
        path=snapshot_dir.parent.parent / str(validator["path"]),
        label="Retained versioned engine",
    )
    if sha256_file(path=local_engine) != validator["sha256"]:
        raise RequirementProfileError("Retained versioned engine bytes differ")
    for relative, binding in validator["dependencies"].items():
        local_dependency = _regular_file(
            path=snapshot_dir.parent.parent / relative,
            label="Retained engine dependency",
        )
        if (
            sha256_file(path=local_dependency) != binding["sha256"]
            or local_dependency.stat().st_size != binding["size"]
        ):
            raise RequirementProfileError("Retained engine dependency differs")
    _verify_bound_files(
        root=snapshot_dir,
        bindings=baseline["snapshot_files"],
        expected_files=PROFILE_BOUND_FILES,
        label="Profile snapshot",
    )
    execution = _mapping(
        value=baseline["execution_authority"], label="Execution authority"
    )
    _exact_fields(
        value=execution,
        expected={"files", "semantic_runtime_versions_hash"},
        label="Execution authority",
    )
    if (
        CONTENT_HASH_PATTERN.fullmatch(str(execution["semantic_runtime_versions_hash"]))
        is None
    ):
        raise RequirementProfileError("Execution semantic version binding is invalid")
    if type(execution["files"]) is not dict or not execution["files"]:
        raise RequirementProfileError("Execution authority file set is absent")
    for relative, binding in execution["files"].items():
        if (
            type(relative) is not str
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or Path(relative).as_posix() != relative
        ):
            raise RequirementProfileError("Execution authority path is unsafe")
        _file_binding(value=binding, label="Execution authority file")
    evidence = baseline["policy_evidence"]
    if type(evidence) is not list or not evidence:
        raise RequirementProfileError("Policy-content provenance is absent")
    source_ids = []
    for raw in evidence:
        source = _mapping(value=raw, label="Policy evidence")
        _exact_fields(
            value=source,
            expected={
                "source_id",
                "kind",
                "source_url",
                "source_sha256",
                "author",
                "published_at_utc",
                "text",
            },
            label="Policy evidence",
        )
        source_ids.append(_text(value=source["source_id"], label="Policy source id"))
        if (
            source["kind"]
            not in {
                "ISSUE_BODY_POLICY",
                "OWNER_POLICY_SUCCESSOR",
                "PARENT_DECISION_POLICY",
            }
            or source["source_url"] == issue["identifier_comment_url"]
            or not str(source["source_url"]).startswith(
                ("https://github.com/", "requirements/")
            )
            or source["source_sha256"]
            != sha256_bytes(
                content=_text(value=source["text"], label="Policy text").encode("utf-8")
            )
        ):
            raise RequirementProfileError("Policy-content provenance differs")
        _text(value=source["author"], label="Policy author")
        parse_utc_timestamp(value=str(source["published_at_utc"]))
        if source["kind"] == "ISSUE_BODY_POLICY" and (
            source["source_url"] != issue_url
            or source["source_sha256"] != issue["tracking_body_sha256"]
            or len(source["text"].encode("utf-8")) != issue["tracking_body_size"]
        ):
            raise RequirementProfileError("Issue policy body binding differs")
    if source_ids != sorted(set(source_ids)):
        raise RequirementProfileError("Policy evidence identities differ")
    return dict(baseline)


def _recorded_parent(
    *, snapshot_dir: Path, binding: Mapping[str, object],
) -> Dict[str, object]:
    """Reconstruct historical authority from recorded hashes and frozen bytes.

    Deliberately do not call the historical adapter: that adapter validates a
    live execution root, while a successor's parent is immutable history.
    """
    expected = set(binding["snapshot_files"])
    if {
        path.name for path in snapshot_dir.iterdir()
    } != expected or snapshot_dir.is_symlink():
        raise RequirementProfileError("Historical parent file exact set differs")
    _verify_bound_files(
        root=snapshot_dir,
        bindings=binding["snapshot_files"],
        expected_files=expected,
        label="Historical parent snapshot",
    )
    hashes = _mapping(value=binding["hashes"], label="Historical parent hashes")
    if content_hash(value=hashes) != binding["requirement_closure_hash"]:
        raise RequirementProfileError("Parent Requirement closure differs")
    file_hash_fields = {
        "baseline_manifest.json": "baseline_sha256",
        "CONTRACT.md": "contract_sha256",
        "decision_register.json": "decision_register_sha256",
        "transfer_manifest.json": "transfer_manifest_sha256",
        "foundation_verification_receipt.json": "foundation_verification_receipt_sha256",
        "legacy_semantic_producer_inventory.json": "legacy_semantic_producer_inventory_sha256",
        "source_strategy_baseline_receipt.json": "source_strategy_baseline_receipt_sha256",
    }
    for filename, field in file_hash_fields.items():
        if (
            filename in expected
            and hashes.get(field) != binding["snapshot_files"][filename]["sha256"]
        ):
            raise RequirementProfileError(
                "Historical parent snapshot/hash binding differs"
            )
    baseline = read_requirement_object(path=snapshot_dir / "baseline_manifest.json")
    register = read_requirement_object(path=snapshot_dir / "decision_register.json")
    if (
        baseline["requirement_id"] != binding["requirement_id"]
        or register["requirement_id"] != binding["requirement_id"]
    ):
        raise RequirementProfileError("Historical parent identity differs")
    if (
        "CONTRACT.md" in expected
        and hashes.get("issue_body_sha256") != hashes["contract_sha256"]
    ):
        raise RequirementProfileError("Historical parent Contract binding differs")
    decisions, chains = resolve_decision_chains(
        decisions=list(register["decisions"])
        + list(register.get("pending_decisions", []))
    )
    return {
        "requirement_id": binding["requirement_id"],
        "hashes": hashes,
        "requirement_closure_hash": content_hash(value=hashes),
        "artifact_requirement_generation": LEGACY_ARTIFACT_GENERATION,
        "baseline": baseline,
        "effective_decisions": decisions,
        "decision_chains": chains,
        "pending_decision_ids": sorted(
            k
            for k, d in decisions.items()
            if d["status"] == "PENDING_EXTERNAL_APPROVAL"
        ),
    }


def _validate_policy_provenance(
    *,
    decisions: Mapping[str, Mapping[str, object]],
    chains: Mapping[str, Sequence[Mapping[str, object]]],
    baseline: Mapping[str, object],
    parent: Mapping[str, object],
) -> None:
    """Separate approval of policy content from transition/live authorization."""
    sources = {row["source_id"]: row for row in baseline["policy_evidence"]}
    for decision_id, decision in decisions.items():
        if decision["status"] != "APPROVED":
            continue
        provenance = _mapping(
            value=decision.get("policy_provenance"), label="Decision policy provenance"
        )
        _exact_fields(
            value=provenance,
            expected={"source_id", "section", "scope"},
            label="Decision policy provenance",
        )
        if (
            provenance["source_id"] not in sources
            or provenance["scope"] != "POLICY_CONTENT_ONLY"
        ):
            raise RequirementProfileError("Decision policy-content evidence is missing")
        source = sources[provenance["source_id"]]
        if (
            decision["approved_by"] != source["author"]
            or decision["approved_at_utc"] != source["published_at_utc"]
            or decision["evidence"] != source["source_url"]
            or _text(value=provenance["section"], label="Policy section")
            not in source["text"]
        ):
            raise RequirementProfileError("Decision approval provenance differs")
        if source["kind"] == "OWNER_POLICY_SUCCESSOR":
            approval = strict_json_loads(text=source["text"])
            if (
                type(approval) is not dict
                or approval
                != {
                    "record_type": "OWNER_POLICY_APPROVAL",
                    "scope": "POLICY_CONTENT_ONLY",
                    "decision_id": decision_id,
                    "choice_hash": content_hash(value=decision["choice"]),
                    "supersedes_record_hash": decision["supersedes_decision_id"],
                }
                or len(chains[decision_id]) < 2
            ):
                raise RequirementProfileError("Owner successor policy approval differs")
        if source["kind"] == "PARENT_DECISION_POLICY":
            recorded = strict_json_loads(text=source["text"])
            if (
                type(recorded) is not dict
                or parent["effective_decisions"].get(recorded.get("decision_id"))
                != recorded
                or source["author"] != recorded["approved_by"]
                or source["published_at_utc"] != recorded["approved_at_utc"]
            ):
                raise RequirementProfileError("Inherited policy provenance differs")


def _load_profile_requirement_snapshot(
    *,
    snapshot_dir: Path,
    parent_loader: Callable[..., Mapping[str, object]],
    generation: str = PROFILE_REQUIREMENT_GENERATION,
    semantic_version: str = PROFILE_SEMANTIC_VERSION,
    engine_file: Path = Path(__file__),
    engine_dependencies: Sequence[Path] = (),
    evaluators: Optional[Mapping[str, Callable]] = None,
) -> Dict[str, object]:
    """Load one profile-driven successor Requirement Snapshot."""
    if snapshot_dir.is_symlink() or not snapshot_dir.is_dir():
        raise RequirementProfileError("Requirement snapshot directory is unsafe")
    entries = list(snapshot_dir.iterdir())
    if {path.name for path in entries} != PROFILE_SNAPSHOT_FILES or any(
        path.is_symlink() or not path.is_file() for path in entries
    ):
        raise RequirementProfileError("Profile Requirement file set differs")
    baseline = _validate_baseline(
        baseline=read_requirement_object(path=snapshot_dir / "baseline_manifest.json"),
        snapshot_dir=snapshot_dir,
        generation=generation,
        semantic_version=semantic_version,
        engine_file=engine_file,
        engine_dependencies=engine_dependencies,
    )
    requirement_id = str(baseline["requirement_id"])
    previous = baseline["supersedes_requirement"]
    if previous is not None:
        _exact_fields(
            value=_mapping(value=previous, label="Requirement revision"),
            expected={"requirement_id", "requirement_closure_hash"},
            label="Requirement revision",
        )
        previous_id = str(previous["requirement_id"])
        previous_match = re.fullmatch(r"issue_([0-9]+)_v([1-9][0-9]*)", previous_id)
        current_match = re.fullmatch(r"issue_([0-9]+)_v([1-9][0-9]*)", requirement_id)
        if (
            previous_match is None
            or current_match is None
            or previous_match[1] != current_match[1]
            or int(previous_match[2]) >= int(current_match[2])
        ):
            raise RequirementProfileError("Requirement revision identity differs")
        previous_requirement = parent_loader(
            snapshot_dir=snapshot_dir.parent / previous_id
        )
        if (
            previous_requirement["requirement_closure_hash"]
            != previous["requirement_closure_hash"]
        ):
            raise RequirementProfileError("Requirement revision closure differs")
    elif not requirement_id.endswith("_v1"):
        raise RequirementProfileError("Requirement revision predecessor is missing")
    parent_binding = baseline["parent"]
    parent_dir = snapshot_dir.parent / str(parent_binding["requirement_id"])
    if parent_dir.is_symlink() or not parent_dir.is_dir():
        raise RequirementProfileError("Parent Requirement directory is unsafe")
    if parent_binding["requirement_id"] == requirement_id:
        raise RequirementProfileError("Requirement parent cannot be itself")
    try:
        parent_baseline = read_requirement_object(
            path=parent_dir / "baseline_manifest.json"
        )
        parent = (
            dict(parent_loader(snapshot_dir=parent_dir))
            if str(parent_baseline.get("requirement_generation", "")).startswith(
                "PROFILE_DRIVEN_"
            )
            else _recorded_parent(snapshot_dir=parent_dir, binding=parent_binding)
        )
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

    register = read_requirement_object(path=snapshot_dir / "decision_register.json")
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
    _validate_policy_provenance(
        decisions=decisions, chains=chains, baseline=baseline, parent=parent
    )
    pending_ids = sorted(
        decision_id
        for decision_id, decision in decisions.items()
        if decision["status"] == "PENDING_EXTERNAL_APPROVAL"
    )

    profile = read_requirement_object(path=snapshot_dir / "invariant_profile.json")
    evaluated = evaluate_invariant_profile(
        profile=profile,
        requirement_id=requirement_id,
        effective_decisions=decisions,
        semantic_version=semantic_version,
        evaluators=evaluators,
    )
    transfer = read_requirement_object(path=snapshot_dir / "transfer_manifest.json")
    transfer_result = _validate_transfer(
        transfer=transfer,
        requirement_id=requirement_id,
        parent=parent,
        current_decisions=decisions,
        parent_snapshot_dir=parent_dir,
        parent_snapshot_files=parent_binding["snapshot_files"],
    )

    evaluated_rows = list(evaluated["by_invariant_id"].values())
    values_by_kind: Dict[str, list] = {}
    scoped_keys = set()
    for row in evaluated_rows:
        kind, value = row["kind"], row["value"]
        scope = value.get("ratchet_id") if kind in SCOPED_INVARIANT_KINDS else "GLOBAL"
        if scope != "GLOBAL" and (type(scope) is not str or not scope.startswith("R")):
            raise RequirementProfileError("Invariant ratchet scope is invalid")
        if (kind, scope) in scoped_keys:
            raise RequirementProfileError("Duplicate invariant kind within one scope")
        scoped_keys.add((kind, scope))
        values_by_kind.setdefault(kind, []).append(value)
    if not SUPPORTED_INVARIANT_KINDS.issubset(values_by_kind):
        raise RequirementProfileError("Required typed safety invariant is absent")
    historical = values_by_kind["HISTORICAL_EVIDENCE_POLICY"][0]
    artifact_identity = values_by_kind["ARTIFACT_REQUIREMENT_IDENTITY"][0]
    if (
        historical["archive_ref"] != baseline["historical_archive"]["ref"]
        or historical["archive_commit"] != baseline["historical_archive"]["commit"]
        or historical["classification"] != baseline["historical_archive"]["status"]
        or artifact_identity["generation"]
        != baseline["artifact_requirement_generation"]
    ):
        raise RequirementProfileError("Baseline invariant binding differs")
    for publication in values_by_kind["PUBLICATION_PREDECESSOR"]:
        if (
            publication["ratchet_id"] == "R4"
            and publication["required_predecessor"]
            != baseline["active_publication"]["publication_id"]
        ):
            raise RequirementProfileError("R4 predecessor binding differs")
    for calls in values_by_kind["LIVE_CALL_BOUND"]:
        ratchet = calls["ratchet_id"]
        if any((kind, ratchet) not in scoped_keys for kind in SCOPED_INVARIANT_KINDS):
            raise RequirementProfileError("Live ratchet policy scope is incomplete")
        source = next(
            v
            for v in values_by_kind["SOURCE_SCOPE_POLICY"]
            if v["ratchet_id"] == ratchet
        )
        if (
            source["positive_fixture_classes"] != calls["positive_fixture_classes"]
            or source["zero_call_fixture_classes"] != calls["zero_call_fixture_classes"]
        ):
            raise RequirementProfileError("Fixture call-class scope differs")
    for row in transfer_result["historical_material"]:
        if (
            row["archive_ref"] != historical["archive_ref"]
            or row["archive_commit"] != historical["archive_commit"]
        ):
            raise RequirementProfileError("Historical material archive differs")
    parent_decisions = parent["effective_decisions"]
    inherited_provider = (
        parent_decisions["D-01"]["choice"]
        if "D-01" in parent_decisions
        else next(
            d["choice"]
            for d in parent_decisions.values()
            if d.get("choice", {}).get("kind") == "PROVIDER_TRANSPORT_POLICY"
        )
    )
    provider_row = next(
        row for row in evaluated_rows if row["kind"] == "PROVIDER_TRANSPORT_POLICY"
    )
    provider_decision = decisions[provider_row["decision_id"]]
    if {k: v for k, v in provider_row["value"].items() if k != "kind"} != {
        k: v for k, v in inherited_provider.items() if k != "kind"
    }:
        sources = {s["source_id"]: s for s in baseline["policy_evidence"]}
        source = sources[provider_decision["policy_provenance"]["source_id"]]
        if (
            len(chains[provider_row["decision_id"]]) < 2
            or source["kind"] != "OWNER_POLICY_SUCCESSOR"
        ):
            raise RequirementProfileError(
                "Provider change requires explicit owner successor Decision"
            )
    inherited_test = (
        parent_decisions["D-26"]["choice"]
        if "D-26" in parent_decisions
        else next(
            d["choice"]
            for d in parent_decisions.values()
            if d.get("choice", {}).get("kind") == "TEST_POLICY"
        )
    )
    if not set(inherited_test["required_short_deterministic_invariants"]).issubset(
        values_by_kind["TEST_POLICY"][0]["required_short_deterministic_invariants"]
    ):
        raise RequirementProfileError("Test policy removed an inherited fast invariant")
    for obligation in values_by_kind["PARENT_POLICY_CARRY_FORWARD"][0]["obligations"]:
        decision_id = obligation["decision_id"]
        if decision_id not in parent_decisions:
            raise RequirementProfileError("Inherited Decision is absent")
        fragments = choice_fragments(value=parent_decisions[decision_id]["choice"])
        if (
            obligation["source_path"] not in fragments
            or content_hash(value=fragments[obligation["source_path"]])
            != obligation["source_value_hash"]
        ):
            raise RequirementProfileError("Inherited semantic obligation differs")

    hashes = {
        "baseline_sha256": sha256_file(path=snapshot_dir / "baseline_manifest.json"),
        "contract_sha256": sha256_file(path=snapshot_dir / "CONTRACT.md"),
        "decision_register_sha256": sha256_file(
            path=snapshot_dir / "decision_register.json"
        ),
        "invariant_profile_sha256": sha256_file(
            path=snapshot_dir / "invariant_profile.json"
        ),
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "transfer_manifest_sha256": sha256_file(
            path=snapshot_dir / "transfer_manifest.json"
        ),
        "validator_sha256": baseline["validator"]["sha256"],
    }
    return {
        "artifact_requirement_generation": baseline["artifact_requirement_generation"],
        "baseline": baseline,
        "decision_chains": chains,
        "effective_decisions": decisions,
        "evaluated_invariants": evaluated,
        "hashes": hashes,
        "issue_contract_revision": register["issue_contract_revision"],
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "parent_requirement_id": parent["requirement_id"],
        "pending_decision_ids": pending_ids,
        "requirement_closure_hash": content_hash(value=hashes),
        "requirement_generation": generation,
        "requirement_id": requirement_id,
        "transfer": transfer_result,
        "parent_snapshot": parent,
        "execution_authority": baseline["execution_authority"],
        "activation_state": "NOT_ACTIVATED",
    }


def load_profile_requirement_snapshot(
    *, snapshot_dir: Path, parent_loader: Callable[..., Mapping[str, object]],
) -> Dict[str, object]:
    """Load the retained V1 engine, regardless of future registry additions."""
    return _load_profile_requirement_snapshot(
        snapshot_dir=snapshot_dir, parent_loader=parent_loader,
    )


def validate_artifact_requirement_identity(
    *, artifact: Mapping[str, object], requirement: Mapping[str, object]
) -> Dict[str, object]:
    """Apply generation-specific Requirement identity to one artifact.

    Legacy artifacts remain byte-compatible and are accepted only under a
    legacy Requirement adapter.  A profile-driven successor requires all
    three explicit identity fields; missing fields cannot select legacy mode.
    """
    record_type = _text(value=artifact.get("record_type"), label="artifact type")
    generation = requirement.get("artifact_requirement_generation")
    explicit_fields = {
        "requirement_closure_hash",
        "requirement_hashes",
        "requirement_id",
    }
    if record_type not in SUCCESSOR_RECORD_TYPES:
        if generation != LEGACY_ARTIFACT_GENERATION:
            raise RequirementProfileError(
                "Legacy record cannot use successor Requirement"
            )
        if record_type == "ISSUE_15_RELEASE_PLAN":
            if (
                "artifact_requirement_generation" in artifact
                or artifact.get("requirement_id") != requirement["requirement_id"]
                or artifact.get("requirement_closure_hash")
                != requirement["requirement_closure_hash"]
            ):
                raise RequirementProfileError(
                    "Historical ReleasePlan Requirement identity differs"
                )
            return {
                "generation": LEGACY_ARTIFACT_GENERATION,
                "record_type": record_type,
            }
        if record_type not in {"RUN", "PUBLICATION_MANIFEST"}:
            raise RequirementProfileError("Legacy artifact type is unsupported")
        if {
            "requirement_closure_hash",
            "requirement_id",
            "artifact_requirement_generation",
        } & set(artifact):
            raise RequirementProfileError(
                "Legacy artifact contains successor Requirement identity"
            )
        hashes = artifact.get("requirement_hashes")
        if type(hashes) is not dict or hashes != requirement["hashes"]:
            raise RequirementProfileError("Legacy artifact Requirement hashes differ")
        return {
            "generation": LEGACY_ARTIFACT_GENERATION,
            "record_type": record_type,
        }
    if generation != EXPLICIT_ARTIFACT_GENERATION:
        raise RequirementProfileError("Artifact Requirement generation is unknown")
    if artifact.get("artifact_requirement_generation") != EXPLICIT_ARTIFACT_GENERATION:
        raise RequirementProfileError(
            "Successor artifact generation is missing or invalid"
        )
    missing = explicit_fields - set(artifact)
    if missing:
        raise RequirementProfileError(
            "Successor artifact Requirement identity is missing"
        )
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


def validate_execution_authority(
    *, repo_root: Path, requirement: Mapping[str, object]
) -> None:
    """Validate current execution inputs separately from immutable parent loading."""
    execution = requirement["execution_authority"]
    for relative, binding in execution["files"].items():
        path = repo_root
        for part in Path(relative).parts:
            path = path / part
            if path.is_symlink():
                raise RequirementProfileError("Execution authority contains a symlink")
        _regular_file(path=path, label="Execution authority")
        if (
            sha256_file(path=path) != binding["sha256"]
            or path.stat().st_size != binding["size"]
        ):
            raise RequirementProfileError(
                "Successor execution authority bytes differ: " + relative
            )
    if (
        content_hash(value=SEMANTIC_VERSIONS)
        != execution["semantic_runtime_versions_hash"]
    ):
        raise RequirementProfileError("Successor execution semantic version differs")


def validate_transition_activation_receipt(
    *,
    receipt: Mapping[str, object],
    requirement: Mapping[str, object],
    exact_head: str,
) -> Dict[str, object]:
    """Validate a separately issued exact-head activation, never infer one."""
    _exact_fields(
        value=receipt,
        expected={
            "record_type",
            "schema_version",
            "receipt_id",
            "requirement_id",
            "requirement_closure_hash",
            "exact_head",
            "authorization_scope",
            "provider_paid_sec_authorized",
            "approval_kind",
            "owner",
            "approved_at_utc",
            "source_url",
            "approval_text",
            "approval_text_sha256",
        },
        label="Transition activation receipt",
    )
    body = {k: v for k, v in receipt.items() if k != "receipt_id"}
    if (
        receipt["record_type"] != "REQUIREMENT_TRANSITION_ACTIVATION"
        or receipt["schema_version"] != 1
        or receipt["receipt_id"] != content_hash(value=body)
        or receipt["requirement_id"] != requirement["requirement_id"]
        or receipt["requirement_closure_hash"]
        != requirement["requirement_closure_hash"]
        or receipt["exact_head"] != exact_head
        or COMMIT_PATTERN.fullmatch(exact_head) is None
        or receipt["authorization_scope"] != "TRANSITION_ONLY"
        or receipt["provider_paid_sec_authorized"] is not False
        or receipt["approval_kind"] != "EXACT_HEAD_TRANSITION_APPROVAL"
        or receipt["source_url"]
        == requirement["baseline"]["issue"]["identifier_comment_url"]
        or not str(receipt["source_url"]).startswith(
            "https://github.com/"
            + str(requirement["baseline"]["repository"]["identity"])
            + "/pull/"
        )
        or receipt["owner"] != requirement["baseline"]["policy_evidence"][0]["author"]
    ):
        raise RequirementProfileError(
            "Transition activation is absent or not exact-head approval"
        )
    approval_text = _text(
        value=receipt["approval_text"], label="Exact-head approval text"
    )
    if receipt["approval_text_sha256"] != sha256_bytes(
        content=approval_text.encode("utf-8")
    ) or strict_json_loads(text=approval_text) != {
        "decision": "APPROVE_REQUIREMENT_TRANSITION",
        "exact_head": exact_head,
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "scope": "TRANSITION_ONLY",
        "provider_paid_sec_authorized": False,
    }:
        raise RequirementProfileError("Exact-head activation approval content differs")
    parse_utc_timestamp(value=str(receipt["approved_at_utc"]))
    return dict(receipt)
