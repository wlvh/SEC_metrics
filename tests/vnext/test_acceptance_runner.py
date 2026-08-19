"""Acceptance command-evidence and honest NOT_RUN status tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from functools import partial
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from sec_pipeline import build_readme
from validation_provenance import SourceSnapshot, ensure_readme_routes


TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import run_acceptance  # noqa: E402
from run_acceptance import (  # noqa: E402
    _offline_environment,
    _validated_live_attempt_audit,
    AcceptanceError,
    FAST_TEST_COMMAND,
    execute_acceptance,
    external_blockers,
    formal_evidence_binding,
    recorded_commands,
    run_command,
)
from sec_http import SecIdentityError, load_config  # noqa: E402
from vnext.canonical import content_hash  # noqa: E402
from vnext.canonical import sha256_file  # noqa: E402


PRODUCTION_AUTHORITY_BINDING = run_acceptance._acceptance_authority_binding


def run_public_acceptance_cli(*, repo_root, arguments):
    """Run the supported acceptance CLI against one isolated repository.

    Args:
        repo_root: Isolated repository authority passed to the public CLI.
        arguments: Additional public CLI arguments.

    Returns:
        Completed process with exact captured stdout and stderr.
    """
    environment = dict(os.environ)
    environment.pop("OPENAI_API_KEY", None)
    environment.pop("SEC_CONTACT_EMAIL", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/run_acceptance.py"),
            "--repo-root",
            str(repo_root),
            *arguments,
        ],
        cwd=str(REPO_ROOT),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def passed_command(**arguments):
    """Return one deterministic successful command receipt for plan tests.

    Args:
        arguments: Runner keyword arguments; only argv is reflected.

    Returns:
        Minimal command row compatible with receipt status aggregation.
    """
    argv = list(arguments["argv"])
    if "--output" in argv:
        output = Path(str(argv[argv.index("--output") + 1]))
        output.parent.mkdir(parents=True, exist_ok=True)
        if run_acceptance.TERMINAL_PUBLICATION_COMMAND in argv:
            publication_id = str(
                argv[argv.index("--expected-publication-id") + 1]
            )
            authority = {
                "outputs/active_publication.json": "a" * 64,
            }
            body = {
                "schema_version": 1,
                "status": "PASSED",
                "publication_id": publication_id,
                "active_pointer_sha256": "b" * 64,
                "source_commit": "c" * 40,
                "source_input_tree_sha256": "d" * 64,
                "gates": [
                    {
                        "gate_id": gate_id,
                        "outcome": "PASSED",
                        "details": {},
                    }
                    for gate_id in run_acceptance.TERMINAL_GATE_IDS
                ],
                "authority_hashes_before": authority,
                "authority_hashes_after": authority,
                "validation_snapshot_sha256": "e" * 64,
                "side_effects": {
                    "ai_socket_count": 0,
                    "sec_socket_count": 0,
                    "repair_count": 0,
                    "report_authoritative_write_count": 0,
                },
            }
            result = {
                **body,
                "terminal_cycle_id": content_hash(value=body),
            }
            output.write_text(
                json.dumps({"ok": True, "result": result}) + "\n",
                encoding="utf-8",
            )
        else:
            output.write_text("{}\n", encoding="utf-8")
    return {
        "argv": argv,
        "interpreter": str(arguments["argv"][0]),
        "outcome": "PASSED",
        "return_code": 0,
        "duration_ms": 1,
        "stdout_sha256": "0" * 64,
        "stdout_size": 0,
        "stderr_sha256": "0" * 64,
        "stderr_size": 0,
        "reason": "",
        "error_class": "",
        "environment_keys": sorted(arguments["environment"]),
    }


def failed_terminal_command(*, target, **arguments):
    """Fail one selected terminal gate in a mocked full run.

    Args:
        target: Exact report, Stage 12, or snapshot-checker path to fail.
        arguments: Runner keyword arguments containing the exact argv.

    Returns:
        Deterministic command evidence with one selected gate marked FAILED.
    """
    record = passed_command(**arguments)
    if target in record["argv"]:
        record["outcome"] = "FAILED"
        record["return_code"] = 1
        record["reason"] = "NONZERO_RETURN_CODE"
    return record


def publication_state(*, publication_id, marker):
    """Build one deterministic official pointer/mirror snapshot.

    Args:
        publication_id: Active publication identity.
        marker: Digest marker used to distinguish mirror generations.

    Returns:
        State compatible with the acceptance runner's read-back checks.
    """
    return {
        "active_publication_id": publication_id,
        "mirror_hashes": {"fixture": marker * 64},
    }


def cutover_envelope(*, previous_id, publication_id):
    """Return a successful formal Cutover public-CLI envelope.

    Args:
        previous_id: Committed predecessor.
        publication_id: Newly committed publication.

    Returns:
        Minimal structured result used before final byte binding.
    """
    return {
        "ok": True,
        "result": {
            "status": "PUBLISHED",
            "release_input_plan_id": "sha256:" + "3" * 64,
            "batch_manifest_id": "sha256:" + "4" * 64,
            "publication_id": publication_id,
            "previous_publication_id": previous_id,
            "validation_receipt_id": "sha256:" + "5" * 64,
        },
    }


def initial_cutover_envelope(*, previous_id, publication_id):
    """Return a first-Cutover envelope with imported legacy predecessor A.

    Args:
        previous_id: Newly imported legacy predecessor identity.
        publication_id: Newly committed formal publication identity.

    Returns:
        Structured public-CLI result proving the atomic A-to-B bootstrap.
    """
    envelope = cutover_envelope(
        previous_id=previous_id,
        publication_id=publication_id,
    )
    envelope["result"]["initial_publication_id"] = previous_id
    return envelope


def switch_envelope(*, command, publication_id, previous_id):
    """Return one successful rollback/restore operator envelope.

    Args:
        command: Operator subcommand.
        publication_id: Newly active target.
        previous_id: Publication switched away from.

    Returns:
        Structured public-CLI response.
    """
    return {
        "ok": True,
        "command": command,
        "result": {
            "publication_id": publication_id,
            "previous_publication_id": previous_id,
        },
    }


def recorded_evidence(*, state):
    """Build deterministic successful recorded-gate evidence.

    Args:
        state: Formal state observed before live Cutover starts.

    Returns:
        Evidence accepted by the public full acceptance entrypoint.
    """
    command = passed_command(
        argv=[sys.executable, "recorded-gate"],
        environment={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    return {
        "commands": [command],
        "publication_state_after": state,
        "active_state_unchanged": True,
        "artifact_closure_complete": True,
        "artifact_hashes": {
            "scalability_audit.csv": "7" * 64,
            "semantic_audit_receipt.json": "8" * 64,
        },
        "old_resolver_throws_receipt": {
            "receipt_id": "sha256:" + "9" * 64,
        },
    }


def acceptance_authority(*, marker="1"):
    """Return one deterministic source and Requirement authority binding.

    Args:
        marker: Single digest character used to model authority drift.

    Returns:
        Acceptance binding compatible with the production runner.
    """
    return {
        "source": {
            "checkout_status": "GIT_CLEAN",
            "source_commit": marker * 40,
            "tree_sha256": marker * 64,
            "file_count": 1,
            "dirty_paths": (),
        },
        "requirements": {
            "requirement_closure_hash": "sha256:" + marker * 64,
            "hashes": {"fsd_sha256": marker * 64},
        },
    }


class AcceptanceRunnerTest(unittest.TestCase):
    """Prove failures and external blockers cannot be reported as full PASS."""

    def setUp(self) -> None:
        """Use a stable clean authority unless one test models drift."""
        self.authority_patcher = mock.patch(
            "run_acceptance._acceptance_authority_binding",
            return_value=acceptance_authority(),
        )
        self.authority_runner = self.authority_patcher.start()
        self.addCleanup(self.authority_patcher.stop)

    def test_live_attempt_audit_binds_portable_exact_closure(self) -> None:
        """Require copied stability bytes and all-attempt exact identities."""
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            digest = "a" * 64
            closure = (
                repo_root / "outputs" / "vnext_cutover_audits" / digest
            )
            receipt_path = (
                closure / "receipts" / "live_reader_stability.json"
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text('{"status":"PASSED"}\n', encoding="utf-8")
            manifest_path = closure / "audit_manifest.json"
            manifest_path.write_text("{}\n", encoding="utf-8")
            attempts = [
                {
                    "attempt_id": "sha256:" + str(ordinal) * 64,
                    "run_id": "run:audit:{}".format(ordinal),
                }
                for ordinal in range(1, 4)
            ]
            manifest = {
                "schema_version": 1,
                "closure_type": "LIVE_READER_ATTEMPT_AUDIT",
                "stability_receipt_id": "sha256:" + "b" * 64,
                "attempt_ids": [
                    attempt["attempt_id"] for attempt in attempts
                ],
                "run_bindings": [
                    {
                        "audit_manifest_hash": "sha256:" + "c" * 64,
                        "content_manifest_hash": "sha256:" + "d" * 64,
                        "path": "runs/{}".format(ordinal),
                        "run_id": attempts[ordinal - 1]["run_id"],
                        "status": "FROZEN",
                    }
                    for ordinal in range(1, 4)
                ],
                "files": [
                    {
                        "path": "receipts/live_reader_stability.json",
                        "sha256": sha256_file(path=receipt_path),
                        "size": receipt_path.stat().st_size,
                    }
                ],
                "audit_closure_id": "sha256:" + digest,
            }
            with mock.patch(
                "run_acceptance._verify_live_attempt_audit_closure",
                return_value=manifest,
            ):
                binding = _validated_live_attempt_audit(
                    repo_root=repo_root,
                    closure_path_value=closure,
                    expected_closure_id="sha256:" + digest,
                    stability_receipt_id="sha256:" + "b" * 64,
                    stability_receipt_sha256=sha256_file(
                        path=receipt_path,
                    ),
                    attempts=attempts,
                )
                receipt_path.write_text(
                    '{"status":"tampered"}\n', encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    AcceptanceError, "stability receipt bytes differ",
                ):
                    _validated_live_attempt_audit(
                        repo_root=repo_root,
                        closure_path_value=closure,
                        expected_closure_id="sha256:" + digest,
                        stability_receipt_id="sha256:" + "b" * 64,
                        stability_receipt_sha256=binding[
                            "stability_receipt_sha256"
                        ],
                        attempts=attempts,
                    )

    def test_r4_fast_gate_has_a_stable_public_command(self) -> None:
        """Expose the sole R4 test runner as a stable public command."""
        self.assertEqual("tools/run_fast_tests.py", FAST_TEST_COMMAND)

    def test_sec_identity_gate_and_http_client_share_fail_fast_rules(
        self,
    ) -> None:
        """Use the same stable identity error at both live entry points."""
        invalid_identities = (
            ("", "ops@corp.co", "SEC_ORGANIZATION_INVALID"),
            (None, "ops@corp.co", "SEC_ORGANIZATION_INVALID"),
            ("Fixture", "ops@corp.co", "SEC_ORGANIZATION_INVALID"),
            ("axaxl", "", "SEC_CONTACT_EMAIL_REQUIRED"),
            ("axaxl", "x", "SEC_CONTACT_EMAIL_INVALID"),
            ("axaxl", "ops@corp.test", "SEC_CONTACT_EMAIL_INVALID"),
            ("axaxl", "test@example.com", "SEC_CONTACT_EMAIL_INVALID"),
        )
        for index, identity in enumerate(invalid_identities):
            with self.subTest(index=index), tempfile.TemporaryDirectory(
            ) as directory, mock.patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "fixture-key",
                    "SEC_CONTACT_EMAIL": identity[1],
                },
                clear=True,
            ):
                root = Path(directory)
                config_path = root / "config" / "sec_config.json"
                config_path.parent.mkdir(parents=True)
                config = {
                    "organization": identity[0],
                    "rate_limit_per_sec": 5,
                    "max_retries": 4,
                    "backoff_initial_seconds": 1.0,
                }
                config_path.write_text(
                    json.dumps(config), encoding="utf-8",
                )
                with mock.patch(
                    "run_acceptance.load_requirement_snapshot",
                    return_value={"pending_decision_ids": []},
                ), mock.patch(
                    "run_acceptance.capture_source_snapshot",
                    return_value={},
                ), mock.patch(
                    "run_acceptance.publication_state_snapshot",
                    return_value=publication_state(
                        publication_id="publication_" + "1" * 64,
                        marker="1",
                    ),
                ):
                    blockers = external_blockers(repo_root=root)
                self.assertEqual(
                    [identity[2]],
                    [blocker["code"] for blocker in blockers],
                )
                with self.assertRaises(SecIdentityError):
                    load_config(config_path=config_path)

    def test_nonzero_command_keeps_return_code_and_stream_digests(
        self,
    ) -> None:
        """Preserve command failure evidence without storing raw streams."""
        record = run_command(
            argv=[
                sys.executable,
                "-c",
                (
                    "import sys;print('out');"
                    "print('err',file=sys.stderr);sys.exit(7)"
                ),
            ],
            repo_root=REPO_ROOT,
            environment={"PYTHONDONTWRITEBYTECODE": "1"},
            timeout_seconds=30,
        )
        self.assertEqual("FAILED", record["outcome"])
        self.assertEqual(7, record["return_code"])
        self.assertGreater(record["stdout_size"], 0)
        self.assertGreater(record["stderr_size"], 0)
        self.assertNotIn("out", record)

    def test_offline_guard_blocks_a_real_socket_constructor(self) -> None:
        """Prove recorded subprocesses cannot create even one socket."""
        with tempfile.TemporaryDirectory() as directory:
            guard = _offline_environment(guard_dir=Path(directory))
            record = run_command(
                argv=[
                    sys.executable,
                    "-c",
                    (
                        "import socket\n"
                        "try:\n socket.socket()\n"
                        "except PermissionError as error:\n"
                        " assert str(error) == 'RECORDED_SOCKET_BLOCKED'\n"
                        "else:\n raise SystemExit(9)"
                    ),
                ],
                repo_root=REPO_ROOT,
                environment=guard,
                timeout_seconds=30,
            )
        self.assertEqual("PASSED", record["outcome"])

    def test_recorded_guard_sanitizes_secrets_and_blocks_dash_s_child(
        self,
    ) -> None:
        """Keep live secrets out and inherit OS network denial into ``-S``."""
        stable = {
            "active_publication_id": None,
            "mirror_hashes": {},
            "authority_hashes": {
                "outputs/active_publication.json": None,
                "outputs/validation_snapshot_provenance.json": None,
            },
        }
        child = (
            "import socket\n"
            "sock = socket.socket()\n"
            "try:\n"
            " sock.bind(('127.0.0.1', 0))\n"
            "except PermissionError:\n"
            " raise SystemExit(0)\n"
            "raise SystemExit(19)\n"
        )
        parent = (
            "import os, subprocess, sys\n"
            "if 'OPENAI_API_KEY' in os.environ:\n raise SystemExit(17)\n"
            "if 'SEC_CONTACT_EMAIL' in os.environ:\n raise SystemExit(18)\n"
            "result = subprocess.run([sys.executable, '-S', '-c', {!r}])\n"
            "raise SystemExit(result.returncode)\n"
        ).format(child)
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only-secret",
                "SEC_CONTACT_EMAIL": "operator@axaxl.co",
            },
        ), mock.patch(
            "run_acceptance.recorded_commands",
            return_value=[{
                "argv": [sys.executable, "-c", parent],
                "reason": "",
            }],
        ), mock.patch(
            "run_acceptance._recorded_state_snapshot",
            side_effect=(stable, stable),
        ):
            evidence = run_acceptance._recorded_gate_execution(
                repo_root=REPO_ROOT,
                current_python=sys.executable,
                python39=sys.executable,
                gate_output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("PASSED", evidence["commands"][1]["outcome"])

    def test_terminal_cycles_remove_live_secrets_and_deny_network(self) -> None:
        """Apply the same process-tree isolation to every terminal consumer."""
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ) as runner:
            records = run_acceptance._terminal_cycle(
                repo_root=REPO_ROOT,
                current_python=sys.executable,
                timeout_seconds=30,
                guard_dir=Path(directory),
                expected_publication_id="publication_" + "1" * 64,
            )
        self.assertEqual(1, len(records))
        self.assertIn("terminal_cycle_result", records[0])
        for call in runner.call_args_list:
            with self.subTest(argv=call.kwargs["argv"]):
                self.assertIsNone(
                    call.kwargs["environment"]["OPENAI_API_KEY"]
                )
                self.assertIsNone(
                    call.kwargs["environment"]["SEC_CONTACT_EMAIL"]
                )
                self.assertTrue(call.kwargs["sandbox_profile"])

    def test_readme_generator_separates_recorded_and_formal_evidence(
        self,
    ) -> None:
        """Generate both supported paths without upgrading recorded PASS."""
        readme = build_readme()
        self.assertIn("## vNext 正式 operator 与证据等级", readme)
        self.assertIn("tools/run_acceptance.py --scope recorded", readme)
        self.assertIn("--scope full --execute-live", readme)
        self.assertIn("review decide", readme)
        self.assertIn("PASSED_FAST_LOCAL_ONLY", readme)
        self.assertIn(
            "ACCEPTANCE_OUTPUT_DIR_OVERLAPS_FORMAL_AUTHORITY", readme,
        )
        self.assertIn("R4不再启动 Python 3.9 全量测试", readme)

    def test_readme_matches_generator_and_stable_postprocessor(self) -> None:
        """Keep the checked-in README reproducible by the stage 11 path."""
        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory)
            readme_path = workdir / "README_RUN.md"
            readme_path.write_text(build_readme(), encoding="utf-8")
            ensure_readme_routes(workdir=workdir)
            generated = readme_path.read_text(encoding="utf-8")
        current = (REPO_ROOT / "README_RUN.md").read_text(encoding="utf-8")
        self.assertEqual(current, generated)

    def test_readme_routes_formal_and_legacy_batches_without_root_writes(
        self,
    ) -> None:
        """Route formal refresh and the complete isolated candidate honestly."""
        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory)
            readme_path = workdir / "README_RUN.md"
            readme_path.write_text(build_readme(), encoding="utf-8")
            ensure_readme_routes(workdir=workdir)
            generated = readme_path.read_text(encoding="utf-8")
        self.assertIn(
            "tools/run_acceptance.py --scope full --execute-live",
            generated,
        )
        self.assertIn("## 内部阶段 00-11", generated)
        self.assertNotIn("## 内部阶段 00-12", generated)
        self.assertNotIn(
            "/ABSOLUTE/CANDIDATE_WORKSPACE 12_validate_repair",
            generated,
        )
        self.assertNotIn("按顺序运行阶段 `00`–`11`", generated)
        self.assertIn(
            "pointer 存在时业务用户读取的 root CSV",
            generated,
        )
        self.assertIn("formal Cutover 或 full acceptance", generated)

    def test_r4_plan_uses_fast_runner_without_full_discovery(self) -> None:
        """Keep R4 acceptance free of full-suite and floor-interpreter work."""
        plan = recorded_commands(
            current_python=sys.executable,
            python39=None,
            gate_output_dir=REPO_ROOT / "outputs" / "acceptance_receipts",
        )
        command_text = [" ".join(row["argv"]) for row in plan]
        self.assertEqual(4, len(command_text))
        self.assertEqual(
            "{} {} --jobs 4".format(sys.executable, FAST_TEST_COMMAND),
            command_text[0],
        )
        self.assertTrue(all("unittest discover" not in text for text in command_text))
        self.assertTrue(all("python3.9" not in text for text in command_text))
        self.assertEqual(60, run_acceptance.R4_RECORDED_TIMEOUT_SECONDS)
        self.assertEqual(30, run_acceptance.R4_FAST_CASE_TIMEOUT_SECONDS)

    def test_recorded_plan_keeps_required_gate_layers_in_order(self) -> None:
        """Keep only R4 fast and static gates in deterministic order."""
        with tempfile.TemporaryDirectory() as directory:
            plan = recorded_commands(
                current_python=sys.executable,
                python39="/python3.9",
                gate_output_dir=Path(directory),
            )
        command_text = [
            " ".join(str(value) for value in row["argv"])
            for row in plan
        ]
        expected_fragments = (
            FAST_TEST_COMMAND,
            "tools/check_vnext_semantics.py",
            "tools/check_no_company_literals.py",
            "tools/check_capability_contract_alignment.py",
        )
        self.assertEqual(len(expected_fragments), len(command_text))
        for command, fragment in zip(command_text, expected_fragments):
            with self.subTest(command=command):
                self.assertIn(fragment, command)

    def test_recorded_gate_artifacts_never_target_active_mirrors(
        self,
    ) -> None:
        """Write audit evidence outside the root compatibility mirrors."""
        with tempfile.TemporaryDirectory() as directory:
            gate_dir = Path(directory)
            plan = recorded_commands(
                current_python=sys.executable,
                python39="/python3.9",
                gate_output_dir=gate_dir,
            )
        command_text = "\n".join(
            " ".join(str(value) for value in row["argv"]) for row in plan
        )
        self.assertNotIn("outputs/semantic_audit_receipt.json", command_text)
        self.assertNotIn("outputs/scalability_audit.csv", command_text)
        self.assertIn(str(gate_dir), command_text)

    def test_recorded_scope_is_labeled_recorded_only(self) -> None:
        """Keep offline success distinct from final live acceptance."""
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch(
                "run_acceptance.run_command", side_effect=passed_command
            ):
                receipt = execute_acceptance(
                    repo_root=REPO_ROOT,
                    scope="recorded",
                    execute_live=False,
                    current_python=sys.executable,
                    python39="/python3.9",
                    output_dir=Path(directory),
                    timeout_seconds=30,
                )
            self.assertEqual("PASSED_FAST_LOCAL_ONLY", receipt["status"])
            self.assertEqual([], receipt["external_blockers"])
            self.assertTrue(receipt["recorded_evidence"][
                "active_state_unchanged"
            ])
            self.assertTrue(Path(receipt["output_path"]).is_file())
            persisted_json = list(Path(directory).rglob("*.json"))
            self.assertTrue(persisted_json)
            for path in persisted_json:
                with self.subTest(path=path):
                    text = path.read_text(encoding="utf-8")
                    self.assertNotIn(str(REPO_ROOT), text)
                    self.assertNotIn(sys.executable, text)
            fast_policy_paths = [
                path
                for path in persisted_json
                if path.name.startswith("r4_fast_test_policy_")
            ]
            self.assertEqual(1, len(fast_policy_paths))
            fast_policy = json.loads(
                fast_policy_paths[0].read_text(encoding="utf-8")
            )
            self.assertEqual(
                "$PYTHON_CURRENT",
                fast_policy["command"]["argv"][0],
            )
            self.assertIn(
                "$PYTHON_CURRENT", fast_policy["runtime_bindings"]
            )

    def test_recorded_scope_blocks_sockets_and_never_calls_live_preflight(
        self,
    ) -> None:
        """Apply the audit-hook guard to every executed offline command."""
        previous = publication_state(
            publication_id="publication_" + "1" * 64, marker="1",
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers",
        ) as preflight, mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(previous, previous),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ) as runner:
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("PASSED_FAST_LOCAL_ONLY", receipt["status"])
        preflight.assert_not_called()
        self.assertTrue(runner.call_args_list)
        for command in runner.call_args_list:
            with self.subTest(argv=command.kwargs["argv"]):
                self.assertIn("PYTHONPATH", command.kwargs["environment"])

    def test_recorded_scope_fails_if_active_or_mirrors_change(self) -> None:
        """Reject an offline gate that mutates formal publication state."""
        before = publication_state(
            publication_id="publication_" + "1" * 64, marker="1",
        )
        after = publication_state(
            publication_id="publication_" + "1" * 64, marker="2",
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(before, after, before),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ), mock.patch(
            "run_acceptance._recorded_authority_backup",
            create=True,
            return_value={},
        ), mock.patch(
            "run_acceptance._restore_recorded_authority",
            create=True,
        ) as restore:
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("RECORDED_ACTIVE_STATE_CHANGED", receipt["status"])
        restore.assert_called_once()
        self.assertEqual(
            "PASSED",
            receipt["recorded_evidence"]["state_recovery"]["outcome"],
        )

    def test_recorded_snapshot_binds_formal_namespaces_and_sec_ledger(
        self,
    ) -> None:
        """Bind exact formal trees and ledger bytes, not only active mirrors."""
        formal_roots = (
            Path("artifacts/vnext/cutover"),
            Path("artifacts/vnext/qualification"),
            Path("artifacts/vnext/zero_ai_release"),
            Path("evidence/request_attempts"),
            Path("outputs/publication_fault_receipts"),
            Path("outputs/publications"),
            Path("outputs/publication_switch_intents"),
            Path("outputs/publication_switch_receipts"),
            Path("outputs/zero_ai_release_receipts"),
            Path("outputs/vnext_cutover_audits"),
        )
        ledger_paths = (
            Path("evidence/requests_log.csv"),
            Path("evidence/requests_log_manifest.json"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, relative in enumerate(formal_roots):
                path = root / relative / "bound.bin"
                path.parent.mkdir(parents=True)
                path.write_bytes("formal-{}\n".format(index).encode())
            for index, relative in enumerate(ledger_paths):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes("ledger-{}\n".format(index).encode())
            publication = publication_state(
                publication_id="publication_" + "1" * 64,
                marker="1",
            )
            with mock.patch(
                "run_acceptance.publication_state_snapshot",
                return_value=publication,
            ):
                before = run_acceptance._recorded_state_snapshot(
                    repo_root=root,
                )
                (root / formal_roots[0] / "bound.bin").write_bytes(
                    b"changed\n"
                )
                after = run_acceptance._recorded_state_snapshot(
                    repo_root=root,
                )
        self.assertEqual(
            {path.as_posix() for path in formal_roots},
            set(before["formal_namespace_trees"]),
        )
        for relative in ledger_paths:
            self.assertIn(
                relative.as_posix(), before["authority_hashes"],
            )
        self.assertNotEqual(before, after)

    def test_recorded_sandbox_denies_formal_namespace_and_ledger_writes(
        self,
    ) -> None:
        """Protect every formal directory subtree and SEC ledger file."""
        profile = run_acceptance._offline_sandbox_profile(
            repo_root=REPO_ROOT, protect_authority=True,
        )
        for relative in (
            "artifacts/vnext/cutover",
            "artifacts/vnext/qualification",
            "artifacts/vnext/zero_ai_release",
            "evidence/request_attempts",
            "outputs/publication_fault_receipts",
            "outputs/publications",
            "outputs/publication_switch_intents",
            "outputs/publication_switch_receipts",
            "outputs/zero_ai_release_receipts",
            "outputs/vnext_cutover_audits",
        ):
            with self.subTest(relative=relative):
                self.assertIn(
                    '(subpath "{}")'.format(REPO_ROOT / relative),
                    profile,
                )
        for relative in (
            "artifacts/vnext/latest_run_status.json",
            "outputs/active_publication.json.lock",
            "evidence/requests_log.csv",
            "evidence/requests_log_manifest.json",
        ):
            with self.subTest(relative=relative):
                self.assertIn(
                    '(literal "{}")'.format(REPO_ROOT / relative),
                    profile,
                )

    def test_recorded_snapshot_detects_switch_lock_and_latest_drift(
        self,
    ) -> None:
        """Bind switch history, pending intent, lock, and latest status bytes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            switch_files = (
                Path("outputs/publication_switch_intents/intent.json"),
                Path("outputs/publication_switch_receipts/receipt.json"),
                Path("outputs/active_publication.json.lock"),
                Path("artifacts/vnext/latest_run_status.json"),
            )
            for relative in switch_files:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"before\n")
            publication = publication_state(
                publication_id="publication_" + "1" * 64,
                marker="1",
            )
            with mock.patch(
                "run_acceptance.publication_state_snapshot",
                return_value=publication,
            ):
                before = run_acceptance._recorded_state_snapshot(
                    repo_root=root,
                )
                for relative in switch_files:
                    (root / relative).write_bytes(b"after\n")
                after = run_acceptance._recorded_state_snapshot(
                    repo_root=root,
                )
        self.assertNotEqual(before, after)
        self.assertIn(
            "outputs/publication_switch_intents",
            before["formal_namespace_trees"],
        )
        self.assertIn(
            "outputs/publication_switch_receipts",
            before["formal_namespace_trees"],
        )
        self.assertIn(
            "outputs/active_publication.json.lock",
            before["authority_hashes"],
        )
        self.assertIn(
            "artifacts/vnext/latest_run_status.json",
            before["authority_hashes"],
        )

    def test_unreadable_recorded_post_state_restores_before_failure(
        self,
    ) -> None:
        """Attempt exact recovery when an offline child makes state unreadable."""
        before = {
            "active_publication_id": None,
            "mirror_hashes": {},
            "authority_hashes": {
                "outputs/active_publication.json": None,
                "outputs/validation_snapshot_provenance.json": None,
            },
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance._recorded_state_snapshot",
            side_effect=(
                before,
                AcceptanceError("unsafe"),
                before,
            ),
        ), mock.patch(
            "run_acceptance._recorded_authority_backup", return_value={},
        ), mock.patch(
            "run_acceptance._restore_recorded_authority",
        ) as restore, mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("RECORDED_GATE_EXECUTION_FAILED", receipt["status"])
        restore.assert_called_once()

    def test_recorded_scope_rejects_missing_gate_artifacts(self) -> None:
        """Do not accept zero-output semantic or scalability checkers."""
        stable = {
            "active_publication_id": None,
            "mirror_hashes": {},
            "authority_hashes": {
                "outputs/active_publication.json": None,
                "outputs/validation_snapshot_provenance.json": None,
            },
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance._recorded_state_snapshot",
            side_effect=(stable, stable),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ), mock.patch(
            "run_acceptance.artifact_hashes", return_value={},
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual(
            "RECORDED_ARTIFACT_CLOSURE_INCOMPLETE", receipt["status"],
        )

    def test_full_reopens_recorded_gate_artifact_bytes(self) -> None:
        """Reject semantic/scalability artifacts changed after recorded gates."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate_dir = root / "outputs" / "acceptance_receipts" / "gate"
            gate_dir.mkdir(parents=True)
            hashes = {}
            references = {}
            for name in run_acceptance.RECORDED_GATE_ARTIFACTS:
                path = gate_dir / name
                path.write_text(name + "\n", encoding="utf-8")
                hashes[name] = sha256_file(path=path)
                references[name] = {
                    "path": str(path),
                    "sha256": hashes[name],
                }
            evidence = {
                "artifact_closure_complete": True,
                "artifact_hashes": hashes,
                "artifact_references": references,
            }
            binding = run_acceptance._validated_recorded_gate_artifacts(
                repo_root=root, recorded_evidence=evidence,
            )
            self.assertEqual(set(hashes), set(binding))
            (gate_dir / "scalability_audit.csv").write_text(
                "tampered\n", encoding="utf-8",
            )
            with self.assertRaises(AcceptanceError):
                run_acceptance._validated_recorded_gate_artifacts(
                    repo_root=root, recorded_evidence=evidence,
                )

    def test_recorded_receipt_binds_source_and_requirement_authority(
        self,
    ) -> None:
        """Persist exact commit/tree and Requirement closure on recorded PASS."""
        state = publication_state(publication_id=None, marker="0")
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=state),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("PASSED_FAST_LOCAL_ONLY", receipt["status"])
        expected = json.loads(json.dumps(acceptance_authority()))
        self.assertEqual(expected, receipt["authority_binding"])

    def test_persisted_receipt_rejects_local_absolute_paths(self) -> None:
        """Keep exact command identity without persisting host-local paths."""
        state = publication_state(publication_id=None, marker="0")
        evidence = recorded_evidence(state=state)
        evidence["commands"][0]["reason"] = "invalid /bin/true path"
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=evidence,
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
            persisted = json.loads(
                Path(receipt["output_path"]).read_text(encoding="utf-8")
            )

        def strings(value):
            """Yield every nested string so no receipt field can hide a path."""
            if isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
            elif isinstance(value, str):
                yield value

        absolute_values = [
            value for value in strings(persisted) if value.startswith("/")
        ]
        self.assertEqual([], absolute_values)
        self.assertNotIn("/bin/true", json.dumps(persisted))
        self.assertEqual(
            "$PYTHON_CURRENT", persisted["commands"][0]["argv"][0]
        )
        self.assertIn("$PYTHON_CURRENT", persisted["runtime_bindings"])

    def test_authority_binding_contains_every_governed_input_hash(self) -> None:
        """Bind FSD, R2, R3, Decision, baseline, release, and runtime bytes."""
        snapshot = SourceSnapshot(
            checkout_status="GIT_CLEAN",
            source_commit="a" * 40,
            tree_sha256="b" * 64,
            file_count=1,
            dirty_paths=(),
        )
        with mock.patch(
            "run_acceptance.capture_source_snapshot", return_value=snapshot,
        ):
            binding = PRODUCTION_AUTHORITY_BINDING(repo_root=REPO_ROOT)
        self.assertEqual({
            "baseline_sha256",
            "decision_register_sha256",
            "fsd_sha256",
            "issue_body_sha256",
            "legacy_path_inventory_sha256",
            "r3_addendum_sha256",
            "release_plan_sha256",
            "semantic_runtime_versions_hash",
        }, set(binding["requirements"]["hashes"]))
        self.assertEqual("a" * 40, binding["source"]["source_commit"])

    def test_authority_drift_invalidates_recorded_pass(self) -> None:
        """Reject source or Requirement bytes that change during acceptance."""
        state = publication_state(publication_id=None, marker="0")
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance._acceptance_authority_binding",
            side_effect=(
                acceptance_authority(marker="1"),
                acceptance_authority(marker="2"),
            ),
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=state),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("ACCEPTANCE_AUTHORITY_CHANGED", receipt["status"])

    def test_dirty_authority_fails_before_acceptance_commands(self) -> None:
        """Fail closed before gates when source-input closure is not clean."""
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance._acceptance_authority_binding",
            side_effect=run_acceptance.ValidationProvenanceError("dirty"),
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
        ) as recorded_runner:
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="recorded",
                execute_live=False,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual(
            "SOURCE_REQUIREMENT_CLOSURE_INVALID", receipt["status"],
        )
        recorded_runner.assert_not_called()

    def test_full_authority_requires_exact_formal_rebinding(self) -> None:
        """Reject formal evidence from a different source/Requirement closure."""
        self.assertFalse(run_acceptance._formal_authority_matches(
            authority=acceptance_authority(marker="1"),
            formal=acceptance_authority(marker="2"),
        ))

    def test_python39_override_must_be_a_real_python39(self) -> None:
        """Reject an executable that returns zero without running Python 3.9."""
        true_path = shutil.which("true")
        self.assertIsNotNone(true_path)
        with self.assertRaises(AcceptanceError):
            run_acceptance.resolve_python39(explicit_path=true_path)

    def test_public_fake_python39_cannot_mutate_formal_authority(
        self,
    ) -> None:
        """Reject a self-reporting executable before it can rewrite ledger."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            ledger = root / "evidence/requests_log.csv"
            ledger.parent.mkdir(parents=True)
            ledger.write_bytes(b"immutable-ledger\n")
            fake = Path(directory) / "fake-python3.9"
            fake.write_text(
                "#!/bin/sh\n"
                "printf 'mutated-ledger\\n' > {!r}\n"
                "printf 'PYTHON_3_9\\n'\n".format(str(ledger)),
                encoding="utf-8",
            )
            fake.chmod(0o755)
            completed = run_public_acceptance_cli(
                repo_root=root,
                arguments=[
                    "--scope",
                    "recorded",
                    "--python39",
                    str(fake),
                    "--output-dir",
                    "outputs/acceptance_receipts",
                ],
            )
            payload = json.loads(completed.stdout)
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual(
                "PYTHON39_INTERPRETER_INVALID", payload["error"]["code"],
            )
            self.assertEqual(b"immutable-ledger\n", ledger.read_bytes())
            self.assertNotIn("Traceback", completed.stderr)

    def test_python39_probe_restores_drift_under_complete_sandbox(
        self,
    ) -> None:
        """Restore exact formal bytes if even a native probe mutates state."""
        observed = {}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            ledger = root / "evidence/requests_log.csv"
            ledger.parent.mkdir(parents=True)
            ledger.write_bytes(b"before\n")

            def mutate_during_probe(**arguments):
                """Simulate a hostile native executable despite the policy."""
                observed["sandbox_profile"] = arguments["sandbox_profile"]
                ledger.write_bytes(b"after\n")
                return ({"outcome": "PASSED"}, b"{}\n")

            with mock.patch(
                "run_acceptance._native_executable", return_value=True,
            ), mock.patch(
                "run_acceptance._execute_command",
                side_effect=mutate_during_probe,
            ), self.assertRaisesRegex(
                AcceptanceError,
                "PYTHON39_PROBE_MUTATED_FORMAL_AUTHORITY",
            ):
                run_acceptance.resolve_python39(
                    explicit_path=sys.executable, repo_root=root,
                )
            self.assertEqual(b"before\n", ledger.read_bytes())
        profile = observed["sandbox_profile"]
        for relative in (
            *run_acceptance._recorded_protected_file_relative_paths(),
            *run_acceptance.FORMAL_NAMESPACE_PATHS,
        ):
            with self.subTest(relative=relative):
                self.assertIn(str(root / relative), profile)

    def test_installed_python39_passes_structured_native_probe(self) -> None:
        """Accept the installed native CPython 3.9 after exact read-back."""
        executable = shutil.which("python3.9")
        if executable is None:
            self.skipTest("python3.9 is unavailable")
        resolved = run_acceptance.resolve_python39(
            explicit_path=executable, repo_root=REPO_ROOT,
        )
        self.assertEqual(str(Path(executable).resolve()), resolved)

    def test_command_timeout_remains_a_failed_gate(self) -> None:
        """Preserve timeout as FAILED even with a production-safe default."""
        timeout = run_acceptance.subprocess.TimeoutExpired(
            cmd=[sys.executable], timeout=1,
        )
        with mock.patch(
            "run_acceptance.subprocess.run", side_effect=timeout,
        ):
            record = run_command(
                argv=[sys.executable, "-c", "pass"],
                repo_root=REPO_ROOT,
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
                timeout_seconds=1,
            )
        self.assertEqual("FAILED", record["outcome"])
        self.assertEqual("COMMAND_TIMEOUT", record["reason"])

    def test_public_output_dir_cannot_escape_repository(self) -> None:
        """Reject absolute and symlink-redirected acceptance receipt roots."""
        fake_receipt = {
            "status": "LIVE_EXECUTION_NOT_AUTHORIZED",
            "acceptance_receipt_id": "sha256:" + "1" * 64,
            "output_path": "unused.json",
            "blocking_detail": {"code": "LIVE_EXECUTION_NOT_AUTHORIZED"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            external = Path(directory) / "external"
            root.mkdir()
            external.mkdir()
            (root / "redirect").symlink_to(
                external, target_is_directory=True,
            )
            for value in (str(external), "redirect"):
                with self.subTest(value=value), self.assertRaises(
                    AcceptanceError
                ), mock.patch(
                    "run_acceptance.resolve_python39",
                    return_value="python3.9",
                ), mock.patch(
                    "run_acceptance.execute_acceptance",
                    return_value=fake_receipt,
                ), mock.patch("builtins.print"):
                    run_acceptance.main(argv=[
                        "--repo-root", str(root),
                        "--scope", "full",
                        "--output-dir", value,
                    ])

    def test_public_output_dir_rejects_all_formal_overlaps_before_write(
        self,
    ) -> None:
        """Reject formal ancestors and descendants in both public scopes."""
        cases = (
            ("recorded", "outputs/publications/acceptance"),
            ("full", "outputs"),
            ("recorded", "evidence"),
            ("full", "evidence/requests_log.csv/acceptance"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (scope, value) in enumerate(cases):
                with self.subTest(scope=scope, value=value):
                    root = Path(directory) / "repo-{}".format(index)
                    root.mkdir()
                    if "requests_log.csv" in value:
                        ledger = root / "evidence/requests_log.csv"
                        ledger.parent.mkdir(parents=True)
                        ledger.write_bytes(b"existing-ledger\n")
                    before = [
                        (
                            path.relative_to(root).as_posix(),
                            path.read_bytes() if path.is_file() else None,
                        )
                        for path in sorted(root.rglob("*"))
                    ]
                    completed = run_public_acceptance_cli(
                        repo_root=root,
                        arguments=[
                            "--scope",
                            scope,
                            "--output-dir",
                            value,
                        ],
                    )
                    payload = json.loads(completed.stdout)
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual(
                        "ACCEPTANCE_OUTPUT_DIR_OVERLAPS_FORMAL_AUTHORITY",
                        payload["error"]["code"],
                    )
                    after = [
                        (
                            path.relative_to(root).as_posix(),
                            path.read_bytes() if path.is_file() else None,
                        )
                        for path in sorted(root.rglob("*"))
                    ]
                    self.assertEqual(before, after)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_default_timeout_exceeds_observed_python39_gate_duration(
        self,
    ) -> None:
        """Keep the documented no-flag command above its measured 900s run."""
        observed = {}

        def fake_acceptance(**arguments):
            """Capture parser defaults without running acceptance commands."""
            observed.update(arguments)
            return {
                "status": "LIVE_EXECUTION_NOT_AUTHORIZED",
                "acceptance_receipt_id": "sha256:" + "1" * 64,
                "output_path": "unused.json",
                "blocking_detail": {
                    "code": "LIVE_EXECUTION_NOT_AUTHORIZED",
                },
            }

        with mock.patch(
            "run_acceptance.resolve_python39", return_value="python3.9",
        ), mock.patch(
            "run_acceptance.execute_acceptance", side_effect=fake_acceptance,
        ), mock.patch("builtins.print"):
            run_acceptance.main(argv=["--scope", "full"])
        self.assertGreater(observed["timeout_seconds"], 900)

    def test_full_uses_cutover_then_three_validated_pointer_views(
        self,
    ) -> None:
        """Avoid legacy migrated writers and prove cutover/rollback/restore."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        structured = [
            (passed_command(
                argv=[sys.executable, "tools/vnext_cutover.py"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            ), cutover_envelope(
                previous_id=previous_id, publication_id=publication_id,
            )),
            (passed_command(
                argv=[sys.executable, "tools/vnext_operator.py", "rollback"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            ), switch_envelope(
                command="rollback",
                publication_id=previous_id,
                previous_id=publication_id,
            )),
            (passed_command(
                argv=[sys.executable, "tools/vnext_operator.py", "restore"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            ), switch_envelope(
                command="restore",
                publication_id=publication_id,
                previous_id=previous_id,
            )),
        ]
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(previous, previous, current, previous, current),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ), mock.patch(
            "run_acceptance.run_json_command", side_effect=structured,
        ) as json_runner, mock.patch(
            "run_acceptance.formal_evidence_binding",
            return_value={**acceptance_authority(), "bound": True},
        ), mock.patch(
            "run_acceptance._validated_publication_state",
            side_effect=(
                {"state": previous, "publication_id": previous_id},
                {"state": current, "publication_id": publication_id},
            ),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("PASSED", receipt["status"])
        self.assertEqual(3, json_runner.call_count)
        argv_text = "\n".join(
            " ".join(str(value) for value in row["argv"])
            for row in receipt["commands"]
        )
        self.assertNotIn("04_compute_standard_metrics.py", argv_text)
        self.assertNotIn("09_extract_mda_and_risk_text.py", argv_text)
        self.assertEqual(
            3,
            argv_text.count(run_acceptance.TERMINAL_PUBLICATION_COMMAND),
        )
        self.assertIsNotNone(receipt["rollback_receipt"])
        self.assertIsNotNone(receipt["restore_receipt"])
        self.assertEqual([], receipt["not_run_items"])
        self.assertEqual(
            {"new_publication", "rollback", "restore"},
            set(receipt["terminal_cycle_results"]),
        )
        for phase, result in receipt["terminal_cycle_results"].items():
            with self.subTest(phase=phase):
                self.assertEqual(
                    result["terminal_cycle_id"],
                    receipt["terminal_cycle_ids"][phase],
                )
                self.assertEqual(
                    run_acceptance.TERMINAL_GATE_IDS,
                    tuple(
                        gate["gate_id"] for gate in result["gates"]
                    ),
                )

    def test_full_rolls_back_when_pinned_terminal_cycle_fails(
        self,
    ) -> None:
        """Recover when the one structured terminal entry returns nonzero."""
        target = run_acceptance.TERMINAL_PUBLICATION_COMMAND
        with tempfile.TemporaryDirectory() as directory:
                previous_id = "publication_" + "1" * 64
                publication_id = "publication_" + "2" * 64
                previous = publication_state(
                    publication_id=previous_id, marker="1",
                )
                current = publication_state(
                    publication_id=publication_id, marker="2",
                )
                structured = (
                    (
                        passed_command(
                            argv=[
                                sys.executable, "tools/vnext_cutover.py",
                            ],
                            environment={"PYTHONDONTWRITEBYTECODE": "1"},
                        ),
                        cutover_envelope(
                            previous_id=previous_id,
                            publication_id=publication_id,
                        ),
                    ),
                    (
                        passed_command(
                            argv=[
                                sys.executable,
                                "tools/vnext_operator.py",
                                "rollback",
                            ],
                            environment={"PYTHONDONTWRITEBYTECODE": "1"},
                        ),
                        switch_envelope(
                            command="rollback",
                            publication_id=previous_id,
                            previous_id=publication_id,
                        ),
                    ),
                )
                runner = partial(
                    failed_terminal_command, target=target,
                )
                with mock.patch(
                    "run_acceptance.external_blockers", return_value=[],
                ), mock.patch(
                    "run_acceptance.publication_state_snapshot",
                    side_effect=(previous, previous, current),
                ), mock.patch(
                    "run_acceptance.run_command", side_effect=runner,
                ), mock.patch(
                    "run_acceptance.run_json_command",
                    side_effect=structured,
                ) as json_runner, mock.patch(
                    "run_acceptance._validated_publication_state",
                    create=True,
                    return_value={
                        "state": previous,
                        "publication_id": previous_id,
                    },
                ):
                    receipt = execute_acceptance(
                        repo_root=REPO_ROOT,
                        scope="full",
                        execute_live=True,
                        current_python=sys.executable,
                        python39="/python3.9",
                        output_dir=Path(directory),
                        timeout_seconds=30,
                    )
                self.assertEqual("BLOCKED", receipt["status"])
                self.assertEqual(
                    "NEW_PUBLICATION_TERMINAL_VALIDATION_FAILED",
                    receipt["blocking_detail"]["code"],
                )
                self.assertEqual(
                    "ROLLED_BACK", receipt["blocking_detail"]["recovery"],
                )
                self.assertEqual(2, json_runner.call_count)
                self.assertIsNotNone(receipt["rollback_receipt"])
                self.assertIsNone(receipt["restore_receipt"])
                self.assertEqual(
                    previous_id,
                    receipt["rollback_receipt"]["active_after"],
                )

    def test_first_cutover_failure_uses_validated_imported_predecessor(
        self,
    ) -> None:
        """Accept verified A mirrors instead of incomplete pre-import roots."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        no_pointer = publication_state(publication_id=None, marker="0")
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        structured = (
            (
                passed_command(
                    argv=[sys.executable, "tools/vnext_cutover.py"],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                initial_cutover_envelope(
                    previous_id=previous_id,
                    publication_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
        )
        runner = partial(
            failed_terminal_command,
            target=run_acceptance.TERMINAL_PUBLICATION_COMMAND,
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=no_pointer),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            return_value=current,
        ), mock.patch(
            "run_acceptance.run_command", side_effect=runner,
        ), mock.patch(
            "run_acceptance.run_json_command", side_effect=structured,
        ), mock.patch(
            "run_acceptance._validated_publication_state",
            return_value={
                "state": previous,
                "publication_id": previous_id,
            },
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertEqual(
            "ROLLED_BACK", receipt["blocking_detail"]["recovery"],
        )
        self.assertEqual(
            previous_id, receipt["rollback_receipt"]["active_after"],
        )

    def test_rollback_terminal_failure_restores_validated_new_active(
        self,
    ) -> None:
        """Reverse A terminal failure to byte-exact previously validated B."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        structured = [
            (
                passed_command(
                    argv=[sys.executable, "tools/vnext_cutover.py"],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                cutover_envelope(
                    previous_id=previous_id,
                    publication_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "restore",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="restore",
                    publication_id=publication_id,
                    previous_id=previous_id,
                ),
            ),
        ]
        terminal_call = 0

        def fail_rollback_terminal(**arguments):
            """Fail the first report after B-to-A rollback only."""
            nonlocal terminal_call
            terminal_call += 1
            record = passed_command(**arguments)
            if terminal_call == 2:
                record["outcome"] = "FAILED"
                record["return_code"] = 1
                record["reason"] = "NONZERO_RETURN_CODE"
            return record

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=previous),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(current, previous),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=fail_rollback_terminal,
        ), mock.patch(
            "run_acceptance.run_json_command", side_effect=structured,
        ) as json_runner, mock.patch(
            "run_acceptance._validated_publication_state",
            side_effect=(
                {"state": previous, "publication_id": previous_id},
                {"state": current, "publication_id": publication_id},
            ),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertEqual(
            "ROLLBACK_TERMINAL_VALIDATION_FAILED",
            receipt["blocking_detail"]["code"],
        )
        self.assertEqual(
            "RESTORED_NEW_PUBLICATION",
            receipt["blocking_detail"]["recovery"],
        )
        self.assertEqual(3, json_runner.call_count)
        self.assertEqual(
            publication_id,
            receipt["recovery_receipt"]["active_after"],
        )

    def test_restore_terminal_failure_rolls_back_validated_predecessor(
        self,
    ) -> None:
        """Reverse B terminal failure to byte-exact validated predecessor A."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        structured = [
            (
                passed_command(
                    argv=[sys.executable, "tools/vnext_cutover.py"],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                cutover_envelope(
                    previous_id=previous_id,
                    publication_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "restore",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="restore",
                    publication_id=publication_id,
                    previous_id=previous_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
        ]
        terminal_call = 0

        def fail_restore_terminal(**arguments):
            """Fail the first report after A-to-B restore only."""
            nonlocal terminal_call
            terminal_call += 1
            record = passed_command(**arguments)
            if terminal_call == 3:
                record["outcome"] = "FAILED"
                record["return_code"] = 1
                record["reason"] = "NONZERO_RETURN_CODE"
            return record

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=previous),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(current, previous, current),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=fail_restore_terminal,
        ), mock.patch(
            "run_acceptance.run_json_command", side_effect=structured,
        ) as json_runner, mock.patch(
            "run_acceptance._validated_publication_state",
            side_effect=(
                {"state": previous, "publication_id": previous_id},
                {"state": current, "publication_id": publication_id},
                {"state": previous, "publication_id": previous_id},
            ),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertEqual(
            "RESTORE_TERMINAL_VALIDATION_FAILED",
            receipt["blocking_detail"]["code"],
        )
        self.assertEqual(
            "ROLLED_BACK_PREDECESSOR",
            receipt["blocking_detail"]["recovery"],
        )
        self.assertEqual(4, json_runner.call_count)
        self.assertEqual(
            previous_id,
            receipt["recovery_receipt"]["active_after"],
        )

    def test_final_evidence_failure_rolls_back_validated_predecessor(
        self,
    ) -> None:
        """Never leave B active when final byte binding fails closed."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        structured = [
            (
                passed_command(
                    argv=[sys.executable, "tools/vnext_cutover.py"],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                cutover_envelope(
                    previous_id=previous_id,
                    publication_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "restore",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="restore",
                    publication_id=publication_id,
                    previous_id=previous_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
        ]
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=previous),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(current, previous, current),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ), mock.patch(
            "run_acceptance.run_json_command", side_effect=structured,
        ) as json_runner, mock.patch(
            "run_acceptance._validated_publication_state",
            side_effect=(
                {"state": previous, "publication_id": previous_id},
                {"state": current, "publication_id": publication_id},
                {"state": previous, "publication_id": previous_id},
            ),
        ), mock.patch(
            "run_acceptance.formal_evidence_binding",
            side_effect=AcceptanceError("fixture binding failure"),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("FULL_EVIDENCE_BINDING_FAILED", receipt["status"])
        self.assertEqual(
            "ROLLED_BACK_PREDECESSOR",
            receipt["blocking_detail"]["recovery"],
        )
        self.assertEqual(4, json_runner.call_count)
        self.assertEqual(
            previous_id,
            receipt["recovery_receipt"]["active_after"],
        )

    def test_full_receipt_write_failure_rolls_back_predecessor(
        self,
    ) -> None:
        """Compensate B when the final full receipt cannot be persisted."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        structured = [
            (
                passed_command(
                    argv=[sys.executable, "tools/vnext_cutover.py"],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                cutover_envelope(
                    previous_id=previous_id,
                    publication_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "restore",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="restore",
                    publication_id=publication_id,
                    previous_id=previous_id,
                ),
            ),
            (
                passed_command(
                    argv=[
                        sys.executable,
                        "tools/vnext_operator.py",
                        "rollback",
                    ],
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                ),
                switch_envelope(
                    command="rollback",
                    publication_id=previous_id,
                    previous_id=publication_id,
                ),
            ),
        ]
        real_atomic_write = __import__(
            "vnext.canonical", fromlist=["atomic_write_json"],
        ).atomic_write_json
        failed = False

        def fail_first_full_receipt(*, path, value):
            """Fail only the first top-level acceptance receipt write."""
            nonlocal failed
            if path.parent == Path(directory) and not failed:
                failed = True
                raise OSError("fixture full receipt write failure")
            real_atomic_write(path=path, value=value)

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=previous),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(current, previous, current),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ), mock.patch(
            "run_acceptance.run_json_command", side_effect=structured,
        ) as json_runner, mock.patch(
            "run_acceptance._validated_publication_state",
            side_effect=(
                {"state": previous, "publication_id": previous_id},
                {"state": current, "publication_id": publication_id},
                {"state": previous, "publication_id": previous_id},
            ),
        ), mock.patch(
            "run_acceptance.formal_evidence_binding",
            return_value={**acceptance_authority(), "bound": True},
        ), mock.patch(
            "run_acceptance.atomic_write_json",
            side_effect=fail_first_full_receipt,
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("FULL_RECEIPT_WRITE_FAILED", receipt["status"])
        self.assertEqual(
            "ROLLED_BACK_PREDECESSOR",
            receipt["blocking_detail"]["recovery"],
        )
        self.assertEqual(4, json_runner.call_count)
        self.assertEqual(
            previous_id,
            receipt["recovery_receipt"]["active_after"],
        )

    def test_human_review_blocker_is_preserved_as_acceptance_status(
        self,
    ) -> None:
        """Surface the HUMAN blocker without running terminal stages."""
        previous_id = "publication_" + "1" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        failed = passed_command(
            argv=[sys.executable, "tools/vnext_cutover.py"],
            environment={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        failed["outcome"] = "FAILED"
        failed["return_code"] = 2
        failed["reason"] = "NONZERO_RETURN_CODE"
        envelope = {
            "ok": False,
            "error": {
                "code": "HUMAN_REVIEW_REQUIRED",
                "message": "Explicit HUMAN decision is required.",
                "details": {},
            },
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            side_effect=(previous, previous, previous),
        ), mock.patch(
            "run_acceptance.run_command", side_effect=passed_command,
        ), mock.patch(
            "run_acceptance.run_json_command",
            return_value=(failed, envelope),
        ):
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("HUMAN_REVIEW_REQUIRED", receipt["status"])
        self.assertEqual(
            "HUMAN_REVIEW_REQUIRED",
            receipt["blocking_detail"]["code"],
        )
        self.assertIn(
            "tools/run_acceptance.py --scope full --execute-live",
            receipt["blocking_detail"]["resume_command"],
        )
        terminal_paths = {run_acceptance.TERMINAL_PUBLICATION_COMMAND}
        self.assertFalse(any(
            terminal_paths.intersection(row["argv"])
            for row in receipt["commands"]
        ))

    def test_human_after_unexpected_commit_recovers_predecessor(self) -> None:
        """Read back and reverse B even when the child reports HUMAN required."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        failed = passed_command(
            argv=[sys.executable, "tools/vnext_cutover.py"],
            environment={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        failed.update({
            "outcome": "FAILED",
            "return_code": 2,
            "reason": "NONZERO_RETURN_CODE",
        })
        envelope = {
            "ok": False,
            "error": {
                "code": "HUMAN_REVIEW_REQUIRED",
                "message": "Explicit HUMAN decision is required.",
                "details": {},
            },
        }
        recovery = {
            "command": passed_command(
                argv=[sys.executable, "tools/vnext_operator.py", "rollback"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            ),
            "error_code": "",
            "message": "",
            "ok": True,
            "receipt": {
                "receipt_id": "sha256:" + "3" * 64,
                "active_after": previous_id,
            },
            "state": previous,
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=previous),
        ), mock.patch(
            "run_acceptance.run_json_command",
            return_value=(failed, envelope),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            return_value=current,
        ) as readback, mock.patch(
            "run_acceptance._validated_publication_switch",
            return_value=recovery,
        ) as switch:
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("HUMAN_REVIEW_REQUIRED", receipt["status"])
        readback.assert_called_once_with(publication_root=REPO_ROOT)
        switch.assert_called_once()
        self.assertEqual(
            previous_id, switch.call_args.kwargs["target_publication_id"],
        )
        self.assertEqual(
            "ROLLED_BACK_PREDECESSOR",
            receipt["blocking_detail"]["recovery"],
        )
        self.assertIsNotNone(receipt["recovery_receipt"])

    def test_initial_human_side_effect_restores_no_pointer_bytes(self) -> None:
        """Restore exact legacy root bytes when no committed predecessor exists."""
        no_pointer = publication_state(publication_id=None, marker="0")
        publication_id = "publication_" + "2" * 64
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        failed = passed_command(
            argv=[sys.executable, "tools/vnext_cutover.py"],
            environment={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        failed.update({
            "outcome": "FAILED",
            "return_code": 2,
            "reason": "NONZERO_RETURN_CODE",
        })
        envelope = {
            "ok": False,
            "error": {
                "code": "HUMAN_REVIEW_REQUIRED",
                "message": "Explicit HUMAN decision is required.",
                "details": {},
            },
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=no_pointer),
        ), mock.patch(
            "run_acceptance._recorded_authority_backup", return_value={},
        ), mock.patch(
            "run_acceptance.run_json_command",
            return_value=(failed, envelope),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            return_value=current,
        ), mock.patch(
            "run_acceptance._restore_recorded_authority",
        ) as restore, mock.patch(
            "run_acceptance._recorded_state_snapshot",
            return_value=no_pointer,
        ), mock.patch(
            "run_acceptance._validated_publication_switch",
        ) as switch:
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("HUMAN_REVIEW_REQUIRED", receipt["status"])
        restore.assert_called_once()
        switch.assert_not_called()
        self.assertIsNone(receipt["recovery_receipt"]["active_after"])

    def test_resumed_cutover_uses_declared_predecessor_after_crash(
        self,
    ) -> None:
        """Continue a committed B resume instead of comparing B with prior A."""
        previous_id = "publication_" + "1" * 64
        publication_id = "publication_" + "2" * 64
        previous = publication_state(
            publication_id=previous_id, marker="1",
        )
        current = publication_state(
            publication_id=publication_id, marker="2",
        )
        envelope = cutover_envelope(
            previous_id=previous_id, publication_id=publication_id,
        )
        envelope["result"]["resumed_after_commit"] = True
        recovery = {
            "command": passed_command(
                argv=[sys.executable, "tools/vnext_operator.py", "rollback"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            ),
            "error_code": "",
            "message": "",
            "ok": True,
            "receipt": {
                "receipt_id": "sha256:" + "3" * 64,
                "active_after": previous_id,
            },
            "state": previous,
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "run_acceptance.external_blockers", return_value=[],
        ), mock.patch(
            "run_acceptance._recorded_gate_execution",
            return_value=recorded_evidence(state=current),
        ), mock.patch(
            "run_acceptance.run_json_command",
            return_value=(passed_command(
                argv=[sys.executable, "tools/vnext_cutover.py"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            ), envelope),
        ), mock.patch(
            "run_acceptance.publication_state_snapshot",
            return_value=current,
        ), mock.patch(
            "run_acceptance.run_command",
            side_effect=partial(
                failed_terminal_command,
                target=run_acceptance.TERMINAL_PUBLICATION_COMMAND,
            ),
        ), mock.patch(
            "run_acceptance._validated_publication_switch",
            return_value=recovery,
        ) as switch:
            receipt = execute_acceptance(
                repo_root=REPO_ROOT,
                scope="full",
                execute_live=True,
                current_python=sys.executable,
                python39="/python3.9",
                output_dir=Path(directory),
                timeout_seconds=30,
            )
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertEqual(
            "NEW_PUBLICATION_TERMINAL_VALIDATION_FAILED",
            receipt["blocking_detail"]["code"],
        )
        self.assertEqual(
            previous_id, switch.call_args.kwargs["target_publication_id"],
        )
        self.assertIsNone(
            switch.call_args.kwargs["expected_target_state"],
        )

    def test_formal_binding_rejects_minimal_self_signed_evidence(
        self,
    ) -> None:
        """Reject hashes without real Run, Batch, bundle, and fault proof."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(
                json.dumps({"run_id": "run:fixture"}), encoding="utf-8",
            )
            batch_path = root / "batch.json"
            batch_path.write_text("{}\n", encoding="utf-8")
            pointer_path = root / "outputs" / "active_publication.json"
            pointer_path.parent.mkdir()
            pointer_path.write_text("{}\n", encoding="utf-8")
            snapshot_path = (
                root / "outputs" / "validation_snapshot_provenance.json"
            )
            snapshot_path.write_text("{}\n", encoding="utf-8")
            publication_id = "publication_" + "2" * 64
            manifest_path = (
                root / "outputs/publications" / publication_id
                / "publication_manifest.json"
            )
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("{}\n", encoding="utf-8")
            acquisition_body = {
                "schema_version": 1,
                "receipt_type": "LIVE_SEC_ACQUISITION",
                "status": "PASSED",
            }
            acquisition = {
                **acquisition_body,
                "receipt_id": content_hash(value=acquisition_body),
            }
            acquisition_path = root / "sec_acquisition.json"
            acquisition_path.write_text(
                json.dumps(acquisition, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            fault_body = {
                "schema_version": 1,
                "scenario_id": "fixture-fault",
            }
            fault_id = content_hash(value=fault_body)
            fault = {**fault_body, "fault_receipt_id": fault_id}
            fault_path = (
                root / "outputs" / "publication_fault_receipts"
                / (fault_id.split(":", maxsplit=1)[1] + ".json")
            )
            fault_path.parent.mkdir()
            fault_path.write_text(
                json.dumps(fault, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            staging_body = {
                "schema_version": 1,
                "receipt_type": "TEN_COMPANY_STAGING_PARITY",
                "status": "PASS",
            }
            staging = {
                **staging_body,
                "receipt_id": content_hash(value=staging_body),
            }
            staging_path = root / "staging_parity.json"
            staging_path.write_text(
                json.dumps(staging, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            evidence_without_cutover = {
                "fault_injection_receipt_ids": [fault_id],
                "holdout_receipt_id": "sha256:" + "c" * 64,
                "legacy_invariant_migration_receipt_id": (
                    "sha256:" + "d" * 64
                ),
                "production_freeze_receipt_id": "sha256:" + "f" * 64,
                "second_layout_receipt_id": "sha256:" + "1" * 64,
                "sec_acquisition_receipt_id": acquisition["receipt_id"],
                "staging_parity_receipt_id": staging["receipt_id"],
            }
            cutover_body = {
                "schema_version": 1,
                "receipt_type": "FORMAL_VNEXT_CUTOVER",
                "status": "PASSED",
                **evidence_without_cutover,
            }
            cutover_receipt = {
                **cutover_body,
                "receipt_id": content_hash(value=cutover_body),
            }
            cutover_path = root / "cutover.json"
            cutover_path.write_text(
                json.dumps(cutover_receipt, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            attempts = []
            for ordinal in range(3):
                attempts.append({
                    "attempt_id": "sha256:" + str(ordinal) * 64,
                    "request_body_sha256": str(ordinal) * 64,
                    "assistant_output_sha256": "a" * 64,
                    "raw_response_sha256": str(ordinal) * 64,
                    "model_requested": "gpt-5.6-terra",
                    "model_returned": "gpt-5.6-terra",
                    "candidate_hash": "sha256:" + "3" * 64,
                    "evidence_check_id": "sha256:" + "4" * 64,
                    "review_unit_hash": "sha256:" + "5" * 64,
                    "error_class": "",
                    "run_id": "run:fixture",
                    "status": "FROZEN",
                    "transport_observation_hash": "sha256:" + "6" * 64,
                    "run_dir": str(run_dir),
                })
            cutover = {
                "acceptance_evidence": {
                    "cutover_receipt_id": cutover_receipt["receipt_id"],
                    **evidence_without_cutover,
                },
                "batch_manifest_id": "sha256:" + "6" * 64,
                "batch_manifest_path": str(batch_path),
                "cutover_receipt_path": str(cutover_path),
                "live_attempts": attempts,
                "publication_id": publication_id,
                "previous_publication_id": "publication_" + "1" * 64,
                "run_dirs": [str(run_dir)],
                "sec_acquisition_receipt_id": acquisition["receipt_id"],
                "sec_acquisition_receipt_path": str(acquisition_path),
                "staging_parity_receipt_path": str(staging_path),
                "validation_receipt_id": "sha256:" + "7" * 64,
            }
            with mock.patch(
                "run_acceptance.capture_source_snapshot",
                return_value=SourceSnapshot(
                    checkout_status="GIT_CLEAN",
                    source_commit="a" * 40,
                    tree_sha256="b" * 64,
                    file_count=1,
                    dirty_paths=(),
                ),
            ), mock.patch(
                "run_acceptance.load_requirement_snapshot",
                return_value={
                    "requirement_closure_hash": "sha256:" + "8" * 64,
                    "hashes": {"fsd_sha256": "9" * 64},
                    "effective_decisions": {
                        "D-01": {
                            "decision_id": "D-01",
                            "status": "APPROVED",
                            "choice": {
                                "provider": "openai",
                                "model": "gpt-5.6-terra",
                            },
                        },
                    },
                },
            ):
                with self.assertRaises(AcceptanceError):
                    formal_evidence_binding(
                        repo_root=root,
                        cutover_result=cutover,
                        final_state=publication_state(
                            publication_id=publication_id, marker="2",
                        ),
                        recorded_evidence={
                            "old_resolver_throws_receipt": {
                                "receipt_id": "sha256:" + "e" * 64,
                            },
                        },
                    )

    def test_full_binding_reuses_complete_sec_acquisition_schema(
        self,
    ) -> None:
        """Rebind the producer receipt through its strict current validator."""
        stages = (
            "scripts/00_smoke_test_sec_access.py",
            "scripts/01_resolve_companies.py",
            "scripts/02_inventory_filings.py",
            "scripts/03_companyfacts_inventory.py",
            "scripts/05_fetch_accession_materials.py",
        )
        body = {
            "schema_version": 1,
            "receipt_type": "LIVE_SEC_ACQUISITION",
            "executed_at_utc": "2026-08-06T00:00:00+00:00",
            "status": "PASSED",
            "runtime_bindings": {
                "$PYTHON_CURRENT": {
                    "name": "python-current",
                    "sha256": "3" * 64,
                }
            },
            "commands": [
                {
                    "argv": ["$PYTHON_CURRENT", stage],
                    "duration_ms": 1,
                    "error_class": "",
                    "return_code": 0,
                    "stderr_sha256": "1" * 64,
                    "stderr_size": 0,
                    "stdout_sha256": "2" * 64,
                    "stdout_size": 1,
                }
                for stage in stages
            ],
            "ledger_before": {
                "row_count": 0,
                "content_sha256": "4" * 64,
            },
            "ledger_after": {
                "row_count": 1,
                "content_sha256": "5" * 64,
            },
            "new_attempts": [{"attempt_id": "request:attempt:test"}],
            "inventory_artifacts": {
                "outputs/company_resolution.csv": {
                    "sha256": "6" * 64,
                    "size": 1,
                }
            },
        }
        receipt = {**body, "receipt_id": content_hash(value=body)}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = (
                root
                / "artifacts/vnext/cutover/receipts"
                / "sec_acquisition_{}.json".format(
                    str(receipt["receipt_id"]).split(":", maxsplit=1)[1]
                )
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(receipt, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            caller_path = root / "caller-authority.json"
            caller_path.write_text(
                json.dumps(receipt, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with mock.patch(
                "run_acceptance._validate_live_sec_acquisition_receipt",
                return_value=receipt,
            ) as validator:
                binding, payload = (
                    run_acceptance._validated_sec_acquisition_binding(
                        repo_root=root,
                        receipt_id=receipt["receipt_id"],
                        receipt_path=str(receipt_path),
                    )
                )
                with self.assertRaises(AcceptanceError):
                    run_acceptance._validated_sec_acquisition_binding(
                        repo_root=root,
                        receipt_id=receipt["receipt_id"],
                        receipt_path=caller_path,
                    )
        self.assertEqual(receipt["receipt_id"], binding["receipt_id"])
        self.assertEqual(
            receipt["runtime_bindings"], payload["runtime_bindings"],
        )
        validator.assert_called_once_with(repo_root=root, receipt=receipt)

    def test_full_scope_without_authorization_fails_before_commands(
        self,
    ) -> None:
        """Reject the former pseudo-full plan with one stable error."""
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("run_acceptance.run_command") as runner:
                receipt = execute_acceptance(
                    repo_root=REPO_ROOT,
                    scope="full",
                    execute_live=False,
                    current_python=sys.executable,
                    python39="/python3.9",
                    output_dir=Path(directory),
                    timeout_seconds=30,
                )
            self.assertEqual(
                "LIVE_EXECUTION_NOT_AUTHORIZED", receipt["status"],
            )
            self.assertEqual([], receipt["commands"])
            runner.assert_not_called()
            self.authority_runner.assert_not_called()

    def test_authorized_full_with_missing_prerequisite_runs_nothing(
        self,
    ) -> None:
        """Fail before SEC/OpenAI when a required secret is missing."""
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "", "SEC_CONTACT_EMAIL": ""},
        ):
            with mock.patch("run_acceptance.run_command") as runner:
                receipt = execute_acceptance(
                    repo_root=REPO_ROOT,
                    scope="full",
                    execute_live=True,
                    current_python=sys.executable,
                    python39="/python3.9",
                    output_dir=Path(directory),
                    timeout_seconds=30,
                )
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertTrue(receipt["external_blockers"])
        blocker_codes = {
            blocker["code"] for blocker in receipt["external_blockers"]
        }
        self.assertIn("OPENAI_API_KEY_REQUIRED", blocker_codes)
        self.assertNotIn(
            "ACTIVE_PUBLICATION_PREDECESSOR_REQUIRED", blocker_codes,
        )
        self.assertEqual([], receipt["commands"])
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
