"""Load the Issue #15 SourceStrategy registry and ratchet ReleasePlan.

The registry owns target source routing and reader-family literals for all 39
metrics. The separate ReleasePlan is the only owner of current migration
state. Both files are byte-bound by the Issue #15 Requirement closure before
their semantic fields are accepted here.
"""

from __future__ import annotations

import csv
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
    "added_metric_ids",
    "authority_hashes",
    "cumulative_metric_ids",
    "cumulative_vnext_result_keys",
    "parent_release_plan_content_id",
    "parent_release_plan_id",
    "reader_family_versions",
    "record_type",
    "release_plan_content_id",
    "release_plan_id",
    "release_stage",
    "requirement_id",
    "requirement_closure_hash",
    "retired_legacy_producer_ids",
    "schema_version",
}
RELEASE_PLAN_INDEX_FIELDS = {
    "active_release_plan_content_id",
    "active_release_plan_id",
    "record_type",
    "release_plan_index_id",
    "release_plan_paths",
    "requirement_id",
    "schema_version",
}
RELEASE_PLAN_INDEX_ENTRY_FIELDS = {
    "path", "release_plan_content_id", "release_plan_id",
}
RELEASE_AUTHORITY_FIELDS = {
    "company_trait_catalog_sha256",
    "company_registry_sha256",
    "deterministic_metric_catalog_sha256",
    "event_route_catalog_sha256",
    "final_metric_id_set_hash",
    "frozen_legacy_keyset_hash",
    "producer_inventory_sha256",
    "qualification_matrix_subset_hash",
    "source_strategy_registry_sha256",
}
RELEASE_PLAN_IDS = (
    "issue_15_zero_ai_r1",
    "issue_15_zero_ai_r2",
)


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


def _result_keys(*, value: object, label: str) -> List[Dict[str, str]]:
    """Return one unique ordered company/metric coordinate list.

    Args:
        value: Candidate ReleasePlan coordinate array.
        label: Stable diagnostic location.

    Returns:
        Isolated exact-key mappings in declared order.
    """
    if not isinstance(value, list):
        raise SourceStrategyError("{} must be an array".format(label))
    keys = []
    identities = []
    for entry_value in value:
        entry = _object(value=entry_value, label=label + " entry")
        _exact_fields(
            value=entry,
            expected={"company_id", "metric_id"},
            label=label + " entry",
        )
        company_id = _nonempty_string(
            value=entry["company_id"], label=label + " company id"
        )
        metric_id = _nonempty_string(
            value=entry["metric_id"], label=label + " metric id"
        )
        keys.append({"company_id": company_id, "metric_id": metric_id})
        identities.append((company_id, metric_id))
    if len(identities) != len(set(identities)):
        raise SourceStrategyError("{} contains duplicates".format(label))
    return keys


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


def _company_ids(*, repo_root: Path) -> List[str]:
    """Return the exact sorted company identity set from registry authority."""
    path = repo_root / "config" / "company_registry.csv"
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        rows = [dict(row) for row in csv.DictReader(file_obj)]
    if any("company_id" not in row for row in rows):
        raise SourceStrategyError("Company registry identity is incomplete")
    company_ids = sorted(str(row["company_id"]) for row in rows)
    if not company_ids or len(company_ids) != len(set(company_ids)):
        raise SourceStrategyError("Company registry exact set differs")
    return company_ids


def _retired_producer_ids(
    *, repo_root: Path, cumulative_metric_ids: Sequence[str]
) -> List[str]:
    """Derive the exact semantic-producer retirement set for one ratchet."""
    inventory = _json_object(
        path=(repo_root / "requirements" / ISSUE_15_REQUIREMENT_ID
              / "legacy_semantic_producer_inventory.json"),
        label="legacy semantic producer inventory",
    )
    if "producers" not in inventory or not isinstance(
        inventory["producers"], list
    ):
        raise SourceStrategyError("Legacy producer inventory is invalid")
    metric_ids = set(cumulative_metric_ids)
    retired = []
    for producer in inventory["producers"]:
        if not isinstance(producer, dict) or not {
            "covered_metric_ids", "kind", "producer_id",
        }.issubset(producer):
            raise SourceStrategyError("Legacy producer record is invalid")
        if (
            producer["kind"] == "SEMANTIC_PRODUCER"
            and metric_ids.intersection(producer["covered_metric_ids"])
        ):
            retired.append(str(producer["producer_id"]))
    retired.sort()
    if not retired or len(retired) != len(set(retired)):
        raise SourceStrategyError("Retired producer exact set is invalid")
    return retired


