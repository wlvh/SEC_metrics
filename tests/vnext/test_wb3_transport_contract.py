"""Current controlled transport audit checks beyond the obsolete factory."""

from contextlib import ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_invocation_control import CanaryDeepSeekOpener
from tests.vnext.test_invocation_control import ProductionReaderTransport
from tests.vnext.test_invocation_control import cutover_reader_plan_fixture, operator_arguments
from tools import vnext_operator
from vnext import ai_adapter
from vnext.canonical import sha256_bytes
from vnext.run_store import load_open_run


SECRET = "test-wb3-secret-never-persist"


class ExactWireOpener(CanaryDeepSeekOpener):
    """Keep the canary's exact wire for comparison with native Run bytes."""

    def open(self, *, fullurl, timeout):
        response = super().open(fullurl=fullurl, timeout=timeout)
        self.raw_response = response.response_bytes
        return response


class Wb3ControlledTransportContractTest(unittest.TestCase):
    """Use the actual SEC replay and WB-3 entrypoint with injected transports."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wb3-transport-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = cutover_reader_plan_fixture(workspace=self.root / "fixture")
        self.run_dir = self.root / "runs" / "controlled"
        self.canary = ExactWireOpener()
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(mock.patch.object(
            ai_adapter, "_REPOSITORY_ROOT", self.fixture["repo_root"]))
        self.patches.enter_context(mock.patch.object(
            vnext_operator, "REPO_ROOT", self.fixture["repo_root"]))
        self.patches.enter_context(mock.patch.object(
            ai_adapter, "_DEEPSEEK_OPENER", self.canary))
        self.patches.enter_context(mock.patch.object(
            ai_adapter._InvocationControllerTransport, "transport_kind", "MOCK"))
        self.patches.enter_context(mock.patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": SECRET,
            "SEC_CONTACT_EMAIL": "sec-tests@wlvh.com",
        }))
        self.socket = self.patches.enter_context(mock.patch(
            "socket.socket", side_effect=AssertionError("NO_NETWORK")))
        self.addCleanup(self.socket.assert_not_called)

    def prepare(self):
        return vnext_operator._prepare(arguments=operator_arguments(
            run_dir=self.run_dir, fixture=self.fixture))

    def attempt(self):
        _, records, _ = load_open_run(run_dir=self.run_dir)
        return next(row for row in records if row["record_type"] == "AI_EXTRACTION_ATTEMPT")

    def test_controlled_operator_preserves_exact_wire_and_never_persists_secret(self):
        result = self.prepare()
        self.assertEqual("PENDING_HUMAN_REVIEW", result["status"])
        attempt = self.attempt()
        self.assertEqual("SUCCEEDED", attempt["status"])
        self.assertEqual(1, len(self.canary.calls))
        request, _ = self.canary.calls[0]
        self.assertEqual("Bearer " + SECRET, request.get_header("Authorization"))
        raw = (self.run_dir / attempt["raw_response_path"]).read_bytes()
        outbound = (self.run_dir / attempt["request_body_path"]).read_bytes()
        assistant = (self.run_dir / attempt["assistant_output_path"]).read_bytes()
        reader = (self.run_dir / attempt["reader_payload_path"]).read_bytes()
        self.assertEqual(self.canary.raw_response, raw)
        self.assertEqual(request.data, outbound)
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"].encode(), assistant)
        self.assertEqual(json.loads(reader), json.loads(json.loads(outbound)["messages"][1]["content"]))
        self.assertNotEqual(reader, outbound)
        self.assertEqual(sha256_bytes(content=raw), attempt["raw_response_sha256"])
        self.assertEqual(sha256_bytes(content=outbound), attempt["request_body_sha256"])
        self.assertEqual("deepseek", attempt["provider"])
        self.assertEqual("chat_completions", attempt["api"])
        self.assertEqual("api.deepseek.com", attempt["endpoint_host"])
        for path in self.run_dir.parent.rglob("*"):
            if path.is_file():
                with self.subTest(path=path.relative_to(self.run_dir.parent)):
                    self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_observed_wrong_host_is_retained_and_has_no_success_receipt(self):
        calls = []

        class WrongHostTransport(ProductionReaderTransport):
            def complete(self, *, prepared_request, egress_capability):
                result = super().complete(prepared_request=prepared_request,
                                          egress_capability=egress_capability)
                return replace(result, observation=replace(
                    result.observation, endpoint_host="attacker.invalid"))

        def factory(*, policy):
            return WrongHostTransport(policy=policy, mutation="PASS", calls=calls)

        with mock.patch.object(ai_adapter, "_TRANSPORT_FACTORIES", {"deepseek": factory}):
            result = self.prepare()
        self.assertEqual("FAILED_ATTEMPT", result["status"])
        attempt = self.attempt()
        self.assertEqual("FAILED", attempt["status"])
        self.assertEqual("attacker.invalid", attempt["endpoint_host"])
        self.assertEqual("attacker.invalid", attempt["transport_observation"]["endpoint_host"])
        self.assertTrue(attempt["transport_observation"]["egress_attempted"])
        self.assertTrue((self.run_dir / attempt["raw_response_path"]).is_file())
        self.assertEqual(1, len(calls))
        self.assertEqual([], self.canary.calls)
        responses = self.run_dir.parent / "invocation_control/responses"
        self.assertEqual([], list(responses.rglob("receipt.json")))

    def test_unobserved_legacy_tuple_cannot_become_an_audited_success(self):
        calls = []

        class UnobservedTransport(ProductionReaderTransport):
            def complete(self, *, prepared_request, egress_capability):
                result = super().complete(prepared_request=prepared_request,
                                          egress_capability=egress_capability)
                return result.response_bytes, result.provider_request_id

        def factory(*, policy):
            return UnobservedTransport(policy=policy, mutation="PASS", calls=calls)

        with mock.patch.object(ai_adapter, "_TRANSPORT_FACTORIES", {"deepseek": factory}):
            with self.assertRaisesRegex(ai_adapter.AIAdapterError,
                                        "Attempt failed without transport observation") as raised:
                self.prepare()
        self.assertRegex(str(raised.exception.__cause__),
                         "Repository transport returned without transport observation")
        self.assertEqual(1, len(calls))
        self.assertEqual([], self.canary.calls)
        responses = self.run_dir.parent / "invocation_control/responses"
        self.assertEqual([], list(responses.rglob("receipt.json")))

    def test_unobserved_timeout_cannot_become_an_audited_success(self):
        calls = []

        class UnobservedTimeout(ProductionReaderTransport):
            def complete(self, *, prepared_request, egress_capability):
                super().complete(prepared_request=prepared_request,
                                 egress_capability=egress_capability)
                raise TimeoutError("test timeout without transport observation")

        def factory(*, policy):
            return UnobservedTimeout(policy=policy, mutation="PASS", calls=calls)

        with mock.patch.object(ai_adapter, "_TRANSPORT_FACTORIES", {"deepseek": factory}):
            with self.assertRaisesRegex(ai_adapter.AIAdapterError,
                                        "Attempt failed without transport observation") as raised:
                self.prepare()
        self.assertRegex(str(raised.exception.__cause__),
                         "Repository transport failed without auditable observation")
        self.assertEqual(1, len(calls))
        self.assertEqual([], self.canary.calls)
        responses = self.run_dir.parent / "invocation_control/responses"
        self.assertEqual([], list(responses.rglob("receipt.json")))

    def test_factory_policy_mismatch_stops_before_transport_call(self):
        complete = mock.Mock(side_effect=AssertionError("FORGED_TRANSPORT_CALLED"))

        def factory(*, policy):
            return SimpleNamespace(policy=replace(policy, endpoint_host="attacker.invalid"),
                                   complete=complete)

        with mock.patch.object(ai_adapter, "_TRANSPORT_FACTORIES", {"deepseek": factory}):
            with self.assertRaisesRegex(ai_adapter.AIAdapterError,
                                        "Attempt failed without transport observation") as raised:
                self.prepare()
        self.assertRegex(str(raised.exception.__cause__),
                         "Repository transport policy differs from D-01")
        complete.assert_not_called()
        self.assertEqual([], self.canary.calls)


if __name__ == "__main__":
    unittest.main()
