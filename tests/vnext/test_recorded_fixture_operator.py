"""Recorded fixture discovery and cold-start operator failure-first tests."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tools import vnext_cutover, vnext_operator
from vnext.publication import PublicationView
from vnext.publication import publication_state_snapshot
from vnext.recorded_fixtures import CATALOG_RELATIVE_PATH
from vnext.recorded_fixtures import RecordedFixtureError
from vnext.recorded_fixtures import load_recorded_fixture
from vnext.run_store import load_open_run


FIXTURE_ID = "marriott-2025-real-layout-v1"


def run_operator(*arguments: str) -> tuple[int, str, str]:
    """Execute the public operator while capturing its stable envelope.

    Args:
        arguments: CLI tokens excluding the interpreter and script.

    Returns:
        Return code, stdout, and stderr.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with contextlib.redirect_stderr(stderr):
            return_code = vnext_operator.main(argv=list(arguments))
    return return_code, stdout.getvalue(), stderr.getvalue()


def run_cutover_cli(*arguments: str) -> tuple[int, str, str]:
    """Execute the public Cutover CLI while capturing its stable envelope.

    Args:
        arguments: CLI tokens excluding the interpreter and script.

    Returns:
        Return code, stdout, and stderr.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with contextlib.redirect_stderr(stderr):
            return_code = vnext_cutover.main(argv=list(arguments))
    return return_code, stdout.getvalue(), stderr.getvalue()


class RecordedFixtureOperatorTest(unittest.TestCase):
    """Prove cold-start discovery never accepts caller business authority."""

    def test_fixture_list_and_show_return_copyable_commands(self) -> None:
        """Discover the checked-in fixture without reading source or tests."""
        return_code, stdout, stderr = run_operator(
            "--json", "fixture", "list",
        )
        self.assertEqual(0, return_code, stderr)
        listed = json.loads(stdout)["result"]
        self.assertGreaterEqual(listed["fixture_count"], 1)
        fixture = next(
            item
            for item in listed["fixtures"]
            if item["fixture_id"] == FIXTURE_ID
        )
        self.assertIn("prepare --fixture-id", fixture["prepare_command"])
        self.assertIn(
            "tools/vnext_cutover.py", fixture["cutover_command"],
        )
        self.assertNotIn("--recorded-response", fixture["prepare_command"])

        return_code, stdout, stderr = run_operator(
            "--json", "fixture", "show", "--fixture-id", FIXTURE_ID,
        )
        self.assertEqual(0, return_code, stderr)
        shown = json.loads(stdout)["result"]
        self.assertEqual(FIXTURE_ID, shown["fixture"]["fixture_id"])
        self.assertRegex(
            shown["fixture"]["fixture_binding_id"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertFalse(
            Path(shown["fixture"]["source"]["repo_relative_path"])
            .is_absolute()
        )

    def test_fixture_prepare_is_socket_zero_and_creates_real_open_run(
        self,
    ) -> None:
        """Create the production review graph without caller source fields."""
        ignored_root = REPO_ROOT / "artifacts" / "vnext" / "runs" / "open"
        ignored_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="fixture-operator-", dir=ignored_root,
        ) as directory, mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("recorded fixture opened a socket"),
        ):
            run_dir = Path(directory) / "run"
            return_code, stdout, stderr = run_operator(
                "--json",
                "prepare",
                "--fixture-id",
                FIXTURE_ID,
                "--run-dir",
                str(run_dir),
                "--run-id",
                "run:recorded:fixture-operator-test",
            )
            self.assertEqual(0, return_code, stderr)
            result = json.loads(stdout)["result"]
            self.assertEqual("PENDING_HUMAN_REVIEW", result["status"])
            self.assertEqual(
                FIXTURE_ID, result["recorded_fixture"]["fixture_id"],
            )
            manifest, _records, decisions = load_open_run(run_dir=run_dir)
        self.assertEqual("OPEN", manifest["status"])
        self.assertEqual([], decisions)

    def test_fixture_prepare_rejects_caller_business_override(self) -> None:
        """Reject an attempt to replace catalog-derived company authority."""
        return_code, stdout, stderr = run_operator(
            "--json",
            "prepare",
            "--fixture-id",
            FIXTURE_ID,
            "--company-id",
            "caller_override",
        )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
            json.loads(stdout)["error"]["code"],
        )
        self.assertNotIn("Traceback", stdout + stderr)

    def test_fixture_prepare_rejects_recorded_response_override(
        self,
    ) -> None:
        """Never bind a catalog identity to caller-selected response bytes."""
        fixture = load_recorded_fixture(
            repo_root=REPO_ROOT, fixture_id=FIXTURE_ID,
        )
        with mock.patch(
            "tools.vnext_operator.create_review_run",
            side_effect=AssertionError("mixed fixture authority reached Run"),
        ) as creator:
            return_code, stdout, stderr = run_operator(
                "--json",
                "prepare",
                "--fixture-id",
                FIXTURE_ID,
                "--recorded-response",
                str(REPO_ROOT / fixture["response"]["repo_relative_path"]),
            )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
            json.loads(stdout)["error"]["code"],
        )
        creator.assert_not_called()
        self.assertNotIn("Traceback", stdout + stderr)

    def test_fixture_prepare_rejects_formal_workspace_before_run_write(
        self,
    ) -> None:
        """Keep fixture Run bytes below the recorded artifact namespace."""
        forbidden = (
            REPO_ROOT
            / "outputs"
            / "recorded-fixture-run-authority-negative-test"
        )
        self.assertFalse(forbidden.exists())
        with mock.patch(
            "tools.vnext_operator.create_review_run",
            side_effect=AssertionError(
                "unsafe Run workspace reached workflow"
            ),
        ) as creator:
            return_code, stdout, stderr = run_operator(
                "--json",
                "prepare",
                "--fixture-id",
                FIXTURE_ID,
                "--run-dir",
                str(forbidden),
            )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "RECORDED_FIXTURE_WORKSPACE_INVALID",
            json.loads(stdout)["error"]["code"],
        )
        creator.assert_not_called()
        self.assertFalse(forbidden.exists())
        self.assertNotIn("Traceback", stdout + stderr)

    def test_fixture_prepare_rejects_workspace_symlink_before_run_write(
        self,
    ) -> None:
        """Reject a fixture Run path aliased out of artifacts/vnext."""
        sandbox_parent = REPO_ROOT / "artifacts" / "vnext"
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        forbidden_parent = REPO_ROOT / "outputs"
        with tempfile.TemporaryDirectory(
            prefix="recorded-run-authority-", dir=sandbox_parent,
        ) as directory, tempfile.TemporaryDirectory(
            prefix="recorded-run-target-", dir=forbidden_parent,
        ) as target_directory:
            linked = Path(directory) / "linked"
            linked.symlink_to(
                Path(target_directory), target_is_directory=True,
            )
            with mock.patch(
                "tools.vnext_operator.create_review_run",
                side_effect=AssertionError(
                    "symlinked Run workspace reached workflow"
                ),
            ) as creator:
                return_code, stdout, stderr = run_operator(
                    "--json",
                    "prepare",
                    "--fixture-id",
                    FIXTURE_ID,
                    "--run-dir",
                    str(linked / "run"),
                )
            self.assertEqual(2, return_code, stderr)
            self.assertEqual(
                "RECORDED_FIXTURE_WORKSPACE_INVALID",
                json.loads(stdout)["error"]["code"],
            )
            creator.assert_not_called()
            self.assertEqual([], list(Path(target_directory).iterdir()))
            self.assertNotIn("Traceback", stdout + stderr)

    def test_fixture_id_path_traversal_has_stable_json_error(self) -> None:
        """Reject traversal before resolving any repository fixture bytes."""
        return_code, stdout, stderr = run_operator(
            "--json", "fixture", "show", "--fixture-id", "../escape",
        )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "RECORDED_FIXTURE_ID_INVALID",
            json.loads(stdout)["error"]["code"],
        )
        self.assertNotIn("Traceback", stdout + stderr)

    def test_fixture_response_tamper_fails_before_adapter_creation(
        self,
    ) -> None:
        """Reject changed recorded bytes against repository fixture hashes."""
        fixture = load_recorded_fixture(
            repo_root=REPO_ROOT, fixture_id=FIXTURE_ID,
        )
        relatives = (
            CATALOG_RELATIVE_PATH.as_posix(),
            fixture["provenance"]["repo_relative_path"],
            fixture["source"]["repo_relative_path"],
            fixture["response"]["repo_relative_path"],
            fixture["excerpt"]["repo_relative_path"],
            fixture["disclosure"]["spec_path"],
        )
        with tempfile.TemporaryDirectory() as directory:
            copied_root = Path(directory)
            for relative in relatives:
                destination = copied_root / str(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / str(relative), destination)
            response_path = (
                copied_root
                / str(fixture["response"]["repo_relative_path"])
            )
            response_path.write_bytes(response_path.read_bytes() + b"\n")
            with self.assertRaises(RecordedFixtureError) as raised:
                load_recorded_fixture(
                    repo_root=copied_root, fixture_id=FIXTURE_ID,
                )
        self.assertEqual(
            "RECORDED_FIXTURE_BYTES_INVALID", raised.exception.code,
        )

    def test_cutover_fixture_shortcut_passes_only_verified_response(
        self,
    ) -> None:
        """Resolve the public Cutover shortcut from the same fixed catalog."""
        expected = load_recorded_fixture(
            repo_root=REPO_ROOT, fixture_id=FIXTURE_ID,
        )
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            return_value={"status": "PASSED_RECORDED_ONLY"},
        ) as runner, mock.patch(
            "tools.vnext_cutover._complete_recorded_sandbox_publication",
            return_value={"publication_id": "publication_" + "e" * 64},
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    return_code = vnext_cutover.main(
                        argv=["--json", "--fixture-id", FIXTURE_ID]
                    )
        self.assertEqual(0, return_code, stderr.getvalue())
        call = runner.call_args.kwargs
        self.assertEqual(
            REPO_ROOT / expected["response"]["repo_relative_path"],
            call["recorded_response_path"],
        )
        self.assertEqual(
            expected["fixture_binding_id"], call["recorded_fixture_id"],
        )
        result = json.loads(stdout.getvalue())["result"]
        self.assertEqual(
            expected["fixture_binding_id"],
            result["recorded_fixture"]["fixture_binding_id"],
        )

    def test_cutover_fixture_rejects_recorded_response_override(
        self,
    ) -> None:
        """Reject mixed fixture/caller response authority before workflow."""
        fixture = load_recorded_fixture(
            repo_root=REPO_ROOT, fixture_id=FIXTURE_ID,
        )
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            side_effect=AssertionError(
                "mixed fixture authority reached Cutover"
            ),
        ) as runner:
            return_code, stdout, stderr = run_cutover_cli(
                "--json",
                "--fixture-id",
                FIXTURE_ID,
                "--recorded-response",
                str(REPO_ROOT / fixture["response"]["repo_relative_path"]),
            )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
            json.loads(stdout)["error"]["code"],
        )
        runner.assert_not_called()
        self.assertNotIn("Traceback", stdout + stderr)

    def test_cutover_rejects_standalone_recorded_response_override(
        self,
    ) -> None:
        """Reject caller response authority even without a fixture identity."""
        fixture = load_recorded_fixture(
            repo_root=REPO_ROOT, fixture_id=FIXTURE_ID,
        )
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            side_effect=AssertionError(
                "standalone caller response reached Cutover"
            ),
        ) as runner:
            return_code, stdout, stderr = run_cutover_cli(
                "--json",
                "--recorded-response",
                str(REPO_ROOT / fixture["response"]["repo_relative_path"]),
            )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "RECORDED_FIXTURE_OVERRIDE_FORBIDDEN",
            json.loads(stdout)["error"]["code"],
        )
        runner.assert_not_called()
        self.assertNotIn("Traceback", stdout + stderr)

    def test_cutover_live_rejects_fixture_before_network(self) -> None:
        """Keep a repository recorded fixture outside the live authority."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("invalid live fixture opened a socket"),
        ), contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                return_code = vnext_cutover.main(argv=[
                    "--json", "--execute-live", "--fixture-id", FIXTURE_ID,
                ])
        self.assertEqual(2, return_code, stderr.getvalue())
        self.assertEqual(
            "LIVE_RECORDED_INPUT_FORBIDDEN",
            json.loads(stdout.getvalue())["error"]["code"],
        )
        self.assertNotIn("Traceback", stdout.getvalue() + stderr.getvalue())

    def test_live_cutover_rejects_workspace_override_before_any_write(
        self,
    ) -> None:
        """Keep live authority at the fixed repository-owned workspace."""
        forbidden = (
            REPO_ROOT
            / "artifacts"
            / "vnext"
            / "live-caller-workspace-negative-test"
        )
        self.assertFalse(forbidden.exists())
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            side_effect=AssertionError("live override reached workflow"),
        ) as runner:
            return_code, stdout, stderr = run_cutover_cli(
                "--json",
                "--execute-live",
                "--workspace-dir",
                str(forbidden),
            )
        self.assertEqual(2, return_code, stderr)
        self.assertEqual(
            "LIVE_WORKSPACE_OVERRIDE_FORBIDDEN",
            json.loads(stdout)["error"]["code"],
        )
        runner.assert_not_called()
        self.assertFalse(forbidden.exists())
        self.assertNotIn("Traceback", stdout + stderr)

    def test_cutover_fixture_rejects_formal_workspace_before_any_write(
        self,
    ) -> None:
        """Reject a formal namespace before invoking the shared workflow."""
        forbidden = (
            REPO_ROOT
            / "outputs"
            / "publications"
            / "recorded-fixture-authority-negative-test"
        )
        self.assertFalse(forbidden.exists())
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            side_effect=AssertionError("unsafe workspace reached workflow"),
        ) as runner, contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                return_code = vnext_cutover.main(argv=[
                    "--json",
                    "--fixture-id",
                    FIXTURE_ID,
                    "--workspace-dir",
                    str(forbidden),
                ])
        self.assertEqual(2, return_code, stderr.getvalue())
        self.assertEqual(
            "RECORDED_SANDBOX_WORKSPACE_INVALID",
            json.loads(stdout.getvalue())["error"]["code"],
        )
        runner.assert_not_called()
        self.assertFalse(forbidden.exists())
        self.assertNotIn("Traceback", stdout.getvalue() + stderr.getvalue())

    def test_cutover_fixture_rejects_every_formal_namespace_before_write(
        self,
    ) -> None:
        """Keep caller-selected recorded work out of formal namespaces."""
        formal_roots = (
            REPO_ROOT / "artifacts/vnext/cutover",
            REPO_ROOT / "artifacts/vnext/qualification",
            REPO_ROOT / "artifacts/vnext/publications",
            REPO_ROOT / "artifacts/vnext/live_audit",
            REPO_ROOT / "artifacts/vnext/runs",
        )

        def exact_tree(*, root: Path) -> dict[str, object]:
            """Capture exact directory and regular-file bytes for one root."""
            if not root.exists():
                return {"exists": False, "directories": (), "files": {}}
            directories = []
            files = {}
            for path in sorted((root, *root.rglob("*"))):
                relative = path.relative_to(root).as_posix()
                if path.is_dir():
                    directories.append(relative)
                elif path.is_file():
                    files[relative] = path.read_bytes()
                else:
                    files[relative] = b"UNSAFE_ENTRY"
            return {
                "exists": True,
                "directories": tuple(directories),
                "files": files,
            }

        for formal_root in formal_roots:
            with self.subTest(formal_root=formal_root):
                workspace = formal_root / (
                    "recorded-formal-namespace-negative-test"
                )
                self.assertFalse(workspace.exists())
                before = exact_tree(root=formal_root)

                def unsafe_runner(**arguments: object) -> dict[str, object]:
                    """Model the first downstream write if preflight is absent."""
                    selected = Path(str(arguments["workspace_dir"]))
                    selected.mkdir(parents=True, exist_ok=True)
                    (selected / "unsafe-recorded-byte").write_bytes(b"unsafe\n")
                    raise AssertionError("formal workspace reached workflow")

                try:
                    with mock.patch(
                        "tools.vnext_cutover.run_cutover",
                        side_effect=unsafe_runner,
                    ) as runner:
                        return_code, stdout, stderr = run_cutover_cli(
                            "--json",
                            "--fixture-id",
                            FIXTURE_ID,
                            "--workspace-dir",
                            str(workspace),
                        )
                    after = exact_tree(root=formal_root)
                finally:
                    if workspace.exists():
                        shutil.rmtree(workspace)
                    if before["exists"] is False and formal_root.exists():
                        formal_root.rmdir()
                self.assertEqual(2, return_code, stderr)
                self.assertEqual(
                    "RECORDED_SANDBOX_WORKSPACE_INVALID",
                    json.loads(stdout)["error"]["code"],
                )
                runner.assert_not_called()
                self.assertEqual(before, after)
                self.assertNotIn("Traceback", stdout + stderr)

    def test_cutover_fixture_rejects_workspace_symlink_before_write(
        self,
    ) -> None:
        """Reject a symlink component without writing through its target."""
        sandbox_parent = REPO_ROOT / "artifacts" / "vnext"
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="recorded-workspace-authority-", dir=sandbox_parent,
        ) as directory:
            authority = Path(directory)
            target = authority / "target"
            target.mkdir()
            linked = authority / "linked"
            linked.symlink_to(target, target_is_directory=True)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch(
                "tools.vnext_cutover.run_cutover",
                side_effect=AssertionError("symlink reached workflow"),
            ) as runner, contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    return_code = vnext_cutover.main(argv=[
                        "--json",
                        "--fixture-id",
                        FIXTURE_ID,
                        "--workspace-dir",
                        str(linked / "workspace"),
                    ])
            self.assertEqual(2, return_code, stderr.getvalue())
            self.assertEqual(
                "RECORDED_SANDBOX_WORKSPACE_INVALID",
                json.loads(stdout.getvalue())["error"]["code"],
            )
            runner.assert_not_called()
            self.assertEqual([], list(target.iterdir()))
            self.assertNotIn(
                "Traceback", stdout.getvalue() + stderr.getvalue(),
            )

    def test_recorded_cutover_commits_and_reads_back_only_sandbox_view(
        self,
    ) -> None:
        """Complete recorded publication without touching formal authority."""
        recorded_result = {
            "status": "PASSED_RECORDED_ONLY",
            "batch_manifest_path": (
                "artifacts/vnext/recorded-cutover/batch.json"
            ),
            "staging_dir": "artifacts/vnext/recorded-cutover/staging",
        }
        sandbox_result = {
            "publication_id": "publication_" + "a" * 64,
            "pointer_sha256": "b" * 64,
            "readback_hashes": {
                "metrics_matrix.csv": "c" * 64,
            },
            "publication_root": (
                "artifacts/vnext/recorded-cutover/recorded-publication"
            ),
        }
        formal_before = {
            "active_publication_id": None,
            "mirror_hashes": {"metrics_matrix.csv": "d" * 64},
        }
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            return_value=recorded_result,
        ), mock.patch(
            "tools.vnext_cutover.publication_state_snapshot",
            return_value=formal_before,
            create=True,
        ), mock.patch(
            "tools.vnext_cutover._complete_recorded_sandbox_publication",
            return_value=sandbox_result,
            create=True,
        ) as sandbox:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with contextlib.redirect_stderr(stderr):
                    return_code = vnext_cutover.main(argv=[
                        "--json",
                        "--fixture-id",
                        FIXTURE_ID,
                        "--validated-at-utc",
                        "2026-08-07T00:00:00Z",
                        "--committed-at-utc",
                        "2026-08-07T00:00:01Z",
                    ])
        self.assertEqual(0, return_code, stderr.getvalue())
        result = json.loads(stdout.getvalue())["result"]
        self.assertEqual(sandbox_result, result["recorded_publication"])
        call = sandbox.call_args.kwargs
        self.assertEqual(
            REPO_ROOT / "artifacts/vnext/recorded-cutover",
            call["workspace_dir"],
        )
        self.assertNotIn("publication_root", call)
        self.assertEqual(formal_before, call["formal_state_before"])
        self.assertEqual(
            "2026-08-07T00:00:01Z", call["committed_at_utc"],
        )

    def test_recorded_and_live_defaults_use_disjoint_workspaces(self) -> None:
        """Keep no-flag recorded bytes outside the live Cutover workspace."""
        with mock.patch(
            "tools.vnext_cutover.run_cutover",
            return_value={"status": "TEST_ONLY_LIVE_BOUNDARY"},
        ) as runner:
            return_code, _stdout, stderr = run_cutover_cli(
                "--json", "--execute-live",
            )
        self.assertEqual(0, return_code, stderr)
        self.assertEqual(
            REPO_ROOT / "artifacts/vnext/cutover",
            runner.call_args.kwargs["workspace_dir"],
        )

    def test_public_recorded_cold_start_review_resume_and_readback(
        self,
    ) -> None:
        """Exercise explicit test review and the real sandbox transaction."""
        sandbox_parent = REPO_ROOT / "artifacts" / "vnext"
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        formal_before = publication_state_snapshot(
            publication_root=REPO_ROOT,
        )
        with tempfile.TemporaryDirectory(
            prefix="recorded-publication-uat-", dir=sandbox_parent,
        ) as directory, mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("recorded UX opened a socket"),
        ):
            workspace = Path(directory)
            command = (
                "--json",
                "--debug",
                "--fixture-id",
                FIXTURE_ID,
                "--workspace-dir",
                str(workspace),
                "--validated-at-utc",
                "2026-08-07T00:10:00Z",
                "--committed-at-utc",
                "2026-08-07T00:10:01Z",
            )
            return_code, stdout, stderr = run_cutover_cli(*command)
            self.assertEqual(2, return_code, stderr)
            blocked = json.loads(stdout)["error"]
            self.assertEqual("HUMAN_REVIEW_REQUIRED", blocked["code"])
            pending = blocked["details"]["pending_reviews"]
            self.assertGreaterEqual(len(pending), 1)
            self.assertFalse(
                (workspace / "recorded-publication").exists()
            )

            # The public CLI call is an explicit test action, never a
            # production auto-approval or formal HUMAN acceptance receipt.
            for index, review in enumerate(pending):
                decided_at = "2026-08-07T00:11:{:02d}Z".format(index)
                review_code, review_stdout, review_stderr = run_operator(
                    "--json",
                    "review",
                    "decide",
                    "--run-dir",
                    str(review["run_dir"]),
                    "--review-unit-hash",
                    str(review["review_unit_hash"]),
                    "--decision",
                    "APPROVE",
                    "--reviewer-id",
                    "TEST_ONLY_EXPLICIT_REVIEW",
                    "--decided-at-utc",
                    decided_at,
                    "--reason",
                    (
                        "TEST_ONLY_EXPLICIT_REVIEW: explicit non-formal "
                        "recorded UX decision; not HUMAN acceptance evidence."
                    ),
                )
                self.assertEqual(0, review_code, review_stderr)
                decision = json.loads(review_stdout)["result"]
                self.assertEqual(
                    "TEST_ONLY_EXPLICIT_REVIEW", decision["reviewer_id"],
                )

            return_code, stdout, stderr = run_cutover_cli(*command)
            self.assertEqual(0, return_code, stderr + stdout)
            result = json.loads(stdout)["result"]
            self.assertEqual("PASSED_RECORDED_ONLY", result["status"])
            recorded = result["recorded_publication"]
            sandbox_root = REPO_ROOT / str(recorded["publication_root"])
            self.assertEqual(
                workspace / "recorded-publication", sandbox_root,
            )
            view = PublicationView.open(publication_root=sandbox_root)
            self.assertEqual(recorded["publication_id"], view.publication_id)
            sandbox_state = publication_state_snapshot(
                publication_root=sandbox_root,
            )
            self.assertEqual(
                recorded["publication_id"],
                sandbox_state["active_publication_id"],
            )
            self.assertEqual(
                recorded["readback_hashes"],
                sandbox_state["mirror_hashes"],
            )
            self.assertEqual(
                formal_before,
                publication_state_snapshot(publication_root=REPO_ROOT),
            )
        self.assertFalse(Path(directory).exists())
        self.assertEqual(
            formal_before,
            publication_state_snapshot(publication_root=REPO_ROOT),
        )


if __name__ == "__main__":
    unittest.main()
