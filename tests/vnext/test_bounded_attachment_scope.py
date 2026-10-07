"""Exact resumed URL admission; no network, ledger writes or broader grant."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock
from types import SimpleNamespace
from contextlib import nullcontext

from vnext.historical_source_acquisition import request_is_in_scope, HistoricalAcquisitionError


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence/issue47_history"


class BoundedAttachmentScopeTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((EVIDENCE / "acquisition-wiring/approval-comment-body.json").read_text())
        cls.extension = json.loads((EVIDENCE / "acquisition-extension/approval-comment-body.json").read_text())
        cls.dependency = json.loads((EVIDENCE / "paramount2024-e01-exhibit-dependency-2026-10-05/approved-actual-dependency.json").read_text())["dependency"]
        cls.company = "paramount_skydance_paramount_global"
        cls.purpose = cls.extension["scope"]["purposes"][0]
        cls.bound = {"company_id": cls.company, "source_url": cls.dependency["source_url"],
                     "maximum_additional_sec_calls": 1, "retry_count": 0}

    def check(self, *, allowance=None, dependency=None, bound=None, purpose=None):
        return request_is_in_scope(allowance=allowance or self.extension,
            company_id=self.company, dependency=dependency or self.dependency,
            purpose=purpose or self.purpose, bounded_capture=bound)

    def test_original_broad_grant_and_later_replacement_explain_the_refusal(self):
        self.assertIn("B_EVENT_WINDOWS", self.check(allowance=self.original)["grants"])
        with self.assertRaisesRegex(HistoricalAcquisitionError, "REQUEST_OUTSIDE_EVERY_GRANT"):
            self.check()

    def test_specific_one_capture_is_admitted_without_mutating_either_approval(self):
        before = deepcopy(self.extension)
        result = self.check(bound=self.bound)
        self.assertEqual(["OWNER_APPROVED_BOUNDED_CAPTURE"], result["grants"])
        self.assertEqual(["2024-12-31"], result["periods"])
        self.assertEqual(self.extension, before)

    def test_other_url_cannot_use_the_exact_capture(self):
        dependency = {**self.dependency, "source_url": self.dependency["source_url"].replace("ex-99.htm", "other.htm")}
        with self.assertRaisesRegex(HistoricalAcquisitionError, "REQUEST_OUTSIDE_EVERY_GRANT"):
            self.check(dependency=dependency, bound=self.bound)

    def test_other_company_or_more_calls_or_retry_cannot_use_the_capture(self):
        for change in ({"company_id": "another_company"},
                       {"maximum_additional_sec_calls": 2}, {"retry_count": 1}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(HistoricalAcquisitionError, "REQUEST_OUTSIDE_EVERY_GRANT"):
                    self.check(bound={**self.bound, **change})

    def test_purpose_class_and_date_checks_are_not_bypassed(self):
        with self.assertRaisesRegex(HistoricalAcquisitionError, "PURPOSE_NOT_IN_SCOPE"):
            self.check(bound=self.bound, purpose="unapproved-purpose")
        for change, reason in [({"dependency_class": "UNAPPROVED_CLASS"}, "DEPENDENCY_CLASS_NOT_IN_SCOPE"),
                               ({"consumers": ["period:2030-12-31"]}, "TARGET_PERIOD_NOT_IN_SCOPE")]:
            with self.subTest(change=change):
                with self.assertRaisesRegex(HistoricalAcquisitionError, reason):
                    self.check(dependency={**self.dependency, **change}, bound=self.bound)

    def test_new_general_request_is_still_refused_after_the_specific_preflight(self):
        self.check(bound=self.bound)
        with self.assertRaisesRegex(HistoricalAcquisitionError, "REQUEST_OUTSIDE_EVERY_GRANT"):
            self.check()

    def session_control(self, counts):
        from vnext.historical_sec_session import HistoricalSecSession
        session = object.__new__(HistoricalSecSession)
        bound = {**self.bound, "counts_before": [0, 0, 1771],
                 "maximum_counts": [0, 0, 1772]}
        session.ledger = SimpleNamespace(_bounded_capture=bound,
            locked=lambda: nullcontext(), require_unblocked=lambda: None,
            snapshot=lambda: {"counts": counts}, claimed_url_ordinals=lambda: {})
        session.allowance = self.extension
        session.data_root = ROOT
        session._check = lambda: None
        session._published_still = lambda: None
        session._reclaim = lambda *args: None
        session._capture_one = Mock(side_effect=RuntimeError("TEST_ADMISSION_REACHED_NO_HTTP_OR_CLAIM"))
        return session

    def test_capture_consumer_reaches_admission_before_any_claim_or_socket(self):
        session = self.session_control([0, 0, 1771])
        with patch("vnext.historical_sec_session.install_historical_source_inputs"), \
             patch("vnext.historical_sec_session.declared_frame", return_value={
                 "requirements": [self.dependency], "target_report_dates": ["2024-12-31"]}):
            with self.assertRaisesRegex(RuntimeError, "TEST_ADMISSION_REACHED_NO_HTTP_OR_CLAIM"):
                session.capture(company_id=self.company, url=self.dependency["source_url"])
        session._capture_one.assert_called_once()
        self.assertEqual(["OWNER_APPROVED_BOUNDED_CAPTURE"],
            session._capture_one.call_args.kwargs["admitted"]["grants"])

    def test_consumed_one_attempt_refuses_before_the_capture_boundary(self):
        from vnext.historical_sec_session import HistoricalSessionError
        session = self.session_control([0, 0, 1772])
        with self.assertRaisesRegex(HistoricalSessionError, "LIMITED_RESUME_CALL_CONSUMED"):
            session.capture(company_id=self.company, url=self.dependency["source_url"])
        session._capture_one.assert_not_called()
