"""Provider-neutral AI attempt and recorded workflow contract tests."""

from __future__ import annotations

import json
import shutil
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import List, Optional
from unittest import mock

import vnext.ai_adapter as ai_adapter
from tests.vnext.common import REPO_ROOT, compiled_specs, fixed_clock
from tests.vnext.common import reader_response, sample_asset
from tests.vnext.common import sample_source_reference
from vnext.ai_adapter import AIAdapterError, build_approved_transport_adapter
from vnext.ai_adapter import build_recorded_adapter, run_ai_attempt
from vnext.canonical import canonical_json_bytes, sha256_bytes
from vnext.requirements import load_requirement_snapshot
from vnext.reader_input import build_reader_input_manifest
from vnext.reader_input import prepare_reader_request
from vnext.replay import replay_frozen_results
from vnext.run_store import freeze_run
from vnext.run_store import load_open_run
from vnext.run_store import write_validation_receipt
from vnext.sources import raw_blob_record
from vnext.table_grid import build_table_grid
from vnext.workflow import create_review_run


def reader_attempt_fixture() -> dict:
    """Build one complete prepared request and matching Reader response.

    Returns:
        Deterministic request/response pair using the repository disclosure
        Spec and full table-grid fixture.
    """
    asset = sample_asset()
    source = sample_source_reference(
        raw_asset_id=str(asset["parent_raw_asset_ids"][0])
    )
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=[str(source["source_reference_id"])],
    )
    return {
        "prepared_request": prepare_reader_request(
            manifest=manifest,
            derived_asset=asset,
            compiled_spec=compiled_specs()["DISCLOSURE"],
        ),
        "response_bytes": reader_response(asset=asset),
    }


def write_approved_d01_snapshot(
    *, repo_root: Path, maximum_payload_bytes: int = 10000
) -> Path:
    """Create one internally consistent Requirement copy with approved D-01.

    Args:
        repo_root: Empty temporary repository root.
        maximum_payload_bytes: Approved exact outbound request budget.

    Returns:
        Copied Requirement Snapshot directory with its updated baseline hash.
    """
    source = REPO_ROOT / "requirements" / "ai_first_v3_3_1"
    snapshot_dir = repo_root / "requirements" / "ai_first_v3_3_1"
    snapshot_dir.parent.mkdir(parents=True)
    shutil.copytree(source, snapshot_dir)
    register_path = snapshot_dir / "decision_register.json"
    register = json.loads(register_path.read_text(encoding="utf-8"))
    register["decisions"].append(
        {
            "decision_id": "D-01",
            "status": "APPROVED",
            "choice": {
                "provider": "approved-provider",
                "model": "approved-model",
                "endpoint_host": "api.approved.example",
                "region": "us",
                "retention": "zero",
                "data_use": "disabled",
                "timeout_seconds": 30,
                "retry_count": 0,
                "maximum_payload_bytes": maximum_payload_bytes,
                "filing_egress_policy": "approved",
            },
            "approved_by": "human:security-owner",
            "approved_at_utc": "2026-07-30T10:00:00Z",
            "supersedes_decision_id": None,
            "evidence": "test-approved-d01",
        }
    )
    register["pending_decisions"] = [
        pending
        for pending in register["pending_decisions"]
        if pending["decision_id"] != "D-01"
    ]
    register_bytes = canonical_json_bytes(value=register) + b"\n"
    register_path.write_bytes(register_bytes)

    # The loader intentionally binds Decision bytes through the baseline, so
    # an approved test snapshot must update that exact local authority too.
    baseline_path = snapshot_dir / "baseline_manifest.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["decision_register_sha256"] = sha256_bytes(
        content=register_bytes,
    )
    baseline_path.write_bytes(canonical_json_bytes(value=baseline) + b"\n")
    return snapshot_dir


