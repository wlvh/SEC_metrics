"""Issue #47's model calls in the repository tree, where the egress patch is not applied.

``historical_model_calls`` holds everything a #47 model call would be bound to
except the socket. What is proven here, without the patch:

* the allowance is verified rather than merely present, the same three layers
  as the SEC allowance, plus the model-specific rules - one call is one
  provider and one paid call, never an SEC request; the transport is the fixed
  one; only wired metrics may be granted; the ledger root overlaps neither
  #28's, the checkout nor #47's SEC ledger;
* the ledger counts every claim, never redraws a request, stops on a slot
  without a terminal and on the stop reasons, and refuses a changed slot; a
  stop is recomputed from the slot's own evidence, and a count or a stop
  cannot be released by deleting a slot, the claim log or the whole root;
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


# The requests the fixture grant names: the digests the ledger cases claim.
GRANTED = ["sha256:" + digit * 64 for digit in "123"]


def scope(first="2023-12-31", last="2023-12-31", metric="D04", digests=None):
    return {"purposes": [calls.PURPOSE], "metric_ids": [metric],
            "company_ids": ["marriott_international"], "earliest_report_end": first,
            "latest_report_end": last,
            "grants": [{"grant": "TEST", "metric_ids": [metric],
                        "company_ids": ["marriott_international"],
                        "earliest_report_end": first, "latest_report_end": last,
                        "request_digests": list(digests or GRANTED)}]}


def fixture_tree(directory, *, policy_overrides=None, body_overrides=None, comment_overrides=None,
                 digest=None, budget_root="/var/lib/issue47-model-ledger-test"):
    """A temporary root holding a model allowance and its approval record."""
    root = Path(directory)
    policy = {"requirement_id": calls.REQUIREMENT_ID, "repository": "wlvh/SEC_metrics",
              "approver_login": "wlvh", "delegation_url": URL, "delegation_record_path": RECORD,
              "budget_root": budget_root, "maximum_additional_provider_paid_sec_calls": [4, 4, 0],
              "scope": scope(), "transport": dict(TRANSPORT),
              "retry_policy": dict(calls.FIXED_RETRY_POLICY), "model_wiring_receipt_path": RECEIPT,
              "model_wiring_receipt_id": "sha256:" + "1" * 64}
    policy.update(policy_overrides or {})
    body = {"record_type": calls.DELEGATION_TYPE, "requirement_id": calls.REQUIREMENT_ID,
            "fixture": "RECORDED_TEST_ONLY_NOT_AN_APPROVAL", "production_authorized": False,
            **{field: policy[field] for field in calls.RESTATED_BY_THE_COMMENT}}
    body.update(body_overrides or {})
    text = json.dumps(body, sort_keys=True)
    comment = {"id": 1000000001, "html_url": URL,
               "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
               "user": {"login": "wlvh"}, "body": text,
               "created_at": "2026-09-27T00:00:00Z", "updated_at": "2026-09-27T00:00:00Z",
               **(comment_overrides or {})}
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

    def test_a_duplicate_key_is_refused_not_resolved_last_wins(self):
        """An independent review had [4,4,0] followed by a duplicate [400,400,0] granted as the larger."""
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory)
            path = Path(directory) / calls.ALLOWANCE_PATH
            text = path.read_text(encoding="utf-8")
            path.write_text(text[:-1] + ', "maximum_additional_provider_paid_sec_calls": [400, 400, 0]}',
                            encoding="utf-8")
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_ALLOWANCE_NOT_STRICT_JSON"):
                calls.model_allowance(repo_root=Path(directory))
        with tempfile.TemporaryDirectory() as directory:
            comment = fixture_tree(directory)
            body = comment["body"][:-1] + ', "maximum_additional_provider_paid_sec_calls": [400, 400, 0]}'
            (Path(directory) / RECORD).write_text(json.dumps({**comment, "body": body}), encoding="utf-8")
            policy_path = Path(directory) / calls.ALLOWANCE_PATH
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["delegation_body_sha256"] = sha256_bytes(content=body.encode("utf-8"))
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_DELEGATION_BODY_IS_NOT_A_RECORD"):
                calls.model_allowance(repo_root=Path(directory))

    def test_an_edited_approval_comment_is_refused(self):
        """An approval is what was posted; an edit is a new decision and needs a new comment."""
        self.refused("ISSUE_47_DELEGATION_COMMENT_WAS_EDITED:saved_record",
                     comment_overrides={"updated_at": "2026-09-28T00:00:00Z"})
        with tempfile.TemporaryDirectory() as directory:
            comment = fixture_tree(directory)
            edited = {**comment, "updated_at": "2026-09-28T00:00:00Z"}
            with self.assertRaisesRegex(ValueError, "ISSUE_47_DELEGATION_COMMENT_WAS_EDITED:fetched"):
                calls.model_allowance(repo_root=Path(directory), delegation_reader=lambda path: edited)

    def test_the_sec_ledger_root_respelt_is_still_the_sec_ledger_root(self):
        """Compared as directories - real paths, casefolded, both ways - not as strings."""
        with tempfile.TemporaryDirectory() as outside:
            sec_root = Path(outside) / "issue47-sec-ledger"
            sec_root.mkdir()
            alias = Path(outside) / "issue47-sec-alias"
            alias.symlink_to(sec_root)
            for spelling in (str(alias), str(sec_root).upper(), str(sec_root) + "/model"):
                with self.subTest(spelling=spelling), tempfile.TemporaryDirectory() as directory:
                    fixture_tree(directory, budget_root=spelling)
                    (Path(directory) / "config/issue47_historical_calls_v1.json").write_text(
                        json.dumps({"budget_root": str(sec_root)}), encoding="utf-8")
                    with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                                "ISSUE_47_MODEL_LEDGER_OVERLAPS_THE_SEC_LEDGER"):
                        calls.model_allowance(repo_root=Path(directory))

    def test_the_approval_must_say_what_the_policy_grants(self):
        self.refused("ISSUE_47_MODEL_DELEGATION_BODY_DOES_NOT_MATCH", digest="0" * 64)
        self.refused("ISSUE_47_MODEL_ALLOWANCE_WIDENS_THE_APPROVED_GRANT:model_wiring_receipt_id",
                     body_overrides={"model_wiring_receipt_id": "sha256:" + "2" * 64})
        self.refused("ISSUE_47_MODEL_ALLOWANCE_FIELD_MALFORMED:model_wiring_receipt_id",
                     policy_overrides={"model_wiring_receipt_id": "not-a-receipt-id"})
        self.refused("ISSUE_47_MODEL_ALLOWANCE_WIDENS_THE_APPROVED_GRANT:scope",
                     body_overrides={"scope": scope(metric="D04") | {"company_ids": ["x"]}})
        self.refused("ISSUE_47_MODEL_DELEGATION_MUST_NOT_AUTHORIZE_PRODUCTION",
                     body_overrides={"production_authorized": True})
        self.refused("ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER",
                     comment_overrides={"user": {"login": "someone-else"}})

    def test_a_grant_names_the_requests_it_allows(self):
        """A grant by position alone let any request built for that position through."""
        base = scope()
        cases = (({key: value for key, value in base["grants"][0].items()
                   if key != "request_digests"}, "ISSUE_47_MODEL_GRANT_FIELDS_NOT_EXACT"),
                 ({**base["grants"][0], "request_digests": []},
                  "ISSUE_47_MODEL_GRANT_REQUEST_DIGESTS_MALFORMED"),
                 ({**base["grants"][0], "request_digests": ["not-a-digest"]},
                  "ISSUE_47_MODEL_GRANT_REQUEST_DIGESTS_MALFORMED"),
                 ({**base["grants"][0], "request_digests": [GRANTED[0], GRANTED[0]]},
                  "ISSUE_47_MODEL_GRANT_REQUEST_DIGESTS_MALFORMED"))
        for grant, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                fixture_tree(directory, policy_overrides={"scope": {**base, "grants": [grant]}})
                with self.assertRaisesRegex(calls.HistoricalModelCallError, reason):
                    calls.model_allowance(repo_root=Path(directory))

    def test_one_request_is_not_named_by_two_grants(self):
        base = scope()
        second = {**base["grants"][0], "grant": "TEST_TWO"}
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory, policy_overrides={"scope": {**base, "grants": [
                base["grants"][0], second]}})
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_GRANT_REQUEST_DIGEST_REPEATS"):
                calls.model_allowance(repo_root=Path(directory))

    def test_a_request_inside_the_position_but_not_named_is_outside(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory)
            allowance = calls.model_allowance(repo_root=Path(directory))
            where = {"allowance": allowance, "metric_id": "D04",
                     "company_id": "marriott_international", "report_end": "2023-12-31"}
            self.assertEqual(["TEST"], calls.request_in_scope(**where))
            self.assertEqual(["TEST"], calls.request_in_scope(**where, request_digest=GRANTED[1]))
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED"):
                calls.request_in_scope(**where, request_digest="sha256:" + "9" * 64)

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


def slot_evidence(path, intent, *, stop=""):
    """Write the three files ``_slot_evidence`` reads, shaped to imply ``stop``."""
    identity = intent["intent_id"].split(":", 1)[1][:24]
    execution_id = "execution:" + identity
    status = "UNKNOWN_REMOTE_OUTCOME" if stop == "UNKNOWN_REMOTE_OUTCOME" else (
        "FAILED" if stop else "SUCCEEDED")
    execution = calls._sealed({"execution_id": execution_id, "status": status,
                               "counters": {"real_model_provider_egress_count": 0,
                                            "paid_model_provider_call_count": 0,
                                            "mock_transport_invocation_count": 1}},
                              "execution_receipt_id")
    marker = calls._sealed({"ai_invocation_plan_id": intent["plan_id"], "execution_id": execution_id,
                            "attempt_ordinal": 1, "transport_kind": "MOCK"}, "egress_marker_id")
    error_class = stop if stop not in ("", "UNKNOWN_REMOTE_OUTCOME", "USAGE_UNKNOWN") else ""
    wire = calls._sealed({"intent_id": intent["intent_id"], "execution_id": execution_id,
                          "mode": "RECORDED_TEST_ONLY", "error_class": error_class,
                          "usage": {"input_tokens": None if stop == "USAGE_UNKNOWN" else 100,
                                    "output_tokens": 20},
                          "raw_response_sha256": None, "assistant_output_sha256": None}, "wire_id")
    calls._write_once(path / "invocation_control" / "executions" / (identity + ".json"), execution)
    calls._write_once(path / "invocation_control" / "egress" / identity / "01.json", marker)
    calls._write_once(path / "wire" / "journal.json", wire)
    return execution, wire


class TheApprovalIsRegisteredFromWhatWasPosted(unittest.TestCase):
    """The owner posts the committed proposal; registration writes the allowance from the post."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        # A fixture tree whose allowance and record are then removed: what is
        # left is the proposal, which is what an owner's checkout holds.
        comment = fixture_tree(self.directory.name)
        (self.root / calls.ALLOWANCE_PATH).unlink()
        (self.root / RECORD).unlink()
        (self.root / calls.APPROVAL_BODY_PATH).parent.mkdir(parents=True, exist_ok=True)
        (self.root / calls.APPROVAL_BODY_PATH).write_text(comment["body"], encoding="utf-8")
        self.comment = comment

    def register(self, comment):
        return calls.register_model_approval(repo_root=self.root, comment_url=URL,
                                             reader=lambda path: comment)

    def test_the_posted_proposal_is_registered_and_checked_by_the_gate(self):
        registered = self.register(self.comment)
        self.assertEqual("MODEL_APPROVAL_REGISTERED", registered["status"])
        self.assertEqual([4, 4, 0], registered["limits"])
        allowance = calls.model_allowance(repo_root=self.root, delegation_reader=lambda path: self.comment)
        self.assertTrue(allowance["provenance_verified_against_github"])
        self.assertEqual(self.register(self.comment)["written"], registered["written"])

    def test_a_post_that_is_not_the_proposal_is_refused(self):
        changed = {**self.comment, "body": self.comment["body"] + " "}
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_POSTED_BODY_IS_NOT_THE_PROPOSED_TEXT"):
            self.register(changed)
        self.assertFalse((self.root / calls.ALLOWANCE_PATH).exists())

    def test_a_post_by_someone_else_or_edited_is_refused(self):
        for overrides, reason in (({"user": {"login": "someone-else"}},
                                   "ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER"),
                                  ({"updated_at": "2026-09-28T00:00:00Z"},
                                   "ISSUE_47_DELEGATION_COMMENT_WAS_EDITED")):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.register({**self.comment, **overrides})
        self.assertFalse((self.root / calls.ALLOWANCE_PATH).exists())

    def test_an_allowance_already_registered_differently_is_not_overwritten(self):
        self.register(self.comment)
        path = self.root / calls.ALLOWANCE_PATH
        path.write_text(path.read_text(encoding="utf-8").replace('"wlvh/SEC_metrics"', '"wlvh/other"'),
                        encoding="utf-8")
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_ALLOWANCE_ALREADY_REGISTERED_DIFFERENTLY"):
            self.register(self.comment)


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
        """Seal a slot through the ledger from evidence that implies ``stop``.

        The ledger reads a stop from the slot's own files - the controller's
        execution receipt, its egress marker and the wire journal - not from a
        terminal a caller writes, so the fixture writes those files and lets
        ``finish`` seal them. They are synthetic (no controller ran here); what
        is tested is that the ledger derives the stop from them.
        """
        execution, wire = slot_evidence(path, intent, stop=stop)
        return self.ledger.finish(path=path, intent=intent, execution=execution, wire=wire)

    def test_a_claim_needs_the_lock(self):
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_LOCK_REQUIRED"):
            self.claim("sha256:" + "1" * 64)

    def test_a_claim_for_a_request_no_grant_names_is_refused(self):
        """The ledger holds the approval's request list, so a caller cannot pass a wider one."""
        with self.ledger.locked():
            for grants in (["TEST"], [], ["OTHER"]):
                with self.subTest(grants=grants), self.assertRaisesRegex(
                        calls.HistoricalModelCallError, "ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED"):
                    self.ledger.claim(request_digest="sha256:" + "9" * 64, plan_id="p",
                                      purpose=calls.PURPOSE, grants=grants, request_identity="r",
                                      authority_files_hash="sha256:" + "0" * 64)
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED"):
                self.ledger.claim(request_digest=GRANTED[0], plan_id="p", purpose=calls.PURPOSE,
                                  grants=["OTHER"], request_identity="r",
                                  authority_files_hash="sha256:" + "0" * 64)
            self.assertEqual([0, 0, 0], self.ledger.snapshot()["counts"])

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
        """An edited intent disagrees with the synced claim log before anything else."""
        with self.ledger.locked():
            path, intent = self.claim("sha256:" + "1" * 64)
            self.finish(path, intent)
        (path / "intent.json").chmod(0o600)
        (path / "intent.json").write_text(json.dumps({**intent, "purpose": "OTHER"}))
        with self.ledger.locked(), self.assertRaisesRegex(
                calls.HistoricalModelCallError, "ISSUE_47_MODEL_LEDGER_CLAIM_CHANGED:0001"):
            self.ledger.snapshot()

    def stopped(self):
        """A ledger whose only slot ended with a stop the evidence implies."""
        with self.ledger.locked():
            path, intent = self.claim("sha256:" + "1" * 64)
            self.finish(path, intent, stop="HTTP_402")
            self.assertEqual(["0001=HTTP_402"], self.ledger.snapshot()["stopped"])
        return path

    def test_deleting_a_stopped_slot_refuses_rather_than_releasing_it(self):
        """An independent review deleted a stopped slot and claimed the same request again."""
        import shutil
        shutil.rmtree(self.stopped())
        with self.ledger.locked(), self.assertRaisesRegex(
                calls.HistoricalModelCallError, "ISSUE_47_MODEL_LEDGER_CLAIM_SET_CHANGED"):
            self.claim("sha256:" + "1" * 64)

    def test_deleting_the_claim_log_refuses_rather_than_forgetting_the_claims(self):
        self.stopped()
        (self.ledger.root / "claims.jsonl").unlink()
        with self.ledger.locked(), self.assertRaisesRegex(
                calls.HistoricalModelCallError, "ISSUE_47_MODEL_LEDGER_CLAIM_SET_CHANGED"):
            self.ledger.snapshot()

    def test_deleting_the_root_refuses_rather_than_resetting_the_count(self):
        """The anchor beside the root is what deleting the root does not take with it."""
        import shutil
        self.stopped()
        shutil.rmtree(self.ledger.root)
        self.assertTrue(calls.HistoricalModelLedger.anchor_path(self.ledger.root).is_file())
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_BINDING_MISSING_OR_RESET"):
            with self.ledger.locked():
                pass

    def test_a_resealed_terminal_that_drops_its_stop_is_refused(self):
        """The stop is recomputed from the slot's evidence, not read from a self-hashed terminal."""
        path = self.stopped()
        terminal = json.loads((path / "terminal.json").read_text())
        body = {**{key: value for key, value in terminal.items() if key != "terminal_id"},
                "stop_reason": ""}
        (path / "terminal.json").chmod(0o600)
        (path / "terminal.json").write_text(json.dumps({**body, "terminal_id": content_hash(value=body)}))
        with self.ledger.locked(), self.assertRaisesRegex(
                calls.HistoricalModelCallError,
                "ISSUE_47_MODEL_LEDGER_TERMINAL_DISAGREES_WITH_ITS_EVIDENCE:0001"):
            self.ledger.snapshot()

    def test_a_ledger_root_reached_through_a_symlink_is_refused(self):
        real = Path(self.directory.name) / "real-ledger"
        real.mkdir()
        alias = Path(self.directory.name) / "alias-ledger"
        alias.symlink_to(real)
        ledger = calls._ledger(allowance=self.allowance, root=alias, live=False)
        with self.assertRaisesRegex(calls.HistoricalModelCallError, "ISSUE_47_MODEL_LEDGER_PATH_ALIAS"):
            with ledger.locked():
                pass

    def test_only_the_open_last_claim_is_a_claimed_slot(self):
        """What a transport's send asks before the socket: this slot is counted and still open."""
        with self.ledger.locked():
            path, intent = self.claim("sha256:" + "1" * 64)
            self.assertTrue(self.ledger.claimed_slot(path=path, intent=intent))
            self.assertFalse(self.ledger.claimed_slot(path=path, intent={**intent, "purpose": "X"}))
            self.assertFalse(self.ledger.claimed_slot(path=path.parent / "0002", intent=intent))
            self.finish(path, intent)
            self.assertFalse(self.ledger.claimed_slot(path=path, intent=intent))
        self.assertFalse(self.ledger.claimed_slot(path=path, intent=intent))

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
                calls.verify_model_wiring(receipt_path=RECEIPT, receipt_id="sha256:" + "0" * 64)
            return
        receipt = json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))
        self.assertTrue(receipt["all_checks_passed"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, receipt["calls"])
        # Named by the approval or not, it does not hold here: a receipt the
        # approval does not name is refused first, and the one it names still
        # describes a patched tree.
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_WIRING_RECEIPT_IS_NOT_THE_APPROVED_ONE"):
            calls.verify_model_wiring(receipt_path=RECEIPT, receipt_id="sha256:" + "0" * 64)
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_WIRING_FILE_(CHANGED|MISSING):"):
            calls.verify_model_wiring(receipt_path=RECEIPT, receipt_id=receipt["receipt_id"])
        # What it binds that this tree has unchanged is exactly what the
        # repository carries: this module, the SEC module whose approval checks
        # it imports and that module's tests (the gh reader's case runs in the
        # harness), the harness and the patch itself. Everything else is
        # either new in the patch or changed by it.
        same = sorted(relative for relative, binding in receipt["bound_files"].items()
                      if (ROOT / relative).is_file()
                      and {"sha256": sha256_bytes(content=(ROOT / relative).read_bytes()),
                           "size": (ROOT / relative).stat().st_size} == binding)
        self.assertEqual(sorted(["scripts/vnext/historical_model_calls.py",
                                 "scripts/vnext/historical_source_acquisition.py",
                                 "tests/vnext/test_historical_source_acquisition.py",
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
