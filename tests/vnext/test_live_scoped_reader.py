"""Successor scoped provider envelope and private transport boundaries."""

import copy
import dataclasses
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext.ai_adapter import AIAdapterError, _DeepSeekChatCompletionsTransport
from vnext.ai_adapter import approved_scoped_transport_policy
from vnext.ai_adapter import build_recorded_scoped_transport, build_scoped_provider_request_body
from vnext.ai_adapter import build_scoped_qualification_transport_adapter
from vnext.ai_adapter import _no_egress_policy_observation, _write_scoped_wire_journal
from vnext.ai_adapter import _qualification_usage_error
from vnext.ai_adapter import load_scoped_wire_journal, run_scoped_ai_attempt
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.invocation_control import build_ai_invocation_plan, execution_identity, _egress_marker
from vnext.live_scoped_reader import INPUT_RECORD_TYPE, LiveScopedReaderError
from vnext.live_scoped_reader import LiveScopedReaderRequest
from vnext.live_scoped_reader import LiveScopedReaderSession, _SESSION_FACTORY
from vnext.live_scoped_reader import ScopedInvocationAcceptanceContext
from vnext.requirements import load_requirement_snapshot


CASE = REPO_ROOT / "docs/r4_offline/qualified_cases/r4_a03_alternate/scoped_request.json"


class LiveScopedEnvelopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # v1 already carries the same inherited S-PROVIDER-TRANSPORT policy;
        # it avoids depending on an in-progress unactivated v2 source rebind.
        cls.requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_28_v1")
        cls.policy = approved_scoped_transport_policy(requirement=cls.requirement)
        cls.offline_bytes = CASE.read_bytes()
        body = json.loads(cls.offline_bytes)
        body.pop("scoped_plan_id")
        body["record_type"] = INPUT_RECORD_TYPE
        cls.live_input_bytes = canonical_json_bytes(value=body)

    def test_successor_envelope_preserves_scoped_period_unit_and_no_answer_metadata(self):
        outbound, schema = build_scoped_provider_request_body(
            policy=self.policy, reader_request_bytes=self.live_input_bytes)
        envelope = json.loads(outbound)
        request = json.loads(self.live_input_bytes)
        prompt = envelope["messages"][0]["content"]
        self.assertNotIn("FY<year>", prompt)
        self.assertIn("scoped_transport_contract.requested_period", prompt)
        self.assertEqual("2025Q4", request["scoped_transport_contract"]["requested_period"])
        self.assertEqual("percent", request["scoped_transport_contract"]["reported_unit_contract"])
        self.assertEqual(request, json.loads(envelope["messages"][1]["content"]))
        for forbidden in ("reference", "synthetic_candidate", "source_bound_proof",
                          "table_audit", "navigation_paths", "material_layout_proof"):
            self.assertNotIn(forbidden, request)
        self.assertEqual(sha256_bytes(content=schema),
                         sha256_bytes(content=canonical_json_bytes(value=json.loads(schema))))

    def test_offline_or_partial_request_cannot_be_dispatched_as_live_scoped_input(self):
        for data in (self.offline_bytes, b"{}", canonical_json_bytes(value={
                "record_type": INPUT_RECORD_TYPE, "schema_version": 2})):
            with self.subTest(data=data[:32]), self.assertRaises(AIAdapterError):
                build_scoped_provider_request_body(policy=self.policy,
                                                  reader_request_bytes=data)

    def test_scoped_policy_never_falls_back_to_d01_or_nonzero_retry(self):
        changed = copy.deepcopy(self.requirement)
        changed["effective_decisions"]["D-01"] = copy.deepcopy(
            changed["effective_decisions"]["S-PROVIDER-TRANSPORT"])
        changed["effective_decisions"]["D-01"]["choice"]["provider"] = "not-used"
        self.assertEqual(self.policy, approved_scoped_transport_policy(requirement=changed))
        changed = copy.deepcopy(self.requirement)
        del changed["effective_decisions"]["S-PROVIDER-TRANSPORT"]
        with self.assertRaises(AIAdapterError):
            approved_scoped_transport_policy(requirement=changed)
        changed = copy.deepcopy(self.requirement)
        changed["effective_decisions"]["S-PROVIDER-TRANSPORT"]["choice"]["retry_count"] = 1
        with self.assertRaises(AIAdapterError):
            approved_scoped_transport_policy(requirement=changed)

    def test_r4_raw_wire_usage_missing_or_over_ceiling_is_terminal(self):
        wire = {"id": "recorded-r4-usage-boundary", "object": "chat.completion",
            "model": self.policy.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"},
                         "finish_reason": "stop"}]}
        gate = {"actual_prompt_tokens_max": 200000, "terminal_error_class": "CONTEXT_LIMIT"}
        for label, usage, expected in (
            ("missing", None, "CONTEXT_LIMIT"),
            ("over", {"prompt_tokens": 200001, "completion_tokens": 1, "total_tokens": 200002},
             "CONTEXT_LIMIT"),
            ("inclusive ceiling", {"prompt_tokens": 200000, "completion_tokens": 1,
                                   "total_tokens": 200001}, ""),
        ):
            raw = dict(wire)
            if usage is not None:
                raw["usage"] = usage
            with self.subTest(usage=label):
                self.assertEqual(expected, _qualification_usage_error(
                    raw_response_bytes=canonical_json_bytes(value=raw), policy=gate))

    def test_private_request_and_recorded_transport_cannot_be_forged_or_promoted(self):
        with self.assertRaises(LiveScopedReaderError):
            LiveScopedReaderRequest(factory=object(), record_bytes=b"{}", request_bytes=b"{}",
                provider_request_body_bytes=b"{}", output_schema_bytes=b"{}",
                task_contract_bytes=b"{}", session=object())
        transport = build_recorded_scoped_transport(raw_response_bytes=b"{}",
            expected_provider_request_body_sha256="0" * 64)
        self.assertEqual("MOCK", transport.transport_kind)
        self.assertFalse(hasattr(transport, "complete"))
        self.assertFalse(hasattr(transport, "open"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            transport.status_code = 200

    def test_unwrapped_object_cannot_reach_repository_opener(self):
        transport = _DeepSeekChatCompletionsTransport(policy=self.policy)
        with mock.patch("vnext.ai_adapter._DEEPSEEK_OPENER.open",
                        side_effect=AssertionError("NO_PROVIDER")) as opener:
            with self.assertRaises(AIAdapterError):
                transport.complete(prepared_request=object())
        opener.assert_not_called()

    def test_na_only_source_is_materialized_once_without_a_provider_scope(self):
        # This pure ownership-branch test complements the real four-source
        # integration; it neither creates an authorization nor claims Evidence.
        session = object.__new__(LiveScopedReaderSession)
        session._factory, session._root = _SESSION_FACTORY, REPO_ROOT
        session._requirement, session._base_files, session._sources = {}, {}, {}
        session._authority = {"sources": {"not_applicable_source": {
            "source_repo_relative_path": "tests/fixtures/vnext/r4_offline/b0_source.html",
            "source_sha256": "0" * 64, "source_size": 1}},
            "fixtures": [{"source_id": "not_applicable_source", "task_contract_id": "task"}]}
        session._index = {"cases": [{"source_id": "not_applicable_source",
                                    "artifact_kind": "ZERO_CALL_CLASSIFICATION"}]}
        with mock.patch("vnext.live_scoped_reader.source_authority", return_value={
                "source_bytes": b"x", "raw_blob": {}, "source_reference": {}}), \
             mock.patch("vnext.live_scoped_reader.materialize_full_source", return_value={
                "asset": {}, "asset_bytes": b"{}", "report": {}}) as materialize, \
             mock.patch("vnext.live_scoped_reader.resolve_r4_task_contract",
                        return_value={"task_contract_id": "task"}), \
             mock.patch("vnext.live_scoped_reader.prepare_offline_evidence_context_from_asset_bytes",
                        return_value=object()), \
             mock.patch("vnext.live_scoped_reader.prepare_source_bundle_from_context",
                        return_value={"source_id": "not_applicable_source"}), \
             mock.patch("vnext.live_scoped_reader.prepare_offline_scoped_context",
                        side_effect=AssertionError("N/A must not create a provider scope")) as scoped:
            source = session._source("not_applicable_source")
            self.assertIsNone(source["scoped"])
            self.assertIs(source, session._source("not_applicable_source"))
        materialize.assert_called_once()
        scoped.assert_not_called()

    def test_recorded_transport_is_accepted_only_by_recorded_authorization_generation(self):
        transport = build_recorded_scoped_transport(raw_response_bytes=b"{}",
            expected_provider_request_body_sha256="0" * 64)
        with mock.patch("vnext.r4_live_authority.authorization_fields",
                        return_value={"execution_mode": "RECORDED_TEST"}):
            adapter = build_scoped_qualification_transport_adapter(
                authorization=object(), recorded_transport=transport)
        self.assertEqual("RECORDED_TEST", adapter.execution_mode)
        with mock.patch("vnext.r4_live_authority.authorization_fields",
                        return_value={"execution_mode": "LIVE"}):
            with self.assertRaises(AIAdapterError):
                build_scoped_qualification_transport_adapter(
                    authorization=object(), recorded_transport=transport)

    def test_provider_capacity_must_cover_but_does_not_replace_r4_context_ceiling(self):
        # Isolate the policy comparison before any invocation or transport;
        # source/type ownership is independently exercised by the real corpus.
        request = SimpleNamespace(record_bytes=b"request-record", repository_root=REPO_ROOT,
            _session=SimpleNamespace(_requirement=self.requirement, _invocation_authority=object()),
            identity={"requirement_id": "issue_28_v2", "full_reader_input_manifest_id": "manifest",
                      "full_derived_asset_id": "asset"},
            task_contract_bytes=b"task", output_schema_bytes=b"schema", provider_request_body_bytes=b"request")
        context = object.__new__(ScopedInvocationAcceptanceContext)
        object.__setattr__(context, "_request", request)
        fields = {"execution_mode": "RECORDED_TEST", "context_limit_tokens": 200000, "entry_id": "entry"}
        runtime = {"maximum_context_tokens": 199999, "context_authority_hash": "context",
            "estimator_id": "estimator", "estimator_version": "1", "estimator_method": "bytes",
            "billing_class": "PAID_MODEL_ENDPOINT", "paid_call_observation_source": "policy"}
        with mock.patch("vnext.ai_adapter._scoped_authorized_fields", return_value=fields), \
             mock.patch("vnext.ai_adapter.load_provider_runtime_authority", return_value=runtime), \
             mock.patch("vnext.ai_adapter.estimate_context_tokens", return_value=1), \
             mock.patch("vnext.invocation_control.build_successor_ai_invocation_plan",
                        side_effect=RuntimeError("STOP_BEFORE_EXECUTION")) as plan:
            with self.assertRaisesRegex(AIAdapterError, "approved context ceiling"):
                run_scoped_ai_attempt(adapter=object(), prepared_request=request, acceptance_context=context)
            plan.assert_not_called()
            for provider_capacity in (200000, 1000000):
                runtime["maximum_context_tokens"] = provider_capacity
                with self.subTest(provider_capacity=provider_capacity), \
                     self.assertRaisesRegex(RuntimeError, "STOP_BEFORE_EXECUTION"):
                    run_scoped_ai_attempt(adapter=object(), prepared_request=request, acceptance_context=context)
                self.assertEqual(200000, plan.call_args.kwargs["maximum_context_tokens"])

    def _wire_fixture(self, directory):
        body, schema = build_scoped_provider_request_body(
            policy=self.policy, reader_request_bytes=self.live_input_bytes)
        source = json.loads(self.live_input_bytes)
        plan = build_ai_invocation_plan(release_input_plan_id=content_hash(value="journal-unit-entry"),
            source_identity_hash=source["full_reader_input_manifest_id"],
            selected_representation_hash=source["full_derived_asset_id"],
            task_contract_hash=content_hash(value=source["task_contract"]),
            output_schema_hash="sha256:" + sha256_bytes(content=schema),
            serialization_version="journal-unit-v1", provider=self.policy.provider,
            model=self.policy.model, api=self.policy.api, request_body=body,
            maximum_payload_bytes=self.policy.maximum_payload_bytes, maximum_context_tokens=200000,
            estimated_context_tokens=len(body), context_authority_hash=content_hash(value="context"),
            estimator_id="UTF8_BYTES", estimator_version="1", estimator_method="UTF8_BYTE_UPPER_BOUND",
            billing_class="PAID_MODEL_ENDPOINT", paid_call_observation_source="PROVIDER_POLICY_BILLING_CLASS_X_EGRESS_MARKER",
            pricing_snapshot_hash=content_hash(value="non-blocking-price"), estimated_cost="0")
        timestamp = "2026-09-04T00:00:00Z"
        execution_id = execution_identity(ai_invocation_plan_id=plan["ai_invocation_plan_id"],
            owner_token="recorded-journal-unit", authorized_at_utc=timestamp)
        _egress_marker(root=directory / "invocation_control", execution_id=execution_id,
            plan=plan, attempt_ordinal=1, egress_started_at_utc=timestamp, transport_kind="MOCK")
        return body, plan, execution_id, timestamp

    def test_original_wire_is_immutable_and_never_replaced_by_assistant_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body, plan, execution_id, timestamp = self._wire_fixture(root)
            raw, assistant = b'{"original_provider_wire":true}', b'{"candidates":[]}'
            journal = _write_scoped_wire_journal(workspace_dir=root, plan=plan,
                execution_id=execution_id, request_body=body,
                observation=_no_egress_policy_observation(policy=self.policy, request_bytes=body),
                provider_request_id="recorded-journal", raw_response_bytes=raw,
                assistant_output_bytes=assistant, error_class="", observed_at_utc=timestamp)
            execution = {"execution_id": execution_id, "status": "SUCCEEDED", "finished_at_utc": timestamp}
            loaded = load_scoped_wire_journal(workspace_dir=root, plan=plan,
                execution_receipt=execution, request_body=body)
            self.assertEqual(journal, loaded["journal"])
            self.assertEqual(raw, loaded["raw_response_bytes"])
            self.assertEqual(assistant, loaded["assistant_output_bytes"])
            wire_path = root / "scoped_wire" / execution_id.split(":", 1)[1] / "raw_response.bin"
            self.assertTrue(wire_path.is_file())
            self.assertFalse((root / "invocation_control/scoped_wire").exists())
            wire_path.write_bytes(assistant)
            with self.assertRaises(AIAdapterError):
                load_scoped_wire_journal(workspace_dir=root, plan=plan,
                    execution_receipt=execution, request_body=body)

    def test_unknown_without_observed_wire_does_not_create_a_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body, plan, execution_id, timestamp = self._wire_fixture(root)
            execution = {"execution_id": execution_id, "status": "UNKNOWN_REMOTE_OUTCOME",
                         "finished_at_utc": timestamp}
            self.assertIsNone(load_scoped_wire_journal(workspace_dir=root, plan=plan,
                execution_receipt=execution, request_body=body))
            self.assertFalse((root / "scoped_wire").exists())
            execution["status"] = "SUCCEEDED"
            with self.assertRaises(AIAdapterError):
                load_scoped_wire_journal(workspace_dir=root, plan=plan,
                    execution_receipt=execution, request_body=body)
            execution["status"] = "UNKNOWN_REMOTE_OUTCOME"
            journal_directory = root / "scoped_wire" / execution_id.split(":", 1)[1]
            journal_directory.mkdir(parents=True)
            (journal_directory / "journal.json").symlink_to(root / "missing-journal")
            with self.assertRaises(AIAdapterError):
                load_scoped_wire_journal(workspace_dir=root, plan=plan,
                    execution_receipt=execution, request_body=body)


if __name__ == "__main__":
    unittest.main()
