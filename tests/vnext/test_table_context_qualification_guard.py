"""Exercise qualification-only guards around exact context feasibility."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_invocation_control import GENERIC_RESPONSE_BODY
from tests.vnext.test_invocation_control import UTC, clock, execution, plan
from tests.vnext.test_invocation_control import validate_evidence
from tests.vnext.test_invocation_control import validate_response
from vnext import ai_adapter, qualification
from vnext.invocation_control import execute_batch
from vnext.requirements import load_requirement_snapshot
from vnext.table_context_attestation import (
    ATTESTATION_ROOT,
    TableContextAttestationError,
    validate_table_context_feasibility_attestation,
)
from vnext.table_qualification_freeze import _family_measurement_receipts
from vnext.table_qualification_freeze import _readiness_by_family
from vnext.table_qualification_freeze import _readiness_by_task_request
from vnext.table_qualification_freeze import load_table_qualification_matrix
from vnext.table_task_contracts import load_table_task_contracts


class _QualificationUsageTransport:
    """Inject one provider-like raw usage object without any socket action."""

    transport_kind = "MOCK"

    def __init__(self, *, raw_response: bytes, policy: dict) -> None:
        self.raw_response = raw_response
        self.policy = policy
        self.calls = 0

    def send(
        self, *, request_body: bytes, plan: dict,
        execution_id: str, attempt_ordinal: int,
    ) -> dict:
        """Map missing/excess usage to D-35's terminal CONTEXT_LIMIT."""
        self.calls += 1
        error = ai_adapter._qualification_usage_error(
            raw_response_bytes=self.raw_response,
            policy=self.policy,
        )
        return {
            "status_code": 0 if error else 200,
            "error_class": error,
            "response_body": GENERIC_RESPONSE_BODY,
            "provider_request_id": "qualification-usage-test",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_hit_input_tokens": 0,
                "cache_miss_input_tokens": 0,
                "actual_cost": "0",
            },
        }


