"""A LIVE registration is accepted only with the counted calls that answered it.

An independent re-review found each registration contract accepted
``mode="LIVE"`` from its caller: one function call, no model call, and the
batch's default loader published a withheld E01 window as 3 (N1). The fix
lives in the repository - the three contracts, their consumers and
``historical_counted_calls`` - while the suite that makes real counted calls
needs the egress patch and runs only in a patched tree. These cases hold the
fix where CI runs: E01 and D02 refuse LIVE without counted calls, at
registration and when a record written straight into a journal is read back;
the check every consumer shares refuses a missing block, a changed seal, a
mode or a ledger that is not the registration's, and calls counted in a ledger
no registered approval granted. D04's registration and consumer are held in
``test_historical_semantic_routes``, where a pinned source already exists.
"""
import json
import tempfile
import unittest
from pathlib import Path

from vnext import historical_counted_calls as counted_calls
from vnext import historical_legal_review as legal_review
from vnext import historical_ma_confirmation as confirmation
from vnext.canonical import canonical_json_bytes, content_hash


def _sealed(body, field):
    return {**body, field: content_hash(value=body)}


def _allowance(root, *, grant="G1"):
    """The allowance fields a ledger binding and a granted-ledger record read; nothing else."""
    return {"maximum_additional_provider_paid_sec_calls": [1, 1, 0],
            "scope": {"purposes": ["TEST"],
                      "grants": [{"grant": grant, "request_digests": ["sha256:" + "a" * 64]}]},
            "delegation_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-1",
            "delegation_body_sha256": "b" * 64, "budget_root": str(root),
            "transport": {"provider": "deepseek", "model": "deepseek-flash"},
            "model_wiring_receipt_id": "sha256:" + "c" * 64}


def _block(allowance, *, live=True, mode="LIVE", calls=()):
    binding = counted_calls.ledger_binding(allowance, root=Path(allowance["budget_root"]), live=live)
    return counted_calls.counted_calls(ledger_binding=binding, transport=allowance["transport"],
                                       mode=mode, calls=list(calls))


class ARegistrationCannotSayLiveWithoutItsCalls(unittest.TestCase):
    """At registration, and when a record placed straight into a journal is read back."""

    REQUEST = {"request_id": "sha256:" + "d" * 64, "company_id": "marriott_international"}

    def test_e01_refuses_a_live_confirmation_without_counted_calls(self):
        with self.assertRaisesRegex(ValueError, "E01_LIVE_CONFIRMATION_WITHOUT_COUNTED_CALLS"):
            confirmation.registered_confirmation(request=self.REQUEST, period_selection_id="s",
                                                 output=b"{}", mode="LIVE")

    def test_d02_refuses_a_live_review_without_counted_calls(self):
        with self.assertRaisesRegex(ValueError, "D02_LIVE_REVIEW_WITHOUT_COUNTED_CALLS"):
            legal_review.registered_review(request=self.REQUEST, company_id=self.REQUEST["company_id"],
                                           period_selection_id="s", output=b"{}", mode="LIVE")

    def test_an_e01_record_written_as_live_is_not_read(self):
        """What the review did: a sealed LIVE record placed where the loader looks."""
        record = _sealed({"record_type": confirmation.RECORD_TYPE, "schema_version": 1,
                          "requirement_id": confirmation.REQUIREMENT_ID, "mode": "LIVE",
                          "request_id": self.REQUEST["request_id"], "assistant_output": "{}"},
                         "input_record_id")
        with self.assertRaisesRegex(ValueError, "E01_LIVE_CONFIRMATION_WITHOUT_COUNTED_CALLS"):
            confirmation.validate_registered(record=record, request=self.REQUEST,
                                             period_selection_id="s", mode="LIVE")

    def test_a_d02_record_written_as_live_is_not_read(self):
        record = _sealed({"record_type": legal_review.RECORD_TYPE, "schema_version": 1,
                          "requirement_id": legal_review.REQUIREMENT_ID, "mode": "LIVE",
                          "request_id": self.REQUEST["request_id"],
                          "company_id": self.REQUEST["company_id"], "period_selection_id": "s",
                          "assistant_output": "{}"}, "input_record_id")
        with self.assertRaisesRegex(ValueError, "D02_LIVE_REVIEW_WITHOUT_COUNTED_CALLS"):
            legal_review.select_registered_review(records=[record], request=self.REQUEST)


