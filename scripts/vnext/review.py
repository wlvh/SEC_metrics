"""Bind ReviewUnit content, HUMAN decisions, and verified observations."""

from __future__ import annotations

import re
from typing import Dict, Mapping, Optional, Sequence

from .canonical import CanonicalError, content_hash, parse_utc_timestamp
from .records import validate_record
from .specs import SEMANTIC_SET_PATHS


REVIEWER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{2,127}$")


class ReviewError(ValueError):
    """Report invalid review binding, decision chain, or approved claims."""


def build_review_unit(
    *,
    candidate: Mapping[str, object],
    evidence_check: Mapping[str, object],
    source_bindings: Sequence[Mapping[str, object]],
    compiled_spec: Mapping[str, object],
    review_context_hash: str,
    rendered_review_hash: str,
    renderer_semantic_version: str,
) -> Dict[str, object]:
    """Create one hash-bound review unit for all selected roles.

    Args:
        candidate: Candidate including selected, competing, and unresolved
            claims.
        evidence_check: Mechanical checker result.
        source_bindings: Reviewed source identities.
        compiled_spec: Compiled Spec wrapper owning every reviewed claim.
        review_context_hash: Canonical context actually rendered.
        rendered_review_hash: Exact review bytes shown to the reviewer.
        renderer_semantic_version: Renderer behavior identity.

    Returns:
        Strict ``REVIEW_UNIT`` record in ``PENDING`` state.
    """
    validate_record(record=candidate)
    validate_record(record=evidence_check)
    if evidence_check["candidate_hash"] != candidate["candidate_hash"]:
        raise ReviewError("EvidenceCheck binds a different Candidate")
    if evidence_check["status"] != "PASS":
        raise ReviewError("Rejected EvidenceCheck cannot enter HUMAN approval")
    if (
        not isinstance(compiled_spec, dict)
        or "compiled" not in compiled_spec
        or "spec_semantic_hash" not in compiled_spec
        or not isinstance(compiled_spec["compiled"], dict)
        or compiled_spec["spec_semantic_hash"]
        != content_hash(
            value=compiled_spec["compiled"], set_paths=SEMANTIC_SET_PATHS,
        )
    ):
        raise ReviewError("ReviewUnit compiled Spec is invalid")
    semantic = dict(compiled_spec["compiled"])
    required_claims = semantic["required_claims"]
    if not isinstance(required_claims, dict) or not required_claims:
        raise ReviewError("ReviewUnit required claims must be non-empty")
    validated_sources = []
    for binding in source_bindings:
        validated = validate_record(record=binding)
        if validated["record_type"] != "SOURCE_REFERENCE":
            raise ReviewError("ReviewUnit source is not a SourceReference")
        validated_sources.append(validated)
    if [
        source["source_reference_id"] for source in validated_sources
    ] != candidate["source_reference_ids"]:
        raise ReviewError("ReviewUnit SourceReference exact set differs")
    candidate_hashes = [
        content_hash(value=candidate["selected"][role])
        for role in sorted(candidate["selected"])
    ]
    substantive = {
        "selected": candidate["selected"],
        "competing_candidates": candidate["competing_candidates"],
        "unresolved_competing_claims": candidate[
            "unresolved_competing_claims"
        ],
        "candidate_hashes": candidate_hashes,
        "source_bindings": validated_sources,
        "spec_semantic_hash": compiled_spec["spec_semantic_hash"],
        "compiled_spec": semantic,
        "required_claims": dict(required_claims),
        "evidence_check_id": evidence_check["evidence_check_id"],
        "review_context_hash": review_context_hash,
        "rendered_review_hash": rendered_review_hash,
        "review_renderer_semantic_version": renderer_semantic_version,
    }
    record = {
        "record_type": "REVIEW_UNIT",
        "review_unit_hash": content_hash(value=substantive),
        "status": "PENDING",
        "selected": candidate["selected"],
        "competing_candidates": candidate["competing_candidates"],
        "unresolved_competing_claims": candidate[
            "unresolved_competing_claims"
        ],
        "candidate_hashes": candidate_hashes,
        "source_bindings": substantive["source_bindings"],
        "spec_semantic_hash": substantive["spec_semantic_hash"],
        "compiled_spec": substantive["compiled_spec"],
        "required_claims": substantive["required_claims"],
        "evidence_check_id": evidence_check["evidence_check_id"],
        "review_context_hash": review_context_hash,
        "rendered_review_hash": rendered_review_hash,
        "review_renderer_semantic_version": renderer_semantic_version,
    }
    return validate_record(record=record)