class TableContextQualificationGuardTest(unittest.TestCase):
    """Prove context admission never becomes qualification permission."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build the two current lodging task/request measurements once."""
        cls.requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_15_v1",
        )
        cls.matrix = load_table_qualification_matrix(
            repo_root=REPO_ROOT,
            family_id="lodging_kpi_table",
        )
        cls.contracts = load_table_task_contracts(
            repo_root=REPO_ROOT,
            family_id="lodging_kpi_table",
        )
        cls.measurements = _family_measurement_receipts(
            repo_root=REPO_ROOT,
            family_id="lodging_kpi_table",
            matrix=cls.matrix,
            task_contracts=cls.contracts,
            requirement=cls.requirement,
        )

    def test_revised_requests_use_reviewed_qualification_usage_readiness(
        self,
    ) -> None:
        """Keep old attestations historical and admit only reviewed new calls."""
        tasks = _readiness_by_task_request(
            matrix=self.matrix,
            measurements=self.measurements,
            drift_by_family={},
        )
        family = _readiness_by_family(
            matrix=self.matrix,
            measurements=self.measurements,
            drift_by_family={},
        )["lodging_kpi_table"]
        occupancy = next(
            value for value in tasks.values()
            if value["task_contract_id"]
            == "lodging_occupancy_table_v2"
        )
        revpar = next(
            value for value in tasks.values()
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
        self.assertTrue(family["live_ready"])
        self.assertEqual(2, len(family["ready_task_request_ids"]))
        self.assertEqual(2, len(family["required_task_request_ids"]))

    def test_context_admission_never_opens_provider(self) -> None:
        """Keep context feasibility separate from provider execution."""
        measurement = {
            "context_feasibility": {
                "status": "PASSED",
                "evidence_basis": "PROVIDER_REPORTED_EXACT_BINDING",
            },
        }
        with mock.patch.object(ai_adapter, "_open_provider_request") as opener:
            context = qualification._qualification_context_plan(
                measurement=measurement,
                qualification_phase="FRESH_STABILITY",
                matrix_entry={},
                scope={},
            )
        self.assertEqual("PASSED", context["status"])
        opener.assert_not_called()

    def test_reviewed_usage_readiness_does_not_bypass_provider_limits(
        self,
    ) -> None:
        """Keep provider context/payload and materialization blockers hard."""
        measurements = copy.deepcopy(self.measurements)
        occupancy = next(
            row
            for row in measurements["qualification_task_measurements"]
            if row["task_contract_id"] == "lodging_occupancy_table_v2"
        )
        occupancy["context_feasibility"]["status"] = "BLOCKED"
        occupancy["context_feasibility"]["blocking_reason_code"] = (
            "PROVIDER_CONTEXT_LIMIT"
        )
        occupancy["blocking_reason_codes"] = ["PROVIDER_CONTEXT_LIMIT"]
        readiness = _readiness_by_task_request(
            matrix=self.matrix,
            measurements=measurements,
            drift_by_family={},
        )
        occupancy_readiness = next(
            row
            for row in readiness.values()
            if row["task_contract_id"] == "lodging_occupancy_table_v2"
        )
        self.assertFalse(occupancy_readiness["live_ready"])
        self.assertIn(
            "PROVIDER_CONTEXT_LIMIT",
            occupancy_readiness["blocking_reason_codes"],
        )

    def test_measurement_response_and_evidence_cannot_be_reused(self) -> None:
        """Reject generic success reuse and measurement evidence promotion."""
        accepted = self.requirement["effective_decisions"]["D-07"]["choice"][
            "accepted_context_attestations"
        ][0]
        attestation = json.loads(
            (
                REPO_ROOT
                / ATTESTATION_ROOT
                / (
                    accepted["attestation_id"].split(":", maxsplit=1)[1]
                    + ".json"
                )
            ).read_text(encoding="utf-8")
        )
        with self.assertRaises(TableContextAttestationError):
            validate_table_context_feasibility_attestation(
                repo_root=REPO_ROOT,
            )
        reused_attempt = {
            "record_type": "AI_EXTRACTION_ATTEMPT",
            "request_body_sha256": attestation[
                "exact_provider_request_body_sha256"
            ],
            "raw_response_sha256": attestation["raw_provider_response_id"].split(
                ":", maxsplit=1,
            )[1],
            "transport_observation": {"egress_attempted": False},
        }
        with self.assertRaises(qualification.QualificationError) as caught:
            qualification._require_new_qualification_execution(
                attempt=reused_attempt,
            )
        self.assertEqual(
            "TABLE_QUALIFICATION_RESPONSE_REUSE_FORBIDDEN",
            caught.exception.code,
        )
        measurement_evidence = json.loads(
            (REPO_ROOT / attestation["measurement_evidence_path"]).read_text(
                encoding="utf-8"
            )
        )
        with self.assertRaises(qualification.QualificationError):
            qualification._validate_table_qualification_evidence(
                evidence=measurement_evidence,
            )

    def test_missing_or_excess_usage_is_terminal_and_skips_ordinal_two(
        self,
    ) -> None:
        """Make usage failure terminal, retry-free, and batch-stopping."""
        policy = {
            "actual_prompt_tokens_max": 200000,
            "terminal_error_class": "CONTEXT_LIMIT",
        }
        responses = {
            "missing": b'{"id":"no-usage"}',
            "excess": (
                b'{"usage":{"prompt_tokens":200001,'
                b'"completion_tokens":1,"total_tokens":200002}}'
            ),
        }
        for label, raw_response in responses.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                invocation_plan = plan()
                invocations = []
                for ordinal in (1, 2):
                    owner = "qualification-owner-{}".format(ordinal)
                    invocations.append({
                        "authorized_at_utc": UTC,
                        "execution_id": execution(
                            invocation_plan=invocation_plan,
                            owner=owner,
                            at=UTC,
                        ),
                        "owner_token": owner,
                        "plan": invocation_plan,
                        "request_body": (
                            b'{"model":"test-model",'
                            b'"input":"public filing"}'
                        ),
                        "stability_ordinal": ordinal,
                    })
                transport = _QualificationUsageTransport(
                    raw_response=raw_response,
                    policy=policy,
                )
                result = execute_batch(
                    workspace_dir=Path(temp),
                    invocations=invocations,
                    clock=clock,
                    transport=transport,
                    response_validator=validate_response,
                    evidence_validator=validate_evidence,
                )
                self.assertEqual("TERMINATED", result["status"])
                self.assertEqual([1], result["completed_stability_ordinals"])
                self.assertEqual([2], result["skipped_stability_ordinals"])
                self.assertEqual(1, transport.calls)
                terminal = result["execution_receipts"][0]
                self.assertTrue(terminal["batch_terminal"])
                self.assertEqual("FAILED_TERMINAL", terminal["status"])
                self.assertEqual(1, len(terminal["attempts"]))
                self.assertEqual(
                    "CONTEXT_LIMIT",
                    terminal["attempts"][0]["error_class"],
                )

    def test_exact_reviewed_terminal_usage_path_covers_revised_phases(
        self,
    ) -> None:
        """Admit only the three no-measurement lodging sample phases."""
        scope = self.requirement["effective_decisions"]["D-07"]["choice"][
            "live_qualification_scope"
        ]
        measurement = {
            "context_feasibility": {
                "status": "BLOCKED",
                "evidence_basis": None,
            },
            "blocking_reason_codes": ["ESTIMATED_CONTEXT_LIMIT"],
        }
        matrix_entry = {
            "token_context_limits": {
                "max_estimated_input_tokens": 200000,
            }
        }
        for phase in (
            "SECOND_LAYOUT",
            "POST_FREEZE_HOLDOUT",
            "FRESH_STABILITY",
        ):
            with self.subTest(phase=phase):
                context = qualification._qualification_context_plan(
                    measurement=measurement,
                    qualification_phase=phase,
                    matrix_entry=matrix_entry,
                    scope=scope,
                )
                self.assertEqual("PASSED", context["status"])
                self.assertEqual(
                    "EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE",
                    context["evidence_basis"],
                )
        with self.assertRaises(qualification.QualificationError):
            qualification._qualification_context_plan(
                measurement=measurement,
                qualification_phase="PRODUCTION_SEMANTIC_FREEZE",
                matrix_entry=matrix_entry,
                scope=scope,
            )


if __name__ == "__main__":
    unittest.main()
