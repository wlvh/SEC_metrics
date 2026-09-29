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
import re
import sys
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import ai_adapter as adapter
from vnext import historical_model_calls as calls
from vnext import invocation_control as control
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes

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
               "user": {"login": "wlvh", "id": 30534800, "type": "User"},
               "author_association": "OWNER", "performed_via_github_app": None, "body": text,
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
        """The first review's case: [4,4,0] shown first, a duplicate [400,400,0] granted as the larger.

        Built so that last-key-wins reading would accept it - the later value
        is the one the rest of the files agree with - which makes the strict
        reading the only thing that refuses. The previous version of this case
        appended a value the restatement check refused anyway, and a re-review
        found it passed with the strict reading removed.
        """
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory)
            path = Path(directory) / calls.ALLOWANCE_PATH
            text = path.read_text(encoding="utf-8")
            path.write_text('{"maximum_additional_provider_paid_sec_calls": [400, 400, 0], ' + text[1:],
                            encoding="utf-8")
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_ALLOWANCE_NOT_STRICT_JSON"):
                calls.model_allowance(repo_root=Path(directory))
        with tempfile.TemporaryDirectory() as directory:
            comment = fixture_tree(directory, policy_overrides={
                "maximum_additional_provider_paid_sec_calls": [400, 400, 0]})
            body = '{"maximum_additional_provider_paid_sec_calls": [4, 4, 0], ' + comment["body"][1:]
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

    def test_the_approval_is_the_approver_s_own_post(self):
        """An independent review found only the login was read: another account's, a bot's or an app's passed."""
        for overrides, reason in (
                ({"user": {"login": "wlvh", "id": 1, "type": "User"}},
                 "ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER"),
                ({"user": {"login": "wlvh", "id": 30534800, "type": "Bot"}},
                 "ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER"),
                ({"author_association": "NONE"}, "ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER"),
                ({"performed_via_github_app": {"slug": "claude"}},
                 "ISSUE_47_MODEL_APPROVAL_WAS_POSTED_THROUGH_AN_APP")):
            with self.subTest(overrides=overrides):
                self.refused(reason, comment_overrides=overrides)
        # A record that does not say how it was posted says nothing about it.
        with tempfile.TemporaryDirectory() as directory:
            fixture_tree(directory)
            record = Path(directory) / RECORD
            saved = json.loads(record.read_text(encoding="utf-8"))
            del saved["performed_via_github_app"]
            record.write_text(json.dumps(saved), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ISSUE_47_MODEL_APPROVAL_WAS_POSTED_THROUGH_AN_APP"):
                calls.model_allowance(repo_root=Path(directory))

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
        # Laid out over many lines, as the real proposal is, so a browser's
        # line breaks land inside the record and not only after it (an
        # independent review found these cases ran on a one-line body).
        comment = {**comment, "body": json.dumps(json.loads(comment["body"]), indent=1,
                                                 sort_keys=True)}
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
        # The ledger a Run accepts LIVE registrations from is written here, from
        # the verified allowance, and nowhere else.
        from vnext import historical_counted_calls as counted
        self.assertIn(counted.GRANTED_LEDGER_PATH, registered["written"])
        self.assertEqual(counted.granted_ledger_record(allowance), json.loads(
            (self.root / counted.GRANTED_LEDGER_PATH).read_text(encoding="utf-8")))

    def test_a_post_that_is_not_the_proposal_is_refused(self):
        # Anything but the line breaks a browser adds and whitespace after the
        # record: a character appended, the text indented differently, a lone CR.
        body = self.comment["body"]
        for changed in (body + " x", "\n" + body, body.replace("\n", "\r", 1)
                        if "\n" in body else body.replace(" ", "  ", 1)):
            with self.subTest(changed=changed[:40]):
                with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                            "ISSUE_47_MODEL_POSTED_BODY_IS_NOT_THE_PROPOSED_TEXT"):
                    self.register({**self.comment, "body": changed})
                self.assertFalse((self.root / calls.ALLOWANCE_PATH).exists())

    def test_a_proposal_pasted_into_the_web_page_registers(self):
        """A browser may send CRLF line breaks and a trailing newline; the record is the same."""
        self.assertGreater(self.comment["body"].count("\n"), 5, "line breaks inside the record")
        pasted = {**self.comment, "body": self.comment["body"].replace("\n", "\r\n") + "\r\n"}
        registered = self.register(pasted)
        self.assertEqual("MODEL_APPROVAL_REGISTERED", registered["status"])
        allowance = calls.model_allowance(repo_root=self.root, delegation_reader=lambda path: pasted)
        self.assertTrue(allowance["provenance_verified_against_github"])

    def test_a_post_by_someone_else_or_edited_is_refused(self):
        for overrides, reason in (({"user": {"login": "someone-else"}},
                                   "ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER"),
                                  ({"updated_at": "2026-09-28T00:00:00Z"},
                                   "ISSUE_47_DELEGATION_COMMENT_WAS_EDITED"),
                                  ({"performed_via_github_app": {"slug": "claude"}},
                                   "ISSUE_47_MODEL_APPROVAL_WAS_POSTED_THROUGH_AN_APP")):
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
        # Named here rather than read from STOPS: a re-review removed a reason
        # from STOPS and this case, iterating STOPS, could not notice.
        expected = {"HTTP_402", "UNKNOWN_REMOTE_OUTCOME", "SOURCE_AUTHENTICITY_FAILED", "USAGE_UNKNOWN",
                    "CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT", "TRANSPORT_OBSERVATION_CHANGED",
                    "APPROVAL_NOT_CONFIRMED_ON_GITHUB"}
        self.assertEqual(expected, set(calls.STOPS))
        for reason in sorted(expected):
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
                calls.HistoricalModelCallError, "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR"):
            self.ledger.snapshot()

    def test_emptying_the_root_refuses_rather_than_resetting_the_count(self):
        """A re-review removed the slots and the claim log together, kept binding and anchor: [0, 0, 0]."""
        import shutil
        self.stopped()
        shutil.rmtree(self.ledger.root / "calls")
        (self.ledger.root / "claims.jsonl").unlink()
        with self.ledger.locked(), self.assertRaisesRegex(
                calls.HistoricalModelCallError,
                "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR:0 in the root, 1 beside it"):
            self.ledger.snapshot()

    def reseal(self, path, intent, **changes):
        """Rewrite one claim everywhere it is recorded - slot, log and its copy - under a new seal."""
        body = {**{key: value for key, value in intent.items() if key != "intent_id"}, **changes}
        changed = {**body, "intent_id": content_hash(value=body)}
        (path / "intent.json").chmod(0o600)
        (path / "intent.json").write_bytes(canonical_json_bytes(value=changed))
        line = canonical_json_bytes(value=changed).rstrip(b"\n") + b"\n"
        for log in (self.ledger.root / "claims.jsonl",
                    calls.HistoricalModelLedger.mirror_path(self.ledger.root)):
            lines = log.read_bytes().splitlines(keepends=True)
            lines[intent["ordinal"] - 1] = line
            log.write_bytes(b"".join(lines))
        return changed

    def test_the_claims_must_name_each_other_in_order(self):
        """A claim rewritten to follow another - consistently in all three places - breaks the chain."""
        with self.ledger.locked():
            self.finish(*self.claim("sha256:" + "1" * 64))
            path, intent = self.claim("sha256:" + "2" * 64)
        self.reseal(path, intent, previous_intent_id="sha256:" + "0" * 64)
        with self.ledger.locked(), self.assertRaisesRegex(
                calls.HistoricalModelCallError, "ISSUE_47_MODEL_LEDGER_SLOT_CHANGED:0002"):
            self.ledger.snapshot()

    def test_an_edited_binding_or_anchor_is_refused(self):
        self.stopped()
        for path, reason in ((self.ledger.root / "binding.json", "ISSUE_47_MODEL_LEDGER_BINDING_CHANGED"),
                             (calls.HistoricalModelLedger.anchor_path(self.ledger.root),
                              "ISSUE_47_MODEL_LEDGER_INITIALIZATION_ANCHOR_CHANGED")):
            with self.subTest(file=path.name):
                saved = path.read_bytes()
                path.chmod(0o600)
                path.write_bytes(canonical_json_bytes(value={**json.loads(saved), "limits": [99, 99, 0]}))
                try:
                    with self.assertRaisesRegex(calls.HistoricalModelCallError, reason):
                        with self.ledger.locked():
                            pass
                finally:
                    path.write_bytes(saved)

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
                                    "ISSUE_47_MODEL_WIRING_(FILE_CHANGED|FILE_MISSING|"
                                    "DOES_NOT_BIND_THE_CALL_PATH)"):
            calls.verify_model_wiring(receipt_path=RECEIPT, receipt_id=receipt["receipt_id"])
        # What makes it refuse here is the patch: every bound file the patch
        # creates or changes differs in this unpatched tree. A bound file the
        # repository carries may match the receipt or not - it stops matching
        # when it changes after the seal, and then the receipt must be sealed
        # again before any call, which the refusal above already enforces. The
        # previous form of this case asserted the exact unchanged set and so
        # failed on every repository change between two seals.
        touched = set(re.findall(r"^\+\+\+ b/(\S+)", PATCH.read_text(encoding="utf-8"), re.M))
        bound_and_patched = sorted(touched & set(receipt["bound_files"]))
        self.assertTrue(bound_and_patched)
        for relative in bound_and_patched:
            with self.subTest(relative):
                path = ROOT / relative
                self.assertFalse(path.is_file() and {
                    "sha256": sha256_bytes(content=path.read_bytes()),
                    "size": path.stat().st_size} == receipt["bound_files"][relative],
                    "a file the patch creates or changes matches the patched tree's bytes here")

    def test_the_patch_still_applies_to_this_tree(self):
        import subprocess
        run = subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(0, run.returncode, run.stderr)



