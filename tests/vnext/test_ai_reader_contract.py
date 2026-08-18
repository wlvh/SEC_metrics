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
from sec_http import REQUEST_LOG_FIELDNAMES, request_log_attempt_id
from tests.vnext.common import REPO_ROOT, compiled_specs, fixed_clock
from tests.vnext.common import SAMPLE_HTML
from tests.vnext.common import reader_response, sample_asset
from tests.vnext.common import sample_source_reference
from tests.vnext.test_publication import write_request_ledger_rows
from vnext.ai_adapter import AIAdapterError, build_approved_transport_adapter
from vnext.ai_adapter import build_recorded_adapter, run_ai_attempt
from vnext.canonical import canonical_json_bytes, sha256_bytes
from vnext.requirements import load_requirement_snapshot
from vnext.reader_input import build_reader_input_manifest
from vnext.reader_input import prepare_live_reader_request
from vnext.reader_input import prepare_reader_request
from vnext.replay import replay_frozen_results
from vnext.run_store import load_open_run
from vnext.run_store import validate_and_freeze_run
from vnext.sources import raw_blob_record, source_reference_record
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


def run_remote_transport_unit_attempt(
    *, adapter: object, prepared_request: object
) -> tuple:
    """Exercise remote transport mechanics below the live source gate.

    Args:
        adapter: Repository-built remote adapter under test.
        prepared_request: Deterministic Reader payload for transport assertions.

    Returns:
        Exact ``run_ai_attempt`` result tuple.

    Why:
        These unit cases mutate D-01/provider behavior. One separate workflow
        case exercises the real immutable SEC source replay end to end.
    """
    with mock.patch.object(
        ai_adapter,
        "_validate_live_prepared_request",
        return_value=prepared_request,
    ) as validator:
        result = run_ai_attempt(
            adapter=adapter,
            prepared_request=prepared_request,
            clock=fixed_clock,
        )
    expected = mock.call(prepared_request=prepared_request)
    if (
        validator.call_count not in {2, 3}
        or any(call != expected for call in validator.call_args_list)
    ):
        raise AssertionError(
            "Every remote layer must replay the same live authority"
        )
    return result


def complete_remote_transport_unit(
    *, adapter: object, request_bytes: bytes
) -> object:
    """Invoke the private transport implementation for policy unit tests.

    Args:
        adapter: Exact repository remote adapter implementation.
        request_bytes: Transport-unit payload bytes.

    Returns:
        Exact transport result below the public no-egress method.
    """
    prepared_request = replace(
        reader_attempt_fixture()["prepared_request"],
        request_bytes=request_bytes,
    )
    with mock.patch.object(
        ai_adapter,
        "_validate_live_prepared_request",
        return_value=prepared_request,
    ):
        return adapter._complete_authorized(
            prepared_request=prepared_request,
        )


