"""Pure deterministic catalog validation and Spec compilation.

Fourteen supported metric definitions retain the existing formula/arity,
unit, dimension and concept-priority checks. No release workflow is imported.
"""
import json
from pathlib import Path
from typing import Dict, Mapping
from .canonical import strict_json_file
from .specs import compile_spec


class ZeroAiReleaseError(ValueError):
    """Report a source, result, compatibility, or publication invariant."""


R2_METRIC_IDS = (
    "A01", "A02", "A05", "A06", "A07", "A08", "A10",
    "B01", "B02", "B03", "B04", "B05", "B07", "B08", "B09", "B12",
    "C01", "E01", "E02", "E03", "E04", "E05",
)


R2_ADDED_METRIC_IDS = tuple(
    metric_id for metric_id in R2_METRIC_IDS
    if metric_id not in {"B01", "B03"}
)


R2_DETERMINISTIC_METRIC_IDS = tuple(
    metric_id for metric_id in R2_ADDED_METRIC_IDS
    if not metric_id.startswith("E") and metric_id != "C01"
)


DETERMINISTIC_CATALOG_FIELDS = {
    "metrics", "record_type", "schema_version",
}


DETERMINISTIC_ROUTE_FIELDS = {
    "adapter_id",
    "applicability",
    "branches",
    "canonical_unit",
    "continuity_policy",
    "name",
    "result_period_role",
    "source_class",
    "source_role",
    "success_status",
}


DETERMINISTIC_BRANCH_FIELDS = {
    "branch_id", "components", "formula_id", "quality",
}


DETERMINISTIC_COMPONENT_FIELDS = {
    "accession_role",
    "approved_concepts",
    "dimension_policy",
    "period_role",
    "required_dimensions",
    "role",
    "unit",
}


FORMULA_IDS = {
    "average_denominator_ratio",
    "difference",
    "direct",
    "growth",
    "interest_coverage",
    "ratio",
}


FORMULA_ARITIES = {
    "average_denominator_ratio": {3},
    "difference": {2},
    "direct": {1},
    "growth": {2},
    "interest_coverage": {2, 3},
    "ratio": {2},
}


def _required_text(*, value: object, label: str) -> str:
    """Return one required catalog text value.

    Args:
        value: Candidate catalog value.
        label: Stable diagnostic field name.

    Returns:
        Non-empty text.
    """
    if not isinstance(value, str) or not value:
        raise ZeroAiReleaseError(label + " must be non-empty text")
    return value


def _validate_deterministic_component(
    *, component: object,
) -> Dict[str, object]:
    """Validate one catalog-owned fact selection component."""
    if not isinstance(component, dict) or set(component) != (
        DETERMINISTIC_COMPONENT_FIELDS
    ):
        raise ZeroAiReleaseError("Deterministic component fields differ")
    value = dict(component)
    _required_text(value=value["role"], label="Component role")
    _required_text(value=value["unit"], label="Component unit")
    if value["accession_role"] not in {"current", "prior"}:
        raise ZeroAiReleaseError("Component accession role is invalid")
    if value["period_role"] not in {
        "current_annual", "current_instant",
        "prior_annual", "prior_instant",
    }:
        raise ZeroAiReleaseError("Component period role is invalid")
    concepts = value["approved_concepts"]
    if (
        not isinstance(concepts, list)
        or not concepts
        or any(not isinstance(item, str) or not item for item in concepts)
        or len(concepts) != len(set(concepts))
    ):
        raise ZeroAiReleaseError("Component concept priority is invalid")
    dimensions = value["required_dimensions"]
    if (
        not isinstance(dimensions, dict)
        or any(
            not isinstance(axis, str)
            or not axis
            or not isinstance(member, str)
            or not member
            for axis, member in dimensions.items()
        )
    ):
        raise ZeroAiReleaseError("Component dimensions are invalid")
    if value["dimension_policy"] not in {"EXACT", "NONE"}:
        raise ZeroAiReleaseError("Component dimension policy is invalid")
    if value["dimension_policy"] == "NONE" and dimensions:
        raise ZeroAiReleaseError("NONE dimension policy cannot name dimensions")
    return value


