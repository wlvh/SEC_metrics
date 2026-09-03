"""B0 scoped packing uses original IDs and full native Evidence replay."""

import copy
import json
import unittest
from dataclasses import replace

from tests.vnext.r4_b0_fixture_support import b0_fixture
from vnext.canonical import content_hash
from vnext.scoped_reader import ScopedReaderError, prepare_scoped_reader_request
from vnext.scoped_reader import replay_scoped_offline_attempt, validate_scoped_reader_response
from vnext.source_scope import build_source_scope_manifest


class ScopedReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = b0_fixture()

    def _arguments(self):
        f = self.fixture
        return {"source_scope_manifest": f["scope"],
                "expected_manifest_id": f["scope"]["source_scope_manifest_id"],
                **f["authority"]}

    def test_scoped_request_keeps_full_authority_without_leaking_audit_answers(self):
        args = self._arguments()
        prepared = prepare_scoped_reader_request(**args)
        body = json.loads(prepared.request_bytes)
        self.assertEqual("SCOPED_READER_REQUEST", body["record_type"])
        self.assertEqual([1], body["window_binding"]["ordered_table_orders"])
        self.assertEqual(1, len(body["untrusted_scoped_table_data"]["tables"]))
        self.assertNotIn("synthetic_candidate", body)
        self.assertNotIn("reference", body)
        self.assertNotIn("target_locator", body)
        self.assertEqual(3, len(args["reader_manifest"]["tables"]))
        attempt = validate_scoped_reader_response(
            prepared_request=prepared, response_text=self.fixture["response_text"],
            attempt_id="attempt:b0:scoped", **args,
        )
        self.assertEqual("PASS", attempt["evidence"]["status"])
        self.assertEqual(0, attempt["provider_call_count"])
        self.assertEqual(attempt, replay_scoped_offline_attempt(
            attempt=attempt, prepared_request=prepared, **args))

    def test_request_or_attempt_rebinding_cannot_bypass_full_replay(self):
        args = self._arguments()
        prepared = prepare_scoped_reader_request(**args)
        with self.assertRaisesRegex(ScopedReaderError, "request bytes"):
            validate_scoped_reader_response(
                prepared_request=replace(prepared, request_bytes=b"{}"),
                response_text=self.fixture["response_text"], attempt_id="attempt:b0:bad", **args)
        attempt = validate_scoped_reader_response(
            prepared_request=prepared, response_text=self.fixture["response_text"],
            attempt_id="attempt:b0:valid", **args)
        changed = copy.deepcopy(attempt)
        changed["source_scope_manifest_id"] = "sha256:" + "0" * 64
        changed["scoped_attempt_id"] = content_hash(value={
            k: v for k, v in changed.items() if k != "scoped_attempt_id"})
        with self.assertRaises(ScopedReaderError):
            replay_scoped_offline_attempt(attempt=changed, prepared_request=prepared, **args)

    def test_all_four_zero_call_classes_cannot_prepare_requests(self):
        f = self.fixture
        for classification in ("NEGATIVE_EXPECTED", "NOT_APPLICABLE", "QUALITATIVE_ONLY", "AMBIGUOUS_EXCLUDED"):
            audit = copy.deepcopy(f["audit"])
            audit.update(fixture_class=classification, synthetic_candidate=None, target_locator=None)
            scope = build_source_scope_manifest(audit=audit, **f["authority"])
            with self.subTest(classification=classification), self.assertRaisesRegex(ScopedReaderError, "ZERO_CALL_FIXTURE"):
                prepare_scoped_reader_request(source_scope_manifest=scope,
                    expected_manifest_id=scope["source_scope_manifest_id"], **f["authority"])