def live_sec_reader_repository(*, workspace: Path) -> dict:
    """Create one exact immutable SEC filing authority for a live mock.

    Args:
        workspace: Empty test directory receiving the scoped repository.

    Returns:
        Repository and exact source coordinates accepted by the live verifier.
    """
    repo_root = workspace / "repo"
    repo_root.mkdir()
    for relative in ("catalog", "config", "requirements"):
        shutil.copytree(REPO_ROOT / relative, repo_root / relative)
    source_url = (
        "https://www.sec.gov/Archives/edgar/data/1048286/"
        "000104828625000001/sample.htm"
    )
    accession = "0001048286-25-000001"
    document_name = "sample.htm"
    digest = sha256_bytes(content=SAMPLE_HTML)
    body_relative = Path(
        "evidence", "request_attempts", digest[:2], digest, document_name,
    )
    body_path = repo_root / body_relative
    body_path.parent.mkdir(parents=True)
    body_path.write_bytes(SAMPLE_HTML)
    headers_bytes = canonical_json_bytes(
        value={
            "url": source_url,
            "status_code": 200,
            "headers": {"Content-Type": "text/html"},
            "content_length": len(SAMPLE_HTML),
            "sha256": digest,
            "saved_at_utc": "2026-07-29T12:59:59+00:00",
        }
    ) + b"\n"
    headers_relative = body_relative.with_name(
        "{}.{}.headers.json".format(
            document_name, sha256_bytes(content=headers_bytes),
        )
    )
    (repo_root / headers_relative).write_bytes(headers_bytes)
    row = {
        "timestamp_utc": "2026-07-29T13:00:00+00:00",
        "method": "GET",
        "source_url": source_url,
        "status_code": "200",
        "purpose": "live_reader_authority_fixture",
        "repo_relative_path": body_relative.as_posix(),
        "headers_repo_relative_path": headers_relative.as_posix(),
        "content_length": str(len(SAMPLE_HTML)),
        "content_sha256": digest,
        "accession": accession,
        "document_name": document_name,
        "user_agent": "SEC metrics fixture fixture@example.com",
        "retry_attempt": "0",
        "error": "",
    }
    if set(row) != set(REQUEST_LOG_FIELDNAMES):
        raise AssertionError("Live SEC ledger fixture fields differ")
    write_request_ledger_rows(repo_root=repo_root, rows=[row])
    return {
        "repo_root": repo_root,
        "source_repo_relative_path": body_relative.as_posix(),
        "source_url": source_url,
        "accession": accession,
        "document_name": document_name,
        "request_attempt_id": request_log_attempt_id(
            row_index=0, row=row,
        ),
    }


def live_prepared_fixture(
    *, fixture: dict, table_html_bytes: Optional[bytes] = None
) -> object:
    """Build one factory live wrapper, optionally with substituted grid bytes.

    Args:
        fixture: Exact result of :func:`live_sec_reader_repository`.
        table_html_bytes: Optional adversarial bytes used only for DerivedAsset.

    Returns:
        Factory-produced live request coordinates for boundary tests.
    """
    repo_root = fixture["repo_root"]
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=str(fixture["source_repo_relative_path"]),
        media_type="text/html",
    )
    source = source_reference_record(
        raw_blob=raw,
        company_id="marriott_international",
        source_url=str(fixture["source_url"]),
        accession=str(fixture["accession"]),
        document_name=str(fixture["document_name"]),
        source_role="target_primary",
        request_attempt_id=str(fixture["request_attempt_id"]),
    )
    source_bytes = (
        (repo_root / str(fixture["source_repo_relative_path"])).read_bytes()
        if table_html_bytes is None
        else table_html_bytes
    )
    asset = build_table_grid(
        html_bytes=source_bytes,
        parent_raw_asset_ids=[str(raw["raw_asset_id"])],
        storage_uri=(
            "artifacts/vnext/derived/{}.json".format(
                str(raw["raw_asset_id"]).split(":", maxsplit=1)[1]
            )
        ),
    )
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=[str(source["source_reference_id"])],
    )
    ordinary = prepare_reader_request(
        manifest=manifest,
        derived_asset=asset,
        compiled_spec=compiled_specs()["DISCLOSURE"],
    )
    return prepare_live_reader_request(
        prepared_request=ordinary,
        raw_blob=raw,
        source_reference=source,
        derived_asset=asset,
        reader_manifest=manifest,
        disclosure_spec_path="catalog/disclosures/lodging_kpi_table.md",
        immutable_source_repo_relative_path=str(
            fixture["source_repo_relative_path"]
        ),
    )


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
    approved = next(
        decision
        for decision in register["decisions"]
        if decision["decision_id"] == "D-01"
    )
    approved["choice"] = {
        "provider": "approved-provider",
        "model": "approved-model",
        "api": "responses",
        "endpoint_host": "api.approved.example",
        "region": "us",
        "retention": "zero",
        "data_use": "disabled",
        "timeout_seconds": 30,
        "retry_count": 0,
        "maximum_payload_bytes": maximum_payload_bytes,
        "filing_egress_policy": "approved",
    }
    approved["approved_by"] = "human:security-owner"
    approved["approved_at_utc"] = "2026-07-30T10:00:00Z"
    approved["evidence"] = "test-approved-d01"
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

    def complete(self, *, prepared_request: object) -> object:
        """Return transport facts that can differ from the approved policy.

        Args:
            prepared_request: Live request replayed at the transport boundary.

        Returns:
            Deterministic TransportResult on success.

        Raises:
            TransportAttemptError: For a deterministic transport failure.
        """
        rebuilt = ai_adapter._validate_live_prepared_request(
            prepared_request=prepared_request,
        )
        request_bytes = rebuilt.request_bytes
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
            model_requested=self.policy.model,
            model_returned=self.policy.model,
            api=self.policy.api,
            store=False,
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


