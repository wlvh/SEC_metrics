"""Bind ReviewUnit content, HUMAN decisions, and verified observations."""

from __future__ import annotations

import re
from typing import Dict, Mapping, Optional, Sequence

from .canonical import CanonicalError, content_hash, parse_utc_timestamp
from .records import validate_record
from .scope_contract import scope_satisfies_contract, validate_scope_contract
from .specs import SEMANTIC_SET_PATHS


REVIEWER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{2,127}$")
SYSTEM_REVIEWER_ID = "system:optional-review-v1"
SYSTEM_REVIEW_REASON = "EVIDENCE_BOUND_AUTO_APPROVE"
_OPTIONAL_REVIEW_POLICY_FIELDS = {
    "binds_canonical_and_rendered_context",
    "binds_selected_competing_unresolved",
    "decision_target",
    "human_review_required",
    "parallel_effective_decisions",
    "system_approval_policy",
    "system_reviewer_type",
}


class ReviewError(ValueError):
    """Report invalid review binding, decision chain, or approved claims."""


def _approved_claims_satisfy_unit(
    *, review_unit: Mapping[str, object], approved_claims: Mapping[str, object],
) -> bool:
    """Check a reviewed scope without allowing caller-defined normalization.

    Args:
        review_unit: Exact unit carrying compiled Spec authority.
        approved_claims: HUMAN or SYSTEM canonical decision claims.

    Returns:
        True when legacy claims match exactly or v2 scope satisfies its Spec.
    """
    if type(approved_claims) is not dict:
        return False
    required_claims = review_unit["required_claims"]
    compiled_spec = review_unit["compiled_spec"]
    scope_contract = (
        compiled_spec["scope_contract"]
        if "scope_contract" in compiled_spec
        else None
    )
    if scope_contract is None:
        return dict(approved_claims) == required_claims
    validated_contract = validate_scope_contract(value=scope_contract)
    allowed_dimensions = set(validated_contract["allowed_dimensions"])
    required_dimensions = set(validated_contract["required_dimensions"])
    non_scope_required = {
        key: required_claims[key]
        for key in required_claims
        if key not in allowed_dimensions
    }
    non_scope_approved = {
        key: approved_claims[key]
        for key in approved_claims
        if key not in allowed_dimensions
    }
    normalized_scope = {
        key: approved_claims[key]
        for key in approved_claims
        if key in allowed_dimensions
    }
    if (
        non_scope_approved != non_scope_required
        or not required_dimensions.issubset(set(normalized_scope))
    ):
        return False
    return scope_satisfies_contract(
        contract=validated_contract,
        normalized_scope=normalized_scope,
    )


def _system_approved_claims(*, review_unit: Mapping[str, object]) -> Dict[str, object]:
    """Build SYSTEM-approved claims only from Evidence-normalized scope data.

    Args:
        review_unit: Pending ReviewUnit containing Evidence scope binding.

    Returns:
        Full canonical approval claims with non-scope Spec facts retained.

    Raises:
        ReviewError: If the Candidate is not mechanically eligible for SYSTEM.
    """
    if (
        "normalized_scope" not in review_unit
        or review_unit["system_approval_eligible"] is not True
    ):
        raise ReviewError("SYSTEM review requires exact enum scope evidence")
    approved_claims = dict(review_unit["required_claims"])
    for dimension, canonical_value in review_unit["normalized_scope"].items():
        approved_claims[dimension] = canonical_value
    if not _approved_claims_satisfy_unit(
        review_unit=review_unit, approved_claims=approved_claims,
    ):
        raise ReviewError("SYSTEM review scope does not satisfy contract")
    return approved_claims


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
    scope_contract = semantic["scope_contract"]
    normalized_scope = None
    system_approval_eligible = None
    if scope_contract is not None:
        validate_scope_contract(value=scope_contract)
        if (
            "normalized_scope" not in evidence_check
            or "system_approval_eligible" not in evidence_check
            or "unresolved_scope_dimensions" not in evidence_check
        ):
            raise ReviewError("ReviewUnit Evidence scope binding is absent")
        normalized_scope = dict(evidence_check["normalized_scope"])
        system_approval_eligible = bool(
            evidence_check["system_approval_eligible"]
        )
        if system_approval_eligible and not scope_satisfies_contract(
            contract=scope_contract,
            normalized_scope=normalized_scope,
        ):
            raise ReviewError("ReviewUnit Evidence scope is not approvable")
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
    if normalized_scope is not None:
        substantive["normalized_scope"] = normalized_scope
        substantive["system_approval_eligible"] = system_approval_eligible
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
    if normalized_scope is not None:
        record["normalized_scope"] = normalized_scope
        record["system_approval_eligible"] = system_approval_eligible
    return validate_record(record=record)