class _FixtureApprovedTransport:
    """Model one repository-owned provider transport without network I/O."""

    def __init__(
        self,
        *,
        policy: object,
        calls: List[bytes],
        actual_endpoint_host: Optional[str] = None,
        failure_class: str = "",
    ) -> None:
        """Bind an exact policy and deterministic completion behavior.

        Args:
            policy: TransportPolicy compiled from effective D-01.
            calls: Mutable fixture ledger proving whether bytes crossed the
                adapter boundary.
            actual_endpoint_host: Optional observed host override used to
                model a repository transport implementation bug.
            failure_class: Optional underlying failure class to return.
        """
        self.policy = policy
        self._calls = calls
        self._actual_endpoint_host = actual_endpoint_host
        self._failure_class = failure_class

    def complete(self, *, request_bytes: bytes) -> object:
        """Return transport facts that can differ from the approved policy.

        Args:
            request_bytes: Exact outbound model payload.

        Returns:
            Deterministic TransportResult on success.

        Raises:
            TransportAttemptError: For a deterministic transport failure.
        """
        self._calls.append(request_bytes)
        endpoint_host = (
            self.policy.endpoint_host
            if self._actual_endpoint_host is None
            else self._actual_endpoint_host
        )
        observation = ai_adapter.TransportObservation(
            egress_attempted=True,
            provider=self.policy.provider,
            model=self.policy.model,
            endpoint_host=endpoint_host,
            region=self.policy.region,
            retention=self.policy.retention,
            data_use=self.policy.data_use,
            timeout_seconds=self.policy.timeout_seconds,
            retry_count=self.policy.retry_count,
            retries_performed=0,
            maximum_payload_bytes=self.policy.maximum_payload_bytes,
            filing_egress_policy=self.policy.filing_egress_policy,
            request_body_bytes=len(request_bytes),
        )
        if self._failure_class:
            raise ai_adapter.TransportAttemptError(
                "Fixture transport failed",
                observation=observation,
                provider_request_id="request:failed",
                raw_response_bytes=None,
                error_class=self._failure_class,
            )
        return ai_adapter.TransportResult(
            response_bytes=reader_attempt_fixture()["response_bytes"],
            provider_request_id="request:approved",
            observation=observation,
        )


