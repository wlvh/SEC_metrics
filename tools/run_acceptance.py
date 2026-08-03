"""Run deterministic acceptance gates and preserve exact command evidence.

The recorded scope runs only offline checks. The full scope records, but does
not bypass, external approval, valid SEC identity, clean-checkout, and live
stage prerequisites; it still executes the offline Stage 12 and snapshot
checker gates. Each command keeps exact argv, interpreter, return code,
duration, and stdout/stderr digests; skipped work is never labeled PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.canonical import atomic_write_json, content_hash  # noqa: E402
from vnext.canonical import sha256_file  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402
from sec_http import SecIdentityError, validate_sec_identity  # noqa: E402
from validation_provenance import (  # noqa: E402
    ValidationProvenanceError,
    capture_source_snapshot,
)


LIVE_STAGE_SCRIPTS = (
    "scripts/00_smoke_test_sec_access.py",
    "scripts/01_resolve_companies.py",
    "scripts/02_inventory_filings.py",
    "scripts/03_companyfacts_inventory.py",
    "scripts/04_compute_standard_metrics.py",
    "scripts/05_fetch_accession_materials.py",
    "scripts/06_parse_xbrl_instances.py",
    "scripts/07_extract_8k_events.py",
    "scripts/08_extract_def14a.py",
    "scripts/09_extract_mda_and_risk_text.py",
    "scripts/10_run_golden_assertions.py",
    "scripts/11_build_report.py",
)
OFFLINE_TERMINAL_SCRIPTS = (
    "scripts/12_validate_repair.py",
    "tools/check_validation_snapshot.py",
)
RECORDED_ARTIFACTS = (
    "outputs/scalability_audit.csv",
    "outputs/semantic_audit_receipt.json",
)


class AcceptanceError(RuntimeError):
    """Report invalid runner inputs or an unsafe acceptance environment."""


def utc_now() -> str:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(tz=timezone.utc).isoformat()


def sha256_bytes(*, content: bytes) -> str:
    """Return a lowercase SHA-256 digest for exact captured stream bytes.

    Args:
        content: Captured stdout or stderr bytes.

    Returns:
        Lowercase digest.
    """
    return hashlib.sha256(content).hexdigest()


def command_record(
    *,
    argv: Sequence[str],
    interpreter: str,
    outcome: str,
    return_code: Optional[int],
    duration_ms: int,
    stdout: bytes,
    stderr: bytes,
    reason: str,
    error_class: str,
    environment_keys: Sequence[str],
) -> Dict[str, object]:
    """Build one exact command evidence record without storing stream content.

    Args:
        argv: Exact executed or proposed argument vector.
        interpreter: Resolved interpreter path or executable identity.
        outcome: PASSED, FAILED, or NOT_RUN.
        return_code: Process return code, or ``None`` when not executed.
        duration_ms: Monotonic elapsed milliseconds.
        stdout: Captured standard output.
        stderr: Captured standard error.
        reason: Explicit skip/failure context.
        error_class: Runner-level exception class, if any.
        environment_keys: Names of injected variables; values are excluded.

    Returns:
        Serializable command receipt row.
    """
    return {
        "argv": list(argv),
        "interpreter": interpreter,
        "outcome": outcome,
        "return_code": return_code,
        "duration_ms": duration_ms,
        "stdout_sha256": sha256_bytes(content=stdout),
        "stdout_size": len(stdout),
        "stderr_sha256": sha256_bytes(content=stderr),
        "stderr_size": len(stderr),
        "reason": reason,
        "error_class": error_class,
        "environment_keys": list(environment_keys),
    }


def run_command(
    *,
    argv: Sequence[str],
    repo_root: Path,
    environment: Mapping[str, str],
    timeout_seconds: int,
) -> Dict[str, object]:
    """Execute one no-shell command and retain failure evidence.

    Args:
        argv: Exact non-empty argument vector.
        repo_root: Command working directory.
        environment: Additional environment values, never copied to receipt.
        timeout_seconds: Positive timeout.

    Returns:
        Command receipt row. A nonzero return code remains FAILED.
    """
    if not argv or timeout_seconds < 1:
        raise AcceptanceError("Command argv and timeout must be explicit")
    process_environment = dict(os.environ)
    process_environment.update(environment)
    started = time.monotonic_ns()
    stdout = b""
    stderr = b""
    return_code: Optional[int] = None
    error_class = ""
    reason = ""
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(repo_root),
            env=process_environment,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        return_code = completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, bytes) else b""
        stderr = error.stderr if isinstance(error.stderr, bytes) else b""
        error_class = type(error).__name__
        reason = "COMMAND_TIMEOUT"
    except OSError as error:
        error_class = type(error).__name__
        reason = "COMMAND_START_FAILED"
        stderr = str(error).encode("utf-8")
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    passed = return_code == 0 and not error_class
    if not passed and not reason:
        reason = "NONZERO_RETURN_CODE"
    return command_record(
        argv=argv,
        interpreter=str(argv[0]),
        outcome="PASSED" if passed else "FAILED",
        return_code=return_code,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        reason=reason,
        error_class=error_class,
        environment_keys=sorted(environment),
    )


def not_run_command(*, argv: Sequence[str], reason: str) -> Dict[str, object]:
    """Record one explicit unexecuted command.

    Args:
        argv: Exact command that remains unexecuted.
        reason: Stable blocker explanation.

    Returns:
        NOT_RUN command receipt row.
    """
    return command_record(
        argv=argv,
        interpreter=str(argv[0]),
        outcome="NOT_RUN",
        return_code=None,
        duration_ms=0,
        stdout=b"",
        stderr=b"",
        reason=reason,
        error_class="",
        environment_keys=[],
    )


def resolve_python39(*, explicit_path: Optional[str]) -> Optional[str]:
    """Resolve the Python 3.9 floor interpreter without guessing a fallback.

    Args:
        explicit_path: Optional caller-supplied interpreter.

    Returns:
        Executable path or ``None`` when unavailable.
    """
    candidate = (
        explicit_path
        if explicit_path is not None
        else shutil.which("python3.9")
    )
    if candidate is None:
        return None
    path = Path(candidate)
    return str(path.resolve()) if path.exists() else candidate


def external_blockers(*, repo_root: Path) -> List[Dict[str, str]]:
    """Return live/full acceptance prerequisites that are not satisfied.

    Args:
        repo_root: Repository containing Requirement and SEC config.

    Returns:
        Ordered blocker code/detail records.
    """
    blockers = []
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/ai_first_v3_3_1"
    )
    if "D-01" in requirement["pending_decision_ids"]:
        blockers.append(
            {
                "code": "D01_EXTERNAL_APPROVAL_PENDING",
                "detail": (
                    "Remote model, filing egress, retention, and provider "
                    "policy are unapproved."
                ),
            }
        )
    config_path = repo_root / "config/sec_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    try:
        validate_sec_identity(config=config)
    except SecIdentityError as error:
        blockers.append(
            {
                "code": "SEC_IDENTITY_INVALID",
                "detail": str(error),
            }
        )
    # Full acceptance must bind a committed source-input closure. Recording the
    # dirty state here prevents external approvals from masking local drift.
    try:
        capture_source_snapshot(workdir=repo_root)
    except ValidationProvenanceError as error:
        blockers.append({
            "code": "SOURCE_INPUT_CLOSURE_NOT_CLEAN",
            "detail": str(error),
        })
    return blockers


def recorded_commands(
    *, current_python: str, python39: Optional[str]
) -> List[Dict[str, object]]:
    """Build the deterministic offline command plan in TESTING.md order.

    Args:
        current_python: Default interpreter path.
        python39: Python 3.9 path or ``None``.

    Returns:
        Plan records with argv and optional skip reason.
    """
    plan: List[Dict[str, object]] = []
    vnext_args = [
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests/vnext",
        "-t",
        ".",
        "-p",
        "test_*.py",
        "-v",
    ]
    if python39 is None:
        plan.append(
            {
                "argv": ["python3.9", *vnext_args],
                "reason": "PYTHON39_INTERPRETER_NOT_FOUND",
            }
        )
    else:
        plan.append({"argv": [python39, *vnext_args], "reason": ""})
    plan.extend(
        [
            {
                "argv": [
                    current_python,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-t",
                    ".",
                    "-p",
                    "test_*.py",
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "-m",
                    "unittest",
                    "tests.test_validation_provenance",
                    "tests.test_validation_provenance_light_package",
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "tools/check_vnext_semantics.py",
                    "--repo-root",
                    ".",
                    "--output",
                    "outputs/semantic_audit_receipt.json",
                    "--secret-token-env",
                    "VNEXT_SECRET_SCAN_TOKEN",
                    "--secret-root",
                    "artifacts/vnext",
                    "--secret-root",
                    "outputs",
                ],
                "reason": "",
            },
            {
                "argv": [current_python, "tools/check_no_company_literals.py"],
                "reason": "",
            },
        ]
    )
    return plan


def artifact_hashes(*, repo_root: Path) -> Dict[str, str]:
    """Hash recorded-gate artifacts that exist after command execution.

    Args:
        repo_root: Repository root.

    Returns:
        Relative path to exact digest.
    """
    hashes = {}
    for relative in RECORDED_ARTIFACTS:
        path = repo_root / relative
        if path.is_file() and not path.is_symlink():
            hashes[relative] = sha256_file(path=path)
    return hashes


def execute_acceptance(
    *,
    repo_root: Path,
    scope: str,
    current_python: str,
    python39: Optional[str],
    output_dir: Path,
    timeout_seconds: int,
) -> Dict[str, object]:
    """Execute recorded gates and preserve full-scope blockers honestly.

    Args:
        repo_root: Repository root.
        scope: ``recorded`` or ``full``.
        current_python: Default interpreter.
        python39: Floor interpreter or ``None``.
        output_dir: Receipt directory.
        timeout_seconds: Per-command timeout.

    Returns:
        Complete acceptance receipt including its output path.
    """
    if scope not in {"recorded", "full"}:
        raise AcceptanceError("Acceptance scope is invalid")
    started_at = utc_now()
    blockers = external_blockers(repo_root=repo_root)
    commands = []
    secret_token = "scan-" + uuid.uuid4().hex
    for planned in recorded_commands(
        current_python=current_python, python39=python39,
    ):
        argv = planned["argv"]
        reason = str(planned["reason"])
        if reason:
            commands.append(not_run_command(argv=argv, reason=reason))
            continue
        environment = {"PYTHONDONTWRITEBYTECODE": "1"}
        if "--secret-token-env" in argv:
            environment["VNEXT_SECRET_SCAN_TOKEN"] = secret_token
        commands.append(
            run_command(
                argv=argv,
                repo_root=repo_root,
                environment=environment,
                timeout_seconds=timeout_seconds,
            )
        )
    if scope == "full":
        reason = ";".join(blocker["code"] for blocker in blockers)
        if not reason:
            reason = "LIVE_EXECUTION_REQUIRES_EXPLICIT_OPERATOR_RUN"
        for relative in LIVE_STAGE_SCRIPTS:
            commands.append(
                not_run_command(
                    argv=[current_python, relative], reason=reason,
                )
            )
        for relative in OFFLINE_TERMINAL_SCRIPTS:
            commands.append(
                run_command(
                    argv=[current_python, relative],
                    repo_root=repo_root,
                    environment={"PYTHONDONTWRITEBYTECODE": "1"},
                    timeout_seconds=timeout_seconds,
                )
            )
    failed = any(command["outcome"] == "FAILED" for command in commands)
    not_run = any(command["outcome"] == "NOT_RUN" for command in commands)
    if failed:
        status = "FAILED"
    elif scope == "full" and (blockers or not_run):
        status = "BLOCKED"
    elif not_run:
        status = "INCOMPLETE"
    else:
        status = "PASSED_RECORDED_ONLY" if scope == "recorded" else "PASSED"
    body = {
        "schema_version": 1,
        "scope": scope,
        "status": status,
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "commands": commands,
        "external_blockers": blockers,
        "artifact_hashes": artifact_hashes(repo_root=repo_root),
    }
    receipt_id = content_hash(value=body)
    receipt = dict(body)
    receipt["acceptance_receipt_id"] = receipt_id
    output_path = output_dir / (receipt_id.split(":", 1)[1] + ".json")
    atomic_write_json(path=output_path, value=receipt)
    receipt["output_path"] = str(output_path)
    return receipt


def main(*, argv: Sequence[str]) -> int:
    """Parse CLI arguments, run gates, and return nonzero on incomplete work.

    Args:
        argv: Command-line arguments excluding executable name.

    Returns:
        Zero only for a complete recorded scope or complete full acceptance.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--scope", choices=("recorded", "full"), default="recorded"
    )
    parser.add_argument("--python39")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--output-dir", default="outputs/acceptance_receipts")
    arguments = parser.parse_args(list(argv))
    repo_root = Path(arguments.repo_root).resolve()
    output_dir = repo_root / arguments.output_dir
    receipt = execute_acceptance(
        repo_root=repo_root,
        scope=arguments.scope,
        current_python=str(Path(sys.executable).resolve()),
        python39=resolve_python39(explicit_path=arguments.python39),
        output_dir=output_dir,
        timeout_seconds=arguments.timeout_seconds,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "acceptance_receipt_id": receipt["acceptance_receipt_id"],
                "output_path": receipt["output_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if receipt["status"] in {"PASSED", "PASSED_RECORDED_ONLY"} else 1


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
