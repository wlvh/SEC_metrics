"""Exercise WB-6 catalog-owned single-table task contract derivation."""

from __future__ import annotations

import unittest
from pathlib import Path

from vnext.table_task_contracts import load_table_task_contracts


REPO_ROOT = Path(__file__).resolve().parents[2]


class TableTaskContractsTest(unittest.TestCase):
    """Verify no table contract depends on a runtime metric/table selector."""

    def test_all_table_routes_are_single_role_catalog_contracts(self) -> None:
        """Derive the exact table-authorized family and metric sets offline."""
        catalog = load_table_task_contracts(repo_root=REPO_ROOT)
        self.assertEqual(
            ["financial_statement", "lodging_kpi_table"],
            catalog["authorized_family_ids"],
        )
        self.assertEqual(
            [
                "A03",
                "A04",
                "A09",
                "A11",
                "A12",
                "A13",
                "B06",
                "B10",
                "B11",
                "B13",
            ],
            catalog["table_metric_ids"],
        )
        for contract in catalog["contracts"]:
            with self.subTest(task_contract_id=contract["task_contract_id"]):
                self.assertEqual("table", contract["representation"])
                self.assertEqual(1, len(contract["required_roles"]))
                self.assertEqual("NOT_RUN", contract["actual_incremental_tokens"])
                self.assertTrue(contract["task_contract_hash"].startswith("sha256:"))
                self.assertTrue(contract["output_schema_hash"].startswith("sha256:"))
                self.assertTrue(contract["system_prompt_hash"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