def system_review_allowed(*, requirement: Mapping[str, object]) -> bool:
    """Return whether the effective D-06 permits a SYSTEM decision.

    Args:
        requirement: Current verified Requirement Snapshot.

    Returns:
        True only for the user-authorized optional-review policy.
    """
    if "effective_decisions" not in requirement:
        return False
    decisions = requirement["effective_decisions"]
    if not isinstance(decisions, dict) or "D-06" not in decisions:
        return False
    decision = decisions["D-06"]
    if not isinstance(decision, dict) or decision["status"] != "APPROVED":
        return False
    choice = decision["choice"]
    return (
        isinstance(choice, dict)
        and set(choice) == _OPTIONAL_REVIEW_POLICY_FIELDS
        and choice["decision_target"] == "WHOLE_REVIEW_UNIT"
        and choice["binds_selected_competing_unresolved"] is True
        and choice["binds_canonical_and_rendered_context"] is True
        and choice["parallel_effective_decisions"] == "FAIL_CLOSED"
        and choice["human_review_required"] is False
        and choice["system_reviewer_type"] == "SYSTEM"
        and choice["system_approval_policy"]
        == "EVIDENCE_BOUND_AUTO_APPROVE"
    )


def _create_review_decision(
    *,
    review_unit: Mapping[str, object],
    decision: str,
    approved_claims: Mapping[str, object],
    required_claims: Mapping[str, object],
    reviewer_type: str,
    reviewer_id: str,
    decided_at_utc: str,
    reason: str,
    supersedes_decision_id: Optional[str],
) -> Dict[str, object]:
    """Create an immutable review decision bound to rendered context.

    Args:
        review_unit: Unit the human reviewed.
        decision: ``APPROVE`` or ``REJECT``.
        approved_claims: Canonical claims approved as a whole.
        required_claims: Exact Spec-required claims.
        reviewer_type: ``HUMAN`` or the authorized ``SYSTEM`` identity.
        reviewer_id: Stable opaque reviewer identity; OS/model identity is not
            inferred.
        decided_at_utc: Explicit UTC timestamp supplied by the review CLI.
        reason: Human rationale.
        supersedes_decision_id: Prior decision ID or ``None``.

    Returns:
        Strict ``REVIEW_DECISION`` record.

    Raises:
        ReviewError: On invalid reviewer identity, mismatched claims, invalid
            choice, or missing rationale.
    """
    validate_record(record=review_unit)
    if review_unit["status"] != "PENDING":
        raise ReviewError("Review decision requires a PENDING unit")
    if decision not in {"APPROVE", "REJECT"}:
        raise ReviewError("Review decision must be APPROVE or REJECT")
    if reviewer_type not in {"HUMAN", "SYSTEM"}:
        raise ReviewError("Review decision reviewer type is invalid")
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
    if decision == "APPROVE" and not _approved_claims_satisfy_unit(
        review_unit=review_unit, approved_claims=approved_claims,
    ):
        raise ReviewError(
            "Approved scope does not exactly satisfy the ReviewUnit"
        )
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
            "reviewer_type": reviewer_type,
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
        "reviewer_type": reviewer_type,
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
        reviewer_id: Stable opaque human identity.
        decided_at_utc: Explicit UTC timestamp supplied by the review CLI.
        reason: Human rationale.
        supersedes_decision_id: Prior decision ID or ``None``.

    Returns:
        Strict HUMAN ``REVIEW_DECISION`` record.
    """
    return _create_review_decision(
        review_unit=review_unit,
        decision=decision,
        approved_claims=approved_claims,
        required_claims=required_claims,
        reviewer_type="HUMAN",
        reviewer_id=reviewer_id,
        decided_at_utc=decided_at_utc,
        reason=reason,
        supersedes_decision_id=supersedes_decision_id,
    )


def create_system_review_decision(
    *,
    review_unit: Mapping[str, object],
    required_claims: Mapping[str, object],
    decided_at_utc: str,
    requirement: Mapping[str, object],
) -> Dict[str, object]:
    """Append the optional-policy SYSTEM approval without impersonating a human.

    Args:
        review_unit: Pending unit whose Evidence and rendered bytes are bound.
        required_claims: Exact repository Spec claims for the unit.
        decided_at_utc: Terminal AI-attempt UTC timestamp reused as audit time.
        requirement: Current verified Requirement Snapshot owning D-06.

    Returns:
        Strict SYSTEM ``REVIEW_DECISION`` with the full required claim set.

    Raises:
        ReviewError: If optional review is not explicitly authorized.
    """
    # The SYSTEM record makes the no-human path auditable.  It never claims a
    # person approved the result and is unavailable unless D-06 opts in.
    if not system_review_allowed(requirement=requirement):
        raise ReviewError("SYSTEM review is not authorized by D-06")
    approved_claims = _system_approved_claims(review_unit=review_unit)
    return _create_review_decision(
        review_unit=review_unit,
        decision="APPROVE",
        approved_claims=approved_claims,
        required_claims=required_claims,
        reviewer_type="SYSTEM",
        reviewer_id=SYSTEM_REVIEWER_ID,
        decided_at_utc=decided_at_utc,
        reason=SYSTEM_REVIEW_REASON,
        supersedes_decision_id=None,
    )


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
        and not _approved_claims_satisfy_unit(
            review_unit=validated_unit,
            approved_claims=validated_decision["approved_claims"],
        )
    ):
        raise ReviewError(
            "Approved claims do not satisfy the ReviewUnit"
        )
