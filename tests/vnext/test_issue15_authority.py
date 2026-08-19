"""Verify the frozen Issue #15 WB-1 authority transfer.

The positive test loads both explicit Requirement schemas, compares all 13
historical Decision records by canonical hash, recomputes the matrix baseline,
and checks every frozen ``file::symbol`` producer locator.  The negative test
proves one Contract byte invalidates the child snapshot without modifying the
immutable parent fixture.
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
from vnext.requirements import RequirementError, load_requirement_snapshot


PARENT_DIR = REPO_ROOT / "requirements" / "ai_first_v3_3_1"
ISSUE_15_DIR = REPO_ROOT / "requirements" / "issue_15_v1"
CONTRACT_SHA256 = (
    "9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec"
)
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


class Issue15AuthorityTest(unittest.TestCase):
    """Prove WB-1 bytes, Decision history, and frozen inventories close."""

    def test_issue15_snapshot_loads_and_preserves_parent_history(self) -> None:
        """Load Issue #15 and recompute every WB-1 boundary from source bytes."""
        parent_snapshot = load_requirement_snapshot(snapshot_dir=PARENT_DIR)
        issue_snapshot = load_requirement_snapshot(snapshot_dir=ISSUE_15_DIR)
        parent_register = read_json(path=PARENT_DIR / "decision_register.json")
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
            CONTRACT_SHA256,
            sha256_file(path=ISSUE_15_DIR / "CONTRACT.md"),
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
        historical_child = (
            list(issue_decisions[:len(parent_decisions)]) + list(issue_pending)
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
            0,
            issue_snapshot["effective_decisions"]["D-01"]["choice"][
                "retry_count"
            ],
        )
        self.assertNotIn(
            "freeze_replay",
            issue_snapshot["effective_decisions"]["D-26"]["choice"][
                "prohibited_required_test_classes"
            ],
        )
        for decision_id in [
            "D-30", "D-31", "D-32", "D-33", "D-34", "D-35", "D-36",
            "D-37", "D-38",
        ]:
            self.assertEqual(
                1,
                len(issue_snapshot["decision_chains"][decision_id]),
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
            source_receipt["metric_id_set_hash"],
            content_hash(value=metric_ids),
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
            source_receipt["frozen_legacy_keyset_hash"],
            content_hash(value=keys),
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
            inventory["producer_record_set_hash"],
            content_hash(value=producers),
        )
        self.assertEqual(
            inventory["semantic_producer_record_set_hash"],
            content_hash(value=semantic_producers),
        )
        self.assertEqual(metric_ids, inventory["covered_metric_ids"])
        symbols_by_file: Dict[str, Set[str]] = {}
        for producer in producers:
            relative, symbol = producer["producer_id"].split("::", 1)
            if relative not in symbols_by_file:
                symbols_by_file[relative] = module_symbols(
                    path=REPO_ROOT / relative
                )
            self.assertIn(symbol, symbols_by_file[relative])
        self.assertIs(False, inventory["mutable_legacy_retirement_config_ledger"])
        self.assertFalse(
            (REPO_ROOT / "config" / "legacy_retirement_ledger.json").exists()
        )

        self.assertEqual(
            FOUNDATION_SOURCE_COMMIT,
            foundation["foundation_source_commit"],
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

        for relative, binding in baseline["root_business_artifacts"].items():
            path = REPO_ROOT / relative
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

    def test_issue15_contract_byte_change_invalidates_snapshot(self) -> None:
        """Reject one Contract byte while leaving the copied parent untouched."""
        with tempfile.TemporaryDirectory() as temp_dir:
            requirements_dir = Path(temp_dir) / "requirements"
            parent_copy = requirements_dir / "ai_first_v3_3_1"
            issue_copy = requirements_dir / "issue_15_v1"
            shutil.copytree(src=PARENT_DIR, dst=parent_copy)
            shutil.copytree(src=ISSUE_15_DIR, dst=issue_copy)
            with (issue_copy / "CONTRACT.md").open(mode="ab") as file_obj:
                file_obj.write(b"\n")
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)


if __name__ == "__main__":
    unittest.main()
