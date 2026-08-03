"""Create canonical VerifiedObservation records from approved inputs.

Structured facts and HUMAN-reviewed AI claims enter through separate adapters,
then share one observation identity contract. The calculator consumes only
these records or structured candidates that can be converted into them.
"""

from __future__ import annotations

from typing import Dict, Mapping

from .canonical import content_hash, decimal_text, parse_decimal
from .records import validate_record
from .review import validate_decision_binding


class ObservationError(ValueError):
    """Report an unverified value, source, scope, or review binding."""


def scope_key(*, scope: Mapping[str, object]) -> str:
    """Return the unambiguous canonical identity of a scope object.

    Args:
        scope: Non-empty canonical scope mapping.

    Returns:
        Content hash of the exact scope structure.
    """
    if not isinstance(scope, dict) or not scope:
        raise ObservationError("Observation scope must be a non-empty object")
    return content_hash(value=dict(scope))


def _build_observation(
    *,
    metric_id: str,
    semantic_role: str,
    company_id: str,
    period_start: str,
    period_end: str,
    scope: Mapping[str, object],
    value: str,
    unit: str,
    quality: str,
    source_binding: Mapping[str, object],
    approval_effect_hash: str,
) -> Dict[str, object]:
    """Build one strict observation after path-specific checks pass.

    Args:
        metric_id: Metric whose input/result this observation supports.
        semantic_role: Spec role supplied to the calculator.
        company_id: Logical company identity.
        period_start: Inclusive ISO period start.
        period_end: Inclusive ISO period end.
        scope: Canonical approved scope.
        value: Canonical fixed-point value.
        unit: Canonical unit.
        quality: EXACT or APPROX.
        source_binding: Portable exact evidence identity.
        approval_effect_hash: HUMAN approval effect for AI claims, or an empty
            string for deterministic structured observations.

    Returns:
        Strict VERIFIED_OBSERVATION record.
    """
    required_text = {
        "company_id": company_id,
        "period_end": period_end,
        "period_start": period_start,
        "metric_id": metric_id,
        "semantic_role": semantic_role,
        "unit": unit,
    }
    missing = sorted(key for key in required_text if not required_text[key])
    if missing:
        raise ObservationError(
            "Observation fields are empty: {}".format(",".join(missing))
        )
    if quality not in {"EXACT", "APPROX"}:
        raise ObservationError("Observation quality is invalid")
    normalized_value = decimal_text(value=parse_decimal(value=value))
    canonical_scope = dict(scope)
    identity = {
        "semantic_role": semantic_role,
        "metric_id": metric_id,
        "company_id": company_id,
        "period_start": period_start,
        "period_end": period_end,
        "scope": canonical_scope,
        "scope_key": scope_key(scope=canonical_scope),
        "value": normalized_value,
        "unit": unit,
        "source_binding": dict(source_binding),
    }
    record = dict(identity)
    record.update(
        {
            "record_type": "VERIFIED_OBSERVATION",
            "observation_id": content_hash(value=identity),
            "quality": quality,
            "approval_effect_hash": approval_effect_hash,
        }
    )
    return validate_record(record=record)


def structured_observation(
    *,
    metric_id: str,
    semantic_role: str,
    company_id: str,
    period_start: str,
    period_end: str,
    scope: Mapping[str, object],
    value: str,
    unit: str,
    quality: str,
    source_binding: Mapping[str, object],
) -> Dict[str, object]:
    """Convert one deterministically selected structured fact.

    Args:
        metric_id: Metric supported by the selected fact.
        semantic_role: Compiled input/component role.
        company_id: Logical company identity.
        period_start: Target period start.
        period_end: Target period end.
        scope: Canonical target scope.
        value: Fixed-point structured value.
        unit: Canonical source unit.
        quality: Compiled quality.
        source_binding: Existing SEC SourceReference/fact locator binding.

    Returns:
        Structured VerifiedObservation without a HUMAN approval effect.
    """
    return _build_observation(
        metric_id=metric_id,
        semantic_role=semantic_role,
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        scope=scope,
        value=value,
        unit=unit,
        quality=quality,
        source_binding=source_binding,
        approval_effect_hash="",
    )


