"""Validate static PR-3 table qualification freeze inputs before receipt write."""

from __future__ import annotations

import unittest
from pathlib import Path

from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_qualification_freeze import _protected_closure
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
                actual_paths = set(closure["families"][family_id]["files"])
                expected_paths = {
                    metric["path"]
                    for contract in contracts["contracts"]
                    if contract["reader_family_id"] == family_id
                    for metric in contract["metric_specs"]
                }
                self.assertTrue(expected_paths)
                self.assertTrue(expected_paths.issubset(actual_paths))


if __name__ == "__main__":
    unittest.main()