def _reader_family_versions(
    *, cumulative_metric_ids: Sequence[str], registry: Mapping[str, object]
) -> Dict[str, str]:
    """Derive family-version closure for cumulative metric routes."""
    metrics = _object(value=registry["metrics"], label="metric routes")
    families = _object(value=registry["families"], label="reader families")
    family_ids = sorted({
        str(_object(value=metrics[metric_id], label="metric route")[
            "reader_family_id"
        ])
        for metric_id in cumulative_metric_ids
    })
    return {
        family_id: str(_object(
            value=families[family_id], label="reader family"
        )["reader_contract_id"])
        for family_id in family_ids
    }


def _release_authority(
    *, repo_root: Path, registry: Mapping[str, object],
    qualification_subset: Sequence[Mapping[str, str]],
) -> Dict[str, str]:
    """Return the complete Contract section-4 authority hash mapping."""
    baseline = _json_object(
        path=(repo_root / "requirements" / ISSUE_15_REQUIREMENT_ID
              / "source_strategy_baseline_receipt.json"),
        label="SourceStrategy baseline receipt",
    )
    return {
        "company_trait_catalog_sha256": sha256_file(
            path=repo_root / "catalog" / "company_traits.yaml"
        ),
        "company_registry_sha256": sha256_file(
            path=repo_root / "config" / "company_registry.csv"
        ),
        "deterministic_metric_catalog_sha256": sha256_file(
            path=repo_root / "catalog" / "deterministic_metrics.json"
        ),
        "event_route_catalog_sha256": sha256_file(
            path=repo_root / "catalog" / "event_routes.json"
        ),
        "final_metric_id_set_hash": content_hash(
            value=registry["metric_ids"]
        ),
        "frozen_legacy_keyset_hash": str(
            baseline["frozen_legacy_keyset_hash"]
        ),
        "producer_inventory_sha256": sha256_file(
            path=(repo_root / "requirements" / ISSUE_15_REQUIREMENT_ID
                  / "legacy_semantic_producer_inventory.json")
        ),
        "qualification_matrix_subset_hash": content_hash(
            value=list(qualification_subset)
        ),
        "source_strategy_registry_sha256": str(registry["registry_sha256"]),
    }


def _validate_release_plan(
    *, repo_root: Path, plan: Mapping[str, object],
    registry: Mapping[str, object], requirement_closure_hash: str,
) -> Dict[str, object]:
    """Validate one immutable full-schema ReleasePlan independently."""
    value = _object(value=plan, label="Issue #15 ReleasePlan")
    _exact_fields(
        value=value, expected=RELEASE_PLAN_FIELDS,
        label="Issue #15 ReleasePlan",
    )
    if (
        value["schema_version"] != 2
        or value["record_type"] != "ISSUE_15_RELEASE_PLAN"
        or value["requirement_id"] != ISSUE_15_REQUIREMENT_ID
        or value["requirement_closure_hash"] != requirement_closure_hash
    ):
        raise SourceStrategyError("Issue #15 ReleasePlan identity differs")
    release_plan_id = _nonempty_string(
        value=value["release_plan_id"], label="release plan id"
    )
    if release_plan_id not in RELEASE_PLAN_IDS:
        raise SourceStrategyError("ReleasePlan id is not authorized")
    expected_stage = "R1" if release_plan_id == RELEASE_PLAN_IDS[0] else "R2"
    if value["release_stage"] != expected_stage:
        raise SourceStrategyError("ReleasePlan stage differs")
    added = _string_list(
        value=value["added_metric_ids"], label="added metric ids",
        allow_empty=False,
    )
    cumulative = _string_list(
        value=value["cumulative_metric_ids"], label="cumulative metric ids",
        allow_empty=False,
    )
    if (
        added != sorted(added)
        or cumulative != sorted(cumulative)
        or not set(cumulative).issubset(set(registry["metric_ids"]))
    ):
        raise SourceStrategyError("ReleasePlan metric sets differ")
    _result_keys(
        value=value["cumulative_vnext_result_keys"],
        label="ReleasePlan cumulative result keys",
    )
    retired = _string_list(
        value=value["retired_legacy_producer_ids"],
        label="retired legacy producer ids",
        allow_empty=True,
    )
    if retired != sorted(retired):
        raise SourceStrategyError("ReleasePlan retired producer order differs")
    expected_versions = _reader_family_versions(
        cumulative_metric_ids=cumulative, registry=registry,
    )
    if value["reader_family_versions"] != expected_versions:
        raise SourceStrategyError("ReleasePlan reader family versions differ")
    qualification_subset = _qualification_subset(
        cumulative_metric_ids=cumulative, metrics=registry["metrics"],
    )
    authority = _object(
        value=value["authority_hashes"], label="release authority hashes"
    )
    _exact_fields(
        value=authority, expected=RELEASE_AUTHORITY_FIELDS,
        label="release authority hashes",
    )
    if authority != _release_authority(
        repo_root=repo_root, registry=registry,
        qualification_subset=qualification_subset,
    ):
        raise SourceStrategyError("Issue #15 ReleasePlan authority differs")
    body = {
        field: value[field]
        for field in value if field != "release_plan_content_id"
    }
    if value["release_plan_content_id"] != content_hash(value=body):
        raise SourceStrategyError("ReleasePlan content identity differs")
    return {
        **value,
        "qualification_matrix_subset": qualification_subset,
    }


