"""Issue #47's model calls in the repository tree, where the egress patch is not applied.

``historical_model_calls`` holds everything a #47 model call would be bound to
except the socket. What is proven here, without the patch:

* the allowance is verified rather than merely present, the same three layers
  as the SEC allowance, plus the model-specific rules - one call is one
  provider and one paid call, never an SEC request; the transport is the fixed
  one; only wired metrics may be granted; the ledger root overlaps neither
  #28's, the checkout nor #47's SEC ledger;
* the ledger counts every claim, never redraws a request, stops on a slot
  without a terminal and on the stop reasons, and refuses a changed slot;
* nothing here can reach a provider: the controller makes no issue_47_v1
  authority, the adapter hands no bytes to this module's request type, the
  egress gate passes with this module present, and the sealed offline
  verification - which describes a tree with the patch applied - does not hold
  in this one.

The patched half is verified in a scratch tree by
docs/evidence/issue47_history/model-egress/verify.py.
"""
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import ai_adapter as adapter
from vnext import historical_model_calls as calls
from vnext import invocation_control as control
from vnext.canonical import content_hash, sha256_bytes

URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-1000000001"
RECORD = "docs/evidence/issue47_history/model-egress/test-fixture/delegation.json"
RECEIPT = "docs/evidence/issue47_history/model-egress/offline-verification.json"
PATCH = ROOT / "docs/evidence/issue47_history/model-egress/egress-registration.patch"
TRANSPORT = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
             "endpoint_host": adapter._DEEPSEEK_ENDPOINT_HOST,
             "region": "provider-managed-no-residency-guarantee",
             "retention": "provider-managed; no zero-retention claim",
             "data_use": "provider-managed; no training or data-use guarantee",
             "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
             "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}


def scope(first="2023-12-31", last="2023-12-31", metric="D04"):
    return {"purposes": [calls.PURPOSE], "metric_ids": [metric],
            "company_ids": ["marriott_international"], "earliest_report_end": first,
            "latest_report_end": last,
            "grants": [{"grant": "TEST", "metric_ids": [metric],
                        "company_ids": ["marriott_international"],
                        "earliest_report_end": first, "latest_report_end": last}]}


def fixture_tree(directory, *, policy_overrides=None, body_overrides=None, comment_overrides=None,
                 digest=None, budget_root="/var/lib/issue47-model-ledger-test"):
    """A temporary root holding a model allowance and its approval record."""
    root = Path(directory)
    policy = {"requirement_id": calls.REQUIREMENT_ID, "repository": "wlvh/SEC_metrics",
              "approver_login": "wlvh", "delegation_url": URL, "delegation_record_path": RECORD,
              "budget_root": budget_root, "maximum_additional_provider_paid_sec_calls": [4, 4, 0],
              "scope": scope(), "transport": dict(TRANSPORT),
              "retry_policy": dict(calls.FIXED_RETRY_POLICY), "model_wiring_receipt_path": RECEIPT}
    policy.update(policy_overrides or {})
    body = {"record_type": calls.DELEGATION_TYPE, "requirement_id": calls.REQUIREMENT_ID,
            "fixture": "RECORDED_TEST_ONLY_NOT_AN_APPROVAL", "production_authorized": False,
            **{field: policy[field] for field in calls.RESTATED_BY_THE_COMMENT}}
    body.update(body_overrides or {})
    text = json.dumps(body, sort_keys=True)
    comment = {"id": 1000000001, "html_url": URL,
               "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
               "user": {"login": "wlvh"}, "body": text, **(comment_overrides or {})}
    policy["delegation_body_sha256"] = digest or sha256_bytes(content=text.encode("utf-8"))
    (root / Path(RECORD).parent).mkdir(parents=True, exist_ok=True)
    (root / RECORD).write_text(json.dumps(comment), encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / calls.ALLOWANCE_PATH).write_text(json.dumps(policy), encoding="utf-8")
    return comment