def create_review_decision(
    *,
    review_unit: Mapping[str, object],
    decision: str,
    approved_claims: Mapping[str, object],
    required_claims: Mapping[str, object],
    reviewer_id: str,
    decided_at_utc: str,
    reason: str,
    supersedes_decision_id: Optional[str],
) -> Dict[str, object]:
    """Create an immutable HUMAN decision bound to actual rendered context.

    Args:
        review_unit: Unit the human reviewed.
        decision: ``APPROVE`` or ``REJECT``.
        approved_claims: Canonical claims approved as a whole.
        required_claims: Exact Spec-required claims.
        reviewer_id: Stable opaque human identity; OS/model identity is not
            inferred.
        decided_at_utc: Explicit UTC timestamp supplied by the review CLI.
        reason: Human rationale.
        supersedes_decision_id: Prior decision ID or ``None``.

    Returns:
        Strict ``REVIEW_DECISION`` record.

    Raises:
        ReviewError: On non-human/empty identity, mismatched claims, invalid
            choice, or missing rationale.
    """
    validate_record(record=review_unit)
    if review_unit["status"] != "PENDING":
        raise ReviewError("Review decision requires a PENDING unit")
    if decision not in {"APPROVE", "REJECT"}:
        raise ReviewError("Review decision must be APPROVE or REJECT")
    if REVIEWER_PATTERN.fullmatch(reviewer_id) is None:
        raise ReviewError("reviewer_id is not a stable opaque identifier")
    try:
        parse_utc_timestamp(value=decided_at_utc)
    except CanonicalError as error:
        raise ReviewError("Review decision timestamp is invalid") from error
    if not reason:
        raise ReviewError("Review decision reason is required")
    if dict(required_claims) != review_unit["required_claims"]:
        raise ReviewError("ReviewUnit required claims differ")
    approval_effect = {
        "review_unit_hash": review_unit["review_unit_hash"],
        "decision": decision,
        "approved_claims": dict(approved_claims),
        "reviewed_spec_semantic_hash": review_unit["spec_semantic_hash"],
        "reviewed_source_bindings": review_unit["source_bindings"],
        "review_context_hash": review_unit["review_context_hash"],
        "rendered_review_hash": review_unit["rendered_review_hash"],
        "review_renderer_semantic_version": review_unit[
            "review_renderer_semantic_version"
        ],
    }
    audit = dict(approval_effect)
    audit.update(
        {
            "reviewer_type": "HUMAN",
            "reviewer_id": reviewer_id,
            "decided_at_utc": decided_at_utc,
            "reason": reason,
            "supersedes_decision_id": supersedes_decision_id,
        }
    )
    record = {
        "record_type": "REVIEW_DECISION",
        "review_decision_id": content_hash(value=audit),
        "review_unit_hash": review_unit["review_unit_hash"],
        "decision": decision,
        "approved_claims": dict(approved_claims),
        "reviewed_spec_semantic_hash": review_unit["spec_semantic_hash"],
        "reviewed_source_bindings": review_unit["source_bindings"],
        "review_context_hash": review_unit["review_context_hash"],
        "rendered_review_hash": review_unit["rendered_review_hash"],
        "review_renderer_semantic_version": review_unit[
            "review_renderer_semantic_version"
        ],
        "reviewer_type": "HUMAN",
        "reviewer_id": reviewer_id,
        "decided_at_utc": decided_at_utc,
        "reason": reason,
        "supersedes_decision_id": supersedes_decision_id,
        "approval_effect_hash": content_hash(value=approval_effect),
    }
    validated = validate_record(record=record)
    validate_decision_binding(
        review_unit=review_unit, decision=validated,
    )
    return validated


def effective_review_decision(
    *,
    review_unit: Mapping[str, object],
    decisions: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    """Return the single effective tip of an immutable supersedes chain.

    Args:
        review_unit: Target review unit.
        decisions: All immutable decisions for the unit.

    Returns:
        Unique effective decision.

    Raises:
        ReviewError: On no decision, foreign binding, duplicate ID, cycle,
            missing parent, or parallel children/effective tips.
    """
    if not decisions:
        raise ReviewError("Review unit has no decision")
    by_id: Dict[str, Mapping[str, object]] = {}
    children: Dict[Optional[str], list] = {}
    for decision in decisions:
        # Every immutable chain member remains part of the audit fact, so a
        # superseded record cannot bypass the same semantic binding as the tip.
        validate_decision_binding(
            review_unit=review_unit, decision=decision,
        )
        decision_id = str(decision["review_decision_id"])
        if decision_id in by_id:
            raise ReviewError("Duplicate review decision ID")
        by_id[decision_id] = decision
        parent = decision["supersedes_decision_id"]
        if parent not in children:
            children[parent] = []
        children[parent].append(decision_id)
    roots = children[None] if None in children else []
    if len(roots) != 1:
        raise ReviewError("Decision chain must have one root")
    current = roots[0]
    visited = set()
    while True:
        if current in visited:
            raise ReviewError("Decision supersedes chain contains a cycle")
        visited.add(current)
        next_ids = children[current] if current in children else []
        if len(next_ids) > 1:
            raise ReviewError(
                "Parallel effective review decisions fail closed"
            )
        if not next_ids:
            break
        current = next_ids[0]
    if len(visited) != len(decisions):
        raise ReviewError(
            "Decision chain contains a missing or detached parent"
        )
    return by_id[current]


def validate_decision_binding(
    *, review_unit: Mapping[str, object], decision: Mapping[str, object]
) -> None:
    """Revalidate every Spec/source/context/render binding before freeze.

    Args:
        review_unit: Current bytes-derived unit.
        decision: Effective decision.

    Raises:
        ReviewError: When any substantive or rendered binding changed.
    """
    validated_unit = validate_record(record=review_unit)
    validated_decision = validate_record(record=decision)
    comparisons = {
        "review_unit_hash": validated_unit["review_unit_hash"],
        "reviewed_spec_semantic_hash": validated_unit["spec_semantic_hash"],
        "reviewed_source_bindings": validated_unit["source_bindings"],
        "review_context_hash": validated_unit["review_context_hash"],
        "rendered_review_hash": validated_unit["rendered_review_hash"],
        "review_renderer_semantic_version": validated_unit[
            "review_renderer_semantic_version"
        ],
    }
    for decision_field in comparisons:
        if validated_decision[decision_field] != comparisons[decision_field]:
            raise ReviewError(
                "Review decision binding changed: {}".format(decision_field)
            )
    if (
        validated_decision["decision"] == "APPROVE"
        and validated_decision["approved_claims"]
        != validated_unit["required_claims"]
    ):
        raise ReviewError(
            "Approved claims do not exactly satisfy the ReviewUnit"
        )
