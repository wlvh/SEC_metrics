"""Load catalog-owned single-table Reader task contracts for WB-6.

The catalog maps metrics to independently qualified target-table tasks without
giving shared Reader, Evidence, or Projector code any metric/company/table
literals.  It is deliberately a static declaration layer: a request still
receives the complete compact document table set and the model chooses its one
target table through the normal locator contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping

from .canonical import content_hash, sha256_file, strict_json_file
from .scope_contract import scope_contract_hash, SCOPE_CONTRACT_VERSION
from .source_strategy import load_source_strategy_registry
from .specs import compile_spec_file, parse_spec_document, SEMANTIC_SET_PATHS
from .specs import SpecError


TABLE_TASK_CATALOG_PATH = Path("catalog/table_task_contracts.json")
FALLBACK_REPRESENTATION_PATH = Path(
    "config/source_strategy_fallback_representation.json",
)
TABLE_TASK_CATALOG_FIELDS = {"contracts", "requirement_id", "schema_version"}
FALLBACK_REPRESENTATION_FIELDS = {
    "fallback_representation_by_metric",
    "record_type",
    "schema_version",
    "source_strategy_registry_sha256",
}
TABLE_TASK_CONTRACT_FIELDS = {
    "actual_incremental_tokens",
    "estimated_incremental_tokens",
    "metric_ids",
    "output_schema_version",
    "reader_contract_id",
    "reader_family_id",
    "representation",
    "required_roles",
    "scope_contract_version",
    "split_baseline_kind",
    "split_reason",
    "system_prompt",
    "task_contract_id",
}
SPLIT_BASELINE_KINDS = {"FIRST_TASK_PLUS_DUPLICATED_FULL_PAYLOAD"}
RESOURCE_LIMIT_ESTIMATE = "NOT_AVAILABLE_RESOURCE_LIMIT"
OUTPUT_SCHEMA_IDENTITY = {
    "schema_version": "2",
    "root_fields": [
        "candidates",
        "disclosure_group",
        "table_locator",
        "unresolved_competing_claims",
    ],
    "scope_claim_fields": [
        "dimension",
        "evidence_locator_ids",
        "raw_value",
    ],
    "scope_evidence_fields": [
        "id",
        "location_type",
        "locator",
        "raw_text",
        "supports_dimensions",
    ],
}
RUNTIME_TASK_CONTRACT_FIELDS = {
    "catalog_task_contract_hash",
    "disclosure_group",
    "forbidden_confusions",
    "identity_constraints",
    "metric_ids",
    "metric_spec_closure_hashes",
    "metric_spec_paths",
    "metric_spec_semantic_hashes",
    "output_schema_hash",
    "output_schema_version",
    "reader_contract_id",
    "reader_family_id",
    "representation",
    "required_claims",
    "required_roles",
    "scope_contract",
    "scope_contract_hash",
    "system_prompt",
    "system_prompt_hash",
    "task_contract_id",
    "task_spec_semantic_hash",
}
TASK_RUN_BINDING_FIELDS = {
    "catalog_task_contract_hash",
    "metric_spec_closure_hashes",
    "metric_spec_paths",
    "metric_spec_semantic_hashes",
    "output_schema_hash",
    "system_prompt_hash",
    "task_contract_id",
    "task_spec_semantic_hash",
}
TASK_EXECUTION_SEMANTIC_FIELDS = {
    "applicability",
    "catalog_task_contract_hash",
    "disclosure_group",
    "forbidden_confusions",
    "identity_constraints",
    "kind",
    "legacy_projection",
    "metric_id",
    "metric_spec_closure_hashes",
    "metric_spec_paths",
    "metric_spec_semantic_hashes",
    "output_schema_hash",
    "output_schema_version",
    "reader_contract_id",
    "reader_family_id",
    "required_claims",
    "required_roles",
    "scope_contract",
    "scope_contract_hash",
    "system_prompt_hash",
    "task_contract_id",
}


class TableTaskContractError(ValueError):
    """Report a malformed, non-single-table, or route-divergent contract."""


def _table_route_sets(
    *, repo_root: Path, registry: Mapping[str, object],
) -> Dict[str, object]:
    """Derive table metrics/families from SourceStrategy plus its bound schema.

    Args:
        repo_root: Repository root owning the representation authority file.
        registry: Already verified immutable SourceStrategy registry result.

    Returns:
        Exact table metric/family sets and fallback-schema byte identity.

    Why:
        A structured-first route does not itself say whether its fallback is a
        table or text.  The small schema below is SHA-bound to SourceStrategy,
        has an exact structured-first metric set, and prevents catalog/matrix
        files from proving each other by projection.
    """
    path = repo_root / FALLBACK_REPRESENTATION_PATH
    if path.is_symlink() or not path.is_file():
        raise TableTaskContractError("Fallback representation authority is unsafe")
    payload = strict_json_file(path=path)
    if (
        type(payload) is not dict
        or set(payload) != FALLBACK_REPRESENTATION_FIELDS
        or payload["schema_version"] != 1
        or payload["record_type"]
        != "ISSUE_15_SOURCE_STRATEGY_FALLBACK_REPRESENTATION"
        or payload["source_strategy_registry_sha256"]
        != registry["registry_sha256"]
        or type(payload["fallback_representation_by_metric"]) is not dict
    ):
        raise TableTaskContractError("Fallback representation authority differs")
    metrics = registry["metrics"]
    expected_fallback_metric_ids = {
        metric_id
        for metric_id, route in metrics.items()
        if route["source_mode"] == "structured_first_ai_fallback"
    }
    representations = payload["fallback_representation_by_metric"]
    if set(representations) != expected_fallback_metric_ids:
        raise TableTaskContractError("Fallback representation metric set differs")
    if any(value not in {"table", "text"} for value in representations.values()):
        raise TableTaskContractError("Fallback representation is invalid")
    table_metric_ids = sorted(
        metric_id
        for metric_id, route in metrics.items()
        if route["source_mode"] == "ai_table"
        or (
            route["source_mode"] == "structured_first_ai_fallback"
            and representations[metric_id] == "table"
        )
    )
    return {
        "table_metric_ids": table_metric_ids,
        "table_family_ids": sorted({
            str(metrics[metric_id]["reader_family_id"])
            for metric_id in table_metric_ids
        }),
        "fallback_representation_by_metric": dict(representations),
        "fallback_representation_sha256": sha256_file(path=path),
    }


def _text(*, value: object, label: str) -> str:
    """Require one non-empty text field.

    Args:
        value: Candidate field value.
        label: Stable diagnostic field name.

    Returns:
        Validated text.
    """
    if type(value) is not str or not value:
        raise TableTaskContractError("{} is empty".format(label))
    return value


def _ordered_texts(*, value: object, label: str) -> List[str]:
    """Require one ordered duplicate-free array of text identities.

    Args:
        value: Candidate JSON value.
        label: Stable diagnostic field name.

    Returns:
        Isolated ordered text list.
    """
    if (
        type(value) is not list
        or not value
        or any(type(item) is not str or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise TableTaskContractError("{} is invalid".format(label))
    return list(value)


def _contract_identity(*, contract: Mapping[str, object]) -> Dict[str, object]:
    """Attach deterministic hashes to one validated catalog contract.

    Args:
        contract: Exact validated catalog contract.

    Returns:
        Contract plus task, output-schema, and system-prompt identities.
    """
    output_schema = {
        **OUTPUT_SCHEMA_IDENTITY,
        "output_schema_version": contract["output_schema_version"],
        "scope_contract_version": contract["scope_contract_version"],
    }
    return {
        **contract,
        "task_contract_hash": content_hash(value=dict(contract)),
        "output_schema_hash": content_hash(value=output_schema),
        "system_prompt_hash": content_hash(value=contract["system_prompt"]),
    }


def _metric_spec_paths(*, repo_root: Path) -> Dict[str, Path]:
    """Index MetricSpec paths by their declared metric identity.

    Args:
        repo_root: Repository root owning the MetricSpec catalog.

    Returns:
        Exact metric ID to regular MetricSpec path mapping.

    Why:
        Task contracts may not hand-maintain a second metric-to-file map.
        Parsing each document's public identity lets SourceStrategy remain the
        sole owner of the target metric set.
    """
    root = repo_root / "catalog" / "metrics"
    if root.is_symlink() or not root.is_dir():
        raise TableTaskContractError("MetricSpec catalog is unsafe")
    paths = {}
    for path in sorted(root.glob("*.md")):
        if path.is_symlink() or not path.is_file():
            raise TableTaskContractError("MetricSpec catalog entry is unsafe")
        try:
            front, _body = parse_spec_document(
                text=path.read_text(encoding="utf-8"),
            )
        except (UnicodeDecodeError, SpecError) as error:
            raise TableTaskContractError("MetricSpec catalog entry is invalid") from error
        metric_id = _text(value=front["metric_id"], label="MetricSpec metric id")
        if metric_id in paths:
            raise TableTaskContractError("MetricSpec metric ID is duplicated")
        paths[metric_id] = path
    return paths


def _contract_metric_specs(
    *, repo_root: Path, contract: Mapping[str, object], routes: Mapping[str, object],
    metric_paths: Mapping[str, Path],
) -> List[Dict[str, object]]:
    """Compile the exact MetricSpecs consumed by one catalog task contract.

    Args:
        repo_root: Repository root used only for portable relative paths.
        contract: One validated catalog contract.
        routes: SourceStrategy routes keyed by metric ID.
        metric_paths: Complete MetricSpec identity index.

    Returns:
        Ordered metric semantic bindings owned by the task contract.

    Why:
        The actual Reader task must bind the same MetricSpec scope and
        semantics as its catalog contract, rather than reusing a broader
        disclosure-level role group.
    """
    bindings = []
    for metric_id in contract["metric_ids"]:
        if metric_id not in metric_paths:
            raise TableTaskContractError("Task MetricSpec is absent")
        try:
            wrapper = compile_spec_file(
                path=metric_paths[metric_id], dependency_specs={},
            )
        except SpecError as error:
            raise TableTaskContractError("Task MetricSpec cannot be compiled") from error
        semantic = wrapper["compiled"]
        route = routes[metric_id]
        if (
            semantic["metric_id"] != metric_id
            or semantic["source_mode"] != route["source_mode"]
            or semantic["disclosure_group"] != contract["reader_family_id"]
            or semantic["scope_contract"] is None
        ):
            raise TableTaskContractError("Task MetricSpec route differs")
        bindings.append(
            {
                "metric_id": metric_id,
                "path": metric_paths[metric_id].relative_to(
                    repo_root,
                ).as_posix(),
                "spec_semantic_hash": wrapper["spec_semantic_hash"],
                "spec_closure_hash": wrapper["spec_closure_hash"],
                "compiled": semantic,
            }
        )
    return bindings


def _table_task_semantic(
    *, runtime: Mapping[str, object], metric_semantic: Mapping[str, object],
) -> Dict[str, object]:
    """Build the executable single-table semantic object for one task.

    Args:
        runtime: Rebuilt catalog task contract without caller-controlled data.
        metric_semantic: Exact compiled direct MetricSpec for the one task role.

    Returns:
        A review/replay semantic object whose hash is the task Spec identity.

    Why:
        A catalog task is not a disclosure-group document.  Giving it its own
        immutable semantic object prevents the formal Workflow and replay from
        silently substituting the old multi-role disclosure contract.
    """
    roles = list(runtime["required_roles"])
    metric_ids = list(runtime["metric_ids"])
    if len(roles) != 1 or len(metric_ids) != 1:
        raise TableTaskContractError("Task execution roles are not single")
    semantic = {
        "task_contract_id": runtime["task_contract_id"],
        "catalog_task_contract_hash": runtime[
            "catalog_task_contract_hash"
        ],
        "reader_family_id": runtime["reader_family_id"],
        "reader_contract_id": runtime["reader_contract_id"],
        "metric_id": metric_semantic["metric_id"],
        "metric_spec_paths": list(runtime["metric_spec_paths"]),
        "metric_spec_semantic_hashes": list(
            runtime["metric_spec_semantic_hashes"]
        ),
        "metric_spec_closure_hashes": list(
            runtime["metric_spec_closure_hashes"]
        ),
        "kind": "single_table_task",
        "disclosure_group": runtime["disclosure_group"],
        "required_roles": roles,
        "required_claims": dict(runtime["required_claims"]),
        "scope_contract": dict(runtime["scope_contract"]),
        "scope_contract_hash": runtime["scope_contract_hash"],
        "identity_constraints": list(runtime["identity_constraints"]),
        "forbidden_confusions": list(runtime["forbidden_confusions"]),
        "applicability": dict(metric_semantic["applicability"]),
        "output_schema_version": runtime["output_schema_version"],
        "output_schema_hash": runtime["output_schema_hash"],
        "system_prompt_hash": runtime["system_prompt_hash"],
        "legacy_projection": {
            "roles": roles,
            "supporting_roles": [],
            "role_metric_ids": {roles[0]: metric_ids[0]},
            "supporting_role_units": {},
        },
    }
    if set(semantic) != TASK_EXECUTION_SEMANTIC_FIELDS:
        raise TableTaskContractError("Task execution semantic fields differ")
    return semantic


def table_task_run_binding(
    *, runtime: Mapping[str, object],
) -> Dict[str, object]:
    """Return the exact task identity persisted in a formal Run manifest.

    Args:
        runtime: Fully rebuilt catalog runtime task contract.

    Returns:
        Immutable task identity fields needed before a Run can replay.
    """
    binding = {
        field: runtime[field]
        for field in TASK_RUN_BINDING_FIELDS
    }
    if set(binding) != TASK_RUN_BINDING_FIELDS:
        raise TableTaskContractError("Task Run binding fields differ")
    return binding


def table_task_execution_plan(
    *, repo_root: Path, task_contract_id: str,
) -> Dict[str, object]:
    """Rebuild one catalog task for Workflow, Run freeze, and replay.

    Args:
        repo_root: Repository root owning catalog, MetricSpec, and strategy.
        task_contract_id: Explicit single-table task selected by a plan.

    Returns:
        Runtime payload task, executable task Spec, direct MetricSpec, and
        manifest binding for the same catalog task identity.

    Raises:
        TableTaskContractError: If any catalog, MetricSpec, or synthetic task
        semantic identity does not reconstruct exactly.
    """
    runtime = resolve_table_task_contract(
        repo_root=repo_root,
        task_contract_id=task_contract_id,
    )
    metric_paths = list(runtime["metric_spec_paths"])
    if len(metric_paths) != 1:
        raise TableTaskContractError("Task execution MetricSpec set is invalid")
    metric_path = repo_root / Path(metric_paths[0])
    if metric_path.is_symlink() or not metric_path.is_file():
        raise TableTaskContractError("Task execution MetricSpec is unsafe")
    try:
        metric_spec = compile_spec_file(
            path=metric_path,
            dependency_specs={},
        )
    except SpecError as error:
        raise TableTaskContractError("Task execution MetricSpec is invalid") from error
    if (
        metric_spec["spec_semantic_hash"]
        != runtime["metric_spec_semantic_hashes"][0]
        or metric_spec["spec_closure_hash"]
        != runtime["metric_spec_closure_hashes"][0]
        or metric_spec["compiled"]["metric_id"] != runtime["metric_ids"][0]
    ):
        raise TableTaskContractError("Task execution MetricSpec differs")
    semantic = _table_task_semantic(
        runtime=runtime,
        metric_semantic=metric_spec["compiled"],
    )
    semantic_hash = content_hash(
        value=semantic,
        set_paths=SEMANTIC_SET_PATHS,
    )
    if runtime["task_spec_semantic_hash"] != semantic_hash:
        raise TableTaskContractError("Task execution Spec identity differs")
    task_spec = {
        "compiled": semantic,
        "spec_semantic_hash": semantic_hash,
        "spec_closure_hash": content_hash(
            value={
                "catalog_task_contract_hash": runtime[
                    "catalog_task_contract_hash"
                ],
                "metric_spec_closure_hashes": runtime[
                    "metric_spec_closure_hashes"
                ],
            },
        ),
    }
    return {
        "runtime_task_contract": runtime,
        "task_spec": task_spec,
        "metric_specs": {
            str(metric_spec["compiled"]["metric_id"]): metric_spec,
        },
        "run_binding": table_task_run_binding(runtime=runtime),
    }


def load_table_task_contracts(*, repo_root: Path) -> Dict[str, object]:
    """Load all catalog single-table contracts against SourceStrategy routes.

    Args:
        repo_root: Repository root owning Issue #15 source authority.

    Returns:
        Validated contracts, their hashes, authorized family IDs, and the
        exact metric set whose AI representation is a table.

    Raises:
        TableTaskContractError: If a contract omits an ai_table metric,
        includes ai_text, merges roles, or diverges from SourceStrategy.
    """
    registry = load_source_strategy_registry(repo_root=repo_root)
    path = repo_root / TABLE_TASK_CATALOG_PATH
    if path.is_symlink() or not path.is_file():
        raise TableTaskContractError("Table task contract catalog is unsafe")
    payload = strict_json_file(path=path)
    if (
        type(payload) is not dict
        or set(payload) != TABLE_TASK_CATALOG_FIELDS
        or payload["schema_version"] != 1
        or payload["requirement_id"] != "issue_15_v1"
        or type(payload["contracts"]) is not list
        or not payload["contracts"]
    ):
        raise TableTaskContractError("Table task contract catalog is invalid")
    routes = registry["metrics"]
    families = registry["families"]
    route_sets = _table_route_sets(repo_root=repo_root, registry=registry)
    expected_table_metric_ids = route_sets["table_metric_ids"]
    expected_table_family_ids = route_sets["table_family_ids"]
    metric_paths = _metric_spec_paths(repo_root=repo_root)
    contracts = []
    contract_ids = set()
    contract_metric_ids = []
    for value in payload["contracts"]:
        if type(value) is not dict or set(value) != TABLE_TASK_CONTRACT_FIELDS:
            raise TableTaskContractError("Table task contract fields are not exact")
        contract = dict(value)
        contract_id = _text(
            value=contract["task_contract_id"], label="task_contract_id",
        )
        if contract_id in contract_ids:
            raise TableTaskContractError("Table task contract ID is duplicated")
        contract_ids.add(contract_id)
        family_id = _text(
            value=contract["reader_family_id"], label="reader_family_id",
        )
        if family_id not in families:
            raise TableTaskContractError("Table task contract family is absent")
        if contract["reader_contract_id"] != families[family_id][
            "reader_contract_id"
        ]:
            raise TableTaskContractError("Reader contract differs from family")
        if contract["representation"] != "table":
            raise TableTaskContractError("Table task representation differs")
        metric_ids = _ordered_texts(
            value=contract["metric_ids"], label="task metric_ids",
        )
        roles = _ordered_texts(
            value=contract["required_roles"], label="task required_roles",
        )
        if len(roles) != 1 or len(metric_ids) != 1:
            raise TableTaskContractError("Task contract must have one role")
        if contract["scope_contract_version"] != SCOPE_CONTRACT_VERSION:
            raise TableTaskContractError("Task scope contract version differs")
        if contract["output_schema_version"] != "2":
            raise TableTaskContractError("Task output schema version differs")
        _text(value=contract["system_prompt"], label="task system_prompt")
        _text(value=contract["split_reason"], label="task split_reason")
        if contract["split_baseline_kind"] not in SPLIT_BASELINE_KINDS:
            raise TableTaskContractError("Task split baseline kind is invalid")
        if not (
            type(contract["estimated_incremental_tokens"]) is int
            and contract["estimated_incremental_tokens"] >= 0
            or contract["estimated_incremental_tokens"]
            == RESOURCE_LIMIT_ESTIMATE
        ):
            raise TableTaskContractError("Task estimated incremental tokens invalid")
        actual_tokens = contract["actual_incremental_tokens"]
        if not (
            actual_tokens == "NOT_RUN"
            or type(actual_tokens) is int and actual_tokens >= 0
        ):
            raise TableTaskContractError("Task actual incremental tokens invalid")
        for metric_id in metric_ids:
            if metric_id not in routes:
                raise TableTaskContractError("Task metric is absent from registry")
            route = routes[metric_id]
            if (
                route["reader_family_id"] != family_id
                or metric_id not in expected_table_metric_ids
            ):
                raise TableTaskContractError("Task metric route is not table AI")
            contract_metric_ids.append(metric_id)
        metric_specs = _contract_metric_specs(
            repo_root=repo_root,
            contract=contract,
            routes=routes,
            metric_paths=metric_paths,
        )
        contracts.append({
            **_contract_identity(contract=contract),
            "metric_specs": metric_specs,
        })
    if len(contract_metric_ids) != len(set(contract_metric_ids)):
        raise TableTaskContractError("Task metrics are assigned more than once")
    if sorted(contract_metric_ids) != expected_table_metric_ids:
        raise TableTaskContractError("Table task metric exact set differs")
    authorized_family_ids = sorted({item["reader_family_id"] for item in contracts})
    if authorized_family_ids != expected_table_family_ids:
        raise TableTaskContractError("Table task family exact set differs")
    return {
        "catalog_sha256": sha256_file(path=path),
        "contracts": contracts,
        "authorized_family_ids": authorized_family_ids,
        "table_metric_ids": expected_table_metric_ids,
        "table_family_ids": expected_table_family_ids,
        "fallback_representation_by_metric": route_sets[
            "fallback_representation_by_metric"
        ],
        "fallback_representation_sha256": route_sets[
            "fallback_representation_sha256"
        ],
        "requirement_closure_hash": registry["requirement_closure_hash"],
    }


def resolve_table_task_contract(
    *, repo_root: Path, task_contract_id: str,
) -> Dict[str, object]:
    """Build one runtime Reader task from a catalog single-table contract.

    Args:
        repo_root: Repository root containing SourceStrategy and MetricSpecs.
        task_contract_id: Explicit catalog task identity selected by the caller.

    Returns:
        Exact runtime task contract for Reader, adapter, audit, and replay.

    Why:
        There is no runtime selector/planner here.  The caller names one
        catalog contract, and this factory mechanically joins its catalog,
        SourceStrategy, MetricSpec, scope, schema, and prompt identities.
    """
    contracts = load_table_task_contracts(repo_root=repo_root)["contracts"]
    matches = [
        contract
        for contract in contracts
        if contract["task_contract_id"] == task_contract_id
    ]
    if len(matches) != 1:
        raise TableTaskContractError("Table task contract is absent")
    contract = matches[0]
    metric_specs = contract["metric_specs"]
    if len(metric_specs) != 1:
        raise TableTaskContractError("Table task MetricSpec set is not single")
    metric = metric_specs[0]["compiled"]
    scope_contract = metric["scope_contract"]
    runtime = {
        "task_contract_id": contract["task_contract_id"],
        "catalog_task_contract_hash": contract["task_contract_hash"],
        "reader_family_id": contract["reader_family_id"],
        "reader_contract_id": contract["reader_contract_id"],
        "representation": contract["representation"],
        "metric_ids": list(contract["metric_ids"]),
        "metric_spec_paths": [metric_specs[0]["path"]],
        "metric_spec_semantic_hashes": [
            metric_specs[0]["spec_semantic_hash"],
        ],
        "metric_spec_closure_hashes": [
            metric_specs[0]["spec_closure_hash"],
        ],
        "disclosure_group": metric["disclosure_group"],
        "required_roles": list(contract["required_roles"]),
        "required_claims": dict(metric["required_claims"]),
        "scope_contract": scope_contract,
        "scope_contract_hash": scope_contract_hash(contract=scope_contract),
        "identity_constraints": list(metric["identity_constraints"]),
        "forbidden_confusions": list(metric["forbidden_confusions"]),
        "system_prompt": contract["system_prompt"],
        "system_prompt_hash": contract["system_prompt_hash"],
        "output_schema_version": contract["output_schema_version"],
        "output_schema_hash": contract["output_schema_hash"],
    }
    runtime["task_spec_semantic_hash"] = content_hash(
        value=_table_task_semantic(
            runtime=runtime,
            metric_semantic=metric,
        ),
        set_paths=SEMANTIC_SET_PATHS,
    )
    if set(runtime) != RUNTIME_TASK_CONTRACT_FIELDS:
        raise TableTaskContractError("Runtime task contract fields differ")
    return runtime