class TheAllowanceIsVerifiedNotMerelyPresent(unittest.TestCase):

    def refused(self, reason, **fixture):
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory, **fixture)
            with self.assertRaisesRegex(ValueError, reason):
                calls.model_allowance(repo_root=Path(directory))

    def test_there_is_none_today(self):
        self.assertFalse((ROOT / calls.ALLOWANCE_PATH).exists())
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_ALLOWANCE_NOT_GRANTED:" + calls.ALLOWANCE_PATH):
            calls.model_allowance()

    def test_a_well_formed_one_is_read_and_github_is_what_proves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            comment = fixture_tree(directory)
            offline = calls.model_allowance(repo_root=Path(directory))
            self.assertFalse(offline["provenance_verified_against_github"])
            fetched = calls.model_allowance(repo_root=Path(directory),
                                            delegation_reader=lambda path: comment)
            self.assertTrue(fetched["provenance_verified_against_github"])
            changed = {**comment, "body": comment["body"].replace('"D04"', '"D04" ')}
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_SAVED_DELEGATION_DIFFERS_FROM_GITHUB"):
                calls.model_allowance(repo_root=Path(directory),
                                      delegation_reader=lambda path: changed)

    def test_another_requirement(self):
        self.refused("ISSUE_47_MODEL_ALLOWANCE_IS_FOR_ANOTHER_REQUIREMENT",
                     policy_overrides={"requirement_id": "issue_28_v14"})

    def test_a_model_allowance_grants_no_sec_request(self):
        self.refused("ISSUE_47_MODEL_ALLOWANCE_LIMITS_MALFORMED",
                     policy_overrides={"maximum_additional_provider_paid_sec_calls": [4, 4, 1]})
        self.refused("ISSUE_47_MODEL_ALLOWANCE_LIMITS_MALFORMED",
                     policy_overrides={"maximum_additional_provider_paid_sec_calls": [4, 3, 0]})

    def test_the_transport_is_the_fixed_one(self):
        self.refused("ISSUE_47_MODEL_TRANSPORT_IS_NOT_THE_FIXED_ONE",
                     policy_overrides={"transport": {**TRANSPORT,
                                                     "endpoint_host": "api.example.invalid"}})
        self.refused("ISSUE_47_MODEL_TRANSPORT_IS_NOT_THE_FIXED_ONE",
                     policy_overrides={"transport": {**TRANSPORT, "retry_count": 1}})
        self.refused("ISSUE_47_MODEL_RETRY_POLICY_CHANGED",
                     policy_overrides={"retry_policy": {**calls.FIXED_RETRY_POLICY,
                                                        "http_402_stops_batch": False}})

    def test_only_a_wired_metric_and_the_one_purpose(self):
        self.refused("ISSUE_47_MODEL_SCOPE_NAMES_AN_UNWIRED_METRIC:B13",
                     policy_overrides={"scope": scope(metric="B13")})
        self.refused("ISSUE_47_MODEL_SCOPE_PURPOSE_IS_NOT_THE_ONE",
                     policy_overrides={"scope": {**scope(), "purposes": ["ANYTHING"]}})

    def test_the_envelope_is_nothing_but_its_grants(self):
        wide = {**scope(), "earliest_report_end": "2021-12-31"}
        self.refused("ISSUE_47_MODEL_ENVELOPE_WIDER_THAN_ITS_GRANTS:window",
                     policy_overrides={"scope": wide})
        outside = scope()
        outside["grants"] = [{**outside["grants"][0], "latest_report_end": "2025-12-31"}]
        self.refused("ISSUE_47_MODEL_GRANT_OUTSIDE_THE_ENVELOPE", policy_overrides={"scope": outside})

    def test_the_ledger_root_is_its_own(self):
        from vnext.continuous_call_policy import POLICY_PATH
        issue_28 = json.loads((ROOT / POLICY_PATH).read_text())["budget_root"]
        self.refused("ISSUE_47_BUDGET_ROOT_OVERLAPS_ISSUE_28_S", budget_root=issue_28)
        self.refused("ISSUE_47_BUDGET_ROOT_INSIDE_THE_CHECKOUT", budget_root=str(ROOT / "ledger"))
        self.refused("ISSUE_47_BUDGET_ROOT_NOT_AN_ABSOLUTE_PATH", budget_root="relative/ledger")
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory, budget_root="/var/lib/issue47/sec/model")
            (Path(directory) / "config/issue47_historical_calls_v1.json").write_text(
                json.dumps({"budget_root": "/var/lib/issue47/sec"}), encoding="utf-8")
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_LEDGER_OVERLAPS_THE_SEC_LEDGER"):
                calls.model_allowance(repo_root=Path(directory))

    def test_the_approval_must_say_what_the_policy_grants(self):
        self.refused("ISSUE_47_MODEL_DELEGATION_BODY_DOES_NOT_MATCH", digest="0" * 64)
        self.refused("ISSUE_47_MODEL_ALLOWANCE_WIDENS_THE_APPROVED_GRANT:scope",
                     body_overrides={"scope": scope(metric="D04") | {"company_ids": ["x"]}})
        self.refused("ISSUE_47_MODEL_DELEGATION_MUST_NOT_AUTHORIZE_PRODUCTION",
                     body_overrides={"production_authorized": True})
        self.refused("ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER",
                     comment_overrides={"user": {"login": "someone-else"}})

    def test_a_request_outside_every_grant(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory)
            allowance = calls.model_allowance(repo_root=Path(directory))
        self.assertEqual(["TEST"], calls.request_in_scope(
            allowance=allowance, metric_id="D04", company_id="marriott_international",
            report_end="2023-12-31"))
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_REQUEST_OUTSIDE_EVERY_GRANT:D04:"
                                    "marriott_international:2024-12-31"):
            calls.request_in_scope(allowance=allowance, metric_id="D04",
                                   company_id="marriott_international", report_end="2024-12-31")


