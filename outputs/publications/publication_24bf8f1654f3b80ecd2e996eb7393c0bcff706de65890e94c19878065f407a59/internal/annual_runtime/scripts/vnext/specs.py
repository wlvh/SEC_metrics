"""Compile JSON-compatible MetricSpec front matter into explicit semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Set, Tuple

from .canonical import CanonicalError, content_hash, execution_semantics_hash
from .canonical import parse_decimal, strict_json_loads
from .scope_contract import ScopeContractError, scope_satisfies_contract
from .scope_contract import validate_scope_contract


FRONT_MATTER_SEPARATOR = "---"
MAX_AST_DEPTH = 32
MAX_AST_NODES = 256
SUPPORTED_OPERATIONS = {"add", "subtract", "multiply", "divide"}
SPEC_FIELDS = {
    "ai_instructions",
    "applicability",
    "canonical_unit",
    "dependencies",
    "disclosure_group",
    "forbidden_confusions",
    "formula",
    "identity_constraints",
    "inputs",
    "kind",
    "legacy_projection",
    "metric_id",
    "name",
    "prompt_examples",
    "reported_unit",
    "required_claims",
    "review_policy",
    "selection_policy",
    "scope_contract",
    "source_mode",
    "top_level_guards",
    "unit_policy",
    "quality_rule",
}
REQUIRED_SPEC_FIELDS = {
    "applicability",
    "canonical_unit",
    "kind",
    "legacy_projection",
    "metric_id",
    "name",
}
LEGACY_COMPANYFACTS_V1 = {
    "semantic_version": "1",
    "period_filter": "target_period",
    "form_rule": "10-K_PREFIX_AND_FY",
    "within_concept_order": ["filed_desc", "accession_desc", "unit_desc"],
    "target_accession_priority": True,
    "ambiguous_after_tie_break": "AMBIGUOUS_CANDIDATE",
}
NUMERIC_POLICY = {
    "decimal_precision": 28,
    "rounding": "ROUND_HALF_EVEN",
    "serialization": "fixed_point",
    "normalize_trailing_zeros": True,
    "allow_nan": False,
    "allow_infinity": False,
    "percent_to_ratio": "divide_by_100",
    "maximum_significant_digits": 128,
    "maximum_absolute_scale": 64,
}
EQUALITY_GUARDS = {
    "same_accession",
    "same_period",
    "same_entity",
    "compatible_units",
}
CARDINALITIES = {"exactly_one", "zero_or_one"}
QUALITIES = {"EXACT", "APPROX"}
UNIT_POLICIES = {"fixed_canonical", "preserve_reported"}
SEMANTIC_SET_PATHS = frozenset(
    {("applicability", "all"), ("applicability", "none")}
)


class SpecError(ValueError):
    """Report an invalid, ambiguous, cyclic, or unsupported MetricSpec."""


def parse_spec_document(*, text: str) -> Tuple[Dict[str, object], str]:
    """Parse Markdown with strict JSON-compatible front matter.

    Args:
        text: Complete UTF-8 MetricSpec Markdown.

    Returns:
        Front-matter mapping and human-readable body.

    Raises:
        SpecError: When delimiters, JSON, root type, fields, or required
            semantics are invalid.
    """
    lines = text.splitlines()
    if not lines or lines[0] != FRONT_MATTER_SEPARATOR:
        raise SpecError("MetricSpec must begin with ---")
    try:
        closing = lines.index(FRONT_MATTER_SEPARATOR, 1)
    except ValueError as error:
        raise SpecError("MetricSpec front matter is not closed") from error
    front_text = "\n".join(lines[1:closing])
    try:
        parsed = strict_json_loads(text=front_text, allowed_fields=SPEC_FIELDS)
    except CanonicalError as error:
        raise SpecError(
            "MetricSpec front matter is not strict JSON"
        ) from error
    if not isinstance(parsed, dict):
        raise SpecError("MetricSpec front matter must be an object")
    missing = sorted(REQUIRED_SPEC_FIELDS - set(parsed))
    if missing:
        raise SpecError(
            "MetricSpec fields are missing: {}".format(",".join(missing))
        )
    body = "\n".join(lines[closing + 1:])
    return dict(parsed), body


def _require_string(*, mapping: Mapping[str, object], key: str) -> str:
    """Return one required non-empty string field.

    Args:
        mapping: Spec mapping.
        key: Required field.

    Returns:
        Non-empty string.

    Raises:
        SpecError: When missing or not a non-empty string.
    """
    if (
        key not in mapping
        or not isinstance(mapping[key], str)
        or not mapping[key]
    ):
        raise SpecError("MetricSpec {} must be a non-empty string".format(key))
    return str(mapping[key])


def _count_ast(*, node: object, depth: int = 1) -> int:
    """Validate supported expression nodes and return the node count.

    Args:
        node: Expression value, role reference, or literal.
        depth: Current one-based AST depth.

    Returns:
        Total recursive node count.

    Raises:
        SpecError: On excessive depth/size, unknown operation, malformed args,
            float literal, or unsupported node type.
    """
    if depth > MAX_AST_DEPTH:
        raise SpecError("MetricSpec AST exceeds depth 32")
    if node is None or isinstance(node, (str, int, bool)):
        return 1
    if isinstance(node, float):
        raise SpecError("MetricSpec AST must not contain binary floats")
    if isinstance(node, list):
        total = 1
        for item in node:
            total += _count_ast(node=item, depth=depth + 1)
            if total > MAX_AST_NODES:
                raise SpecError("MetricSpec AST exceeds 256 nodes")
        return total
    if isinstance(node, dict):
        total = 1
        if "op" in node:
            if node["op"] not in SUPPORTED_OPERATIONS:
                raise SpecError(
                    "Unknown MetricSpec operation: {}".format(node["op"])
                )
            if "args" not in node or not isinstance(node["args"], list):
                raise SpecError("Arithmetic operation requires ordered args")
            if len(node["args"]) < 2:
                raise SpecError(
                    "Arithmetic operation requires at least two args"
                )
        for key in node:
            total += _count_ast(node=node[key], depth=depth + 1)
            if total > MAX_AST_NODES:
                raise SpecError("MetricSpec AST exceeds 256 nodes")
        return total
    raise SpecError(
        "Unsupported MetricSpec AST node: {}".format(type(node).__name__)
    )


def _validate_traits(*, applicability: object) -> Dict[str, object]:
    """Validate the bounded trait applicability object.

    Args:
        applicability: Candidate ``all``/``none`` mapping.

    Returns:
        Isolated mapping.

    Raises:
        SpecError: On unknown fields, duplicate traits, or invalid strings.
    """
    if not isinstance(applicability, dict) or set(applicability) != {
        "all",
        "none",
    }:
        raise SpecError("Applicability must contain exact all/none fields")
    for key in ("all", "none"):
        values = applicability[key]
        if not isinstance(values, list):
            raise SpecError("Applicability {} must be an array".format(key))
        if any(not isinstance(value, str) or not value for value in values):
            raise SpecError("Applicability traits must be non-empty strings")
        if len(values) != len(set(values)):
            raise SpecError("Applicability traits must be unique")
    if set(applicability["all"]) & set(applicability["none"]):
        raise SpecError("A trait cannot be both required and forbidden")
    return {
        "all": list(applicability["all"]),
        "none": list(applicability["none"]),
    }


def _expand_selection_policy(*, value: object) -> Dict[str, object]:
    """Expand a named structured-fact policy into hash-visible semantics.

    Args:
        value: ``legacy_companyfacts_v1`` or an already explicit policy.

    Returns:
        Complete policy mapping.

    Raises:
        SpecError: On an unknown policy name or malformed explicit mapping.
    """
    if value == "legacy_companyfacts_v1":
        return dict(LEGACY_COMPANYFACTS_V1)
    if not isinstance(value, dict):
        raise SpecError("selection_policy must be named or explicit")
    required = set(LEGACY_COMPANYFACTS_V1)
    if set(value) != required:
        raise SpecError("Explicit selection_policy fields are not exact")
    if dict(value) != LEGACY_COMPANYFACTS_V1:
        raise SpecError("Explicit selection_policy changes frozen semantics")
    return dict(value)


def _validate_concept_role(
    *, role: object, quality_required: bool
) -> Dict[str, object]:
    """Validate one ordered structured concept-selection role.

    Args:
        role: Candidate role mapping.
        quality_required: Whether this role directly determines result quality.

    Returns:
        Isolated role mapping.
    """
    required = {"approved_concepts", "cardinality"}
    if quality_required:
        required.add("quality")
    optional = {"quality"} - required
    if not isinstance(role, dict) or not required.issubset(role):
        raise SpecError("Structured role fields are incomplete")
    if set(role) - (required | optional):
        raise SpecError("Structured role fields are unknown")
    concepts = role["approved_concepts"]
    if not isinstance(concepts, list) or not concepts:
        raise SpecError(
            "Structured concepts must be a non-empty ordered array"
        )
    if any(not isinstance(item, str) or not item for item in concepts):
        raise SpecError("Structured concept is empty")
    if len(concepts) != len(set(concepts)):
        raise SpecError("Structured concepts must be unique")
    if role["cardinality"] not in CARDINALITIES:
        raise SpecError("Structured role cardinality is unknown")
    if "quality" in role and role["quality"] not in QUALITIES:
        raise SpecError("Structured role quality is unknown")
    return dict(role)


def _validate_cross_check(*, value: object) -> Dict[str, object]:
    """Validate optional generic cross-check semantics.

    Args:
        value: Candidate cross-check mapping.

    Returns:
        Isolated exact mapping.
    """
    fields = {
        "when_available",
        "role",
        "approved_concepts",
        "cardinality",
        "expression",
        "denominator",
        "relative_tolerance",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise SpecError("Cross-check fields are not exact")
    if value["when_available"] is not True:
        raise SpecError("Cross-check must be optional when available")
    _validate_concept_role(
        role={
            "approved_concepts": value["approved_concepts"],
            "cardinality": value["cardinality"],
        },
        quality_required=False,
    )
    if value["cardinality"] != "zero_or_one":
        raise SpecError("Optional cross-check cardinality must be zero_or_one")
    if not isinstance(value["role"], str) or not value["role"]:
        raise SpecError("Cross-check role is empty")
    if value["denominator"] != "ABS_ACTUAL_OR_ONE":
        raise SpecError("Cross-check denominator semantics are unknown")
    if not isinstance(value["relative_tolerance"], str):
        raise SpecError("Cross-check tolerance must be fixed-point text")
    return dict(value)


def _validate_derived_role(*, value: object) -> Dict[str, object]:
    """Validate one deterministic derived fallback branch.

    Args:
        value: Candidate derived-role mapping.

    Returns:
        Isolated branch mapping.
    """
    required = {"op", "inputs", "args", "quality", "guards"}
    optional = {"quality_reason", "cross_check"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise SpecError("Derived role fields are incomplete")
    if set(value) - (required | optional):
        raise SpecError("Derived role fields are unknown")
    if value["op"] not in SUPPORTED_OPERATIONS:
        raise SpecError("Derived role operation is unknown")
    if value["quality"] not in QUALITIES:
        raise SpecError("Derived role quality is unknown")
    if not isinstance(value["inputs"], dict) or not value["inputs"]:
        raise SpecError("Derived role inputs must be a non-empty object")
    for role in value["inputs"]:
        _validate_concept_role(
            role=value["inputs"][role], quality_required=False,
        )
    if not isinstance(value["args"], list) or len(value["args"]) < 2:
        raise SpecError("Derived role args must be ordered")
    if any(argument not in value["inputs"] for argument in value["args"]):
        raise SpecError("Derived role arg names an undeclared input")
    guards = value["guards"]
    if not isinstance(guards, list) or any(
        guard not in EQUALITY_GUARDS for guard in guards
    ):
        raise SpecError("Derived role guard is unknown")
    if len(guards) != len(set(guards)):
        raise SpecError("Derived role guards must be unique")
    if "cross_check" in value:
        _validate_cross_check(value=value["cross_check"])
    return dict(value)


def _validate_inputs(*, value: object) -> Dict[str, object]:
    """Validate top-level structured/reuse/choose-first role contracts.

    Args:
        value: Candidate inputs mapping.

    Returns:
        Isolated ordered mapping.
    """
    if not isinstance(value, dict):
        raise SpecError("MetricSpec inputs must be an object")
    for role in value:
        role_spec = value[role]
        if (
            not isinstance(role, str)
            or not role
            or not isinstance(role_spec, dict)
        ):
            raise SpecError("MetricSpec input role is invalid")
        if set(role_spec) == {"structured_role"}:
            _validate_concept_role(
                role=role_spec["structured_role"], quality_required=True,
            )
            continue
        if set(role_spec) == {"reuse_metric_observation", "cardinality"}:
            if (
                not isinstance(role_spec["reuse_metric_observation"], str)
                or not role_spec["reuse_metric_observation"]
                or role_spec["cardinality"] != "exactly_one"
            ):
                raise SpecError("Reusable observation role is invalid")
            continue
        if set(role_spec) != {"choose_first"}:
            raise SpecError("MetricSpec input role kind is unknown")
        branches = role_spec["choose_first"]
        if not isinstance(branches, list) or not branches:
            raise SpecError("choose_first requires ordered branches")
        for branch in branches:
            if not isinstance(branch, dict) or len(branch) != 1:
                raise SpecError("choose_first branch must have one kind")
            if "extraction_role" in branch:
                _validate_concept_role(
                    role=branch["extraction_role"], quality_required=True,
                )
            elif "derived_role" in branch:
                _validate_derived_role(value=branch["derived_role"])
            else:
                raise SpecError("choose_first branch kind is unknown")
    return dict(value)


def _validate_top_level_guards(*, value: object) -> Sequence[object]:
    """Validate generic top-level equality/economic guards.

    Args:
        value: Candidate ordered guard array.

    Returns:
        Isolated ordered guards.
    """
    if not isinstance(value, list):
        raise SpecError("top_level_guards must be an ordered array")
    seen_strings = set()
    for guard in value:
        if isinstance(guard, str):
            if guard not in EQUALITY_GUARDS | {"denominator_nonzero"}:
                raise SpecError("Top-level guard is unknown")
            if guard in seen_strings:
                raise SpecError("Top-level guard is duplicated")
            seen_strings.add(guard)
            continue
        if not isinstance(guard, dict) or set(guard) != {"annual_duration"}:
            raise SpecError("Top-level guard mapping is unknown")
        limits = guard["annual_duration"]
        if (
            not isinstance(limits, list)
            or len(limits) != 2
            or any(type(item) is not int for item in limits)
            or limits[0] > limits[1]
        ):
            raise SpecError("annual_duration bounds are invalid")
    return list(value)


def _expression_roles(*, expression: object) -> Set[str]:
    """Validate one arithmetic expression and collect role references.

    Args:
        expression: Fixed-point literal, role, integer, or bounded op/args AST.

    Returns:
        Referenced role names.

    Raises:
        SpecError: On malformed operations or unsupported scalar values.
    """
    if isinstance(expression, str):
        try:
            parse_decimal(value=expression)
            return set()
        except CanonicalError:
            return {expression}
    if type(expression) is int:
        return set()
    if not isinstance(expression, dict) or set(expression) != {"op", "args"}:
        raise SpecError("Arithmetic expression fields are not exact")
    if expression["op"] not in SUPPORTED_OPERATIONS:
        raise SpecError("Arithmetic expression operation is unknown")
    arguments = expression["args"]
    if not isinstance(arguments, list) or len(arguments) < 2:
        raise SpecError("Arithmetic expression args must be ordered")
    roles: Set[str] = set()
    for argument in arguments:
        roles.update(_expression_roles(expression=argument))
    return roles


def _validate_executable_semantics(*, compiled: Mapping[str, object]) -> None:
    """Ensure every runtime role/guard/constraint is declared and bounded.

    Args:
        compiled: Default-expanded Spec semantics.

    Raises:
        SpecError: On unknown expression roles, malformed constraints, or a
        reuse dependency omitted from the closure.
    """
    input_roles = set(compiled["inputs"])
    formula = compiled["formula"]
    if formula is not None:
        unknown_formula_roles = (
            _expression_roles(expression=formula) - input_roles
        )
        if unknown_formula_roles:
            raise SpecError("Formula references undeclared input roles")
    for role in compiled["inputs"]:
        role_spec = compiled["inputs"][role]
        if "reuse_metric_observation" in role_spec:
            dependency = role_spec["reuse_metric_observation"]
            if dependency not in compiled["dependencies"]:
                raise SpecError(
                    "Reusable observation is absent from dependencies"
                )
        if "choose_first" not in role_spec:
            continue
        for branch in role_spec["choose_first"]:
            if "derived_role" not in branch:
                continue
            derived = branch["derived_role"]
            if "cross_check" not in derived:
                continue
            cross_check = derived["cross_check"]
            expression = cross_check["expression"]
            if not isinstance(expression, dict) or set(expression) != {
                "expected",
                "actual",
            }:
                raise SpecError("Cross-check expression fields are not exact")
            allowed = input_roles | {str(cross_check["role"]), str(role)}
            references = _expression_roles(
                expression=expression["expected"]
            ) | _expression_roles(expression=expression["actual"])
            if references - allowed:
                raise SpecError("Cross-check references undeclared roles")
            try:
                tolerance = parse_decimal(
                    value=str(cross_check["relative_tolerance"])
                )
            except CanonicalError as error:
                raise SpecError("Cross-check tolerance is invalid") from error
            if tolerance < 0:
                raise SpecError("Cross-check tolerance cannot be negative")
    constraints = compiled["identity_constraints"]
    if not isinstance(constraints, list):
        raise SpecError("identity_constraints must be an ordered array")
    projection = compiled["legacy_projection"]
    projection_roles: Set[str] = set()
    if isinstance(projection, dict):
        for key in ("roles", "supporting_roles"):
            if key in projection:
                if not isinstance(projection[key], list):
                    raise SpecError("Legacy projection roles must be arrays")
                projection_roles.update(str(item) for item in projection[key])
    allowed_constraint_roles = input_roles | projection_roles
    for constraint in constraints:
        if not isinstance(constraint, dict) or set(constraint) != {
            "expression",
            "tolerance",
        }:
            raise SpecError("Identity constraint fields are not exact")
        expression = constraint["expression"]
        tolerance = constraint["tolerance"]
        if not isinstance(expression, dict) or set(expression) != {
            "expected",
            "actual",
        }:
            raise SpecError("Identity expression fields are not exact")
        if not isinstance(tolerance, dict) or set(tolerance) != {
            "kind",
            "value",
        }:
            raise SpecError("Identity tolerance fields are not exact")
        if tolerance["kind"] != "relative" or not isinstance(
            tolerance["value"], str
        ):
            raise SpecError("Identity tolerance semantics are unknown")
        try:
            parsed_tolerance = parse_decimal(value=tolerance["value"])
        except CanonicalError as error:
            raise SpecError("Identity tolerance is invalid") from error
        if parsed_tolerance < 0:
            raise SpecError("Identity tolerance cannot be negative")
        references = _expression_roles(
            expression=expression["expected"]
        ) | _expression_roles(expression=expression["actual"])
        if references - allowed_constraint_roles:
            raise SpecError("Identity constraint references unknown roles")


def _validate_dependencies(
    *, metric_id: str, dependencies: Sequence[object], stack: Tuple[str, ...]
) -> Sequence[str]:
    """Validate declared dependency IDs and detect a direct closure cycle.

    Args:
        metric_id: Current metric.
        dependencies: Declared dependency values.
        stack: Parent compile stack.

    Returns:
        Ordered dependency IDs.

    Raises:
        SpecError: On duplicate, malformed, self, or recursive dependency.
    """
    if any(not isinstance(item, str) or not item for item in dependencies):
        raise SpecError("MetricSpec dependencies must be non-empty strings")
    values = [str(item) for item in dependencies]
    if len(values) != len(set(values)):
        raise SpecError("MetricSpec dependencies must be unique")
    if metric_id in values or metric_id in stack:
        raise SpecError("MetricSpec dependency cycle detected")
    return values


def compile_spec(
    *,
    text: str,
    dependency_specs: Optional[Mapping[str, Mapping[str, object]]] = None,
    stack: Tuple[str, ...] = (),
) -> Dict[str, object]:
    """Compile one bounded MetricSpec with all runtime defaults visible.

    Args:
        text: Markdown + strict JSON front matter.
        dependency_specs: Already compiled transitive dependencies keyed by
            metric ID.
        stack: Compile recursion stack used for cycle diagnostics.

    Returns:
        Compiled semantics, semantic/prompt/closure hashes, and human body.

    Raises:
        SpecError: On hidden defaults, unknown semantics, cycles, AST limits,
            or missing dependency closure.
    """
    front, body = parse_spec_document(text=text)
    metric_id = _require_string(mapping=front, key="metric_id")
    _require_string(mapping=front, key="name")
    _require_string(mapping=front, key="kind")
    _require_string(mapping=front, key="canonical_unit")
    dependencies_raw = front["dependencies"] if "dependencies" in front else []
    if not isinstance(dependencies_raw, list):
        raise SpecError("MetricSpec dependencies must be an ordered array")
    dependencies = _validate_dependencies(
        metric_id=metric_id, dependencies=dependencies_raw, stack=stack,
    )
    supplied_dependencies = (
        dependency_specs if dependency_specs is not None else {}
    )
    missing_dependencies = sorted(
        set(dependencies) - set(supplied_dependencies)
    )
    if missing_dependencies:
        raise SpecError(
            "Compiled dependency specs are missing: {}".format(
                ",".join(missing_dependencies)
            )
        )
    for dependency in dependencies:
        dependency_spec = supplied_dependencies[dependency]
        if (
            not isinstance(dependency_spec, dict)
            or "compiled" not in dependency_spec
            or "spec_semantic_hash" not in dependency_spec
            or "spec_closure_hash" not in dependency_spec
            or not isinstance(dependency_spec["compiled"], dict)
        ):
            raise SpecError("Compiled dependency artifact is malformed")
        if dependency_spec["compiled"]["metric_id"] != dependency:
            raise SpecError("Compiled dependency identity differs")
        expected_semantic_hash = content_hash(
            value=dependency_spec["compiled"],
            set_paths=SEMANTIC_SET_PATHS,
        )
        if dependency_spec["spec_semantic_hash"] != expected_semantic_hash:
            raise SpecError("Compiled dependency semantic hash differs")
    selection_value = (
        front["selection_policy"]
        if "selection_policy" in front
        else "legacy_companyfacts_v1"
    )
    compiled = {
        "metric_id": metric_id,
        "name": front["name"],
        "kind": front["kind"],
        "canonical_unit": front["canonical_unit"],
        "reported_unit": front["reported_unit"]
        if "reported_unit" in front
        else front["canonical_unit"],
        "unit_policy": front["unit_policy"]
        if "unit_policy" in front
        else "fixed_canonical",
        "source_mode": front["source_mode"]
        if "source_mode" in front
        else "structured",
        "applicability": _validate_traits(
            applicability=front["applicability"]
        ),
        "required_claims": front["required_claims"]
        if "required_claims" in front
        else {},
        "scope_contract": front["scope_contract"]
        if "scope_contract" in front
        else None,
        "forbidden_confusions": front["forbidden_confusions"]
        if "forbidden_confusions" in front
        else [],
        "inputs": _validate_inputs(
            value=front["inputs"] if "inputs" in front else {}
        ),
        "formula": front["formula"] if "formula" in front else None,
        "top_level_guards": _validate_top_level_guards(
            value=(
                front["top_level_guards"]
                if "top_level_guards" in front
                else []
            )
        ),
        "identity_constraints": front["identity_constraints"]
        if "identity_constraints" in front
        else [],
        "quality_rule": front["quality_rule"]
        if "quality_rule" in front
        else {},
        "legacy_projection": front["legacy_projection"],
        "review_policy": front["review_policy"]
        if "review_policy" in front
        else "none",
        "selection_policy": _expand_selection_policy(value=selection_value),
        "dependencies": list(dependencies),
        "disclosure_group": front["disclosure_group"]
        if "disclosure_group" in front
        else None,
        "numeric_policy": dict(NUMERIC_POLICY),
    }
    if not isinstance(compiled["legacy_projection"], dict):
        raise SpecError("legacy_projection must be an object")
    if compiled["unit_policy"] not in UNIT_POLICIES:
        raise SpecError("MetricSpec unit_policy is unknown")
    if not isinstance(compiled["required_claims"], dict):
        raise SpecError("required_claims must be an object")
    if compiled["scope_contract"] is not None:
        try:
            compiled["scope_contract"] = validate_scope_contract(
                value=compiled["scope_contract"],
            )
        except ScopeContractError as error:
            raise SpecError("MetricSpec scope contract is invalid") from error
        required_scope = {
            dimension: compiled["required_claims"][dimension]
            for dimension in compiled["required_claims"]
            if dimension in compiled["scope_contract"]["allowed_dimensions"]
        }
        if not scope_satisfies_contract(
            contract=compiled["scope_contract"],
            normalized_scope=required_scope,
        ):
            raise SpecError(
                "MetricSpec required claims do not satisfy scope contract"
            )
    elif compiled["source_mode"] == "ai_table":
        raise SpecError("AI table MetricSpec requires scope contract v2")
    if not isinstance(compiled["forbidden_confusions"], list):
        raise SpecError("forbidden_confusions must be an ordered array")
    if len(compiled["forbidden_confusions"]) != len(
        set(compiled["forbidden_confusions"])
    ):
        raise SpecError("forbidden_confusions must be unique")
    _validate_executable_semantics(compiled=compiled)
    _count_ast(node=compiled)
    semantic_hash = content_hash(
        value=compiled,
        set_paths=SEMANTIC_SET_PATHS,
    )
    prompt_bundle = {
        "spec_semantic_hash": semantic_hash,
        "ai_instructions": front["ai_instructions"]
        if "ai_instructions" in front
        else [],
        "prompt_examples": front["prompt_examples"]
        if "prompt_examples" in front
        else [],
        "disclosure_group": compiled["disclosure_group"],
        "prompt_template_version": "1",
    }
    prompt_hash = content_hash(value=prompt_bundle)
    dependency_closures = [
        supplied_dependencies[dependency]["spec_closure_hash"]
        for dependency in dependencies
    ]
    closure_hash = content_hash(
        value={
            "spec_semantic_hash": semantic_hash,
            "dependency_closure_hashes": dependency_closures,
            "execution_semantics_hash": execution_semantics_hash(),
        }
    )
    return {
        "compiled": compiled,
        "spec_semantic_hash": semantic_hash,
        "prompt_bundle_hash": prompt_hash,
        "prompt_bundle": prompt_bundle,
        "spec_closure_hash": closure_hash,
        "body": body,
    }


def compile_spec_file(
    *,
    path: Path,
    dependency_specs: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Dict[str, object]:
    """Read and compile one UTF-8 regular MetricSpec file.

    Args:
        path: Spec Markdown path.
        dependency_specs: Already compiled dependency mappings.

    Returns:
        Result from :func:`compile_spec`.

    Raises:
        SpecError: When the path is unsafe or text is not UTF-8.
    """
    if path.is_symlink() or not path.is_file():
        raise SpecError("MetricSpec must be a regular file: {}".format(path))
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise SpecError("MetricSpec must be UTF-8") from error
    return compile_spec(text=text, dependency_specs=dependency_specs)


def compile_spec_files(
    *, paths: Sequence[Path]
) -> Dict[str, Dict[str, object]]:
    """Compile an exact finite Spec set in dependency order.

    Args:
        paths: Regular UTF-8 Spec files forming one closed dependency set.

    Returns:
        Compiled wrappers keyed by unique metric ID.

    Raises:
        SpecError: On duplicate IDs, missing dependencies, or a dependency
            cycle. No caller-provided compiled semantics are consulted.
    """
    documents: Dict[str, Tuple[Path, Dict[str, object]]] = {}
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise SpecError(
                "MetricSpec must be a regular file: {}".format(path)
            )
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise SpecError("MetricSpec must be UTF-8") from error
        front, _body = parse_spec_document(text=text)
        metric_id = _require_string(mapping=front, key="metric_id")
        if metric_id in documents:
            raise SpecError("MetricSpec metric_id is duplicated")
        documents[metric_id] = (path, front)
    compiled: Dict[str, Dict[str, object]] = {}
    remaining = dict(documents)
    while remaining:
        progressed = False
        for metric_id in list(remaining):
            path, front = remaining[metric_id]
            dependencies = (
                front["dependencies"] if "dependencies" in front else []
            )
            if not isinstance(dependencies, list):
                raise SpecError("MetricSpec dependencies must be an array")
            missing = set(dependencies) - set(documents)
            if missing:
                raise SpecError(
                    "Compiled dependency specs are missing: {}".format(
                        ",".join(sorted(str(item) for item in missing))
                    )
                )
            if not set(dependencies).issubset(compiled):
                continue
            compiled[metric_id] = compile_spec_file(
                path=path,
                dependency_specs={
                    str(dependency): compiled[str(dependency)]
                    for dependency in dependencies
                },
            )
            del remaining[metric_id]
            progressed = True
        if not progressed:
            raise SpecError("MetricSpec dependency cycle detected")
    return compiled