def _validate_deterministic_branch(*, branch: object) -> Dict[str, object]:
    """Validate one ordered deterministic calculation branch."""
    if not isinstance(branch, dict) or set(branch) != (
        DETERMINISTIC_BRANCH_FIELDS
    ):
        raise ZeroAiReleaseError("Deterministic branch fields differ")
    value = dict(branch)
    _required_text(value=value["branch_id"], label="Branch id")
    if value["formula_id"] not in FORMULA_IDS:
        raise ZeroAiReleaseError("Deterministic branch formula is invalid")
    if value["quality"] not in {"EXACT", "APPROX"}:
        raise ZeroAiReleaseError("Deterministic branch quality is invalid")
    if not isinstance(value["components"], list):
        raise ZeroAiReleaseError("Deterministic branch components differ")
    components = [
        _validate_deterministic_component(component=component)
        for component in value["components"]
    ]
    if len(components) not in FORMULA_ARITIES[value["formula_id"]]:
        raise ZeroAiReleaseError("Deterministic formula arity differs")
    roles = [str(component["role"]) for component in components]
    if len(roles) != len(set(roles)):
        raise ZeroAiReleaseError("Deterministic component role is duplicated")
    value["components"] = components
    return value


def _load_deterministic_catalog(*, repo_root: Path) -> Dict[str, object]:
    """Load and validate the fourteen-metric deterministic catalog.

    Args:
        repo_root: Repository containing catalog authority.

    Returns:
        Strict catalog mapping.
    """
    payload = strict_json_file(
        path=repo_root / "catalog" / "deterministic_metrics.json"
    )
    if not isinstance(payload, dict) or set(payload) != (
        DETERMINISTIC_CATALOG_FIELDS
    ):
        raise ZeroAiReleaseError("Deterministic metric catalog fields differ")
    catalog = dict(payload)
    if (
        catalog["schema_version"] != 2
        or catalog["record_type"] != "DETERMINISTIC_METRIC_CATALOG"
        or not isinstance(catalog["metrics"], dict)
        or set(catalog["metrics"]) != set(R2_DETERMINISTIC_METRIC_IDS)
    ):
        raise ZeroAiReleaseError("Deterministic metric catalog exact set differs")
    for metric_id, route_value in catalog["metrics"].items():
        if not isinstance(route_value, dict) or set(route_value) != (
            DETERMINISTIC_ROUTE_FIELDS
        ):
            raise ZeroAiReleaseError("Deterministic metric route fields differ")
        route = dict(route_value)
        for field in ("canonical_unit", "name", "source_class"):
            _required_text(
                value=route[field], label="Deterministic route " + field,
            )
        expected_source_role = {
            "accession_xbrl": "target_accession_instance",
            "companyfacts": "companyfacts",
        }
        applicability = route["applicability"]
        if (
            route["adapter_id"] not in expected_source_role
            or route["source_role"] != expected_source_role[
                route["adapter_id"]
            ]
            or route["result_period_role"] not in {
                "current_annual", "current_instant",
            }
            or route["continuity_policy"] not in {
                "ALLOW", "REQUIRE_CONTINUOUS",
            }
            or route["success_status"] not in {"DIM_XBRL_OK", "OK"}
            or not isinstance(applicability, dict)
            or set(applicability) != {"all", "none"}
            or any(
                not isinstance(values, list)
                or any(not isinstance(item, str) or not item for item in values)
                or len(values) != len(set(values))
                for values in applicability.values()
            )
            or not isinstance(route["branches"], list)
            or not route["branches"]
        ):
            raise ZeroAiReleaseError(
                "Deterministic metric route is invalid: " + metric_id
            )
        branches = [
            _validate_deterministic_branch(branch=branch)
            for branch in route["branches"]
        ]
        branch_ids = [str(branch["branch_id"]) for branch in branches]
        if len(branch_ids) != len(set(branch_ids)):
            raise ZeroAiReleaseError("Deterministic branch id is duplicated")
        route["branches"] = branches
        catalog["metrics"][metric_id] = route
    return catalog


def _compiled_deterministic_spec(
    *, metric_id: str, route: Mapping[str, object],
) -> Dict[str, object]:
    """Compile one direct projection Spec solely from catalog semantics."""
    front = {
        "metric_id": metric_id,
        "name": route["name"],
        "kind": "direct_numeric",
        "canonical_unit": route["canonical_unit"],
        "unit_policy": "fixed_canonical",
        "source_mode": "structured",
        "applicability": route["applicability"],
        "identity_constraints": [],
        "legacy_projection": {
            "status": route["success_status"],
            "source_class": route["source_class"],
        },
        "dependencies": [],
    }
    text = "---\n{}\n---\n\n# {}\n".format(
        json.dumps(front, ensure_ascii=False, indent=2), route["name"],
    )
    return compile_spec(text=text)