class TheLedgerCountsEveryClaimAndStopsWhereItCannotTrustTheCount(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        fixture_tree(self.directory.name, policy_overrides={
            "maximum_additional_provider_paid_sec_calls": [2, 2, 0]})
        self.allowance = calls.model_allowance(repo_root=Path(self.directory.name))
        self.ledger = calls.recorded_model_ledger(root=Path(self.directory.name) / "ledger",
                                                  allowance=self.allowance)

    def claim(self, digest):
        return self.ledger.claim(request_digest=digest, plan_id="plan-" + digest,
                                 purpose=calls.PURPOSE, grants=["TEST"], request_identity="r",
                                 authority_files_hash="sha256:" + "0" * 64)

    def finish(self, path, intent, stop=""):
        body = {"record_type": "ISSUE_47_HISTORICAL_MODEL_CALL_TERMINAL",
                "intent_id": intent["intent_id"], "status": "SUCCEEDED" if not stop else "FAILED",
                "stop_reason": stop, "counts": [1, 1, 0], "counts_kind": "RECORDED_TEST_SIMULATION",
                "execution_receipt_id": "e", "evidence": {}, "production_authorized": False}
        calls._write_once(path / "terminal.json", {**body, "terminal_id": content_hash(value=body)})

    def test_a_claim_needs_the_lock(self):
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_LOCK_REQUIRED"):
            self.claim("sha256:" + "1" * 64)

    def test_counts_are_cumulative_and_a_request_is_never_redrawn(self):
        with self.ledger.locked():
            first = self.claim("sha256:" + "1" * 64)
            self.finish(*first)
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_REQUEST_ALREADY_CLAIMED_NO_REDRAW"):
                self.claim("sha256:" + "1" * 64)
            self.finish(*self.claim("sha256:" + "2" * 64))
            self.assertEqual([2, 2, 0], self.ledger.snapshot()["counts"])
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        r"ISSUE_47_MODEL_CUMULATIVE_LIMIT_REACHED:\[2, 2, 0\]"):
                self.claim("sha256:" + "3" * 64)

    def test_a_slot_without_a_terminal_counts_and_stops(self):
        with self.ledger.locked():
            self.claim("sha256:" + "1" * 64)
            state = self.ledger.snapshot()
            self.assertEqual([1, 1, 0], state["counts"])
            self.assertEqual(["0001=UNKNOWN_PENDING_RECONCILIATION"], state["stopped"])
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_CHANNEL_STOPPED:0001"):
                self.claim("sha256:" + "2" * 64)

    def test_every_stop_reason_stops(self):
        for reason in sorted(calls.STOPS):
            with self.subTest(reason=reason):
                ledger = calls.recorded_model_ledger(
                    root=Path(self.directory.name) / ("ledger-" + reason), allowance=self.allowance)
                self.ledger = ledger
                with ledger.locked():
                    self.finish(*self.claim("sha256:" + "1" * 64), stop=reason)
                    with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                                "ISSUE_47_MODEL_CHANNEL_STOPPED:0001=" + reason):
                        self.claim("sha256:" + "2" * 64)

    def test_a_changed_slot_is_refused(self):
        with self.ledger.locked():
            path, intent = self.claim("sha256:" + "1" * 64)
            self.finish(path, intent)
        (path / "intent.json").chmod(0o600)
        (path / "intent.json").write_text(json.dumps({**intent, "purpose": "OTHER"}))
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_SLOT_CHANGED:0001"):
            self.ledger.snapshot()

    def test_a_recorded_ledger_is_never_the_granted_one_or_in_the_checkout(self):
        granted = Path(self.allowance["budget_root"])
        for root in (granted, granted / "inside", granted.parent, ROOT / "ledger"):
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_TEST_CANNOT_USE_A_GRANTED_OR_CHECKOUT_LEDGER"):
                calls.recorded_model_ledger(root=root, allowance=self.allowance)


