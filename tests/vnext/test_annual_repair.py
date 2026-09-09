"""Source-backed label regressions and native repair runtime with only I/O mocked."""
import copy, io, json, os, socket, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
from contextlib import contextmanager
from vnext import (
    annual_runtime as runtime,
    annual_repair_budget as budget,
    annual_regression,
    ai_adapter,
)
from vnext.canonical import canonical_json_bytes, sha256_bytes, content_hash
from tests.vnext.test_annual_update import OLD_RUN

ROOT = Path(__file__).resolve().parents[2]
DELEGATION_URL = "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5595412960"
STAGE_URL = "https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-999902"


def comment(url, body):
    return {
        "id": int(url.rsplit("-", 1)[1]),
        "html_url": url,
        "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/28",
        "user": {"login": "wlvh"},
        "created_at": "2026-09-09T03:00:00Z",
        "updated_at": "2026-09-09T03:00:00Z",
        "body": json.dumps(body),
    }


class AnnualLabelRegressionTest(unittest.TestCase):
    def test_policy_selects_new_requirement_only(self):
        from vnext.annual_evidence import policy_choice
        from vnext.requirements import load_requirement_snapshot

        old = load_requirement_snapshot(snapshot_dir=ROOT / "requirements/issue_28_v5")
        new = load_requirement_snapshot(snapshot_dir=ROOT / "requirements/issue_28_v6")
        self.assertIsNone(policy_choice(old))
        self.assertEqual(
            "EXACT_SOURCE_RAW_OR_TEXT_V2",
            policy_choice(new)["label_comparison"]["policy"],
        )

    def test_unmodified_response_and_business_counterexamples(self):
        with mock.patch.object(
            socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN")
        ):
            receipt = annual_regression.build_regression_receipt(repo_root=ROOT)
        self.assertEqual("PASS", receipt["status"], receipt)
        cases = {c["case"]: c for c in receipt["cases"]}
        self.assertEqual(
            ["SCOPE_LABEL_TEXT_MISMATCH"], cases["original_raw_rule"]["reason_codes"]
        )
        self.assertEqual("PASS", cases["original_new_rule"]["observed"])
        self.assertIn(
            "ANNUAL_SCOPE_VALUE_ROW_MISMATCH",
            cases["wrong_region_value"]["reason_codes"],
        )
        self.assertIn(
            "ANNUAL_SCOPE_VALUE_GROUP_MISMATCH",
            cases["same_numeric_value_wrong_group"]["reason_codes"],
        )
        self.assertIn(
            "ANNUAL_SCOPE_UNRESOLVED_OR_UNSUPPORTED",
            cases["unknown_scope_alias"]["reason_codes"],
        )
        self.assertIn(
            "ANNUAL_SCOPE_UNRESOLVED_OR_UNSUPPORTED",
            cases["conflicting_claims"]["reason_codes"],
        )
        annual_regression.verify_regression_receipt(receipt)
        rewritten = copy.deepcopy(receipt)
        bad = next(c for c in rewritten["cases"] if c["case"] == "wrong_unit")
        bad.update(expected="PASS", observed="PASS")
        rewritten["receipt_id"] = content_hash(
            value={k: v for k, v in rewritten.items() if k != "receipt_id"}
        )
        with self.assertRaisesRegex(ValueError, "REGRESSION_STALE_OR_FAILED"):
            annual_regression.verify_regression_receipt(rewritten)
        self.assertIn(
            "ANNUAL_VALUE_HEADER_AMBIGUOUS",
            cases["conflicting_year_header"]["reason_codes"],
        )
        self.assertIn(
            "ANNUAL_VALUE_HEADER_AMBIGUOUS",
            cases["conflicting_role_header"]["reason_codes"],
        )
        self.assertIn(
            "ANNUAL_VALUE_HEADER_PERIOD_MISMATCH",
            cases["same_value_prior_year"]["reason_codes"],
        )

    def test_old_failure_cannot_be_counted_as_a_repair_attempt(self):
        import shutil

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "stages/1"
            candidate = first / "candidates/borrowed"
            shutil.copytree(
                ROOT
                / "docs/evidence/annual_runtime/live/native-candidate/invocation_control",
                candidate / "invocation_control",
            )
            shutil.copyfile(
                ROOT / "docs/evidence/annual_runtime/live/native-candidate/plan.json",
                candidate / "plan.json",
            )
            (first / "stage-approval.json").write_text(
                json.dumps({"stage": {"reviewed_code": {"runtime_tree": "forged"}}})
            )
            with self.assertRaisesRegex(ValueError, "FIRST_APPROVAL_INVALID"):
                budget._prior_for_second(
                    root,
                    {
                        "previous_failure_execution_id": "unused",
                        "new_failure_fixed": True,
                    },
                    {"runtime_tree": "different"},
                )

    def test_text_generation_preserves_business_and_footnotes(self):
        from vnext.table_grid import _semantic_text

        self.assertEqual("Worldwide (2)", _semantic_text(raw_text="\nWorldwide\t(2)\r"))
        self.assertEqual("Worldwide (2)", _semantic_text(raw_text="Worldwide&#160;(2)"))
        for left, right in [
            ("Worldwide (2)", "Worldwide (3)"),
            ("Systemwide", "Company-operated"),
            ("Worldwide", "U.S. & Canada"),
        ]:
            self.assertNotEqual(
                _semantic_text(raw_text=left), _semantic_text(raw_text=right)
            )
        self.assertEqual("A\u200bB", _semantic_text(raw_text="A\u200bB"))


class AnnualRepairRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="annual-repair-mock-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.budget_root = self.root / "budget"
        self.stage_root = self.budget_root / "stages/1"
        blocker = mock.patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("REAL_NETWORK_FORBIDDEN"),
        )
        blocker.start()
        self.addCleanup(blocker.stop)
        old = json.loads(
            (
                ROOT / "docs/evidence/annual_runtime/stage-approved-proposal.json"
            ).read_text()
        )
        delegation = {
            "record_type": "ANNUAL_REPAIR_BUDGET_DELEGATION",
            "approval_kind": "USER_DELEGATED_POLICY_AND_BUDGET_ONLY",
            "budget_root": str(self.budget_root),
            "original_stage_id": old["stage_id"],
            "original_stage_root": old["stage_root"],
            "maximum_additional_provider_paid_sec_calls": [2, 2, 0],
            "maximum_total_provider_paid_sec_calls": [3, 3, 0],
            "automatic_retry_count": 0,
            "execution_authorized_by_this_record": False,
            "formal_publication_authorized": False,
            "merge_authorized": False,
            "evidence_scope": "SIMULATED_GITHUB_BOUNDARY_NOT_A_REAL_GRANT",
        }
        self.responses = {"5595412960": comment(DELEGATION_URL, delegation)}

        def api(path):
            self.assertTrue(
                path.startswith("repos/wlvh/SEC_metrics/issues/comments/"), path
            )
            return copy.deepcopy(self.responses[path.rsplit("/", 1)[1]])

        gate = mock.patch.object(runtime, "_github", side_effect=api)
        gate.start()
        self.addCleanup(gate.stop)
        self.data = self.root / "data"
        runtime.initialize_data_root(data_root=self.data)
        self.receipt = annual_regression.build_regression_receipt(repo_root=ROOT)
        self.evidence = self.root / "regression.json"
        self.evidence.write_text(json.dumps(self.receipt))
        identity = runtime.code_identity()
        review = {
            "reviewer_kind": "INDEPENDENT_MODEL_SUBTASK",
            "conclusion": "NO_BLOCKING_FINDINGS",
            "reviewed_head": identity["exact_head"],
            "runtime_tree": identity["runtime_tree"],
            "repair_regression_id": self.receipt["receipt_id"],
            "root_cause": "SIMULATED_REVIEW: exact source label representation and wrong row/group ownership",
            "necessity_and_business_counterexamples_reviewed": True,
            "evidence_scope": "SIMULATED_GITHUB_BOUNDARY_NOT_REAL_REVIEW",
        }
        self.review = self.root / "review.json"
        self.review.write_text(json.dumps(review))
        self.stage = runtime.stage_proposal(
            stage_root=self.stage_root,
            data_root=self.data,
            baseline_run=OLD_RUN,
            review_path=self.review,
            repair_evidence_path=self.evidence,
            repair_ordinal=1,
        )
        self.responses["999902"] = comment(STAGE_URL, self.stage)

    @contextmanager
    def provider(self, *, wrong_scope=False):
        records, attempt, response, payload = annual_regression._fixture(ROOT)
        expected = (
            ROOT / annual_regression.AUDIT / attempt["request_body_path"]
        ).read_bytes()
        body = json.loads(response.read_text())
        if wrong_scope:
            body["candidates"][0]["scope_evidence_locators"][1][
                "raw_text"
            ] = "Worldwide (3)"
        raw = canonical_json_bytes(
            value={
                "id": "mock-repair-new-execution",
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": json.dumps(body)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 161707,
                    "completion_tokens": 580,
                    "total_tokens": 162287,
                },
            }
        )

        def http(*, fullurl, timeout):
            self.assertEqual(expected, fullurl.data)
            result = io.BytesIO(raw)
            result.headers = {"x-request-id": "mock-repair-new-execution"}
            return result

        with mock.patch.dict(
            os.environ, {"DEEPSEEK_API_KEY": "test-only-not-a-secret"}
        ), mock.patch.object(
            ai_adapter._DEEPSEEK_OPENER, "open", side_effect=http
        ) as opened:
            yield opened

    def test_repaired_native_chain_and_repeat_are_bound_to_one_slot(self):
        with self.provider() as opened:
            result = runtime.run_update(approval_url=STAGE_URL)
            self.assertEqual("CANDIDATE_UPDATE_SUCCEEDED", result["status"], result)
            repeated = runtime.run_update(approval_url=STAGE_URL)
            self.assertEqual("NO_NEW_ANNUAL_FILING", repeated["status"])
            self.assertEqual(1, opened.call_count)
        self.assertEqual([2, 2, 0], result["process_provider_paid_sec_calls"])
        self.assertEqual([1, 1, 0], result["additional_repair_provider_paid_sec_calls"])
        self.assertEqual([0, 0, 0], repeated["provider_paid_sec_calls"])
        self.assertEqual("0.693", result["new_candidate"]["results"][0]["value"])
        self.assertEqual("26186000000", result["structured_candidate"]["B01"]["value"])
        run = Path(result["new_candidate"]["run_directory"])
        records = [
            json.loads(l) for l in (run / "records.jsonl").read_text().splitlines()
        ]
        evidence = next(r for r in records if r["record_type"] == "EVIDENCE_CHECK")
        self.assertTrue(
            any(
                c["check"] == "ANNUAL_SOURCE_OWNERSHIP_V1" and c["status"] == "PASS"
                for c in evidence["checks"]
            )
        )
        # Disk evidence cannot silently fall back to old raw-only replay.
        approval = json.loads((self.stage_root / "stage-approval.json").read_text())
        plan = approval["plan"]
        with self.assertRaisesRegex(ValueError, "REPAIR_SLOT_ALREADY_CONSUMED"):
            budget.claim_slot(self.stage, plan, runtime._requirement())
        with self.assertRaisesRegex(ValueError, "ROOT_NOT_BUDGET_OWNED"):
            runtime.stage_proposal(
                stage_root=self.root / "different",
                data_root=self.data,
                baseline_run=OLD_RUN,
                review_path=self.review,
                repair_evidence_path=self.evidence,
                repair_ordinal=1,
            )

    def test_failed_repair_preserves_old_and_forbids_unchanged_second(self):
        with self.provider(wrong_scope=True) as opened:
            result = runtime.run_update(approval_url=STAGE_URL)
            self.assertEqual("CANDIDATE_UPDATE_FAILED", result["status"], result)
            repeat = runtime.run_update(approval_url=STAGE_URL)
            self.assertEqual("RUNTIME_STAGE_ALREADY_CONSUMED", repeat["error"])
            self.assertEqual(1, opened.call_count)
        self.assertFalse((self.stage_root / "successful-candidate.json").exists())
        approval_file = self.stage_root / "stage-approval.json"
        saved = approval_file.read_bytes()
        forged = json.loads(saved)
        forged["stage"]["reviewed_code"]["runtime_tree"] = "sha256:" + "0" * 64
        approval_file.write_text(json.dumps(forged))
        try:
            with self.assertRaisesRegex(ValueError, "FIRST_STAGE_PLAN_ID_CHANGED"):
                runtime.stage_proposal(
                    stage_root=self.budget_root / "stages/2",
                    data_root=self.data,
                    baseline_run=OLD_RUN,
                    review_path=self.review,
                    repair_evidence_path=self.evidence,
                    repair_ordinal=2,
                )
        finally:
            approval_file.write_bytes(saved)
        with self.assertRaisesRegex(ValueError, "UNCHANGED_REROLL"):
            runtime.stage_proposal(
                stage_root=self.budget_root / "stages/2",
                data_root=self.data,
                baseline_run=OLD_RUN,
                review_path=self.review,
                repair_evidence_path=self.evidence,
                repair_ordinal=2,
            )
        with self.assertRaisesRegex(ValueError, "ORDINAL_INVALID"):
            runtime.stage_proposal(
                stage_root=self.budget_root / "stages/3",
                data_root=self.data,
                baseline_run=OLD_RUN,
                review_path=self.review,
                repair_evidence_path=self.evidence,
                repair_ordinal=3,
            )
        self.assertEqual([2, 2, 0], budget.counts(self.budget_root))


if __name__ == "__main__":
    unittest.main()
