"""Formal Cutover semantic-stability and terminal-state regressions."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from vnext.canonical import atomic_write_bytes, atomic_write_json
from vnext.canonical import content_hash, strict_json_file
from vnext.cutover import CutoverError, _validate_live_stability
from vnext.cutover import _live_acquisition_artifacts
from vnext.cutover import _complete_prepared_cutover_receipt
from vnext.cutover import _require_sha256_identity
from vnext.cutover import _resume_committed_cutover
from vnext.cutover import _run_live_sec_acquisition
from vnext.cutover import _sec_stage_environment
from vnext.cutover import _verify_live_attempt_audit_closure
from vnext.cutover import _write_live_attempt_audit_closure
from vnext.cutover import _write_live_stability_receipt
from vnext.cutover import _write_formal_cutover_receipt
from vnext.cutover import run_cutover
from tests.vnext.common import REPO_ROOT
from tests.vnext.test_publication import commit_formal_fixture
from tests.vnext.test_publication import publication_inputs
from vnext.publication import prepare_publication_bundle
from vnext.publication import publication_state_snapshot


QUALIFICATION = {
    "qualification_id": "sha256:" + "1" * 64,
    "production_freeze_receipt_id": "sha256:" + "2" * 64,
    "second_layout": {"receipt_id": "sha256:" + "3" * 64},
    "post_freeze_holdout": {"receipt_id": "sha256:" + "4" * 64},
}


def stable_attempt(*, ordinal: int) -> dict:
    """Build one complete substantive live-attempt summary for mutation."""
    return {
        "attempt_id": "attempt:{}".format(ordinal),
        "candidate_hash": "sha256:" + "5" * 64,
        "evidence_check_id": "sha256:" + "6" * 64,
        "review_unit_hash": "sha256:" + "7" * 64,
        "review_context_hash": "sha256:" + "8" * 64,
        "rendered_review_hash": "sha256:" + "9" * 64,
        "request_body_sha256": "c" * 64,
        "model_requested": "gpt-5.6-terra",
        "model_returned": "gpt-5.6-terra",
        "selected_values_locators_claims": {
            "occupancy": {
                "claimed_value": "69.3",
                "locator": {"row": 4, "column": 2},
            },
        },
        "required_claims": {"period": "FY2025", "scope": "systemwide"},
        "metric_results": [
            {
                "metric_id": "B10",
                "publication": "PUBLISHED",
                "value": "69.3",
            },
        ],
        "effective_decision": {
            "approval_effect_hash": "sha256:" + "a" * 64,
            "decision": "APPROVE",
        },
        "strict_compatibility": {
            "receipt_id": "sha256:" + "b" * 64,
            "status": "PASS",
        },
    }


def audit_attempt(
    *, run_dir: Path, ordinal: int, status: str
) -> dict:
    """Build one terminal retry/success audit summary for closure tests."""
    value = {
        "attempt_id": "attempt:audit:{}".format(ordinal),
        "attempt_ordinal": ordinal,
        "company_id": "company-live",
        "decision_count": 0 if status == "FAILED" else 1,
        "error_class": "OPENAI_TIMEOUT" if status == "FAILED" else "",
        "model_requested": "gpt-5.6-terra",
        "model_returned": "none" if status == "FAILED" else "gpt-5.6-terra",
        "provider_request_id": "request:{}".format(ordinal),
        "assistant_output_sha256": "e" * 64 if status == "FAILED" else "f" * 64,
        "raw_response_sha256": str(ordinal) * 64,
        "request_body_sha256": "a" * 64,
        "run_audit_manifest_hash": "sha256:" + "b" * 63 + str(ordinal),
        "run_content_manifest_hash": "sha256:" + "c" * 63 + str(ordinal),
        "run_dir": str(run_dir),
        "run_id": "run:audit:{}".format(ordinal),
        "stability_ordinal": min(ordinal, 3),
        "status": status,
        "transport_observation_hash": "sha256:" + "d" * 64,
    }
    if status == "FAILED":
        value["failure_status"] = "FAILED_ATTEMPT"
    else:
        value.update(stable_attempt(ordinal=ordinal))
        value["attempt_id"] = "attempt:audit:{}".format(ordinal)
        value["run_dir"] = str(run_dir)
        value["run_id"] = "run:audit:{}".format(ordinal)
        value["status"] = status
        value["run_audit_manifest_hash"] = "sha256:" + "b" * 63 + str(
            ordinal
        )
        value["run_content_manifest_hash"] = "sha256:" + "c" * 63 + str(
            ordinal
        )
        value.update({
            "attempt_ordinal": ordinal,
            "company_id": "company-live",
            "decision_count": 1,
            "error_class": "",
            "model_requested": "gpt-5.6-terra",
            "model_returned": "gpt-5.6-terra",
            "provider_request_id": "request:{}".format(ordinal),
            "assistant_output_sha256": "f" * 64,
            "raw_response_sha256": str(ordinal) * 64,
            "request_body_sha256": "a" * 64,
            "stability_ordinal": ordinal - 1,
            "transport_observation_hash": "sha256:" + "d" * 64,
        })
    return value


class CutoverFailureFirstTest(unittest.TestCase):
    """Reject authority drift before any formal pointer mutation."""

    def test_live_stability_rejects_every_substantive_mixed_field(
        self,
    ) -> None:
        """Bind selected claims, Results, HUMAN outcome, and compatibility."""
        mutations = {
            "selected_values_locators_claims": {
                "occupancy": {
                    "claimed_value": "70.0",
                    "locator": {"row": 4, "column": 2},
                },
            },
            "required_claims": {
                "period": "FY2025",
                "scope": "comparable",
            },
            "metric_results": [
                {
                    "metric_id": "B10",
                    "publication": "PUBLISHED",
                    "value": "70.0",
                },
            ],
            "effective_decision": {
                "approval_effect_hash": "sha256:" + "c" * 64,
                "decision": "REJECT",
            },
            "strict_compatibility": {
                "receipt_id": "sha256:" + "d" * 64,
                "status": "FAIL",
            },
            "request_body_sha256": "e" * 64,
            "model_requested": "unexpected-model",
            "model_returned": "unexpected-model",
        }
        for field, changed_value in mutations.items():
            with self.subTest(field=field):
                attempts = [
                    stable_attempt(ordinal=value) for value in range(3)
                ]
                attempts[2][field] = changed_value
                with self.assertRaises(CutoverError) as raised:
                    _validate_live_stability(attempts=attempts)
                self.assertEqual("LIVE_READER_UNSTABLE", raised.exception.code)

    def test_precommit_cutover_receipt_is_not_passed(self) -> None:
        """Keep the durable success claim absent until official read-back."""
        publication_id = "publication_" + "e" * 64
        with tempfile.TemporaryDirectory() as directory:
            reference = _write_formal_cutover_receipt(
                workspace_dir=Path(directory),
                release_input_plan_id="sha256:" + "f" * 64,
                batch_manifest_id="sha256:" + "0" * 64,
                sec_acquisition_receipt_id="sha256:" + "1" * 64,
                live_stability_receipt_id="sha256:" + "2" * 64,
                cutover_qualification=QUALIFICATION,
                staging_parity_receipt_id="sha256:" + "3" * 64,
                legacy_invariant_migration_receipt_id="sha256:" + "4" * 64,
                fault_matrix={
                    "status": "PASSED",
                    "fault_matrix_id": "sha256:" + "5" * 64,
                    "fault_receipt_references": [
                        {"fault_receipt_id": "sha256:" + "6" * 64},
                    ],
                },
                validation_receipt_id="sha256:" + "7" * 64,
                initial_publication_id=None,
                previous_publication_id="publication_" + "d" * 64,
                publication_id=publication_id,
                active_after={
                    "active_publication_id": publication_id,
                    "mirror_hashes": {},
                },
                committed_at_utc="2026-08-06T00:00:00+00:00",
                live_attempt_audit_closure_id="sha256:" + "8" * 64,
            )
            receipt = strict_json_file(path=Path(reference["receipt_path"]))
        self.assertEqual("PREPARED", receipt["status"])
        self.assertNotIn("committed_at_utc", receipt)

    def test_formal_receipts_require_nonempty_audit_closure_id(self) -> None:
        """Reject absent or malformed live-attempt closure identities."""
        for identity in (None, "", "sha256:" + "G" * 64):
            with self.subTest(identity=identity):
                with self.assertRaises(CutoverError) as raised:
                    _require_sha256_identity(
                        value=identity,
                        field="live_attempt_audit_closure_id",
                    )
                self.assertEqual(
                    "CUTOVER_EVIDENCE_INCOMPLETE", raised.exception.code
                )

    def test_official_readback_supersedes_prepared_with_passed(self) -> None:
        """Create a distinct PASSED receipt only from official active state."""
        publication_id = "publication_" + "e" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared_reference = _write_formal_cutover_receipt(
                workspace_dir=root / "workspace",
                release_input_plan_id="sha256:" + "f" * 64,
                batch_manifest_id="sha256:" + "0" * 64,
                sec_acquisition_receipt_id="sha256:" + "1" * 64,
                live_stability_receipt_id="sha256:" + "2" * 64,
                cutover_qualification=QUALIFICATION,
                staging_parity_receipt_id="sha256:" + "3" * 64,
                legacy_invariant_migration_receipt_id="sha256:" + "4" * 64,
                fault_matrix={
                    "status": "PASSED",
                    "fault_matrix_id": "sha256:" + "5" * 64,
                    "fault_receipt_references": [
                        {"fault_receipt_id": "sha256:" + "6" * 64},
                    ],
                },
                validation_receipt_id="sha256:" + "7" * 64,
                initial_publication_id=None,
                previous_publication_id="publication_" + "d" * 64,
                publication_id=publication_id,
                active_after={
                    "active_publication_id": publication_id,
                    "mirror_hashes": {"metrics_matrix.csv": "8" * 64},
                },
                committed_at_utc="2026-08-06T00:00:00+00:00",
                live_attempt_audit_closure_id="sha256:" + "9" * 64,
            )
            prepared = strict_json_file(
                path=Path(prepared_reference["receipt_path"])
            )
            with self.assertRaises(CutoverError) as mismatched:
                _complete_prepared_cutover_receipt(
                    receipt_root=root / "durable-audit",
                    prepared=prepared,
                    active_after={
                        "active_publication_id": publication_id,
                        "mirror_hashes": {"metrics_matrix.csv": "0" * 64},
                    },
                    committed_at_utc="2026-08-06T00:00:01+00:00",
                )
            passed_reference = _complete_prepared_cutover_receipt(
                receipt_root=root / "durable-audit",
                prepared=prepared,
                active_after={
                    "active_publication_id": publication_id,
                    "mirror_hashes": {"metrics_matrix.csv": "8" * 64},
                },
                committed_at_utc="2026-08-06T00:00:01+00:00",
            )
            repeated_reference = _complete_prepared_cutover_receipt(
                receipt_root=root / "durable-audit",
                prepared=prepared,
                active_after={
                    "active_publication_id": publication_id,
                    "mirror_hashes": {"metrics_matrix.csv": "8" * 64},
                },
                committed_at_utc="2026-08-06T00:00:02+00:00",
            )
            passed = strict_json_file(
                path=Path(passed_reference["receipt_path"])
            )
        self.assertEqual("PREPARED", prepared["status"])
        self.assertEqual("PASSED", passed["status"])
        self.assertEqual(prepared["receipt_id"], passed["prepared_receipt_id"])
        self.assertNotEqual(prepared["receipt_id"], passed["receipt_id"])
        self.assertEqual(passed_reference, repeated_reference)
        self.assertEqual(
            "CUTOVER_FINAL_STATE_INVALID", mismatched.exception.code
        )

    def test_postcommit_resume_reacquires_sec_but_skips_ai_and_commit(
        self,
    ) -> None:
        """Refresh SEC, then return official state without OpenAI or CAS."""
        publication_id = "publication_" + "a" * 64
        resumed = {
            "status": "PUBLISHED",
            "publication_id": publication_id,
            "resumed_after_commit": True,
        }
        acquisition_reference = {
            "receipt_id": "sha256:" + "b" * 64,
            "receipt_path": "artifacts/vnext/cutover/sec.json",
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-secret",
                "SEC_CONTACT_EMAIL": "operator@axaxl.com",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@axaxl.com"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            return_value=QUALIFICATION,
        ), mock.patch(
            "vnext.cutover._validate_live_authority_roots",
        ), mock.patch(
            "vnext.cutover._resume_committed_cutover", return_value=resumed,
        ) as resume, mock.patch(
            "vnext.cutover.write_latest_run_status",
        ) as latest, mock.patch(
            "vnext.cutover._run_live_sec_acquisition",
            return_value=acquisition_reference,
        ) as acquisition, mock.patch(
            "vnext.cutover.build_approved_transport_adapter",
        ) as adapter, mock.patch(
            "vnext.cutover._commit_publication",
        ) as commit, mock.patch(
            "vnext.cutover._commit_initial_publication_chain",
        ) as initial_commit:
            result = run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=REPO_ROOT,
                execute_live=True,
                recorded_response_path=None,
                recorded_fixture_id=None,
                commit=True,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc="2026-08-06T00:00:01+00:00",
            )
        self.assertEqual(resumed, result)
        self.assertEqual(
            acquisition_reference["receipt_id"],
            result["invocation_sec_acquisition_receipt_id"],
        )
        self.assertEqual(
            acquisition_reference["receipt_path"],
            result["invocation_sec_acquisition_receipt_path"],
        )
        resume.assert_called_once()
        latest.assert_called_once()
        acquisition.assert_called_once_with(
            repo_root=REPO_ROOT,
            workspace_dir=Path(directory) / "workspace",
            executed_at_utc="2026-08-06T00:00:00+00:00",
        )
        adapter.assert_not_called()
        commit.assert_not_called()
        initial_commit.assert_not_called()

    def test_first_cutover_imports_legacy_then_commits_one_atomic_chain(
        self,
    ) -> None:
        """Use imported root A as B predecessor and avoid two public CASes."""
        predecessor = "publication_" + "1" * 64
        successor = "publication_" + "2" * 64
        attempt = {
            "attempt_id": "attempt:1",
            "run_dir": "/tmp/live-run",
            "run_id": "run:1",
            "status": "FROZEN",
        }
        prepared = {
            "batch_run_dirs": [Path("/tmp/batch-run")],
            "live_attempts": [attempt],
            "pending_reviews": [],
            "live_stability_receipt_id": "sha256:" + "3" * 64,
            "live_stability_receipt_path": "/tmp/stability.json",
            "semantic_stability_complete": True,
            "retry_policy": {"retry_count": 2},
        }
        states = iter((
            {"active_publication_id": None, "mirror_hashes": {}},
            {
                "active_publication_id": successor,
                "mirror_hashes": {"metrics_matrix.csv": "4" * 64},
            },
        ))

        def publication_state(*, publication_root: Path) -> dict:
            """Return official before/after or the isolated expected state."""
            if publication_root.name == "fault_matrix_source":
                return {
                    "active_publication_id": successor,
                    "mirror_hashes": {"metrics_matrix.csv": "4" * 64},
                }
            return next(states)

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(mock.patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-secret",
                    "SEC_CONTACT_EMAIL": "operator@axaxl.com",
                },
                clear=True,
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.validate_sec_identity",
                return_value=("axaxl", "operator@axaxl.com"),
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.validate_cutover_qualifications",
                return_value=QUALIFICATION,
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._validate_live_authority_roots",
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._run_live_sec_acquisition",
                return_value={
                    "receipt_id": "sha256:" + "5" * 64,
                    "receipt_path": "sec.json",
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.build_release_input_plan",
                return_value={
                    "release_input_plan_id": "sha256:" + "6" * 64
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._prepare_runs", return_value=prepared,
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.write_projection_batch_manifest",
                return_value={"batch_manifest_id": "sha256:" + "7" * 64},
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.write_projection_candidate",
                return_value={"compatibility_status": "PASS"},
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.build_projection_manifest",
                return_value={
                    "projection_manifest_id": "sha256:" + "2" * 64,
                    "publication_candidate_status": "PUBLISHABLE",
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._bind_live_strict_compatibility",
                return_value={
                    "attempts": [attempt],
                    "stability_receipt_id": "sha256:" + "8" * 64,
                    "stability_receipt_path": "/tmp/final-stability.json",
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._write_live_attempt_audit_closure",
                return_value={
                    "audit_closure_id": "sha256:" + "9" * 64,
                    "audit_closure_path": "/tmp/audit",
                    "portable_run_paths": {
                        "run:1": "/tmp/audit/runs/run-1",
                    },
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.publication_state_snapshot",
                side_effect=publication_state,
            ))
            import_legacy = stack.enter_context(mock.patch(
                "vnext.cutover.prepare_legacy_baseline_predecessor",
                return_value={"publication_id": predecessor},
            ))
            validate_publication = stack.enter_context(mock.patch(
                "vnext.cutover._write_cutover_publication_validation_receipt",
                return_value={"validation_receipt_id": "sha256:" + "a" * 64},
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover.prepare_publication_bundle",
                return_value={"publication_id": successor},
            ))
            latest = stack.enter_context(mock.patch(
                "vnext.cutover.write_latest_run_status",
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._write_staging_parity_receipt",
                return_value={
                    "receipt_id": "sha256:" + "b" * 64,
                    "receipt_path": "staging.json",
                    "legacy_invariant_migration_receipt_id": (
                        "sha256:" + "c" * 64
                    ),
                },
            ))
            fault_matrix = stack.enter_context(mock.patch(
                "vnext.cutover.run_cutover_publication_fault_matrix",
                return_value={
                    "status": "PASSED",
                    "fault_matrix_id": "sha256:" + "d" * 64,
                    "fault_receipt_references": [
                        {"fault_receipt_id": "sha256:" + "e" * 64},
                    ],
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._write_formal_cutover_receipt",
                return_value={
                    "receipt_id": "sha256:" + "f" * 64,
                    "receipt_path": "prepared.json",
                },
            ))
            stack.enter_context(mock.patch(
                "vnext.cutover._write_committed_cutover_receipt",
                return_value={
                    "receipt_id": "sha256:" + "0" * 64,
                    "receipt_path": "passed.json",
                },
            ))
            initial_chain = stack.enter_context(mock.patch(
                "vnext.cutover._commit_initial_publication_chain",
                return_value={
                    "active_pointer": {"publication_id": successor},
                },
            ))
            ordinary_commit = stack.enter_context(mock.patch(
                "vnext.cutover._commit_publication",
            ))
            publication_root = Path(directory) / "publication-root"
            result = run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=publication_root,
                execute_live=True,
                recorded_response_path=None,
                recorded_fixture_id=None,
                commit=True,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc="2026-08-06T00:00:01+00:00",
            )
        self.assertEqual("PUBLISHED", result["status"])
        self.assertEqual(predecessor, result["previous_publication_id"])
        self.assertEqual(
            "/tmp/audit/runs/run-1", result["live_attempts"][0]["run_dir"]
        )
        self.assertEqual(
            "/tmp/audit/receipts/live_reader_stability.json",
            result["live_stability_receipt_path"],
        )
        import_legacy.assert_called_once_with(
            publication_root=publication_root,
            repo_root=REPO_ROOT,
            legacy_root=REPO_ROOT,
        )
        self.assertEqual(
            predecessor,
            validate_publication.call_args.kwargs["previous_publication_id"],
        )
        self.assertEqual(
            successor,
            fault_matrix.call_args.kwargs[
                "prepared_successor_publication_id"
            ],
        )
        initial_chain.assert_called_once_with(
            publication_root=publication_root,
            legacy_predecessor_publication_id=predecessor,
            successor_publication_id=successor,
            committed_at_utc="2026-08-06T00:00:01+00:00",
        )
        ordinary_commit.assert_not_called()
        self.assertEqual(2, latest.call_count)

    def test_failed_postcommit_readback_never_writes_passed_receipt(
        self,
    ) -> None:
        """Verify every referenced closure before persisting PASSED."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "formal-root"
            root.mkdir()
            inputs = publication_inputs(
                root=root,
                tag="resume-dependency-failure",
                previous_publication_id=None,
            )
            manifest = prepare_publication_bundle(
                publication_root=root,
                **inputs,
            )
            commit_formal_fixture(
                publication_root=root,
                publication_id=str(manifest["publication_id"]),
                expected_active_publication_id=None,
                committed_at_utc="2026-08-06T00:00:00Z",
            )
            state = publication_state_snapshot(publication_root=root)
            workspace = Path(directory) / "caller-workspace"
            receipt_dir = workspace / "receipts"
            receipt_dir.mkdir(parents=True)
            body = {
                "schema_version": 1,
                "receipt_type": "FORMAL_VNEXT_CUTOVER",
                "status": "PREPARED",
                "commit_requested_at_utc": "2026-08-06T00:00:00Z",
                "release_input_plan_id": "sha256:" + "1" * 64,
                "batch_manifest_id": manifest["batch_manifest_id"],
                "sec_acquisition_receipt_id": "sha256:" + "2" * 64,
                "live_stability_receipt_id": "sha256:" + "3" * 64,
                "live_attempt_audit_closure_id": "sha256:" + "4" * 64,
                "qualification_id": "sha256:" + "5" * 64,
                "production_freeze_receipt_id": "sha256:" + "6" * 64,
                "second_layout_receipt_id": "sha256:" + "7" * 64,
                "holdout_receipt_id": "sha256:" + "8" * 64,
                "staging_parity_receipt_id": "sha256:" + "9" * 64,
                "legacy_invariant_migration_receipt_id": (
                    "sha256:" + "a" * 64
                ),
                "fault_matrix_id": "sha256:" + "b" * 64,
                "fault_injection_receipt_ids": ["sha256:" + "c" * 64],
                "publication_validation_receipt_id": manifest[
                    "validation_receipt_id"
                ],
                "initial_publication_id": None,
                "previous_publication_id": None,
                "publication_id": manifest["publication_id"],
                "expected_pointer_and_mirrors_after": state,
            }
            receipt = {**body, "receipt_id": content_hash(value=body)}
            atomic_write_json(
                path=receipt_dir / "formal_cutover_failure_first.json",
                value=receipt,
            )
            with self.assertRaises(CutoverError):
                _resume_committed_cutover(
                    repo_root=inputs["repo_root"],
                    workspace_dir=workspace,
                    publication_root=root,
                    committed_at_utc="2026-08-06T00:01:00Z",
                )
            official = (
                root
                / "outputs"
                / "vnext_cutover_audits"
                / "receipts"
            )
            committed = (
                list(official.glob("formal_cutover_committed_*.json"))
                if official.exists()
                else []
            )
        self.assertEqual([], committed)

    def test_blocked_cli_returns_stable_nonzero_error(self) -> None:
        """Prevent a compatibility blocker from looking like CLI success."""
        from tools import vnext_cutover

        standard_output = io.StringIO()
        standard_error = io.StringIO()
        with mock.patch(
            "tools.vnext_cutover._execute",
            return_value={"status": "BLOCKED", "publication_id": None},
        ), redirect_stdout(standard_output), redirect_stderr(standard_error):
            return_code = vnext_cutover.main(argv=["--json"])
        payload = json.loads(standard_output.getvalue())
        self.assertEqual(2, return_code)
        self.assertFalse(payload["ok"])
        self.assertEqual("CUTOVER_CANDIDATE_BLOCKED", payload["error"]["code"])
        self.assertEqual("", standard_error.getvalue())

    def test_live_attempt_audit_survives_workspace_removal(
        self,
    ) -> None:
        """Keep three successes and a failed retry after workspace removal."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "mutable-workspace"
            publication_root = root / "formal-root"
            attempts = []
            for ordinal, status in (
                (1, "FAILED"),
                (2, "FROZEN"),
                (3, "FROZEN"),
                (4, "FROZEN"),
            ):
                run_dir = workspace / "runs" / str(ordinal)
                attempt = audit_attempt(
                    run_dir=run_dir, ordinal=ordinal, status=status,
                )
                atomic_write_json(
                    path=run_dir / "manifest.json",
                    value={
                        "run_id": attempt["run_id"],
                        "status": status,
                        "content_manifest_hash": attempt[
                            "run_content_manifest_hash"
                        ],
                        "audit_manifest_hash": attempt[
                            "run_audit_manifest_hash"
                        ],
                    },
                )
                atomic_write_bytes(
                    path=run_dir / "attempt_payloads" / "response.bin",
                    content="response-{}".format(ordinal).encode("utf-8"),
                )
                attempts.append(attempt)
            stability = _write_live_stability_receipt(
                workspace_dir=workspace,
                release_input_plan_id="sha256:" + "e" * 64,
                retry_policy={"retry_count": 2},
                cutover_qualification=QUALIFICATION,
                attempts=attempts,
                status="PASSED",
            )

            def load_terminal_run(*, run_dir: Path, repo_root: Path) -> tuple:
                """Read the copied manifest as the terminal Run authority."""
                del repo_root
                return strict_json_file(
                    path=run_dir / "manifest.json"
                ), [], []

            with mock.patch(
                "vnext.cutover.load_run_for_status",
                side_effect=load_terminal_run,
            ):
                closure = _write_live_attempt_audit_closure(
                    publication_root=publication_root,
                    repo_root=root,
                    attempts=attempts,
                    stability_receipt_id=stability[
                        "stability_receipt_id"
                    ],
                    stability_receipt_path=Path(
                        stability["stability_receipt_path"]
                    ),
                )
                shutil.rmtree(workspace)
                verified = _verify_live_attempt_audit_closure(
                    closure_dir=Path(closure["audit_closure_path"]),
                    repo_root=root,
                )
                first_file = Path(closure["audit_closure_path"]) / str(
                    verified["files"][0]["path"]
                )
                atomic_write_bytes(path=first_file, content=b"tampered\n")
                with self.assertRaises(CutoverError) as raised:
                    _verify_live_attempt_audit_closure(
                        closure_dir=Path(closure["audit_closure_path"]),
                        repo_root=root,
                    )
        self.assertEqual(closure["audit_closure_id"], verified[
            "audit_closure_id"
        ])
        self.assertEqual(4, len(verified["run_bindings"]))
        self.assertEqual(4, len(closure["portable_run_paths"]))
        self.assertFalse(workspace.exists())
        self.assertEqual(
            "LIVE_AUDIT_CLOSURE_INVALID", raised.exception.code
        )

    def test_sec_children_exclude_openai_key_and_keep_sec_identity(
        self,
    ) -> None:
        """Keep OpenAI authority out of every SEC-only child process."""
        new_row = {
            "source_url": "https://www.sec.gov/test.json",
            "status_code": "200",
            "error": "",
            "content_sha256": "1" * 64,
            "repo_relative_path": "evidence/attempt/body.json",
            "headers_repo_relative_path": "evidence/attempt/headers.json",
            "accession": "",
            "document_name": "test.json",
        }
        states = (
            {"rows": [], "row_count": 0, "content_sha256": "0" * 64},
            {
                "rows": [new_row],
                "row_count": 1,
                "content_sha256": "2" * 64,
            },
        )
        completed = mock.Mock(returncode=0, stdout=b"ok", stderr=b"")
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "must-not-enter-sec-child",
                "SEC_CONTACT_EMAIL": "operator@axaxl.com",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover._request_ledger_state", side_effect=states,
        ), mock.patch(
            "vnext.cutover._live_acquisition_artifacts",
            return_value={
                "outputs/accession_materials_inventory.csv": {
                    "sha256": "3" * 64,
                    "size": 1,
                },
            },
        ), mock.patch(
            "vnext.cutover.request_log_attempt_id",
            return_value="request:attempt:" + "4" * 64,
        ), mock.patch(
            "vnext.cutover.subprocess.run", return_value=completed,
        ) as runner:
            root = Path(directory)
            _run_live_sec_acquisition(
                repo_root=root,
                workspace_dir=root / "artifacts/vnext/cutover",
                executed_at_utc="2026-08-06T00:00:00+00:00",
            )
        self.assertEqual(5, runner.call_count)
        for call in runner.call_args_list:
            environment = call.kwargs["env"]
            self.assertNotIn("OPENAI_API_KEY", environment)
            self.assertEqual(
                "operator@axaxl.com", environment["SEC_CONTACT_EMAIL"]
            )

    def test_stage05_inventory_is_required_by_live_artifact_binding(
        self,
    ) -> None:
        """Fail when Stage05 did not persist accession material inventory."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                "outputs/company_resolution.csv",
                "outputs/latest_filings_inventory.csv",
                "outputs/concept_inventory/company_companyfacts.csv",
            ):
                atomic_write_bytes(path=root / relative, content=b"x\n")
            with self.assertRaises(CutoverError) as raised:
                _live_acquisition_artifacts(repo_root=root)
        self.assertEqual(
            "SEC_ACQUISITION_OUTPUT_INVALID", raised.exception.code
        )

    def test_sec_stage_environment_drops_only_openai_authority(self) -> None:
        """Retain SEC contact while removing the unrelated API secret."""
        with mock.patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "secret",
                "SEC_CONTACT_EMAIL": "operator@axaxl.com",
                "PATH": "/usr/bin",
            },
            clear=True,
        ):
            environment = _sec_stage_environment()
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertEqual(
            "operator@axaxl.com", environment["SEC_CONTACT_EMAIL"]
        )
        self.assertEqual("/usr/bin", environment["PATH"])

    def test_human_and_failed_live_attempts_update_latest_only(
        self,
    ) -> None:
        """Expose both blockers while keeping commit unreachable."""
        pending_run = Path("/tmp/cutover-pending-run")
        failed_run = Path("/tmp/cutover-failed-run")
        plan = {"release_input_plan_id": "sha256:" + "1" * 64}
        common_patches = (
            mock.patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-secret",
                    "SEC_CONTACT_EMAIL": "operator@axaxl.com",
                },
                clear=True,
            ),
            mock.patch(
                "vnext.cutover.validate_sec_identity",
                return_value=("axaxl", "operator@axaxl.com"),
            ),
            mock.patch(
                "vnext.cutover.validate_cutover_qualifications",
                return_value=QUALIFICATION,
            ),
            mock.patch(
                "vnext.cutover._validate_live_authority_roots",
            ),
            mock.patch(
                "vnext.cutover._run_live_sec_acquisition",
                return_value={
                    "receipt_id": "sha256:" + "2" * 64,
                    "receipt_path": "sec.json",
                },
            ),
            mock.patch(
                "vnext.cutover.build_release_input_plan", return_value=plan,
            ),
        )
        for code, prepared, expected_run in (
            (
                "HUMAN_REVIEW_REQUIRED",
                {
                    "batch_run_dirs": [],
                    "live_attempts": [],
                    "pending_reviews": [{
                        "run_dir": str(pending_run),
                        "review_unit_hash": "sha256:" + "3" * 64,
                    }],
                    "live_stability_receipt_id": "sha256:" + "4" * 64,
                    "live_stability_receipt_path": "stability.json",
                },
                pending_run,
            ),
            (
                "LIVE_READER_RETRIES_EXHAUSTED",
                CutoverError(
                    code="LIVE_READER_RETRIES_EXHAUSTED",
                    message="failed",
                    details={"latest_run_dir": str(failed_run)},
                ),
                failed_run,
            ),
        ):
            with (
                self.subTest(code=code),
                tempfile.TemporaryDirectory() as value,
            ):
                entered = []
                try:
                    for patcher in common_patches:
                        entered.append(patcher.start())
                    preparation = mock.patch(
                        "vnext.cutover._prepare_runs",
                        side_effect=(
                            prepared
                            if isinstance(prepared, Exception)
                            else None
                        ),
                        return_value=(
                            prepared if isinstance(prepared, dict) else None
                        ),
                    )
                    preparation.start()
                    latest = mock.patch(
                        "vnext.cutover.write_latest_run_status"
                    )
                    latest_writer = latest.start()
                    commit = mock.patch("vnext.cutover._commit_publication")
                    committer = commit.start()
                    with self.assertRaises(CutoverError) as raised:
                        run_cutover(
                            repo_root=REPO_ROOT,
                            workspace_dir=Path(value) / "workspace",
                            legacy_snapshot_dir=REPO_ROOT / "outputs",
                            publication_root=REPO_ROOT,
                            execute_live=True,
                            recorded_response_path=None,
                            recorded_fixture_id=None,
                            commit=True,
                            validated_at_utc="2026-08-06T00:00:00+00:00",
                            committed_at_utc="2026-08-06T00:00:01+00:00",
                        )
                    self.assertEqual(code, raised.exception.code)
                    self.assertEqual(
                        expected_run,
                        latest_writer.call_args.kwargs["latest_run_dir"],
                    )
                    committer.assert_not_called()
                finally:
                    mock.patch.stopall()

    def test_blocked_live_candidate_updates_latest_and_preserves_active(
        self,
    ) -> None:
        """Record a strict-compatibility blocker without any formal commit."""
        previous = "publication_" + "1" * 64
        attempt_run = Path("/tmp/cutover-blocked-run")
        prepared = {
            "batch_run_dirs": [attempt_run],
            "live_attempts": [{
                "run_dir": str(attempt_run),
                "status": "FROZEN",
            }],
            "pending_reviews": [],
            "live_stability_receipt_id": "sha256:" + "2" * 64,
            "live_stability_receipt_path": "stability.json",
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-secret",
                "SEC_CONTACT_EMAIL": "operator@axaxl.com",
            },
            clear=True,
        ), mock.patch(
            "vnext.cutover.validate_sec_identity",
            return_value=("axaxl", "operator@axaxl.com"),
        ), mock.patch(
            "vnext.cutover.validate_cutover_qualifications",
            return_value=QUALIFICATION,
        ), mock.patch(
            "vnext.cutover._validate_live_authority_roots",
        ), mock.patch(
            "vnext.cutover._run_live_sec_acquisition",
            return_value={
                "receipt_id": "sha256:" + "3" * 64,
                "receipt_path": "sec.json",
            },
        ), mock.patch(
            "vnext.cutover.build_release_input_plan",
            return_value={"release_input_plan_id": "sha256:" + "4" * 64},
        ), mock.patch(
            "vnext.cutover._prepare_runs", return_value=prepared,
        ), mock.patch(
            "vnext.cutover.write_projection_batch_manifest",
            return_value={"batch_manifest_id": "sha256:" + "5" * 64},
        ), mock.patch(
            "vnext.cutover.write_projection_candidate",
            return_value={"compatibility_status": "FAIL"},
        ), mock.patch(
            "vnext.cutover.build_projection_manifest",
            return_value={
                "projection_manifest_id": "sha256:" + "6" * 64,
                "publication_candidate_status": "BLOCKED",
            },
        ), mock.patch(
            "vnext.cutover.publication_state_snapshot",
            return_value={
                "active_publication_id": previous,
                "mirror_hashes": {},
            },
        ), mock.patch(
            "vnext.cutover.write_latest_run_status",
        ) as latest, mock.patch(
            "vnext.cutover._commit_publication",
        ) as committer:
            result = run_cutover(
                repo_root=REPO_ROOT,
                workspace_dir=Path(directory) / "workspace",
                legacy_snapshot_dir=REPO_ROOT / "outputs",
                publication_root=REPO_ROOT,
                execute_live=True,
                recorded_response_path=None,
                recorded_fixture_id=None,
                commit=True,
                validated_at_utc="2026-08-06T00:00:00+00:00",
                committed_at_utc="2026-08-06T00:00:01+00:00",
            )
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual(previous, result["previous_publication_id"])
        self.assertEqual(
            attempt_run, latest.call_args.kwargs["latest_run_dir"]
        )
        committer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
