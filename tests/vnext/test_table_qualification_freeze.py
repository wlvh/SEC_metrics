"""Validate static PR-3 table qualification freeze inputs before receipt write."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_qualification_freeze import _protected_closure
from vnext.table_qualification_freeze import _protected_closure_drift
from vnext.table_qualification_freeze import _measurement_receipts
from vnext.table_qualification_freeze import _split_cost_receipts
from vnext.table_task_contracts import load_table_task_contracts


REPO_ROOT = Path(__file__).resolve().parents[2]


class TableQualificationFreezeTest(unittest.TestCase):
    """Ensure the freeze is table-family complete before any qualification."""

    def test_matrix_and_task_contracts_bind_same_table_families(self) -> None:
        """Require each authorized table family to have one frozen matrix entry."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        contracts = load_table_task_contracts(repo_root=REPO_ROOT)
        self.assertEqual(
            contracts["authorized_family_ids"],
            sorted(matrix["entries"]),
        )
        for family_id in contracts["authorized_family_ids"]:
            with self.subTest(family_id=family_id):
                entry = matrix["entries"][family_id]
                family_contracts = [
                    contract
                    for contract in contracts["contracts"]
                    if contract["reader_family_id"] == family_id
                ]
                self.assertEqual("REQUIRED", entry["second_layout_policy"])
                self.assertGreaterEqual(entry["fresh_samples_required"], 1)
                self.assertEqual(
                    entry["task_contract_ids"],
                    sorted(
                        contract["task_contract_id"]
                        for contract in family_contracts
                    ),
                )
                self.assertEqual(
                    sorted(entry["expected_claims"]),
                    sorted(
                        role
                        for contract in family_contracts
                        for role in contract["required_roles"]
                    ),
                )

    def test_protected_closure_is_derived_from_each_family_metric_specs(self) -> None:
        """Reject an authorized family whose semantic authority is empty."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        contracts = load_table_task_contracts(repo_root=REPO_ROOT)
        closure = _protected_closure(
            repo_root=REPO_ROOT,
            matrix=matrix,
            task_contracts=contracts,
        )
        for family_id in contracts["authorized_family_ids"]:
            with self.subTest(family_id=family_id):
                actual_paths = set(
                    closure["families"][family_id]["semantic_files"]
                )
                expected_paths = {
                    metric["path"]
                    for contract in contracts["contracts"]
                    if contract["reader_family_id"] == family_id
                    for metric in contract["metric_specs"]
                }
                self.assertTrue(expected_paths)
                self.assertTrue(expected_paths.issubset(actual_paths))

    def test_shared_engine_drift_invalidates_every_table_family(self) -> None:
        """Propagate a Workflow/replay semantic mutation to every family."""
        closure = self._closure()
        current = copy.deepcopy(closure)
        current["shared_engine_files"]["scripts/vnext/workflow.py"] = {
            "sha256": "0" * 64,
            "size": 0,
        }
        drift = _protected_closure_drift(
            frozen=closure,
            current=current,
        )
        self.assertEqual(set(closure["families"]), set(drift))
        for family_id in drift:
            self.assertIn(
                "shared_engine:scripts/vnext/workflow.py",
                drift[family_id],
            )

    def test_shared_engine_closure_covers_formal_execution_and_replay(self) -> None:
        """Bind every module that turns a task plan into a frozen Run."""
        shared = self._closure()["shared_engine_files"]
        required = {
            "scripts/vnext/provider_runtime.py",
            "scripts/vnext/qualification.py",
            "scripts/vnext/run_store.py",
            "scripts/vnext/source_strategy.py",
            "scripts/vnext/specs.py",
            "scripts/vnext/workflow.py",
        }
        self.assertTrue(required.issubset(set(shared)))

    def test_family_fragment_drift_invalidates_only_its_owner(self) -> None:
        """Keep lodging and financial matrix/task changes dependency-scoped."""
        closure = self._closure()
        lodging = copy.deepcopy(closure)
        lodging["families"]["lodging_kpi_table"][
            "matrix_entry_hash"
        ] = "sha256:" + "1" * 64
        lodging_drift = _protected_closure_drift(
            frozen=closure,
            current=lodging,
        )
        self.assertEqual(["lodging_kpi_table"], sorted(lodging_drift))
        financial = copy.deepcopy(closure)
        financial["families"]["financial_statement"]["task_contracts"][
            "financial_liquidity_coverage_ratio_table_v1"
        ]["catalog_task_contract_hash"] = "sha256:" + "2" * 64
        financial_drift = _protected_closure_drift(
            frozen=closure,
            current=financial,
        )
        self.assertEqual(["financial_statement"], sorted(financial_drift))

    def test_unrelated_renderer_or_document_is_not_in_engine_closure(self) -> None:
        """Avoid invalidating qualification for non-executed report artifacts."""
        closure = self._closure()
        shared = closure["shared_engine_files"]
        self.assertNotIn("scripts/vnext/public_projection.py", shared)
        self.assertNotIn("REPORT_十公司财务指标.md", shared)

    def test_measurements_cover_all_local_development_tasks_and_split_costs(self) -> None:
        """Measure every authorized local source/task without a provider call."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        contracts = load_table_task_contracts(repo_root=REPO_ROOT)
        measurements = _measurement_receipts(
            repo_root=REPO_ROOT,
            matrix=matrix,
            task_contracts=contracts,
        )
        task_rows = measurements["qualification_task_measurements"]
        self.assertEqual(11, len(measurements["round_trip_receipts"]))
        self.assertEqual(len(contracts["contracts"]), len(task_rows))
        self.assertEqual(
            {contract["task_contract_id"] for contract in contracts["contracts"]},
            {row["task_contract_id"] for row in task_rows},
        )
        self.assertTrue(measurements["d07_decision_required"])
        self.assertEqual(
            "NOT_AVAILABLE_RESOURCE_LIMIT",
            measurements["family_maximum_estimated_input_tokens"][
                "financial_statement"
            ],
        )
        self.assertGreater(
            measurements["family_maximum_estimated_input_tokens"][
                "lodging_kpi_table"
            ],
            100000,
        )
        split_rows = _split_cost_receipts(
            task_contracts=contracts,
            task_measurements=task_rows,
        )
        self.assertEqual(len(contracts["contracts"]), len(split_rows))
        self.assertTrue(any(
            type(row["estimated_incremental_tokens"]) is int
            and row["estimated_incremental_tokens"] > 0
            for row in split_rows
        ))
        self.assertTrue(all(
            row["actual_incremental_tokens"] == "NOT_RUN"
            for row in split_rows
        ))

    @staticmethod
    def _closure() -> dict:
        """Build one fresh protected closure for mutation-isolation tests."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        contracts = load_table_task_contracts(repo_root=REPO_ROOT)
        return _protected_closure(
            repo_root=REPO_ROOT,
            matrix=matrix,
            task_contracts=contracts,
        )


if __name__ == "__main__":
    unittest.main()
