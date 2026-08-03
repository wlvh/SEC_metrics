"""Resolve compiled roles and calculate deterministic metric results.

The runtime consumes only compiled Spec data, structured candidates, and
verified observations. It contains no metric, company, industry, or scope-word
branches; all business ordering, concepts, guards, and tolerances arrive as
data.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .canonical import (
    CanonicalError,
    arithmetic_context,
    content_hash,
    decimal_text,
)
from .canonical import execution_semantics_hash, parse_decimal
from .constraints import ConstraintError, evaluate_expression
from .constraints import observations_share_fields
from .observations import scope_key, structured_observation
from .records import metric_result_contract_hash, validate_record


FACT_FIELDS = {
    "accession",
    "concept",
    "duration_days",
    "entity",
    "fact_id",
    "filed",
    "fiscal_period",
    "form",
    "period_end",
    "period_start",
    "source_binding",
    "unit",
    "value",
}


class CalculationError(ValueError):
    """Report invalid calculator input or an unsupported compiled contract."""


class BranchRejected(CalculationError):
    """Reject one ordered branch while allowing the next declared fallback."""

    def __init__(self, *, reason_code: str, details: str) -> None:
        """Create a stable branch rejection.

        Args:
            reason_code: Machine-readable rejection reason.
            details: Human-readable audit detail.
        """
        super().__init__(details)
        self.reason_code = reason_code
        self.details = details


def _decimal_value(*, value: object) -> Decimal:
    """Return a contract Decimal from a structured candidate value.

    Args:
        value: Decimal or fixed-point string.

    Returns:
        Finite Decimal.

    Raises:
        CalculationError: On unsupported or out-of-policy values.
    """
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CalculationError("Structured value is non-finite")
        try:
            return parse_decimal(value=format(value, "f"))
        except CanonicalError as error:
            raise CalculationError(
                "Structured value violates Decimal policy"
            ) from error
    if not isinstance(value, str):
        raise CalculationError("Structured value must be fixed-point text")
    try:
        return parse_decimal(value=value)
    except CanonicalError as error:
        raise CalculationError(
            "Structured value violates Decimal policy"
        ) from error


def _validate_fact(*, fact: Mapping[str, object]) -> Dict[str, object]:
    """Validate one strict structured candidate fact.

    Args:
        fact: Candidate fact mapping.

    Returns:
        Isolated fact with its value converted to Decimal.

    Raises:
        CalculationError: On schema drift or invalid field types.
    """
    if set(fact) != FACT_FIELDS:
        raise CalculationError("Structured fact fields are not exact")
    for key in (
        "accession",
        "concept",
        "entity",
        "fact_id",
        "filed",
        "fiscal_period",
        "form",
        "period_end",
        "period_start",
        "unit",
    ):
        if not isinstance(fact[key], str) or not fact[key]:
            raise CalculationError(
                "Structured fact field is empty: {}".format(key)
            )
    if type(fact["duration_days"]) is not int:
        raise CalculationError("Structured fact duration_days must be int")
    if not isinstance(fact["source_binding"], dict):
        raise CalculationError(
            "Structured fact source_binding must be an object"
        )
    for key in ("accession", "entity"):
        if key not in fact["source_binding"]:
            raise CalculationError(
                "Structured source binding lacks {}".format(key)
            )
        if fact["source_binding"][key] != fact[key]:
            raise CalculationError(
                "Structured source binding {} differs".format(key)
            )
    output = dict(fact)
    output["value"] = _decimal_value(value=fact["value"])
    return output


def _fact_observation(
    *,
    role: str,
    fact: Mapping[str, object],
    target: Mapping[str, object],
    quality: str,
) -> Dict[str, object]:
    """Materialize one selected structured fact as an observation.

    Args:
        role: Compiled semantic role.
        fact: Validated selected fact.
        target: Exact calculation target and canonical scope.
        quality: Compiled EXACT or APPROX quality.

    Returns:
        VerifiedObservation with fact-level audit fields in source_binding.
    """
    source_binding = dict(fact["source_binding"])
    source_binding.update(
        {
            "concept": fact["concept"],
            "duration_days": fact["duration_days"],
            "fact_id": fact["fact_id"],
            "filed": fact["filed"],
            "fiscal_period": fact["fiscal_period"],
            "form": fact["form"],
        }
    )
    return structured_observation(
        metric_id=str(target["metric_id"]),
        semantic_role=role,
        company_id=str(target["company_id"]),
        period_start=str(fact["period_start"]),
        period_end=str(fact["period_end"]),
        scope=target["scope"],
        value=decimal_text(value=fact["value"]),
        unit=str(fact["unit"]),
        quality=quality,
        source_binding=source_binding,
    )


def _concept_local_name(*, concept: str) -> str:
    """Return the local concept token while preserving exact priority order.

    Args:
        concept: Qualified or local concept.

    Returns:
        Local token used only to bridge existing unqualified inventories.
    """
    return concept.split(":", 1)[1] if ":" in concept else concept


def _approved_concept_matches(*, approved: str, candidate: str) -> bool:
    """Match an exact concept or an existing unqualified inventory token.

    Args:
        approved: Spec-approved qualified or local concept.
        candidate: Structured inventory concept.

    Returns:
        True for exact identity, or when an unqualified candidate equals the
        approved local token. A different explicit namespace never matches.
    """
    return candidate == approved or (
        ":" not in candidate
        and candidate == _concept_local_name(concept=approved)
    )


def _select_structured_fact(
    *,
    role_spec: Mapping[str, object],
    facts: Sequence[Mapping[str, object]],
    target: Mapping[str, object],
) -> Dict[str, object]:
    """Apply ordered concept and legacy-companyfacts tie-break semantics.

    Args:
        role_spec: Approved concepts and cardinality.
        facts: Structured candidate facts.
        target: Exact target period/accession/entity.

    Returns:
        Unique selected fact.

    Raises:
        BranchRejected: On missing or ambiguous candidate.
        CalculationError: On malformed role or target.
    """
    required = {"approved_concepts", "cardinality"}
    optional = {"quality"}
    if not isinstance(role_spec, dict) or not required.issubset(role_spec):
        raise CalculationError("Structured role lacks concept/cardinality")
    if set(role_spec) - (required | optional):
        raise CalculationError("Structured role has unknown fields")
    concepts = role_spec["approved_concepts"]
    if not isinstance(concepts, list) or not concepts:
        raise CalculationError("Structured role concepts must be ordered")
    if role_spec["cardinality"] not in {"exactly_one", "zero_or_one"}:
        raise CalculationError("Unsupported structured role cardinality")
    required_target = {"period_start", "period_end", "accession", "entity"}
    if not required_target.issubset(target):
        raise CalculationError("Target context is incomplete")
    validated = [_validate_fact(fact=fact) for fact in facts]
    for approved in concepts:
        if not isinstance(approved, str) or not approved:
            raise CalculationError("Approved concept is empty")
        candidates = [
            fact
            for fact in validated
            if _approved_concept_matches(
                approved=approved, candidate=str(fact["concept"]),
            )
            and fact["period_start"] == target["period_start"]
            and fact["period_end"] == target["period_end"]
            and fact["entity"] == target["entity"]
            and str(fact["form"]).startswith("10-K")
            and fact["fiscal_period"] == "FY"
        ]
        if not candidates:
            continue
        target_accession = [
            fact
            for fact in candidates
            if fact["accession"] == target["accession"]
        ]
        if target_accession:
            candidates = target_accession
        candidates = sorted(
            candidates,
            key=lambda fact: (
                str(fact["filed"]),
                str(fact["accession"]),
                str(fact["unit"]),
            ),
            reverse=True,
        )
        best_key = (
            str(candidates[0]["filed"]),
            str(candidates[0]["accession"]),
            str(candidates[0]["unit"]),
        )
        tied = [
            fact
            for fact in candidates
            if (str(fact["filed"]), str(fact["accession"]), str(fact["unit"]),)
            == best_key
        ]
        # Exact duplicate rows are harmless, but any distinct provenance or
        # fact field after the declared tie-break remains ambiguous.
        substantive = {content_hash(value=fact) for fact in tied}
        if len(substantive) != 1:
            raise BranchRejected(
                reason_code="AMBIGUOUS_CANDIDATE",
                details="Structured tie-break left multiple facts",
            )
        return tied[0]
    raise BranchRejected(
        reason_code="MISSING_CANDIDATE",
        details="No approved structured fact matched the target context",
    )


def _guard_fields(*, guard: str) -> Tuple[str, ...]:
    """Map a generic guard name to explicit candidate fields.

    Args:
        guard: Compiled guard name.

    Returns:
        Fields that must be equal.

    Raises:
        CalculationError: On unknown guard.
    """
    mapping = {
        "same_accession": ("accession",),
        "same_period": ("period_start", "period_end"),
        "same_entity": ("entity",),
        "compatible_units": ("unit",),
    }
    if guard not in mapping:
        raise CalculationError("Unknown equality guard: {}".format(guard))
    return mapping[guard]


def _apply_equality_guards(
    *, guards: Sequence[object], observations: Sequence[Mapping[str, object]]
) -> None:
    """Reject a branch whose declared source/period/unit guards fail.

    Args:
        guards: Ordered guard names.
        observations: Facts participating in the branch.

    Raises:
        BranchRejected: On a mismatch.
        CalculationError: On malformed/unknown guard.
    """
    guard_views = []
    for observation in observations:
        view = dict(observation)
        if "source_binding" in observation:
            source_binding = observation["source_binding"]
            if not isinstance(source_binding, dict):
                raise CalculationError(
                    "Observation source_binding is malformed"
                )
            for field in ("accession", "entity"):
                if field in source_binding:
                    view[field] = source_binding[field]
        guard_views.append(view)
    for guard in guards:
        if not isinstance(guard, str):
            raise CalculationError("Branch equality guard must be a string")
        fields = _guard_fields(guard=guard)
        try:
            passed, reason = observations_share_fields(
                observations=guard_views, fields=fields,
            )
        except ConstraintError as error:
            raise CalculationError(
                "Branch guard input is incomplete"
            ) from error
        if not passed:
            raise BranchRejected(
                reason_code=reason, details="Branch guard failed"
            )


def _resolve_derived_branch(
    *,
    role: str,
    branch: Mapping[str, object],
    facts: Sequence[Mapping[str, object]],
    target: Mapping[str, object],
    available_values: Mapping[str, Decimal],
    trace_steps: List[Dict[str, object]],
) -> Dict[str, object]:
    """Resolve named component facts and execute one declared branch.

    Args:
        role: Top-level role produced by this branch.
        branch: Derived-role contract.
        facts: Structured candidate facts.
        target: Exact target context.
        available_values: Previously resolved top-level roles.
        trace_steps: Mutable audit list owned by the caller.

    Returns:
        Value, quality, and participating observations.

    Raises:
        BranchRejected: On missing facts, failed guards, or failed cross-check.
        CalculationError: On malformed branch semantics.
    """
    required = {"op", "inputs", "args", "quality", "guards"}
    optional = {"quality_reason", "cross_check"}
    if not required.issubset(branch) or set(branch) - (required | optional):
        raise CalculationError("Derived branch fields are not supported")
    inputs = branch["inputs"]
    arguments = branch["args"]
    if not isinstance(inputs, dict) or not isinstance(arguments, list):
        raise CalculationError("Derived branch inputs/args are malformed")
    component_values: Dict[str, Decimal] = {}
    selected_facts: List[Dict[str, object]] = []
    selected_observations: List[Dict[str, object]] = []
    for component_role in inputs:
        fact = _select_structured_fact(
            role_spec=inputs[component_role], facts=facts, target=target,
        )
        component_values[str(component_role)] = fact["value"]
        selected_facts.append(fact)
        selected_observations.append(
            _fact_observation(
                role=str(component_role),
                fact=fact,
                target=target,
                quality="EXACT",
            )
        )
    _apply_equality_guards(
        guards=branch["guards"], observations=selected_observations,
    )
    expression = {"op": branch["op"], "args": list(arguments)}
    try:
        value = evaluate_expression(
            expression=expression, values=component_values,
        )
    except ConstraintError as error:
        raise BranchRejected(
            reason_code="ARITHMETIC_FAILED", details=str(error),
        ) from error
    selection_step = {
        "event": "DERIVED_BRANCH_SELECTED",
        "role": role,
        "operation": branch["op"],
        "args": list(arguments),
        "component_observation_ids": [
            observation["observation_id"]
            for observation in selected_observations
        ],
        "component_values": {
            key: decimal_text(value=component_values[key])
            for key in component_values
        },
        "value": decimal_text(value=value),
        "quality": branch["quality"],
    }
    cross_check_steps: List[Dict[str, object]] = []
    if "cross_check" in branch:
        try:
            cross_fact = _evaluate_cross_check(
                cross_check=branch["cross_check"],
                facts=facts,
                target=target,
                available_values=available_values,
                branch_value=value,
                selected=selected_facts,
                trace_steps=cross_check_steps,
            )
        except BranchRejected:
            # A rejected branch keeps its mechanical cross-check evidence but
            # never claims that its discarded component observations won.
            trace_steps.extend(cross_check_steps)
            raise
        if cross_fact is not None:
            selected_observations.append(
                _fact_observation(
                    role=str(branch["cross_check"]["role"]),
                    fact=cross_fact,
                    target=target,
                    quality="EXACT",
                )
            )
    # Commit branch identity only after every guard and optional cross-check
    # accepts it; this keeps Trace component IDs inside the returned graph.
    trace_steps.append(selection_step)
    trace_steps.extend(cross_check_steps)
    return {
        "value": value,
        "quality": branch["quality"],
        "observations": selected_observations,
    }


def _evaluate_cross_check(
    *,
    cross_check: Mapping[str, object],
    facts: Sequence[Mapping[str, object]],
    target: Mapping[str, object],
    available_values: Mapping[str, Decimal],
    branch_value: Decimal,
    selected: Sequence[Mapping[str, object]],
    trace_steps: List[Dict[str, object]],
) -> Optional[Dict[str, object]]:
    """Evaluate one optional cross-check with frozen denominator semantics.

    Args:
        cross_check: Compiled optional check.
        facts: Structured candidates.
        target: Exact target context.
        available_values: Previously resolved top-level roles.
        branch_value: Actual value produced by the current generic branch.
        selected: Facts already used by the branch.
        trace_steps: Mutable trace.

    Raises:
        BranchRejected: When an available compatible check exceeds tolerance.
        CalculationError: On malformed check configuration.

    Returns:
        Selected compatible cross-check fact, or ``None`` when unavailable or
        explicitly incompatible.
    """
    required = {
        "when_available",
        "role",
        "approved_concepts",
        "cardinality",
        "expression",
        "denominator",
        "relative_tolerance",
    }
    if (
        set(cross_check) != required
        or cross_check["when_available"] is not True
    ):
        raise CalculationError("Cross-check fields are not exact")
    role = str(cross_check["role"])
    role_spec = {
        "approved_concepts": cross_check["approved_concepts"],
        "cardinality": cross_check["cardinality"],
    }
    try:
        cross_fact = _select_structured_fact(
            role_spec=role_spec, facts=facts, target=target,
        )
    except BranchRejected as error:
        if error.reason_code == "MISSING_CANDIDATE":
            trace_steps.append({
                "event": "CROSS_CHECK_UNAVAILABLE",
                "role": role,
            })
            return None
        raise
    compatible, reason = observations_share_fields(
        observations=[*selected, cross_fact],
        fields=("accession", "period_start", "period_end", "entity", "unit"),
    )
    if not compatible:
        trace_steps.append(
            {
                "event": "CROSS_CHECK_INCOMPATIBLE",
                "role": role,
                "reason": reason,
            }
        )
        return None
    expression = cross_check["expression"]
    if not isinstance(expression, dict) or set(expression) != {
        "expected",
        "actual",
    }:
        raise CalculationError("Cross-check expression fields are not exact")
    actual_role = expression["actual"]
    if not isinstance(actual_role, str) or not actual_role:
        raise CalculationError("Cross-check actual must name the current role")
    values = dict(available_values)
    values[role] = cross_fact["value"]
    values[actual_role] = branch_value
    try:
        expected = evaluate_expression(
            expression=expression["expected"], values=values,
        )
        actual = evaluate_expression(
            expression=expression["actual"], values=values,
        )
        tolerance = parse_decimal(value=str(cross_check["relative_tolerance"]))
    except (ConstraintError, CanonicalError) as error:
        raise CalculationError("Cross-check expression is invalid") from error
    denominator = abs(actual) if actual != 0 else Decimal("1")
    with arithmetic_context():
        relative_error = abs(expected - actual) / denominator
    trace_steps.append(
        {
            "event": "CROSS_CHECK_EVALUATED",
            "expected": decimal_text(value=expected),
            "actual": decimal_text(value=actual),
            "denominator": decimal_text(value=denominator),
            "relative_error": decimal_text(value=relative_error),
            "tolerance": decimal_text(value=tolerance),
        }
    )
    if relative_error > tolerance:
        raise BranchRejected(
            reason_code="CROSS_CHECK_FAILED",
            details="Cross-check exceeds declared relative tolerance",
        )
    return cross_fact


def _resolve_input_role(
    *,
    role: str,
    role_spec: Mapping[str, object],
    facts: Sequence[Mapping[str, object]],
    observations: Sequence[Mapping[str, object]],
    target: Mapping[str, object],
    resolved_values: Mapping[str, Decimal],
    trace_steps: List[Dict[str, object]],
) -> Dict[str, object]:
    """Resolve one top-level role from reuse, direct, or ordered branches.

    Args:
        role: Top-level role name.
        role_spec: Compiled role semantics.
        facts: Structured candidates.
        observations: Verified reusable observations.
        target: Exact result grain.
        resolved_values: Earlier role values.
        trace_steps: Mutable trace.

    Returns:
        Value, quality, observations, and input IDs.
    """
    if "reuse_metric_observation" in role_spec:
        expected_fields = {"reuse_metric_observation", "cardinality"}
        if (
            set(role_spec) != expected_fields
            or role_spec["cardinality"] != "exactly_one"
        ):
            raise CalculationError("Reuse role contract is invalid")
        validated_observations = []
        for observation in observations:
            validated = validate_record(record=observation)
            if validated["record_type"] != "VERIFIED_OBSERVATION":
                raise CalculationError("Reusable input is not an observation")
            validated_observations.append(validated)
        matches = [
            observation
            for observation in validated_observations
            if observation["metric_id"]
            == role_spec["reuse_metric_observation"]
            and observation["company_id"] == target["company_id"]
            and observation["period_start"] == target["period_start"]
            and observation["period_end"] == target["period_end"]
            and observation["scope_key"] == target["scope_key"]
        ]
        if len(matches) != 1:
            raise BranchRejected(
                reason_code="REUSE_CARDINALITY_FAILED",
                details="Reusable metric observation is not unique",
            )
        value = _decimal_value(value=matches[0]["value"])
        trace_steps.append(
            {
                "event": "REUSED_OBSERVATION",
                "role": role,
                "observation_id": matches[0]["observation_id"],
                "value": decimal_text(value=value),
            }
        )
        return {
            "value": value,
            "quality": matches[0]["quality"],
            "observations": [dict(matches[0])],
            "input_ids": [matches[0]["observation_id"]],
        }
    if "structured_role" in role_spec:
        if set(role_spec) != {"structured_role"}:
            raise CalculationError(
                "Direct structured role fields are not exact"
            )
        fact = _select_structured_fact(
            role_spec=role_spec["structured_role"], facts=facts, target=target,
        )
        quality = role_spec["structured_role"]["quality"]
        observation = _fact_observation(
            role=role, fact=fact, target=target, quality=str(quality),
        )
        trace_steps.append(
            {
                "event": "DIRECT_STRUCTURED_SELECTED",
                "role": role,
                "observation_id": observation["observation_id"],
                "value": decimal_text(value=fact["value"]),
                "quality": quality,
            }
        )
        return {
            "value": fact["value"],
            "quality": quality,
            "observations": [observation],
            "input_ids": [observation["observation_id"]],
        }
    if set(role_spec) != {"choose_first"} or not isinstance(
        role_spec["choose_first"], list
    ):
        raise CalculationError(
            "Top-level role must declare ordered choose_first"
        )
    for index, branch_wrapper in enumerate(role_spec["choose_first"]):
        if not isinstance(branch_wrapper, dict) or len(branch_wrapper) != 1:
            raise CalculationError("choose_first branch must have one kind")
        try:
            if "extraction_role" in branch_wrapper:
                fact = _select_structured_fact(
                    role_spec=branch_wrapper["extraction_role"],
                    facts=facts,
                    target=target,
                )
                observation = _fact_observation(
                    role=role,
                    fact=fact,
                    target=target,
                    quality=str(branch_wrapper["extraction_role"]["quality"]),
                )
                result = {
                    "value": fact["value"],
                    "quality": branch_wrapper["extraction_role"]["quality"],
                    "observations": [observation],
                    "input_ids": [observation["observation_id"]],
                }
            elif "derived_role" in branch_wrapper:
                result = _resolve_derived_branch(
                    role=role,
                    branch=branch_wrapper["derived_role"],
                    facts=facts,
                    target=target,
                    available_values=resolved_values,
                    trace_steps=trace_steps,
                )
                result["input_ids"] = [
                    observation["observation_id"]
                    for observation in result["observations"]
                ]
            else:
                raise CalculationError("Unknown choose_first branch kind")
            trace_steps.append(
                {
                    "event": "CHOOSE_FIRST_ACCEPTED",
                    "role": role,
                    "branch_index": index,
                }
            )
            return result
        except BranchRejected as error:
            trace_steps.append(
                {
                    "event": "CHOOSE_FIRST_REJECTED",
                    "role": role,
                    "branch_index": index,
                    "reason_code": error.reason_code,
                    "details": error.details,
                }
            )
    raise BranchRejected(
        reason_code="ALL_BRANCHES_REJECTED",
        details="Every declared choose_first branch was rejected",
    )


def metric_is_applicable(
    *, applicability: Mapping[str, object], traits: Sequence[str]
) -> bool:
    """Evaluate bounded all/none trait applicability.

    Args:
        applicability: Compiled all/none traits.
        traits: Company traits derived from existing configuration.

    Returns:
        Whether all required and no forbidden traits are present.
    """
    trait_set = set(traits)
    return set(applicability["all"]).issubset(trait_set) and not (
        set(applicability["none"]) & trait_set
    )


def _duration_out_of_range(
    *, observations: Sequence[Mapping[str, object]], minimum: int, maximum: int
) -> bool:
    """Check declared annual-duration bounds on structured observations.

    Args:
        observations: Resolved top-level/component observations.
        minimum: Inclusive minimum duration days.
        maximum: Inclusive maximum duration days.

    Returns:
        Whether any observation that carries duration evidence is outside the
        declared interval.

    Raises:
        CalculationError: When present duration evidence is not an integer.
    """
    for observation in observations:
        binding = observation["source_binding"]
        if "duration_days" not in binding:
            continue
        duration = binding["duration_days"]
        if type(duration) is not int:
            raise CalculationError("Observation duration_days must be int")
        if not minimum <= duration <= maximum:
            return True
    return False


def _result_and_trace(
    *,
    compiled_spec: Mapping[str, object],
    target: Mapping[str, object],
    applicability: str,
    quality: str,
    publication: str,
    reason_code: str,
    value: Optional[Decimal],
    result_unit: Optional[str],
    trace_steps: Sequence[Mapping[str, object]],
    input_ids: Sequence[str],
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Build mutually bound MetricResult and ExecutionTrace records.

    Args:
        compiled_spec: Compiled Spec wrapper.
        target: Result grain.
        applicability: APPLICABLE or N_A_STRUCTURAL.
        quality: EXACT, APPROX, NOT_MEANINGFUL, or NONE.
        publication: PUBLISHED or WITHHELD.
        reason_code: Stable result reason.
        value: Canonical Decimal or ``None``.
        result_unit: Exact output unit, or ``None`` with a null value.
        trace_steps: Complete ordered execution trace.
        input_ids: Source observation/fact identities.

    Returns:
        Strict result and trace records.
    """
    semantic = compiled_spec["compiled"]
    if (value is None) != (result_unit is None):
        raise CalculationError("Result value/unit nullability differs")
    if result_unit is not None and not result_unit:
        raise CalculationError("Result unit is empty")
    if ("accession" in target) != ("entity" in target):
        raise CalculationError("Calculation source target is incomplete")
    calculation_target = {
        "accession": (
            target["accession"] if "accession" in target else None
        ),
        "company_id": target["company_id"],
        "entity": target["entity"] if "entity" in target else None,
        "period_end": target["period_end"],
        "period_start": target["period_start"],
        "scope": dict(target["scope"]),
        "scope_key": target["scope_key"],
    }
    value_text = decimal_text(value=value) if value is not None else None
    result_contract = {
        "company_id": target["company_id"],
        "metric_id": semantic["metric_id"],
        "period_start": target["period_start"],
        "period_end": target["period_end"],
        "scope_key": target["scope_key"],
        "spec_closure_hash": compiled_spec["spec_closure_hash"],
        "applicability": applicability,
        "quality": quality,
        "publication": publication,
        "reason_code": reason_code,
        "value": value_text,
        "unit": result_unit,
    }
    trace_body = {
        "metric_id": semantic["metric_id"],
        "calculation_target": calculation_target,
        "input_observation_ids": list(input_ids),
        "steps": [dict(step) for step in trace_steps],
        "quality": quality,
        "result": value_text,
        "spec_closure_hash": compiled_spec["spec_closure_hash"],
        "execution_semantics_hash": execution_semantics_hash(),
        "result_contract_hash": metric_result_contract_hash(
            result=result_contract,
        ),
    }
    trace_id = content_hash(value=trace_body)
    trace = {
        "record_type": "EXECUTION_TRACE",
        "trace_id": trace_id,
        "metric_id": semantic["metric_id"],
        "calculation_target": calculation_target,
        "input_observation_ids": list(input_ids),
        "steps": [dict(step) for step in trace_steps],
        "quality": quality,
        "result": value_text,
        "spec_closure_hash": compiled_spec["spec_closure_hash"],
        "execution_semantics_hash": execution_semantics_hash(),
        "result_contract_hash": trace_body["result_contract_hash"],
    }
    result_body = dict(result_contract)
    result_body["trace_id"] = trace_id
    result = dict(result_body)
    result["record_type"] = "METRIC_RESULT"
    result["result_id"] = content_hash(value=result_body)
    return validate_record(record=result), validate_record(record=trace)


