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
from .scope_contract import SCOPE_CONTRACT_VERSION
from .source_strategy import load_source_strategy_registry


TABLE_TASK_CATALOG_PATH = Path("catalog/table_task_contracts.json")
TABLE_TASK_CATALOG_FIELDS = {"contracts", "requirement_id", "schema_version"}
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
    "split_reason",
    "system_prompt",
    "task_contract_id",
}
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


class TableTaskContractError(ValueError):
    """Report a malformed, non-single-table, or route-divergent contract."""


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
        if len(roles) != 1:
            raise TableTaskContractError("Task contract must have one role")
        if contract["scope_contract_version"] != SCOPE_CONTRACT_VERSION:
            raise TableTaskContractError("Task scope contract version differs")
        if contract["output_schema_version"] != "2":
            raise TableTaskContractError("Task output schema version differs")
        _text(value=contract["system_prompt"], label="task system_prompt")
        _text(value=contract["split_reason"], label="task split_reason")
        if type(contract["estimated_incremental_tokens"]) is not int or (
            contract["estimated_incremental_tokens"] < 0
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
                or route["source_mode"] not in {
                    "ai_table",
                    "structured_first_ai_fallback",
                }
            ):
                raise TableTaskContractError("Task metric route is not table AI")
            contract_metric_ids.append(metric_id)
        contracts.append(_contract_identity(contract=contract))
    if len(contract_metric_ids) != len(set(contract_metric_ids)):
        raise TableTaskContractError("Task metrics are assigned more than once")
    ai_table_metrics = sorted(
        metric_id
        for metric_id, route in routes.items()
        if route["source_mode"] == "ai_table"
    )
    if not set(ai_table_metrics).issubset(set(contract_metric_ids)):
        raise TableTaskContractError("An ai_table metric lacks a task contract")
    authorized_family_ids = sorted({item["reader_family_id"] for item in contracts})
    return {
        "catalog_sha256": sha256_file(path=path),
        "contracts": contracts,
        "authorized_family_ids": authorized_family_ids,
        "table_metric_ids": sorted(contract_metric_ids),
        "requirement_closure_hash": registry["requirement_closure_hash"],
    }