class AiReaderContractTest(unittest.TestCase):
    """Prove remote fail-closed behavior and immutable recorded attempts."""

    def test_run_attempt_rejects_caller_adapter_before_complete(self) -> None:
        """Require factory authority and the repository implementation."""
        fixture = reader_attempt_fixture()
        calls: List[bytes] = []

        class CallerAdapter:
            """Return forged no-egress facts after observing request bytes."""

            def complete(self, *, request_bytes: bytes) -> object:
                """Model unauthorized egress hidden by recorded facts."""
                calls.append(request_bytes)
                return build_recorded_adapter(
                    response_bytes=fixture["response_bytes"],
                    fixture_id="fixture:forged-authority",
                ).complete(request_bytes=request_bytes)

        authorized = build_recorded_adapter(
            response_bytes=fixture["response_bytes"],
            fixture_id="fixture:authorized",
        )

        class CallerSubclass(type(authorized)):
            """Override a repository class without factory construction."""

            def complete(self, *, request_bytes: bytes) -> object:
                """Model a subclass attempting the same hidden egress."""
                return CallerAdapter().complete(request_bytes=request_bytes)

        unauthorized = (
            CallerAdapter(),
            object.__new__(CallerSubclass),
            object.__new__(type(authorized)),
        )
        for adapter in unauthorized:
            with self.subTest(adapter_type=type(adapter).__name__), (
                self.assertRaisesRegex(
                    AIAdapterError, "repository-constructed adapter"
                )
            ):
                run_ai_attempt(
                    adapter=adapter,
                    prepared_request=fixture["prepared_request"],
                    clock=fixed_clock,
                )
        self.assertEqual([], calls)

        # Exact class dispatch prevents an instance-level method replacement
        # from becoming a second hidden transport entry.
        authorized.complete = CallerAdapter().complete
        response, _raw, _attempt = run_ai_attempt(
            adapter=authorized,
            prepared_request=fixture["prepared_request"],
            clock=fixed_clock,
        )
        self.assertEqual(fixture["response_bytes"], response)
        self.assertEqual([], calls)

    def test_recorded_attempt_opens_no_socket_and_retries_are_distinct(
        self,
    ) -> None:
        """Keep response hashes stable and give retries new audit IDs."""
        fixture = reader_attempt_fixture()
        adapter = build_recorded_adapter(
            response_bytes=fixture["response_bytes"],
            fixture_id="fixture:reader:001",
        )

        with mock.patch.object(
            socket, "socket", side_effect=AssertionError("network forbidden"),
        ):
            first_response, first_raw, first = run_ai_attempt(
                adapter=adapter,
                prepared_request=fixture["prepared_request"],
                clock=fixed_clock,
            )
            second_response, second_raw, second = run_ai_attempt(
                adapter=adapter,
                prepared_request=fixture["prepared_request"],
                clock=fixed_clock,
            )
        self.assertEqual(first_response, second_response)
        self.assertEqual(first_raw, second_raw)
        self.assertNotEqual(first["attempt_id"], second["attempt_id"])
        self.assertEqual(
            first["raw_response_sha256"], second["raw_response_sha256"],
        )

    def test_schema_failure_preserves_raw_hash_without_fallback(self) -> None:
        """Record invalid model bytes and return no usable response."""
        fixture = reader_attempt_fixture()
        adapter = build_recorded_adapter(
            response_bytes=b'{"invalid":true}',
            fixture_id="fixture:reader:invalid",
        )

        response, raw_response, attempt = run_ai_attempt(
            adapter=adapter,
            prepared_request=fixture["prepared_request"],
            clock=fixed_clock,
        )
        self.assertIsNone(response)
        self.assertEqual(b'{"invalid":true}', raw_response)
        self.assertEqual("FAILED", attempt["status"])
        self.assertEqual("ReaderError", attempt["error_class"])
        self.assertTrue(attempt["raw_response_sha256"])

    def test_filtered_prepared_request_fails_before_transport(self) -> None:
        """Reject request bytes no longer carrying the manifest table set."""
        fixture = reader_attempt_fixture()
        prepared = fixture["prepared_request"]
        body = json.loads(prepared.request_bytes.decode("utf-8"))
        body["untrusted_table_data"] = []
        filtered = replace(
            prepared,
            request_bytes=canonical_json_bytes(value=body),
        )
        adapter = build_recorded_adapter(
            response_bytes=fixture["response_bytes"],
            fixture_id="fixture:reader:filtered",
        )

        with mock.patch.object(
            adapter, "complete", wraps=adapter.complete,
        ) as complete, self.assertRaisesRegex(
            AIAdapterError, "binding differs"
        ):
            run_ai_attempt(
                adapter=adapter,
                prepared_request=filtered,
                clock=fixed_clock,
            )
        complete.assert_not_called()

    def test_remote_adapter_binds_policy_owned_repository_transport(
        self,
    ) -> None:
        """Compile every D-01 field into a repository-selected transport."""
        calls: List[bytes] = []
        forged = {
            "decision_id": "D-01",
            "status": "APPROVED",
            "provider": "unapproved-provider",
            "model": "unapproved-model",
            "endpoint_host": "attacker.example",
            "region": "unknown",
            "retention": "unknown",
            "data_use": "unknown",
            "timeout_seconds": 30,
            "retry_count": 0,
            "maximum_payload_bytes": 1000,
            "filing_egress_policy": "unapproved",
        }

        # A caller cannot supply policy, root, or transport implementation.
        with self.assertRaises(TypeError):
            build_approved_transport_adapter(
                decision=forged,
            )
        with self.assertRaisesRegex(AIAdapterError, "approved D-01"):
            build_approved_transport_adapter()
        self.assertEqual([], calls)

        # Patching private module-owned authorities models a future committed
        # approval and provider registration without creating a caller API.
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            snapshot_dir = write_approved_d01_snapshot(
                repo_root=repo_root, maximum_payload_bytes=1024,
            )
            requirement = load_requirement_snapshot(
                snapshot_dir=snapshot_dir,
            )
            with self.assertRaises(TypeError):
                build_approved_transport_adapter(
                    repo_root=repo_root,
                )
            self.assertEqual([], calls)

            captured_policies = []

            def transport_factory(*, policy: object) -> object:
                """Capture the immutable policy passed by the adapter."""
                captured_policies.append(policy)
                return _FixtureApprovedTransport(
                    policy=policy, calls=calls,
                )

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": transport_factory},
                create=True,
            ):
                adapter = build_approved_transport_adapter()
                caller_transport_calls: List[bytes] = []
                adapter._transport = _FixtureApprovedTransport(
                    policy=adapter.policy,
                    calls=caller_transport_calls,
                )
                result = adapter.complete(
                    request_bytes=b"filing-bytes",
                )
        self.assertEqual([], caller_transport_calls)
        self.assertEqual([b"filing-bytes"], calls)
        self.assertEqual(
            reader_attempt_fixture()["response_bytes"],
            result.response_bytes,
        )
        self.assertEqual("request:approved", result.provider_request_id)
        self.assertEqual(1, len(captured_policies))
        self.assertEqual(
            {
                "provider": "approved-provider",
                "model": "approved-model",
                "endpoint_host": "api.approved.example",
                "region": "us",
                "retention": "zero",
                "data_use": "disabled",
                "timeout_seconds": 30,
                "retry_count": 0,
                "maximum_payload_bytes": 1024,
                "filing_egress_policy": "approved",
            },
            captured_policies[0].as_mapping(),
        )
        self.assertEqual(
            requirement["requirement_closure_hash"],
            adapter.requirement_closure_hash,
        )

    def test_remote_workflow_rejects_payload_root_outside_authority(
        self,
    ) -> None:
        """Reject a foreign workflow root before approved transport egress."""
        calls: List[bytes] = []
        relative = "tests/fixtures/vnext/sample_lodging.html"

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            authority_root = workspace / "authority"
            write_approved_d01_snapshot(repo_root=authority_root)

            def transport_factory(*, policy: object) -> object:
                """Return one observable repository-owned transport."""
                return _FixtureApprovedTransport(
                    policy=policy, calls=calls,
                )

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", authority_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": transport_factory},
                create=True,
            ):
                adapter = build_approved_transport_adapter()
                with self.assertRaisesRegex(
                    AIAdapterError, "repository authority"
                ):
                    create_review_run(
                        repo_root=REPO_ROOT,
                        run_dir=workspace / "run",
                        run_id="run:remote:foreign-root",
                        company_id="marriott_international",
                        target_period={
                            "fiscal_year": 2025,
                            "period_start": "2025-01-01",
                            "period_end": "2025-12-31",
                        },
                        source_repo_relative_path=relative,
                        source_media_type="text/html",
                        source_url=(
                            "https://www.sec.gov/Archives/sample.htm"
                        ),
                        accession="0001048286-25-000001",
                        document_name="sample_lodging.html",
                        source_role="target_primary",
                        request_attempt_id="request:attempt:fixture",
                        disclosure_spec_path=(
                            "catalog/disclosures/lodging_kpi_table.md"
                        ),
                        adapter=adapter,
                        clock=fixed_clock,
                    )
        self.assertEqual([], calls)

    def _assert_transport_policy_mismatch_blocks_before_payload(self) -> None:
        """Reject a provider transport not bound to exact approved policy."""
        calls: List[bytes] = []
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            write_approved_d01_snapshot(repo_root=repo_root)

            def mismatched_factory(*, policy: object) -> object:
                """Return a transport whose declared host is unapproved."""
                changed = ai_adapter.TransportPolicy(
                    **{
                        **policy.as_mapping(),
                        "endpoint_host": "attacker.example",
                    }
                )
                return _FixtureApprovedTransport(
                    policy=changed, calls=calls,
                )

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": mismatched_factory},
                create=True,
            ):
                with self.assertRaisesRegex(
                    AIAdapterError, "policy differs from D-01"
                ):
                    build_approved_transport_adapter().complete(
                        request_bytes=b"filing-bytes",
                    )
        self.assertEqual([], calls)

    def _assert_attempt_audits_actual_host_and_transport_failure(
        self,
    ) -> None:
        """Never copy an approved host over an observed destination."""
        cases = (
            ("attacker.example", "", "AIAdapterError"),
            (None, "TimeoutError", "TimeoutError"),
        )
        for actual_host, failure_class, expected_error in cases:
            with self.subTest(
                actual_host=actual_host, failure_class=failure_class,
            ):
                calls: List[bytes] = []
                with tempfile.TemporaryDirectory() as directory:
                    repo_root = Path(directory)
                    write_approved_d01_snapshot(repo_root=repo_root)

                    def transport_factory(*, policy: object) -> object:
                        """Create one observed success or failure fixture."""
                        return _FixtureApprovedTransport(
                            policy=policy,
                            calls=calls,
                            actual_endpoint_host=actual_host,
                            failure_class=failure_class,
                        )

                    with mock.patch(
                        "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
                    ), mock.patch.object(
                        ai_adapter,
                        "_TRANSPORT_FACTORIES",
                        {"approved-provider": transport_factory},
                        create=True,
                    ):
                        adapter = build_approved_transport_adapter()
                        prepared = reader_attempt_fixture()[
                            "prepared_request"
                        ]
                        response, raw, attempt = run_ai_attempt(
                            adapter=adapter,
                            prepared_request=prepared,
                            clock=fixed_clock,
                        )
                expected_host = (
                    "api.approved.example"
                    if actual_host is None
                    else actual_host
                )
                self.assertIsNone(response)
                if failure_class:
                    self.assertIsNone(raw)
                else:
                    self.assertEqual(
                        reader_attempt_fixture()["response_bytes"], raw,
                    )
                self.assertEqual("FAILED", attempt["status"])
                self.assertEqual(expected_error, attempt["error_class"])
                self.assertEqual(expected_host, attempt["endpoint_host"])
                self.assertEqual(
                    expected_host,
                    attempt["transport_observation"]["endpoint_host"],
                )
                self.assertTrue(
                    attempt["transport_observation"]["egress_attempted"]
                )
                self.assertEqual([prepared.request_bytes], calls)

    def _assert_unobserved_transport_failure_cannot_forge_audit(
        self,
    ) -> None:
        """Fail hard when a transport omits facts needed for audit."""
        calls: List[bytes] = []
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            write_approved_d01_snapshot(repo_root=repo_root)

            class UnobservedFailureTransport:
                """Model a broken repository transport contract."""

                def __init__(self, *, policy: object) -> None:
                    """Bind the exact policy but omit failure observations."""
                    self.policy = policy

                def complete(self, *, request_bytes: bytes) -> object:
                    """Raise a raw timeout after recording invocation."""
                    calls.append(request_bytes)
                    raise TimeoutError("fixture timeout without observation")

            def transport_factory(*, policy: object) -> object:
                """Create the deliberately non-conforming transport."""
                return UnobservedFailureTransport(policy=policy)

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": transport_factory},
                create=True,
            ):
                adapter = build_approved_transport_adapter()
                with self.assertRaisesRegex(
                    AIAdapterError, "without transport observation"
                ):
                    prepared = reader_attempt_fixture()["prepared_request"]
                    run_ai_attempt(
                        adapter=adapter,
                        prepared_request=prepared,
                        clock=fixed_clock,
                    )
        self.assertEqual([prepared.request_bytes], calls)

    def _assert_invalid_result_cannot_forge_transport_observation(
        self,
    ) -> None:
        """Do not invent approved-host facts for an unobserved result."""
        calls: List[bytes] = []
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            write_approved_d01_snapshot(repo_root=repo_root)

            class InvalidResultTransport:
                """Return legacy tuple bytes without actual transport facts."""

                def __init__(self, *, policy: object) -> None:
                    """Retain the exact policy required by construction."""
                    self.policy = policy

                def complete(self, *, request_bytes: bytes) -> object:
                    """Model an invoked transport that omits observation."""
                    calls.append(request_bytes)
                    return b'{"approved":true}', "request:legacy"

            def transport_factory(*, policy: object) -> object:
                """Create the deliberately incomplete transport result."""
                return InvalidResultTransport(policy=policy)

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": transport_factory},
                create=True,
            ):
                adapter = build_approved_transport_adapter()
                with self.assertRaisesRegex(
                    AIAdapterError, "without transport observation"
                ):
                    prepared = reader_attempt_fixture()["prepared_request"]
                    run_ai_attempt(
                        adapter=adapter,
                        prepared_request=prepared,
                        clock=fixed_clock,
                    )
        self.assertEqual([prepared.request_bytes], calls)

    def _assert_d01_is_revalidated_before_reused_adapter_egress(
        self,
    ) -> None:
        """Recheck current authority before every outbound request."""
        calls: List[bytes] = []
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            snapshot_dir = write_approved_d01_snapshot(repo_root=repo_root)

            def transport_factory(*, policy: object) -> object:
                """Return a transport whose call ledger must stay empty."""
                return _FixtureApprovedTransport(
                    policy=policy, calls=calls,
                )

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": transport_factory},
                create=True,
            ):
                adapter = build_approved_transport_adapter()

                # Replace both bound files with the repository's current
                # PENDING authority after construction but before egress.
                source = REPO_ROOT / "requirements" / "ai_first_v3_3_1"
                for name in (
                    "decision_register.json", "baseline_manifest.json",
                ):
                    shutil.copy2(source / name, snapshot_dir / name)
                with self.assertRaisesRegex(
                    AIAdapterError, "approved D-01"
                ):
                    adapter.complete(request_bytes=b"filing-bytes")
        self.assertEqual([], calls)

    def _assert_payload_budget_fails_before_egress_with_observed_fact(
        self,
    ) -> None:
        """Record that no egress occurred when D-01 payload policy blocks."""
        calls: List[bytes] = []
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            write_approved_d01_snapshot(
                repo_root=repo_root, maximum_payload_bytes=1024,
            )

            def transport_factory(*, policy: object) -> object:
                """Return a transport whose call ledger must stay empty."""
                return _FixtureApprovedTransport(
                    policy=policy, calls=calls,
                )

            with mock.patch(
                "vnext.ai_adapter._REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"approved-provider": transport_factory},
                create=True,
            ):
                adapter = build_approved_transport_adapter()
                prepared = reader_attempt_fixture()["prepared_request"]
                _response, _raw, attempt = run_ai_attempt(
                    adapter=adapter,
                    prepared_request=prepared,
                    clock=fixed_clock,
                )
        self.assertEqual([], calls)
        self.assertEqual("FAILED", attempt["status"])
        self.assertEqual("none", attempt["endpoint_host"])
        self.assertFalse(
            attempt["transport_observation"]["egress_attempted"]
        )

    def test_remote_transport_policy_enforcement_matrix(self) -> None:
        """Cover exact policy binding, no-egress budget, and actual audit."""
        self._assert_transport_policy_mismatch_blocks_before_payload()
        self._assert_attempt_audits_actual_host_and_transport_failure()
        self._assert_unobserved_transport_failure_cannot_forge_audit()
        self._assert_invalid_result_cannot_forge_transport_observation()
        self._assert_d01_is_revalidated_before_reused_adapter_egress()
        self._assert_payload_budget_fails_before_egress_with_observed_fact()

    def test_recorded_shadow_builds_pending_review_without_publication(
        self,
    ) -> None:
        """Wire a complete fixture through evidence to pending review."""
        relative = "tests/fixtures/vnext/sample_lodging.html"
        raw = raw_blob_record(
            repo_root=REPO_ROOT,
            repo_relative_path=relative,
            media_type="text/html",
        )
        asset = build_table_grid(
            html_bytes=(REPO_ROOT / relative).read_bytes(),
            parent_raw_asset_ids=[str(raw["raw_asset_id"])],
            storage_uri="artifacts/vnext/derived/fixture.json",
        )
        response = reader_response(asset=asset)
        active_path = REPO_ROOT / "outputs/active_publication.json"
        active_before = (
            active_path.read_bytes() if active_path.exists() else None
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            result = create_review_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                run_id="run:recorded:lodging:001",
                company_id="marriott_international",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_repo_relative_path=relative,
                source_media_type="text/html",
                source_url="https://www.sec.gov/Archives/sample.htm",
                accession="0001048286-25-000001",
                document_name="sample_lodging.html",
                source_role="target_primary",
                request_attempt_id="request:attempt:fixture",
                disclosure_spec_path=(
                    "catalog/disclosures/lodging_kpi_table.md"
                ),
                adapter=build_recorded_adapter(
                    response_bytes=response,
                    fixture_id="fixture:lodging:001",
                ),
                clock=fixed_clock,
            )
            self.assertEqual("PENDING_HUMAN_REVIEW", result["status"])
            manifest, records, _decisions = load_open_run(run_dir=run_dir)
            self.assertEqual(
                {
                    "catalog/disclosures/lodging_kpi_table.md",
                    "catalog/metrics/B10_occupancy.md",
                    "catalog/metrics/B11_revpar.md",
                },
                set(manifest["spec_file_hashes"]),
            )
            requirement = load_requirement_snapshot(
                snapshot_dir=(
                    REPO_ROOT / "requirements" / "ai_first_v3_3_1"
                )
            )
            self.assertEqual(
                requirement["hashes"], manifest["requirement_hashes"],
            )
            attempt = next(
                record
                for record in records
                if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
            )
            self.assertEqual(
                {"temperature": 0}, attempt["sampling_parameters"],
            )
            for path_field in (
                "request_body_path",
                "raw_response_path",
                "task_contract_path",
            ):
                with self.subTest(path_field=path_field):
                    path = run_dir / str(attempt[path_field])
                    self.assertTrue(path.is_file())
            active_after = (
                active_path.read_bytes() if active_path.exists() else None
            )
            self.assertEqual(active_before, active_after)

    def test_non_lodging_stops_before_source_or_ai(self) -> None:
        """Persist replayable structural results without source or AI I/O."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            result = create_review_run(
                repo_root=REPO_ROOT,
                run_dir=run_dir,
                run_id="run:recorded:nonlodging:001",
                company_id="pfizer",
                target_period={
                    "fiscal_year": 2025,
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
                source_repo_relative_path="missing-file-must-not-be-read.html",
                source_media_type="text/html",
                source_url="https://www.sec.gov/Archives/missing.htm",
                accession="0000000000-25-000001",
                document_name="missing.htm",
                source_role="target_primary",
                request_attempt_id="request:attempt:missing",
                disclosure_spec_path=(
                    "catalog/disclosures/lodging_kpi_table.md"
                ),
                adapter=build_recorded_adapter(
                    response_bytes=b"not consulted",
                    fixture_id="fixture:not-consulted",
                ),
                clock=fixed_clock,
            )
            self.assertEqual("N_A_STRUCTURAL", result["status"])
            self.assertEqual(0, result["attempt_count"])
            self.assertTrue(run_dir.is_dir())
            manifest, records, decisions = load_open_run(run_dir=run_dir)
            self.assertEqual("pfizer", manifest["company_id"])
            self.assertEqual([], decisions)
            self.assertEqual(
                {"B10", "B11"},
                {
                    record["metric_id"]
                    for record in records
                    if record["record_type"] == "METRIC_RESULT"
                },
            )
            self.assertEqual(
                {"N_A_STRUCTURAL"},
                {
                    record["applicability"]
                    for record in records
                    if record["record_type"] == "METRIC_RESULT"
                },
            )
            self.assertEqual(
                {"B10", "B11"},
                {
                    record["metric_id"]
                    for record in records
                    if record["record_type"] == "EXECUTION_TRACE"
                },
            )
            self.assertFalse(
                any(
                    record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                    for record in records
                )
            )
            write_validation_receipt(
                run_dir=run_dir,
                status="PASSED",
                checks=[{"check": "N_A_RECORD", "status": "PASS"}],
            )
            freeze_run(run_dir=run_dir, repo_root=REPO_ROOT)
            replay = replay_frozen_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            self.assertEqual(2, len(replay["results"]))


if __name__ == "__main__":
    unittest.main()
