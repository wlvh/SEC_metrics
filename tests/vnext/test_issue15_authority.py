"""Verify the frozen Issue #15 WB-1 authority transfer.

The positive test loads both explicit Requirement schemas, compares all 13
historical Decision records by canonical hash, recomputes the matrix baseline,
and checks every frozen ``file::symbol`` producer locator.  Negative tests
prove Contract, receipt, parent-disposition, and producer-scope drift fail
closed without modifying the immutable parent fixture.
"""

from __future__ import annotations

import ast
import csv
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Dict, Set

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, sha256_file
from vnext.requirements import (
    ISSUE_15_BASE_PIPELINE_SHA256,
    ISSUE_15_EXPECTED_PRODUCER_EXACT_SET_HASH,
    ISSUE_15_EXPECTED_SEMANTIC_RECORD_SET_HASH,
    RequirementError,
    load_requirement_snapshot,
)


PARENT_DIR = REPO_ROOT / "requirements" / "ai_first_v3_3_1"
ISSUE_15_DIR = REPO_ROOT / "requirements" / "issue_15_v1"
CONTRACT_SHA256 = "9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec"
FOUNDATION_SOURCE_COMMIT = "f1cc44342e6814522ec2688cf3674f7ec442be8d"
FOUNDATION_MERGE_COMMIT = "4d02db6a474f93eec9e058d780e206b4504ab24d"


def read_json(*, path: Path) -> Dict[str, object]:
    """Read one trusted test JSON object with explicit UTF-8 decoding.

    Args:
        path: Existing Requirement JSON file.

    Returns:
        Parsed root object.
    """
    value = json.loads(s=path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Test JSON root must be an object")
    return value


def module_symbols(*, path: Path) -> Set[str]:
    """Return top-level function, class, and assignment names in one module.

    Args:
        path: Existing UTF-8 Python source file.

    Returns:
        Top-level symbols addressable by the inventory's ``file::symbol``
        convention.
    """
    tree = ast.parse(source=path.read_text(encoding="utf-8"))
    symbols: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.add(target.id)
                    if target.id == "RETIRED_LEGACY_PRODUCER_NAMES":
                        symbols.update(
                            child.value
                            for child in ast.walk(node.value)
                            if isinstance(child, ast.Constant)
                            and isinstance(child.value, str)
                        )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.add(node.target.id)
    return symbols


def direct_callers(*, path: Path, callee: str) -> Set[str]:
    """Return top-level functions that directly invoke one named function.

    Args:
        path: Existing UTF-8 Python source file.
        callee: Unqualified function name used at a direct call site.

    Returns:
        Exact direct-caller set from the audited source AST.
    """
    tree = ast.parse(source=path.read_text(encoding="utf-8"))
    callers = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == callee
            for child in ast.walk(node)
        ):
            callers.add(node.name)
    return callers


def copy_test_repository(*, temp_dir: str) -> Path:
    """Copy both Requirement snapshots and every bound foundation receipt.

    Args:
        temp_dir: Empty temporary directory used as a repository root.

    Returns:
        Copied ``requirements/issue_15_v1`` directory.
    """
    repository_root = Path(temp_dir)
    requirements_dir = repository_root / "requirements"
    parent_copy = requirements_dir / "ai_first_v3_3_1"
    issue_copy = requirements_dir / "issue_15_v1"
    shutil.copytree(src=PARENT_DIR, dst=parent_copy)
    shutil.copytree(src=ISSUE_15_DIR, dst=issue_copy)
    foundation = read_json(path=ISSUE_15_DIR / "foundation_verification_receipt.json")
    for binding in foundation["receipt_bindings"]:
        relative = Path(binding["path"])
        destination = repository_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src=REPO_ROOT / relative, dst=destination)
    return issue_copy


def write_json(*, path: Path, value: Dict[str, object]) -> None:
    """Write one deterministic test JSON object as UTF-8.

    Args:
        path: Destination fixture path.
        value: Complete JSON object.

    Expected output:
        The test copy changes without mutating repository authority bytes.
    """
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def rebind_inventory(*, issue_copy: Path, inventory: Dict[str, object]) -> None:
    """Write a forged inventory and update only its snapshot byte binding.

    Args:
        issue_copy: Copied child Requirement directory.
        inventory: Mutated inventory object under negative test.

    Expected output:
        Baseline byte checks pass so the independent semantic closure must
        reject the forged content.
    """
    inventory_path = issue_copy / "legacy_semantic_producer_inventory.json"
    write_json(path=inventory_path, value=inventory)
    baseline_path = issue_copy / "baseline_manifest.json"
    baseline = read_json(path=baseline_path)
    binding = baseline["snapshot_files"]["legacy_semantic_producer_inventory.json"]
    binding["sha256"] = sha256_file(path=inventory_path)
    binding["size"] = inventory_path.stat().st_size
    write_json(path=baseline_path, value=baseline)