class TheCheckEveryConsumerSharesHoldsEachPart(unittest.TestCase):
    """Block-level conditions and the granted ledger, without any call."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.allowance = _allowance(self.root / "ledger")

    def tearDown(self):
        self.temporary.cleanup()

    def test_a_live_registration_without_a_block_is_refused(self):
        with self.assertRaisesRegex(ValueError, "ISSUE_47_LIVE_REGISTRATION_WITHOUT_COUNTED_CALLS"):
            counted_calls.check_live_registration(counted=None, answered=[], repo_root=self.root)

    def test_a_block_that_is_not_its_seal_mode_or_ledger_is_refused(self):
        block = _block(self.allowance)
        for name, changed, mode, reason in (
                ("an edited block", {**block, "mode": "RECORDED_TEST_ONLY"}, "RECORDED_TEST_ONLY",
                 "ISSUE_47_COUNTED_CALLS_CHANGED"),
                ("another mode", block, "RECORDED_TEST_ONLY", "ISSUE_47_COUNTED_CALLS_CHANGED"),
                ("a recorded ledger's binding", _block(self.allowance, live=False), "LIVE",
                 "ISSUE_47_COUNTED_CALLS_LEDGER_CHANGED"),
                ("no call", block, "LIVE", "ISSUE_47_COUNTED_CALLS_DO_NOT_ANSWER_EVERY_REQUEST")):
            with self.subTest(name), self.assertRaisesRegex(ValueError, reason):
                counted_calls.check_counted_calls(counted=changed, answered=[], mode=mode)

    def test_calls_only_count_in_the_ledger_a_registered_approval_granted(self):
        block = _block(self.allowance)
        with self.assertRaisesRegex(ValueError, "ISSUE_47_LIVE_REGISTRATION_WITHOUT_A_REGISTERED_APPROVAL"):
            counted_calls.check_granted(counted=block, repo_root=self.root)
        granted = self.root / counted_calls.GRANTED_LEDGER_PATH
        granted.parent.mkdir(parents=True)
        for name, allowance, reason in (
                ("another grant", _allowance(self.root / "ledger", grant="G2"),
                 "ISSUE_47_LIVE_REGISTRATION_IS_FROM_A_LEDGER_NO_REGISTERED_APPROVAL_GRANTED"),
                ("another root", _allowance(self.root / "elsewhere"),
                 "ISSUE_47_LIVE_REGISTRATION_IS_FROM_A_LEDGER_NO_REGISTERED_APPROVAL_GRANTED"),
                ("another transport", {**self.allowance, "transport": {"provider": "other"}},
                 "ISSUE_47_LIVE_REGISTRATION_IS_FROM_A_LEDGER_NO_REGISTERED_APPROVAL_GRANTED")):
            granted.write_bytes(canonical_json_bytes(value=counted_calls.granted_ledger_record(allowance)))
            with self.subTest(name), self.assertRaisesRegex(ValueError, reason):
                counted_calls.check_granted(counted=block, repo_root=self.root)
        record = counted_calls.granted_ledger_record(self.allowance)
        granted.write_text(json.dumps({**record, "transport": {"provider": "other"}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ISSUE_47_REGISTERED_APPROVAL_LEDGER_CHANGED"):
            counted_calls.check_granted(counted=block, repo_root=self.root)
        granted.write_bytes(canonical_json_bytes(value=record))
        self.assertEqual(record, counted_calls.check_granted(counted=block, repo_root=self.root))


if __name__ == "__main__":
    unittest.main()
