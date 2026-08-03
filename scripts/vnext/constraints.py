"""Evaluate generic Decimal expressions, guards, and declared constraints."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Dict, Mapping, Sequence, Tuple

from .canonical import CanonicalError, arithmetic_context, decimal_text
from .canonical import parse_decimal


NUMERIC_TEXT_PATTERN = re.compile(
    r"^\s*(\()?\s*([+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)"
    r"(?:\.[0-9]+)?)\s*"
    r"(percent|%|million|billion)?\s*(\))?\s*$",
    flags=re.IGNORECASE,
)


class ConstraintError(ValueError):
    """Report an unevaluable expression, guard, or numeric claim."""


def parse_numeric_claim(*, raw_value: str, reported_unit: str) -> Decimal:
    """Normalize one cell value under the shared numeric policy.

    Args:
        raw_value: Cell text containing a finite number, optional commas,
            parentheses, percent, million, or billion suffix.
        reported_unit: Declared unit. ``percent`` converts to canonical ratio.

    Returns:
        Canonical Decimal.

    Raises:
        ConstraintError: On malformed text, mismatched parentheses, or unit
            disagreement.
    """
    match = NUMERIC_TEXT_PATTERN.fullmatch(raw_value)
    if match is None:
        raise ConstraintError("Cell is not a supported numeric claim")
    open_parenthesis, number, suffix, close_parenthesis = match.groups()
    if bool(open_parenthesis) != bool(close_parenthesis):
        raise ConstraintError("Numeric parentheses are unbalanced")
    normalized_number = number.replace(",", "")
    try:
        value = parse_decimal(value=normalized_number)
    except CanonicalError as error:
        raise ConstraintError(
            "Numeric claim violates Decimal policy"
        ) from error
    if open_parenthesis:
        value = -abs(value)
    suffix_text = suffix.lower() if suffix is not None else ""
    normalized_unit = reported_unit.lower()
    if suffix_text in {"million", "billion"} and normalized_unit in {
        "percent",
        "ratio",
    }:
        raise ConstraintError(
            "Magnitude suffix conflicts with reported unit"
        )
    with arithmetic_context():
        if suffix_text in {"percent", "%"}:
            if normalized_unit not in {"percent", "ratio"}:
                raise ConstraintError(
                    "Percent suffix conflicts with reported unit"
                )
            value = value / Decimal("100")
        elif normalized_unit == "percent":
            value = value / Decimal("100")
        elif suffix_text == "million":
            value = value * Decimal("1000000")
        elif suffix_text == "billion":
            value = value * Decimal("1000000000")
    return value


def evaluate_expression(
    *, expression: object, values: Mapping[str, Decimal]
) -> Decimal:
    """Evaluate a bounded arithmetic AST without business-specific branches.

    Args:
        expression: Role reference, fixed-point literal, or operation mapping.
        values: Named canonical Decimal values.

    Returns:
        Decimal result under precision 28 and HALF_EVEN.

    Raises:
        ConstraintError: On unknown roles/operations, malformed args, or zero
            division.
    """
    if isinstance(expression, str):
        if expression in values:
            return values[expression]
        try:
            return parse_decimal(value=expression)
        except CanonicalError as error:
            raise ConstraintError(
                "Unknown expression role: {}".format(expression)
            ) from error
    if not isinstance(expression, dict) or set(expression) != {"op", "args"}:
        raise ConstraintError("Expression must contain exact op/args fields")
    operation = expression["op"]
    arguments = expression["args"]
    if operation not in {"add", "subtract", "multiply", "divide"}:
        raise ConstraintError("Unsupported arithmetic operation")
    if not isinstance(arguments, list) or len(arguments) < 2:
        raise ConstraintError("Expression args must be an ordered array")
    operands = [
        evaluate_expression(expression=argument, values=values)
        for argument in arguments
    ]
    with arithmetic_context():
        result = operands[0]
        for operand in operands[1:]:
            if operation == "add":
                result += operand
            elif operation == "subtract":
                result -= operand
            elif operation == "multiply":
                result *= operand
            elif operation == "divide":
                if operand == 0:
                    raise ConstraintError("Division denominator is zero")
                result /= operand
    return result


def evaluate_identity_constraint(
    *, constraint: Mapping[str, object], values: Mapping[str, Decimal]
) -> Dict[str, object]:
    """Evaluate one generic expected/actual relative constraint.

    Args:
        constraint: Exact expression/tolerance mapping from a compiled Spec.
        values: Named canonical Decimal observations.

    Returns:
        Pass flag, expected/actual values, relative error, and tolerance.

    Raises:
        ConstraintError: On malformed fields, unsupported tolerance, missing
            input, non-positive expected value, or incompatible expression.
    """
    if set(constraint) != {"expression", "tolerance"}:
        raise ConstraintError("Identity constraint fields are not exact")
    expression = constraint["expression"]
    tolerance = constraint["tolerance"]
    if not isinstance(expression, dict) or set(expression) != {
        "expected",
        "actual",
    }:
        raise ConstraintError("Identity expression fields are not exact")
    if not isinstance(tolerance, dict) or set(tolerance) != {"kind", "value"}:
        raise ConstraintError("Identity tolerance fields are not exact")
    if tolerance["kind"] != "relative" or not isinstance(
        tolerance["value"], str
    ):
        raise ConstraintError(
            "Only relative fixed-point tolerance is supported"
        )
    expected = evaluate_expression(
        expression=expression["expected"], values=values
    )
    actual = evaluate_expression(
        expression=expression["actual"], values=values
    )
    if expected <= 0:
        raise ConstraintError("Identity expected value must be positive")
    try:
        threshold = parse_decimal(value=tolerance["value"])
    except CanonicalError as error:
        raise ConstraintError(
            "Identity tolerance violates Decimal policy"
        ) from error
    with arithmetic_context():
        relative_error = abs(actual - expected) / abs(expected)
    return {
        "passed": relative_error <= threshold,
        "expected": decimal_text(value=expected),
        "actual": decimal_text(value=actual),
        "relative_error": decimal_text(value=relative_error),
        "tolerance": decimal_text(value=threshold),
    }


def observations_share_fields(
    *, observations: Sequence[Mapping[str, object]], fields: Sequence[str]
) -> Tuple[bool, str]:
    """Check exact equality for generic source/period/entity/unit guards.

    Args:
        observations: Input observations or structured candidates.
        fields: Explicit fields named by a compiled guard.

    Returns:
        Boolean and stable diagnostic reason.

    Raises:
        ConstraintError: When a required field is missing.
    """
    if not observations:
        raise ConstraintError("Guard requires at least one observation")
    for field in fields:
        if any(field not in observation for observation in observations):
            raise ConstraintError("Guard input lacks field: {}".format(field))
        first = observations[0][field]
        if any(
            type(observation[field]) is not type(first)
            or observation[field] != first
            for observation in observations[1:]
        ):
            return False, "MISMATCH_{}".format(field.upper())
    return True, "PASS"


def verify_trace_observation_values(
    *,
    trace: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]],
) -> None:
    """Bind stored trace role values to exact input observations.

    Args:
        trace: ExecutionTrace whose final formula may use direct or derived
            semantic roles.
        observations: Verified observations keyed by observation identity.

    Raises:
        ConstraintError: On duplicate/missing inputs, detached component
            values, or final resolved values that differ from observations.
    """
    input_ids = trace["input_observation_ids"]
    if (
        type(input_ids) is not list
        or any(type(observation_id) is not str for observation_id in input_ids)
        or len(input_ids) != len(set(input_ids))
    ):
        raise ConstraintError("Trace input observation IDs are not unique")
    role_values: Dict[str, str] = {}
    for observation_id in input_ids:
        if observation_id not in observations:
            raise ConstraintError("Trace input observation is missing")
        observation = observations[str(observation_id)]
        role = observation["semantic_role"]
        value = observation["value"]
        if not isinstance(role, str) or not isinstance(value, str):
            raise ConstraintError("Trace observation role/value is malformed")
        if role in role_values:
            raise ConstraintError("Trace observation role is ambiguous")
        role_values[role] = value
    steps = trace["steps"]
    if type(steps) is not list:
        raise ConstraintError("Trace steps must be a list")
    for step in steps:
        if (
            type(step) is not dict
            or "event" not in step
            or type(step["event"]) is not str
        ):
            raise ConstraintError("Trace step event is malformed")
        if step["event"] != "DERIVED_BRANCH_SELECTED":
            continue
        required = {
            "args",
            "component_observation_ids",
            "component_values",
            "event",
            "operation",
            "quality",
            "role",
            "value",
        }
        if set(step) != required:
            raise ConstraintError("Derived Trace step fields are not exact")
        component_ids = step["component_observation_ids"]
        if (
            type(component_ids) is not list
            or any(
                type(observation_id) is not str
                for observation_id in component_ids
            )
            or len(component_ids) != len(set(component_ids))
        ):
            raise ConstraintError("Derived Trace components are not unique")
        if set(component_ids) - set(input_ids):
            raise ConstraintError("Derived Trace component is not an input")
        component_values = {}
        for observation_id in component_ids:
            if observation_id not in observations:
                raise ConstraintError("Derived Trace observation is missing")
            observation = observations[str(observation_id)]
            role = observation["semantic_role"]
            value = observation["value"]
            if type(role) is not str or type(value) is not str:
                raise ConstraintError(
                    "Derived Trace observation role/value is malformed"
                )
            if role in component_values:
                raise ConstraintError(
                    "Derived Trace component role is ambiguous"
                )
            component_values[role] = value
        if type(step["component_values"]) is not dict:
            raise ConstraintError("Derived Trace component values malformed")
        if component_values != step["component_values"]:
            raise ConstraintError(
                "Derived Trace component value differs from observation"
            )
        if (
            type(step["operation"]) is not str
            or type(step["args"]) is not list
            or type(step["value"]) is not str
        ):
            raise ConstraintError("Derived Trace expression is malformed")
        try:
            values = {
                role: parse_decimal(value=component_values[role])
                for role in component_values
            }
            calculated = evaluate_expression(
                expression={
                    "op": step["operation"], "args": step["args"],
                },
                values=values,
            )
        except CanonicalError as error:
            raise ConstraintError(
                "Derived Trace Decimal is malformed"
            ) from error
        if decimal_text(value=calculated) != step["value"]:
            raise ConstraintError("Derived Trace value cannot be recalculated")
        role = step["role"]
        if type(role) is not str or not role or role in role_values:
            raise ConstraintError("Derived Trace role is ambiguous")
        role_values[role] = step["value"]
    final_steps = [
        step for step in steps if step["event"] == "FORMULA_RESULT"
    ]
    if trace["result"] is None:
        if final_steps:
            raise ConstraintError(
                "Null Trace unexpectedly contains a final formula"
            )
        return
    if len(final_steps) != 1:
        raise ConstraintError("Published Trace needs one final formula")
    final = final_steps[0]
    required = {"event", "formula", "resolved_values", "value", "quality"}
    if set(final) != required:
        raise ConstraintError("Final Trace step fields are not exact")
    resolved = final["resolved_values"]
    if type(resolved) is not dict or any(
        type(role) is not str or type(resolved[role]) is not str
        for role in resolved
    ):
        raise ConstraintError("Trace resolved values must be an object")
    for role in resolved:
        if role not in role_values or resolved[role] != role_values[role]:
            raise ConstraintError(
                "Trace resolved value differs from observation"
            )
    if type(final["value"]) is not str or final["quality"] != trace[
        "quality"
    ]:
        raise ConstraintError("Final Trace value/quality is malformed")
    try:
        values = {
            role: parse_decimal(value=resolved[role]) for role in resolved
        }
        recalculated = evaluate_expression(
            expression=final["formula"], values=values,
        )
    except CanonicalError as error:
        raise ConstraintError("Final Trace Decimal is malformed") from error
    if (
        decimal_text(value=recalculated) != final["value"]
        or final["value"] != trace["result"]
    ):
        raise ConstraintError("Trace formula cannot be recalculated")