class TheModelLedgerStartsOnceAndOnlyItsOwnMarkerCounts(unittest.TestCase):
    """The model ledger's start: the same mechanism as the SEC ledger's, never the same record.

    The owner decided the model calls run in the executor's cloud container
    too, so the model ledger is started once like the SEC ledger
    (historical_ledger_start). The two ledgers spend two different approvals;
    a marker or an export of one must not start, block or stand in for the
    other, even for the same approval digest.
    """

    URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5800000002"

    def setUp(self):
        from unittest.mock import patch
        self.root = Path(tempfile.mkdtemp(prefix="issue47-model-start-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        self.allowance = {"requirement_id": calls.REQUIREMENT_ID,
                          "budget_root": str(self.root / "ledger"),
                          "delegation_url": self.URL, "delegation_body_sha256": "c" * 64,
                          "scope": {"grants": [{"grant": "G1", "request_digests": [
                              "sha256:" + "a" * 64, "sha256:" + "b" * 64]}]}}
        self.patch = patch

    @staticmethod
    def _reader(comments):
        return lambda path: [dict(item) for item in comments] if "page=1" in path else []

    @staticmethod
    def _comment(body, *, number=5900000101):
        """A marker as the comment list returns it: on issue 47, by the owner's account, unedited."""
        return {"id": number, "author_association": "OWNER", "created_at": "2026-09-29T01:00:00Z",
                "updated_at": "2026-09-29T01:00:00Z", "body": body,
                "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
                "user": {"login": "wlvh", "id": 30534800, "type": "User"},
                "html_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-"
                            + str(number)}

    def _export(self, digest, *, requests=(), claims=b""):
        """An export index of approval ``digest`` in its own directory, claiming ``requests``."""
        directory = self.root / calls.MODEL_EXPORT_DIRECTORY / digest[:16]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / calls.MODEL_EXPORT_INDEX).write_text(json.dumps({
            "execution_mode": "LIVE", "approval": {"delegation_body_sha256": digest},
            "requests": list(requests),
            "archive": {"members": {"root/claims.jsonl": {
                "sha256": __import__("hashlib").sha256(claims).hexdigest(), "size": len(claims)}}}}),
            encoding="utf-8")
        return directory

    def test_the_model_start_writes_a_model_record_and_its_marker_verifies(self):
        started = calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                           checkout=self.root)
        self.assertEqual("ISSUE_47_MODEL_LEDGER_START", started["record"]["record_type"])
        marker = self._comment(started["marker_comment_body"])
        verified = calls.require_published_model_start(allowance=self.allowance,
                                                       reader=self._reader([marker]))
        self.assertEqual(marker["html_url"], verified["marker_url"])

    def test_an_sec_marker_neither_starts_nor_blocks_the_model_ledger(self):
        from vnext import historical_sec_session as session
        sec_allowance = {**self.allowance, "budget_root": str(self.root / "sec-ledger")}
        model_allowance = {**self.allowance, "budget_root": str(self.root / "model-ledger")}
        sec = session.start_ledger(allowance=sec_allowance, reader=lambda path: [],
                                   checkout=self.root)
        sec_marker = self._comment(sec["marker_comment_body"])
        # The SEC marker is for the same approval digest, and still it is not
        # the model ledger's: no model start is published, and one can be made.
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_NOT_STARTED"):
            calls.require_published_model_start(allowance=model_allowance,
                                                 reader=self._reader([sec_marker]))
        started = calls.start_model_ledger(allowance=model_allowance,
                                           reader=self._reader([sec_marker]), checkout=self.root)
        # And the model marker does not stand in for the SEC start.
        with self.assertRaisesRegex(ValueError, "ISSUE_47_SEC_LEDGER_START_NOT_PUBLISHED"):
            session.require_published_start(
                allowance=sec_allowance,
                reader=self._reader([self._comment(started["marker_comment_body"])]))
        # A start record of the other ledger's kind at a root is not this one's.
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_START_RECORD_IS_FOR_ANOTHER_APPROVAL"):
            calls.require_published_model_start(allowance=sec_allowance,
                                                 reader=self._reader([sec_marker]))

    def test_only_the_model_export_blocks_a_model_start(self):
        from vnext import historical_sec_session as session
        self._export("c" * 64)
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_ALREADY_EXPORTED"):
            calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                     checkout=self.root)
        # The SEC ledger reads its own export index, not this one.
        self.assertEqual("LEDGER_START_WRITTEN", session.start_ledger(
            allowance=self.allowance, reader=lambda path: [], checkout=self.root)["status"])

    def test_the_live_ledger_reads_the_host_s_reader_and_checks_the_start_last(self):
        """Allowance, wiring, then the start - before the ledger exists or anything is sent."""
        from vnext import historical_source_acquisition as gate
        asked = []

        def reader(path):
            asked.append(path)
            return []

        order = []
        with self.patch.object(gate, "live_github_reader", return_value=reader), \
                self.patch.object(calls, "model_allowance",
                                  side_effect=lambda **kw: order.append("allowance")
                                  or {**self.allowance, "model_wiring_receipt_path": "r",
                                      "model_wiring_receipt_id": "i"}), \
                self.patch.object(calls, "verify_model_wiring",
                                  side_effect=lambda **kw: order.append("wiring")), \
                self.patch.object(calls, "_ledger", side_effect=AssertionError("ledger built")):
            with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                        "ISSUE_47_MODEL_LEDGER_NOT_STARTED"):
                calls.live_model_ledger()
        self.assertEqual(["allowance", "wiring"], order)
        self.assertTrue(asked and all("/issues/47/comments?" in path for path in asked))


    def test_the_marker_does_not_carry_what_the_local_record_needs(self):
        """A marker copied back beside an empty root is not this host's start.

        An independent review copied a marker that carried the whole record,
        random number included, back beside an empty root on a new host, and
        the start matched. The marker now carries the record without its
        number and a digest of the whole.
        """
        from vnext.historical_ledger_start import marker_record, start_record_path
        started = calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                           checkout=self.root)
        marker = self._comment(started["marker_comment_body"])
        published = marker_record(calls._model_start(), marker["body"])
        local = json.loads(start_record_path(self.root / "ledger").read_text(encoding="utf-8"))
        self.assertNotIn("instance_nonce", published)
        self.assertNotIn("instance_nonce", started["record"])
        self.assertNotIn(local["instance_nonce"], started["marker_comment_body"])
        # The new host writes what the marker shows, and adds any number: no match.
        start_record_path(self.root / "ledger").unlink()
        copied = {**{k: v for k, v in published.items() if k != "start_record_sha256"},
                  "instance_nonce": "0" * 32}
        start_record_path(self.root / "ledger").write_text(json.dumps(copied), encoding="utf-8")
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_STARTED_ELSEWHERE"):
            calls.require_published_model_start(allowance=self.allowance,
                                                 reader=self._reader([marker]), checkout=self.root)

    def test_a_ledger_behind_its_export_is_refused(self):
        """The branch's export says more was claimed than this ledger holds: not the exported ledger."""
        from vnext.historical_ledger_start import start_record_path
        started = calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                           checkout=self.root)
        marker = self._comment(started["marker_comment_body"])
        claims = b'{"n":1}\n{"n":2}\n'
        self._export("c" * 64, requests=["sha256:" + "a" * 64], claims=claims)
        ledger = self.root / "ledger"
        for held in (None, claims[:8]):
            with self.subTest(held=held):
                if held is not None:
                    ledger.mkdir(exist_ok=True)
                    (ledger / "claims.jsonl").write_bytes(held)
                with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                            "ISSUE_47_MODEL_LEDGER_BEHIND_ITS_EXPORT"):
                    calls.require_published_model_start(
                        allowance=self.allowance, reader=self._reader([marker]),
                        checkout=self.root)
        # The exported log, and one that goes on past it, are this ledger.
        for held in (claims, claims + b'{"n":3}\n'):
            (ledger / "claims.jsonl").write_bytes(held)
            self.assertTrue(start_record_path(ledger).is_file())
            self.assertEqual(marker["html_url"], calls.require_published_model_start(
                allowance=self.allowance, reader=self._reader([marker]),
                checkout=self.root)["marker_url"])
        # A log that begins otherwise is not.
        (ledger / "claims.jsonl").write_bytes(b'{"n":9}\n{"n":2}\n{"n":3}\n')
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_BEHIND_ITS_EXPORT"):
            calls.require_published_model_start(allowance=self.allowance,
                                                 reader=self._reader([marker]), checkout=self.root)

    def test_a_marker_not_from_this_issue_or_account_does_not_count(self):
        started = calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                           checkout=self.root)
        marker = self._comment(started["marker_comment_body"])
        for field, value in (("issue_url", "https://api.github.com/repos/wlvh/SEC_metrics/issues/28"),
                             ("user", {"login": "wlvh", "id": 1, "type": "User"}),
                             ("user", {"login": "wlvh", "id": 30534800, "type": "Bot"})):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                            "ISSUE_47_MODEL_LEDGER_START_NOT_PUBLISHED"):
                    calls.require_published_model_start(
                        allowance=self.allowance, reader=self._reader([{**marker, field: value}]),
                        checkout=self.root)

    def test_a_re_approval_cannot_start_over_requests_another_approval_claimed(self):
        """A re-approval is not a redraw: requests an earlier approval's export claimed stay claimed."""
        self._export("d" * 64, requests=["sha256:" + "b" * 64])
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_GRANTS_REQUESTS_ANOTHER_APPROVAL_CLAIMED:"
                                    "sha256:" + "b" * 64):
            calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                     checkout=self.root)
        # An unreadable export of another approval is not evidence nothing was claimed.
        (self.root / calls.MODEL_EXPORT_DIRECTORY / ("d" * 16) / calls.MODEL_EXPORT_INDEX
         ).write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_ANOTHER_APPROVAL_S_EXPORT_UNREADABLE"):
            calls.start_model_ledger(allowance=self.allowance, reader=self._reader([]),
                                     checkout=self.root)
        # Requests the earlier approval never claimed can be granted again.
        self._export("d" * 64, requests=["sha256:" + "e" * 64])
        self.assertEqual("LEDGER_START_WRITTEN", calls.start_model_ledger(
            allowance=self.allowance, reader=self._reader([]), checkout=self.root)["status"])

    def test_each_approval_exports_into_its_own_directory(self):
        self.assertEqual(calls.MODEL_EXPORT_DIRECTORY + "/" + "c" * 16,
                         calls.model_export_directory(self.allowance))
        self.assertNotEqual(calls.model_export_directory(self.allowance),
                            calls.model_export_directory({"delegation_body_sha256": "d" * 64}))


