"""Verify the Stage-C one-shot token measurement boundary with mocks only."""

from __future__ import annotations

import copy
import json
import multiprocessing
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Callable, Dict, Optional

from tests.vnext.common import REPO_ROOT
from vnext.invocation_control import UnknownRemoteOutcomeError
from vnext.qualification import QualificationError
from vnext.qualification import table_qualification_task_plan
from vnext.records import RecordError, validate_record
from vnext.table_context_measurement import _execute_with_transport
from vnext.table_context_measurement import build_table_context_measurement_plan
from vnext.table_context_measurement import EXTERNAL_AUTHORIZATION_STATEMENT
from vnext.table_context_measurement import issue_table_context_measurement_authorization
from vnext.table_context_measurement import TableContextMeasurementError
from vnext.table_context_measurement import validate_table_context_measurement_evidence
from vnext.table_qualification_freeze import _context_blocking_reason_codes
from vnext.table_qualification_freeze import ESTIMATED_CONTEXT_LIMIT


def _clock() -> Callable[[], str]:
    """Return a deterministic strictly ordered UTC text clock."""
    values = iter([
        "2026-08-25T00:00:01+00:00",
        "2026-08-25T00:00:02+00:00",
        "2026-08-25T00:00:03+00:00",
    ])
    return lambda: next(values)


class _MockMeasurementTransport:
    """Invoke one injected terminal only after the marker callback."""

    transport_kind = "MOCK"

    def __init__(
        self,
        *,
        response: bytes = b"",
        http_status: int = 200,
        error_class: str = "",
        terminal_status: str = "SUCCEEDED",
        unknown: bool = False,
        fail_before_egress: bool = False,
    ) -> None:
        self.response = response
        self.http_status = http_status
        self.error_class = error_class
        self.terminal_status = terminal_status
        self.unknown = unknown
        self.fail_before_egress = fail_before_egress
        self.send_calls = 0
        self.egress_calls = 0

    def send(
        self,
        *,
        request_body: bytes,
        authorization_id: str,
        execution_id: str,
        attempt_ordinal: int,
        before_egress: Callable[[], None],
    ) -> Dict[str, object]:
        """Return one exact raw provider envelope or simulated terminal."""
        self.send_calls += 1
        if self.fail_before_egress:
            raise ValueError("mock pre-egress failure")
        if not request_body or not authorization_id or not execution_id:
            raise ValueError("mock request identity absent")
        if attempt_ordinal != 1:
            raise ValueError("mock retry attempted")
        before_egress()
        self.egress_calls += 1
        if self.unknown:
            raise UnknownRemoteOutcomeError("mock unknown remote outcome")
        return {
            "http_status": self.http_status,
            "error_class": self.error_class,
            "provider_response_bytes": self.response,
            "provider_request_id": "mock-request-1",
            "transport_terminal_status": self.terminal_status,
        }


class _ConcurrentMockTransport:
    """Align two senders immediately before the one-shot marker callback."""

    transport_kind = "MOCK"

    def __init__(self, *, barrier: object, opener_reached: object) -> None:
        self.barrier = barrier
        self.opener_reached = opener_reached

    def send(
        self,
        *,
        request_body: bytes,
        authorization_id: str,
        execution_id: str,
        attempt_ordinal: int,
        before_egress: Callable[[], None],
    ) -> Dict[str, object]:
        """Reach the opener counter only after winning the marker claim."""
        if (
            not request_body
            or not authorization_id
            or not execution_id
            or attempt_ordinal != 1
        ):
            raise ValueError("concurrent mock request identity differs")
        self.barrier.wait(timeout=10)
        before_egress()
        with self.opener_reached.get_lock():
            self.opener_reached.value += 1
        return {
            "http_status": 200,
            "error_class": "",
            "provider_response_bytes": _usage_response(),
            "provider_request_id": "mock-concurrent-request",
            "transport_terminal_status": "SUCCEEDED",
        }


def _run_concurrent_sender(
    *, authorization: object, workspace: str, barrier: object,
    opener_reached: object, outcomes: object,
) -> None:
    """Execute one forked sender and return only its stable terminal code."""
    transport = _ConcurrentMockTransport(
        barrier=barrier, opener_reached=opener_reached,
    )
    try:
        result = _execute_with_transport(
            repo_root=REPO_ROOT,
            authorization=authorization,
            workspace_root=Path(workspace),
            transport=transport,
            clock=lambda: "2026-08-25T00:00:01+00:00",
        )
    except TableContextMeasurementError as error:
        outcomes.put(error.code)
    else:
        outcomes.put(str(result["status"]))