class _DirectProviderResponse:
    """Return one valid provider envelope for direct-egress probes."""

    headers = {"x-request-id": "request:direct-egress-probe"}

    def __init__(self, *, response_bytes: bytes) -> None:
        """Preserve exact response bytes supplied by the probe."""
        self._response_bytes = response_bytes

    def __enter__(self) -> "_DirectProviderResponse":
        """Enter the deterministic provider response context."""
        return self

    def __exit__(self, *args: object) -> None:
        """Leave the response context without suppressing errors."""
        return None

    def read(self) -> bytes:
        """Return the exact fake provider envelope bytes."""
        return self._response_bytes


class _DirectProviderOpener:
    """Capture any attempted direct provider request without real network."""

    def __init__(self, *, calls: List[object]) -> None:
        """Bind the mutable call ledger used by no-egress assertions."""
        self._calls = calls

    def open(self, *, fullurl: object, timeout: int) -> object:
        """Record the attempted egress and return a valid provider result."""
        self._calls.append((fullurl, timeout))
        fixture = reader_attempt_fixture()
        return _DirectProviderResponse(
            response_bytes=canonical_json_bytes(
                value={
                    "id": "resp_direct_egress_probe",
                    "model": "gpt-5.6-terra",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": fixture[
                                        "response_bytes"
                                    ].decode("utf-8"),
                                }
                            ],
                        }
                    ],
                }
            )
        )


