"""Validate and apply the Spec-owned generic scope contract v2.

Reader output carries only raw scope strings and evidence locator IDs.  This
module owns the sole automatic normalization mechanism: exact raw-string alias
resolution declared by a MetricSpec.  It deliberately contains no numeric,
percentage, date, or free-text normalizers.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

from .canonical import content_hash


SCOPE_CONTRACT_VERSION = "2"
SCOPE_CONTRACT_FIELDS = {
    "allowed_dimensions",
    "cross_dimension_constraints",
    "exact_enum_aliases",
    "required_dimensions",
    "scope_contract_version",
    "selection_preference",
}
SELECTION_PREFERENCE_FIELDS = {
    "dimension_order",
    "prefer_complete_required_dimensions",
}
CROSS_DIMENSION_CONSTRAINT_FIELDS = {
    "if_dimension",
    "if_value",
    "requires_dimension",
    "requires_value",
}


class ScopeContractError(ValueError):
    """Report malformed scope authority or unresolved scope facts."""


def _ordered_text_list(*, value: object, label: str) -> List[str]:
    """Validate one ordered, duplicate-free non-empty text list.

    Args:
        value: Candidate JSON list.
        label: Stable diagnostic field name.

    Returns:
        Isolated ordered text values.

    Raises:
        ScopeContractError: If the list is malformed or duplicates a value.
    """
    if (
        type(value) is not list
        or any(type(item) is not str or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ScopeContractError("{} must be unique non-empty text".format(label))
    return list(value)


def validate_scope_contract(*, value: object) -> Dict[str, object]:
    """Validate a complete Spec-owned scope contract v2.

    Args:
        value: Untrusted scope contract from compiled MetricSpec semantics.

    Returns:
        Canonical contract dictionary used by Reader, Evidence, and Review.

    Raises:
        ScopeContractError: If aliases, dimensions, preferences, or cross
        dimension constraints are incomplete or ambiguous.
    """
    if type(value) is not dict or set(value) != SCOPE_CONTRACT_FIELDS:
        raise ScopeContractError("Scope contract fields are not exact")
    contract = dict(value)
    if contract["scope_contract_version"] != SCOPE_CONTRACT_VERSION:
        raise ScopeContractError("Scope contract version is unsupported")
    required = _ordered_text_list(
        value=contract["required_dimensions"],
        label="required_dimensions",
    )
    allowed = _ordered_text_list(
        value=contract["allowed_dimensions"],
        label="allowed_dimensions",
    )
    if not set(required).issubset(set(allowed)):
        raise ScopeContractError("Required scope dimension is not allowed")
    aliases = contract["exact_enum_aliases"]
    if type(aliases) is not dict or set(aliases) != set(allowed):
        raise ScopeContractError("Scope alias dimensions are not exact")
    normalized_aliases: Dict[str, Dict[str, List[str]]] = {}
    for dimension in allowed:
        values = aliases[dimension]
        if type(values) is not dict or not values:
            raise ScopeContractError("Scope enum aliases are invalid")
        seen_aliases = set()
        normalized_values: Dict[str, List[str]] = {}
        for canonical_value, raw_aliases in values.items():
            aliases_for_value = _ordered_text_list(
                value=raw_aliases,
                label="Scope exact enum aliases",
            )
            if (
                type(canonical_value) is not str
                or not canonical_value
                or seen_aliases.intersection(aliases_for_value)
            ):
                raise ScopeContractError("Scope enum aliases are ambiguous")
            seen_aliases.update(aliases_for_value)
            normalized_values[canonical_value] = aliases_for_value
        normalized_aliases[dimension] = normalized_values
    preference = contract["selection_preference"]
    if (
        type(preference) is not dict
        or set(preference) != SELECTION_PREFERENCE_FIELDS
        or preference["prefer_complete_required_dimensions"] is not True
    ):
        raise ScopeContractError("Scope selection preference is invalid")
    order = _ordered_text_list(
        value=preference["dimension_order"],
        label="Scope preference dimension_order",
    )
    if set(order) != set(allowed):
        raise ScopeContractError("Scope preference dimensions differ")
    constraints = contract["cross_dimension_constraints"]
    if type(constraints) is not list:
        raise ScopeContractError("Scope cross constraints must be an array")
    normalized_constraints = []
    for constraint in constraints:
        if (
            type(constraint) is not dict
            or set(constraint) != CROSS_DIMENSION_CONSTRAINT_FIELDS
        ):
            raise ScopeContractError("Scope cross constraint fields are invalid")
        for dimension_field, value_field in (
            ("if_dimension", "if_value"),
            ("requires_dimension", "requires_value"),
        ):
            dimension = constraint[dimension_field]
            canonical_value = constraint[value_field]
            if (
                type(dimension) is not str
                or dimension not in normalized_aliases
                or type(canonical_value) is not str
                or canonical_value not in normalized_aliases[dimension]
            ):
                raise ScopeContractError("Scope cross constraint value is invalid")
        normalized_constraints.append(dict(constraint))
    return {
        "scope_contract_version": SCOPE_CONTRACT_VERSION,
        "required_dimensions": required,
        "allowed_dimensions": allowed,
        "exact_enum_aliases": normalized_aliases,
        "selection_preference": {
            "dimension_order": order,
            "prefer_complete_required_dimensions": True,
        },
        "cross_dimension_constraints": normalized_constraints,
    }


def scope_contract_hash(*, contract: Mapping[str, object]) -> str:
    """Return the content identity for a validated generic scope contract.

    Args:
        contract: Scope contract accepted by :func:`validate_scope_contract`.

    Returns:
        Canonical content hash used by task and qualification bindings.
    """
    return content_hash(value=validate_scope_contract(value=contract))


def exact_enum_alias(
    *, contract: Mapping[str, object], dimension: str, raw_value: str,
) -> Optional[str]:
    """Resolve one raw scope text only by exact Spec enum alias.

    Args:
        contract: Validated generic scope contract.
        dimension: Declared scope dimension.
        raw_value: Exact text mechanically reread from the supplied locator.

    Returns:
        Canonical enum string, or ``None`` when no exact alias exists.
    """
    validated = validate_scope_contract(value=contract)
    if dimension not in validated["exact_enum_aliases"]:
        raise ScopeContractError("Scope dimension is not allowed")
    if type(raw_value) is not str or not raw_value:
        raise ScopeContractError("Scope raw value is invalid")
    for canonical_value, aliases in validated["exact_enum_aliases"][dimension].items():
        if raw_value in aliases:
            return canonical_value
    return None


def scope_satisfies_contract(
    *, contract: Mapping[str, object], normalized_scope: Mapping[str, object],
) -> bool:
    """Return whether canonical scope facts meet the declarative contract.

    Args:
        contract: Validated scope contract v2.
        normalized_scope: Canonical dimension-to-enum mapping.

    Returns:
        True only when dimensions, enum values, and cross constraints pass.
    """
    validated = validate_scope_contract(value=contract)
    if type(normalized_scope) is not dict:
        return False
    keys = set(normalized_scope)
    allowed = set(validated["allowed_dimensions"])
    required = set(validated["required_dimensions"])
    if not required.issubset(keys) or not keys.issubset(allowed):
        return False
    for dimension, canonical_value in normalized_scope.items():
        if (
            type(canonical_value) is not str
            or canonical_value not in validated["exact_enum_aliases"][dimension]
        ):
            return False
    for constraint in validated["cross_dimension_constraints"]:
        if (
            constraint["if_dimension"] not in normalized_scope
            or normalized_scope[constraint["if_dimension"]]
            != constraint["if_value"]
        ):
            continue
        if (
            constraint["requires_dimension"] not in normalized_scope
            or normalized_scope[constraint["requires_dimension"]]
            != constraint["requires_value"]
        ):
            return False
    return True