def _usage_response(*, include_prompt: bool = True) -> bytes:
    """Return a raw provider envelope with or without authoritative prompt usage."""
    usage: Dict[str, int] = {
        "completion_tokens": 17,
        "total_tokens": 123474,
        "prompt_cache_hit_tokens": 120000,
        "prompt_cache_miss_tokens": 3457,
    }
    if include_prompt:
        usage["prompt_tokens"] = 123457
    return json.dumps(
        {"id": "mock-response-1", "usage": usage},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class TableContextMeasurementTest(unittest.TestCase):
    """Prove one egress, permanent consumption, and zero qualification credit."""

    @classmethod
    def setUpClass(cls) -> None:
        """Issue a mock capability only while the historical grant is open."""
        cls.head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        cls.request_sha256 = (
            "1dbe25dd3886bc7ab5e559c7f790bf40cc3471a3550553435450acfe92e72b0b"
        )
        cls.review_comment_url = (
            "https://github.com/wlvh/SEC_metrics/pull/22#issuecomment-1"
        )
        try:
            cls.authorization = issue_table_context_measurement_authorization(
                repo_root=REPO_ROOT,
                external_authorization_statement=EXTERNAL_AUTHORIZATION_STATEMENT,
                authorized_repository_head=cls.head,
                authorized_provider_request_body_sha256=cls.request_sha256,
                external_review_comment_url=cls.review_comment_url,
                authorized_at_utc="2026-08-25T00:00:00+00:00",
            )
        except TableContextMeasurementError as error:
            if error.code != "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED":
                raise
            cls.authorization = None

    def _execute(
        self, *, workspace: Path, transport: _MockMeasurementTransport,
        authorization: Optional[object] = None,
    ) -> Dict[str, object]:
        """Run the private injected boundary against one isolated workspace."""
        return _execute_with_transport(
            repo_root=REPO_ROOT,
            authorization=(
                self.authorization if authorization is None else authorization
            ),
            workspace_root=workspace,
            transport=transport,
            clock=_clock(),
        )

    def test_plan_is_exact_revpar_request_without_ratio_substitution(self) -> None:
        """Bind current catalog task, source, serializer, and provider bytes."""
        if self.authorization is None:
            self.skipTest("The real one-shot authorization is permanently consumed")
        plan = build_table_context_measurement_plan(repo_root=REPO_ROOT)
        self.assertEqual("lodging_kpi_table", plan["family_id"])
        self.assertEqual(
            "lodging_revpar_table_v2", plan["task_contract_id"],
        )
        self.assertEqual(
            "c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547",
            plan["source_sha256"],
        )
        self.assertEqual("2", plan["table_payload_serialization_version"])
        self.assertEqual(392438, plan["estimated_input_tokens"])
        self.assertEqual(
            self.request_sha256, plan["provider_request_body_sha256"],
        )
        self.assertEqual(200000, plan[
            "ordinary_qualification_max_estimated_input_tokens"
        ])
        self.assertTrue(plan["ordinary_qualification_remains_blocked"])
        self.assertFalse(plan["qualification_evidence_eligible"])
        self.assertFalse(plan["response_reuse_for_qualification"])

    def test_mock_matrix_enforces_one_egress_and_no_downstream_credit(self) -> None:
        """Cover success, terminal failures, tamper, and ordinary 200k blocking."""
        if self.authorization is None:
            self.skipTest("Historical open-grant mock matrix is preserved in Git")
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "success"
            success_transport = _MockMeasurementTransport(
                response=_usage_response(),
            )
            success = self._execute(
                workspace=workspace, transport=success_transport,
            )
            self.assertEqual("COMPLETED", success["status"])
            self.assertEqual(1, success_transport.send_calls)
            self.assertEqual(1, success_transport.egress_calls)
            self.assertEqual(123457, success["actual_prompt_tokens"])
            self.assertEqual(17, success["actual_completion_tokens"])
            self.assertEqual(123474, success["actual_total_tokens"])
            self.assertEqual(120000, success["prompt_cache_hit_tokens"])
            self.assertEqual(3457, success["prompt_cache_miss_tokens"])
            self.assertEqual(0, success["real_model_provider_egress_count"])
            self.assertEqual(0, success["paid_model_provider_call_count"])
            self.assertEqual(0, success["real_SEC_egress_count"])
            self.assertEqual("lodging_kpi_table", success["family_id"])
            self.assertEqual(
                "lodging_revpar_table_v2", success["task_contract_id"],
            )
            self.assertEqual(self.head, success["authorized_repository_head"])
            self.assertEqual(
                self.review_comment_url,
                success["external_review_comment_url"],
            )
            second_success_transport = _MockMeasurementTransport(
                response=_usage_response(),
            )
            with self.assertRaisesRegex(
                TableContextMeasurementError,
                "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
            ):
                self._execute(
                    workspace=workspace,
                    transport=second_success_transport,
                )
            self.assertEqual(1, success_transport.send_calls)
            self.assertEqual(0, second_success_transport.send_calls)

            evidence = {
                key: value for key, value in success.items()
                if key != "measurement_evidence_path"
            }
            validate_table_context_measurement_evidence(evidence=evidence)
            with self.assertRaises(RecordError):
                validate_record(record=evidence)
            self.assertFalse(evidence["qualification_credit"])
            self.assertFalse(evidence["publication_eligible"])
            self.assertFalse(evidence["response_reuse_for_qualification"])

            http_402_transport = _MockMeasurementTransport(
                response=b'{"error":{"message":"balance"}}',
                http_status=402,
                error_class="HTTP_402",
                terminal_status="HTTP_402",
            )
            http_402_workspace = Path(temp_dir) / "http-402"
            failed_402 = self._execute(
                workspace=http_402_workspace,
                transport=http_402_transport,
            )
            self.assertEqual("FAILED_TRANSPORT", failed_402["status"])
            self.assertEqual(1, http_402_transport.send_calls)
            self.assertEqual(1, http_402_transport.egress_calls)
            self.assertFalse(failed_402["retry_performed"])
            after_402_transport = _MockMeasurementTransport(
                response=_usage_response(),
            )
            with self.assertRaisesRegex(
                TableContextMeasurementError,
                "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
            ):
                self._execute(
                    workspace=http_402_workspace,
                    transport=after_402_transport,
                )
            self.assertEqual(0, after_402_transport.send_calls)

            unknown_transport = _MockMeasurementTransport(unknown=True)
            unknown_workspace = Path(temp_dir) / "unknown"
            unknown = self._execute(
                workspace=unknown_workspace,
                transport=unknown_transport,
            )
            self.assertEqual("UNKNOWN_REMOTE_OUTCOME", unknown["status"])
            self.assertEqual(1, unknown_transport.send_calls)
            self.assertEqual(1, unknown_transport.egress_calls)
            self.assertFalse(unknown["retry_performed"])
            after_unknown_transport = _MockMeasurementTransport(
                response=_usage_response(),
            )
            with self.assertRaisesRegex(
                TableContextMeasurementError,
                "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
            ):
                self._execute(
                    workspace=unknown_workspace,
                    transport=after_unknown_transport,
                )
            self.assertEqual(0, after_unknown_transport.send_calls)

            missing_usage_transport = _MockMeasurementTransport(
                response=_usage_response(include_prompt=False),
            )
            missing_usage = self._execute(
                workspace=Path(temp_dir) / "missing-usage",
                transport=missing_usage_transport,
            )
            self.assertEqual(
                "FAILED_USAGE_UNAVAILABLE", missing_usage["status"],
            )
            self.assertIsNone(missing_usage["actual_prompt_tokens"])

            preflight_transport = _MockMeasurementTransport(
                fail_before_egress=True,
            )
            preflight_workspace = Path(temp_dir) / "preflight"
            with self.assertRaisesRegex(
                TableContextMeasurementError,
                "TABLE_CONTEXT_MEASUREMENT_PRE_EGRESS_FAILED",
            ):
                self._execute(
                    workspace=preflight_workspace,
                    transport=preflight_transport,
                )
            self.assertEqual(1, preflight_transport.send_calls)
            self.assertEqual(0, preflight_transport.egress_calls)
            explicit_rerun = _MockMeasurementTransport(
                response=_usage_response(),
            )
            self.assertEqual(
                "COMPLETED",
                self._execute(
                    workspace=preflight_workspace,
                    transport=explicit_rerun,
                )["status"],
            )

            tamper_values = {
                "family_id": "tampered-family",
                "task_contract_id": "tampered-task",
                "source_sha256": "0" * 64,
                "provider_request_body_sha256": "1" * 64,
                "system_prompt_hash": "sha256:" + "2" * 64,
                "output_schema_hash": "sha256:" + "3" * 64,
                "authorized_repository_head": "4" * 40,
            }
            for field, replacement in tamper_values.items():
                with self.subTest(field=field):
                    tampered = copy.copy(self.authorization)
                    binding = tampered.as_mapping()
                    binding[field] = replacement
                    object.__setattr__(tampered, "_binding", binding)
                    transport = _MockMeasurementTransport(
                        response=_usage_response(),
                    )
                    with self.assertRaises(TableContextMeasurementError):
                        self._execute(
                            workspace=Path(temp_dir) / ("tamper-" + field),
                            transport=transport,
                            authorization=tampered,
                        )
                    self.assertEqual(0, transport.send_calls)
                    self.assertEqual(0, transport.egress_calls)

            reasons = _context_blocking_reason_codes(
                estimated_input_tokens=392447,
                max_estimated_input_tokens=200000,
                maximum_context_tokens=1000000,
                provider_envelope_bytes=392447,
                maximum_payload_bytes=8388608,
            )
            self.assertEqual([ESTIMATED_CONTEXT_LIMIT], reasons)
            with self.assertRaises(QualificationError):
                table_qualification_task_plan(
                    repo_root=REPO_ROOT,
                    family_id="lodging_kpi_table",
                    task_contract_id="lodging_revpar_table_v2",
                    qualification_ordinal=1,
                )

            record_types = set()
            for path in Path(temp_dir).rglob("*.json"):
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict) and "record_type" in value:
                    record_types.add(value["record_type"])
            self.assertEqual(
                {
                    "TABLE_CONTEXT_MEASUREMENT_EGRESS_MARKER",
                    "TABLE_CONTEXT_MEASUREMENT_EVIDENCE",
                },
                record_types,
            )

            context = multiprocessing.get_context("fork")
            barrier = context.Barrier(2)
            opener_reached = context.Value("i", 0)
            outcomes = context.Queue()
            concurrent_workspace = Path(temp_dir) / "concurrent"
            processes = [
                context.Process(
                    target=_run_concurrent_sender,
                    kwargs={
                        "authorization": self.authorization,
                        "workspace": str(concurrent_workspace),
                        "barrier": barrier,
                        "opener_reached": opener_reached,
                        "outcomes": outcomes,
                    },
                )
                for _ in range(2)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=15)
            self.assertEqual([0, 0], [process.exitcode for process in processes])
            self.assertEqual(1, opener_reached.value)
            self.assertEqual(
                [
                    "COMPLETED",
                    "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
                ],
                sorted(outcomes.get(timeout=2) for _ in range(2)),
            )

    def test_external_authorization_must_bind_current_head(self) -> None:
        """Reject missing wording or any different repository HEAD."""
        if self.authorization is None:
            self.skipTest("The real one-shot authorization is permanently consumed")
        with self.assertRaisesRegex(
            TableContextMeasurementError,
            "TABLE_CONTEXT_MEASUREMENT_EXTERNAL_AUTHORIZATION_REQUIRED",
        ):
            issue_table_context_measurement_authorization(
                repo_root=REPO_ROOT,
                external_authorization_statement="NOT_AUTHORIZED",
                authorized_repository_head=self.head,
                authorized_provider_request_body_sha256=self.request_sha256,
                external_review_comment_url=self.review_comment_url,
                authorized_at_utc="2026-08-25T00:00:00+00:00",
            )