class AiReaderContractTest(unittest.TestCase):
    """Prove remote fail-closed behavior and immutable recorded attempts."""

    def test_remote_adapter_direct_complete_requires_live_source_authority(
        self,
    ) -> None:
        """Reject raw caller bytes before the repository transport is invoked."""
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Return an observable transport that must remain untouched."""
            return _FixtureApprovedTransport(policy=policy, calls=calls)

        with mock.patch.object(
            ai_adapter,
            "_TRANSPORT_FACTORIES",
            {"openai": transport_factory},
        ):
            adapter = build_approved_transport_adapter()
            with self.assertRaisesRegex(
                AIAdapterError, "live source authority"
            ):
                adapter.complete(
                    request_bytes=b'{"private_non_sec_data":"secret"}'
                )
        self.assertEqual([], calls)

    def test_remote_attempt_rejects_factory_request_without_sec_authority(
        self,
    ) -> None:
        """Reject a self-consistent private table-grid before remote egress."""
        private_html = (
            b"<html><body><table><tr><th>private</th></tr>"
            b"<tr><td>secret-value</td></tr></table></body></html>"
        )
        private_asset = build_table_grid(
            html_bytes=private_html,
            parent_raw_asset_ids=[
                "sha256:" + sha256_bytes(content=private_html)
            ],
            storage_uri="private-memory-only",
        )
        private_manifest = build_reader_input_manifest(
            derived_asset=private_asset,
            source_reference_ids=["sha256:" + "a" * 64],
        )
        prepared = prepare_reader_request(
            manifest=private_manifest,
            derived_asset=private_asset,
            compiled_spec=compiled_specs()["DISCLOSURE"],
        )
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Return an observable transport that must remain untouched."""
            return _FixtureApprovedTransport(policy=policy, calls=calls)

        with mock.patch.object(
            ai_adapter,
            "_TRANSPORT_FACTORIES",
            {"openai": transport_factory},
        ):
            adapter = build_approved_transport_adapter()
            with self.assertRaisesRegex(
                AIAdapterError, "live source authority"
            ):
                run_ai_attempt(
                    adapter=adapter,
                    prepared_request=prepared,
                    clock=fixed_clock,
                )
        self.assertEqual([], calls)

    def test_remote_authorized_method_rejects_imported_token_and_raw(
        self,
    ) -> None:
        """Reject the module token combined with caller-selected raw bytes."""
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Return a transport proving whether raw bytes crossed."""
            return _FixtureApprovedTransport(policy=policy, calls=calls)

        with mock.patch.object(
            ai_adapter,
            "_TRANSPORT_FACTORIES",
            {"openai": transport_factory},
        ):
            adapter = build_approved_transport_adapter()
            self.assertFalse(
                hasattr(ai_adapter, "_REMOTE_ATTEMPT_AUTHORITY")
            )
            with self.assertRaises(TypeError):
                adapter._complete_authorized(
                    request_bytes=b'{"private_non_sec_data":"secret"}',
                    authority=object(),
                )
        self.assertEqual([], calls)

    def test_openai_transport_class_rejects_caller_raw_bytes(self) -> None:
        """Reject direct construction of the raw-capable OpenAI transport."""
        calls: List[object] = []
        adapter = build_approved_transport_adapter()
        transport = ai_adapter._OpenAIResponsesTransport(
            policy=adapter.policy,
        )
        with self.assertRaises(TypeError):
            transport.complete(
                request_bytes=b'{"private_non_sec_data":"secret"}'
            )
        with mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "direct-egress-probe"}
        ), mock.patch.object(
            ai_adapter,
            "_OPENAI_OPENER",
            _DirectProviderOpener(calls=calls),
        ), self.assertRaisesRegex(
            AIAdapterError, "live source authority"
        ):
            transport.complete(
                prepared_request=b'{"private_non_sec_data":"secret"}'
            )
        self.assertEqual([], calls)

    def test_openai_transport_factory_rejects_caller_raw_bytes(self) -> None:
        """Reject raw bytes passed through the importable factory mapping."""
        calls: List[object] = []
        adapter = build_approved_transport_adapter()
        transport = ai_adapter._TRANSPORT_FACTORIES["openai"](
            policy=adapter.policy,
        )
        with self.assertRaises(TypeError):
            transport.complete(
                request_bytes=b'{"private_non_sec_data":"secret"}'
            )
        with mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "direct-egress-probe"}
        ), mock.patch.object(
            ai_adapter,
            "_OPENAI_OPENER",
            _DirectProviderOpener(calls=calls),
        ), self.assertRaisesRegex(
            AIAdapterError, "live source authority"
        ):
            transport.complete(
                prepared_request=b'{"private_non_sec_data":"secret"}'
            )
        self.assertEqual([], calls)

    def test_openai_transport_accepts_replayed_live_sec_request(self) -> None:
        """Send only after the actual transport replays immutable SEC bytes."""
        calls: List[object] = []
        policy = build_approved_transport_adapter().policy
        transport = ai_adapter._OpenAIResponsesTransport(policy=policy)
        with tempfile.TemporaryDirectory() as directory:
            fixture = live_sec_reader_repository(
                workspace=Path(directory),
            )
            prepared_request = live_prepared_fixture(fixture=fixture)
            with mock.patch.object(
                ai_adapter, "_REPOSITORY_ROOT", fixture["repo_root"],
            ), mock.patch.dict(
                "os.environ", {"OPENAI_API_KEY": "live-sec-probe"}
            ), mock.patch.object(
                ai_adapter,
                "_OPENAI_OPENER",
                _DirectProviderOpener(calls=calls),
            ):
                result = transport.complete(
                    prepared_request=prepared_request,
                )
        self.assertEqual(1, len(calls))
        self.assertTrue(result.observation.egress_attempted)
        request = calls[0][0]
        outbound = json.loads(request.data.decode("utf-8"))
        serialized = canonical_json_bytes(value=outbound)
        self.assertNotIn(b"source_repo_relative_path", serialized)
        self.assertNotIn(b"request_attempt_id", serialized)

    def test_live_authority_rebuild_rejects_substituted_table_grid(
        self,
    ) -> None:
        """Reject a factory wrapper whose grid was not parsed from SEC bytes."""
        calls: List[bytes] = []

        def transport_factory(*, policy: object) -> object:
            """Return an observable transport that must remain untouched."""
            return _FixtureApprovedTransport(policy=policy, calls=calls)

        with tempfile.TemporaryDirectory() as directory:
            fixture = live_sec_reader_repository(
                workspace=Path(directory),
            )
            substituted = live_prepared_fixture(
                fixture=fixture,
                table_html_bytes=(
                    b"<html><body><table><tr><td>private-secret"
                    b"</td></tr></table></body></html>"
                ),
            )
            with mock.patch.object(
                ai_adapter, "_REPOSITORY_ROOT", fixture["repo_root"],
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"openai": transport_factory},
            ):
                with self.assertRaisesRegex(
                    AIAdapterError, "source authority binding differs"
                ):
                    run_ai_attempt(
                        adapter=build_approved_transport_adapter(),
                        prepared_request=substituted,
                        clock=fixed_clock,
                    )
        self.assertEqual([], calls)

    def test_openai_responses_envelope_is_strict_and_tool_free(self) -> None:
        """Bind the approved Reader payload to the exact safe provider body."""
        policy = ai_adapter.TransportPolicy.from_mapping(
            value={
                "provider": "openai",
                "model": "gpt-5.6-terra",
                "api": "responses",
                "endpoint_host": "api.openai.com",
                "region": "provider-managed-global-no-residency-guarantee",
                "retention": (
                    "default abuse-monitoring up to 30 days; responses "
                    "store=false; no ZDR claim"
                ),
                "data_use": (
                    "not used for training by default; no opt-in sharing"
                ),
                "timeout_seconds": 120,
                "retry_count": 2,
                "maximum_payload_bytes": 8388608,
                "filing_egress_policy": (
                    "PUBLIC_SEC_FILING_TABLE_GRIDS_ONLY"
                ),
            }
        )
        prepared = reader_attempt_fixture()["prepared_request"]
        body_bytes, schema_bytes = ai_adapter.build_openai_responses_body(
            policy=policy,
            reader_request_bytes=prepared.request_bytes,
        )
        body = json.loads(body_bytes.decode("utf-8"))
        self.assertEqual(
            {
                "background",
                "input",
                "model",
                "parallel_tool_calls",
                "reasoning",
                "store",
                "temperature",
                "text",
                "tool_choice",
                "tools",
                "truncation",
            },
            set(body),
        )
        self.assertEqual("gpt-5.6-terra", body["model"])
        self.assertFalse(body["store"])
        self.assertFalse(body["background"])
        self.assertEqual([], body["tools"])
        self.assertEqual("none", body["tool_choice"])
        self.assertEqual(0, body["temperature"])
        self.assertEqual({"effort": "none"}, body["reasoning"])
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(
            body["text"]["format"]["schema"],
            json.loads(schema_bytes.decode("utf-8")),
        )
        self.assertNotIn("OPENAI_API_KEY", body_bytes.decode("utf-8"))

    def test_deepseek_chat_envelope_is_json_and_tool_free(self) -> None:
        """Bind the R5 Reader payload to DeepSeek's official chat envelope."""
        policy = ai_adapter.TransportPolicy.from_mapping(
            value={
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "api": "chat_completions",
                "endpoint_host": "api.deepseek.com",
                "region": "provider-managed-no-residency-guarantee",
                "retention": "provider-managed; no zero-retention claim",
                "data_use": (
                    "provider-managed; no training or data-use guarantee"
                ),
                "timeout_seconds": 120,
                "retry_count": 2,
                "maximum_payload_bytes": 8388608,
                "filing_egress_policy": (
                    "PUBLIC_SEC_FILING_TABLE_GRIDS_ONLY"
                ),
            }
        )
        prepared = reader_attempt_fixture()["prepared_request"]
        body_bytes, schema_bytes = (
            ai_adapter.build_deepseek_chat_completions_body(
                policy=policy,
                reader_request_bytes=prepared.request_bytes,
            )
        )
        body = json.loads(body_bytes.decode("utf-8"))
        self.assertEqual(
            {
                "messages", "model", "response_format", "stream",
                "temperature", "thinking",
            },
            set(body),
        )
        self.assertEqual("deepseek-v4-flash", body["model"])
        self.assertEqual({"type": "json_object"}, body["response_format"])
        self.assertEqual({"type": "disabled"}, body["thinking"])
        self.assertIs(False, body["stream"])
        self.assertEqual(0, body["temperature"])
        self.assertEqual(2, len(body["messages"]))
        self.assertEqual("system", body["messages"][0]["role"])
        self.assertEqual("user", body["messages"][1]["role"])
        self.assertIn(
            '"unresolved_competing_claims"',
            body["messages"][0]["content"],
        )
        self.assertEqual(
            ai_adapter.READER_OUTPUT_JSON_SCHEMA,
            json.loads(schema_bytes.decode("utf-8")),
        )
        self.assertNotIn("DEEPSEEK_API_KEY", body_bytes.decode("utf-8"))

    def test_openai_key_missing_is_observed_without_egress(self) -> None:
        """Return a stable missing-secret failure before opening a socket."""
        policy = ai_adapter.TransportPolicy.from_mapping(
            value={
                "provider": "openai",
                "model": "gpt-5.6-terra",
                "api": "responses",
                "endpoint_host": "api.openai.com",
                "region": "provider-managed-global-no-residency-guarantee",
                "retention": (
                    "default abuse-monitoring up to 30 days; responses "
                    "store=false; no ZDR claim"
                ),
                "data_use": (
                    "not used for training by default; no opt-in sharing"
                ),
                "timeout_seconds": 120,
                "retry_count": 2,
                "maximum_payload_bytes": 8388608,
                "filing_egress_policy": (
                    "PUBLIC_SEC_FILING_TABLE_GRIDS_ONLY"
                ),
            }
        )
        transport = ai_adapter._TRANSPORT_FACTORIES["openai"](
            policy=policy
        )
        with mock.patch.dict("os.environ", {}, clear=True), (
            self.assertRaises(ai_adapter.TransportAttemptError)
        ) as raised, mock.patch.object(
            socket, "socket", side_effect=AssertionError("network forbidden")
        ), mock.patch.object(
            ai_adapter,
            "_validate_live_prepared_request",
            return_value=reader_attempt_fixture()["prepared_request"],
        ):
            transport.complete(
                prepared_request=reader_attempt_fixture()[
                    "prepared_request"
                ]
            )
        self.assertEqual("OPENAI_API_KEY_REQUIRED", raised.exception.error_class)
        self.assertFalse(raised.exception.observation.egress_attempted)

    def test_openai_response_keeps_provider_and_envelope_bytes(self) -> None:
        """Preserve raw provider bytes separately from extracted JSON output."""
        fixture = reader_attempt_fixture()
        provider_bytes = canonical_json_bytes(
            value={
                "id": "resp_fixture_001",
                "model": "gpt-5.6-terra",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": fixture["response_bytes"].decode(
                                    "utf-8"
                                ),
                            }
                        ],
                    }
                ],
            }
        )
        requests = []

        class FixtureResponse:
            """Return one exact provider response without network I/O."""

            headers = {"x-request-id": "request_fixture_001"}

            def __enter__(self) -> "FixtureResponse":
                """Enter the fake response context."""
                return self

            def __exit__(self, *args: object) -> None:
                """Leave the fake response context without suppressing."""
                return None

            def read(self) -> bytes:
                """Return the exact raw provider bytes."""
                return provider_bytes

        class FixtureOpener:
            """Capture the fixed URL and secret-bearing ephemeral request."""

            def open(self, *, fullurl: object, timeout: int) -> object:
                """Return a deterministic response for one exact request."""
                requests.append((fullurl, timeout))
                return FixtureResponse()

        with mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "test-secret-never-persist"}
        ), mock.patch.object(
            ai_adapter, "_OPENAI_OPENER", FixtureOpener()
        ):
            adapter = build_approved_transport_adapter()
            response, raw, attempt, payloads = run_remote_transport_unit_attempt(
                adapter=adapter,
                prepared_request=fixture["prepared_request"],
            )
        self.assertEqual(fixture["response_bytes"], response)
        self.assertEqual(provider_bytes, raw)
        self.assertEqual(provider_bytes, payloads.raw_response_bytes)
        self.assertNotEqual(
            payloads.reader_payload_bytes, payloads.request_body_bytes
        )
        self.assertEqual("gpt-5.6-terra", attempt["model_requested"])
        self.assertEqual("gpt-5.6-terra", attempt["model_returned"])
        self.assertEqual("responses", attempt["api"])
        self.assertEqual(
            sha256_bytes(content=payloads.request_body_bytes),
            attempt["request_body_sha256"],
        )
        self.assertEqual(
            sha256_bytes(content=provider_bytes),
            attempt["raw_response_sha256"],
        )
        for content in (
            payloads.request_body_bytes,
            payloads.output_schema_bytes,
            payloads.raw_response_bytes,
        ):
            self.assertNotIn(b"test-secret-never-persist", content)
        self.assertEqual(1, len(requests))
        request, timeout = requests[0]
        self.assertEqual("https://api.openai.com/v1/responses", request.full_url)
        self.assertEqual(120, timeout)

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
        response, _raw, _attempt, _payloads = run_ai_attempt(
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
            first_response, first_raw, first, _first_payloads = run_ai_attempt(
                adapter=adapter,
                prepared_request=fixture["prepared_request"],
                clock=fixed_clock,
            )
            second_response, second_raw, second, _second_payloads = (
                run_ai_attempt(
                adapter=adapter,
                prepared_request=fixture["prepared_request"],
                clock=fixed_clock,
                )
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

        response, raw_response, attempt, _payloads = run_ai_attempt(
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
        current = build_approved_transport_adapter()
        self.assertEqual("openai", current.policy.provider)
        self.assertEqual("gpt-5.6-terra", current.policy.model)
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
                result = complete_remote_transport_unit(
                    adapter=adapter,
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
                "api": "responses",
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

    def test_live_workflow_rebuilds_sec_authority_before_remote_mock(
        self,
    ) -> None:
        """Allow one immutable SEC body only after full source replay."""
        calls: List[bytes] = []

        class LiveReaderTransport:
            """Return a response whose locators follow the rebuilt request."""

            def __init__(self, *, policy: object) -> None:
                """Bind the exact repository D-01 transport policy."""
                self.policy = policy

            def complete(self, *, prepared_request: object) -> object:
                """Record the authorized payload and return matching claims."""
                rebuilt = ai_adapter._validate_live_prepared_request(
                    prepared_request=prepared_request,
                )
                request_bytes = rebuilt.request_bytes
                calls.append(request_bytes)
                request = json.loads(request_bytes.decode("utf-8"))
                manifest = request["reader_input_manifest"]
                asset = {
                    "derived_asset_id": manifest["derived_asset_id"],
                    "tables": request["untrusted_table_data"],
                }
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
                    request_body_bytes=len(request_bytes),
                )
                return ai_adapter.TransportResult(
                    response_bytes=reader_response(asset=asset),
                    provider_request_id="request:live-authority-fixture",
                    observation=observation,
                )

        with tempfile.TemporaryDirectory() as directory:
            fixture = live_sec_reader_repository(
                workspace=Path(directory),
            )
            repo_root = fixture["repo_root"]
            with mock.patch.object(
                ai_adapter, "_REPOSITORY_ROOT", repo_root,
            ), mock.patch.object(
                ai_adapter,
                "_TRANSPORT_FACTORIES",
                {"openai": LiveReaderTransport},
            ):
                result = create_review_run(
                    repo_root=repo_root,
                    run_dir=Path(directory) / "run",
                    run_id="run:live:source-authority-positive",
                    company_id="marriott_international",
                    target_period={
                        "fiscal_year": 2025,
                        "period_start": "2025-01-01",
                        "period_end": "2025-12-31",
                    },
                    source_repo_relative_path=str(
                        fixture["source_repo_relative_path"]
                    ),
                    source_media_type="text/html",
                    source_url=str(fixture["source_url"]),
                    accession=str(fixture["accession"]),
                    document_name=str(fixture["document_name"]),
                    source_role="target_primary",
                    request_attempt_id=str(
                        fixture["request_attempt_id"]
                    ),
                    disclosure_spec_path=(
                        "catalog/disclosures/lodging_kpi_table.md"
                    ),
                    adapter=build_approved_transport_adapter(),
                    clock=fixed_clock,
                )
        self.assertEqual("PENDING_HUMAN_REVIEW", result["status"])
        self.assertEqual(1, len(calls))
        payload = json.loads(calls[0].decode("utf-8"))
        self.assertNotIn("request_attempt_id", payload)
        self.assertNotIn("source_repo_relative_path", payload)

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
                    complete_remote_transport_unit(
                        adapter=build_approved_transport_adapter(),
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
                        response, raw, attempt, _payloads = (
                            run_remote_transport_unit_attempt(
                            adapter=adapter,
                            prepared_request=prepared,
                            )
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

                def complete(self, *, prepared_request: object) -> object:
                    """Raise a raw timeout after recording invocation."""
                    rebuilt = ai_adapter._validate_live_prepared_request(
                        prepared_request=prepared_request,
                    )
                    request_bytes = rebuilt.request_bytes
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
                    run_remote_transport_unit_attempt(
                        adapter=adapter,
                        prepared_request=prepared,
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

                def complete(self, *, prepared_request: object) -> object:
                    """Model an invoked transport that omits observation."""
                    rebuilt = ai_adapter._validate_live_prepared_request(
                        prepared_request=prepared_request,
                    )
                    request_bytes = rebuilt.request_bytes
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
                    run_remote_transport_unit_attempt(
                        adapter=adapter,
                        prepared_request=prepared,
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
                    AIAdapterError, "D-01 changed"
                ):
                    complete_remote_transport_unit(
                        adapter=adapter, request_bytes=b"filing-bytes",
                    )
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
                _response, _raw, attempt, _payloads = (
                    run_remote_transport_unit_attempt(
                    adapter=adapter,
                    prepared_request=prepared,
                    )
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
                {"temperature": 0, "reasoning_effort": "none"},
                attempt["sampling_parameters"],
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
            validate_and_freeze_run(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            replay = replay_frozen_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            self.assertEqual(2, len(replay["results"]))


if __name__ == "__main__":
    unittest.main()