class NothingHereReachesAProvider(unittest.TestCase):
    """The state today: the patch is not applied, so every path to the socket is closed."""

    def test_the_controller_makes_no_issue_47_authority(self):
        from vnext.requirement_profile import RequirementProfileError
        from vnext.requirements import RequirementError
        with self.assertRaises((control.InvocationControlError, RequirementError,
                                RequirementProfileError)):
            control.prepare_successor_invocation_authority(repo_root=ROOT,
                                                           requirement_id=calls.REQUIREMENT_ID)

    def test_the_adapter_hands_no_bytes_to_this_request_type(self):
        policy = adapter.TransportPolicy.from_mapping(value=dict(TRANSPORT))
        request = calls.HistoricalSemanticRequest(calls._FACTORY, "c", "D04", "2023-12-31", {},
                                                  b"{}", b"{}", b"{}", b"{}", None, {}, ROOT)
        self.assertIsNone(adapter._scoped_transport_payload(policy=policy,
                                                            prepared_request=request))
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_REQUEST_TYPE_REQUIRED"):
            calls.transport_payload(request=object(), policy=policy)

    def test_the_gate_passes_with_this_module_present(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from check_provider_egress import _CallVisitor, check_provider_egress
        self.assertEqual("PASS", check_provider_egress(repo_root=ROOT)["status"])
        visitor = _CallVisitor(relative_path="scripts/vnext/historical_model_calls.py")
        visitor.visit(ast.parse((ROOT / "scripts/vnext/historical_model_calls.py").read_text()))
        self.assertEqual(([], [], [], []), (visitor.transport_factories,
                                            visitor.capability_references,
                                            visitor.provider_host_literals, visitor.opener_calls))

    def test_the_live_path_refuses_here_with_or_without_the_sealed_verification(self):
        """No receipt: refused as missing. A receipt: it describes a patched tree, not this one.

        The receipt is sealed by the harness in a scratch tree after the whole
        suite and every fault injection pass; until it is committed the live
        path must refuse for its absence, and once it is, for this tree not
        being the one it verified. Either way the live path does not open here.
        """
        if not (ROOT / RECEIPT).is_file():
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_WIRING_RECEIPT_MISSING:" + RECEIPT):
                calls.verify_model_wiring(receipt_path=RECEIPT)
            return
        receipt = json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))
        self.assertTrue(receipt["all_checks_passed"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, receipt["calls"])
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_WIRING_FILE_(CHANGED|MISSING):"):
            calls.verify_model_wiring(receipt_path=RECEIPT)
        # What it binds that this tree has unchanged is exactly what the
        # repository carries: this module, the harness and the patch itself.
        # Everything else is either new in the patch or changed by it.
        same = sorted(relative for relative, binding in receipt["bound_files"].items()
                      if (ROOT / relative).is_file()
                      and {"sha256": sha256_bytes(content=(ROOT / relative).read_bytes()),
                           "size": (ROOT / relative).stat().st_size} == binding)
        self.assertEqual(sorted(["scripts/vnext/historical_model_calls.py",
                                 "docs/evidence/issue47_history/model-egress/verify.py",
                                 "docs/evidence/issue47_history/model-egress/"
                                 "egress-registration.patch"]), same)

    def test_the_patch_still_applies_to_this_tree(self):
        import subprocess
        run = subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(0, run.returncode, run.stderr)


if __name__ == "__main__":
    unittest.main()
