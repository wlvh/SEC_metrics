"""Load the Issue #15 SourceStrategy registry and ratchet ReleasePlan.

The registry owns target source routing and reader-family literals for all 39
metrics. The separate ReleasePlan is the only owner of current migration
state. Both files are byte-bound by the Issue #15 Requirement closure before
their semantic fields are accepted here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from .canonical import content_hash, sha256_file, strict_json_file
from .requirements import ISSUE_15_REQUIREMENT_ID, load_requirement_snapshot


ALLOWED_SOURCE_MODES = [
    "structured_only",
    "structured_first_ai_fallback",
    "ai_table",
    "ai_text",
]
ALLOWED_STRUCTURED_ROUTE_IDS = {
    "8k_item_index_v1",
    "accession_xbrl_v1",
    "auditor_fact_v1",
    "companyfacts_v1",
    "ecd_xbrl_v1",
}
ALLOWED_COVERAGE_MODES = {"OPEN_WORLD", "CLOSED_WORLD"}
FORBIDDEN_MIGRATION_STATES = {
    "ROUTE_INVENTORY_ONLY",
    "SHADOW_ONLY",
    "MIGRATED_PRODUCTION",
}
GENERIC_FORBIDDEN_LITERAL_DENYLIST = {
    "risk",
    "value",
    "event",
    "income",
    "current",
}
REGISTRY_FIELDS = {
    "allowed_source_modes",
    "families",
    "metrics",
    "migration_state_authority",
    "requirement_id",
    "schema_version",
}
FAMILY_FIELDS = {"forbidden_production_literals", "reader_contract_id"}
METRIC_FIELDS = {
    "applicability_rule_id",
    "coverage_mode",
    "fallback_trigger_codes",
    "reader_family_id",
    "source_mode",
    "structured_route_id",
}
RELEASE_PLAN_FIELDS = {
    "authority_hashes",
    "cumulative_metric_ids",
    "release_plan_id",
    "requirement_id",
    "schema_version",
}
RELEASE_AUTHORITY_FIELDS = {
    "company_registry_sha256",
    "final_metric_id_set_hash",
    "frozen_legacy_keyset_hash",
    "producer_inventory_sha256",
    "qualification_matrix_subset_hash",
    "source_strategy_registry_sha256",
}


class SourceStrategyError(ValueError):
    """Report malformed, incomplete, or detached SourceStrategy authority."""


def _object(*, value: object, label: str) -> Dict[str, object]:
    """Return one isolated mapping or fail with a stable diagnostic.

    Args:
        value: Parsed candidate value.
        label: Human-readable schema location.

    Returns:
        Shallow isolated mapping.

    Raises:
        SourceStrategyError: When the value is not an object.
    """
    if not isinstance(value, dict):
        raise SourceStrategyError("{} must be an object".format(label))
    return dict(value)


def _exact_fields(
    *, value: Mapping[str, object], expected: set[str], label: str
) -> None:
    """Require an exact field set so unknown policy inputs fail fast.

    Args:
        value: Mapping under validation.
        expected: Exact required and allowed keys.
        label: Human-readable schema location.

    Raises:
        SourceStrategyError: When one key is missing or extra.
    """
    if set(value) != expected:
        raise SourceStrategyError("{} fields are not exact".format(label))


def _nonempty_string(*, value: object, label: str) -> str:
    """Return one required non-empty string.

    Args:
        value: Candidate scalar.
        label: Human-readable schema location.

    Returns:
        Validated string.

    Raises:
        SourceStrategyError: When the scalar is absent or empty.
    """
    if not isinstance(value, str) or not value:
        raise SourceStrategyError("{} must be a non-empty string".format(label))
    return value


def _string_list(
    *, value: object, label: str, allow_empty: bool
) -> List[str]:
    """Return a duplicate-free ordered string list.

    Args:
        value: Candidate list.
        label: Human-readable schema location.
        allow_empty: Whether an empty list is valid for this field.

    Returns:
        Validated isolated list.

    Raises:
        SourceStrategyError: On wrong type, empty item, duplicate, or an
            unexpectedly empty list.
    """
    if not isinstance(value, list):
        raise SourceStrategyError("{} must be an array".format(label))
    items = list(value)
    if (
        (not allow_empty and not items)
        or any(not isinstance(item, str) or not item for item in items)
        or len(items) != len(set(items))
    ):
        raise SourceStrategyError("{} string set is invalid".format(label))
    return items


def _json_object(*, path: Path, label: str) -> Dict[str, object]:
    """Read one strict UTF-8 JSON object.

    Args:
        path: Exact regular JSON path.
        label: Human-readable schema location.

    Returns:
        Parsed isolated object.
    """
    return _object(value=strict_json_file(path=path), label=label)


def _validate_family(
    *, family_id: str, family: Mapping[str, object]
) -> List[str]:
    """Validate one family and return its forbidden production literals.

    Args:
        family_id: Stable registry family identity.
        family: Family policy object.

    Returns:
        Ordered family-owned business literals.

    Raises:
        SourceStrategyError: On schema, identity, or generic-literal drift.
    """
    _nonempty_string(value=family_id, label="reader family id")
    _exact_fields(value=family, expected=FAMILY_FIELDS, label="reader family")
    _nonempty_string(
        value=family["reader_contract_id"], label="reader contract id"
    )
    literals = _string_list(
        value=family["forbidden_production_literals"],
        label="forbidden production literals",
        allow_empty=True,
    )
    folded = [literal.casefold() for literal in literals]
    if len(folded) != len(set(folded)):
        raise SourceStrategyError("Family literals differ only by case")
    if GENERIC_FORBIDDEN_LITERAL_DENYLIST.intersection(folded):
        raise SourceStrategyError("Generic words cannot be forbidden literals")
    return literals


def _validate_metric(
    *, metric_id: str, metric: Mapping[str, object], family_ids: set[str]
) -> None:
    """Validate one exact metric route without accepting migration state.

    Args:
        metric_id: Stable metric identity.
        metric: Metric route object.
        family_ids: Exact family identities in the same registry.

    Raises:
        SourceStrategyError: On family, mode, route, fallback, coverage, or
            applicability drift.
    """
    _nonempty_string(value=metric_id, label="metric id")
    _exact_fields(value=metric, expected=METRIC_FIELDS, label="metric route")
    family_id = _nonempty_string(
        value=metric["reader_family_id"], label="metric reader family id"
    )
    if family_id not in family_ids:
        raise SourceStrategyError("Metric references an unknown reader family")
    source_mode = _nonempty_string(
        value=metric["source_mode"], label="metric source mode"
    )
    if source_mode not in ALLOWED_SOURCE_MODES:
        raise SourceStrategyError("Metric source mode is invalid")
    route_id = metric["structured_route_id"]
    fallback_codes = _string_list(
        value=metric["fallback_trigger_codes"],
        label="fallback trigger codes",
        allow_empty=True,
    )
    if source_mode in {"structured_only", "structured_first_ai_fallback"}:
        if route_id not in ALLOWED_STRUCTURED_ROUTE_IDS:
            raise SourceStrategyError("Structured route id is invalid")
    elif route_id is not None:
        raise SourceStrategyError("AI-only metric cannot name a structured route")
    if source_mode == "structured_first_ai_fallback":
        if not fallback_codes:
            raise SourceStrategyError("Structured-first fallback codes are required")
    elif fallback_codes:
        raise SourceStrategyError("Fallback codes require structured-first mode")
    if metric["coverage_mode"] not in ALLOWED_COVERAGE_MODES:
        raise SourceStrategyError("Metric coverage mode is invalid")
    _nonempty_string(
        value=metric["applicability_rule_id"],
        label="metric applicability rule id",
    )


def load_source_strategy_registry(*, repo_root: Path) -> Dict[str, object]:
    """Load and verify the 39-metric Issue #15 SourceStrategy registry.

    Args:
        repo_root: Repository root containing config and Requirement bytes.

    Returns:
        Registry, exact metric set, literal union, and byte identity.

    Raises:
        SourceStrategyError: On Requirement, schema, coverage, source-mode,
            family-literal, migration-state, or byte-binding drift.
    """
    requirement_dir = repo_root / "requirements" / ISSUE_15_REQUIREMENT_ID
    requirement = load_requirement_snapshot(snapshot_dir=requirement_dir)
    registry_path = repo_root / "config" / "source_strategy_registry.json"
    registry = _json_object(path=registry_path, label="SourceStrategy registry")
    _exact_fields(
        value=registry, expected=REGISTRY_FIELDS, label="SourceStrategy registry"
    )
    if registry["schema_version"] != 1:
        raise SourceStrategyError("SourceStrategy schema version differs")
    if registry["requirement_id"] != ISSUE_15_REQUIREMENT_ID:
        raise SourceStrategyError("SourceStrategy Requirement identity differs")
    if registry["allowed_source_modes"] != ALLOWED_SOURCE_MODES:
        raise SourceStrategyError("Allowed source modes differ")
    if (
        registry["migration_state_authority"]
        != "ReleasePlan.cumulative_metric_ids"
    ):
        raise SourceStrategyError("Migration state authority differs")

    # Registry bytes cannot smuggle one of the three runtime migration states
    # into a family or metric field while preserving the top-level schema.
    serialized = json.dumps(registry, ensure_ascii=False, sort_keys=True)
    if "ai_event_text" in serialized:
        raise SourceStrategyError("ai_event_text is not a supported source mode")
    if any(state in serialized for state in FORBIDDEN_MIGRATION_STATES):
        raise SourceStrategyError("Registry contains current migration state")

    families = _object(value=registry["families"], label="reader families")
    if not families:
        raise SourceStrategyError("Reader family set cannot be empty")
    literal_union: List[str] = []
    for family_id in sorted(families):
        family = _object(
            value=families[family_id], label="reader family " + family_id
        )
        literal_union.extend(
            _validate_family(family_id=family_id, family=family)
        )
    folded_union = [literal.casefold() for literal in literal_union]
    if len(folded_union) != len(set(folded_union)):
        raise SourceStrategyError("Forbidden literal ownership is ambiguous")

    metrics = _object(value=registry["metrics"], label="metric routes")
    metric_ids = sorted(metrics)
    for metric_id in metric_ids:
        metric = _object(value=metrics[metric_id], label="metric " + metric_id)
        _validate_metric(
            metric_id=metric_id, metric=metric, family_ids=set(families)
        )

    baseline = _json_object(
        path=requirement_dir / "source_strategy_baseline_receipt.json",
        label="SourceStrategy baseline receipt",
    )
    if metric_ids != baseline["metric_id_set"] or len(metric_ids) != 39:
        raise SourceStrategyError("SourceStrategy metric exact set differs")
    expected_mode_by_metric = {
        metric_id: source_mode
        for source_mode, mode_metric_ids in baseline[
            "metrics_by_target_source_mode"
        ].items()
        for metric_id in mode_metric_ids
    }
    actual_mode_by_metric = {
        metric_id: metrics[metric_id]["source_mode"] for metric_id in metric_ids
    }
    if actual_mode_by_metric != expected_mode_by_metric:
        raise SourceStrategyError("SourceStrategy mode mapping differs")
    registry_sha256 = sha256_file(path=registry_path)
    if (
        requirement["hashes"]["source_strategy_registry_sha256"]
        != registry_sha256
    ):
        raise SourceStrategyError("SourceStrategy Requirement binding differs")
    return {
        "families": families,
        "forbidden_production_literals": literal_union,
        "metric_ids": metric_ids,
        "metrics": metrics,
        "registry": registry,
        "registry_sha256": registry_sha256,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
    }


def _qualification_subset(
    *, cumulative_metric_ids: Sequence[str], metrics: Mapping[str, object]
) -> List[Dict[str, str]]:
    """Derive the exact cumulative metrics that can require model evidence.

    Args:
        cumulative_metric_ids: Ordered ReleasePlan ratchet set.
        metrics: Validated registry metric routes.

    Returns:
        Ordered identity rows for non-structured-only metrics.
    """
    subset = []
    for metric_id in cumulative_metric_ids:
        metric = _object(value=metrics[metric_id], label="metric " + metric_id)
        if metric["source_mode"] == "structured_only":
            continue
        subset.append(
            {
                "metric_id": metric_id,
                "reader_family_id": str(metric["reader_family_id"]),
                "source_mode": str(metric["source_mode"]),
            }
        )
    return subset


def load_issue15_release_plan(*, repo_root: Path) -> Dict[str, object]:
    """Load the sole Issue #15 migration-state authority.

    Args:
        repo_root: Repository root containing config and Requirement bytes.

    Returns:
        Exact ReleasePlan plus derived qualification subset and byte identity.

    Raises:
        SourceStrategyError: On schema, cumulative-set, authority-hash, or
            Requirement-binding drift.
    """
    registry = load_source_strategy_registry(repo_root=repo_root)
    plan_path = repo_root / "config" / "issue_15_release_plan.json"
    plan = _json_object(path=plan_path, label="Issue #15 ReleasePlan")
    _exact_fields(
        value=plan, expected=RELEASE_PLAN_FIELDS, label="Issue #15 ReleasePlan"
    )
    if plan["schema_version"] != 1:
        raise SourceStrategyError("Issue #15 ReleasePlan schema differs")
    if plan["requirement_id"] != ISSUE_15_REQUIREMENT_ID:
        raise SourceStrategyError("Issue #15 ReleasePlan identity differs")
    _nonempty_string(value=plan["release_plan_id"], label="release plan id")
    cumulative = _string_list(
        value=plan["cumulative_metric_ids"],
        label="cumulative metric ids",
        allow_empty=True,
    )
    if cumulative != sorted(cumulative):
        raise SourceStrategyError("Cumulative metric ids must be sorted")
    if not set(cumulative).issubset(set(registry["metric_ids"])):
        raise SourceStrategyError("Cumulative metric ids escape the registry")
    authority = _object(
        value=plan["authority_hashes"], label="release authority hashes"
    )
    _exact_fields(
        value=authority,
        expected=RELEASE_AUTHORITY_FIELDS,
        label="release authority hashes",
    )
    baseline = _json_object(
        path=(
            repo_root
            / "requirements"
            / ISSUE_15_REQUIREMENT_ID
            / "source_strategy_baseline_receipt.json"
        ),
        label="SourceStrategy baseline receipt",
    )
    qualification_subset = _qualification_subset(
        cumulative_metric_ids=cumulative, metrics=registry["metrics"]
    )
    expected_authority = {
        "company_registry_sha256": sha256_file(
            path=repo_root / "config" / "company_registry.csv"
        ),
        "final_metric_id_set_hash": content_hash(value=registry["metric_ids"]),
        "frozen_legacy_keyset_hash": baseline["frozen_legacy_keyset_hash"],
        "producer_inventory_sha256": sha256_file(
            path=(
                repo_root
                / "requirements"
                / ISSUE_15_REQUIREMENT_ID
                / "legacy_semantic_producer_inventory.json"
            )
        ),
        "qualification_matrix_subset_hash": content_hash(
            value=qualification_subset
        ),
        "source_strategy_registry_sha256": registry["registry_sha256"],
    }
    if authority != expected_authority:
        raise SourceStrategyError("Issue #15 ReleasePlan authority differs")
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / ISSUE_15_REQUIREMENT_ID
    )
    plan_sha256 = sha256_file(path=plan_path)
    if requirement["hashes"]["issue_15_release_plan_sha256"] != plan_sha256:
        raise SourceStrategyError("Issue #15 ReleasePlan binding differs")
    return {
        "authority_hashes": authority,
        "cumulative_metric_ids": cumulative,
        "qualification_matrix_subset": qualification_subset,
        "release_plan": plan,
        "release_plan_sha256": plan_sha256,
        "source_strategy_registry_sha256": registry["registry_sha256"],
    }
