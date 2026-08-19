"""Run the R4 fast local verification set concurrently.

Purpose:
    Provide the fast/local feedback loop inherited by Issue #15. Its D-26 tip
    keeps broad repository and isolated-workspace suites out of the required
    path while permitting short deterministic invariant tests.

Call relationships:
    Developers and ``tools/run_acceptance.py`` call this script.  Each selected
    unittest is a direct, non-isolated unit boundary and executes in a separate
    subprocess so independent checks use available CPU cores without sharing
    repository authority state.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
FAST_TESTS = (
    "tests.vnext.test_cutover_qualification.CutoverQualificationTest."
    "test_layout_terminal_requires_approval_publish_and_validation",
    "tests.vnext.test_ai_reader_contract.AiReaderContractTest."
    "test_deepseek_chat_envelope_is_json_and_tool_free",
    "tests.vnext.test_review_binding.ReviewBindingTest."
    "test_optional_system_decision_is_auditable",
    "tests.vnext.test_legacy_projector.LegacyProjectorTest."
    "test_legacy_inventory_binds_frozen_commit_and_source_blobs",
    "tests.vnext.test_issue15_authority.Issue15AuthorityTest."
    "test_issue15_snapshot_loads_and_preserves_parent_history",
    "tests.vnext.test_issue15_authority.Issue15AuthorityTest."
    "test_reusable_producer_scopes_match_exact_base_call_graph",
    "tests.vnext.test_acceptance_runner.AcceptanceRunnerTest."
    "test_r4_plan_uses_fast_runner_without_full_discovery",
)
FAST_TEST_TIMEOUT_SECONDS = 30


class FastTestError(ValueError):
    """Report an invalid fast-test CLI configuration."""


def _run_case(*, test_name: str) -> Dict[str, object]:
    """Execute one direct unittest case without sharing process state.

    Args:
        test_name: Fully qualified unittest method selected by R4.

    Returns:
        Test name, return code, duration, and bounded diagnostics.
    """
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args=[sys.executable, "-m", "unittest", "-q", test_name],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            encoding="utf-8",
            env=environment,
            timeout=FAST_TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        stderr = error.stderr
        stdout = error.stdout
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        return {
            "test": test_name,
            "return_code": 124,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stderr_tail": (
                (stderr or "")[-2000:]
                + "\nFAST_TEST_TIMEOUT_SECONDS={}\n".format(
                    FAST_TEST_TIMEOUT_SECONDS,
                )
            ),
            "stdout_tail": (stdout or "")[-2000:],
        }
    return {
        "test": test_name,
        "return_code": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stderr_tail": completed.stderr[-2000:],
        "stdout_tail": completed.stdout[-2000:],
    }


def run_fast_tests(*, jobs: int) -> Dict[str, object]:
    """Run the complete R4-selected test list with bounded concurrency.

    Args:
        jobs: Maximum number of independent test subprocesses to run at once.

    Returns:
        A deterministic summary labelled only as fast local evidence.

    Raises:
        FastTestError: If the requested concurrency is outside the safe range.
    """
    if jobs < 1 or jobs > len(FAST_TESTS):
        raise FastTestError("FAST_TEST_JOBS_INVALID")
    started = time.monotonic()
    # Every selected method avoids shared publication state, so process-level
    # concurrency shortens feedback without changing an authority boundary.
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=jobs,
    ) as executor:
        futures = {
            executor.submit(_run_case, test_name=test_name): test_name
            for test_name in FAST_TESTS
        }
        rows = [future.result() for future in futures]
    rows.sort(key=lambda row: str(row["test"]))
    return {
        "evidence_tier": "FAST_LOCAL_ONLY",
        "jobs": jobs,
        "per_case_timeout_seconds": FAST_TEST_TIMEOUT_SECONDS,
        "duration_seconds": round(time.monotonic() - started, 3),
        "tests": rows,
        "status": (
            "PASSED"
            if all(row["return_code"] == 0 for row in rows)
            else "FAILED"
        ),
    }


def main(*, argv: Sequence[str]) -> int:
    """Parse R4 fast-test options and emit a concise JSON summary.

    Args:
        argv: Command-line tokens excluding the executable name.

    Returns:
        Zero only when every selected direct test passes.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=min(4, len(FAST_TESTS)))
    parser.add_argument("--list", action="store_true")
    arguments = parser.parse_args(list(argv))
    if arguments.list:
        print(json.dumps({"tests": list(FAST_TESTS)}, ensure_ascii=False))
        return 0
    try:
        result = run_fast_tests(jobs=arguments.jobs)
    except FastTestError as error:
        print(json.dumps(
            {
                "status": "FAILED",
                "error_code": str(error),
                "evidence_tier": "FAST_LOCAL_ONLY",
            },
            ensure_ascii=False,
        ))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
