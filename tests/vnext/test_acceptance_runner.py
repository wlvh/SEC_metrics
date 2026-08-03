"""Acceptance command-evidence and honest NOT_RUN status tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.vnext.common import REPO_ROOT
from sec_pipeline import build_readme
from validation_provenance import ensure_readme_routes


TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from run_acceptance import (  # noqa: E402
    execute_acceptance,
    external_blockers,
    recorded_commands,
    run_command,
)
from sec_http import SecIdentityError, load_config  # noqa: E402


def passed_command(**arguments):
    """Return one deterministic successful command receipt for plan tests.

    Args:
        arguments: Runner keyword arguments; only argv is reflected.

    Returns:
        Minimal command row compatible with receipt status aggregation.
    """
    return {
        "argv": list(arguments["argv"]),
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


def failed_stage12_command(**arguments):
    """Fail only the offline Stage 12 terminal gate in a mocked full run.

    Args:
        arguments: Runner keyword arguments containing the exact argv.

    Returns:
        Deterministic command evidence with Stage 12 marked FAILED.
    """
    record = passed_command(**arguments)
    if "scripts/12_validate_repair.py" in record["argv"]:
        record["outcome"] = "FAILED"
        record["return_code"] = 1
        record["reason"] = "NONZERO_RETURN_CODE"
    return record


class AcceptanceRunnerTest(unittest.TestCase):
    """Prove failures and external blockers cannot be reported as full PASS."""

    def test_sec_identity_gate_and_http_client_share_fail_fast_rules(
        self,
    ) -> None:
        """Reject blank, null, malformed, and example SEC identities twice."""
        invalid_identities = (
            {"organization": "", "contact_email": ""},
            {"organization": None, "contact_email": None},
            {"organization": "Fixture", "contact_email": "x"},
            {"organization": "   ", "contact_email": "ops@secmetrics.dev"},
            {
                "organization": "Fixture\nInjected",
                "contact_email": "ops@secmetrics.dev",
            },
            {"organization": "Fixture", "contact_email": "ops@corp.test"},
            {
                "organization": "Fixture",
                "contact_email": "test@example.com",
            },
        )
        for index, identity in enumerate(invalid_identities):
            with self.subTest(index=index), tempfile.TemporaryDirectory(
            ) as directory:
                root = Path(directory)
                config_path = root / "config" / "sec_config.json"
                config_path.parent.mkdir(parents=True)
                config = {
                    **identity,
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
                ):
                    blockers = external_blockers(repo_root=root)
                self.assertEqual(
                    ["SEC_IDENTITY_INVALID"],
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

    def test_readme_generator_keeps_recorded_scope_explicit(self) -> None:
        """Generate recorded commands without advertising full Cutover."""
        readme = build_readme()
        self.assertIn("## vNext recorded shadow（尚未切流）", readme)
        self.assertIn("tools/run_acceptance.py --scope recorded", readme)
        self.assertIn("PASSED_RECORDED_ONLY", readme)

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

    def test_full_discovery_uses_repository_top_level(self) -> None:
        """Prevent tests/vnext from colliding with scripts/vnext package."""
        plan = recorded_commands(
            current_python=sys.executable,
            python39="/python3.9",
        )
        vnext_argv = plan[0]["argv"]
        self.assertEqual(".", vnext_argv[vnext_argv.index("-t") + 1])
        full_argv = plan[1]["argv"]
        self.assertEqual(".", full_argv[full_argv.index("-t") + 1])

    def test_recorded_scope_is_labeled_recorded_only(self) -> None:
        """Keep offline success distinct from final live acceptance."""
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch(
                "run_acceptance.run_command", side_effect=passed_command
            ):
                receipt = execute_acceptance(
                    repo_root=REPO_ROOT,
                    scope="recorded",
                    current_python=sys.executable,
                    python39="/python3.9",
                    output_dir=Path(directory),
                    timeout_seconds=30,
                )
            self.assertEqual("PASSED_RECORDED_ONLY", receipt["status"])
            self.assertTrue(receipt["external_blockers"])
            self.assertTrue(Path(receipt["output_path"]).is_file())

    def test_full_scope_records_live_commands_as_blocked(self) -> None:
        """Block live stages but still execute both offline terminal gates."""
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch(
                "run_acceptance.run_command", side_effect=passed_command
            ):
                receipt = execute_acceptance(
                    repo_root=REPO_ROOT,
                    scope="full",
                    current_python=sys.executable,
                    python39="/python3.9",
                    output_dir=Path(directory),
                    timeout_seconds=30,
                )
            self.assertEqual("BLOCKED", receipt["status"])
            by_argv = {
                tuple(command["argv"]): command["outcome"]
                for command in receipt["commands"]
            }
            outcomes = list(by_argv.values())
            self.assertIn("NOT_RUN", outcomes)
            self.assertEqual(
                "NOT_RUN",
                by_argv[
                    (sys.executable, "scripts/00_smoke_test_sec_access.py")
                ],
            )
            self.assertEqual(
                "NOT_RUN",
                by_argv[(sys.executable, "scripts/11_build_report.py")],
            )
            self.assertEqual(
                "PASSED",
                by_argv[(sys.executable, "scripts/12_validate_repair.py")],
            )
            self.assertEqual(
                "PASSED",
                by_argv[(
                    sys.executable,
                    "tools/check_validation_snapshot.py",
                )],
            )
            self.assertNotEqual("PASSED", receipt["status"])

    def test_full_scope_fails_when_offline_terminal_gate_fails(self) -> None:
        """Do not let external blockers hide an executable offline failure."""
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch(
                "run_acceptance.run_command",
                side_effect=failed_stage12_command,
            ):
                receipt = execute_acceptance(
                    repo_root=REPO_ROOT,
                    scope="full",
                    current_python=sys.executable,
                    python39="/python3.9",
                    output_dir=Path(directory),
                    timeout_seconds=30,
                )
        self.assertEqual("FAILED", receipt["status"])


if __name__ == "__main__":
    unittest.main()
