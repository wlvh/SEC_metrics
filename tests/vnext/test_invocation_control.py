"""Verify Issue #15 WB-3 invocation safety with injected mock transport."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from typing import List, Mapping, Optional

from vnext.canonical import content_hash
from vnext.cutover import _live_retry_policy, _normalized_invocation_error
from vnext.invocation_control import InvocationControlError
from vnext.invocation_control import EvidenceFailureError, SchemaViolationError
from vnext.invocation_control import UnknownRemoteOutcomeError
from vnext.invocation_control import build_ai_invocation_plan
from vnext.invocation_control import execute_batch, execute_invocation
from vnext.invocation_control import execution_identity
from vnext.invocation_control import recover_abandoned_before_egress
from vnext.invocation_control import structured_only_result


REQUEST_BODY = b'{"model":"test-model","input":"public filing"}'
UTC = "2026-08-19T12:00:00Z"


def identity(*, label: str) -> str:
    """Return one deterministic SHA-256 identity for tests."""
    return content_hash(value={"label": label})


def transport_result(
    *, status_code: int = 200, error_class: str = "",
    response_body: bytes = b'{"ok":true}', actual_cost: str = "0",
    paid_call: bool = False,
) -> dict:
    """Build one strict injected transport result."""
    return {
        "status_code": status_code,
        "error_class": error_class,
        "response_body": response_body,
        "provider_request_id": "mock-request-1",
        "paid_call": paid_call,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 2,
            "cache_hit_input_tokens": 3,
            "cache_miss_input_tokens": 7,
            "actual_cost": actual_cost,
        },
    }


def plan(
    *, maximum_payload_bytes: int = 1000,
    maximum_context_tokens: int = 1000,
    estimated_context_tokens: int = 10,
    estimated_cost: str = "0",
) -> dict:
    """Build one exact invocation plan with configurable resource limits."""
    return build_ai_invocation_plan(
        release_input_plan_id=identity(label="release"),
        source_identity_hash=identity(label="source"),
        selected_representation_hash=identity(label="representation"),
        task_contract_hash=identity(label="task"),
        output_schema_hash=identity(label="schema"),
        serialization_version="1",
        provider="mock-provider",
        model="test-model",
        api="mock-api",
        request_body=REQUEST_BODY,
        maximum_payload_bytes=maximum_payload_bytes,
        maximum_context_tokens=maximum_context_tokens,
        estimated_context_tokens=estimated_context_tokens,
        pricing_snapshot_hash=identity(label="pricing"),
        estimated_cost=estimated_cost,
    )


def execution(*, invocation_plan: Mapping[str, object], owner: str, at: str) -> str:
    """Return one explicit test execution identity."""
    return execution_identity(
        ai_invocation_plan_id=str(invocation_plan["ai_invocation_plan_id"]),
        owner_token=owner,
        authorized_at_utc=at,
    )


def clock() -> str:
    """Return one stable injected UTC audit time."""
    return UTC


def validate_response(*, response_body: bytes) -> None:
    """Accept the strict test response shape."""
    parsed = json.loads(response_body.decode("utf-8"))
    if parsed != {"ok": True}:
        raise AssertionError("unexpected test response")


def validate_evidence(*, response_body: bytes) -> None:
    """Accept evidence only after the response validator has decoded bytes."""
    if not response_body:
        raise AssertionError("empty test response")


def reject_schema(*, response_body: bytes) -> None:
    """Raise the effective terminal schema class for valid response bytes."""
    if response_body:
        raise SchemaViolationError("schema rejected")


def reject_evidence(*, response_body: bytes) -> None:
    """Raise the effective terminal evidence class after schema succeeds."""
    if response_body:
        raise EvidenceFailureError("evidence rejected")


class MockTransport:
    """Return queued results while exposing exact invocation count."""

    transport_kind = "MOCK"

    def __init__(
        self,
        *,
        results: List[object],
        entered: Optional[threading.Event] = None,
        release: Optional[threading.Event] = None,
    ) -> None:
        """Initialize a synchronized result queue."""
        self.results = list(results)
        self.entered = entered
        self.release = release
        self.invocation_count = 0
        self.lock = threading.Lock()

    def send(
        self, *, request_body: bytes, plan: Mapping[str, object],
        execution_id: str, attempt_ordinal: int,
    ) -> object:
        """Return or raise the next injected provider outcome."""
        if request_body != REQUEST_BODY or not execution_id or attempt_ordinal <= 0:
            raise AssertionError("mock transport input differs")
        if plan["provider_request_body_sha256"] == "":
            raise AssertionError("mock plan identity is empty")
        with self.lock:
            self.invocation_count += 1
            if not self.results:
                raise AssertionError("mock transport result queue is empty")
            outcome = self.results.pop(0)
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            self.release.wait(timeout=5)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class InvalidTransport:
    """Leave a reservation before egress by failing kind validation."""

    transport_kind = "INVALID"


class InvocationControlTest(unittest.TestCase):
    """Prove identity, single-flight, retry, stop, and audit invariants."""

    def test_plan_has_three_identities_and_no_monetary_caps(self) -> None:
        """Keep monetary observations non-blocking and cap fields absent."""
        invocation_plan = plan(estimated_cost="999999999999")
        self.assertTrue(invocation_plan["release_input_plan_id"].startswith("sha256:"))
        self.assertTrue(invocation_plan["ai_invocation_plan_id"].startswith("sha256:"))
        execution_id = execution(
            invocation_plan=invocation_plan, owner="owner-a", at=UTC,
        )
        self.assertTrue(execution_id.startswith("sha256:"))
        serialized = json.dumps(invocation_plan, sort_keys=True)
        for field in (
            "owner_absolute_total_cap",
            "owner_absolute_per_request_cap",
            "remaining_owner_cap",
            "maximum_authorized_cost",
            "per_call_monetary_cap",
            "batch_monetary_cap",
        ):
            self.assertNotIn(field, serialized)

    def test_cutover_runtime_uses_issue15_d35_retry_policy(self) -> None:
        """Bind the inherited orchestrator loop to D-35 maximum one retry."""
        policy = _live_retry_policy()
        self.assertEqual("D-35", policy["decision_id"])
        self.assertEqual(1, policy["retry_count"])
        self.assertEqual("TIMEOUT", _normalized_invocation_error(
            error_class="DEEPSEEK_TIMEOUT"
        ))
        self.assertEqual("HTTP_429", _normalized_invocation_error(
            error_class="DEEPSEEK_RATE_LIMIT"
        ))

    def test_concurrent_exact_request_has_one_mock_invocation(self) -> None:
        """Allow only the O_EXCL reservation owner to invoke transport."""
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan()
            entered = threading.Event()
            release = threading.Event()
            transport = MockTransport(
                results=[transport_result()], entered=entered, release=release,
            )
            outputs = []
            errors = []

            def run(*, owner: str, at: str) -> None:
                """Execute one concurrent contender and retain diagnostics."""
                try:
                    outputs.append(
                        execute_invocation(
                            workspace_dir=Path(directory),
                            plan=invocation_plan,
                            request_body=REQUEST_BODY,
                            execution_id=execution(
                                invocation_plan=invocation_plan,
                                owner=owner,
                                at=at,
                            ),
                            owner_token=owner,
                            authorized_at_utc=at,
                            clock=clock,
                            transport=transport,
                            response_validator=validate_response,
                            evidence_validator=validate_evidence,
                        )
                    )
                except BaseException as error:
                    errors.append(error)

            first = threading.Thread(
                target=run,
                kwargs={"owner": "owner-a", "at": "2026-08-19T12:00:00Z"},
            )
            first.start()
            self.assertTrue(entered.wait(timeout=5))
            second = threading.Thread(
                target=run,
                kwargs={"owner": "owner-b", "at": "2026-08-19T12:00:01Z"},
            )
            second.start()
            second.join(timeout=5)
            release.set()
            first.join(timeout=5)
        self.assertEqual([], errors)
        self.assertEqual(1, transport.invocation_count)
        self.assertEqual(
            {"SUCCEEDED", "SINGLE_FLIGHT_HELD"},
            {output["status"] for output in outputs},
        )
        counters = [output["counters"] for output in outputs]
        self.assertEqual(0, sum(row["real_model_provider_egress_count"] for row in counters))
        self.assertEqual(0, sum(row["paid_model_provider_call_count"] for row in counters))
        self.assertEqual(1, sum(row["mock_transport_invocation_count"] for row in counters))

    def test_http_402_calls_once_and_stops_batch(self) -> None:
        """Stop retries and later stability ordinals after one mock 402."""
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan()
            transport = MockTransport(results=[transport_result(status_code=402)])
            invocations = [
                {
                    "plan": invocation_plan,
                    "request_body": REQUEST_BODY,
                    "execution_id": execution(
                        invocation_plan=invocation_plan,
                        owner="owner-{}".format(ordinal),
                        at="2026-08-19T12:00:0{}Z".format(ordinal),
                    ),
                    "owner_token": "owner-{}".format(ordinal),
                    "authorized_at_utc": "2026-08-19T12:00:0{}Z".format(
                        ordinal
                    ),
                    "stability_ordinal": ordinal,
                }
                for ordinal in (1, 2, 3)
            ]
            result = execute_batch(
                workspace_dir=Path(directory),
                invocations=invocations,
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
        self.assertEqual("TERMINATED", result["status"])
        self.assertEqual([1], result["completed_stability_ordinals"])
        self.assertEqual([2, 3], result["skipped_stability_ordinals"])
        self.assertEqual(1, transport.invocation_count)
        receipt = result["execution_receipts"][0]
        self.assertEqual(1, len(receipt["attempts"]))
        self.assertEqual("HTTP_402", receipt["attempts"][0]["error_class"])

    def test_successful_exact_response_resume_has_zero_mock_invocation(self) -> None:
        """Reuse the exact persisted response before reservation or transport."""
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan()
            first_transport = MockTransport(results=[transport_result()])
            first = execute_invocation(
                workspace_dir=Path(directory),
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan,
                    owner="owner-a",
                    at="2026-08-19T12:00:00Z",
                ),
                owner_token="owner-a",
                authorized_at_utc="2026-08-19T12:00:00Z",
                clock=clock,
                transport=first_transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
            second_transport = MockTransport(results=[AssertionError("called")])
            resumed = execute_invocation(
                workspace_dir=Path(directory),
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan,
                    owner="owner-b",
                    at="2026-08-19T12:00:01Z",
                ),
                owner_token="owner-b",
                authorized_at_utc="2026-08-19T12:00:01Z",
                clock=clock,
                transport=second_transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
        self.assertEqual("SUCCEEDED", first["status"])
        self.assertEqual("REUSED_SUCCESS", resumed["status"])
        self.assertEqual(0, second_transport.invocation_count)
        self.assertEqual(0, resumed["counters"]["mock_transport_invocation_count"])

    def test_egress_crash_is_unknown_and_never_retried(self) -> None:
        """Persist UNKNOWN_REMOTE_OUTCOME with no terminal attempt receipt."""
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan()
            transport = MockTransport(
                results=[UnknownRemoteOutcomeError("crash after egress")]
            )
            execution_id = execution(
                invocation_plan=invocation_plan,
                owner="owner-a",
                at=UTC,
            )
            result = execute_invocation(
                workspace_dir=Path(directory),
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution_id,
                owner_token="owner-a",
                authorized_at_utc=UTC,
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
            resumed = execute_invocation(
                workspace_dir=Path(directory),
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution_id,
                owner_token="owner-a",
                authorized_at_utc=UTC,
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
        self.assertEqual("UNKNOWN_REMOTE_OUTCOME", result["status"])
        self.assertEqual([], result["attempts"])
        self.assertEqual(result, resumed)
        self.assertEqual(1, transport.invocation_count)

    def test_retryable_failure_retries_at_most_once(self) -> None:
        """Retain the first attempt and succeed on the only retry."""
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan()
            transport = MockTransport(
                results=[transport_result(status_code=429), transport_result()]
            )
            result = execute_invocation(
                workspace_dir=Path(directory),
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan, owner="owner-a", at=UTC,
                ),
                owner_token="owner-a",
                authorized_at_utc=UTC,
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
        self.assertEqual("SUCCEEDED", result["status"])
        self.assertEqual(
            ["FAILED_RETRYABLE", "SUCCEEDED"],
            [attempt["status"] for attempt in result["attempts"]],
        )
        self.assertEqual(2, transport.invocation_count)

    def test_terminal_http_schema_and_evidence_never_retry(self) -> None:
        """Stop 400/401/422/schema/evidence classes after one invocation."""
        cases = [
            ("HTTP_400", transport_result(status_code=400), validate_response, validate_evidence),
            ("HTTP_401", transport_result(status_code=401), validate_response, validate_evidence),
            ("HTTP_422", transport_result(status_code=422), validate_response, validate_evidence),
            ("SCHEMA_VIOLATION", transport_result(), reject_schema, validate_evidence),
            ("EVIDENCE_FAILURE", transport_result(), validate_response, reject_evidence),
        ]
        for ordinal, (
            error_class,
            outcome,
            response_validator,
            evidence_validator,
        ) in enumerate(cases, start=1):
            with self.subTest(error_class=error_class), tempfile.TemporaryDirectory() as directory:
                invocation_plan = plan()
                transport = MockTransport(results=[outcome])
                authorized_at = "2026-08-19T12:01:0{}Z".format(ordinal)
                result = execute_invocation(
                    workspace_dir=Path(directory),
                    plan=invocation_plan,
                    request_body=REQUEST_BODY,
                    execution_id=execution(
                        invocation_plan=invocation_plan,
                        owner="owner-terminal",
                        at=authorized_at,
                    ),
                    owner_token="owner-terminal",
                    authorized_at_utc=authorized_at,
                    clock=clock,
                    transport=transport,
                    response_validator=response_validator,
                    evidence_validator=evidence_validator,
                )
                self.assertEqual("FAILED_TERMINAL", result["status"])
                self.assertEqual(1, len(result["attempts"]))
                self.assertEqual(error_class, result["attempts"][0]["error_class"])
                self.assertEqual(1, transport.invocation_count)

    def test_cost_observability_never_blocks_but_resources_do(self) -> None:
        """Allow arbitrary cost observations and fail hard payload/context."""
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan(estimated_cost="999999999999")
            transport = MockTransport(
                results=[transport_result(actual_cost="999999999999")]
            )
            result = execute_invocation(
                workspace_dir=Path(directory),
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan, owner="owner-a", at=UTC,
                ),
                owner_token="owner-a",
                authorized_at_utc=UTC,
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
        self.assertEqual("SUCCEEDED", result["status"])
        self.assertEqual(
            "999999999999", result["attempts"][0]["usage"]["actual_cost"]
        )

        for label, invocation_plan in (
            (
                "PAYLOAD_LIMIT",
                plan(maximum_payload_bytes=len(REQUEST_BODY) - 1),
            ),
            (
                "CONTEXT_LIMIT",
                plan(maximum_context_tokens=9, estimated_context_tokens=10),
            ),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                transport = MockTransport(results=[transport_result()])
                with self.assertRaisesRegex(InvocationControlError, label):
                    execute_invocation(
                        workspace_dir=Path(directory),
                        plan=invocation_plan,
                        request_body=REQUEST_BODY,
                        execution_id=execution(
                            invocation_plan=invocation_plan,
                            owner="owner-resource",
                            at=UTC,
                        ),
                        owner_token="owner-resource",
                        authorized_at_utc=UTC,
                        clock=clock,
                        transport=transport,
                        response_validator=validate_response,
                        evidence_validator=validate_evidence,
                    )
                self.assertEqual(0, transport.invocation_count)

    def test_structured_only_and_abandoned_before_egress_are_zero_call(self) -> None:
        """Prove structured bypass and recover a pre-egress orphan."""
        structured = structured_only_result(
            release_input_plan_id=identity(label="release"),
            result_coordinate_count=220,
        )
        self.assertEqual(
            {
                "real_model_provider_egress_count": 0,
                "paid_model_provider_call_count": 0,
                "mock_transport_invocation_count": 0,
            },
            structured["counters"],
        )
        with tempfile.TemporaryDirectory() as directory:
            invocation_plan = plan()
            execution_id = execution(
                invocation_plan=invocation_plan, owner="owner-a", at=UTC,
            )
            with self.assertRaisesRegex(InvocationControlError, "Transport kind"):
                execute_invocation(
                    workspace_dir=Path(directory),
                    plan=invocation_plan,
                    request_body=REQUEST_BODY,
                    execution_id=execution_id,
                    owner_token="owner-a",
                    authorized_at_utc=UTC,
                    clock=clock,
                    transport=InvalidTransport(),
                    response_validator=validate_response,
                    evidence_validator=validate_evidence,
                )
            recovery = recover_abandoned_before_egress(
                workspace_dir=Path(directory),
                request_identity=str(invocation_plan["provider_request_identity"]),
                expected_execution_id=execution_id,
                recovered_at_utc="2026-08-19T12:00:01Z",
            )
        self.assertEqual("ABANDONED_BEFORE_EGRESS", recovery["status"])


if __name__ == "__main__":
    unittest.main()
