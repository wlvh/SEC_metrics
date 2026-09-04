"""Controller protocol negatives; native recorded R4 integration is separate."""

import copy
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT  # establishes the repository import path
from tests.vnext.test_invocation_control import (
    REQUEST_BODY, UTC, MockTransport, identity, transport_result,
    validate_response, validate_evidence, reject_schema, reject_evidence, plan as legacy_plan,
)
from vnext import invocation_control as control
from vnext.canonical import content_hash


class SuccessorInvocationControlTest(unittest.TestCase):
    """No socket: test the same durable controller with an explicit subtype."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.authority = control.SuccessorInvocationAuthority(
            factory=control._SUCCESSOR_AUTHORITY_FACTORY, root=self.root,
            identity={"artifact_requirement_generation": "EXPLICIT_REQUIREMENT_V1",
                "requirement_id": "issue_28_v2", "requirement_closure_hash": identity(label="closure"),
                "requirement_hashes": {"fixture": identity(label="requirement")}},
            policy={"provider_transport_decision_hash": identity(label="transport"),
                "transport_retry_decision_hash": identity(label="retry"),
                "live_call_bound_decision_hash": identity(label="calls"),
                "automatic_retry_count": 0, "response_reuse_authorized": False,
                "requirement_closure_hash": identity(label="closure")},
            transport={"provider": "deepseek", "model": "deepseek-v4-flash",
                "api": "chat_completions", "maximum_payload_bytes": 8388608}, files={})
        old = legacy_plan()
        self.plan = control.build_successor_ai_invocation_plan(repo_root=self.root, authority=self.authority,
            release_input_plan_id=identity(label="release"), source_identity_hash=old["source_identity_hash"],
            selected_representation_hash=old["selected_representation_hash"], task_contract_hash=identity(label="task"),
            output_schema_hash=identity(label="schema"), serialization_version="R4_SCOPED_V1",
            provider="deepseek", model="deepseek-v4-flash", api="chat_completions", request_body=REQUEST_BODY,
            maximum_payload_bytes=8388608, maximum_context_tokens=200000, estimated_context_tokens=20,
            context_authority_hash=identity(label="context"), estimator_id="utf8_byte_upper_bound",
            estimator_version="1", estimator_method="UTF8_BYTE_UPPER_BOUND", billing_class="PAID_MODEL_ENDPOINT",
            paid_call_observation_source="PROVIDER_POLICY_BILLING_CLASS_X_EGRESS_MARKER",
            pricing_snapshot_hash=identity(label="price"), estimated_cost="0")

    def tearDown(self):
        self.temp.cleanup()

    def run_attempt(self, transport, *, owner="recorded-owner", response=validate_response,
                    evidence=validate_evidence, workspace=None):
        return control.execute_successor_invocation(repo_root=self.root, authority=self.authority,
            workspace_dir=workspace or self.root / "runtime", plan=self.plan, request_body=REQUEST_BODY,
            execution_id=control.execution_identity(ai_invocation_plan_id=self.plan["ai_invocation_plan_id"],
                owner_token=owner, authorized_at_utc=UTC), owner_token=owner, authorized_at_utc=UTC,
            clock=lambda: UTC, transport=transport,
            response_validator=response, evidence_validator=evidence)

    def test_explicit_generation_and_policy_are_bound(self):
        self.assertEqual(self.plan["record_type"], "SUCCESSOR_AI_INVOCATION_PLAN")
        for fields in (("requirement_id",), ("requirement_closure_hash", "requirement_hashes"),
                       ("requirement_id", "requirement_closure_hash", "requirement_hashes"),
                       ("artifact_requirement_generation",)):
            changed = copy.deepcopy(self.plan)
            for field in fields:
                del changed[field]
            changed["ai_invocation_plan_id"] = content_hash(value={k: v for k, v in changed.items()
                if k != "ai_invocation_plan_id"})
            with self.subTest(fields=fields), self.assertRaises(control.InvocationControlError):
                control.validate_successor_ai_invocation_plan(plan=changed, repo_root=self.root, authority=self.authority)
        for key, value in (("automatic_retry_count", 1), ("response_reuse_authorized", True)):
            changed = copy.deepcopy(self.plan)
            changed["invocation_policy"][key] = value
            changed["ai_invocation_plan_id"] = content_hash(value={k: v for k, v in changed.items()
                if k != "ai_invocation_plan_id"})
            with self.assertRaises(control.InvocationControlError):
                control.validate_successor_ai_invocation_plan(plan=changed, repo_root=self.root, authority=self.authority)

    def test_retryable_http_has_one_marker_and_terminal_without_retry(self):
        transport = MockTransport(results=[transport_result(status_code=429), transport_result()])
        receipt = self.run_attempt(transport)
        self.assertEqual(receipt["status"], "FAILED_RETRYABLE_FINAL")
        self.assertTrue(receipt["batch_terminal"])
        self.assertEqual(len(receipt["attempts"]), 1)
        self.assertEqual(receipt["counters"]["mock_transport_invocation_count"], 1)
        self.assertEqual(receipt["counters"]["real_model_provider_egress_count"], 0)
        self.assertEqual(len(list((self.root / "runtime/invocation_control/egress").rglob("*.json"))), 1)

    def test_success_resume_is_idempotent_but_new_execution_cannot_reuse(self):
        transport = MockTransport(results=[transport_result()])
        first = self.run_attempt(transport)
        self.assertEqual(first["status"], "SUCCEEDED")
        self.assertEqual(self.run_attempt(MockTransport(results=[])), first)
        with self.assertRaisesRegex(control.InvocationControlError, "reuse"):
            self.run_attempt(MockTransport(results=[]), owner="different-execution")
        self.assertEqual(len(list((self.root / "runtime/invocation_control/egress").rglob("*.json"))), 1)

    def test_unknown_is_terminal_and_never_retried(self):
        result = self.run_attempt(MockTransport(results=[control.UnknownRemoteOutcomeError("interrupted")]))
        self.assertEqual(result["status"], "UNKNOWN_REMOTE_OUTCOME")
        self.assertTrue(result["batch_terminal"])
        self.assertEqual(self.run_attempt(MockTransport(results=[])), result)
        self.assertEqual(result["counters"]["mock_transport_invocation_count"], 1)

    def test_schema_and_evidence_failures_cannot_make_success(self):
        for validator in ("schema", "evidence"):
            with self.subTest(validator=validator), tempfile.TemporaryDirectory() as path:
                kwargs = {"response": reject_schema} if validator == "schema" else {"evidence": reject_evidence}
                result = self.run_attempt(MockTransport(results=[transport_result()]), workspace=Path(path), **kwargs)
                self.assertEqual(result["status"], "FAILED_TERMINAL")
                self.assertIsNone(result["success_response_receipt_id"])
                self.assertFalse(list((Path(path) / "invocation_control/responses").glob("*.json")))

    def test_historical_factory_output_remains_legacy(self):
        from tests.vnext.test_invocation_control import plan
        legacy = plan()
        self.assertEqual(set(legacy), control.PLAN_FIELDS)
        self.assertEqual(legacy["record_type"], "AI_INVOCATION_PLAN")
        with self.assertRaises(control.InvocationControlError):
            control.validate_successor_ai_invocation_plan(plan=legacy, repo_root=self.root, authority=self.authority)

    def test_portable_native_terminal_replays_markers_usage_reservation_and_acceptance(self):
        receipt = self.run_attempt(MockTransport(results=[transport_result()]))
        bundle = control.capture_successor_execution_bundle(repo_root=self.root, authority=self.authority,
            workspace_dir=self.root / "runtime", plan=self.plan, execution_receipt=receipt)
        success = control.load_successor_successful_response(repo_root=self.root, authority=self.authority,
            workspace_dir=self.root / "runtime", plan=self.plan)
        binding = {"owner_token_hash": content_hash(value="recorded-owner"),
                   "authorized_at_utc": UTC, "execution_mode": "RECORDED_TEST"}
        kwargs = {"receipt": receipt, "plan": self.plan, "authorization_binding": binding,
            "response_body": success["response_body"], "acceptance_receipt": success["acceptance_receipt"],
            "terminal_bundle": bundle, "repo_root": self.root, "authority": self.authority}
        self.assertEqual(control.validate_successor_execution_receipt(**kwargs), receipt)
        for field in ("egress_markers", "reservation_archive", "success_response_receipt"):
            wrong = copy.deepcopy(bundle)
            wrong[field] = [] if field == "egress_markers" else {}
            wrong["terminal_bundle_id"] = content_hash(value={k: v for k, v in wrong.items()
                if k != "terminal_bundle_id"})
            with self.subTest(field=field), self.assertRaises(control.InvocationControlError):
                control.validate_successor_execution_receipt(**{**kwargs, "terminal_bundle": wrong})


if __name__ == "__main__":
    unittest.main()
