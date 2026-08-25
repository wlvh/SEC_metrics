"""Verify matrix-owned qualification phases and exact request identities."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext import ai_adapter
from vnext import qualification as qualification_module
from vnext.canonical import strict_json_file
from vnext.qualification import _qualification_sample_authority
from vnext.qualification import _qualification_sample_measurement
from vnext.qualification import QualificationError
from vnext.requirements import load_requirement_snapshot
from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_task_contracts import resolve_table_task_contract


class TableQualificationSamplesTest(unittest.TestCase):
    """Keep source selection phase-based, exact, and network-free at plan time."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load current authority and the last dual-attestation freeze body."""
        cls.requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_15_v1",
        )
        cls.entry = load_table_qualification_matrix(
            repo_root=REPO_ROOT, family_id="lodging_kpi_table",
        )["entries"]["lodging_kpi_table"]
        cls.freeze = strict_json_file(path=(
            REPO_ROOT
            / "artifacts/vnext/table_qualification_freeze/receipts"
            / "2c736dfb7de7ce1bff3bfe80a484abac47059337d8c8a92ac8a7fffdc3dc1c53.json"
        ))

    def _measurement(self, *, phase: str, task_id: str) -> dict:
        """Build one exact offline phase/task request."""
        sample = _qualification_sample_authority(
            repo_root=REPO_ROOT,
            matrix_entry=self.entry,
            qualification_phase=phase,
            qualification_ordinal=1,
        )
        task = resolve_table_task_contract(
            repo_root=REPO_ROOT,
            task_contract_id=task_id,
            family_id="lodging_kpi_table",
        )
        return _qualification_sample_measurement(
            repo_root=REPO_ROOT,
            family_id="lodging_kpi_table",
            task_contract=task,
            matrix_entry=self.entry,
            sample=sample,
            requirement=self.requirement,
            freeze=self.freeze,
        )

    def test_matrix_phases_resolve_exact_sources_and_requests(self) -> None:
        """Bind second, holdout, and fresh sources without caller locators."""
        expected = {
            ("SECOND_LAYOUT", "lodging_occupancy_table_v2"): (
                "hilton_worldwide_holdings", 153533,
                "f837a421292165735a6c1e8b7ef5f0379f51b9d9b5fcdf161a14b0391096800d",
                "PASSED",
            ),
            ("SECOND_LAYOUT", "lodging_revpar_table_v2"): (
                "hilton_worldwide_holdings", 153524,
                "4bb6dbd4d8f4ade8e6e00f493b46ab409f1498f7dcd4dc49173c68f440a55861",
                "PASSED",
            ),
            ("POST_FREEZE_HOLDOUT", "lodging_occupancy_table_v2"): (
                "hyatt_hotels", 204388,
                "3d62a7feed03e19b2c61185c603d014b8f3151788e97888ec3ae3234f8a32414",
                "BLOCKED",
            ),
            ("POST_FREEZE_HOLDOUT", "lodging_revpar_table_v2"): (
                "hyatt_hotels", 204379,
                "8c1ee9bea968a0ccbcb5c84e4da6ad960efcdf142e862a142e3c83fc8e16fa66",
                "BLOCKED",
            ),
            ("FRESH_STABILITY", "lodging_occupancy_table_v2"): (
                "marriott_international", 392447,
                "5ffa7b16d54ff9e3c2bdbc10d468f84b9aaae2ac029b5fc63e459d895eb8109a",
                "PASSED",
            ),
            ("FRESH_STABILITY", "lodging_revpar_table_v2"): (
                "marriott_international", 392438,
                "1dbe25dd3886bc7ab5e559c7f790bf40cc3471a3550553435450acfe92e72b0b",
                "PASSED",
            ),
        }
        with mock.patch.object(ai_adapter, "_open_provider_request") as opener:
            for (phase, task_id), values in expected.items():
                with self.subTest(phase=phase, task_contract_id=task_id):
                    sample = _qualification_sample_authority(
                        repo_root=REPO_ROOT,
                        matrix_entry=self.entry,
                        qualification_phase=phase,
                        qualification_ordinal=1,
                    )
                    measurement = self._measurement(
                        phase=phase, task_id=task_id,
                    )
                    company, tokens, request_hash, status = values
                    self.assertEqual(
                        company,
                        sample["source_binding"]["source_declaration"][
                            "company_id"
                        ],
                    )
                    self.assertEqual(tokens, measurement["estimated_input_tokens"])
                    self.assertEqual(
                        request_hash, measurement["provider_request_body_sha256"],
                    )
                    self.assertEqual(
                        status, measurement["context_feasibility"]["status"],
                    )
        opener.assert_not_called()

    def test_invalid_phase_ordinals_fail_before_source_or_provider(self) -> None:
        """Keep layout phases single-ordinal and fresh at the D-37 count."""
        for phase, ordinal in (
            ("SECOND_LAYOUT", 2),
            ("POST_FREEZE_HOLDOUT", 2),
            ("FRESH_STABILITY", 4),
            ("UNKNOWN", 1),
        ):
            with self.subTest(phase=phase, ordinal=ordinal):
                with self.assertRaises(QualificationError):
                    _qualification_sample_authority(
                        repo_root=REPO_ROOT,
                        matrix_entry=self.entry,
                        qualification_phase=phase,
                        qualification_ordinal=ordinal,
                    )

    def test_fresh_ordinal_two_requires_every_task_ordinal_one_frozen(
        self,
    ) -> None:
        """Fail before adapter construction when the global barrier is absent."""
        tasks = [
            "lodging_occupancy_table_v2",
            "lodging_revpar_table_v2",
        ]
        requirement = {
            "effective_decisions": {
                "D-07": {
                    "choice": {
                        "live_qualification_authorized": True,
                        "live_qualification_scope": {
                            "authorized_family_ids": ["lodging_kpi_table"],
                            "authorized_task_contract_ids": tasks,
                            "financial_qualification_authorized": False,
                        },
                    },
                },
            },
        }
        freeze = {"qualification_cycle_id": "sha256:" + "a" * 64}
        holdout = [{"task_contract_id": task_id} for task_id in tasks]
        with mock.patch.object(
            qualification_module,
            "load_requirement_snapshot",
            return_value=requirement,
        ), mock.patch.object(
            qualification_module,
            "require_table_qualification_freeze",
            return_value=freeze,
        ), mock.patch.object(
            qualification_module,
            "validate_table_production_semantic_freeze",
        ), mock.patch.object(
            qualification_module,
            "_table_phase_terminal_rows",
            side_effect=(holdout, []),
        ), mock.patch.object(
            qualification_module,
            "build_table_qualification_transport_adapter",
        ) as opener:
            with self.assertRaises(QualificationError) as raised:
                qualification_module.execute_table_qualification_task(
                    repo_root=REPO_ROOT,
                    family_id="lodging_kpi_table",
                    task_contract_id="lodging_occupancy_table_v2",
                    qualification_phase="FRESH_STABILITY",
                    qualification_ordinal=2,
                    target_period={},
                    owner_token="sequence-regression",
                )
        self.assertEqual(
            "TABLE_QUALIFICATION_PRIOR_ORDINAL_REQUIRED",
            raised.exception.code,
        )
        opener.assert_not_called()

    def test_prior_fresh_open_run_is_not_a_frozen_prerequisite(self) -> None:
        """Treat an existing but non-FROZEN prior Run as a sequence blocker."""
        cycle_id = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = (
                root / qualification_module.TABLE_QUALIFICATION_CYCLE_ROOT
                / cycle_id.split(":", maxsplit=1)[1] / "runs" / "open-run"
            )
            run_dir.mkdir(parents=True)
            manifest = {
                "status": "OPEN",
                "qualification_authorization": {
                    "family_id": "lodging_kpi_table",
                    "qualification_phase": "FRESH_STABILITY",
                    "qualification_ordinal": 1,
                },
            }
            with mock.patch.object(
                qualification_module,
                "load_run_for_status",
                return_value=(manifest, [], []),
            ):
                with self.assertRaises(QualificationError) as raised:
                    qualification_module._table_phase_terminal_rows(
                        repo_root=root,
                        qualification_cycle_id=cycle_id,
                        family_id="lodging_kpi_table",
                        qualification_phase="FRESH_STABILITY",
                        qualification_ordinals=(1,),
                    )
        self.assertEqual(
            "TABLE_QUALIFICATION_SEQUENCE_INVALID",
            raised.exception.code,
        )

    def test_production_freeze_binds_second_layout_and_ledger_prefix(self) -> None:
        """Require two FROZEN tasks and reject later semantic-tree drift."""
        cycle_id = "sha256:" + "a" * 64
        task_ids = [
            "lodging_occupancy_table_v2",
            "lodging_revpar_table_v2",
        ]
        rows = [
            {
                "task_contract_id": task_id,
                "qualification_phase": "SECOND_LAYOUT",
                "qualification_ordinal": 1,
                "qualification_terminal_id": "sha256:" + str(index) * 64,
                "qualification_task_plan_id": "sha256:" + str(index + 2) * 64,
                "provider_request_body_sha256": str(index + 4) * 64,
                "source_binding_hash": "sha256:" + str(index + 6) * 64,
                "run_id": "run:test:{}".format(index),
                "qualification_evidence_ids": [
                    "sha256:" + str(index + 7) * 64
                ],
                "result_ids": ["result:test:{}".format(index)],
            }
            for index, task_id in enumerate(task_ids)
        ]
        freeze = {
            "qualification_cycle_id": cycle_id,
            "receipt_id": "sha256:" + "b" * 64,
            "provider_ledger_before": {"path": "ledger.jsonl"},
        }
        requirement = {
            "effective_decisions": {
                "D-07": {
                    "choice": {
                        "live_qualification_scope": {
                            "authorized_task_contract_ids": task_ids,
                            "post_freeze_holdout_fixture_id": (
                                "hyatt-2025-sec-holdout-v2"
                            ),
                        }
                    }
                }
            }
        }
        tree = {
            "semantic_tree_id": "sha256:" + "c" * 64,
            "files": {"scripts/example.py": {"sha256": "d" * 64, "size": 1}},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ledger.jsonl").write_bytes(b"{}\n{}\n")
            with mock.patch.object(
                qualification_module,
                "require_table_qualification_freeze",
                return_value=freeze,
            ), mock.patch.object(
                qualification_module,
                "load_requirement_snapshot",
                return_value=requirement,
            ), mock.patch.object(
                qualification_module,
                "_table_phase_terminal_rows",
                return_value=rows,
            ), mock.patch.object(
                qualification_module,
                "production_semantic_tree",
                return_value=tree,
            ):
                receipt = qualification_module.write_table_production_semantic_freeze(
                    repo_root=root,
                    family_id="lodging_kpi_table",
                    frozen_at_utc="2026-08-25T13:00:00Z",
                )
                validated = (
                    qualification_module.validate_table_production_semantic_freeze(
                        repo_root=root,
                        family_id="lodging_kpi_table",
                    )
                )
                self.assertEqual(receipt["receipt_id"], validated["receipt_id"])
                self.assertEqual(2, validated[
                    "pre_holdout_qualification_ledger_prefix"
                ]["row_count"])
                with mock.patch.object(
                    qualification_module,
                    "production_semantic_tree",
                    return_value={**tree, "semantic_tree_id": "sha256:" + "e" * 64},
                ):
                    with self.assertRaises(QualificationError):
                        qualification_module.validate_table_production_semantic_freeze(
                            repo_root=root,
                            family_id="lodging_kpi_table",
                        )


if __name__ == "__main__":
    unittest.main()