class TableContextMeasurementTerminalTest(unittest.TestCase):
    """Validate the consumed real terminal without reconstructing transport."""

    def test_revpar_terminal_is_consumed_exact_and_non_credit(self) -> None:
        """Bind plan, marker, raw usage, evidence, and permanent consumption."""
        root = (
            REPO_ROOT
            / "artifacts/vnext/table_stage_c_evidence/token_measurement"
        )
        plan = json.loads((
            root
            / "plans/cdb1b05b7f49417662fee4e8237ebe2f0fa3a99284f3f6930bd555532ff1c0ae.json"
        ).read_text(encoding="utf-8"))
        cycle = (
            root
            / "executions/c00fe1b4cdc0e812a9de47fe438dd5b99e3b6a2ce9f67597b1f7087bc2b0e325"
        )
        marker = json.loads(
            (cycle / "provider_egress_marker.json").read_text(encoding="utf-8")
        )
        evidence = json.loads((
            cycle
            / "evidence/9a3d6072a7ce640d510ad8a9451e075f8659c078715a5eaae97b2ef51ffff2cd.json"
        ).read_text(encoding="utf-8"))
        validate_table_context_measurement_evidence(evidence=evidence)
        self.assertEqual(
            "sha256:cdb1b05b7f49417662fee4e8237ebe2f0fa3a99284f3f6930bd555532ff1c0ae",
            plan["measurement_plan_id"],
        )
        self.assertEqual(
            plan["measurement_plan_id"], marker["measurement_plan_id"],
        )
        self.assertEqual(
            plan["provider_request_body_sha256"],
            evidence["provider_request_body_sha256"],
        )
        self.assertEqual("COMPLETED", evidence["status"])
        self.assertEqual(160928, evidence["actual_prompt_tokens"])
        self.assertEqual(535, evidence["actual_completion_tokens"])
        self.assertEqual(161463, evidence["actual_total_tokens"])
        self.assertEqual(1, evidence["real_model_provider_egress_count"])
        self.assertEqual(1, evidence["paid_model_provider_call_count"])
        self.assertEqual(0, evidence["real_SEC_egress_count"])
        self.assertFalse(evidence["qualification_credit"])
        self.assertFalse(evidence["publication_eligible"])
        self.assertFalse(evidence["response_reuse_for_qualification"])
        with self.assertRaisesRegex(
            TableContextMeasurementError,
            "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
        ):
            build_table_context_measurement_plan(repo_root=REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
