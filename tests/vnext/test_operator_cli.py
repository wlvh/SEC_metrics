"""Formal vNext operator and HUMAN review CLI failure-first tests."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Iterator
from unittest import mock

from tests.vnext.common import REPO_ROOT, reader_response
from tests.vnext.test_replay import create_review_run
from tools import vnext_operator, vnext_review
from tools.vnext_review import ReviewCliError, append_human_decision
from tools.vnext_review import list_human_reviews, show_human_review
from vnext.canonical import sha256_file
from vnext.review import create_review_decision
from vnext.run_store import append_review_decision, load_open_run
from vnext.sources import raw_blob_record
from vnext.table_grid import build_table_grid


def run_operator(*arguments: str) -> tuple[int, str, str]:
    """Run the public operator main while capturing both output streams.

    Args:
        arguments: Exact CLI tokens excluding the interpreter and script.

    Returns:
        Return code, stdout, and stderr.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with contextlib.redirect_stderr(stderr):
            return_code = vnext_operator.main(argv=list(arguments))
    return return_code, stdout.getvalue(), stderr.getvalue()


def run_review(*arguments: str) -> tuple[int, str, str]:
    """Run the standalone review CLI while capturing both streams.

    Args:
        arguments: Exact CLI tokens excluding the interpreter and script.

    Returns:
        Return code, stdout, and stderr.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with contextlib.redirect_stderr(stderr):
            return_code = vnext_review.main(argv=list(arguments))
    return return_code, stdout.getvalue(), stderr.getvalue()


def prepare_arguments(*, directory: Path) -> list[str]:
    """Build one real recorded prepare command for the repository fixture.

    Args:
        directory: Temporary workspace receiving response bytes and the Run.

    Returns:
        Public operator argv using only repository-backed business inputs.
    """
    relative = "tests/fixtures/vnext/sample_lodging.html"
    raw = raw_blob_record(
        repo_root=REPO_ROOT,
        repo_relative_path=relative,
        media_type="text/html",
    )
    asset = build_table_grid(
        html_bytes=(REPO_ROOT / relative).read_bytes(),
        parent_raw_asset_ids=[str(raw["raw_asset_id"])],
        storage_uri="artifacts/vnext/derived/operator-fixture.json",
    )
    response_path = directory / "recorded_response.json"
    response_path.write_bytes(reader_response(asset=asset))
    return [
        "--json",
        "prepare",
        "--run-dir",
        str(directory / "run"),
        "--run-id",
        "run:operator:recorded:001",
        "--company-id",
        "marriott_international",
        "--fiscal-year",
        "2025",
        "--period-start",
        "2025-01-01",
        "--period-end",
        "2025-12-31",
        "--source-path",
        relative,
        "--source-media-type",
        "text/html",
        "--source-url",
        "https://www.sec.gov/Archives/sample.htm",
        "--accession",
        "0001048286-25-000001",
        "--document-name",
        "sample_lodging.html",
        "--source-role",
        "target_primary",
        "--request-attempt-id",
        "request:attempt:fixture",
        "--disclosure-spec-path",
        "catalog/disclosures/lodging_kpi_table.md",
        "--recorded-response",
        str(response_path),
    ]


def fixture_prepare_arguments(*, directory: Path) -> list[str]:
    """Build the supported catalog-backed recorded prepare command.

    Args:
        directory: Repository-owned recorded workspace parent.

    Returns:
        Public operator argv with no caller business or response authority.
    """
    return [
        "--json",
        "prepare",
        "--run-dir",
        str(directory / "run"),
        "--run-id",
        "run:operator:recorded:001",
        "--fixture-id",
        "marriott-2025-real-layout-v1",
    ]


@contextlib.contextmanager
def repository_recorded_workspace() -> Iterator[Path]:
    """Yield one temporary Run parent inside the required artifact namespace.

    Yields:
        Repository-owned directory removed with any parent created by this
        helper, so a clean checkout remains clean after the test.
    """
    artifacts_root = REPO_ROOT / "artifacts"
    vnext_root = artifacts_root / "vnext"
    artifacts_existed = artifacts_root.exists()
    vnext_existed = vnext_root.exists()
    vnext_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix="operator-cli-", dir=vnext_root,
        ) as directory:
            yield Path(directory)
    finally:
        if not vnext_existed and not any(vnext_root.iterdir()):
            vnext_root.rmdir()
        if not artifacts_existed and not any(artifacts_root.iterdir()):
            artifacts_root.rmdir()


class OperatorCliTest(unittest.TestCase):
    """Exercise the supported operator surface instead of test-only helpers."""

    def test_cold_start_publication_status_has_null_active(self) -> None:
        """Show latest/active separation before the first formal Cutover."""
        with tempfile.TemporaryDirectory() as directory:
            return_code, stdout, stderr = run_operator(
                "--json",
                "status",
                "--publication-root",
                directory,
            )
        self.assertEqual(0, return_code, stderr)
        status = json.loads(stdout)["result"]
        self.assertIsNone(status["active_publication_id"])
        self.assertIsNone(status["active_manifest"])
        self.assertIsNone(status["latest_run_status"])

    def test_live_prepare_checks_sec_identity_before_openai(self) -> None:
        """Reject a live Reader start before either network boundary opens."""
        with tempfile.TemporaryDirectory() as directory:
            arguments = prepare_arguments(directory=Path(directory))
            recorded_index = arguments.index("--recorded-response")
            del arguments[recorded_index:recorded_index + 2]
            arguments.append("--execute-live")
            environment = dict(os.environ)
            environment.pop("SEC_CONTACT_EMAIL", None)
            with mock.patch.dict(os.environ, environment, clear=True), mock.patch(
                "tools.vnext_operator.build_approved_transport_adapter",
                side_effect=AssertionError("OpenAI adapter built before SEC preflight"),
            ) as adapter_builder:
                return_code, stdout, stderr = run_operator(*arguments)
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "SEC_CONTACT_EMAIL_REQUIRED",
            json.loads(stdout)["error"]["code"],
        )
        adapter_builder.assert_not_called()

    def test_live_prepare_rejects_unbound_source_before_openai(self) -> None:
        """Reject caller-selected bytes absent from immutable SEC authority."""
        with tempfile.TemporaryDirectory() as directory:
            arguments = prepare_arguments(directory=Path(directory))
            recorded_index = arguments.index("--recorded-response")
            del arguments[recorded_index:recorded_index + 2]
            arguments.append("--execute-live")
            with mock.patch.dict(
                os.environ,
                {"SEC_CONTACT_EMAIL": "operator@axaxl.com"},
                clear=True,
            ), mock.patch(
                "vnext.workflow.run_ai_attempt",
                side_effect=AssertionError(
                    "Unbound source reached the OpenAI attempt boundary"
                ),
            ) as reader:
                return_code, stdout, stderr = run_operator(*arguments)
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "LIVE_SOURCE_AUTHORITY_INVALID",
            json.loads(stdout)["error"]["code"],
        )
        reader.assert_not_called()

    def test_publish_commit_cannot_bypass_formal_cutover_authority(
        self,
    ) -> None:
        """Reject a direct pointer commit through the generic operator CLI."""
        prepared = {
            "publication_id": "publication_" + "b" * 64,
        }
        with mock.patch(
            "tools.vnext_operator.write_publication_validation_receipt",
            return_value={"validation_receipt_id": "sha256:" + "c" * 64},
        ) as receipt_writer, mock.patch(
            "tools.vnext_operator.prepare_publication_bundle",
            return_value=prepared,
        ) as preparer:
            return_code, stdout, stderr = run_operator(
                "--json",
                "publish",
                "--publication-root",
                "/tmp/publication-root",
                "--batch-manifest",
                "/tmp/batch.json",
                "--legacy-snapshot-dir",
                "/tmp/legacy",
                "--staging-dir",
                "/tmp/staging",
                "--validated-at-utc",
                "2026-08-06T00:00:00Z",
                "--commit",
                "--committed-at-utc",
                "2026-08-06T00:00:01Z",
            )
        self.assertEqual(2, return_code, stderr)
        payload = json.loads(stdout)
        self.assertEqual(
            "FORMAL_COMMIT_REQUIRES_CUTOVER",
            payload["error"]["code"],
        )
        self.assertEqual(
            "tools/vnext_cutover.py --execute-live",
            payload["error"]["details"]["required_entrypoint"],
        )
        receipt_writer.assert_not_called()
        preparer.assert_not_called()
        self.assertFalse(hasattr(vnext_operator, "commit_publication"))

    def test_publish_without_commit_prepares_inactive_recorded_bundle(
        self,
    ) -> None:
        """Keep generic publication preparation without active mutation."""
        receipt = {"validation_receipt_id": "sha256:" + "c" * 64}
        prepared = {"publication_id": "publication_" + "b" * 64}
        with mock.patch(
            "tools.vnext_operator.write_publication_validation_receipt",
            return_value=receipt,
        ) as receipt_writer, mock.patch(
            "tools.vnext_operator.prepare_publication_bundle",
            return_value=prepared,
        ) as preparer:
            return_code, stdout, stderr = run_operator(
                "--json",
                "publish",
                "--publication-root",
                "/tmp/publication-root",
                "--batch-manifest",
                "/tmp/batch.json",
                "--legacy-snapshot-dir",
                "/tmp/legacy",
                "--staging-dir",
                "/tmp/staging",
                "--validated-at-utc",
                "2026-08-06T00:00:00Z",
            )
        self.assertEqual(0, return_code, stderr)
        result = json.loads(stdout)["result"]
        self.assertEqual(prepared["publication_id"], result["publication_id"])
        self.assertIsNone(result["committed_pointer"])
        receipt_writer.assert_called_once()
        preparer.assert_called_once()

    def test_command_surface_contains_every_formal_operation(self) -> None:
        """Expose the complete supported lifecycle from one parser."""
        help_text = vnext_operator.build_parser().format_help()
        for command in (
            "prepare",
            "status",
            "review",
            "resume",
            "finalize",
            "replay",
            "project",
            "publish",
            "rollback",
            "restore",
            "acceptance",
        ):
            self.assertIn(command, help_text)
        parser = vnext_operator.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action.choices, dict)
            and "publish" in action.choices
        )
        publish_help = subparsers.choices["publish"].format_help()
        self.assertIn(
            "tools/vnext_cutover.py --execute-live", publish_help
        )
        for action in ("list", "show", "decide"):
            parsed = parser.parse_args(
                ["review", action, "--run-dir", "/tmp/run"]
                + (
                    ["--review-unit-hash", "sha256:" + "a" * 64]
                    if action == "show"
                    else []
                )
                + (
                    [
                        "--review-unit-hash",
                        "sha256:" + "a" * 64,
                        "--decision",
                        "APPROVE",
                        "--reviewer-id",
                        "human:operator:001",
                        "--decided-at-utc",
                        "2026-08-06T00:00:00Z",
                        "--reason",
                        "Reviewed exact context.",
                    ]
                    if action == "decide"
                    else []
                )
            )
            self.assertEqual(action, parsed.review_action)

    def test_recorded_prepare_status_list_and_show_use_real_run(self) -> None:
        """Create and inspect one OPEN Run through only public CLI commands."""
        with repository_recorded_workspace() as root:
            with mock.patch(
                "socket.socket",
                side_effect=AssertionError("recorded mode opened a socket"),
            ):
                return_code, stdout, stderr = run_operator(
                    *fixture_prepare_arguments(directory=root)
                )
            self.assertEqual(0, return_code, stderr)
            prepared = json.loads(stdout)
            self.assertEqual(
                "PENDING_HUMAN_REVIEW", prepared["result"]["status"]
            )
            run_dir = root / "run"

            return_code, stdout, stderr = run_operator(
                "--json", "status", "--run-dir", str(run_dir)
            )
            self.assertEqual(0, return_code, stderr)
            self.assertEqual("OPEN", json.loads(stdout)["result"]["status"])

            return_code, stdout, stderr = run_operator(
                "--json", "review", "list", "--run-dir", str(run_dir)
            )
            self.assertEqual(0, return_code, stderr)
            listed = json.loads(stdout)["result"]
            self.assertEqual(1, len(listed["review_units"]))
            review_hash = listed["review_units"][0]["review_unit_hash"]

            return_code, stdout, stderr = run_operator(
                "--json",
                "review",
                "show",
                "--run-dir",
                str(run_dir),
                "--review-unit-hash",
                review_hash,
            )
            self.assertEqual(0, return_code, stderr)
            shown = json.loads(stdout)["result"]
            self.assertEqual(review_hash, shown["review_unit_hash"])
            self.assertIn("vNext HUMAN Review", shown["review_markdown"])

    def test_review_errors_are_stable_and_tip_is_recoverable(self) -> None:
        """Return machine codes and a copyable command without tracebacks."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            first = append_human_decision(
                run_dir=run_dir,
                review_unit_hash=str(created["review_unit_hash"]),
                decision="APPROVE",
                reviewer_id="human:operator:001",
                decided_at_utc="2026-08-06T00:00:00Z",
                reason="Reviewed exact context.",
                supersedes_decision_id=None,
            )
            return_code, stdout, stderr = run_operator(
                "--json",
                "review",
                "decide",
                "--run-dir",
                str(run_dir),
                "--review-unit-hash",
                str(created["review_unit_hash"]),
                "--decision",
                "REJECT",
                "--reviewer-id",
                "human:operator:001",
                "--decided-at-utc",
                "2026-08-06T00:01:00Z",
                "--reason",
                "Correcting the decision.",
                "--supersedes-decision-id",
                "sha256:" + "f" * 64,
            )
            self.assertEqual(2, return_code)
            self.assertEqual("", stderr)
            self.assertNotIn("Traceback", stdout)
            error = json.loads(stdout)["error"]
            self.assertEqual("SUPERSEDES_NOT_EFFECTIVE_TIP", error["code"])
            self.assertEqual(
                first["review_decision_id"],
                error["details"]["current_effective_tip"],
            )
            self.assertIn(
                "review decide", error["details"]["recovery_command"]
            )

            return_code, stdout, _stderr = run_operator(
                "--json",
                "review",
                "decide",
                "--run-dir",
                str(run_dir),
                "--review-unit-hash",
                str(created["review_unit_hash"]),
                "--decision",
                "APPROVE",
                "--reviewer-id",
                "human:operator:001",
                "--decided-at-utc",
                "2026-08-06T00:02:00Z",
                "--reason",
                "Duplicate approval.",
            )
            self.assertEqual(2, return_code)
            self.assertEqual(
                "DECISION_ALREADY_EFFECTIVE",
                json.loads(stdout)["error"]["code"],
            )

    def test_stale_context_rejected_before_decision_append(self) -> None:
        """Detect changed rendered bytes at the HUMAN decision boundary."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            review_path = (
                run_dir
                / "review"
                / str(created["review_unit_hash"])
                / "review.md"
            )
            review_path.write_bytes(review_path.read_bytes() + b"\nchanged\n")
            with self.assertRaises(ReviewCliError) as context:
                append_human_decision(
                    run_dir=run_dir,
                    review_unit_hash=str(created["review_unit_hash"]),
                    decision="APPROVE",
                    reviewer_id="human:operator:001",
                    decided_at_utc="2026-08-06T00:00:00Z",
                    reason="Should not append.",
                    supersedes_decision_id=None,
                )
            self.assertEqual("REVIEW_CONTEXT_STALE", context.exception.code)
            _manifest, _records, decisions = load_open_run(run_dir=run_dir)
            self.assertEqual([], decisions)

    def test_parallel_effective_decisions_fail_with_stable_code(self) -> None:
        """Reject a malformed two-root history without choosing one."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            _manifest, records, _decisions = load_open_run(run_dir=run_dir)
            unit = next(
                record
                for record in records
                if record["record_type"] == "REVIEW_UNIT"
            )
            for index, decision in enumerate(("APPROVE", "REJECT")):
                appended = create_review_decision(
                    review_unit=unit,
                    decision=decision,
                    approved_claims=(
                        dict(unit["required_claims"])
                        if decision == "APPROVE"
                        else {}
                    ),
                    required_claims=dict(unit["required_claims"]),
                    reviewer_id="human:operator:00{}".format(index + 1),
                    decided_at_utc="2026-08-06T00:0{}:00Z".format(index),
                    reason="Independent root.",
                    supersedes_decision_id=None,
                )
                append_review_decision(run_dir=run_dir, decision=appended)
            with self.assertRaises(ReviewCliError) as context:
                list_human_reviews(run_dir=run_dir)
            self.assertEqual(
                "PARALLEL_EFFECTIVE_DECISIONS", context.exception.code
            )
            self.assertEqual(
                str(created["review_unit_hash"]),
                context.exception.details["review_unit_hash"],
            )

    def test_finalize_requires_a_real_human_decision(self) -> None:
        """Require HUMAN input, then mechanically validate and freeze."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            return_code, stdout, stderr = run_operator(
                "--json", "finalize", "--run-dir", str(run_dir)
            )
            self.assertEqual(2, return_code)
            self.assertEqual("", stderr)
            error = json.loads(stdout)["error"]
            self.assertEqual("HUMAN_REVIEW_REQUIRED", error["code"])
            self.assertEqual(
                str(created["review_unit_hash"]),
                error["details"]["review_unit_hash"],
            )
            self.assertIn("review decide", error["details"]["review_command"])

        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            append_human_decision(
                run_dir=run_dir,
                review_unit_hash=str(created["review_unit_hash"]),
                decision="APPROVE",
                reviewer_id="human:operator:001",
                decided_at_utc="2026-08-06T00:00:00Z",
                reason="Reviewed exact context.",
                supersedes_decision_id=None,
            )
            return_code, stdout, stderr = run_operator(
                "--json", "finalize", "--run-dir", str(run_dir)
            )
            self.assertEqual(0, return_code, stderr)
            self.assertEqual(
                "FROZEN", json.loads(stdout)["result"]["status"]
            )
            validation = json.loads(
                (run_dir / "validation.json").read_text(encoding="utf-8")
            )
            self.assertEqual("PASSED", validation["status"])
            self.assertTrue(
                all(
                    check["status"] == "PASS"
                    for check in validation["checks"]
                )
            )

        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            append_human_decision(
                run_dir=run_dir,
                review_unit_hash=str(created["review_unit_hash"]),
                decision="APPROVE",
                reviewer_id="human:operator:001",
                decided_at_utc="2026-08-06T00:00:00Z",
                reason="Reviewed exact context.",
                supersedes_decision_id=None,
            )
            vnext_operator.finalize_reviewed_direct_results(
                run_dir=run_dir, repo_root=REPO_ROOT,
            )
            return_code, stdout, stderr = run_operator(
                "--json", "resume", "--run-dir", str(run_dir)
            )
            self.assertEqual(0, return_code, stderr)
            resumed = json.loads(stdout)["result"]
            self.assertEqual("FROZEN", resumed["status"])
            self.assertTrue(resumed["resumed_after_atomic_finalization"])

    def test_list_show_detect_missing_ambiguous_and_nonopen_runs(self) -> None:
        """Distinguish lookup and state failures with required stable codes."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            with self.assertRaises(ReviewCliError) as context:
                show_human_review(
                    run_dir=run_dir,
                    review_unit_hash="sha256:" + "f" * 64,
                )
            self.assertEqual("REVIEW_UNIT_NOT_FOUND", context.exception.code)

            records_path = run_dir / "records.jsonl"
            records = records_path.read_text(encoding="utf-8").splitlines()
            unit_line = next(
                line
                for line in records
                if json.loads(line)["record_type"] == "REVIEW_UNIT"
            )
            records_path.write_text(
                "\n".join([*records, unit_line]) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ReviewCliError) as context:
                show_human_review(
                    run_dir=run_dir,
                    review_unit_hash=str(created["review_unit_hash"]),
                )
            self.assertEqual(
                "REVIEW_UNIT_AMBIGUOUS", context.exception.code
            )

            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "FAILED"
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ReviewCliError) as context:
                list_human_reviews(run_dir=run_dir)
            self.assertEqual("RUN_NOT_OPEN", context.exception.code)
            self.assertEqual(
                str(created["run_id"]), context.exception.details["run_id"]
            )

    def test_debug_is_only_mode_that_emits_traceback(self) -> None:
        """Keep default errors concise while preserving diagnostics."""
        missing = "/definitely/missing/vnext/run"
        return_code, stdout, stderr = run_operator(
            "--json", "review", "list", "--run-dir", missing
        )
        self.assertEqual(2, return_code)
        self.assertNotIn("Traceback", stdout + stderr)

        return_code, stdout, stderr = run_operator(
            "--json", "--debug", "review", "list", "--run-dir", missing
        )
        self.assertEqual(2, return_code)
        self.assertIn("Traceback", stderr)
        self.assertEqual("RUN_NOT_OPEN", json.loads(stdout)["error"]["code"])

    def test_unexpected_cli_errors_hide_traceback_by_default(self) -> None:
        """Convert unexpected ordinary errors only at each CLI boundary."""
        with mock.patch(
            "tools.vnext_operator._execute",
            side_effect=RuntimeError("unexpected operator failure"),
        ):
            return_code, stdout, stderr = run_operator(
                "--json", "status", "--run-dir", "/tmp/unused"
            )
        self.assertEqual(2, return_code)
        self.assertNotIn("Traceback", stdout + stderr)
        self.assertEqual(
            "OPERATOR_COMMAND_FAILED", json.loads(stdout)["error"]["code"]
        )

        with mock.patch(
            "tools.vnext_review.list_human_reviews",
            side_effect=RuntimeError("unexpected review failure"),
        ):
            return_code, stdout, stderr = run_review(
                "list", "--run-dir", "/tmp/unused", "--json"
            )
        self.assertEqual(2, return_code)
        self.assertNotIn("Traceback", stdout + stderr)
        self.assertEqual(
            "REVIEW_COMMAND_FAILED", json.loads(stdout)["error"]["code"]
        )

    def test_restore_uses_verified_pointer_switch_primitive(self) -> None:
        """Restore through rollback semantics instead of an old producer."""
        pointer = {
            "publication_id": "publication_" + "b" * 64,
            "previous_publication_id": "publication_" + "a" * 64,
        }
        with mock.patch(
            "tools.vnext_operator.rollback_publication", return_value=pointer
        ) as rollback:
            return_code, stdout, stderr = run_operator(
                "--json",
                "restore",
                "--publication-root",
                "/tmp/publication-root",
                "--target-publication-id",
                "publication_" + "b" * 64,
                "--expected-active-publication-id",
                "publication_" + "a" * 64,
                "--committed-at-utc",
                "2026-08-06T00:00:00Z",
            )
        self.assertEqual(0, return_code, stderr)
        self.assertEqual(pointer, json.loads(stdout)["result"])
        rollback.assert_called_once_with(
            publication_root=Path("/tmp/publication-root"),
            target_publication_id="publication_" + "b" * 64,
            expected_active_publication_id="publication_" + "a" * 64,
            committed_at_utc="2026-08-06T00:00:00Z",
        )

    def test_review_show_reports_exact_bound_file_hashes(self) -> None:
        """Give the HUMAN the exact canonical and rendered bytes identities."""
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            created = create_review_run(run_dir=run_dir)
            shown = show_human_review(
                run_dir=run_dir,
                review_unit_hash=str(created["review_unit_hash"]),
            )
            self.assertEqual(
                shown["review_context_hash"],
                sha256_file(path=Path(shown["review_context_path"])),
            )
            self.assertEqual(
                shown["rendered_review_hash"],
                sha256_file(path=Path(shown["review_path"])),
            )


if __name__ == "__main__":
    unittest.main()
