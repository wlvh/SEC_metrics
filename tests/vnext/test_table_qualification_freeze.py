"""Validate static PR-3 table qualification freeze inputs before receipt write."""

from __future__ import annotations

import copy
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from vnext import table_qualification_freeze as freeze_module
from vnext.canonical import content_hash
from vnext.requirements import load_requirement_snapshot
from vnext.table_qualification_freeze import _d07_authority
from vnext.table_qualification_freeze import _run_wb3_test_receipts
from vnext.table_qualification_freeze import _context_blocking_reason_codes
from vnext.table_qualification_freeze import _readiness_by_family
from vnext.table_qualification_freeze import _readiness_by_task_request
from vnext.table_qualification_freeze import _round_trip_input_closure
from vnext.table_qualification_freeze import build_table_qualification_freeze_receipt
from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_qualification_freeze import validate_table_qualification_freeze
from vnext.table_qualification_freeze import _protected_closure
from vnext.table_qualification_freeze import _protected_closure_drift
from vnext.table_qualification_freeze import _measurement_receipts
from vnext.table_qualification_freeze import _split_cost_receipts
from vnext.table_context_attestation import current_exact_request_binding
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
                self.assertEqual(
                    200000,
                    entry["token_context_limits"][
                        "max_estimated_input_tokens"
                    ],
                )
                self.assertEqual(
                    1000000,
                    entry["token_context_limits"]["maximum_context_tokens"],
                )

    def test_each_lodging_task_uses_schema_v3_attested_closure(self) -> None:
        """Do not reuse one schema-v3 protected hash for its sibling request."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        task_ids = matrix["entries"]["lodging_kpi_table"]["task_contract_ids"]
        self.assertEqual(2, len(task_ids))
        for task_id in task_ids:
            with self.subTest(task_contract_id=task_id):
                expected = current_exact_request_binding(
                    repo_root=REPO_ROOT,
                    task_contract_id=task_id,
                )
                actual = freeze_module._attested_request_authority(
                    repo_root=REPO_ROOT,
                    task_contract_id=task_id,
                )
                self.assertIsNotNone(actual)
                self.assertEqual(
                    expected["protected_closure_hash"],
                    actual["protected_closure_hash"],
                )

    def test_estimated_context_threshold_is_inclusive(self) -> None:
        """Pass 200000 exactly and block the first value above the D-07 cap."""
        common = {
            "max_estimated_input_tokens": 200000,
            "maximum_context_tokens": 1000000,
            "provider_envelope_bytes": 200000,
            "maximum_payload_bytes": 8388608,
        }
        self.assertEqual(
            [],
            _context_blocking_reason_codes(
                estimated_input_tokens=200000,
                **common,
            ),
        )
        self.assertEqual(
            ["ESTIMATED_CONTEXT_LIMIT"],
            _context_blocking_reason_codes(
                estimated_input_tokens=200001,
                **common,
            ),
        )

    def test_family_context_and_resource_blockers_are_independent(
        self,
    ) -> None:
        """Keep one ready family usable when the other family is blocked."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        lodging_ready = self._synthetic_measurements(
            lodging_reasons=[],
            financial_reasons=["EXPANDED_GRID_RESOURCE_LIMIT"],
        )
        first = _readiness_by_family(
            matrix=matrix,
            measurements=lodging_ready,
            drift_by_family={},
        )
        self.assertTrue(first["lodging_kpi_table"]["live_ready"])
        self.assertFalse(first["financial_statement"]["live_ready"])
        self.assertIn(
            "EXPANDED_GRID_RESOURCE_LIMIT",
            first["financial_statement"]["blocking_reason_codes"],
        )

        financial_ready = self._synthetic_measurements(
            lodging_reasons=["ESTIMATED_CONTEXT_LIMIT"],
            financial_reasons=[],
        )
        second = _readiness_by_family(
            matrix=matrix,
            measurements=financial_ready,
            drift_by_family={},
        )
        self.assertTrue(second["financial_statement"]["live_ready"])
        self.assertFalse(second["lodging_kpi_table"]["live_ready"])
        self.assertIn(
            "ESTIMATED_CONTEXT_LIMIT",
            second["lodging_kpi_table"]["blocking_reason_codes"],
        )

    def test_shared_dependency_drift_blocks_both_families(self) -> None:
        """Propagate shared engine drift to every dependent family."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        measurements = self._synthetic_measurements(
            lodging_reasons=[], financial_reasons=[],
        )
        shared = {
            family_id: ["shared_engine:scripts/vnext/table_payload.py"]
            for family_id in matrix["entries"]
        }
        readiness = _readiness_by_family(
            matrix=matrix,
            measurements=measurements,
            drift_by_family=shared,
        )
        self.assertTrue(all(
            not value["live_ready"] for value in readiness.values()
        ))
        self.assertTrue(all(
            value["protected_closure_gate"]["shared_dependency_drift"]
            for value in readiness.values()
        ))

    def test_family_local_drift_blocks_only_lodging(self) -> None:
        """Keep financial ready after lodging matrix/task/MetricSpec drift."""
        self._assert_only_local_family_blocked(family_id="lodging_kpi_table")

    def test_family_local_drift_blocks_only_financial(self) -> None:
        """Keep lodging ready after financial matrix/task/MetricSpec drift."""
        self._assert_only_local_family_blocked(family_id="financial_statement")

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

    def test_shared_round_trip_input_closure_is_exact_and_global(self) -> None:
        """Bind all eleven current sources and propagate one input drift."""
        closure = self._closure()
        inputs = closure["shared_measurement_inputs"]
        self.assertEqual(11, inputs["source_count"])
        self.assertEqual(
            list(range(11)),
            [row["order"] for row in inputs["sources"]],
        )
        self.assertEqual(
            inputs,
            _round_trip_input_closure(repo_root=REPO_ROOT),
        )
        current = copy.deepcopy(closure)
        current["shared_measurement_inputs"]["sources"][1][
            "actual_source_sha256"
        ] = "0" * 64
        drift = _protected_closure_drift(
            frozen=closure,
            current=current,
        )
        self.assertEqual(set(closure["families"]), set(drift))
        for labels in drift.values():
            self.assertIn(
                "shared_measurement:round_trip_source_set",
                labels,
            )

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
        self.assertTrue(measurements["any_measurement_blocked"])
        self.assertEqual(
            ["financial_statement", "lodging_kpi_table"],
            measurements["blocking_family_ids"],
        )
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
            200000,
        )
        readiness = _readiness_by_family(
            matrix=matrix,
            measurements=measurements,
            drift_by_family={},
        )
        self.assertEqual(
            395337,
            readiness["lodging_kpi_table"]["context_gate"][
                "maximum_observed_estimated_input_tokens"
            ],
        )
        self.assertEqual(
            [], readiness["lodging_kpi_table"]["blocking_reason_codes"],
        )
        task_readiness = _readiness_by_task_request(
            matrix=matrix,
            measurements=measurements,
            drift_by_family={},
        )
        occupancy = next(
            value for value in task_readiness.values()
            if value["task_contract_id"]
            == "lodging_occupancy_table_v2"
        )
        revpar = next(
            value for value in task_readiness.values()
            if value["task_contract_id"] == "lodging_revpar_table_v2"
        )
        self.assertTrue(occupancy["live_ready"])
        self.assertEqual(
            "EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE",
            occupancy["context_gate"]["evidence_basis"],
        )
        self.assertTrue(revpar["live_ready"])
        self.assertEqual(
            "EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE",
            revpar["context_gate"]["evidence_basis"],
        )
        self.assertEqual(
            ["EXPANDED_GRID_RESOURCE_LIMIT"],
            readiness["financial_statement"]["blocking_reason_codes"],
        )
        self.assertEqual(
            ["lodging_kpi_table"],
            sorted(
                family_id
                for family_id, value in readiness.items()
                if value["live_ready"]
            ),
        )
        d07 = _d07_authority(
            requirement=load_requirement_snapshot(
                snapshot_dir=REPO_ROOT / "requirements/issue_15_v1",
            ),
            matrix=matrix,
            measurements=measurements,
        )
        self.assertFalse(d07["d07_decision_required"])
        self.assertEqual(
            ["financial_statement", "lodging_kpi_table"],
            d07["blocking_family_ids"],
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

    def test_wb3_regression_receipt_ignores_runner_elapsed_time(self) -> None:
        """Keep semantically equal regression outcomes content-addressed alike."""
        first_outputs = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="Ran 1 test in 0.001s\n",
            )
            for _ in range(4)
        ]
        second_outputs = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="different harmless output\n",
                stderr="Ran 1 test in 9.999s\n",
            )
            for _ in range(4)
        ]
        with mock.patch(
            "vnext.table_qualification_freeze.subprocess.run",
            side_effect=first_outputs + second_outputs,
        ):
            first = _run_wb3_test_receipts(repo_root=REPO_ROOT)
            second = _run_wb3_test_receipts(repo_root=REPO_ROOT)
        self.assertEqual(2, first["schema_version"])
        self.assertEqual(
            first["wb3_regression_receipt_id"],
            second["wb3_regression_receipt_id"],
        )
        for row in first["tests"].values():
            self.assertEqual(
                {"test_id", "return_code", "test_source_sha256", "outcome"},
                set(row),
            )
            self.assertEqual("PASSED", row["outcome"])

    def test_full_freeze_receipt_rebuild_is_deterministic(self) -> None:
        """Rebuild the complete freeze twice from identical source and clock."""
        freeze_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
        first = build_table_qualification_freeze_receipt(
            repo_root=REPO_ROOT,
            freeze_commit=freeze_commit,
            frozen_at_utc="2026-08-21T09:00:00Z",
        )
        second = build_table_qualification_freeze_receipt(
            repo_root=REPO_ROOT,
            freeze_commit=freeze_commit,
            frozen_at_utc="2026-08-21T09:00:00Z",
        )
        self.assertEqual(
            first["table_qualification_freeze_receipt_id"],
            second["table_qualification_freeze_receipt_id"],
        )

    def test_validator_rejects_self_declared_family_readiness(self) -> None:
        """Rebuild family gates instead of trusting live-ready text."""
        original = freeze_module._json_object

        def tampered_json_object(**kwargs: object) -> dict:
            """Return a self-consistent but false family-ready receipt."""
            value = original(**kwargs)
            if kwargs["label"] == "table qualification freeze receipt":
                body = {
                    key: copy.deepcopy(item)
                    for key, item in value.items()
                    if key != "table_qualification_freeze_receipt_id"
                }
                body["readiness_by_family"]["lodging_kpi_table"][
                    "live_ready"
                ] = False
                body["live_ready_family_ids"] = []
                return {
                    "table_qualification_freeze_receipt_id": content_hash(
                        value=body,
                    ),
                    **body,
                }
            if kwargs["label"] == "table qualification freeze pointer":
                receipt = tampered_json_object(
                    repo_root=kwargs["repo_root"],
                    relative=Path(str(value["receipt_path"])),
                    label="table qualification freeze receipt",
                )
                return {
                    **value,
                    "receipt_id": receipt[
                        "table_qualification_freeze_receipt_id"
                    ],
                }
            return value

        with mock.patch(
            "vnext.table_qualification_freeze._json_object",
            side_effect=tampered_json_object,
        ), self.assertRaisesRegex(
            freeze_module.TableQualificationFreezeError,
            "Frozen family readiness differs",
        ):
            validate_table_qualification_freeze(repo_root=REPO_ROOT)

    @staticmethod
    def _synthetic_measurements(
        *, lodging_reasons: list[str], financial_reasons: list[str],
    ) -> dict:
        """Build minimal deterministic per-family rows for readiness tests."""
        rows = []
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        for family_id, reasons in (
            ("financial_statement", financial_reasons),
            ("lodging_kpi_table", lodging_reasons),
        ):
            if "EXPANDED_GRID_RESOURCE_LIMIT" in reasons:
                estimate: object = "NOT_AVAILABLE_RESOURCE_LIMIT"
            elif "ESTIMATED_CONTEXT_LIMIT" in reasons:
                estimate = 200001
            else:
                estimate = 200000
            context_status = (
                "NOT_EVALUATED_RESOURCE_LIMIT"
                if estimate == "NOT_AVAILABLE_RESOURCE_LIMIT"
                else "BLOCKED"
                if "ESTIMATED_CONTEXT_LIMIT" in reasons
                else "PASSED"
            )
            for task_contract_id in matrix["entries"][family_id][
                "task_contract_ids"
            ]:
                identity = content_hash(value={
                    "family_id": family_id,
                    "task_contract_id": task_contract_id,
                })
                rows.append({
                    "family_id": family_id,
                    "task_contract_id": task_contract_id,
                    "task_request_id": identity,
                    "source_sha256": "a" * 64,
                    "provider_request_body_sha256": (
                        "NOT_AVAILABLE_RESOURCE_LIMIT"
                        if estimate == "NOT_AVAILABLE_RESOURCE_LIMIT"
                        else "b" * 64
                    ),
                    "blocking_reason_codes": list(reasons),
                    "estimated_input_tokens": estimate,
                    "measurement_id": content_hash(value={
                        "task_request_id": identity,
                        "reasons": reasons,
                    }),
                    "context_feasibility": {
                        "status": context_status,
                        "evidence_basis": (
                            "ESTIMATED_BOUND"
                            if context_status == "PASSED" else None
                        ),
                        "attestation_id": None,
                        "attested_actual_prompt_tokens": None,
                        "context_budget_tokens": 200000,
                        "exact_binding_match": False,
                        "drift_fields": [],
                        "blocking_reason_code": (
                            "EXACT_CONTEXT_ATTESTATION_REQUIRED"
                            if context_status == "BLOCKED" else None
                        ),
                    },
                })
        return {"qualification_task_measurements": rows}

    def _assert_only_local_family_blocked(self, *, family_id: str) -> None:
        """Assert one local drift cannot invalidate the unrelated family."""
        matrix = load_table_qualification_matrix(repo_root=REPO_ROOT)
        measurements = self._synthetic_measurements(
            lodging_reasons=[], financial_reasons=[],
        )
        readiness = _readiness_by_family(
            matrix=matrix,
            measurements=measurements,
            drift_by_family={family_id: ["family_matrix_entry"]},
        )
        other = (
            "financial_statement"
            if family_id == "lodging_kpi_table"
            else "lodging_kpi_table"
        )
        self.assertFalse(readiness[family_id]["live_ready"])
        self.assertIn(
            "FAMILY_LOCAL_AUTHORITY_DRIFT",
            readiness[family_id]["blocking_reason_codes"],
        )
        self.assertTrue(readiness[other]["live_ready"])

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
