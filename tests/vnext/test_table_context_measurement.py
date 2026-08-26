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
from vnext.canonical import atomic_write_json, content_hash
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
            "1afd27317162e441fb0812253e79e287bbb302da0fb9ddf301c887541d06e43a"
        )
        cls.review_comment_url = (
            "https://github.com/wlvh/SEC_metrics/pull/22#issuecomment-1"
        )
        try:
            cls.authorization = issue_table_context_measurement_authorization(
                repo_root=REPO_ROOT,
                task_contract_id="lodging_revpar_table_v2",
                external_authorization_statement=EXTERNAL_AUTHORIZATION_STATEMENT,
                authorized_repository_head=cls.head,
                authorized_provider_request_body_sha256=cls.request_sha256,
                external_review_comment_url=cls.review_comment_url,
                authorized_at_utc="2026-08-25T00:00:00+00:00",
            )
        except TableContextMeasurementError as error:
            if error.code not in {
                "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
                "TABLE_CONTEXT_MEASUREMENT_REPOSITORY_NOT_CLEAN",
            }:
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
        """Bind the authorized scope-bound RevPAR plan and provider bytes."""
        plan = json.loads((
            REPO_ROOT
            / "artifacts/vnext/table_stage_c_evidence/token_measurement/"
            "plans/977a007d70d6f737012174de59ae6e9626709122fe1cdba6d712bb3f078fcd7f.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual("lodging_kpi_table", plan["family_id"])
        self.assertEqual(
            "lodging_revpar_table_v2", plan["task_contract_id"],
        )
        self.assertEqual(
            "c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547",
            plan["source_sha256"],
        )
        self.assertEqual("2", plan["table_payload_serialization_version"])
        self.assertEqual(394828, plan["estimated_input_tokens"])
        self.assertEqual(
            self.request_sha256, plan["provider_request_body_sha256"],
        )
        self.assertEqual(200000, plan[
            "ordinary_qualification_max_estimated_input_tokens"
        ])
        self.assertTrue(plan["ordinary_qualification_remains_blocked"])
        self.assertFalse(plan["qualification_evidence_eligible"])
        self.assertFalse(plan["response_reuse_for_qualification"])

    def test_revised_prompt_plans_are_task_exact_and_schema_unchanged(
        self,
    ) -> None:
        """Bind the two task-exact scope-bound schema-v3 plans."""
        plan_root = (
            REPO_ROOT
            / "artifacts/vnext/table_stage_c_evidence/token_measurement/plans"
        )
        occupancy = json.loads((
            plan_root
            / "26fdb6a2e6e0f33578c01c70d7bf86bd6dec642825edafc9908a6ff25dffa236.json"
        ).read_text(encoding="utf-8"))
        revpar = json.loads((
            plan_root
            / "977a007d70d6f737012174de59ae6e9626709122fe1cdba6d712bb3f078fcd7f.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(394837, occupancy["estimated_input_tokens"])
        self.assertEqual(394828, revpar["estimated_input_tokens"])
        self.assertEqual(self.request_sha256, revpar[
            "provider_request_body_sha256"
        ])
        self.assertNotEqual(
            occupancy["measurement_plan_id"], revpar["measurement_plan_id"],
        )
        self.assertEqual(
            occupancy["system_prompt_hash"], revpar["system_prompt_hash"],
        )
        self.assertEqual(
            occupancy["output_schema_hash"], revpar["output_schema_hash"],
        )
        self.assertEqual(
            "SCOPE_BINDING_PROMPT_REVISION_APPROVED_EXACT_GRANTS_PENDING",
            occupancy["revised_prompt_measurement_policy"]["policy_status"],
        )

    def test_plan_marker_consumes_grant_across_head_bindings(self) -> None:
        """Reject a later-head authorization after this exact plan egressed."""
        if self.authorization is None:
            self.skipTest("Exact-head authorization requires a clean checkout")
        binding = self.authorization.as_mapping()
        other_cycle = content_hash(value={
            "measurement_plan_id": binding["measurement_plan_id"],
            "authorized_repository_head": "f" * 40,
            "authorized_repository_tree": "e" * 40,
            "measurement_ordinal": 1,
        })
        marker_body = {
            "schema_version": 2,
            "record_type": "TABLE_CONTEXT_MEASUREMENT_EGRESS_MARKER",
            "measurement_plan_id": binding["measurement_plan_id"],
            "measurement_cycle_id": other_cycle,
            "authorization_id": "sha256:" + "a" * 64,
            "execution_id": "sha256:" + "b" * 64,
            "measurement_ordinal": 1,
            "family_id": binding["family_id"],
            "task_contract_id": binding["task_contract_id"],
            "authorized_repository_head": "f" * 40,
            "authorized_repository_tree": "e" * 40,
            "external_review_comment_url": self.review_comment_url,
            "provider_request_body_sha256": binding[
                "provider_request_body_sha256"
            ],
            "transport_kind": "MOCK",
            "egress_started_at_utc": "2026-08-25T00:00:01+00:00",
        }
        marker = {
            **marker_body, "egress_marker_id": content_hash(value=marker_body),
        }
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            atomic_write_json(
                path=(
                    workspace
                    / other_cycle.split(":", maxsplit=1)[1]
                    / "provider_egress_marker.json"
                ),
                value=marker,
            )
            transport = _MockMeasurementTransport(
                response=_usage_response(include_prompt=True),
            )
            with self.assertRaisesRegex(
                TableContextMeasurementError,
                "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
            ):
                self._execute(workspace=workspace, transport=transport)
            self.assertEqual(0, transport.send_calls)

    def test_revised_tasks_have_independent_one_shot_markers(self) -> None:
        """Allow one mock marker per exact task plan and reject each second use."""
        if self.authorization is None:
            self.skipTest("Exact-head authorization requires a clean checkout")
        occupancy_plan = build_table_context_measurement_plan(
            repo_root=REPO_ROOT,
            task_contract_id="lodging_occupancy_table_v2",
        )
        occupancy_authorization = issue_table_context_measurement_authorization(
            repo_root=REPO_ROOT,
            task_contract_id="lodging_occupancy_table_v2",
            external_authorization_statement=EXTERNAL_AUTHORIZATION_STATEMENT,
            authorized_repository_head=self.head,
            authorized_provider_request_body_sha256=occupancy_plan[
                "provider_request_body_sha256"
            ],
            external_review_comment_url=self.review_comment_url,
            authorized_at_utc="2026-08-25T00:00:01+00:00",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "dual-task"
            occupancy = self._execute(
                workspace=workspace,
                transport=_MockMeasurementTransport(response=_usage_response()),
                authorization=occupancy_authorization,
            )
            revpar = self._execute(
                workspace=workspace,
                transport=_MockMeasurementTransport(response=_usage_response()),
            )
            self.assertEqual("COMPLETED", occupancy["status"])
            self.assertEqual("COMPLETED", revpar["status"])
            self.assertNotEqual(
                occupancy["measurement_cycle_id"], revpar["measurement_cycle_id"],
            )
            for authorization in (
                occupancy_authorization,
                self.authorization,
            ):
                with self.assertRaisesRegex(
                    TableContextMeasurementError,
                    "TABLE_CONTEXT_MEASUREMENT_AUTHORIZATION_CONSUMED",
                ):
                    self._execute(
                        workspace=workspace,
                        transport=_MockMeasurementTransport(
                            response=_usage_response(),
                        ),
                        authorization=authorization,
                    )

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
                task_contract_id="lodging_revpar_table_v2",
                external_authorization_statement="NOT_AUTHORIZED",
                authorized_repository_head=self.head,
                authorized_provider_request_body_sha256=self.request_sha256,
                external_review_comment_url=self.review_comment_url,
                authorized_at_utc="2026-08-25T00:00:00+00:00",
            )


class TableContextMeasurementTerminalTest(unittest.TestCase):
    """Validate the consumed real terminal without reconstructing transport."""

    def test_revpar_terminal_is_consumed_exact_and_non_credit(self) -> None:
        """Bind revised plan, marker, usage, and permanent consumption."""
        root = (
            REPO_ROOT
            / "artifacts/vnext/table_stage_c_evidence/token_measurement"
        )
        plan = json.loads((
            root
            / "plans/468d6ee09f9538f0c3da3296ba0ae8b885254a3dafc40ed488d1116b75343563.json"
        ).read_text(encoding="utf-8"))
        cycle = (
            root
            / "executions/615b546ad79b8078cb4bb3b82e992eaf42125e90a16baccba180cab133b2e989"
        )
        marker = json.loads(
            (cycle / "provider_egress_marker.json").read_text(encoding="utf-8")
        )
        evidence = json.loads((
            cycle
            / "evidence/7679c5d712f4635b5b31ba2f4e6661085dc09a8498b9b40929f308a964dfaa42.json"
        ).read_text(encoding="utf-8"))
        validate_table_context_measurement_evidence(evidence=evidence)
        self.assertEqual(
            "sha256:468d6ee09f9538f0c3da3296ba0ae8b885254a3dafc40ed488d1116b75343563",
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
        self.assertEqual(161263, evidence["actual_prompt_tokens"])
        self.assertEqual(1051, evidence["actual_completion_tokens"])
        self.assertEqual(162314, evidence["actual_total_tokens"])
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
            build_table_context_measurement_plan(
                repo_root=REPO_ROOT,
                task_contract_id="lodging_revpar_table_v2",
            )


if __name__ == "__main__":
    unittest.main()