def load_issue15_release_plans(*, repo_root: Path) -> Dict[str, object]:
    """Load and validate the complete immutable R1-to-R2 plan chain."""
    registry = load_source_strategy_registry(repo_root=repo_root)
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / ISSUE_15_REQUIREMENT_ID
    )
    index_path = repo_root / "config" / "issue_15_release_plan.json"
    index = _json_object(path=index_path, label="ReleasePlan index")
    _exact_fields(
        value=index, expected=RELEASE_PLAN_INDEX_FIELDS,
        label="ReleasePlan index",
    )
    if (
        index["schema_version"] != 1
        or index["record_type"] != "ISSUE_15_RELEASE_PLAN_INDEX"
        or index["requirement_id"] != ISSUE_15_REQUIREMENT_ID
    ):
        raise SourceStrategyError("ReleasePlan index identity differs")
    index_body = {
        field: index[field]
        for field in index if field != "release_plan_index_id"
    }
    if index["release_plan_index_id"] != content_hash(value=index_body):
        raise SourceStrategyError("ReleasePlan index content identity differs")
    entries = index["release_plan_paths"]
    if not isinstance(entries, list) or len(entries) != len(RELEASE_PLAN_IDS):
        raise SourceStrategyError("ReleasePlan index exact set differs")
    plans = []
    paths = []
    for entry_value, expected_id in zip(entries, RELEASE_PLAN_IDS):
        entry = _object(value=entry_value, label="ReleasePlan index entry")
        _exact_fields(
            value=entry, expected=RELEASE_PLAN_INDEX_ENTRY_FIELDS,
            label="ReleasePlan index entry",
        )
        if entry["release_plan_id"] != expected_id:
            raise SourceStrategyError("ReleasePlan index order differs")
        relative = Path(str(entry["path"]))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[:2] != ("config", "release_plans")
            or relative.suffix != ".json"
        ):
            raise SourceStrategyError("ReleasePlan path is unsafe")
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise SourceStrategyError("ReleasePlan file is unavailable")
        plan = _validate_release_plan(
            repo_root=repo_root,
            plan=_json_object(path=path, label="Issue #15 ReleasePlan"),
            registry=registry,
            requirement_closure_hash=str(
                requirement["requirement_closure_hash"]
            ),
        )
        if plan["release_plan_content_id"] != entry[
            "release_plan_content_id"
        ]:
            raise SourceStrategyError("ReleasePlan index binding differs")
        plans.append(plan)
        paths.append(path)
    transitions = []
    for ordinal, plan in enumerate(plans):
        parent = plans[ordinal - 1] if ordinal else None
        expected_parent_id = (
            parent["release_plan_id"] if parent is not None else None
        )
        expected_parent_content = (
            parent["release_plan_content_id"] if parent is not None else None
        )
        expected_added = (
            sorted(set(plan["cumulative_metric_ids"]) - set(
                parent["cumulative_metric_ids"]
            ))
            if parent is not None
            else list(plan["cumulative_metric_ids"])
        )
        parent_metrics = (
            set(parent["cumulative_metric_ids"])
            if parent is not None else set()
        )
        child_metrics = set(plan["cumulative_metric_ids"])
        parent_keys = (
            {
                (entry["company_id"], entry["metric_id"])
                for entry in parent["cumulative_vnext_result_keys"]
            }
            if parent is not None else set()
        )
        child_keys = {
            (entry["company_id"], entry["metric_id"])
            for entry in plan["cumulative_vnext_result_keys"]
        }
        parent_retired = (
            set(parent["retired_legacy_producer_ids"])
            if parent is not None else set()
        )
        child_retired = set(plan["retired_legacy_producer_ids"])
        removed_metric_ids = sorted(parent_metrics - child_metrics)
        removed_result_keys = [
            {"company_id": company_id, "metric_id": metric_id}
            for company_id, metric_id in sorted(parent_keys - child_keys)
        ]
        unretired_producer_ids = sorted(parent_retired - child_retired)
        if (
            removed_metric_ids
            or removed_result_keys
            or unretired_producer_ids
        ):
            raise SourceStrategyError(
                "ReleasePlan no-removal gate failed"
            )
        if (
            plan["parent_release_plan_id"] != expected_parent_id
            or plan["parent_release_plan_content_id"]
            != expected_parent_content
            or plan["added_metric_ids"] != expected_added
        ):
            raise SourceStrategyError("ReleasePlan ratchet chain differs")
        expected_keys = [
            {"company_id": company_id, "metric_id": metric_id}
            for company_id in _company_ids(repo_root=repo_root)
            for metric_id in plan["cumulative_metric_ids"]
        ]
        if plan["cumulative_vnext_result_keys"] != expected_keys:
            raise SourceStrategyError(
                "ReleasePlan cumulative result keys differ"
            )
        expected_retired = _retired_producer_ids(
            repo_root=repo_root,
            cumulative_metric_ids=plan["cumulative_metric_ids"],
        )
        if plan["retired_legacy_producer_ids"] != expected_retired:
            raise SourceStrategyError(
                "ReleasePlan retired producer set differs"
            )
        transitions.append({
            "parent_release_plan_content_id": expected_parent_content,
            "release_plan_content_id": plan["release_plan_content_id"],
            "added_metric_ids": list(plan["added_metric_ids"]),
            "removed_metric_ids": removed_metric_ids,
            "removed_vnext_result_keys": removed_result_keys,
            "unretired_legacy_producer_ids": unretired_producer_ids,
        })
    active = plans[-1]
    if (
        index["active_release_plan_id"] != active["release_plan_id"]
        or index["active_release_plan_content_id"]
        != active["release_plan_content_id"]
    ):
        raise SourceStrategyError("ReleasePlan active tip differs")
    return {
        "active_release_plan_id": active["release_plan_id"],
        "index": index,
        "index_sha256": sha256_file(path=index_path),
        "plans": plans,
        "ratchet_transitions": transitions,
        "plan_paths": paths,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "source_strategy_registry_sha256": registry["registry_sha256"],
    }


def load_issue15_release_plan(
    *, repo_root: Path, release_plan_id: str
) -> Dict[str, object]:
    """Return one named immutable plan from the validated complete chain."""
    plan_id = _nonempty_string(
        value=release_plan_id, label="requested release plan id"
    )
    loaded = load_issue15_release_plans(repo_root=repo_root)
    matches = [
        (plan, path)
        for plan, path in zip(loaded["plans"], loaded["plan_paths"])
        if plan["release_plan_id"] == plan_id
    ]
    if len(matches) != 1:
        raise SourceStrategyError("Requested ReleasePlan is unavailable")
    plan, path = matches[0]
    return {
        "authority_hashes": plan["authority_hashes"],
        "cumulative_metric_ids": plan["cumulative_metric_ids"],
        "qualification_matrix_subset": plan["qualification_matrix_subset"],
        "release_plan": plan,
        "release_plan_chain": loaded["plans"],
        "ratchet_transitions": loaded["ratchet_transitions"],
        "release_plan_content_id": plan["release_plan_content_id"],
        "release_plan_sha256": sha256_file(path=path),
        "source_strategy_registry_sha256": loaded[
            "source_strategy_registry_sha256"
        ],
    }