def reviewed_observation(
    *,
    metric_id: str,
    role: str,
    company_id: str,
    period_start: str,
    period_end: str,
    canonical_unit: str,
    candidate: Mapping[str, object],
    evidence_check: Mapping[str, object],
    review_unit: Mapping[str, object],
    decision: Mapping[str, object],
    source_reference: Mapping[str, object],
    derived_asset_id: str,
    quality: str,
) -> Dict[str, object]:
    """Materialize one AI claim only after mechanical and HUMAN approval.

    Args:
        metric_id: Metric projected from the reviewed role.
        role: Selected role in the joint review unit.
        company_id: Logical company identity.
        period_start: Target period start.
        period_end: Target period end.
        canonical_unit: Spec canonical unit after numeric normalization.
        candidate: Immutable Candidate.
        evidence_check: PASS check bound to the Candidate.
        review_unit: Whole-unit binding for the reviewed Candidate/context.
        decision: Effective APPROVE HUMAN decision.
        source_reference: Exact source chosen for this observation.
        derived_asset_id: Table-grid identity containing the locator.
        quality: Compiled observation quality.

    Returns:
        Review-bound VerifiedObservation.

    Raises:
        ObservationError: On any stale or rejected binding.
    """
    for record in (
        candidate,
        evidence_check,
        review_unit,
        decision,
        source_reference,
    ):
        validate_record(record=record)
    if evidence_check["candidate_hash"] != candidate["candidate_hash"]:
        raise ObservationError("EvidenceCheck binds a different Candidate")
    if evidence_check["status"] != "PASS":
        raise ObservationError("Rejected evidence cannot become verified")
    if review_unit["evidence_check_id"] != evidence_check["evidence_check_id"]:
        raise ObservationError("ReviewUnit binds a different EvidenceCheck")
    for field in (
        "selected",
        "competing_candidates",
        "unresolved_competing_claims",
    ):
        if review_unit[field] != candidate[field]:
            raise ObservationError("ReviewUnit Candidate content differs")
    try:
        validate_decision_binding(
            review_unit=review_unit, decision=decision,
        )
    except ValueError as error:
        raise ObservationError("ReviewDecision binding is stale") from error
    if (
        decision["decision"] != "APPROVE"
        or decision["reviewer_type"] != "HUMAN"
    ):
        raise ObservationError("AI claim requires an effective HUMAN approval")
    if role not in candidate["selected"]:
        raise ObservationError("Reviewed role is absent from Candidate")
    if role not in evidence_check["normalized_values"]:
        raise ObservationError("EvidenceCheck lacks normalized role value")
    if (
        source_reference["source_reference_id"]
        not in candidate["source_reference_ids"]
    ):
        raise ObservationError("SourceReference is outside Candidate bindings")
    claim = candidate["selected"][role]
    if claim["locator"]["derived_asset_id"] != derived_asset_id:
        raise ObservationError("Claim locator binds a different DerivedAsset")
    source_binding = {
        "raw_asset_id": source_reference["raw_asset_id"],
        "source_reference_id": source_reference["source_reference_id"],
        "accession": source_reference["accession"],
        "document_name": source_reference["document_name"],
        "source_role": source_reference["source_role"],
        "derived_asset_id": derived_asset_id,
        "locator": dict(claim["locator"]),
    }
    return _build_observation(
        metric_id=metric_id,
        semantic_role=role,
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        scope=decision["approved_claims"],
        value=evidence_check["normalized_values"][role],
        unit=canonical_unit,
        quality=quality,
        source_binding=source_binding,
        approval_effect_hash=str(decision["approval_effect_hash"]),
    )
