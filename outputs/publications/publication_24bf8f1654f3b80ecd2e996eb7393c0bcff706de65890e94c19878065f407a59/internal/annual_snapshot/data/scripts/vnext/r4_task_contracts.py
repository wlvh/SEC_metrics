"""Explicit successor R4 task resolution; historical catalogs stay untouched.

The new data catalog binds six successor IDs to retained task structure and
separate native-compiled MetricSpecs. It is not a dynamic task override and does
not activate a Requirement revision or grant provider/SEC execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .requirement_profile import validate_execution_authority
from .sources import resolve_repository_file
from .specs import compile_spec_file
from .table_task_contracts import _contract_identity, _runtime_task_contract
from .table_task_contracts import RUNTIME_TASK_CONTRACT_FIELDS


CATALOG_PATH = "config/r4_task_contracts_v2.json"
CATALOG_FIELDS = frozenset({"record_type", "schema_version", "ratchet_id",
                            "policy_evidence_path", "policy_body_sha256", "tasks"})
TASK_FIELDS = frozenset({"task_contract_id", "metric_id", "legacy_task_contract_id",
                        "metric_spec_path"})


class R4TaskContractError(ValueError):
    """Reject unbound, ambiguous or non-R4 successor task declarations."""


def _r4_metrics(requirement: Mapping) -> list:
    policies = [decision["choice"] for decision in requirement["effective_decisions"].values()
                if decision["status"] == "APPROVED"
                and decision["choice"].get("kind") == "RATCHET_SCOPE"
                and decision["choice"].get("ratchet_id") == "R4"]
    if len(policies) != 1:
        raise R4TaskContractError("R4 ratchet policy is absent or ambiguous")
    return list(policies[0]["metric_ids"])


def _read_catalog(*, repo_root: Path) -> tuple:
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=CATALOG_PATH)
    catalog = strict_json_file(path=path)
    if (type(catalog) is not dict or set(catalog) != CATALOG_FIELDS
            or catalog["record_type"] != "R4_SUCCESSOR_TASK_CATALOG"
            or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 2
            or catalog["ratchet_id"] != "R4" or type(catalog["tasks"]) is not list):
        raise R4TaskContractError("Successor task catalog fields or generation differ")
    for task in catalog["tasks"]:
        if (type(task) is not dict or set(task) != TASK_FIELDS
                or any(type(value) is not str or not value for value in task.values())
                or not task["task_contract_id"].startswith("r4_")
                or not task["metric_spec_path"].startswith("catalog/r4_v2/")):
            raise R4TaskContractError("Successor task identity or path is invalid")
    for key in ("task_contract_id", "metric_id", "legacy_task_contract_id", "metric_spec_path"):
        values = [task[key] for task in catalog["tasks"]]
        if len(values) != len(set(values)):
            raise R4TaskContractError("Successor task catalog has duplicate " + key)
    policy_path = resolve_repository_file(repo_root=repo_root,
                                          repo_relative_path=catalog["policy_evidence_path"])
    evidence = strict_json_file(path=policy_path)
    if (sha256_bytes(content=evidence["raw_body"].encode("utf-8")) != catalog["policy_body_sha256"]
            or evidence["body_sha256"] != catalog["policy_body_sha256"]
            or evidence["evidence_scope"] != "POLICY_CONTENT_ONLY"):
        raise R4TaskContractError("Task policy-content evidence differs")
    return catalog, path


def inspect_r4_task_catalog(*, repo_root: Path) -> dict:
    """Read and compile candidate input data without claiming execution authority."""
    catalog, path = _read_catalog(repo_root=repo_root)
    legacy_path = resolve_repository_file(repo_root=repo_root,
                                          repo_relative_path="catalog/table_task_contracts.json")
    legacy = strict_json_file(path=legacy_path)
    by_id = {item["task_contract_id"]: item for item in legacy["contracts"]}
    contracts = []
    for item in catalog["tasks"]:
        if item["legacy_task_contract_id"] not in by_id:
            raise R4TaskContractError("Retained task identity is absent")
        prior = by_id[item["legacy_task_contract_id"]]
        if prior["metric_ids"] != [item["metric_id"]]:
            raise R4TaskContractError("Successor task relabels a retained metric")
        spec_path = resolve_repository_file(repo_root=repo_root,
                                            repo_relative_path=item["metric_spec_path"])
        spec = compile_spec_file(path=spec_path, dependency_specs={})
        if (spec["compiled"]["metric_id"] != item["metric_id"]
                or spec["compiled"]["kind"] != "direct_numeric"
                or spec["compiled"]["disclosure_group"] != prior["reader_family_id"]):
            raise R4TaskContractError("Successor native MetricSpec identity differs")
        declaration = {**prior, "task_contract_id": item["task_contract_id"],
                       "successor_metric_spec_path": item["metric_spec_path"],
                       "successor_policy_body_sha256": catalog["policy_body_sha256"]}
        contract = {**_contract_identity(contract=declaration), "metric_specs": [{
            "metric_id": item["metric_id"], "path": item["metric_spec_path"],
            "spec_semantic_hash": spec["spec_semantic_hash"],
            "spec_closure_hash": spec["spec_closure_hash"], "compiled": spec["compiled"],
        }]}
        runtime = _runtime_task_contract(contract=contract)
        if set(runtime) != RUNTIME_TASK_CONTRACT_FIELDS:
            raise R4TaskContractError("Successor runtime task shape differs")
        contracts.append(runtime)
    return {"catalog_id": content_hash(value=catalog), "catalog_sha256": sha256_file(path=path),
            "catalog": catalog, "contracts": contracts,
            "execution_authority": "NOT_CHECKED_INSPECTION_ONLY"}


def resolve_r4_task_contract(*, repo_root: Path, requirement: Mapping,
                            task_contract_id: str) -> dict:
    """Resolve a task only when every successor input is execution-bound."""
    validate_execution_authority(repo_root=repo_root, requirement=requirement)
    inspected = inspect_r4_task_catalog(repo_root=repo_root)
    catalog = inspected["catalog"]
    expected_paths = {CATALOG_PATH, catalog["policy_evidence_path"]} | {
        item["metric_spec_path"] for item in catalog["tasks"]}
    if not expected_paths.issubset(requirement["execution_authority"]["files"]):
        raise R4TaskContractError("Requirement does not bind successor task inputs")
    if sorted(_r4_metrics(requirement)) != sorted(item["metric_id"] for item in catalog["tasks"]):
        raise R4TaskContractError("Successor task catalog is not the exact R4 metric set")
    matches = [task for task in inspected["contracts"] if task["task_contract_id"] == task_contract_id]
    if len(matches) != 1:
        raise R4TaskContractError("Successor task is absent or ambiguous")
    return dict(matches[0])
