"""B0 scoped packing uses original IDs and full native Evidence replay."""

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tests.vnext.r4_b0_fixture_support import REPO_ROOT, b0_fixture, zero_call_audit
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.scoped_reader import ScopedReaderError, prepare_scoped_reader_request
from vnext.scoped_reader import replay_scoped_offline_attempt, validate_scoped_reader_response
from vnext.scoped_reader import build_scoped_reader_plan, load_scoped_reader_plan
from vnext.scoped_reader import load_scoped_reader_request, load_scoped_offline_attempt
from vnext.scoped_reader import replay_scoped_offline_artifact_set
from vnext.source_scope import build_source_scope_manifest
from vnext.reader import validate_reader_output
from vnext.evidence import check_evidence
from tests.vnext.common import cell_locator


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
            audit = zero_call_audit(audit=f["audit"], classification=classification)
            scope = build_source_scope_manifest(audit=audit, **f["authority"])
            with self.subTest(classification=classification), self.assertRaisesRegex(ScopedReaderError, "ZERO_CALL_FIXTURE"):
                prepare_scoped_reader_request(source_scope_manifest=scope,
                    expected_manifest_id=scope["source_scope_manifest_id"], **f["authority"])

    def _attempt(self):
        prepared = prepare_scoped_reader_request(**self._arguments())
        attempt = validate_scoped_reader_response(prepared_request=prepared,
            response_text=self.fixture["response_text"], attempt_id="attempt:scoped:full-artifact", **self._arguments())
        return prepared, attempt

    def test_plan_request_attempt_native_evidence_link_is_complete(self):
        prepared, attempt = self._attempt()
        plan = build_scoped_reader_plan(**self._arguments())
        self.assertEqual(prepared.plan_bytes, canonical_json_bytes(value=plan))
        self.assertEqual(prepared.plan_id, plan["scoped_plan_id"])
        self.assertEqual(prepared.plan_id, json.loads(prepared.request_bytes)["scoped_plan_id"])
        self.assertEqual("NOT_AUTHORIZED", plan["live_authorization"])
        self.assertFalse(plan["provider_paid_sec_authorized"])
        link = attempt["candidate_evidence_link"]
        self.assertEqual(prepared.plan_id, link["scoped_plan_id"])
        self.assertEqual(prepared.request_id, link["scoped_request_id"])
        self.assertEqual(attempt["candidate"]["candidate_hash"], link["candidate_hash"])
        self.assertEqual(attempt["evidence"]["evidence_check_id"], link["evidence_check_id"])
        self.assertEqual(attempt["candidate"]["assistant_output_sha256"], link["response_sha256"])
        self.assertEqual("NONE", link["qualification_credit"])

    def test_request_data_contains_only_certified_tables_not_full_source_or_audit(self):
        prepared = prepare_scoped_reader_request(**self._arguments())
        body = json.loads(prepared.request_bytes)
        self.assertNotIn("untrusted_table_data", body)
        self.assertNotIn("reader_input_manifest", body)
        for forbidden in ("reference", "navigation_paths", "table_audit", "synthetic_candidate",
                          "target_locator", "check_evidence_result", "out_of_window_candidates"):
            self.assertNotIn(forbidden, body)
            self.assertNotIn(forbidden, body["untrusted_scoped_table_data"])
        self.assertNotIn(b"Unrelated table", prepared.request_bytes)
        self.assertNotIn(b"Other appendix", prepared.request_bytes)
        self.assertIn(b"111%", prepared.request_bytes)
        self.assertEqual(3, len(self.fixture["authority"]["full_derived_asset"]["tables"]))

    def test_complete_attempt_tamper_matrix_rejects_even_after_content_id_rebind(self):
        prepared, attempt = self._attempt()
        mutations = [
            lambda a: a.__setitem__("scoped_plan_id", "sha256:" + "0" * 64),
            lambda a: a.__setitem__("request_sha256", "0" * 64),
            lambda a: a.__setitem__("response_sha256", "0" * 64),
            lambda a: a.__setitem__("provider_call_count", 1),
            lambda a: a.__setitem__("paid_model_call_count", True),
            lambda a: a.__setitem__("actual_provider_usage", {"prompt_tokens": 100}),
            lambda a: a.__setitem__("execution_mode", "LIVE"),
            lambda a: a.__setitem__("qualification_credit", "CURRENT"),
            lambda a: a["candidate_evidence_link"].__setitem__("request_sha256", "0" * 64),
            lambda a: a["candidate_evidence_link"].__setitem__("candidate_record_sha256", "0" * 64),
            lambda a: a["candidate_evidence_link"].__setitem__("evidence_record_sha256", "0" * 64),
            lambda a: a["candidate"].__setitem__("attempt_id", "attempt:wrong:source"),
            lambda a: a["candidate"].__setitem__("assistant_output_sha256", "0" * 64),
            lambda a: a["evidence"].__setitem__("system_approval_eligible", False),
            lambda a: a.__setitem__("unknown_extra_field", "must fail"),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(attempt)
            mutation(changed)
            changed["scoped_attempt_id"] = content_hash(value={
                key: value for key, value in changed.items() if key != "scoped_attempt_id"})
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                replay_scoped_offline_attempt(attempt=changed,
                    expected_attempt_id=changed["scoped_attempt_id"], prepared_request=prepared, **self._arguments())

    def test_scoped_response_cannot_move_any_locator_outside_the_certified_window(self):
        prepared = prepare_scoped_reader_request(**self._arguments())
        response = copy.deepcopy(self.fixture["response"])
        response["table_locator"]["table_id"] = "table_000001"
        candidate = response["candidates"][0]
        candidate["locator"].update(table_id="table_000001", row_index=0, column_index=0,
                                    origin_row_index=0, origin_column_index=0)
        candidate["scope_evidence_locators"][0]["locator"]["table_id"] = "table_000001"
        with self.assertRaisesRegex(ScopedReaderError, "leaves certified windows"):
            validate_scoped_reader_response(prepared_request=prepared,
                response_text=json.dumps(response), attempt_id="attempt:scoped:outside", **self._arguments())

    def test_two_windows_do_not_authorize_cross_table_scope_locators(self):
        audit = copy.deepcopy(self.fixture["audit"])
        audit["windows"] = [{"start_order": 0, "end_order": 0}, {"start_order": 1, "end_order": 1}]
        scope = build_source_scope_manifest(audit=audit, **self.fixture["authority"])
        args = {**self._arguments(), "source_scope_manifest": scope,
                "expected_manifest_id": scope["source_scope_manifest_id"]}
        prepared = prepare_scoped_reader_request(**args)
        response = copy.deepcopy(self.fixture["response"])
        response["candidates"][0]["scope_evidence_locators"][0]["locator"]["table_id"] = "table_000001"
        with self.assertRaisesRegex(ValueError, "leaves the target table"):
            validate_scoped_reader_response(prepared_request=prepared, response_text=json.dumps(response),
                attempt_id="attempt:scoped:cross-table", **args)

    def test_native_evidence_rejection_is_retained_not_repaired(self):
        prepared = prepare_scoped_reader_request(**self._arguments())
        response = copy.deepcopy(self.fixture["response"])
        response["candidates"][0]["claimed_raw_value"] = "112%"
        attempt = validate_scoped_reader_response(prepared_request=prepared,
            response_text=json.dumps(response), attempt_id="attempt:scoped:rejected", **self._arguments())
        self.assertEqual("REJECTED", attempt["evidence"]["status"])
        self.assertIn("AI_CLAIMED_VALUE_CELL_MISMATCH", attempt["evidence"]["reason_codes"])
        self.assertEqual(attempt, replay_scoped_offline_attempt(
            attempt=attempt, prepared_request=prepared, **self._arguments()))
        self.assertEqual(0, attempt["provider_call_count"])

    def test_native_pass_for_wrong_in_window_cell_unit_or_period_is_not_certified(self):
        args = self._arguments()
        prepared = prepare_scoped_reader_request(**args)
        mutations = [
            lambda claim: claim.update(locator=cell_locator(asset=args["full_derived_asset"],
                table_id="table_000002", row_index=1, column_index=0), claimed_raw_value="2025"),
            lambda claim: claim.update(claimed_period="FY2024"),
            lambda claim: claim.update(claimed_reported_unit="ratio"),
        ]
        for mutation in mutations:
            response = copy.deepcopy(self.fixture["response"])
            mutation(response["candidates"][0])
            response_text = json.dumps(response)
            candidate = validate_reader_output(response_text=response_text, attempt_id="attempt:wrong:certificate",
                required_roles=args["task_contract"]["required_roles"], scope_contract=args["task_contract"]["scope_contract"],
                source_reference_ids=args["reader_manifest"]["source_reference_ids"],
                derived_asset_ids=[args["full_derived_asset"]["derived_asset_id"]])
            evidence = check_evidence(candidate=candidate, derived_asset=args["full_derived_asset"],
                reader_manifest=args["reader_manifest"], reader_payload_body=args["evidence_authority_payload"],
                source_references=[args["source_reference"]], identity_constraints=args["task_contract"]["identity_constraints"],
                scope_contract=args["task_contract"]["scope_contract"])
            with self.subTest(mutation=mutation):
                self.assertEqual("PASS", evidence["status"])
                with self.assertRaisesRegex(ScopedReaderError, "SCOPED_(CERTIFIED_TARGET_MISMATCH|REFERENCE_RECONCILIATION_FAILED)"):
                    validate_scoped_reader_response(prepared_request=prepared, response_text=response_text,
                        attempt_id="attempt:wrong:certificate", **args)

    def _write_artifact_set(self, directory, prepared, attempt):
        contents = {"source_scope.json": canonical_json_bytes(value=self.fixture["scope"]),
                    "scoped_plan.json": prepared.plan_bytes,
                    "scoped_request.json": prepared.request_bytes,
                    "scoped_attempt.json": canonical_json_bytes(value=attempt)}
        for name, data in contents.items():
            (directory / name).write_bytes(data)
        return {name: {"sha256": sha256_bytes(content=data), "size": len(data)}
                for name, data in contents.items()}

    def test_full_four_file_disk_replay_and_exact_directory_set(self):
        prepared, attempt = self._attempt()
        with tempfile.TemporaryDirectory(prefix="r4-scoped-bundle-", dir=REPO_ROOT) as tmp:
            directory = Path(tmp)
            bindings = self._write_artifact_set(directory, prepared, attempt)
            args = {"directory": directory, "repo_root": REPO_ROOT, "file_bindings": bindings,
                    "expected_manifest_id": self.fixture["scope"]["source_scope_manifest_id"],
                    "expected_plan_id": prepared.plan_id, "expected_request_id": prepared.request_id,
                    "expected_attempt_id": attempt["scoped_attempt_id"], **self.fixture["authority"]}
            replayed = replay_scoped_offline_artifact_set(**args)
            self.assertEqual(attempt, replayed["attempt"])
            self.assertEqual(prepared, replayed["request"])
            unexpected = directory / "unexpected.json"
            unexpected.write_text("{}")
            with self.assertRaisesRegex(ScopedReaderError, "exact set"):
                replay_scoped_offline_artifact_set(**args)
            unexpected.unlink()
            request_path = directory / "scoped_request.json"
            request_path.unlink()
            request_path.symlink_to(directory / "scoped_plan.json")
            with self.assertRaises(ValueError):
                replay_scoped_offline_artifact_set(**args)

    def test_full_disk_subtypes_reject_partial_identity_and_self_rebound_tamper(self):
        prepared, attempt = self._attempt()
        with tempfile.TemporaryDirectory(prefix="r4-scoped-identities-", dir=REPO_ROOT) as tmp:
            directory = Path(tmp)
            datasets = [
                ("plan.json", json.loads(prepared.plan_bytes), "scoped_plan_id",
                 lambda path, identity: load_scoped_reader_plan(path=path, repo_root=REPO_ROOT,
                    expected_plan_id=identity, **self._arguments())),
                ("request.json", json.loads(prepared.request_bytes), None,
                 lambda path, identity: load_scoped_reader_request(path=path, repo_root=REPO_ROOT,
                    expected_request_id=identity, **self._arguments())),
                ("attempt.json", attempt, "scoped_attempt_id",
                 lambda path, identity: load_scoped_offline_attempt(path=path, repo_root=REPO_ROOT,
                    expected_attempt_id=identity, prepared_request=prepared, **self._arguments())),
            ]
            fields = ["artifact_requirement_generation", "requirement_id", "requirement_closure_hash", "requirement_hashes"]
            for name, original, id_field, loader in datasets:
                for removed in [fields, fields[1:], fields[:2]] + [[field] for field in fields]:
                    changed = copy.deepcopy(original)
                    for field in removed:
                        changed.pop(field)
                    identity = content_hash(value={key: value for key, value in changed.items() if key != id_field})
                    if id_field is not None:
                        changed[id_field] = identity
                    path = directory / name
                    path.write_bytes(canonical_json_bytes(value=changed))
                    with self.subTest(record=name, removed=removed), self.assertRaises(ValueError):
                        loader(path, identity)