def calculate_metric(
    *,
    compiled_spec: Mapping[str, object],
    target: Mapping[str, object],
    company_traits: Sequence[str],
    structured_facts: Sequence[Mapping[str, object]],
    verified_observations: Sequence[Mapping[str, object]],
) -> Tuple[Dict[str, object], Dict[str, object], List[Dict[str, object]]]:
    """Calculate one metric entirely from compiled declarative semantics.

    Args:
        compiled_spec: Output of ``compile_spec``.
        target: Exact company/period/accession/entity/scope result grain.
        company_traits: Config-projected traits.
        structured_facts: Candidate facts.
        verified_observations: Previously verified reusable observations.

    Returns:
        Strict MetricResult, complete ExecutionTrace, and every selected
        VerifiedObservation created for this calculation.
    """
    required_target = {
        "company_id",
        "period_start",
        "period_end",
        "accession",
        "entity",
        "scope",
        "scope_key",
    }
    if set(target) != required_target:
        raise CalculationError("Calculation target fields are not exact")
    if target["scope_key"] != scope_key(scope=target["scope"]):
        raise CalculationError("Calculation target scope_key differs")
    semantic = compiled_spec["compiled"]
    execution_target = dict(target)
    execution_target["metric_id"] = semantic["metric_id"]
    if not metric_is_applicable(
        applicability=semantic["applicability"], traits=company_traits,
    ):
        result, trace = _result_and_trace(
            compiled_spec=compiled_spec,
            target=execution_target,
            applicability="N_A_STRUCTURAL",
            quality="NONE",
            publication="PUBLISHED",
            reason_code="TRAIT_NOT_APPLICABLE",
            value=None,
            result_unit=None,
            trace_steps=[{"event": "N_A_STRUCTURAL"}],
            input_ids=[],
        )
        return result, trace, []
    resolved: Dict[str, Decimal] = {}
    qualities: List[str] = []
    all_observations: List[Mapping[str, object]] = []
    input_ids: List[str] = []
    trace_steps: List[Dict[str, object]] = []
    try:
        for role in semantic["inputs"]:
            role_result = _resolve_input_role(
                role=str(role),
                role_spec=semantic["inputs"][role],
                facts=structured_facts,
                observations=verified_observations,
                target=execution_target,
                resolved_values=resolved,
                trace_steps=trace_steps,
            )
            resolved[str(role)] = role_result["value"]
            qualities.append(str(role_result["quality"]))
            all_observations.extend(role_result["observations"])
            input_ids.extend(str(item) for item in role_result["input_ids"])
        for guard in semantic["top_level_guards"]:
            if isinstance(guard, str) and guard in {
                "same_accession",
                "same_period",
                "same_entity",
                "compatible_units",
            }:
                _apply_equality_guards(
                    guards=[guard], observations=all_observations,
                )
            elif isinstance(guard, dict) and set(guard) == {"annual_duration"}:
                limits = guard["annual_duration"]
                if not isinstance(limits, list) or len(limits) != 2:
                    raise CalculationError(
                        "annual_duration guard is malformed"
                    )
                minimum, maximum = limits
                if type(minimum) is not int or type(maximum) is not int:
                    raise CalculationError(
                        "annual_duration limits must be int"
                    )
                if _duration_out_of_range(
                    observations=all_observations,
                    minimum=minimum,
                    maximum=maximum,
                ):
                    result, trace = _result_and_trace(
                        compiled_spec=compiled_spec,
                        target=target,
                        applicability="APPLICABLE",
                        quality="NOT_MEANINGFUL",
                        publication="PUBLISHED",
                        reason_code="ANNUAL_DURATION_OUT_OF_RANGE",
                        value=None,
                        result_unit=None,
                        trace_steps=trace_steps,
                        input_ids=input_ids,
                    )
                    return (
                        result,
                        trace,
                        [dict(item) for item in all_observations],
                    )
            elif guard == "denominator_nonzero":
                continue
            else:
                raise CalculationError("Unknown top-level guard")
        formula = semantic["formula"]
        # Guard the declared denominator before division so zero remains a
        # meaningful terminal business state instead of an arithmetic error.
        if "denominator_nonzero" in semantic["top_level_guards"]:
            formula_args = formula["args"] if isinstance(formula, dict) else []
            denominator_expression = formula_args[-1] if formula_args else None
            if denominator_expression is not None:
                denominator = evaluate_expression(
                    expression=denominator_expression, values=resolved,
                )
                if denominator == 0:
                    result, trace = _result_and_trace(
                        compiled_spec=compiled_spec,
                        target=target,
                        applicability="APPLICABLE",
                        quality="NOT_MEANINGFUL",
                        publication="PUBLISHED",
                        reason_code="DENOMINATOR_ZERO",
                        value=None,
                        result_unit=None,
                        trace_steps=trace_steps,
                        input_ids=input_ids,
                    )
                    return (
                        result,
                        trace,
                        [dict(item) for item in all_observations],
                    )
        if isinstance(formula, str) and formula in resolved:
            value = resolved[formula]
        else:
            value = evaluate_expression(expression=formula, values=resolved)
        quality = "APPROX" if "APPROX" in qualities else "EXACT"
        trace_steps.append(
            {
                "event": "FORMULA_RESULT",
                "formula": formula,
                "resolved_values": {
                    role: decimal_text(value=resolved[role])
                    for role in resolved
                },
                "value": decimal_text(value=value),
                "quality": quality,
            }
        )
        result_unit = str(semantic["canonical_unit"])
        if semantic["unit_policy"] == "preserve_reported":
            reported_units = {
                str(observation["unit"])
                for observation in all_observations
            }
            if len(reported_units) != 1:
                raise CalculationError(
                    "preserve_reported requires one unambiguous input unit"
                )
            result_unit = reported_units.pop()
        result, trace = _result_and_trace(
            compiled_spec=compiled_spec,
            target=target,
            applicability="APPLICABLE",
            quality=quality,
            publication="PUBLISHED",
            reason_code="PASS",
            value=value,
            result_unit=result_unit,
            trace_steps=trace_steps,
            input_ids=input_ids,
        )
        return result, trace, [dict(item) for item in all_observations]
    except (BranchRejected, ConstraintError) as error:
        reason = (
            error.reason_code
            if isinstance(error, BranchRejected)
            else "CALCULATION_GUARD_FAILED"
        )
        trace_steps.append({"event": "WITHHELD", "reason_code": reason})
        result, trace = _result_and_trace(
            compiled_spec=compiled_spec,
            target=target,
            applicability="APPLICABLE",
            quality="NONE",
            publication="WITHHELD",
            reason_code=reason,
            value=None,
            result_unit=None,
            trace_steps=trace_steps,
            input_ids=input_ids,
        )
        return result, trace, [dict(item) for item in all_observations]