class Issue15AuthorityTest(unittest.TestCase):
    """Prove WB-1 bytes, Decision history, and frozen inventories close."""

    def test_issue15_snapshot_loads_and_preserves_parent_history(self) -> None:
        """Load Issue #15 and recompute every WB-1 boundary from source bytes."""
        parent_snapshot = load_requirement_snapshot(snapshot_dir=PARENT_DIR)
        issue_snapshot = load_requirement_snapshot(snapshot_dir=ISSUE_15_DIR)
        parent_register = read_json(path=PARENT_DIR / "decision_register.json")
        parent_inventory = read_json(path=PARENT_DIR / "legacy_path_inventory.json")
        issue_register = read_json(path=ISSUE_15_DIR / "decision_register.json")
        baseline = read_json(path=ISSUE_15_DIR / "baseline_manifest.json")
        transfer = read_json(path=ISSUE_15_DIR / "transfer_manifest.json")
        source_receipt = read_json(
            path=ISSUE_15_DIR / "source_strategy_baseline_receipt.json"
        )
        inventory = read_json(
            path=ISSUE_15_DIR / "legacy_semantic_producer_inventory.json"
        )
        foundation = read_json(
            path=ISSUE_15_DIR / "foundation_verification_receipt.json"
        )

        self.assertEqual("issue_15_v1", issue_snapshot["requirement_id"])
        self.assertEqual(
            parent_snapshot["requirement_closure_hash"],
            issue_snapshot["parent_requirement_closure_hash"],
        )
        self.assertEqual(
            "SUPERSEDED_BY_NEW_DECISION",
            transfer["decision_transfer"]["parent_contract_risk_transitions"][0][
                "status"
            ],
        )
        self.assertEqual(
            CONTRACT_SHA256, sha256_file(path=ISSUE_15_DIR / "CONTRACT.md"),
        )
        contract = (ISSUE_15_DIR / "CONTRACT.md").read_text(encoding="utf-8")
        self.assertNotIn("/ PR #14 主正文", contract)
        self.assertNotIn("合并前 PR #14 停止新增 Reader 代码", contract)

        parent_decisions = parent_register["decisions"]
        parent_pending = parent_register["pending_decisions"]
        issue_decisions = issue_register["decisions"]
        issue_pending = issue_register["pending_decisions"]
        self.assertEqual(12, len(parent_decisions))
        self.assertEqual(1, len(parent_pending))
        historical_parent = list(parent_decisions) + list(parent_pending)
        historical_child = list(issue_decisions[: len(parent_decisions)]) + list(
            issue_pending
        )
        self.assertEqual(13, len(historical_child))
        self.assertEqual(
            [content_hash(value=record) for record in historical_parent],
            [content_hash(value=record) for record in historical_child],
        )
        self.assertEqual([], issue_snapshot["pending_decision_ids"])
        self.assertEqual(4, len(issue_snapshot["decision_chains"]["D-01"]))
        self.assertEqual(2, len(issue_snapshot["decision_chains"]["D-26"]))
        self.assertEqual(
            set(baseline["effective_decision_ids"]),
            set(issue_snapshot["effective_decisions"]),
        )
        self.assertEqual(
            0, issue_snapshot["effective_decisions"]["D-01"]["choice"]["retry_count"],
        )
        self.assertNotIn(
            "freeze_replay",
            issue_snapshot["effective_decisions"]["D-26"]["choice"][
                "prohibited_required_test_classes"
            ],
        )
        for decision_id in [
            "D-30",
            "D-31",
            "D-32",
            "D-33",
            "D-34",
            "D-35",
            "D-36",
            "D-37",
            "D-38",
        ]:
            self.assertEqual(
                1, len(issue_snapshot["decision_chains"][decision_id]),
            )

        parent_files = transfer["parent_snapshot_files"]
        for filename, binding in parent_files.items():
            parent_path = PARENT_DIR / filename
            self.assertEqual(binding["sha256"], sha256_file(path=parent_path))
            self.assertEqual(binding["size"], parent_path.stat().st_size)

        matrix_path = REPO_ROOT / "outputs" / "metrics_matrix.csv"
        with matrix_path.open(mode="r", encoding="utf-8", newline="") as file_obj:
            rows = list(csv.DictReader(f=file_obj))
        metric_ids = sorted({row["metric_id"] for row in rows})
        keys = sorted(
            [
                {"company": row["company"], "metric_id": row["metric_id"]}
                for row in rows
            ],
            key=lambda row: (row["company"], row["metric_id"]),
        )
        self.assertEqual(230, len(rows))
        self.assertEqual(39, len(metric_ids))
        self.assertEqual(source_receipt["matrix_sha256"], sha256_file(path=matrix_path))
        self.assertEqual(source_receipt["metric_id_set"], metric_ids)
        self.assertEqual(
            source_receipt["metric_id_set_hash"], content_hash(value=metric_ids),
        )
        self.assertEqual(
            source_receipt["rows_by_metric"],
            dict(sorted(Counter(row["metric_id"] for row in rows).items())),
        )
        self.assertEqual(
            source_receipt["rows_by_current_status"],
            dict(sorted(Counter(row["status"] for row in rows).items())),
        )
        self.assertEqual(
            source_receipt["frozen_legacy_keyset_hash"], content_hash(value=keys),
        )

        producers = inventory["producers"]
        semantic_producers = [
            producer
            for producer in producers
            if producer["kind"] == "SEMANTIC_PRODUCER"
        ]
        semantic_producer_ids = sorted(
            producer["producer_id"] for producer in semantic_producers
        )
        self.assertEqual(
            inventory["producer_exact_set_hash"],
            content_hash(value=semantic_producer_ids),
        )
        self.assertEqual(
            inventory["producer_record_set_hash"], content_hash(value=producers),
        )
        self.assertEqual(
            inventory["semantic_producer_record_set_hash"],
            content_hash(value=semantic_producers),
        )
        self.assertEqual(
            ISSUE_15_EXPECTED_PRODUCER_EXACT_SET_HASH,
            content_hash(value=semantic_producer_ids),
        )
        self.assertEqual(
            ISSUE_15_EXPECTED_SEMANTIC_RECORD_SET_HASH,
            content_hash(value=semantic_producers),
        )
        self.assertEqual(
            ISSUE_15_BASE_PIPELINE_SHA256,
            inventory["producer_source_files"]["scripts/sec_pipeline.py"]["sha256"],
        )
        expected_parent_groups = {
            group: parent_inventory[group]
            for group in sorted(parent_inventory["migration_rules"])
        }
        self.assertEqual(
            expected_parent_groups, inventory["parent_inventory_groups"],
        )
        self.assertEqual(
            set(expected_parent_groups), set(inventory["parent_symbol_dispositions"]),
        )
        for group, members in expected_parent_groups.items():
            self.assertEqual(
                set(members), set(inventory["parent_symbol_dispositions"][group]),
            )
        select_target = next(
            producer
            for producer in semantic_producers
            if producer["producer_id"]
            == "scripts/sec_pipeline.py::select_target_component"
        )
        self.assertEqual(
            ["A04", "A08", "A10", "B06", "B07"], select_target["active_metric_ids"],
        )
        self.assertEqual(["B03"], select_target["retired_metric_ids"])
        scope_evidence = inventory["scope_evidence_by_producer"][
            "scripts/sec_pipeline.py::select_target_component"
        ]
        evidenced_callers = {
            caller.split("::", 1)[1]
            for caller in (
                set(scope_evidence["active_callers"])
                | set(scope_evidence["retired_callers"])
            )
        }
        self.assertEqual(
            evidenced_callers,
            direct_callers(
                path=REPO_ROOT / "scripts" / "sec_pipeline.py",
                callee="select_target_component",
            ),
        )
        self.assertEqual(
            select_target["active_metric_ids"],
            sorted(
                {
                    metric_id
                    for metric_ids_by_caller in scope_evidence[
                        "active_callers"
                    ].values()
                    for metric_id in metric_ids_by_caller
                }
            ),
        )
        self.assertEqual(
            select_target["retired_metric_ids"],
            sorted(
                {
                    metric_id
                    for metric_ids_by_caller in scope_evidence[
                        "retired_callers"
                    ].values()
                    for metric_id in metric_ids_by_caller
                }
            ),
        )
        self.assertEqual(metric_ids, inventory["covered_metric_ids"])
        symbols_by_file: Dict[str, Set[str]] = {}
        for producer in producers:
            relative, symbol = producer["producer_id"].split("::", 1)
            if relative not in symbols_by_file:
                symbols_by_file[relative] = module_symbols(path=REPO_ROOT / relative)
            self.assertIn(symbol, symbols_by_file[relative])
        self.assertIs(False, inventory["mutable_legacy_retirement_config_ledger"])
        self.assertFalse(
            (REPO_ROOT / "config" / "legacy_retirement_ledger.json").exists()
        )

        self.assertEqual(
            FOUNDATION_SOURCE_COMMIT, foundation["foundation_source_commit"],
        )
        self.assertEqual(FOUNDATION_MERGE_COMMIT, foundation["foundation_merge_commit"])
        self.assertEqual("issue-15-foundation-v1", foundation["foundation_tag"])
        self.assertEqual("FAST_LOCAL_ONLY", foundation["highest_evidence_level"])
        self.assertEqual(0, foundation["real_external_provider_egress_count"])
        self.assertEqual(0, foundation["paid_provider_call_count"])
        self.assertEqual(
            [0, 0, 0, 0],
            [row["return_code"] for row in foundation["verification_commands"]],
        )
        bound_paths = {binding["path"] for binding in foundation["receipt_bindings"]}
        for binding in foundation["receipt_bindings"]:
            path = REPO_ROOT / binding["path"]
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertEqual(binding["size"], path.stat().st_size)
            self.assertEqual(binding["sha256"], sha256_file(path=path))
        for command in foundation["verification_commands"]:
            self.assertTrue(set(command["receipt_paths"]).issubset(bound_paths))

        for relative, binding in baseline["root_business_artifacts"].items():
            path = REPO_ROOT / relative
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

    def test_issue15_contract_byte_change_invalidates_snapshot(self) -> None:
        """Reject one Contract byte while leaving the copied parent untouched."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            with (issue_copy / "CONTRACT.md").open(mode="ab") as file_obj:
                file_obj.write(b"\n")
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_missing_foundation_receipt_invalidates_snapshot(self) -> None:
        """Reject a binding whose declared repository file is absent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            foundation = read_json(
                path=issue_copy / "foundation_verification_receipt.json"
            )
            repository_root = issue_copy.parents[1]
            missing = repository_root / foundation["receipt_bindings"][0]["path"]
            missing.unlink()
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_one_byte_foundation_receipt_tamper_invalidates_snapshot(self) -> None:
        """Reject same-size supporting evidence with one changed byte."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            foundation = read_json(
                path=issue_copy / "foundation_verification_receipt.json"
            )
            repository_root = issue_copy.parents[1]
            target = repository_root / foundation["receipt_bindings"][2]["path"]
            with target.open(mode="r+b") as file_obj:
                original = file_obj.read(1)
                file_obj.seek(0)
                file_obj.write(b"[" if original != b"[" else b"{")
            self.assertEqual(
                foundation["receipt_bindings"][2]["size"], target.stat().st_size,
            )
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_missing_parent_production_disposition_invalidates_snapshot(self,) -> None:
        """Reject a self-rebound inventory missing one parent producer."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            inventory = read_json(
                path=issue_copy / "legacy_semantic_producer_inventory.json"
            )
            del inventory["parent_symbol_dispositions"][
                "additional_migrated_production_symbols"
            ]["custom_da_observation_note"]
            rebind_inventory(issue_copy=issue_copy, inventory=inventory)
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_self_consistent_producer_scope_tamper_invalidates_snapshot(self,) -> None:
        """Reject forged active scope even after all internal hashes are fixed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            inventory = read_json(
                path=issue_copy / "legacy_semantic_producer_inventory.json"
            )
            producer = next(
                row
                for row in inventory["producers"]
                if row["producer_id"]
                == "scripts/sec_pipeline.py::select_target_component"
            )
            producer["active_metric_ids"].remove("A04")
            producer["covered_metric_ids"].remove("A04")
            semantic = [
                row
                for row in inventory["producers"]
                if row["kind"] == "SEMANTIC_PRODUCER"
            ]
            metric_ids = inventory["metric_id_set"]
            inventory["coverage_by_metric"] = {
                metric_id: [
                    row["producer_id"]
                    for row in semantic
                    if metric_id in row["covered_metric_ids"]
                ]
                for metric_id in metric_ids
            }
            inventory["producer_record_set_hash"] = content_hash(
                value=inventory["producers"]
            )
            inventory["semantic_producer_record_set_hash"] = content_hash(
                value=semantic
            )
            rebind_inventory(issue_copy=issue_copy, inventory=inventory)
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)


if __name__ == "__main__":
    unittest.main()