class TheModelLedgerTravelsToTheBranchAndBack(unittest.TestCase):
    """An export of the model ledger is the ledger, checked by its own snapshot, or nothing.

    The ledger lives in the executor's container, whose disk goes with it, so
    it is exported to the branch after each run. A recorded ledger stands in
    for the granted one here: the archive, the index and the snapshot are the
    same code for both, and a restore - which only a granted LIVE ledger may
    have - is refused for it by name.
    """

    GRANT = {"grant": "G1", "request_digests": ["sha256:" + "a" * 64, "sha256:" + "b" * 64]}

    def setUp(self):
        import shutil
        from vnext import historical_model_export as export
        self.export = export
        self.tmp = Path(tempfile.mkdtemp(prefix="issue47-model-export-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        allowance = {"requirement_id": calls.REQUIREMENT_ID,
                     "budget_root": "/nonexistent-granted-model-root",
                     "maximum_additional_provider_paid_sec_calls": [3, 3, 0],
                     "scope": {"purposes": [calls.PURPOSE], "grants": [self.GRANT]},
                     "delegation_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-1",
                     "delegation_body_sha256": "d" * 64}
        self.allowance = allowance
        self.ledger = calls.recorded_model_ledger(root=self.tmp / "ledger", allowance=allowance)
        with self.ledger.locked():
            self.ledger.claim(request_digest=self.GRANT["request_digests"][0], plan_id="plan-1",
                              purpose=calls.PURPOSE, grants=["G1"], request_identity="request-1",
                              authority_files_hash="sha256:" + "e" * 64)
        self.out = self.tmp / "export"
        self.exported = export.export_model_ledger(ledger=self.ledger, out_dir=self.out)

    def test_an_export_is_the_ledger_and_verifies_from_the_archive_alone(self):
        self.assertEqual([1, 1, 0], self.exported["counts"])
        index = self.export.verify_model_export(export_dir=self.out)
        self.assertEqual(["0001=UNKNOWN_PENDING_RECONCILIATION"], index["stopped"])
        self.assertIsNone(index["approval"], "a recorded ledger names no approval")
        members = set(index["archive"]["members"])
        self.assertIn("root/claims.jsonl", members)
        self.assertIn("root/calls/0001/intent.json", members)
        self.assertIn("beside/claims-mirror.jsonl", members)

    def test_a_changed_archive_or_index_is_refused(self):
        from vnext.historical_source_export import HistoricalExportError
        archive = self.out / self.export.ARCHIVE_NAME
        original = archive.read_bytes()
        archive.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(HistoricalExportError, "ISSUE_47_EXPORT_ARCHIVE_CHANGED"):
            self.export.verify_model_export(export_dir=self.out)
        archive.write_bytes(original)
        index_path = self.out / calls.MODEL_EXPORT_INDEX
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["counts"] = [0, 0, 0]
        index_path.write_text(json.dumps(index), encoding="utf-8")
        with self.assertRaisesRegex(HistoricalExportError, "ISSUE_47_EXPORT_RECORD_CHANGED"):
            self.export.verify_model_export(export_dir=self.out)

    def test_a_resealed_archive_of_a_truncated_ledger_is_refused_by_the_ledger(self):
        """Hashes that agree with each other are not a ledger; its own snapshot decides."""
        from vnext.historical_source_export import _archive, _binding, _sealed
        index_path = self.out / calls.MODEL_EXPORT_INDEX
        index = json.loads(index_path.read_text(encoding="utf-8"))
        members = self.export._read(self.out)[1]
        members["beside/claims-mirror.jsonl"] = b""
        data = _archive(members)
        (self.out / self.export.ARCHIVE_NAME).write_bytes(data)
        index = {k: v for k, v in index.items() if k != "export_id"}
        index["archive"] = {"name": self.export.ARCHIVE_NAME, **_binding(data),
                            "members": {name: _binding(content)
                                        for name, content in sorted(members.items())}}
        index_path.write_text(json.dumps(_sealed(index, "export_id")), encoding="utf-8")
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR"):
            self.export.verify_model_export(export_dir=self.out)

    def test_an_index_resealed_with_other_counts_is_refused(self):
        from vnext.historical_source_export import _sealed
        index_path = self.out / calls.MODEL_EXPORT_INDEX
        index = {k: v for k, v in json.loads(index_path.read_text(encoding="utf-8")).items()
                 if k != "export_id"}
        index["counts"], index["stopped"] = [0, 0, 0], []
        index_path.write_text(json.dumps(_sealed(index, "export_id")), encoding="utf-8")
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_RESTORE_SNAPSHOT_DIFFERS_FROM_THE_INDEX"):
            self.export.verify_model_export(export_dir=self.out)

    def test_only_a_live_ledger_is_restored(self):
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_RESTORE_ONLY_A_LIVE_LEDGER"):
            self.export.restore_model_ledger(export_dir=self.out)

    def test_an_export_of_a_ledger_never_started_here_is_refused(self):
        """Exporting through a ledger on an empty root would begin one, and write a record of nothing.

        An independent review exported on a host whose ledger was gone: the
        lock initialised a fresh ledger and the export over the record of what
        was spent said [0, 0, 0], and verified.
        """
        fresh = calls.recorded_model_ledger(root=self.tmp / "gone", allowance=self.allowance)
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_EXPORT_OF_A_LEDGER_NEVER_STARTED_HERE"):
            self.export.export_model_ledger(ledger=fresh, out_dir=self.out)
        self.assertFalse((self.tmp / "gone").exists(), "nothing is begun at the root")
        self.assertEqual([1, 1, 0], self.export.verify_model_export(export_dir=self.out)["counts"])

    def test_an_export_only_moves_forward(self):
        # The same ledger again: its log begins with the exported one, so it may replace it.
        self.assertEqual([1, 1, 0], self.export.export_model_ledger(
            ledger=self.ledger, out_dir=self.out)["counts"])
        # A ledger begun again with the same binding and a claim of its own:
        # its log does not begin with the exported one.
        again = calls.recorded_model_ledger(root=self.tmp / "again", allowance=self.allowance)
        with again.locked():
            again.claim(request_digest=self.GRANT["request_digests"][0], plan_id="plan-1",
                        purpose=calls.PURPOSE, grants=["G1"], request_identity="request-1",
                        authority_files_hash="sha256:" + "e" * 64)
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_EXPORT_WOULD_NOT_EXTEND_THE_EXPORT_THERE"):
            self.export.export_model_ledger(ledger=again, out_dir=self.out)
        # An unreadable index there is not one to write over either.
        (self.out / calls.MODEL_EXPORT_INDEX).write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(calls.HistoricalModelCallError,
                                    "ISSUE_47_MODEL_EXPORT_WOULD_NOT_EXTEND_THE_EXPORT_THERE"):
            self.export.export_model_ledger(ledger=self.ledger, out_dir=self.out)

    def test_an_export_never_carries_the_start(self):
        """The start stays with the host that made it; a restore is a record, not a resumption."""
        index = self.export.verify_model_export(export_dir=self.out)
        self.assertFalse(any("start" in name for name in index["archive"]["members"]))

if __name__ == "__main__":
    unittest.main()