def calculate_observation_metric(
    *,
    compiled_spec: Mapping[str, object],
    target: Mapping[str, object],
    company_traits: Sequence[str],
    observation: Mapping[str, object],
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Project one already-verified direct observation into a metric result.

    Args:
        compiled_spec: Compiled direct-numeric Spec.
        target: Exact company/period/scope result grain.
        company_traits: Config-projected traits.
        observation: HUMAN-reviewed or deterministic VerifiedObservation.

    Returns:
        Direct MetricResult and replayable ExecutionTrace.

    Raises:
        CalculationError: On stale Spec/target/observation binding.
    """
    required_target = {
        "company_id",
        "period_start",
        "period_end",
        "scope",
        "scope_key",
    }
    if set(target) != required_target:
        raise CalculationError(
            "Direct calculation target fields are not exact"
        )
    if target["scope_key"] != scope_key(scope=target["scope"]):
        raise CalculationError("Direct calculation scope_key differs")
    verified = validate_record(record=observation)
    if verified["record_type"] != "VERIFIED_OBSERVATION":
        raise CalculationError("Direct calculation requires an observation")
    semantic = compiled_spec["compiled"]
    if semantic["kind"] != "direct_numeric":
        raise CalculationError(
            "Observation calculator requires direct_numeric Spec"
        )
    comparisons = {
        "metric_id": semantic["metric_id"],
        "company_id": target["company_id"],
        "period_start": target["period_start"],
        "period_end": target["period_end"],
        "scope_key": target["scope_key"],
    }
    if semantic["unit_policy"] == "fixed_canonical":
        comparisons["unit"] = semantic["canonical_unit"]
    for field in comparisons:
        if verified[field] != comparisons[field]:
            raise CalculationError(
                "Direct observation binding differs: {}".format(field)
            )
    if not metric_is_applicable(
        applicability=semantic["applicability"], traits=company_traits,
    ):
        raise CalculationError(
            "Verified direct observation is structurally inapplicable"
        )
    value = _decimal_value(value=verified["value"])
    role = str(verified["semantic_role"])
    steps = [
        {
            "event": "REUSED_OBSERVATION",
            "role": role,
            "observation_id": verified["observation_id"],
            "value": decimal_text(value=value),
        },
        {
            "event": "FORMULA_RESULT",
            "formula": role,
            "resolved_values": {role: decimal_text(value=value)},
            "value": decimal_text(value=value),
            "quality": verified["quality"],
        },
    ]
    return _result_and_trace(
        compiled_spec=compiled_spec,
        target=target,
        applicability="APPLICABLE",
        quality=str(verified["quality"]),
        publication="PUBLISHED",
        reason_code="PASS",
        value=value,
        result_unit=str(verified["unit"]),
        trace_steps=steps,
        input_ids=[str(verified["observation_id"])],
    )


def withheld_metric_result(
    *,
    compiled_spec: Mapping[str, object],
    target: Mapping[str, object],
    reason_code: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Create an explicit fail-closed result after an upstream gate fails.

    Args:
        compiled_spec: Compiled metric Spec.
        target: Exact company/period/scope result grain.
        reason_code: Stable upstream failure reason.

    Returns:
        WITHHELD MetricResult and audit Trace with no invented value.
    """
    required_target = {
        "company_id",
        "period_start",
        "period_end",
        "scope",
        "scope_key",
    }
    if set(target) != required_target:
        raise CalculationError("WITHHELD target fields are not exact")
    if target["scope_key"] != scope_key(scope=target["scope"]):
        raise CalculationError("WITHHELD target scope_key differs")
    if not reason_code:
        raise CalculationError("WITHHELD reason_code is required")
    return _result_and_trace(
        compiled_spec=compiled_spec,
        target=target,
        applicability="APPLICABLE",
        quality="NONE",
        publication="WITHHELD",
        reason_code=reason_code,
        value=None,
        result_unit=None,
        trace_steps=[{"event": "WITHHELD", "reason_code": reason_code}],
        input_ids=[],
    )
