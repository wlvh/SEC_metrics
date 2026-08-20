"""Verify Issue #15 WB-3 invocation safety with injected mock transport."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import tempfile
import threading
import unittest
from pathlib import Path
from typing import List, Mapping, Optional
from unittest import mock

from tests.vnext.common import REPO_ROOT, SAMPLE_HTML, compiled_specs
from tests.vnext.common import reader_response
from tests.vnext.common import reviewed_fixture, sample_asset
from tests.vnext.common import sample_source_reference
from tests.vnext.test_ai_reader_contract import live_sec_reader_repository
import tools.vnext_operator as vnext_operator
from vnext import ai_adapter
from vnext.batch_workflow import request_attempt_binding
from vnext.canonical import content_hash, sha256_bytes
from vnext.cutover import _live_retry_policy, _normalized_invocation_error
from vnext.cutover import _prepare_review_run
from vnext.invocation_control import InvocationControlError
from vnext.invocation_control import EvidenceFailureError, SchemaViolationError
from vnext.invocation_control import UnknownRemoteOutcomeError
from vnext.invocation_control import build_ai_invocation_plan
from vnext.invocation_control import execute_batch, execute_invocation
from vnext.invocation_control import execution_identity
from vnext.invocation_control import recover_abandoned_before_egress
from vnext.invocation_control import structured_only_result
from vnext.reader_input import build_reader_input_manifest
from vnext.reader_input import prepare_reader_request


REQUEST_BODY = b'{"model":"test-model","input":"public filing"}'
UTC = "2026-08-19T12:00:00Z"
GENERIC_RESPONSE_BODY = reader_response(asset=sample_asset())
GENERIC_RESPONSE_SOURCE_BYTES = SAMPLE_HTML


def identity(*, label: str) -> str:
    """Return one deterministic SHA-256 identity for tests."""
    return content_hash(value={"label": label})


def transport_result(
    *, status_code: int = 200, error_class: str = "",
    response_body: bytes = GENERIC_RESPONSE_BODY, actual_cost: str = "0",
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
    fixture = reviewed_fixture(response_bytes=GENERIC_RESPONSE_BODY)
    return build_ai_invocation_plan(
        release_input_plan_id=identity(label="release"),
        source_identity_hash=str(
            fixture["manifest"]["reader_input_manifest_id"]
        ),
        selected_representation_hash=str(fixture["asset"]["derived_asset_id"]),
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
    if not isinstance(parsed, dict) or "candidates" not in parsed:
        raise AssertionError("unexpected test response")


def validate_evidence(*, response_body: bytes) -> dict:
    """Return a complete generic acceptance closure after decoded bytes."""
    if not response_body:
        raise AssertionError("empty test response")
    fixture = reviewed_fixture(response_bytes=response_body)
    candidate = fixture["candidate"]
    evidence = fixture["evidence"]
    return {
        "reader_input_manifest_id": fixture["manifest"][
            "reader_input_manifest_id"
        ],
        "derived_asset_id": fixture["asset"]["derived_asset_id"],
        "source_reference_ids": list(
            fixture["manifest"]["source_reference_ids"]
        ),
        "task_contract_hash": identity(label="task"),
        "spec_semantic_hash": compiled_specs()["DISCLOSURE"][
            "spec_semantic_hash"
        ],
        "candidate_hash": candidate["candidate_hash"],
        "candidate_record": candidate,
        "evidence_check_id": evidence["evidence_check_id"],
        "evidence_record": evidence,
        "evidence_candidate_hash": evidence["candidate_hash"],
        "evidence_status": evidence["status"],
        "validator_semantic_version": "test-acceptance-v1",
        "validator_semantic_hash": identity(label="validator"),
    }


def reject_schema(*, response_body: bytes) -> None:
    """Raise the effective terminal schema class for valid response bytes."""
    if response_body:
        raise SchemaViolationError("schema rejected")


def reject_evidence(*, response_body: bytes) -> None:
    """Raise the effective terminal evidence class after schema succeeds."""
    if response_body:
        raise EvidenceFailureError("evidence rejected")


def production_reader_fixture() -> dict:
    """Build exact Reader and full mechanical-acceptance test inputs."""
    asset = sample_asset()
    source = sample_source_reference(
        raw_asset_id=str(asset["parent_raw_asset_ids"][0])
    )
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=[str(source["source_reference_id"])],
    )
    compiled_spec = compiled_specs()["DISCLOSURE"]
    prepared_request = prepare_reader_request(
        manifest=manifest,
        derived_asset=asset,
        compiled_spec=compiled_spec,
    )
    return {
        "acceptance_context": (
            ai_adapter.build_invocation_acceptance_context(
                compiled_spec=compiled_spec,
                derived_asset=asset,
                reader_manifest=manifest,
                reader_payload_body=json.loads(
                    prepared_request.request_bytes.decode("utf-8")
                ),
                source_references=[source],
            )
        ),
        "asset": asset,
        "prepared_request": prepared_request,
    }


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


class ProcessCrashTransport:
    """Terminate the owner process only after the controller marks egress."""

    transport_kind = "MOCK"

    def send(
        self, *, request_body: bytes, plan: Mapping[str, object],
        execution_id: str, attempt_ordinal: int,
    ) -> object:
        """Exit without a terminal transport outcome or execution receipt."""
        if (
            request_body != REQUEST_BODY
            or not plan["provider_request_identity"]
            or not execution_id
            or attempt_ordinal != 1
        ):
            raise AssertionError("crash transport input differs")
        os._exit(73)


class ProductionReaderTransport:
    """Return injected Reader bytes through the repository transport API."""

    def __init__(
        self, *, policy: object, mutation: str, calls: List[bytes],
    ) -> None:
        """Bind exact policy, one response, and an observable call ledger."""
        self.policy = policy
        self.mutation = mutation
        self.calls = calls

    def complete(self, *, prepared_request: object) -> object:
        """Return the injected response after rebuilding live SEC authority."""
        rebuilt = ai_adapter._validate_live_prepared_request(
            prepared_request=prepared_request,
        )
        outbound, output_schema = ai_adapter.build_provider_request_body(
            policy=self.policy,
            reader_request_bytes=rebuilt.request_bytes,
        )
        self.calls.append(outbound)
        request = json.loads(rebuilt.request_bytes.decode("utf-8"))
        manifest = request["reader_input_manifest"]
        asset = {
            "derived_asset_id": manifest["derived_asset_id"],
            "tables": request["untrusted_table_data"],
        }
        response_body = reader_response(
            asset=asset,
            occupancy_raw=(
                "999.9" if self.mutation == "EVIDENCE_FAILURE" else "69.3%"
            ),
        )
        if self.mutation == "TASK_MISMATCH":
            parsed = json.loads(response_body.decode("utf-8"))
            parsed["disclosure_group"] = "other_disclosure_group"
            response_body = json.dumps(
                parsed, ensure_ascii=False
            ).encode("utf-8")
        elif self.mutation not in {"EVIDENCE_FAILURE", "PASS"}:
            raise AssertionError("Unknown injected Reader mutation")
        observation = ai_adapter.TransportObservation(
            egress_attempted=True,
            provider=self.policy.provider,
            model=self.policy.model,
            model_requested=self.policy.model,
            model_returned=self.policy.model,
            api=self.policy.api,
            store=False,
            endpoint_host=self.policy.endpoint_host,
            region=self.policy.region,
            retention=self.policy.retention,
            data_use=self.policy.data_use,
            timeout_seconds=self.policy.timeout_seconds,
            retry_count=self.policy.retry_count,
            retries_performed=0,
            maximum_payload_bytes=self.policy.maximum_payload_bytes,
            filing_egress_policy=self.policy.filing_egress_policy,
            request_body_bytes=len(outbound),
        )
        return ai_adapter.TransportResult(
            response_bytes=response_body,
            provider_request_id="request:injected-production-reader",
            observation=observation,
            raw_response_bytes=(
                b'{"usage":{"prompt_tokens":10,'
                b'"completion_tokens":2}}'
            ),
            outbound_request_bytes=outbound,
            output_schema_bytes=output_schema,
        )


def cutover_reader_plan_fixture(*, workspace: Path) -> dict:
    """Build one small immutable SEC source plan for production wiring."""
    workspace.mkdir(parents=True)
    fixture = live_sec_reader_repository(workspace=workspace)
    binding = request_attempt_binding(
        repo_root=fixture["repo_root"],
        source_url=str(fixture["source_url"]),
        content_sha256=sha256_bytes(content=GENERIC_RESPONSE_SOURCE_BYTES),
        accession=str(fixture["accession"]),
        document_name=str(fixture["document_name"]),
    )
    source = {
        "accession": fixture["accession"],
        "content_sha256": sha256_bytes(
            content=GENERIC_RESPONSE_SOURCE_BYTES
        ),
        "document_name": fixture["document_name"],
        "repo_relative_path": fixture["source_repo_relative_path"],
        "source_url": fixture["source_url"],
        **binding,
    }
    return {
        "company": {
            "company_id": "marriott_international",
            "target_period": {
                "fiscal_year": 2025,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
            "table_source": source,
        },
        "release_input_plan_id": identity(label="cutover-release-plan"),
        "repo_root": fixture["repo_root"],
    }


def operator_arguments(
    *, run_dir: Path, fixture: Mapping[str, object],
) -> object:
    """Build exact live operator arguments over an immutable source plan."""
    company = fixture["company"]
    source = company["table_source"]
    period = company["target_period"]
    return argparse.Namespace(
        accession=source["accession"],
        company_id=company["company_id"],
        disclosure_spec_path="catalog/disclosures/lodging_kpi_table.md",
        document_name=source["document_name"],
        execute_live=True,
        fiscal_year=period["fiscal_year"],
        fixture_id=None,
        period_end=period["period_end"],
        period_start=period["period_start"],
        recorded_response=None,
        request_attempt_id=source["request_attempt_id"],
        run_dir=str(run_dir),
        run_id="run:operator:controlled-evidence-resume",
        source_media_type="text/html",
        source_path=source["repo_relative_path"],
        source_role="target_primary",
        source_url=source["source_url"],
    )


def crash_after_egress(
    *, workspace_dir: Path, invocation_plan: Mapping[str, object],
    execution_id: str,
) -> None:
    """Run one child execution that dies inside provider send."""
    execute_invocation(
        workspace_dir=workspace_dir,
        plan=invocation_plan,
        request_body=REQUEST_BODY,
        execution_id=execution_id,
        owner_token="crash-owner",
        authorized_at_utc=UTC,
        clock=clock,
        transport=ProcessCrashTransport(),
        response_validator=validate_response,
        evidence_validator=validate_evidence,
    )


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

    def test_production_adapter_routes_repository_transport_through_wb3(
        self,
    ) -> None:
        """Put the socket-owning transport behind plan/reservation/reuse."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            adapter = ai_adapter.build_invocation_controlled_transport_adapter(
                release_input_plan_id=identity(label="production-release"),
                workspace_dir=workspace,
                owner_token="production-owner",
            )
            policy = adapter.policy
            fixture = production_reader_fixture()
            prepared_request = fixture["prepared_request"]
            outbound, output_schema = ai_adapter.build_provider_request_body(
                policy=policy,
                reader_request_bytes=prepared_request.request_bytes,
            )
            transport_result_value = ai_adapter.TransportResult(
                response_bytes=reader_response(asset=fixture["asset"]),
                provider_request_id="mock-production-request",
                observation=ai_adapter.TransportObservation(
                    egress_attempted=True,
                    provider=policy.provider,
                    model=policy.model,
                    model_requested=policy.model,
                    model_returned=policy.model,
                    api=policy.api,
                    store=False,
                    endpoint_host=policy.endpoint_host,
                    region=policy.region,
                    retention=policy.retention,
                    data_use=policy.data_use,
                    timeout_seconds=policy.timeout_seconds,
                    retry_count=1,
                    retries_performed=0,
                    maximum_payload_bytes=policy.maximum_payload_bytes,
                    filing_egress_policy=policy.filing_egress_policy,
                    request_body_bytes=len(outbound),
                ),
                raw_response_bytes=(
                    b'{"usage":{"prompt_tokens":2,'
                    b'"completion_tokens":1}}'
                ),
                outbound_request_bytes=outbound,
                output_schema_bytes=output_schema,
            )
            credential = ai_adapter.api_key_environment_name(policy=policy)
            with mock.patch.object(
                ai_adapter,
                "_validate_live_prepared_request",
                return_value=prepared_request,
            ), mock.patch.object(
                adapter,
                "_complete_repository_transport",
                return_value=transport_result_value,
            ) as repository_transport, mock.patch.dict(
                os.environ, {credential: "test-only-key"}, clear=False,
            ):
                first = adapter._complete_authorized(
                    prepared_request=prepared_request,
                    authorized_at_utc=UTC,
                    invocation_clock=clock,
                    acceptance_context=fixture["acceptance_context"],
                )
                second = adapter._complete_authorized(
                    prepared_request=prepared_request,
                    authorized_at_utc=UTC,
                    invocation_clock=clock,
                    acceptance_context=fixture["acceptance_context"],
                )
            state = workspace / "invocation_control"
            execution_receipt = json.loads(
                next((state / "executions").iterdir()).read_text(
                    encoding="utf-8"
                )
            )
            plan_count = len(list((state / "plans").iterdir()))
            reservation_count = len(list((state / "reservations").iterdir()))
        self.assertEqual(
            reader_response(asset=fixture["asset"]), first.response_bytes,
        )
        self.assertEqual(first.response_bytes, second.response_bytes)
        self.assertEqual(1, repository_transport.call_count)
        self.assertEqual(1, plan_count)
        self.assertEqual(0, reservation_count)
        self.assertEqual(
            1,
            execution_receipt["counters"][
                "real_model_provider_egress_count"
            ],
        )

    def test_cutover_evidence_failure_has_no_success_or_reuse(self) -> None:
        """Stop Cutover after one schema-valid mechanically false response."""
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Inject one Evidence-failing response without a real socket."""
            return ProductionReaderTransport(
                policy=policy,
                mutation="EVIDENCE_FAILURE",
                calls=calls,
            )

        with tempfile.TemporaryDirectory() as directory:
            fixture = cutover_reader_plan_fixture(
                workspace=Path(directory) / "fixture"
            )
            run_dir = Path(directory) / "runs" / "evidence-failure"
            with mock.patch.object(
                ai_adapter, "_REPOSITORY_ROOT", fixture["repo_root"],
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"deepseek": transport_factory},
            ), mock.patch.object(
                ai_adapter._InvocationControllerTransport,
                "transport_kind",
                "MOCK",
            ), mock.patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "injected-only"},
                clear=False,
            ):
                summary = _prepare_review_run(
                    repo_root=fixture["repo_root"],
                    run_dir=run_dir,
                    company=fixture["company"],
                    plan_id=str(fixture["release_input_plan_id"]),
                    stability_ordinal=1,
                    attempt_ordinal=1,
                    disclosure_spec_path=(
                        "catalog/disclosures/lodging_kpi_table.md"
                    ),
                    execute_live=True,
                    recorded_response_bytes=None,
                    recorded_fixture_id=None,
                )
            state = run_dir.parent / "invocation_control"
            executions = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (state / "executions").iterdir()
            ]
            success_receipts = list(
                (state / "responses").rglob("receipt.json")
            )
            acceptance_receipts = list(
                (state / "acceptances").rglob("receipt.json")
            )
            reservations = list((state / "reservations").iterdir())
        self.assertEqual("FAILED", summary["status"])
        self.assertEqual("EVIDENCE_FAILURE", summary["error_class"])
        self.assertEqual(1, len(calls))
        self.assertEqual(1, len(executions))
        self.assertEqual("FAILED_TERMINAL", executions[0]["status"])
        self.assertTrue(executions[0]["batch_terminal"])
        self.assertEqual("EVIDENCE_FAILURE", executions[0]["attempts"][0][
            "error_class"
        ])
        self.assertEqual(1, executions[0]["counters"][
            "mock_transport_invocation_count"
        ])
        self.assertEqual([], success_receipts)
        self.assertEqual([], acceptance_receipts)
        self.assertEqual([], reservations)

    def test_cutover_success_reuses_exact_accepted_response(self) -> None:
        """Reuse only the exact response whose real Evidence closure passed."""
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Inject one valid Reader response without a real socket."""
            return ProductionReaderTransport(
                policy=policy,
                mutation="PASS",
                calls=calls,
            )

        with tempfile.TemporaryDirectory() as directory:
            fixture = cutover_reader_plan_fixture(
                workspace=Path(directory) / "fixture"
            )
            runs = Path(directory) / "runs"
            with mock.patch.object(
                ai_adapter, "_REPOSITORY_ROOT", fixture["repo_root"],
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"deepseek": transport_factory},
            ), mock.patch.object(
                ai_adapter._InvocationControllerTransport,
                "transport_kind",
                "MOCK",
            ), mock.patch.object(
                vnext_operator, "REPO_ROOT", fixture["repo_root"],
            ), mock.patch.dict(
                os.environ,
                {
                    "DEEPSEEK_API_KEY": "injected-only",
                    "SEC_CONTACT_EMAIL": "sec-tests@wlvh.com",
                },
                clear=False,
            ):
                first = vnext_operator._prepare(
                    arguments=operator_arguments(
                        run_dir=runs / "accepted-first", fixture=fixture,
                    )
                )
                second = vnext_operator._prepare(
                    arguments=operator_arguments(
                        run_dir=runs / "accepted-resume", fixture=fixture,
                    )
                )
            state = runs / "invocation_control"
            executions = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (state / "executions").iterdir()
            ]
            success_receipt = json.loads(
                next((state / "responses").rglob("receipt.json")).read_text(
                    encoding="utf-8"
                )
            )
            acceptance_receipt = json.loads(
                next((state / "acceptances").rglob("receipt.json")).read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual("PENDING_HUMAN_REVIEW", first["status"])
        self.assertEqual("PENDING_HUMAN_REVIEW", second["status"])
        self.assertEqual(1, len(calls))
        self.assertEqual(
            {"REUSED_SUCCESS", "SUCCEEDED"},
            {receipt["status"] for receipt in executions},
        )
        self.assertEqual(
            acceptance_receipt["acceptance_receipt_id"],
            success_receipt["acceptance_receipt_id"],
        )
        self.assertEqual(first["candidate_hash"], second["candidate_hash"])
        self.assertEqual(
            first["evidence_check_id"], second["evidence_check_id"],
        )

    def test_cutover_task_mismatch_is_terminal_before_success(self) -> None:
        """Reject a schema-valid disclosure mismatch without retry or reuse."""
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Inject one task-mismatched response without a real socket."""
            return ProductionReaderTransport(
                policy=policy,
                mutation="TASK_MISMATCH",
                calls=calls,
            )

        with tempfile.TemporaryDirectory() as directory:
            fixture = cutover_reader_plan_fixture(
                workspace=Path(directory) / "fixture"
            )
            run_dir = Path(directory) / "runs" / "task-mismatch"
            with mock.patch.object(
                ai_adapter, "_REPOSITORY_ROOT", fixture["repo_root"],
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"deepseek": transport_factory},
            ), mock.patch.object(
                ai_adapter._InvocationControllerTransport,
                "transport_kind",
                "MOCK",
            ), mock.patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "injected-only"},
                clear=False,
            ):
                summary = _prepare_review_run(
                    repo_root=fixture["repo_root"],
                    run_dir=run_dir,
                    company=fixture["company"],
                    plan_id=str(fixture["release_input_plan_id"]),
                    stability_ordinal=1,
                    attempt_ordinal=1,
                    disclosure_spec_path=(
                        "catalog/disclosures/lodging_kpi_table.md"
                    ),
                    execute_live=True,
                    recorded_response_bytes=None,
                    recorded_fixture_id=None,
                )
            state = run_dir.parent / "invocation_control"
            execution_receipt = json.loads(
                next((state / "executions").iterdir()).read_text(
                    encoding="utf-8"
                )
            )
            success_receipts = list(
                (state / "responses").rglob("receipt.json")
            )
        self.assertEqual("FAILED", summary["status"])
        self.assertEqual("EVIDENCE_FAILURE", summary["error_class"])
        self.assertEqual(1, len(calls))
        self.assertEqual("FAILED_TERMINAL", execution_receipt["status"])
        self.assertEqual(1, len(execution_receipt["attempts"]))
        self.assertEqual([], success_receipts)

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
        self.assertEqual(
            0,
            sum(row["real_model_provider_egress_count"] for row in counters),
        )
        self.assertEqual(
            0,
            sum(row["paid_model_provider_call_count"] for row in counters),
        )
        self.assertEqual(
            1,
            sum(row["mock_transport_invocation_count"] for row in counters),
        )

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

    def test_http_402_releases_reservation_for_new_authorization(self) -> None:
        """Permit a later authorized execution after one terminal 402."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            invocation_plan = plan()
            transport = MockTransport(
                results=[transport_result(status_code=402), transport_result()]
            )
            first = execute_invocation(
                workspace_dir=workspace,
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan,
                    owner="owner-402-a",
                    at="2026-08-19T12:02:00Z",
                ),
                owner_token="owner-402-a",
                authorized_at_utc="2026-08-19T12:02:00Z",
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
            second = execute_invocation(
                workspace_dir=workspace,
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan,
                    owner="owner-402-b",
                    at="2026-08-19T12:02:01Z",
                ),
                owner_token="owner-402-b",
                authorized_at_utc="2026-08-19T12:02:01Z",
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
            reservations = list(
                (workspace / "invocation_control" / "reservations").iterdir()
            )
        self.assertEqual("FAILED_TERMINAL", first["status"])
        self.assertEqual("SUCCEEDED", second["status"])
        self.assertEqual(2, transport.invocation_count)
        self.assertEqual([], reservations)

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

    def test_reuse_revalidates_candidate_and_evidence_acceptance(self) -> None:
        """Reject a rehashed receipt whose persisted Candidate was changed."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            invocation_plan = plan()
            execute_invocation(
                workspace_dir=workspace,
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan,
                    owner="acceptance-owner-a",
                    at="2026-08-19T12:03:00Z",
                ),
                owner_token="acceptance-owner-a",
                authorized_at_utc="2026-08-19T12:03:00Z",
                clock=clock,
                transport=MockTransport(results=[transport_result()]),
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
            receipt_path = next(
                (workspace / "invocation_control" / "acceptances").rglob(
                    "receipt.json"
                )
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["candidate_record"]["selected"]["occupancy"][
                "claimed_raw_value"
            ] = "100"
            receipt_body = {
                field: receipt[field]
                for field in receipt
                if field != "acceptance_receipt_id"
            }
            receipt["acceptance_receipt_id"] = content_hash(
                value=receipt_body
            )
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False), encoding="utf-8"
            )
            unused = MockTransport(results=[AssertionError("called")])
            with self.assertRaises(InvocationControlError):
                execute_invocation(
                    workspace_dir=workspace,
                    plan=invocation_plan,
                    request_body=REQUEST_BODY,
                    execution_id=execution(
                        invocation_plan=invocation_plan,
                        owner="acceptance-owner-b",
                        at="2026-08-19T12:03:01Z",
                    ),
                    owner_token="acceptance-owner-b",
                    authorized_at_utc="2026-08-19T12:03:01Z",
                    clock=clock,
                    transport=unused,
                    response_validator=validate_response,
                    evidence_validator=validate_evidence,
                )
        self.assertEqual(0, unused.invocation_count)

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

    def test_process_death_after_egress_recovers_unknown_without_call(
        self,
    ) -> None:
        """Derive UNKNOWN_REMOTE_OUTCOME from a dead owner's disk state."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            invocation_plan = plan()
            execution_id = execution(
                invocation_plan=invocation_plan,
                owner="crash-owner",
                at=UTC,
            )
            process = multiprocessing.get_context("spawn").Process(
                target=crash_after_egress,
                kwargs={
                    "workspace_dir": workspace,
                    "invocation_plan": invocation_plan,
                    "execution_id": execution_id,
                },
            )
            process.start()
            process.join(timeout=10)
            self.assertEqual(73, process.exitcode)
            transport = MockTransport(results=[AssertionError("called")])
            recovered = execute_invocation(
                workspace_dir=workspace,
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution_id,
                owner_token="crash-owner",
                authorized_at_utc=UTC,
                clock=clock,
                transport=transport,
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
        self.assertEqual("UNKNOWN_REMOTE_OUTCOME", recovered["status"])
        self.assertEqual([], recovered["attempts"])
        self.assertEqual(0, transport.invocation_count)
        self.assertEqual(
            1, recovered["counters"]["mock_transport_invocation_count"]
        )

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
            (
                "HTTP_400", transport_result(status_code=400),
                validate_response, validate_evidence,
            ),
            (
                "HTTP_401", transport_result(status_code=401),
                validate_response, validate_evidence,
            ),
            (
                "HTTP_422", transport_result(status_code=422),
                validate_response, validate_evidence,
            ),
            (
                "SCHEMA_VIOLATION", transport_result(),
                reject_schema, validate_evidence,
            ),
            (
                "EVIDENCE_FAILURE", transport_result(),
                validate_response, reject_evidence,
            ),
        ]
        for ordinal, (
            error_class,
            outcome,
            response_validator,
            evidence_validator,
        ) in enumerate(cases, start=1):
            with self.subTest(
                error_class=error_class,
            ), tempfile.TemporaryDirectory() as directory:
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
        with tempfile.TemporaryDirectory() as observation_directory:
            structured = structured_only_result(
                repo_root=REPO_ROOT,
                workspace_dir=Path(observation_directory),
                release_input_plan_id=identity(label="release"),
                cumulative_metric_ids=("B01", "B03"),
                result_coordinate_count=20,
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

    def test_structured_only_proof_rejects_observed_invocation_state(
        self,
    ) -> None:
        """Never replace namespace-derived zero counts with a constant."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            invocation_plan = plan()
            execute_invocation(
                workspace_dir=workspace,
                plan=invocation_plan,
                request_body=REQUEST_BODY,
                execution_id=execution(
                    invocation_plan=invocation_plan,
                    owner="observed-owner",
                    at=UTC,
                ),
                owner_token="observed-owner",
                authorized_at_utc=UTC,
                clock=clock,
                transport=MockTransport(results=[transport_result()]),
                response_validator=validate_response,
                evidence_validator=validate_evidence,
            )
            with self.assertRaisesRegex(
                InvocationControlError, "emitted invocation state",
            ):
                structured_only_result(
                    repo_root=REPO_ROOT,
                    workspace_dir=workspace,
                    release_input_plan_id=identity(label="release"),
                    cumulative_metric_ids=("B01", "B03"),
                    result_coordinate_count=20,
                )


if __name__ == "__main__":
    unittest.main()
