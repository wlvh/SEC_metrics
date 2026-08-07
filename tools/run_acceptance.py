"""Run deterministic acceptance gates and preserve exact command evidence.

The recorded scope runs only offline checks. The full scope requires explicit
live authorization and then runs every live/Cutover/terminal command rather
than manufacturing a permanently NOT_RUN pseudo-full plan. Each command keeps
exact argv, interpreter, return code, duration, and stdout/stderr digests;
skipped work is never labeled PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.canonical import CanonicalError  # noqa: E402
from vnext.canonical import atomic_write_bytes, atomic_write_json  # noqa: E402
from vnext.canonical import content_hash  # noqa: E402
from vnext.canonical import sha256_file, strict_json_file  # noqa: E402
from vnext.cutover import CutoverError  # noqa: E402
from vnext.cutover import _validate_live_sec_acquisition_receipt  # noqa: E402
from vnext.cutover import _verify_live_attempt_audit_closure  # noqa: E402
from vnext.fault_matrix import FaultMatrixError  # noqa: E402
from vnext.fault_matrix import FAULT_MATRIX_SCENARIO_IDS  # noqa: E402
from vnext.fault_matrix import (  # noqa: E402
    resume_formal_publication_fault_matrix,
)
from vnext.projector import ProjectionError  # noqa: E402
from vnext.projector import load_projection_batch_manifest  # noqa: E402
from vnext.publication import PublicationError  # noqa: E402
from vnext.publication import PublicationView  # noqa: E402
from vnext.publication import ROOT_MIRROR_RELATIVE_PATHS  # noqa: E402
from vnext.publication import publication_state_snapshot  # noqa: E402
from vnext.report import validate_active_publication  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402
from vnext.run_store import RunStoreError, load_run_for_status  # noqa: E402
from vnext.terminal_cycle import TERMINAL_GATE_IDS  # noqa: E402
from sec_http import SecIdentityError, validate_sec_identity  # noqa: E402
from validation_provenance import (  # noqa: E402
    ValidationProvenanceError,
    capture_source_snapshot,
)


TERMINAL_PUBLICATION_COMMAND = "tools/vnext_terminal_cycle.py"
FULL_CUTOVER_COMMAND = "tools/vnext_cutover.py"
OLD_RESOLVER_FLOW_TEST = (
    "tests.vnext.test_cutover_orchestrator.CutoverOrchestratorTest."
    "test_public_cutover_ignores_all_retired_resolvers"
)
PUBLICATION_OPERATOR_COMMAND = "tools/vnext_operator.py"
ACTIVE_POINTER_PATH = Path("outputs/active_publication.json")
SNAPSHOT_PATH = Path("outputs/validation_snapshot_provenance.json")
SEC_LEDGER_AUTHORITY_PATHS = (
    Path("evidence/requests_log.csv"),
    Path("evidence/requests_log_manifest.json"),
)
PUBLICATION_AUXILIARY_AUTHORITY_PATHS = (
    Path("artifacts/vnext/latest_run_status.json"),
    Path("outputs/active_publication.json.lock"),
)
FORMAL_NAMESPACE_PATHS = (
    Path("artifacts/vnext/cutover"),
    Path("artifacts/vnext/qualification"),
    Path("evidence/request_attempts"),
    Path("outputs/publication_fault_receipts"),
    Path("outputs/publications"),
    Path("outputs/publication_switch_intents"),
    Path("outputs/publication_switch_receipts"),
    Path("outputs/vnext_cutover_audits"),
)
RECORDED_GATE_ARTIFACTS = (
    "scalability_audit.csv",
    "semantic_audit_receipt.json",
)
DEFAULT_TIMEOUT_SECONDS = 7200
NETWORK_DENY_SANDBOX_PROFILE = "(version 1) (allow default) (deny network*)"
OFFLINE_GUARD_SOURCE = b"""\
import sys


def _block_socket(event, _arguments):
    if event.startswith("socket."):
        raise PermissionError("RECORDED_SOCKET_BLOCKED")


sys.addaudithook(_block_socket)
"""


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


def _runtime_binding(*, executable: str) -> Dict[str, object]:
    """Describe one interpreter or sandbox executable without its host path.

    Args:
        executable: Exact executable used or planned by this acceptance run.

    Returns:
        Portable executable name, byte hash, and availability observation.
    """
    path = Path(executable)
    if not path.is_file():
        # Unit plans may use a deliberate nonexistent executable.  Persist the
        # absence explicitly; production resolution rejects it before use.
        return {
            "available": False,
            "executable_name": path.name,
            "sha256": "",
        }
    resolved = path.resolve(strict=True)
    return {
        "available": True,
        "executable_name": resolved.name,
        "sha256": sha256_file(path=resolved),
    }


def _receipt_runtime_context(
    *, repo_root: Path, output_dir: Path, current_python: str,
    python39: Optional[str],
) -> Tuple[Dict[str, object], Dict[str, str]]:
    """Bind exact runtime bytes and build host-path replacement tokens.

    Args:
        repo_root: Acceptance repository whose paths become portable.
        output_dir: Receipt destination, which may be a test temporary root.
        current_python: Default interpreter executable.
        python39: Validated floor interpreter or ``None`` when not run.

    Returns:
        Runtime binding table and exact-string replacement mapping.
    """
    bindings: Dict[str, object] = {}
    replacements = {
        str(repo_root): "$REPO_ROOT",
        str(repo_root.resolve(strict=True)): "$REPO_ROOT",
        str(output_dir): "$ACCEPTANCE_OUTPUT",
        str(output_dir.resolve(strict=False)): "$ACCEPTANCE_OUTPUT",
    }
    executable_roles = [("$PYTHON_CURRENT", current_python)]
    if python39 is not None:
        executable_roles.append(("$PYTHON39", python39))
    sandbox = Path("/usr/bin/sandbox-exec")
    if sandbox.is_file():
        executable_roles.append(("$SANDBOX_EXEC", str(sandbox)))
    for role, executable in executable_roles:
        # Both the requested and resolved spelling map to a role whose binary
        # digest preserves exact interpreter identity without the local path.
        bindings[role] = _runtime_binding(executable=executable)
        replacements[executable] = role
        path = Path(executable)
        if path.is_file():
            replacements[str(path.resolve(strict=True))] = role
    return bindings, replacements


def _portable_receipt_string(
    *, value: str, replacements: Mapping[str, str]
) -> str:
    """Replace host-local path material with content-bound portable tokens.

    Args:
        value: Arbitrary nested receipt string.
        replacements: Exact local prefixes to portable authority tokens.

    Returns:
        String containing no disclosed host-local absolute path.
    """
    portable = value
    for local in sorted(replacements, key=len, reverse=True):
        if local:
            portable = portable.replace(local, replacements[local])
    # Error text can embed a path not owned by the repository.  Preserve its
    # identity by hash while removing the machine-specific disclosure.
    host_path = re.compile(
        r"(?<![A-Za-z0-9:/])/(?:[A-Za-z0-9._@+~-]+/)+"
        r"[A-Za-z0-9._@+~-]+"
    )

    def replace_match(match: re.Match[str]) -> str:
        """Hash one residual absolute path found inside diagnostic text."""
        raw_path = match.group(0)
        return "$HOST_PATH_SHA256:" + sha256_bytes(
            content=raw_path.encode("utf-8")
        )

    portable = host_path.sub(replace_match, portable)
    if portable.startswith("/"):
        return "$HOST_PATH_SHA256:" + sha256_bytes(
            content=portable.encode("utf-8")
        )
    return portable


def _portable_receipt_value(
    *, value: object, replacements: Mapping[str, str]
) -> object:
    """Recursively remove local absolute paths from a receipt value.

    Args:
        value: JSON-compatible acceptance receipt value.
        replacements: Runtime and workspace path-to-token bindings.

    Returns:
        JSON-compatible value safe for durable repository publication.
    """
    if isinstance(value, dict):
        # Receipt mappings are rebuilt so nested command and error structures
        # cannot bypass the same portability boundary.
        return {
            key: _portable_receipt_value(
                value=value[key], replacements=replacements,
            )
            for key in value
        }
    if isinstance(value, (list, tuple)):
        return [
            _portable_receipt_value(value=item, replacements=replacements)
            for item in value
        ]
    if isinstance(value, str):
        return _portable_receipt_string(
            value=value, replacements=replacements,
        )
    return value


def _persist_acceptance_receipt(
    *, output_dir: Path, body: Mapping[str, object], repo_root: Path,
    current_python: str, python39: Optional[str],
) -> Tuple[Dict[str, object], Path]:
    """Write one content-addressed receipt through the portability boundary.

    Args:
        output_dir: Repository-owned or test-isolated receipt directory.
        body: Complete semantic receipt body without its self-identity.
        repo_root: Acceptance repository used for portable path tokens.
        current_python: Default interpreter used by the command plan.
        python39: Validated floor interpreter or ``None`` when absent.

    Returns:
        Persisted receipt mapping and its local locator.
    """
    runtime_bindings, replacements = _receipt_runtime_context(
        repo_root=repo_root,
        output_dir=output_dir,
        current_python=current_python,
        python39=python39,
    )
    with_runtime = dict(body)
    with_runtime["runtime_bindings"] = runtime_bindings
    portable = _portable_receipt_value(
        value=with_runtime, replacements=replacements,
    )
    if not isinstance(portable, dict):
        raise AcceptanceError("ACCEPTANCE_RECEIPT_ROOT_INVALID")
    receipt_id = content_hash(value=portable)
    receipt = dict(portable)
    receipt["acceptance_receipt_id"] = receipt_id
    output_path = output_dir / (receipt_id.split(":", 1)[1] + ".json")
    atomic_write_json(path=output_path, value=receipt)
    return receipt, output_path


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
    execution_wrapper: Sequence[str] = (),
    sandbox_profile_sha256: str = "",
    executed_argv: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Build one exact command evidence record without storing stream content.

    Args:
        argv: Logical command argument vector before an OS sandbox wrapper.
        interpreter: Resolved interpreter path or executable identity.
        outcome: PASSED, FAILED, or NOT_RUN.
        return_code: Process return code, or ``None`` when not executed.
        duration_ms: Monotonic elapsed milliseconds.
        stdout: Captured standard output.
        stderr: Captured standard error.
        reason: Explicit skip/failure context.
        error_class: Runner-level exception class, if any.
        environment_keys: Names of injected variables; values are excluded.
        execution_wrapper: OS process wrapper applied before the logical argv.
        sandbox_profile_sha256: Exact sandbox policy digest, when applicable.
        executed_argv: Exact OS argument vector, including any wrapper.

    Returns:
        Serializable command receipt row.
    """
    return {
        "argv": list(argv),
        "executed_argv": list(argv if executed_argv is None else executed_argv),
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
        "execution_wrapper": list(execution_wrapper),
        "sandbox_profile_sha256": sandbox_profile_sha256,
    }


def _execute_command(
    *,
    argv: Sequence[str],
    repo_root: Path,
    environment: Mapping[str, Optional[str]],
    timeout_seconds: int,
    sandbox_profile: Optional[str] = None,
) -> Tuple[Dict[str, object], bytes]:
    """Execute one no-shell command and return evidence plus transient stdout.

    Args:
        argv: Exact non-empty argument vector.
        repo_root: Command working directory.
        environment: Environment overrides. ``None`` removes one inherited
            variable before the child starts.
        timeout_seconds: Positive timeout.
        sandbox_profile: Optional macOS process-tree sandbox policy.

    Returns:
        Command receipt row and exact stdout bytes. The bytes are only for
        parsing a structured command response and are never persisted raw.
    """
    if not argv or timeout_seconds < 1:
        raise AcceptanceError("Command argv and timeout must be explicit")
    process_environment = dict(os.environ)
    for key, value in environment.items():
        if value is None:
            process_environment.pop(key, None)
        else:
            process_environment[key] = value
    execution_wrapper: List[str] = []
    executed_argv = list(argv)
    if sandbox_profile is not None:
        sandbox_executable = Path("/usr/bin/sandbox-exec")
        if not sandbox_executable.is_file():
            raise AcceptanceError("OFFLINE_PROCESS_SANDBOX_REQUIRED")
        execution_wrapper = [
            str(sandbox_executable), "-p", sandbox_profile,
        ]
        executed_argv = [*execution_wrapper, *argv]
    started = time.monotonic_ns()
    stdout = b""
    stderr = b""
    return_code: Optional[int] = None
    error_class = ""
    reason = ""
    try:
        completed = subprocess.run(
            executed_argv,
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
    record = command_record(
        argv=argv, interpreter=str(argv[0]),
        outcome="PASSED" if passed else "FAILED",
        return_code=return_code, duration_ms=duration_ms,
        stdout=stdout, stderr=stderr, reason=reason,
        error_class=error_class,
        environment_keys=sorted(environment),
        execution_wrapper=execution_wrapper,
        sandbox_profile_sha256=(
            sha256_bytes(content=sandbox_profile.encode("utf-8"))
            if sandbox_profile is not None else ""
        ),
        executed_argv=executed_argv,
    )
    return record, stdout


def run_command(
    *,
    argv: Sequence[str],
    repo_root: Path,
    environment: Mapping[str, Optional[str]],
    timeout_seconds: int,
    sandbox_profile: Optional[str] = None,
) -> Dict[str, object]:
    """Execute one no-shell command and persist only digest evidence.

    Args:
        argv: Exact non-empty argument vector.
        repo_root: Command working directory.
        environment: Environment overrides; ``None`` deletes a variable.
        timeout_seconds: Positive timeout.
        sandbox_profile: Optional process-tree network/file policy.

    Returns:
        Command receipt row. A nonzero return code remains FAILED.
    """
    record, _stdout = _execute_command(
        argv=argv,
        repo_root=repo_root,
        environment=environment,
        timeout_seconds=timeout_seconds,
        sandbox_profile=sandbox_profile,
    )
    return record


def run_json_command(
    *,
    argv: Sequence[str],
    repo_root: Path,
    environment: Mapping[str, Optional[str]],
    timeout_seconds: int,
    sandbox_profile: Optional[str] = None,
) -> Tuple[Dict[str, object], Optional[Dict[str, object]]]:
    """Execute a JSON CLI and parse its envelope without retaining raw output.

    Args:
        argv: Exact JSON-producing command.
        repo_root: Command working directory.
        environment: Explicit environment overrides.
        timeout_seconds: Positive command timeout.
        sandbox_profile: Optional process-tree network/file policy.

    Returns:
        Command evidence and the parsed JSON object, or ``None`` on malformed
        output. Successful commands with malformed output are changed to
        ``FAILED`` so digest-only evidence cannot conceal an unreadable
        result.
    """
    record, stdout = _execute_command(
        argv=argv,
        repo_root=repo_root,
        environment=environment,
        timeout_seconds=timeout_seconds,
        sandbox_profile=sandbox_profile,
    )
    parsed: Optional[Dict[str, object]] = None
    try:
        value = json.loads(stdout.decode("utf-8"))
        if type(value) is dict:
            parsed = value
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if record["outcome"] == "PASSED" and parsed is None:
        record["outcome"] = "FAILED"
        record["reason"] = "STRUCTURED_OUTPUT_INVALID"
    return record, parsed


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


def _native_executable(*, path: Path) -> bool:
    """Return whether a regular executable has a native binary header.

    Args:
        path: Resolved candidate executable.

    Returns:
        True for Mach-O, ELF, or PE binaries; scripts and shims are false.
    """
    if not path.is_file() or not os.access(path, os.X_OK):
        return False
    with path.open(mode="rb") as file_obj:
        magic = file_obj.read(4)
    return magic in {
        b"\x7fELF",
        b"MZ\x90\x00",
        b"\xca\xfe\xba\xbe",
        b"\xbe\xba\xfe\xca",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
    }


def _formal_probe_authority_backup(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Back up every formal file and namespace before executable probing.

    Args:
        repo_root: Repository whose formal authority must remain unchanged.

    Returns:
        Exact byte backup for protected singleton files and namespace trees.
    """
    root = repo_root.resolve(strict=True)
    single_files: Dict[str, Optional[bytes]] = {}
    for relative in _recorded_protected_file_relative_paths():
        path = root / relative
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise AcceptanceError("Recorded authority path is unsafe")
        single_files[relative.as_posix()] = (
            path.read_bytes() if path.exists() else None
        )
    namespaces = {}
    for relative in FORMAL_NAMESPACE_PATHS:
        tree = _recorded_namespace_tree(
            repo_root=root, relative_root=relative,
        )
        namespaces[relative.as_posix()] = {
            "exists": tree["exists"],
            "directories": list(tree["directories"]),
            "files": {
                name: (root / name).read_bytes()
                for name in tree["files"]
            },
        }
    return {"single_files": single_files, "namespaces": namespaces}


def _restore_formal_probe_authority(
    *, repo_root: Path, backup: Mapping[str, object],
) -> None:
    """Restore the complete formal authority after a hostile probe drift.

    Args:
        repo_root: Repository whose explicit formal paths may be restored.
        backup: Exact value returned by
            :func:`_formal_probe_authority_backup`.
    """
    if set(backup) != {"single_files", "namespaces"}:
        raise AcceptanceError("Formal probe backup schema differs")
    root = repo_root.resolve(strict=True)
    namespaces = backup["namespaces"]
    if type(namespaces) is not dict or set(namespaces) != {
        value.as_posix() for value in FORMAL_NAMESPACE_PATHS
    }:
        raise AcceptanceError("Formal probe namespace backup differs")
    for relative_text in sorted(namespaces):
        relative = Path(relative_text)
        path = root / relative
        parent = root
        for part in relative.parts[:-1]:
            parent /= part
            if parent.is_symlink():
                raise AcceptanceError("Formal probe parent is unsafe")
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
        expected = namespaces[relative_text]
        if type(expected) is not dict or set(expected) != {
            "exists", "directories", "files",
        }:
            raise AcceptanceError("Formal probe namespace schema differs")
        if expected["exists"] is True:
            for directory in sorted(
                expected["directories"],
                key=lambda value: (len(Path(value).parts), value),
            ):
                (root / str(directory)).mkdir(parents=True, exist_ok=True)
            for name in sorted(expected["files"]):
                atomic_write_bytes(
                    path=root / name, content=expected["files"][name],
                )
        elif expected["exists"] is not False:
            raise AcceptanceError("Formal probe namespace state differs")
    single_files = backup["single_files"]
    expected_names = {
        value.as_posix()
        for value in _recorded_protected_file_relative_paths()
    }
    if type(single_files) is not dict or set(single_files) != expected_names:
        raise AcceptanceError("Formal probe file backup differs")
    for relative_text in sorted(single_files):
        path = root / relative_text
        parent = root
        for part in Path(relative_text).parts[:-1]:
            parent /= part
            if parent.is_symlink():
                raise AcceptanceError("Formal probe parent is unsafe")
        expected_bytes = single_files[relative_text]
        if path.is_symlink():
            path.unlink()
        elif path.exists() and not path.is_file():
            raise AcceptanceError("Formal probe path is unsafe")
        if expected_bytes is None:
            if path.exists():
                path.unlink()
        else:
            atomic_write_bytes(path=path, content=expected_bytes)


def _recover_formal_probe_drift(
    *, repo_root: Path, backup: Mapping[str, object],
    before: Mapping[str, object],
) -> None:
    """Restore and exact-read back one mutated executable preflight.

    Args:
        repo_root: Formal repository authority.
        backup: Complete pre-probe byte backup.
        before: Exact pre-probe formal state snapshot.
    """
    _restore_formal_probe_authority(repo_root=repo_root, backup=backup)
    if _recorded_state_snapshot(repo_root=repo_root) != before:
        raise AcceptanceError("PYTHON39_AUTHORITY_RECOVERY_FAILED")


def resolve_python39(
    *, explicit_path: Optional[str], repo_root: Path = REPO_ROOT,
) -> Optional[str]:
    """Resolve a native CPython 3.9 under complete formal-state isolation.

    Args:
        explicit_path: Optional caller-supplied interpreter.
        repo_root: Formal repository captured before the executable starts.

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
    resolved = shutil.which(candidate)
    if resolved is None:
        if explicit_path is None:
            return None
        raise AcceptanceError("PYTHON39_INTERPRETER_INVALID")
    executable_path = Path(resolved).resolve(strict=True)
    if not _native_executable(path=executable_path):
        if explicit_path is None:
            return None
        raise AcceptanceError("PYTHON39_INTERPRETER_INVALID")
    executable = str(executable_path)
    backup = _formal_probe_authority_backup(repo_root=repo_root)
    before = _recorded_state_snapshot(repo_root=repo_root)
    probe_source = (
        "import hashlib,json,pathlib,sys\n"
        "path=pathlib.Path(sys.executable).resolve()\n"
        "print(json.dumps({"
        "'cache_tag':sys.implementation.cache_tag,"
        "'executable_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),"
        "'implementation':sys.implementation.name,"
        "'isolated':sys.flags.isolated,"
        "'no_site':sys.flags.no_site,"
        "'version':list(sys.version_info[:2])"
        "},sort_keys=True,separators=(',',':')))"
    )
    record, stdout = _execute_command(
        argv=[
            executable,
            "-I",
            "-S",
            "-c",
            probe_source,
        ],
        repo_root=repo_root,
        environment={
            "OPENAI_API_KEY": None,
            "SEC_CONTACT_EMAIL": None,
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        timeout_seconds=30,
        sandbox_profile=_offline_sandbox_profile(
            repo_root=repo_root, protect_authority=True,
        ),
    )
    try:
        after = _recorded_state_snapshot(repo_root=repo_root)
    except (AcceptanceError, OSError, PublicationError, ValueError) as error:
        _recover_formal_probe_drift(
            repo_root=repo_root, backup=backup, before=before,
        )
        raise AcceptanceError("PYTHON39_AUTHORITY_OBSERVATION_FAILED") from error
    if after != before:
        _recover_formal_probe_drift(
            repo_root=repo_root, backup=backup, before=before,
        )
        raise AcceptanceError("PYTHON39_PROBE_MUTATED_FORMAL_AUTHORITY")
    try:
        observation = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        observation = None
    expected_observation = {
        "cache_tag": "cpython-39",
        "executable_sha256": sha256_file(path=executable_path),
        "implementation": "cpython",
        "isolated": 1,
        "no_site": 1,
        "version": [3, 9],
    }
    if record["outcome"] != "PASSED" or observation != expected_observation:
        if explicit_path is None:
            return None
        raise AcceptanceError("PYTHON39_INTERPRETER_INVALID")
    return executable


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
    if (
        "OPENAI_API_KEY" not in os.environ
        or not os.environ["OPENAI_API_KEY"].strip()
    ):
        blockers.append({
            "code": "OPENAI_API_KEY_REQUIRED",
            "detail": "OPENAI_API_KEY is required for full live acceptance.",
        })
    config_path = repo_root / "config/sec_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    try:
        validate_sec_identity(config=config)
    except SecIdentityError as error:
        blockers.append(
            {
                "code": error.code,
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
    *,
    current_python: str,
    python39: Optional[str],
    gate_output_dir: Path,
) -> List[Dict[str, object]]:
    """Build the deterministic offline command plan in TESTING.md order.

    Args:
        current_python: Default interpreter path.
        python39: Python 3.9 path or ``None``.
        gate_output_dir: Isolated non-mirror directory for gate artifacts.

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
                "argv": [current_python, *vnext_args],
                "reason": "",
            },
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
                    "-v",
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "-m",
                    "unittest",
                    OLD_RESOLVER_FLOW_TEST,
                    "-v",
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "-m",
                    "unittest",
                    "tests.test_validation_provenance",
                    "-v",
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "-m",
                    "unittest",
                    "tests.test_validation_provenance_light_package",
                    "-v",
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "-m",
                    "unittest",
                    "tests.vnext.test_canonical_hashes",
                    "tests.vnext.test_record_schemas",
                    "tests.vnext.test_spec_compiler",
                    "tests.vnext.test_review_binding",
                    "tests.vnext.test_replay",
                    "-v",
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
                    str(gate_output_dir / "semantic_audit_receipt.json"),
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
                "argv": [
                    current_python,
                    "tools/check_no_company_literals.py",
                    "--output",
                    str(gate_output_dir / "scalability_audit.csv"),
                ],
                "reason": "",
            },
            {
                "argv": [
                    current_python,
                    "tools/check_capability_contract_alignment.py",
                ],
                "reason": "",
            },
        ]
    )
    return plan


def artifact_hashes(*, gate_output_dir: Path) -> Dict[str, str]:
    """Hash isolated recorded-gate artifacts that actually exist.

    Args:
        gate_output_dir: Non-mirror output directory owned by this run.

    Returns:
        Artifact name to exact digest.
    """
    hashes = {}
    for name in RECORDED_GATE_ARTIFACTS:
        path = gate_output_dir / name
        if path.is_file() and not path.is_symlink():
            hashes[name] = sha256_file(path=path)
    return hashes


def _offline_environment(*, guard_dir: Path) -> Dict[str, Optional[str]]:
    """Create the Python audit-hook guard used by every recorded command.

    Args:
        guard_dir: Isolated directory for ``sitecustomize.py``.

    Returns:
        Environment additions that block every Python socket audit event.
    """
    guard_path = guard_dir / "sitecustomize.py"
    atomic_write_bytes(path=guard_path, content=OFFLINE_GUARD_SOURCE)
    python_path = str(guard_dir)
    if "PYTHONPATH" in os.environ and os.environ["PYTHONPATH"]:
        python_path += os.pathsep + os.environ["PYTHONPATH"]
    return {
        "OPENAI_API_KEY": None,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": python_path,
        "SEC_CONTACT_EMAIL": None,
    }


def _sandbox_literal(*, value: Path) -> str:
    """Quote one absolute path for a macOS sandbox literal expression.

    Args:
        value: Absolute file target whose writes must be denied.

    Returns:
        Escaped sandbox expression fragment.
    """
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '(literal "{}")'.format(escaped)


def _sandbox_subpath(*, value: Path) -> str:
    """Quote one absolute directory for a recursive sandbox deny.

    Args:
        value: Absolute namespace root whose complete subtree is immutable.

    Returns:
        Escaped macOS sandbox ``subpath`` expression fragment.
    """
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '(subpath "{}")'.format(escaped)


def _offline_sandbox_profile(
    *, repo_root: Path, protect_authority: bool,
) -> str:
    """Return a process-tree policy that denies network and authority writes.

    Args:
        repo_root: Repository owning formal publication paths.
        protect_authority: Whether root pointer/mirror writes are forbidden.

    Returns:
        Exact macOS sandbox policy persisted by digest in command evidence.
    """
    clauses = ["(version 1)", "(allow default)", "(deny network*)"]
    if protect_authority:
        literals = " ".join(
            _sandbox_literal(value=repo_root / relative)
            for relative in _recorded_protected_file_relative_paths()
        )
        namespaces = " ".join(
            "{} {}".format(
                _sandbox_literal(value=repo_root / relative),
                _sandbox_subpath(value=repo_root / relative),
            )
            for relative in FORMAL_NAMESPACE_PATHS
        )
        clauses.append(
            "(deny file-write* {} {})".format(literals, namespaces)
        )
    return " ".join(clauses)


def _recorded_authority_relative_paths() -> Tuple[Path, ...]:
    """Return the exact formal pointer, mirrors, and sidecar path set."""
    values = {
        ACTIVE_POINTER_PATH,
        SNAPSHOT_PATH,
        *(Path(value) for value in ROOT_MIRROR_RELATIVE_PATHS.values()),
    }
    return tuple(sorted(values, key=lambda value: value.as_posix()))


def _recorded_protected_file_relative_paths() -> Tuple[Path, ...]:
    """Return formal single-file paths blocked only in recorded scope."""
    values = {
        *_recorded_authority_relative_paths(),
        *SEC_LEDGER_AUTHORITY_PATHS,
        *PUBLICATION_AUXILIARY_AUTHORITY_PATHS,
    }
    return tuple(sorted(values, key=lambda value: value.as_posix()))


def _recorded_namespace_tree(
    *, repo_root: Path, relative_root: Path,
) -> Dict[str, object]:
    """Capture one exact optional formal namespace without aliases.

    Args:
        repo_root: Fixed repository root owning the namespace.
        relative_root: Repository-relative formal directory root.

    Returns:
        Presence, exact directory set, and regular-file hash/size mapping.

    Raises:
        AcceptanceError: When any path component is an alias or special file.
    """
    repository = repo_root.resolve(strict=True)
    path = repository / relative_root
    current = repository
    for part in relative_root.parts:
        current /= part
        if current.is_symlink() or (
            current.exists() and not current.is_dir()
        ):
            raise AcceptanceError("Recorded formal namespace is unsafe")
    if not path.exists():
        return {"exists": False, "directories": [], "files": {}}
    if not path.is_dir():
        raise AcceptanceError("Recorded formal namespace is unsafe")
    directories = [relative_root.as_posix()]
    files = {}
    for entry in sorted(path.rglob("*")):
        if entry.is_symlink():
            raise AcceptanceError("Recorded formal namespace is unsafe")
        relative = entry.relative_to(repository).as_posix()
        if entry.is_dir():
            directories.append(relative)
        elif entry.is_file():
            files[relative] = {
                "sha256": sha256_file(path=entry),
                "size": entry.stat().st_size,
            }
        else:
            raise AcceptanceError("Recorded formal namespace is unsafe")
    return {
        "exists": True,
        "directories": sorted(directories),
        "files": files,
    }


def _recorded_formal_namespace_snapshot(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Capture every formal namespace that recorded gates cannot mutate.

    Args:
        repo_root: Repository whose formal namespaces remain immutable.

    Returns:
        Exact namespace-root mapping suitable for before/after equality.
    """
    return {
        relative.as_posix(): _recorded_namespace_tree(
            repo_root=repo_root, relative_root=relative,
        )
        for relative in FORMAL_NAMESPACE_PATHS
    }


def _recorded_authority_backup(
    *, repo_root: Path,
) -> Dict[str, Optional[bytes]]:
    """Capture exact root authority bytes before offline commands run.

    Args:
        repo_root: Formal repository root.

    Returns:
        Repository-relative file names mapped to bytes or absence.
    """
    backup: Dict[str, Optional[bytes]] = {}
    for relative in _recorded_authority_relative_paths():
        path = repo_root / relative
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise AcceptanceError("Recorded authority path is unsafe")
        backup[relative.as_posix()] = (
            path.read_bytes() if path.exists() else None
        )
    return backup


def _restore_recorded_authority(
    *, repo_root: Path, backup: Mapping[str, Optional[bytes]],
) -> None:
    """Restore exact pre-recorded pointer/mirror bytes after any drift.

    Args:
        repo_root: Formal repository root.
        backup: Exact value returned by :func:`_recorded_authority_backup`.
    """
    expected_names = {
        relative.as_posix()
        for relative in _recorded_authority_relative_paths()
    }
    if set(backup) != expected_names:
        raise AcceptanceError("Recorded authority backup set differs")
    root = repo_root.resolve(strict=True)
    for relative_text in sorted(backup):
        relative = Path(relative_text)
        path = repo_root / relative
        parent = path.parent
        candidate = repo_root
        for part in relative.parts[:-1]:
            candidate /= part
            if candidate.is_symlink():
                raise AcceptanceError("Recorded authority parent is unsafe")
        try:
            parent.resolve(strict=False).relative_to(root)
        except ValueError as error:
            raise AcceptanceError(
                "Recorded authority restore escaped repository"
            ) from error
        expected = backup[relative_text]
        if path.is_symlink():
            path.unlink()
        elif path.exists() and not path.is_file():
            raise AcceptanceError("Recorded authority path is unsafe")
        if expected is None:
            if path.exists():
                path.unlink()
        else:
            atomic_write_bytes(path=path, content=expected)


def _recorded_state_snapshot(*, repo_root: Path) -> Dict[str, object]:
    """Read exact formal pointer, mirrors, ledger, and namespace identities.

    Args:
        repo_root: Formal repository root.

    Returns:
        Publication state plus byte hashes for files whose bytes are not fully
        represented by the active publication ID and mirror mapping.
    """
    state = publication_state_snapshot(publication_root=repo_root)
    authority_hashes = {}
    for relative in (
        ACTIVE_POINTER_PATH,
        SNAPSHOT_PATH,
        *SEC_LEDGER_AUTHORITY_PATHS,
        *PUBLICATION_AUXILIARY_AUTHORITY_PATHS,
    ):
        path = repo_root / relative
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise AcceptanceError("Recorded authority path is unsafe")
        authority_hashes[relative.as_posix()] = (
            sha256_file(path=path) if path.exists() else None
        )
    return {
        "active_publication_id": state["active_publication_id"],
        "mirror_hashes": state["mirror_hashes"],
        "authority_hashes": authority_hashes,
        "formal_namespace_trees": _recorded_formal_namespace_snapshot(
            repo_root=repo_root,
        ),
    }


def _recorded_gate_execution(
    *,
    repo_root: Path,
    current_python: str,
    python39: Optional[str],
    gate_output_dir: Path,
    timeout_seconds: int,
) -> Dict[str, object]:
    """Run offline gates while proving no formal publication state changed.

    Args:
        repo_root: Repository root whose active state must remain unchanged.
        current_python: Default interpreter.
        python39: Python 3.9 floor interpreter or ``None``.
        gate_output_dir: Isolated audit-artifact directory.
        timeout_seconds: Per-command timeout.

    Returns:
        Command evidence, before/after publication state, and artifact hashes.
    """
    backup = _recorded_authority_backup(repo_root=repo_root)
    before = _recorded_state_snapshot(repo_root=repo_root)
    environment = _offline_environment(guard_dir=gate_output_dir / "guard")
    sandbox_profile = _offline_sandbox_profile(
        repo_root=repo_root, protect_authority=True,
    )
    commands = []
    probe = [
        current_python,
        "-c",
        (
            "import socket\n"
            "try:\n socket.socket()\n"
            "except PermissionError as error:\n"
            " assert str(error) == 'RECORDED_SOCKET_BLOCKED'\n"
            "else:\n raise SystemExit('RECORDED_SOCKET_NOT_BLOCKED')"
        ),
    ]
    commands.append(run_command(
        argv=probe,
        repo_root=repo_root,
        environment=environment,
        timeout_seconds=timeout_seconds,
        sandbox_profile=sandbox_profile,
    ))
    secret_token = "scan-" + uuid.uuid4().hex
    for planned in recorded_commands(
        current_python=current_python,
        python39=python39,
        gate_output_dir=gate_output_dir,
    ):
        argv = planned["argv"]
        reason = str(planned["reason"])
        if reason:
            commands.append(not_run_command(argv=argv, reason=reason))
            continue
        command_environment = dict(environment)
        if "--secret-token-env" in argv:
            command_environment["VNEXT_SECRET_SCAN_TOKEN"] = secret_token
        commands.append(run_command(
            argv=argv,
            repo_root=repo_root,
            environment=command_environment,
            timeout_seconds=timeout_seconds,
            sandbox_profile=sandbox_profile,
        ))
    try:
        observed_after = _recorded_state_snapshot(repo_root=repo_root)
    except (AcceptanceError, OSError, PublicationError, ValueError) as error:
        # An unreadable post-state can itself be evidence of mutation. Restore
        # the byte backup before propagating a stable recorded failure.
        _restore_recorded_authority(repo_root=repo_root, backup=backup)
        restored = _recorded_state_snapshot(repo_root=repo_root)
        if restored != before:
            raise AcceptanceError(
                "RECORDED_AUTHORITY_RECOVERY_FAILED"
            ) from error
        raise AcceptanceError("RECORDED_AUTHORITY_OBSERVATION_FAILED") from error
    if observed_after == before:
        after = observed_after
        state_recovery = {
            "outcome": "NOT_REQUIRED",
            "restored_state_sha256": "",
        }
    else:
        _restore_recorded_authority(repo_root=repo_root, backup=backup)
        after = _recorded_state_snapshot(repo_root=repo_root)
        if after != before:
            raise AcceptanceError("RECORDED_AUTHORITY_RECOVERY_FAILED")
        state_recovery = {
            "outcome": "PASSED",
            "restored_state_sha256": content_hash(value=after),
        }
    old_resolver_commands = [
        command
        for command in commands
        if OLD_RESOLVER_FLOW_TEST in command["argv"]
    ]
    if (
        len(old_resolver_commands) != 1
        or old_resolver_commands[0]["outcome"] != "PASSED"
    ):
        old_resolver_receipt = None
    else:
        old_resolver_body = {
            "schema_version": 1,
            "scenario_id": (
                "OLD_RESOLVERS_THROW_PUBLIC_CUTOVER_TEST_FLOW"
            ),
            "evidence_tier": "TEST_ONLY_PUBLIC_FLOW",
            "human_decision_evidence": "TEST_ONLY_NOT_ACCEPTANCE",
            "command": old_resolver_commands[0],
            "active_state_unchanged": before == observed_after,
        }
        runtime_bindings, replacements = _receipt_runtime_context(
            repo_root=repo_root,
            output_dir=gate_output_dir,
            current_python=current_python,
            python39=python39,
        )
        old_resolver_body["runtime_bindings"] = runtime_bindings
        portable_old_resolver = _portable_receipt_value(
            value=old_resolver_body,
            replacements=replacements,
        )
        if not isinstance(portable_old_resolver, dict):
            raise AcceptanceError(
                "OLD_RESOLVER_RECEIPT_ROOT_INVALID"
            )
        old_resolver_id = content_hash(value=portable_old_resolver)
        old_resolver_path = gate_output_dir / (
            "old_resolver_throws_{}.json".format(
                old_resolver_id.split(":", maxsplit=1)[1]
            )
        )
        old_resolver_value = {
            **portable_old_resolver,
            "old_resolver_throws_receipt_id": old_resolver_id,
        }
        atomic_write_json(
            path=old_resolver_path, value=old_resolver_value,
        )
        old_resolver_receipt = {
            "receipt_id": old_resolver_id,
            "path": str(old_resolver_path),
            "sha256": sha256_file(path=old_resolver_path),
        }
    hashes = artifact_hashes(gate_output_dir=gate_output_dir)
    artifact_closure_complete = set(hashes) == set(
        RECORDED_GATE_ARTIFACTS
    )
    return {
        "commands": commands,
        "publication_state_before": before,
        "publication_state_after": after,
        "publication_state_observed_after": observed_after,
        "active_state_unchanged": before == observed_after,
        "state_recovery": state_recovery,
        "socket_guard_sha256": hashlib.sha256(
            OFFLINE_GUARD_SOURCE
        ).hexdigest(),
        "sandbox_profile_sha256": sha256_bytes(
            content=sandbox_profile.encode("utf-8"),
        ),
        "artifact_hashes": hashes,
        "artifact_closure_complete": artifact_closure_complete,
        "artifact_references": {
            name: {
                "path": str(gate_output_dir / name),
                "sha256": hashes[name],
            }
            for name in RECORDED_GATE_ARTIFACTS
            if name in hashes
        },
        "old_resolver_throws_receipt": old_resolver_receipt,
    }


def _commands_complete(*, commands: Sequence[Mapping[str, object]]) -> bool:
    """Return whether every command actually ran and returned zero.

    Args:
        commands: Ordered command evidence rows.

    Returns:
        True only for a non-empty all-PASSED sequence.
    """
    return bool(commands) and all(
        command["outcome"] == "PASSED" for command in commands
    )


def _json_result(
    *, parsed: Optional[Mapping[str, object]], command_name: str
) -> Optional[Dict[str, object]]:
    """Extract one successful public-CLI result envelope.

    Args:
        parsed: Parsed JSON object from a command.
        command_name: Expected operator command, or ``cutover``.

    Returns:
        Result mapping, or ``None`` when the envelope is incomplete.
    """
    if parsed is None or "ok" not in parsed or parsed["ok"] is not True:
        return None
    if command_name != "cutover":
        if "command" not in parsed or parsed["command"] != command_name:
            return None
    if "result" not in parsed or type(parsed["result"]) is not dict:
        return None
    return dict(parsed["result"])


def _terminal_cycle(
    *,
    repo_root: Path,
    current_python: str,
    timeout_seconds: int,
    guard_dir: Path,
    expected_publication_id: str,
) -> List[Dict[str, object]]:
    """Run all terminal consumers in one pinned public process.

    Args:
        repo_root: Formal publication root.
        current_python: Default interpreter.
        timeout_seconds: Per-command timeout.
        guard_dir: Isolated directory for the offline Python audit hook.
        expected_publication_id: Exact Cutover/switch result to pin.

    Returns:
        One command row binding the structured single-process gate result.
    """
    if not expected_publication_id:
        raise AcceptanceError("Terminal expected publication is required")
    if guard_dir.is_symlink() or (
        guard_dir.exists() and not guard_dir.is_dir()
    ):
        raise AcceptanceError("Terminal guard directory is unsafe")
    guard_dir.mkdir(parents=True, exist_ok=True)
    output_path = guard_dir / "terminal_cycle_result.json"
    if output_path.is_symlink() or (
        output_path.exists() and not output_path.is_file()
    ):
        raise AcceptanceError("Terminal cycle result path is unsafe")
    if output_path.exists():
        output_path.unlink()
    environment = _offline_environment(guard_dir=guard_dir)
    sandbox_profile = _offline_sandbox_profile(
        repo_root=repo_root,
        protect_authority=False,
    )
    record = run_command(
        argv=[
            current_python,
            TERMINAL_PUBLICATION_COMMAND,
            "--json",
            "--publication-root",
            ".",
            "--expected-publication-id",
            expected_publication_id,
            "--output",
            str(output_path),
        ],
        repo_root=repo_root,
        environment=environment,
        timeout_seconds=timeout_seconds,
        sandbox_profile=sandbox_profile,
    )
    if record["outcome"] != "PASSED":
        return [record]
    try:
        envelope = strict_json_file(path=output_path)
        if type(envelope) is not dict or set(envelope) != {"ok", "result"}:
            raise AcceptanceError("Terminal cycle envelope fields differ")
        if envelope["ok"] is not True or type(envelope["result"]) is not dict:
            raise AcceptanceError("Terminal cycle envelope did not pass")
        result = dict(envelope["result"])
        expected_fields = {
            "active_pointer_sha256",
            "authority_hashes_after",
            "authority_hashes_before",
            "gates",
            "publication_id",
            "schema_version",
            "side_effects",
            "source_commit",
            "source_input_tree_sha256",
            "status",
            "terminal_cycle_id",
            "validation_snapshot_sha256",
        }
        if set(result) != expected_fields:
            raise AcceptanceError("Terminal cycle result fields differ")
        if (
            result["schema_version"] != 1
            or result["status"] != "PASSED"
            or result["publication_id"] != expected_publication_id
        ):
            raise AcceptanceError("Terminal cycle authority differs")
        digest_fields = (
            "active_pointer_sha256",
            "source_input_tree_sha256",
            "validation_snapshot_sha256",
        )
        if any(
            type(result[field]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", result[field]) is None
            for field in digest_fields
        ):
            raise AcceptanceError("Terminal cycle digest is invalid")
        gates = result["gates"]
        if (
            type(gates) is not list
            or tuple(
                gate["gate_id"]
                for gate in gates
                if type(gate) is dict and "gate_id" in gate
            ) != TERMINAL_GATE_IDS
            or any(
                type(gate) is not dict
                or set(gate) != {"gate_id", "outcome", "details"}
                or gate["outcome"] != "PASSED"
                or type(gate["details"]) is not dict
                for gate in gates
            )
        ):
            raise AcceptanceError("Terminal cycle gate exact set differs")
        if (
            type(result["authority_hashes_before"]) is not dict
            or result["authority_hashes_before"]
            != result["authority_hashes_after"]
        ):
            raise AcceptanceError("Terminal cycle authority bytes changed")
        expected_side_effects = {
            "ai_socket_count": 0,
            "sec_socket_count": 0,
            "repair_count": 0,
            "report_authoritative_write_count": 0,
        }
        if result["side_effects"] != expected_side_effects:
            raise AcceptanceError("Terminal cycle side effects differ")
        declared_id = result["terminal_cycle_id"]
        body = dict(result)
        del body["terminal_cycle_id"]
        if declared_id != content_hash(value=body):
            raise AcceptanceError("Terminal cycle identity differs")
    except (
        AcceptanceError,
        CanonicalError,
        FileNotFoundError,
        OSError,
        ValueError,
    ) as error:
        record["outcome"] = "FAILED"
        record["return_code"] = 1
        record["reason"] = "TERMINAL_STRUCTURED_RESULT_INVALID"
        record["error_class"] = type(error).__name__
        return [record]
    record["terminal_cycle_result"] = result
    record["terminal_cycle_result_sha256"] = sha256_file(path=output_path)
    return [record]


def _switch_argv(
    *,
    current_python: str,
    mode: str,
    target_publication_id: str,
    expected_active_publication_id: str,
) -> List[str]:
    """Build one exact rollback/restore public operator command.

    Args:
        current_python: Default interpreter.
        mode: ``rollback`` or ``restore``.
        target_publication_id: Verified bundle to reactivate.
        expected_active_publication_id: Exact CAS predecessor.

    Returns:
        Argument vector with an explicit UTC commit time.
    """
    if mode not in {"rollback", "restore"}:
        raise AcceptanceError("Publication switch mode is invalid")
    return [
        current_python,
        PUBLICATION_OPERATOR_COMMAND,
        "--json",
        mode,
        "--publication-root",
        ".",
        "--target-publication-id",
        target_publication_id,
        "--expected-active-publication-id",
        expected_active_publication_id,
        "--committed-at-utc",
        utc_now(),
    ]


def _write_phase_receipt(
    *,
    output_dir: Path,
    phase: str,
    before: Mapping[str, object],
    after: Mapping[str, object],
    command: Mapping[str, object],
) -> Dict[str, str]:
    """Persist one content-addressed rollback or restore observation.

    Args:
        output_dir: Acceptance evidence root.
        phase: ``ROLLBACK`` or ``RESTORE``.
        before: Official state before the pointer switch.
        after: Official state after the pointer switch.
        command: Exact digest-only command record.

    Returns:
        Receipt identity, path, and exact file digest.
    """
    body = {
        "schema_version": 1,
        "phase": phase,
        "observed_at_utc": utc_now(),
        "active_before": before["active_publication_id"],
        "active_after": after["active_publication_id"],
        "mirror_hashes_before": before["mirror_hashes"],
        "mirror_hashes_after": after["mirror_hashes"],
        "command": dict(command),
        "outcome": "PASSED",
    }
    receipt_id = content_hash(value=body)
    path = output_dir / "publication_switch_receipts" / (
        receipt_id.split(":", maxsplit=1)[1] + ".json"
    )
    receipt = dict(body)
    receipt["receipt_id"] = receipt_id
    atomic_write_json(path=path, value=receipt)
    return {
        "active_after": str(after["active_publication_id"]),
        "active_before": str(before["active_publication_id"]),
        "receipt_id": receipt_id,
        "path": str(path),
        "sha256": sha256_file(path=path),
    }


def _validated_publication_switch(
    *,
    repo_root: Path,
    current_python: str,
    timeout_seconds: int,
    output_dir: Path,
    mode: str,
    phase: str,
    target_publication_id: str,
    expected_active_publication_id: str,
    before: Mapping[str, object],
    expected_target_state: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    """Run one public switch and require exact PublicationView read-back.

    Args:
        repo_root: Formal publication and compatibility-mirror root.
        current_python: Interpreter for the supported operator CLI.
        timeout_seconds: Public command timeout.
        output_dir: Durable acceptance receipt root.
        mode: ``rollback`` or ``restore``.
        phase: Audit phase written into the switch receipt.
        target_publication_id: Exact target bundle identity.
        expected_active_publication_id: CAS identity before the switch.
        before: Verified official state before the switch.
        expected_target_state: Previously verified target state, or ``None``
            when first Cutover imported A and no A state existed beforehand.

    Returns:
        Command evidence, validated state, receipt, and stable outcome fields.

    Why:
        A successful CLI envelope alone cannot prove that the pointer, bundle,
        and every root mirror are the same publication.  The first imported A
        is therefore trusted only after its own PublicationView validation,
        never by comparing it with incomplete pre-import root metadata.
    """
    argv = _switch_argv(
        current_python=current_python,
        mode=mode,
        target_publication_id=target_publication_id,
        expected_active_publication_id=expected_active_publication_id,
    )
    record, envelope = run_json_command(
        argv=argv,
        repo_root=repo_root,
        environment={
            "OPENAI_API_KEY": None,
            "PYTHONDONTWRITEBYTECODE": "1",
            "SEC_CONTACT_EMAIL": None,
        },
        timeout_seconds=timeout_seconds,
        sandbox_profile=NETWORK_DENY_SANDBOX_PROFILE,
    )
    result = _json_result(parsed=envelope, command_name=mode)
    if (
        record["outcome"] != "PASSED"
        or result is None
        or "publication_id" not in result
        or result["publication_id"] != target_publication_id
        or "previous_publication_id" not in result
        or result["previous_publication_id"]
        != expected_active_publication_id
    ):
        return {
            "command": record,
            "error_code": "PUBLICATION_SWITCH_FAILED",
            "message": "Public switch result differs from requested CAS",
            "ok": False,
            "receipt": None,
            "state": None,
        }
    try:
        observation = _validated_publication_state(
            repo_root=repo_root,
            expected_publication_id=target_publication_id,
        )
    except AcceptanceError as error:
        return {
            "command": record,
            "error_code": "PUBLICATION_SWITCH_READBACK_FAILED",
            "message": str(error),
            "ok": False,
            "receipt": None,
            "state": None,
        }
    state = observation["state"]
    if (
        expected_target_state is not None
        and state["mirror_hashes"]
        != expected_target_state["mirror_hashes"]
    ):
        return {
            "command": record,
            "error_code": "PUBLICATION_SWITCH_MIRRORS_DIFFER",
            "message": "Validated target mirror bytes differ",
            "ok": False,
            "receipt": None,
            "state": state,
        }
    receipt = _write_phase_receipt(
        output_dir=output_dir,
        phase=phase,
        before=before,
        after=state,
        command=record,
    )
    return {
        "command": record,
        "error_code": "",
        "message": "",
        "ok": True,
        "receipt": receipt,
        "state": state,
    }


def _bind_addressed_receipt(
    *, repo_root: Path, path_value: object, expected_id: object,
    identity_field: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Verify one repository-owned content-addressed JSON receipt.

    Args:
        repo_root: Fixed formal repository authority.
        path_value: Absolute or repository-relative receipt locator.
        expected_id: Identity declared by the public Cutover result.
        identity_field: Receipt field excluded from its canonical body hash.

    Returns:
        Portable byte binding and the verified strict receipt mapping.
    """
    path = Path(str(path_value))
    if not path.is_absolute():
        path = repo_root / path
    try:
        relative = path.resolve(strict=True).relative_to(
            repo_root.resolve(strict=True)
        ).as_posix()
        payload = strict_json_file(path=path)
    except (CanonicalError, FileNotFoundError, OSError, ValueError) as error:
        raise AcceptanceError(
            "Content-addressed receipt escaped or is unavailable"
        ) from error
    if (
        not isinstance(payload, dict)
        or identity_field not in payload
        or payload[identity_field] != expected_id
    ):
        raise AcceptanceError("Content-addressed receipt identity is invalid")
    body = {
        field: payload[field]
        for field in payload
        if field != identity_field
    }
    if payload[identity_field] != content_hash(value=body):
        raise AcceptanceError("Content-addressed receipt bytes differ")
    return (
        {
            "receipt_id": payload[identity_field],
            "repo_relative_path": relative,
            "sha256": sha256_file(path=path),
        },
        dict(payload),
    )


def _validated_sec_acquisition_binding(
    *, repo_root: Path, receipt_id: object, receipt_path: object,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Rebind the producer receipt through the one strict live validator.

    Args:
        repo_root: Fixed formal repository and current SEC audit authority.
        receipt_id: Exact content identity declared by the workflow result.
        receipt_path: Fixed Cutover-owned receipt locator.

    Returns:
        Portable receipt-byte binding and mechanically rebuilt payload.

    Raises:
        AcceptanceError: When identities differ or current runtime, command,
        ledger, attempt, or inventory closure cannot validate the receipt.
    """
    binding, receipt = _bind_addressed_receipt(
        repo_root=repo_root,
        path_value=receipt_path,
        expected_id=receipt_id,
        identity_field="receipt_id",
    )
    expected_relative = (
        "artifacts/vnext/cutover/receipts/sec_acquisition_{}.json".format(
            str(receipt_id).split(":", maxsplit=1)[1]
        )
    )
    if binding["repo_relative_path"] != expected_relative:
        raise AcceptanceError("SEC acquisition receipt path differs")
    try:
        validated = _validate_live_sec_acquisition_receipt(
            repo_root=repo_root, receipt=receipt,
        )
    except CutoverError as error:
        raise AcceptanceError("SEC acquisition receipt is invalid") from error
    if validated != receipt:
        raise AcceptanceError("SEC acquisition receipt replay differs")
    return binding, validated


def _repository_path(
    *, repo_root: Path, path_value: object, kind: str
) -> Tuple[Path, str]:
    """Resolve one real repository descendant without accepting symlinks.

    Args:
        repo_root: Fixed formal repository authority.
        path_value: Absolute or repository-relative locator.
        kind: ``file`` or ``directory``.

    Returns:
        Resolved path and portable repository-relative locator.

    Why:
        Final evidence must not be redirected to an attacker-controlled path
        after a caller supplies a syntactically plausible locator.
    """
    if kind not in {"file", "directory"}:
        raise AcceptanceError("Repository path kind is invalid")
    root = repo_root.resolve(strict=True)
    value = Path(str(path_value))
    candidate = value if value.is_absolute() else root / value
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        raise AcceptanceError(
            "Formal evidence path escaped or is unavailable"
        ) from error
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise AcceptanceError("Formal evidence path contains a symlink")
    valid = resolved.is_file() if kind == "file" else resolved.is_dir()
    if not valid:
        raise AcceptanceError("Formal evidence path kind differs")
    return resolved, relative.as_posix()


def _validated_live_attempt_audit(
    *, repo_root: Path, closure_path_value: object,
    expected_closure_id: object, stability_receipt_id: object,
    stability_receipt_sha256: str,
    attempts: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Replay and bind the portable all-attempt live Reader closure.

    Args:
        repo_root: Fixed repository and Run replay authority.
        closure_path_value: Repository-owned content-addressed directory.
        expected_closure_id: Identity declared by Cutover and its receipt.
        stability_receipt_id: Final strict-compatibility stability identity.
        stability_receipt_sha256: Hash of the original addressed receipt.
        attempts: Every failed retry and three successful attempt summaries.

    Returns:
        Portable closure, manifest, and copied receipt byte identities.
    """
    if (
        type(expected_closure_id) is not str
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}", expected_closure_id,
        ) is None
    ):
        raise AcceptanceError("Live attempt audit identity is invalid")
    closure_dir, closure_relative = _repository_path(
        repo_root=repo_root,
        path_value=closure_path_value,
        kind="directory",
    )
    try:
        manifest = _verify_live_attempt_audit_closure(
            closure_dir=closure_dir,
            repo_root=repo_root,
        )
    except (CutoverError, OSError, RunStoreError, ValueError) as error:
        raise AcceptanceError(
            "Portable live attempt audit replay failed"
        ) from error
    required = {
        "schema_version",
        "closure_type",
        "stability_receipt_id",
        "attempt_ids",
        "run_bindings",
        "files",
        "audit_closure_id",
    }
    attempt_ids = [str(attempt["attempt_id"]) for attempt in attempts]
    run_ids = [str(attempt["run_id"]) for attempt in attempts]
    run_bindings = manifest["run_bindings"]
    if (
        set(manifest) != required
        or manifest["schema_version"] != 1
        or manifest["closure_type"] != "LIVE_READER_ATTEMPT_AUDIT"
        or manifest["audit_closure_id"] != expected_closure_id
        or manifest["stability_receipt_id"] != stability_receipt_id
        or manifest["attempt_ids"] != attempt_ids
        or type(run_bindings) is not list
        or any(
            type(binding) is not dict
            or set(binding) != {
                "audit_manifest_hash",
                "content_manifest_hash",
                "path",
                "run_id",
                "status",
            }
            for binding in run_bindings
        )
        or type(manifest["files"]) is not list
        or any(
            type(record) is not dict
            or set(record) != {"path", "sha256", "size"}
            for record in manifest["files"]
        )
        or sorted(str(binding["run_id"]) for binding in run_bindings)
        != sorted(run_ids)
    ):
        raise AcceptanceError("Portable live attempt audit binding differs")
    manifest_path = closure_dir / "audit_manifest.json"
    copied_stability_path = (
        closure_dir / "receipts" / "live_reader_stability.json"
    )
    if sha256_file(path=copied_stability_path) != stability_receipt_sha256:
        raise AcceptanceError(
            "Portable live stability receipt bytes differ"
        )
    return {
        "audit_closure_id": expected_closure_id,
        "repo_relative_path": closure_relative,
        "manifest_sha256": sha256_file(path=manifest_path),
        "stability_receipt_sha256": sha256_file(
            path=copied_stability_path,
        ),
        "attempt_ids": attempt_ids,
        "run_ids": sorted(run_ids),
    }


def _validated_publication_state(
    *, repo_root: Path, expected_publication_id: str
) -> Dict[str, object]:
    """Open and validate one active PublicationView and all root mirrors.

    Args:
        repo_root: Formal publication and compatibility-mirror root.
        expected_publication_id: Exact publication that must still be active.

    Returns:
        Fresh pointer, bundle, Batch, validation, and mirror observation.

    Why:
        A pointer ID or caller-supplied mirror digest alone does not prove that
        the bundle can be reopened or that every compatibility mirror is exact.
    """
    try:
        view = PublicationView.open(publication_root=repo_root)
        validated = validate_active_publication(
            publication_view=view,
            publication_root=repo_root,
        )
        state = publication_state_snapshot(publication_root=repo_root)
    except (OSError, PublicationError, ValueError) as error:
        raise AcceptanceError(
            "Active PublicationView read-back failed"
        ) from error
    if (
        view.publication_id != expected_publication_id
        or validated["publication_id"] != expected_publication_id
        or state["active_publication_id"] != expected_publication_id
        or validated["mirror_hashes"] != state["mirror_hashes"]
    ):
        raise AcceptanceError("Active PublicationView identity differs")
    pointer_path, _pointer_relative = _repository_path(
        repo_root=repo_root,
        path_value=ACTIVE_POINTER_PATH,
        kind="file",
    )
    manifest_path, _manifest_relative = _repository_path(
        repo_root=repo_root,
        path_value=view.bundle_dir / "publication_manifest.json",
        kind="file",
    )
    return {
        "state": state,
        "publication_id": view.publication_id,
        "previous_publication_id": view.manifest[
            "previous_publication_id"
        ],
        "batch_manifest_id": view.manifest["batch_manifest_id"],
        "validation_receipt_id": view.manifest[
            "validation_receipt_id"
        ],
        "requirement_hashes": view.manifest["requirement_hashes"],
        "active_pointer_sha256": sha256_file(path=pointer_path),
        "bundle_manifest_sha256": sha256_file(path=manifest_path),
        "root_mirror_hashes": validated["mirror_hashes"],
    }


def _validated_run_summary(
    *, repo_root: Path, run_dir_value: object,
    attempt: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    """Reload one terminal Run and optionally bind its AI attempt graph.

    Args:
        repo_root: Repository authority used for FROZEN replay.
        run_dir_value: Repository-owned Run directory locator.
        attempt: Cutover attempt summary, or ``None`` for a Batch Run.

    Returns:
        Portable Run identity and immutable manifest hashes.
    """
    run_dir, relative = _repository_path(
        repo_root=repo_root, path_value=run_dir_value, kind="directory",
    )
    try:
        manifest, records, decisions = load_run_for_status(
            run_dir=run_dir, repo_root=repo_root,
        )
    except (OSError, RunStoreError, ValueError) as error:
        raise AcceptanceError("Formal Run replay failed") from error
    if attempt is not None:
        if (
            manifest["run_id"] != attempt["run_id"]
            or manifest["status"] != attempt["status"]
        ):
            raise AcceptanceError("Live attempt Run identity differs")
        ai_attempts = [
            record for record in records
            if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
        ]
        if len(ai_attempts) != 1:
            raise AcceptanceError("Live attempt Run graph is ambiguous")
        persisted = ai_attempts[0]
        direct_fields = (
            "assistant_output_sha256",
            "attempt_id",
            "model_requested",
            "model_returned",
            "provider_request_id",
            "raw_response_sha256",
            "request_body_sha256",
        )
        if any(
            persisted[field] != attempt[field] for field in direct_fields
        ) or content_hash(
            value=persisted["transport_observation"]
        ) != attempt["transport_observation_hash"]:
            raise AcceptanceError("Live attempt persisted audit differs")
        if persisted["error_class"]:
            if persisted["error_class"] != attempt["error_class"]:
                raise AcceptanceError("Live attempt error class differs")
        elif (
            attempt["error_class"]
            and (
                "failure_status" not in attempt
                or attempt["error_class"] != attempt["failure_status"]
            )
        ):
            raise AcceptanceError("Live attempt failure class differs")
        if (
            attempt["run_content_manifest_hash"]
            != manifest["content_manifest_hash"]
            or attempt["run_audit_manifest_hash"]
            != manifest["audit_manifest_hash"]
            or (
                "decision_count" in attempt
                and attempt["decision_count"] != len(decisions)
            )
        ):
            raise AcceptanceError("Live attempt Run closure differs")
        optional_records = {
            "candidate_hash": "OBSERVATION_CANDIDATE",
            "evidence_check_id": "EVIDENCE_CHECK",
        }
        for field, record_type in optional_records.items():
            matches = [
                record for record in records
                if record["record_type"] == record_type
            ]
            if field in attempt:
                if len(matches) != 1 or matches[0][field] != attempt[field]:
                    raise AcceptanceError("Live attempt graph differs")
            elif matches:
                raise AcceptanceError("Live attempt graph binding is absent")
        if attempt["status"] == "FROZEN":
            units = [
                record for record in records
                if record["record_type"] == "REVIEW_UNIT"
            ]
            if (
                len(units) != 1
                or units[0]["review_unit_hash"]
                != attempt["review_unit_hash"]
            ):
                raise AcceptanceError("Successful ReviewUnit graph differs")
            unit = units[0]
            if (
                unit["review_context_hash"]
                != attempt["review_context_hash"]
                or unit["rendered_review_hash"]
                != attempt["rendered_review_hash"]
            ):
                raise AcceptanceError("Live ReviewUnit context differs")
    manifest_path = run_dir / "manifest.json"
    if (
        "content_manifest_hash" not in manifest
        or "audit_manifest_hash" not in manifest
    ):
        raise AcceptanceError("Terminal Run manifest hashes are absent")
    return {
        "run_id": manifest["run_id"],
        "status": manifest["status"],
        "repo_relative_path": relative,
        "content_manifest_hash": manifest["content_manifest_hash"],
        "audit_manifest_hash": manifest["audit_manifest_hash"],
        "manifest_sha256": sha256_file(path=manifest_path),
    }


def _validated_run_closure(
    *, repo_root: Path, batch_path: Path,
    cutover_result: Mapping[str, object],
    attempts: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Rebuild the external Batch and every referenced terminal Run.

    Args:
        repo_root: Repository authority for semantic replay.
        batch_path: Persisted formal BatchManifest.
        cutover_result: Public Cutover result naming Batch Runs.
        attempts: Every live attempt including failures and successes.

    Returns:
        Rebuilt Batch plus stable Run and attempt bindings.
    """
    try:
        batch = load_projection_batch_manifest(
            repo_root=repo_root, batch_manifest_path=batch_path,
        )
    except (OSError, ProjectionError, ValueError) as error:
        raise AcceptanceError("Formal Batch/Run replay failed") from error
    if batch["batch_manifest_id"] != cutover_result["batch_manifest_id"]:
        raise AcceptanceError("Formal Batch identity differs")
    declared_values = cutover_result["run_dirs"]
    if type(declared_values) is not list:
        raise AcceptanceError("Cutover Run locator list is invalid")
    expected_dirs = [
        (batch_path.parent / str(binding["run_path"])).resolve()
        for binding in batch["runs"]
    ]
    declared_dirs = []
    for value in declared_values:
        run_dir, _relative = _repository_path(
            repo_root=repo_root, path_value=value, kind="directory",
        )
        declared_dirs.append(run_dir)
    if (
        len(declared_dirs) != len(set(declared_dirs))
        or set(declared_dirs) != set(expected_dirs)
    ):
        raise AcceptanceError("Cutover Batch Run exact set differs")
    batch_runs = [
        _validated_run_summary(
            repo_root=repo_root, run_dir_value=run_dir, attempt=None,
        )
        for run_dir in sorted(declared_dirs)
    ]
    batch_run_ids = {str(binding["run_id"]) for binding in batch["runs"]}
    if (
        {str(binding["run_id"]) for binding in batch_runs}
        != batch_run_ids
        or any(binding["status"] != "FROZEN" for binding in batch_runs)
    ):
        raise AcceptanceError("Cutover Batch Run binding differs")
    attempt_runs = [
        _validated_run_summary(
            repo_root=repo_root,
            run_dir_value=attempt["run_dir"],
            attempt=attempt,
        )
        for attempt in attempts
    ]
    if len({binding["run_id"] for binding in attempt_runs}) != len(
        attempt_runs
    ):
        raise AcceptanceError("Live attempt Run identity is duplicated")
    return {
        "batch": batch,
        "batch_sha256": sha256_file(path=batch_path),
        "batch_runs": batch_runs,
        "attempt_runs": attempt_runs,
    }


def _validated_fault_matrix(
    *, repo_root: Path, cutover_receipt_path: Path,
    cutover_result: Mapping[str, object],
    fault_receipt_ids: Sequence[str],
) -> Dict[str, object]:
    """Resume the retained formal matrix and require its exact 14 scenarios.

    Args:
        repo_root: Formal receipt root.
        cutover_receipt_path: Verified receipt locating the Cutover workspace.
        cutover_result: Public result naming predecessor and successor.
        fault_receipt_ids: IDs bound by the formal Cutover receipt.

    Returns:
        Matrix identity, manifest digest, and exact receipt bindings.
    """
    workspace = cutover_receipt_path.parent.parent
    try:
        matrix = resume_formal_publication_fault_matrix(
            receipt_publication_root=repo_root,
            source_publication_root=workspace / "fault_matrix_source",
            fault_workspace_root=workspace / "publication_fault_matrix",
        )
    except (FaultMatrixError, OSError, PublicationError) as error:
        raise AcceptanceError("Formal fault matrix replay failed") from error
    references = matrix["fault_receipt_references"]
    scenario_ids = [str(row["scenario_id"]) for row in references]
    observed_ids = [str(row["fault_receipt_id"]) for row in references]
    if (
        len(references) != len(FAULT_MATRIX_SCENARIO_IDS)
        or set(scenario_ids) != FAULT_MATRIX_SCENARIO_IDS
        or len(set(observed_ids)) != len(FAULT_MATRIX_SCENARIO_IDS)
        or observed_ids != list(fault_receipt_ids)
        or matrix["fault_matrix_id"] != cutover_result["fault_matrix_id"]
        or matrix["predecessor_publication_id"]
        != cutover_result["previous_publication_id"]
        or matrix["successor_publication_id"]
        != cutover_result["publication_id"]
    ):
        raise AcceptanceError("Formal fault matrix exact set differs")
    bindings = []
    for reference in references:
        binding, payload = _bind_addressed_receipt(
            repo_root=repo_root,
            path_value=reference["fault_receipt_path"],
            expected_id=reference["fault_receipt_id"],
            identity_field="fault_receipt_id",
        )
        if (
            payload["scenario_id"] != reference["scenario_id"]
            or payload["temporary_workspace_cleaned"] is not True
        ):
            raise AcceptanceError("Formal fault receipt semantics differ")
        bindings.append({**binding, "scenario_id": payload["scenario_id"]})
    manifest_path, manifest_relative = _repository_path(
        repo_root=repo_root,
        path_value=workspace / "publication_fault_matrix"
        / "fault_matrix_manifest.json",
        kind="file",
    )
    return {
        "fault_matrix_id": matrix["fault_matrix_id"],
        "scenario_ids": scenario_ids,
        "workspace_manifest_path": manifest_relative,
        "workspace_manifest_sha256": sha256_file(path=manifest_path),
        "receipts": bindings,
    }


def _validated_recorded_gate_artifacts(
    *, repo_root: Path, recorded_evidence: Mapping[str, object],
) -> Dict[str, Dict[str, str]]:
    """Reopen the exact semantic/scalability outputs used by recorded gates.

    Args:
        repo_root: Formal repository authority.
        recorded_evidence: Recorded runner result embedded into full acceptance.

    Returns:
        Artifact name to portable path and exact SHA-256 binding.
    """
    if (
        "artifact_closure_complete" not in recorded_evidence
        or recorded_evidence["artifact_closure_complete"] is not True
        or "artifact_hashes" not in recorded_evidence
        or type(recorded_evidence["artifact_hashes"]) is not dict
        or set(recorded_evidence["artifact_hashes"])
        != set(RECORDED_GATE_ARTIFACTS)
        or "artifact_references" not in recorded_evidence
        or type(recorded_evidence["artifact_references"]) is not dict
        or set(recorded_evidence["artifact_references"])
        != set(RECORDED_GATE_ARTIFACTS)
    ):
        raise AcceptanceError("Recorded gate artifact closure is incomplete")
    bindings: Dict[str, Dict[str, str]] = {}
    for name in RECORDED_GATE_ARTIFACTS:
        reference = recorded_evidence["artifact_references"][name]
        if (
            type(reference) is not dict
            or set(reference) != {"path", "sha256"}
            or reference["sha256"]
            != recorded_evidence["artifact_hashes"][name]
        ):
            raise AcceptanceError("Recorded gate artifact reference differs")
        path, relative = _repository_path(
            repo_root=repo_root,
            path_value=reference["path"],
            kind="file",
        )
        digest = sha256_file(path=path)
        if digest != reference["sha256"]:
            raise AcceptanceError("Recorded gate artifact bytes differ")
        bindings[name] = {
            "repo_relative_path": relative,
            "sha256": digest,
        }
    return bindings


def formal_evidence_binding(
    *,
    repo_root: Path,
    cutover_result: Mapping[str, object],
    final_state: Mapping[str, object],
    recorded_evidence: Mapping[str, object],
) -> Dict[str, object]:
    """Bind source, Requirement, Run, Batch, pointer, and final snapshot bytes.

    Args:
        repo_root: Clean formal repository.
        cutover_result: Successful public Cutover result.
        final_state: Official state after restore and terminal validation.
        recorded_evidence: Socket-blocked gates including old-path proof.

    Returns:
        Final full receipt binding without copying secret-bearing payloads.
    """
    source = capture_source_snapshot(workdir=repo_root)
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/ai_first_v3_3_1"
    )
    recorded_gate_artifacts = _validated_recorded_gate_artifacts(
        repo_root=repo_root, recorded_evidence=recorded_evidence,
    )
    required = {
        "acceptance_evidence",
        "batch_manifest_id",
        "batch_manifest_path",
        "cutover_qualification",
        "cutover_receipt_path",
        "fault_matrix_id",
        "live_attempt_audit_closure_id",
        "live_attempt_audit_closure_path",
        "live_attempts",
        "live_stability_receipt_id",
        "live_stability_receipt_path",
        "invocation_sec_acquisition_receipt_id",
        "invocation_sec_acquisition_receipt_path",
        "publication_id",
        "previous_publication_id",
        "release_input_plan_id",
        "run_dirs",
        "sec_acquisition_receipt_id",
        "sec_acquisition_receipt_path",
        "staging_parity_receipt_path",
        "validation_receipt_id",
    }
    if not required.issubset(cutover_result):
        raise AcceptanceError("Cutover result evidence fields are incomplete")
    if (
        "effective_decisions" not in requirement
        or "D-01" not in requirement["effective_decisions"]
    ):
        raise AcceptanceError("Effective D-01 decision is unavailable")
    d01 = requirement["effective_decisions"]["D-01"]
    attempts = cutover_result["live_attempts"]
    if type(attempts) is not list or not attempts:
        raise AcceptanceError("Live Reader attempt audit is absent")
    common_attempt_fields = (
        "assistant_output_sha256",
        "attempt_id",
        "error_class",
        "model_requested",
        "model_returned",
        "provider_request_id",
        "request_body_sha256",
        "raw_response_sha256",
        "run_audit_manifest_hash",
        "run_content_manifest_hash",
        "run_dir",
        "run_id",
        "status",
        "transport_observation_hash",
    )
    successful_attempt_fields = (
        "candidate_hash",
        "evidence_check_id",
        "rendered_review_hash",
        "review_context_hash",
        "review_unit_hash",
    )
    attempt_bindings = []
    successful = []
    for attempt in attempts:
        if type(attempt) is not dict or any(
            field not in attempt for field in common_attempt_fields
        ):
            raise AcceptanceError("Live attempt binding is incomplete")
        if attempt["status"] == "FROZEN":
            if any(
                field not in attempt for field in successful_attempt_fields
            ):
                raise AcceptanceError(
                    "Successful live attempt binding is incomplete"
                )
            successful.append(attempt)
        elif attempt["status"] != "FAILED":
            raise AcceptanceError("Live attempt terminal state is invalid")
        attempt_bindings.append({
            field: attempt[field]
            for field in (
                *common_attempt_fields,
                *successful_attempt_fields,
            )
            if field in attempt and field != "run_dir"
        })
    successful_ids = [str(attempt["attempt_id"]) for attempt in successful]
    substantive_fields = (
        "candidate_hash",
        "evidence_check_id",
        "model_requested",
        "model_returned",
        "rendered_review_hash",
        "request_body_sha256",
        "review_context_hash",
        "review_unit_hash",
    )
    if (
        len(successful) != 3
        or len(set(successful_ids)) != 3
        or len({str(attempt["run_id"]) for attempt in successful}) != 3
        or any(
            tuple(attempt[field] for field in substantive_fields)
            != tuple(successful[0][field] for field in substantive_fields)
            for attempt in successful[1:]
        )
        or any(
            attempt["model_requested"] != d01["choice"]["model"]
            or attempt["model_returned"] != d01["choice"]["model"]
            for attempt in successful
        )
    ):
        raise AcceptanceError(
            "Exactly three stable successful live attempts are required"
        )

    required_evidence = {
        "cutover_receipt_id",
        "fault_injection_receipt_ids",
        "holdout_receipt_id",
        "legacy_invariant_migration_receipt_id",
        "live_attempt_audit_closure_id",
        "production_freeze_receipt_id",
        "second_layout_receipt_id",
        "sec_acquisition_receipt_id",
        "staging_parity_receipt_id",
    }
    declared_evidence = cutover_result["acceptance_evidence"]
    if (
        type(declared_evidence) is not dict
        or set(declared_evidence) != required_evidence
        or any(
            type(value) is not str or not value
            for key, value in declared_evidence.items()
            if key != "fault_injection_receipt_ids"
        )
        or type(declared_evidence["fault_injection_receipt_ids"]) is not list
        or len(declared_evidence["fault_injection_receipt_ids"])
        != len(FAULT_MATRIX_SCENARIO_IDS)
        or len(set(declared_evidence["fault_injection_receipt_ids"]))
        != len(FAULT_MATRIX_SCENARIO_IDS)
    ):
        raise AcceptanceError("Cutover acceptance evidence is incomplete")

    publication_id = str(cutover_result["publication_id"])
    initial_publication = _validated_publication_state(
        repo_root=repo_root, expected_publication_id=publication_id,
    )
    if (
        initial_publication["state"] != final_state
        or initial_publication["previous_publication_id"]
        != cutover_result["previous_publication_id"]
        or initial_publication["batch_manifest_id"]
        != cutover_result["batch_manifest_id"]
        or initial_publication["validation_receipt_id"]
        != cutover_result["validation_receipt_id"]
        or initial_publication["requirement_hashes"] != requirement["hashes"]
    ):
        raise AcceptanceError("Final PublicationView binding differs")

    if (
        cutover_result["sec_acquisition_receipt_id"]
        != declared_evidence["sec_acquisition_receipt_id"]
    ):
        raise AcceptanceError("SEC acquisition receipt identity differs")
    acquisition_binding, acquisition = _validated_sec_acquisition_binding(
        repo_root=repo_root,
        receipt_id=declared_evidence["sec_acquisition_receipt_id"],
        receipt_path=cutover_result["sec_acquisition_receipt_path"],
    )
    invocation_acquisition_binding, invocation_acquisition = (
        _validated_sec_acquisition_binding(
            repo_root=repo_root,
            receipt_id=cutover_result[
                "invocation_sec_acquisition_receipt_id"
            ],
            receipt_path=cutover_result[
                "invocation_sec_acquisition_receipt_path"
            ],
        )
    )
    staging_binding, staging = _bind_addressed_receipt(
        repo_root=repo_root,
        path_value=cutover_result["staging_parity_receipt_path"],
        expected_id=declared_evidence["staging_parity_receipt_id"],
        identity_field="receipt_id",
    )
    staging_fields = {
        "batch_manifest_id",
        "candidate_artifact_hashes",
        "candidate_summary",
        "evidence_reconciliations_hash",
        "legacy_invariant_migration_receipt_id",
        "legacy_invariant_migration_sha256",
        "legacy_migration_entries_hash",
        "metric_cell_comparisons_hash",
        "publication_validation_receipt_id",
        "receipt_id",
        "receipt_type",
        "schema_version",
        "status",
    }
    if (
        set(staging) != staging_fields
        or staging["receipt_type"] != "TEN_COMPANY_STAGING_PARITY"
        or staging["status"] != "PASS"
        or staging["batch_manifest_id"] != cutover_result["batch_manifest_id"]
        or staging["publication_validation_receipt_id"]
        != cutover_result["validation_receipt_id"]
        or staging["legacy_invariant_migration_receipt_id"]
        != declared_evidence["legacy_invariant_migration_receipt_id"]
    ):
        raise AcceptanceError("Formal staging parity receipt is invalid")
    cutover_binding, cutover = _bind_addressed_receipt(
        repo_root=repo_root,
        path_value=cutover_result["cutover_receipt_path"],
        expected_id=declared_evidence["cutover_receipt_id"],
        identity_field="receipt_id",
    )
    for field in required_evidence - {"cutover_receipt_id"}:
        if field not in cutover or cutover[field] != declared_evidence[field]:
            raise AcceptanceError(
                "Formal Cutover receipt evidence binding differs"
            )
    required_cutover_fields = {
        "batch_manifest_id",
        "fault_matrix_id",
        "live_stability_receipt_id",
        "previous_publication_id",
        "publication_id",
        "publication_validation_receipt_id",
        "receipt_type",
        "status",
    }
    if (
        not required_cutover_fields.issubset(cutover)
        or cutover["receipt_type"] != "FORMAL_VNEXT_CUTOVER"
        or cutover["status"] != "PASSED"
        or cutover["batch_manifest_id"]
        != cutover_result["batch_manifest_id"]
        or cutover["publication_id"] != publication_id
        or cutover["previous_publication_id"]
        != cutover_result["previous_publication_id"]
        or cutover["publication_validation_receipt_id"]
        != cutover_result["validation_receipt_id"]
        or cutover["fault_matrix_id"]
        != cutover_result["fault_matrix_id"]
        or cutover["live_stability_receipt_id"]
        != cutover_result["live_stability_receipt_id"]
    ):
        raise AcceptanceError("Formal Cutover receipt is invalid")
    stability_binding, stability = _bind_addressed_receipt(
        repo_root=repo_root,
        path_value=cutover_result["live_stability_receipt_path"],
        expected_id=cutover_result["live_stability_receipt_id"],
        identity_field="stability_receipt_id",
    )
    required_stability_fields = {
        "attempts",
        "cutover_qualification",
        "receipt_type",
        "release_input_plan_id",
        "stability_target",
        "status",
        "successful_attempt_ids",
    }
    if (
        not required_stability_fields.issubset(stability)
        or stability["receipt_type"] != "LIVE_READER_STABILITY"
        or stability["status"] != "PASSED"
        or stability["stability_target"] != 3
        or stability["release_input_plan_id"]
        != cutover_result["release_input_plan_id"]
        or stability["successful_attempt_ids"] != successful_ids
        or stability["cutover_qualification"]
        != cutover_result["cutover_qualification"]
        or type(stability["attempts"]) is not list
        or len(stability["attempts"]) != len(attempts)
        or any(
            any(
                key not in attempt or attempt[key] != value
                for key, value in receipt_attempt.items()
                if key != "stability_receipt_id"
            )
            for receipt_attempt, attempt in zip(
                stability["attempts"], attempts
            )
        )
    ):
        raise AcceptanceError("Live stability receipt binding differs")
    live_attempt_audit = _validated_live_attempt_audit(
        repo_root=repo_root,
        closure_path_value=cutover_result[
            "live_attempt_audit_closure_path"
        ],
        expected_closure_id=declared_evidence[
            "live_attempt_audit_closure_id"
        ],
        stability_receipt_id=cutover_result[
            "live_stability_receipt_id"
        ],
        stability_receipt_sha256=str(stability_binding["sha256"]),
        attempts=attempts,
    )
    if (
        cutover_result["live_attempt_audit_closure_id"]
        != live_attempt_audit["audit_closure_id"]
    ):
        raise AcceptanceError("Live attempt audit result identity differs")

    old_reference = (
        recorded_evidence["old_resolver_throws_receipt"]
        if "old_resolver_throws_receipt" in recorded_evidence
        else None
    )
    if (
        type(old_reference) is not dict
        or set(old_reference) != {"path", "receipt_id", "sha256"}
    ):
        raise AcceptanceError("Old-resolver public-flow evidence is absent")
    old_binding, old_payload = _bind_addressed_receipt(
        repo_root=repo_root,
        path_value=old_reference["path"],
        expected_id=old_reference["receipt_id"],
        identity_field="old_resolver_throws_receipt_id",
    )
    old_payload_fields = {
        "active_state_unchanged",
        "command",
        "evidence_tier",
        "human_decision_evidence",
        "scenario_id",
    }
    if (
        old_binding["sha256"] != old_reference["sha256"]
        or not old_payload_fields.issubset(old_payload)
        or old_payload["scenario_id"]
        != "OLD_RESOLVERS_THROW_PUBLIC_CUTOVER_TEST_FLOW"
        or old_payload["evidence_tier"] != "TEST_ONLY_PUBLIC_FLOW"
        or old_payload["human_decision_evidence"]
        != "TEST_ONLY_NOT_ACCEPTANCE"
        or old_payload["active_state_unchanged"] is not True
        or type(old_payload["command"]) is not dict
        or "outcome" not in old_payload["command"]
        or old_payload["command"]["outcome"] != "PASSED"
    ):
        raise AcceptanceError("Old-resolver public-flow receipt is invalid")
    acceptance_evidence = {
        **declared_evidence,
        "old_resolver_throws_receipt_id": old_reference["receipt_id"],
    }

    cutover_receipt_path, _cutover_relative = _repository_path(
        repo_root=repo_root,
        path_value=cutover_result["cutover_receipt_path"],
        kind="file",
    )
    fault_matrix = _validated_fault_matrix(
        repo_root=repo_root,
        cutover_receipt_path=cutover_receipt_path,
        cutover_result=cutover_result,
        fault_receipt_ids=declared_evidence[
            "fault_injection_receipt_ids"
        ],
    )
    batch_path, batch_relative = _repository_path(
        repo_root=repo_root,
        path_value=cutover_result["batch_manifest_path"],
        kind="file",
    )
    run_closure = _validated_run_closure(
        repo_root=repo_root,
        batch_path=batch_path,
        cutover_result=cutover_result,
        attempts=attempts,
    )
    snapshot_path, snapshot_relative = _repository_path(
        repo_root=repo_root, path_value=SNAPSHOT_PATH, kind="file",
    )
    snapshot_sha256 = sha256_file(path=snapshot_path)
    receipt_bindings = {
        "cutover": cutover_binding,
        "live_attempt_audit": live_attempt_audit,
        "live_stability": stability_binding,
        "old_resolver_throws": old_binding,
        "sec_acquisition": acquisition_binding,
        "invocation_sec_acquisition": invocation_acquisition_binding,
        "staging_parity": staging_binding,
    }
    receipt_bindings.update({
        "fault:" + binding["scenario_id"]: binding
        for binding in fault_matrix["receipts"]
    })
    initial_receipt_hashes = {
        binding["repo_relative_path"]: binding["sha256"]
        for binding in receipt_bindings.values()
    }

    # Repeat every mutable locator and deep replay before sealing the result;
    # this detects pointer, mirror, Run, Batch, receipt, or source drift.
    final_source = capture_source_snapshot(workdir=repo_root)
    final_requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/ai_first_v3_3_1"
    )
    final_publication = _validated_publication_state(
        repo_root=repo_root, expected_publication_id=publication_id,
    )
    final_run_closure = _validated_run_closure(
        repo_root=repo_root,
        batch_path=batch_path,
        cutover_result=cutover_result,
        attempts=attempts,
    )
    final_fault_matrix = _validated_fault_matrix(
        repo_root=repo_root,
        cutover_receipt_path=cutover_receipt_path,
        cutover_result=cutover_result,
        fault_receipt_ids=declared_evidence[
            "fault_injection_receipt_ids"
        ],
    )
    final_recorded_gate_artifacts = _validated_recorded_gate_artifacts(
        repo_root=repo_root, recorded_evidence=recorded_evidence,
    )
    final_acquisition_binding, final_acquisition = (
        _validated_sec_acquisition_binding(
            repo_root=repo_root,
            receipt_id=declared_evidence["sec_acquisition_receipt_id"],
            receipt_path=cutover_result["sec_acquisition_receipt_path"],
        )
    )
    final_invocation_binding, final_invocation = (
        _validated_sec_acquisition_binding(
            repo_root=repo_root,
            receipt_id=cutover_result[
                "invocation_sec_acquisition_receipt_id"
            ],
            receipt_path=cutover_result[
                "invocation_sec_acquisition_receipt_path"
            ],
        )
    )
    final_receipt_hashes = {}
    for relative, expected_hash in initial_receipt_hashes.items():
        path, _portable = _repository_path(
            repo_root=repo_root, path_value=relative, kind="file",
        )
        final_receipt_hashes[relative] = sha256_file(path=path)
        if final_receipt_hashes[relative] != expected_hash:
            raise AcceptanceError("Formal receipt changed during binding")
    if (
        final_source != source
        or final_requirement != requirement
        or final_publication != initial_publication
        or final_run_closure != run_closure
        or final_fault_matrix != fault_matrix
        or final_recorded_gate_artifacts != recorded_gate_artifacts
        or final_acquisition_binding != acquisition_binding
        or final_acquisition != acquisition
        or final_invocation_binding != invocation_acquisition_binding
        or final_invocation != invocation_acquisition
        or sha256_file(path=snapshot_path) != snapshot_sha256
    ):
        raise AcceptanceError("Formal evidence changed during final binding")

    return {
        "source": asdict(source),
        "requirements": {
            "requirement_closure_hash": requirement[
                "requirement_closure_hash"
            ],
            "hashes": requirement["hashes"],
            "d01_effective_decision_hash": content_hash(value=d01),
            "provider_policy": d01["choice"],
        },
        "batch": {
            "batch_manifest_id": run_closure["batch"][
                "batch_manifest_id"
            ],
            "repo_relative_path": batch_relative,
            "sha256": run_closure["batch_sha256"],
        },
        "runs": run_closure["batch_runs"],
        "live_attempt_runs": run_closure["attempt_runs"],
        "live_attempts": attempt_bindings,
        "successful_live_attempt_ids": successful_ids,
        "formal_receipts": {
            "cutover": cutover_binding,
            "fault_matrix": fault_matrix,
            "live_stability": stability_binding,
            "old_resolver_throws": old_binding,
            "sec_acquisition": acquisition_binding,
            "invocation_sec_acquisition": (
                invocation_acquisition_binding
            ),
            "staging_parity": staging_binding,
            "recorded_gate_artifacts": recorded_gate_artifacts,
        },
        "cutover_acceptance_evidence": acceptance_evidence,
        "publication": {
            key: initial_publication[key]
            for key in (
                "active_pointer_sha256",
                "bundle_manifest_sha256",
                "publication_id",
                "previous_publication_id",
                "root_mirror_hashes",
                "validation_receipt_id",
            )
        },
        "final_snapshot_path": snapshot_relative,
        "final_snapshot_sha256": snapshot_sha256,
    }


def _acceptance_authority_binding(*, repo_root: Path) -> Dict[str, object]:
    """Capture the clean source tree and exact Requirement authority closure.

    Args:
        repo_root: Repository owning source and Requirement snapshots.

    Returns:
        Stable source/Requirement identity safe to persist in any scope.
    """
    source = capture_source_snapshot(workdir=repo_root)
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/ai_first_v3_3_1"
    )
    return {
        "source": asdict(source),
        "requirements": {
            "requirement_closure_hash": requirement[
                "requirement_closure_hash"
            ],
            "hashes": requirement["hashes"],
        },
    }


def _formal_authority_matches(
    *, authority: Mapping[str, object], formal: Mapping[str, object],
) -> bool:
    """Return whether formal evidence rebinds the initial exact authority.

    Args:
        authority: Initial acceptance source/Requirement binding.
        formal: Final formal evidence returned after restore.

    Returns:
        ``True`` only when source and complete Requirement hashes are exact.
    """
    if (
        "source" not in formal
        or formal["source"] != authority["source"]
        or "requirements" not in formal
        or type(formal["requirements"]) is not dict
        or "requirement_closure_hash" not in formal["requirements"]
        or "hashes" not in formal["requirements"]
    ):
        return False
    return (
        formal["requirements"]["requirement_closure_hash"]
        == authority["requirements"]["requirement_closure_hash"]
        and formal["requirements"]["hashes"]
        == authority["requirements"]["hashes"]
    )


def _publication_core_state(
    *, state: Mapping[str, object],
) -> Dict[str, object]:
    """Select the active identity and mirror hashes from one observation.

    Args:
        state: Recorded or official publication observation.

    Returns:
        Publication authority fields used for exact equality checks.
    """
    if "active_publication_id" not in state or "mirror_hashes" not in state:
        raise AcceptanceError("Publication state fields are incomplete")
    return {
        "active_publication_id": state["active_publication_id"],
        "mirror_hashes": state["mirror_hashes"],
    }


def _recover_cutover_side_effect(
    *,
    repo_root: Path,
    current_python: str,
    timeout_seconds: int,
    output_dir: Path,
    predecessor_state: Mapping[str, object],
    observed_state: Mapping[str, object],
    authority_backup: Mapping[str, Optional[bytes]],
) -> Optional[Dict[str, object]]:
    """Rollback a publication committed by a failed Cutover invocation.

    Args:
        repo_root: Formal publication root.
        current_python: Supported operator interpreter.
        timeout_seconds: Operator timeout.
        output_dir: Durable switch-receipt root.
        predecessor_state: State before invoking Cutover.
        observed_state: Official read-back after the child returned.
        authority_backup: Exact root bytes captured before Cutover.

    Returns:
        Validated switch result, or ``None`` when no state changed.
    """
    if _publication_core_state(state=observed_state) == (
        _publication_core_state(state=predecessor_state)
    ):
        return None
    current_id = observed_state["active_publication_id"]
    predecessor_id = predecessor_state["active_publication_id"]
    if current_id is None:
        raise AcceptanceError("Failed Cutover removed the active publication")
    expected_target_state: Optional[Mapping[str, object]] = predecessor_state
    if predecessor_id is None:
        _restore_recorded_authority(
            repo_root=repo_root, backup=authority_backup,
        )
        restored = _recorded_state_snapshot(repo_root=repo_root)
        if _publication_core_state(state=restored) != (
            _publication_core_state(state=predecessor_state)
        ):
            raise AcceptanceError(
                "Failed initial Cutover authority restore differs"
            )
        body = {
            "schema_version": 1,
            "phase": "CUTOVER_FAILURE_AUTHORITY_RESTORE",
            "observed_at_utc": utc_now(),
            "active_before": observed_state["active_publication_id"],
            "active_after": restored["active_publication_id"],
            "mirror_hashes_before": observed_state["mirror_hashes"],
            "mirror_hashes_after": restored["mirror_hashes"],
            "outcome": "PASSED",
        }
        receipt_id = content_hash(value=body)
        path = output_dir / "publication_switch_receipts" / (
            receipt_id.split(":", maxsplit=1)[1] + ".json"
        )
        receipt = {**body, "receipt_id": receipt_id}
        atomic_write_json(path=path, value=receipt)
        return {
            "command": None,
            "error_code": "",
            "message": "",
            "ok": True,
            "receipt": {
                "active_after": None,
                "active_before": str(current_id),
                "path": str(path),
                "receipt_id": receipt_id,
                "sha256": sha256_file(path=path),
            },
            "state": restored,
        }
    return _validated_publication_switch(
        repo_root=repo_root,
        current_python=current_python,
        timeout_seconds=timeout_seconds,
        output_dir=output_dir,
        mode="rollback",
        phase="CUTOVER_FAILURE_RECOVERY_ROLLBACK",
        target_publication_id=str(predecessor_id),
        expected_active_publication_id=str(current_id),
        before=observed_state,
        expected_target_state=expected_target_state,
    )


def execute_acceptance(
    *,
    repo_root: Path,
    scope: str,
    execute_live: bool,
    current_python: str,
    python39: Optional[str],
    output_dir: Path,
    timeout_seconds: int,
) -> Dict[str, object]:
    """Execute recorded gates or the explicitly authorized full command chain.

    Args:
        repo_root: Repository root.
        scope: ``recorded`` or ``full``.
        execute_live: Explicit authority for network/Cutover work.
        current_python: Default interpreter.
        python39: Floor interpreter or ``None``.
        output_dir: Receipt directory.
        timeout_seconds: Per-command timeout.

    Returns:
        Complete acceptance receipt including its output path.
    """
    _validate_acceptance_output_dir(
        repo_root=repo_root, output_dir=output_dir,
    )
    if scope not in {"recorded", "full"}:
        raise AcceptanceError("Acceptance scope is invalid")
    if type(execute_live) is not bool:
        raise AcceptanceError("Live execution authority must be boolean")
    started_at = utc_now()
    authority_binding: Optional[Dict[str, object]] = None
    blockers = []
    commands: List[Dict[str, object]] = []
    not_run_items: List[Dict[str, str]] = []
    recorded_evidence: Optional[Dict[str, object]] = None
    full_binding: Optional[Dict[str, object]] = None
    rollback_receipt: Optional[Dict[str, str]] = None
    restore_receipt: Optional[Dict[str, str]] = None
    recovery_receipt: Optional[Dict[str, object]] = None
    terminal_cycle_ids: Dict[str, str] = {}
    terminal_cycle_results: Dict[str, Dict[str, object]] = {}
    cutover_binding: Optional[Dict[str, object]] = None
    blocking_detail: Optional[Dict[str, object]] = None
    predecessor_state: Optional[Mapping[str, object]] = None
    post_cutover: Optional[Mapping[str, object]] = None
    rolled_back_state: Optional[Mapping[str, object]] = None
    predecessor_validation_state: Optional[Mapping[str, object]] = None
    publication_id: Optional[str] = None
    previous_id: Optional[str] = None
    status = ""
    if scope == "full" and not execute_live:
        status = "LIVE_EXECUTION_NOT_AUTHORIZED"
        blocking_detail = {"code": status}
    if not status:
        try:
            authority_binding = _acceptance_authority_binding(
                repo_root=repo_root,
            )
        except (OSError, ValidationProvenanceError, ValueError) as error:
            status = "SOURCE_REQUIREMENT_CLOSURE_INVALID"
            blocking_detail = {
                "code": status,
                "error_class": type(error).__name__,
                "message": str(error),
            }
    if not status and scope == "full" and execute_live:
        blockers = external_blockers(repo_root=repo_root)
        if blockers:
            status = "BLOCKED"
            blocking_detail = {
                "code": status,
                "blocker_codes": [blocker["code"] for blocker in blockers],
            }
    if status:
        not_run_items.append({
            "phase": "FORMAL_CUTOVER_AND_ROLLBACK_RESTORE",
            "reason": status,
        })
    if not status:
        gate_dir = output_dir / "recorded_gate_runs" / uuid.uuid4().hex
        try:
            recorded_evidence = _recorded_gate_execution(
                repo_root=repo_root,
                current_python=current_python,
                python39=python39,
                gate_output_dir=gate_dir,
                timeout_seconds=timeout_seconds,
            )
        except (
            AcceptanceError,
            OSError,
            PublicationError,
            ValueError,
        ) as error:
            status = "RECORDED_GATE_EXECUTION_FAILED"
            blocking_detail = {
                "code": status,
                "error_class": type(error).__name__,
                "message": str(error),
            }
        if not status:
            commands.extend(recorded_evidence["commands"])
        if not status and not recorded_evidence["active_state_unchanged"]:
            status = "RECORDED_ACTIVE_STATE_CHANGED"
        elif not status and not _commands_complete(commands=commands):
            status = (
                "FAILED"
                if any(row["outcome"] == "FAILED" for row in commands)
                else "INCOMPLETE"
            )
        elif not status and (
            "artifact_closure_complete" not in recorded_evidence
            or recorded_evidence["artifact_closure_complete"] is not True
            or "artifact_hashes" not in recorded_evidence
            or set(recorded_evidence["artifact_hashes"])
            != set(RECORDED_GATE_ARTIFACTS)
        ):
            status = "RECORDED_ARTIFACT_CLOSURE_INCOMPLETE"
        elif not status:
            try:
                final_recorded_authority = _acceptance_authority_binding(
                    repo_root=repo_root,
                )
            except (OSError, ValidationProvenanceError, ValueError) as error:
                status = "ACCEPTANCE_AUTHORITY_CHANGED"
                blocking_detail = {
                    "code": status,
                    "error_class": type(error).__name__,
                    "message": str(error),
                }
            else:
                if final_recorded_authority != authority_binding:
                    status = "ACCEPTANCE_AUTHORITY_CHANGED"
                    blocking_detail = {"code": status}
                elif scope == "recorded":
                    status = "PASSED_RECORDED_ONLY"
    if scope == "full" and not status:
        predecessor_state = recorded_evidence["publication_state_after"]
        previous_id = predecessor_state["active_publication_id"]
        cutover_authority_backup = _recorded_authority_backup(
            repo_root=repo_root,
        )
        cutover_record, cutover_envelope = run_json_command(
            argv=[
                current_python,
                FULL_CUTOVER_COMMAND,
                "--execute-live",
                "--json",
            ],
            repo_root=repo_root,
            environment={"PYTHONDONTWRITEBYTECODE": "1"},
            timeout_seconds=timeout_seconds,
        )
        commands.append(cutover_record)
        cutover_result = _json_result(
            parsed=cutover_envelope, command_name="cutover",
        )
        observed_after_cutover: Optional[Mapping[str, object]] = None
        try:
            observed_after_cutover = publication_state_snapshot(
                publication_root=repo_root,
            )
        except (OSError, PublicationError, ValueError) as error:
            status = "CUTOVER_STATE_READBACK_FAILED"
            blocking_detail = {
                "code": status,
                "error_class": type(error).__name__,
                "message": str(error),
            }
        if (
            not status
            and (
                cutover_record["outcome"] != "PASSED"
                or cutover_result is None
            )
        ):
            status = "FAILED"
            blocking_detail = {"code": status}
            if (
                cutover_envelope is not None
                and "error" in cutover_envelope
                and type(cutover_envelope["error"]) is dict
                and "code" in cutover_envelope["error"]
                and cutover_envelope["error"]["code"]
                == "HUMAN_REVIEW_REQUIRED"
            ):
                status = "HUMAN_REVIEW_REQUIRED"
                blocking_detail = dict(cutover_envelope["error"])
                blocking_detail["resume_command"] = (
                    "python3 tools/run_acceptance.py --scope full "
                    "--execute-live"
                )
        if not status:
            required_result_fields = {
                "publication_id",
                "previous_publication_id",
                "status",
            }
            resumed_after_commit = (
                "resumed_after_commit" in cutover_result
                and cutover_result["resumed_after_commit"] is True
            )
            result_valid = (
                required_result_fields.issubset(cutover_result)
                and cutover_result["status"] == "PUBLISHED"
                and type(cutover_result["publication_id"]) is str
                and bool(cutover_result["publication_id"])
                and type(cutover_result["previous_publication_id"]) is str
                and bool(cutover_result["previous_publication_id"])
            )
            if result_valid and resumed_after_commit:
                result_valid = (
                    previous_id == cutover_result["publication_id"]
                )
                predecessor_validation_state = None
            elif result_valid and previous_id is not None:
                result_valid = (
                    cutover_result["previous_publication_id"] == previous_id
                )
                predecessor_validation_state = predecessor_state
            elif result_valid:
                result_valid = (
                    "initial_publication_id" in cutover_result
                    and cutover_result["initial_publication_id"]
                    == cutover_result["previous_publication_id"]
                )
                predecessor_validation_state = None
            if (
                not result_valid
                or observed_after_cutover["active_publication_id"]
                != cutover_result["publication_id"]
            ):
                status = "CUTOVER_NOT_PUBLISHED"
                blocking_detail = {"code": status}
        if status and observed_after_cutover is not None:
            try:
                recovery = _recover_cutover_side_effect(
                    repo_root=repo_root,
                    current_python=current_python,
                    timeout_seconds=timeout_seconds,
                    output_dir=output_dir,
                    predecessor_state=predecessor_state,
                    observed_state=observed_after_cutover,
                    authority_backup=cutover_authority_backup,
                )
            except (AcceptanceError, OSError, ValueError) as error:
                status = "CUTOVER_FAILURE_RECOVERY_FAILED"
                blocking_detail = {
                    "code": status,
                    "error_class": type(error).__name__,
                    "message": str(error),
                }
            else:
                if recovery is not None:
                    if recovery["command"] is not None:
                        commands.append(recovery["command"])
                    if not recovery["ok"]:
                        status = "CUTOVER_FAILURE_RECOVERY_FAILED"
                        blocking_detail = {
                            "code": status,
                            "failure_code": recovery["error_code"],
                            "message": recovery["message"],
                        }
                    else:
                        recovery_receipt = recovery["receipt"]
                        blocking_detail["recovery"] = (
                            "ROLLED_BACK_PREDECESSOR"
                        )
                        blocking_detail["active_publication_id"] = (
                            recovery["state"]["active_publication_id"]
                        )
        if not status:
            publication_id = str(cutover_result["publication_id"])
            previous_id = str(cutover_result["previous_publication_id"])
            post_cutover = observed_after_cutover
            if post_cutover["active_publication_id"] == publication_id:
                cutover_binding = {
                    "release_input_plan_id": cutover_result[
                        "release_input_plan_id"
                    ] if "release_input_plan_id" in cutover_result else None,
                    "batch_manifest_id": cutover_result[
                        "batch_manifest_id"
                    ] if "batch_manifest_id" in cutover_result else None,
                    "publication_id": publication_id,
                    "previous_publication_id": previous_id,
                    "validation_receipt_id": cutover_result[
                        "validation_receipt_id"
                    ] if "validation_receipt_id" in cutover_result else None,
                    "command_stdout_sha256": cutover_record[
                        "stdout_sha256"
                    ],
                }
                new_cycle = _terminal_cycle(
                    repo_root=repo_root,
                    current_python=current_python,
                    timeout_seconds=timeout_seconds,
                    guard_dir=output_dir / "terminal_guards" / "new",
                    expected_publication_id=publication_id,
                )
                commands.extend(new_cycle)
                if _commands_complete(commands=new_cycle):
                    new_result = dict(
                        new_cycle[0]["terminal_cycle_result"]
                    )
                    terminal_cycle_results["new_publication"] = new_result
                    terminal_cycle_ids["new_publication"] = str(
                        new_result["terminal_cycle_id"]
                    )
                if not _commands_complete(commands=new_cycle):
                    failure_code = (
                        "NEW_PUBLICATION_TERMINAL_VALIDATION_FAILED"
                    )
                    emergency = _validated_publication_switch(
                        repo_root=repo_root,
                        current_python=current_python,
                        timeout_seconds=timeout_seconds,
                        output_dir=output_dir,
                        mode="rollback",
                        phase="ROLLBACK",
                        target_publication_id=previous_id,
                        expected_active_publication_id=publication_id,
                        before=post_cutover,
                        expected_target_state=predecessor_validation_state,
                    )
                    commands.append(emergency["command"])
                    if not emergency["ok"]:
                        status = "EMERGENCY_ROLLBACK_READBACK_FAILED"
                        blocking_detail = {
                            "code": status,
                            "trigger": failure_code,
                            "failure_code": emergency["error_code"],
                            "message": emergency["message"],
                        }
                    else:
                        rollback_receipt = emergency["receipt"]
                        status = "BLOCKED"
                        blocking_detail = {
                            "code": failure_code,
                            "recovery": "ROLLED_BACK",
                            "active_publication_id": previous_id,
                        }
    if scope == "full" and not status:
        rollback = _validated_publication_switch(
            repo_root=repo_root,
            current_python=current_python,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
            mode="rollback",
            phase="ROLLBACK",
            target_publication_id=str(previous_id),
            expected_active_publication_id=str(publication_id),
            before=post_cutover,
            expected_target_state=predecessor_validation_state,
        )
        commands.append(rollback["command"])
        if not rollback["ok"]:
            status = "ROLLBACK_FAILED"
            blocking_detail = {
                "code": status,
                "failure_code": rollback["error_code"],
                "message": rollback["message"],
            }
        else:
            rolled_back_state = rollback["state"]
            rollback_receipt = rollback["receipt"]
            rollback_cycle = _terminal_cycle(
                repo_root=repo_root,
                current_python=current_python,
                timeout_seconds=timeout_seconds,
                guard_dir=output_dir / "terminal_guards" / "rollback",
                expected_publication_id=str(previous_id),
            )
            commands.extend(rollback_cycle)
            if _commands_complete(commands=rollback_cycle):
                rollback_result = dict(
                    rollback_cycle[0]["terminal_cycle_result"]
                )
                terminal_cycle_results["rollback"] = rollback_result
                terminal_cycle_ids["rollback"] = str(
                    rollback_result["terminal_cycle_id"]
                )
            if not _commands_complete(commands=rollback_cycle):
                trigger = "ROLLBACK_TERMINAL_VALIDATION_FAILED"
                recovery = _validated_publication_switch(
                    repo_root=repo_root,
                    current_python=current_python,
                    timeout_seconds=timeout_seconds,
                    output_dir=output_dir,
                    mode="restore",
                    phase="ROLLBACK_TERMINAL_RECOVERY_RESTORE",
                    target_publication_id=str(publication_id),
                    expected_active_publication_id=str(previous_id),
                    before=rolled_back_state,
                    expected_target_state=post_cutover,
                )
                commands.append(recovery["command"])
                if not recovery["ok"]:
                    status = "ROLLBACK_TERMINAL_RECOVERY_FAILED"
                    blocking_detail = {
                        "code": status,
                        "trigger": trigger,
                        "failure_code": recovery["error_code"],
                        "message": recovery["message"],
                    }
                else:
                    recovery_receipt = recovery["receipt"]
                    status = "BLOCKED"
                    blocking_detail = {
                        "code": trigger,
                        "recovery": "RESTORED_NEW_PUBLICATION",
                        "active_publication_id": publication_id,
                    }
    if scope == "full" and not status:
        restore = _validated_publication_switch(
            repo_root=repo_root,
            current_python=current_python,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
            mode="restore",
            phase="RESTORE",
            target_publication_id=str(publication_id),
            expected_active_publication_id=str(previous_id),
            before=rolled_back_state,
            expected_target_state=post_cutover,
        )
        commands.append(restore["command"])
        if not restore["ok"]:
            status = "RESTORE_FAILED"
            blocking_detail = {
                "code": status,
                "failure_code": restore["error_code"],
                "message": restore["message"],
            }
        else:
            restored_state = restore["state"]
            restore_receipt = restore["receipt"]
            final_cycle = _terminal_cycle(
                repo_root=repo_root,
                current_python=current_python,
                timeout_seconds=timeout_seconds,
                guard_dir=output_dir / "terminal_guards" / "restore",
                expected_publication_id=str(publication_id),
            )
            commands.extend(final_cycle)
            if _commands_complete(commands=final_cycle):
                restore_result = dict(
                    final_cycle[0]["terminal_cycle_result"]
                )
                terminal_cycle_results["restore"] = restore_result
                terminal_cycle_ids["restore"] = str(
                    restore_result["terminal_cycle_id"]
                )
            if not _commands_complete(commands=final_cycle):
                trigger = "RESTORE_TERMINAL_VALIDATION_FAILED"
                recovery = _validated_publication_switch(
                    repo_root=repo_root,
                    current_python=current_python,
                    timeout_seconds=timeout_seconds,
                    output_dir=output_dir,
                    mode="rollback",
                    phase="RESTORE_TERMINAL_RECOVERY_ROLLBACK",
                    target_publication_id=str(previous_id),
                    expected_active_publication_id=str(publication_id),
                    before=restored_state,
                    expected_target_state=rolled_back_state,
                )
                commands.append(recovery["command"])
                if not recovery["ok"]:
                    status = "RESTORE_TERMINAL_RECOVERY_FAILED"
                    blocking_detail = {
                        "code": status,
                        "trigger": trigger,
                        "failure_code": recovery["error_code"],
                        "message": recovery["message"],
                    }
                else:
                    recovery_receipt = recovery["receipt"]
                    status = "BLOCKED"
                    blocking_detail = {
                        "code": trigger,
                        "recovery": "ROLLED_BACK_PREDECESSOR",
                        "active_publication_id": previous_id,
                    }
            else:
                try:
                    full_binding = formal_evidence_binding(
                        repo_root=repo_root,
                        cutover_result=cutover_result,
                        final_state=restored_state,
                        recorded_evidence=recorded_evidence,
                    )
                    final_authority = _acceptance_authority_binding(
                        repo_root=repo_root,
                    )
                    if (
                        final_authority != authority_binding
                        or not _formal_authority_matches(
                            authority=authority_binding,
                            formal=full_binding,
                        )
                    ):
                        raise AcceptanceError(
                            "Formal source/Requirement authority differs"
                        )
                except (
                    AcceptanceError,
                    OSError,
                    ValidationProvenanceError,
                    ValueError,
                ) as error:
                    status = "FULL_EVIDENCE_BINDING_FAILED"
                    blocking_detail = {
                        "code": status,
                        "error_class": type(error).__name__,
                        "message": str(error),
                    }
                    recovery = _validated_publication_switch(
                        repo_root=repo_root,
                        current_python=current_python,
                        timeout_seconds=timeout_seconds,
                        output_dir=output_dir,
                        mode="rollback",
                        phase="FULL_EVIDENCE_RECOVERY_ROLLBACK",
                        target_publication_id=str(previous_id),
                        expected_active_publication_id=str(publication_id),
                        before=restored_state,
                        expected_target_state=rolled_back_state,
                    )
                    commands.append(recovery["command"])
                    if not recovery["ok"]:
                        status = "FULL_EVIDENCE_RECOVERY_FAILED"
                        blocking_detail = {
                            "code": status,
                            "trigger": "FULL_EVIDENCE_BINDING_FAILED",
                            "failure_code": recovery["error_code"],
                            "message": recovery["message"],
                        }
                    else:
                        recovery_receipt = recovery["receipt"]
                        blocking_detail["recovery"] = (
                            "ROLLED_BACK_PREDECESSOR"
                        )
                        blocking_detail["active_publication_id"] = (
                            previous_id
                        )
                else:
                    status = "PASSED"
    if scope == "full" and status != "PASSED" and not not_run_items:
        not_run_items.append({
            "phase": "REMAINING_FULL_ACCEPTANCE",
            "reason": status,
        })
    body = {
        "schema_version": 3,
        "scope": scope,
        "execute_live": execute_live,
        "status": status,
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "commands": commands,
        "external_blockers": blockers,
        "blocking_detail": blocking_detail,
        "not_run_items": not_run_items,
        "authority_binding": authority_binding,
        "recorded_evidence": recorded_evidence,
        "cutover_binding": cutover_binding,
        "terminal_cycle_ids": terminal_cycle_ids,
        "terminal_cycle_results": terminal_cycle_results,
        "rollback_receipt": rollback_receipt,
        "restore_receipt": restore_receipt,
        "recovery_receipt": recovery_receipt,
        "full_evidence_binding": full_binding,
    }
    try:
        receipt, output_path = _persist_acceptance_receipt(
            output_dir=output_dir,
            body=body,
            repo_root=repo_root,
            current_python=current_python,
            python39=python39,
        )
    except (AcceptanceError, CanonicalError, OSError, ValueError) as error:
        # A full PASS does not exist until its exact receipt is durable.  Move
        # back to the verified predecessor before emitting any failure result.
        if (
            scope != "full"
            or status != "PASSED"
            or publication_id is None
            or previous_id is None
            or rolled_back_state is None
            or post_cutover is None
        ):
            raise
        try:
            recovery = _validated_publication_switch(
                repo_root=repo_root,
                current_python=current_python,
                timeout_seconds=timeout_seconds,
                output_dir=output_dir,
                mode="rollback",
                phase="FULL_RECEIPT_RECOVERY_ROLLBACK",
                target_publication_id=previous_id,
                expected_active_publication_id=publication_id,
                before=post_cutover,
                expected_target_state=rolled_back_state,
            )
        except (CanonicalError, OSError, ValueError) as recovery_error:
            raise AcceptanceError(
                "Full receipt failed and recovery receipt is not durable"
            ) from recovery_error
        commands.append(recovery["command"])
        if not recovery["ok"]:
            raise AcceptanceError(
                "Full receipt failed and predecessor recovery failed"
            ) from error
        recovery_receipt = recovery["receipt"]
        status = "FULL_RECEIPT_WRITE_FAILED"
        blocking_detail = {
            "code": status,
            "error_class": type(error).__name__,
            "message": str(error),
            "recovery": "ROLLED_BACK_PREDECESSOR",
            "active_publication_id": previous_id,
        }
        not_run_items.append({
            "phase": "FULL_ACCEPTANCE_RECEIPT",
            "reason": status,
        })
        body["status"] = status
        body["blocking_detail"] = blocking_detail
        body["not_run_items"] = not_run_items
        body["recovery_receipt"] = recovery_receipt
        body["finished_at_utc"] = utc_now()
        receipt, output_path = _persist_acceptance_receipt(
            output_dir=output_dir,
            body=body,
            repo_root=repo_root,
            current_python=current_python,
            python39=python39,
        )
    receipt["output_path"] = str(output_path)
    return receipt


def _paths_overlap(*, left: Path, right: Path) -> bool:
    """Return whether either absolute path contains the other.

    Args:
        left: First resolved path.
        right: Second resolved path.

    Returns:
        True for equality, ancestor, or descendant relationships.
    """
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _validate_acceptance_output_dir(
    *, repo_root: Path, output_dir: Path,
) -> None:
    """Reject every output overlap with formal publication authority.

    Args:
        repo_root: Formal repository authority.
        output_dir: Proposed acceptance artifact directory.
    """
    root = repo_root.resolve(strict=True)
    candidate = output_dir.resolve(strict=False)
    protected = (
        *_recorded_protected_file_relative_paths(),
        *FORMAL_NAMESPACE_PATHS,
    )
    for relative in protected:
        if _paths_overlap(left=candidate, right=root / relative):
            raise AcceptanceError(
                "ACCEPTANCE_OUTPUT_DIR_OVERLAPS_FORMAL_AUTHORITY"
            )


def _resolve_acceptance_output_dir(
    *, repo_root: Path, value: str,
) -> Path:
    """Resolve one repository-owned non-symlinked receipt directory.

    Args:
        repo_root: Explicit acceptance repository.
        value: CLI-relative output directory.

    Returns:
        Absolute path proven to stay below ``repo_root``.
    """
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise AcceptanceError("ACCEPTANCE_OUTPUT_DIR_ESCAPES_REPOSITORY")
    root = repo_root.resolve(strict=True)
    _validate_acceptance_output_dir(
        repo_root=repo_root,
        output_dir=(root / relative).resolve(strict=False),
    )
    candidate = root
    for part in relative.parts:
        if part in {"", "."}:
            continue
        candidate /= part
        if candidate.is_symlink():
            raise AcceptanceError("ACCEPTANCE_OUTPUT_DIR_SYMLINK_UNSAFE")
        if candidate.exists() and not candidate.is_dir():
            raise AcceptanceError("ACCEPTANCE_OUTPUT_DIR_NOT_DIRECTORY")
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except ValueError as error:
        raise AcceptanceError(
            "ACCEPTANCE_OUTPUT_DIR_ESCAPES_REPOSITORY"
        ) from error
    _validate_acceptance_output_dir(
        repo_root=repo_root, output_dir=resolved,
    )
    return resolved


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
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--python39")
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--output-dir", default="outputs/acceptance_receipts")
    arguments = parser.parse_args(list(argv))
    repo_root = Path(arguments.repo_root).resolve()
    output_dir = _resolve_acceptance_output_dir(
        repo_root=repo_root, value=arguments.output_dir,
    )
    python39 = (
        None
        if arguments.scope == "full" and not arguments.execute_live
        else resolve_python39(
            explicit_path=arguments.python39, repo_root=repo_root,
        )
    )
    receipt = execute_acceptance(
        repo_root=repo_root,
        scope=arguments.scope,
        execute_live=arguments.execute_live,
        current_python=str(Path(sys.executable).resolve()),
        python39=python39,
        output_dir=output_dir,
        timeout_seconds=arguments.timeout_seconds,
    )
    summary = {
        "status": receipt["status"],
        "acceptance_receipt_id": receipt["acceptance_receipt_id"],
        "output_path": receipt["output_path"],
    }
    if receipt["blocking_detail"] is not None:
        summary["blocking_detail"] = receipt["blocking_detail"]
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if receipt["status"] in {"PASSED", "PASSED_RECORDED_ONLY"} else 1


if __name__ == "__main__":
    try:
        sys.exit(main(argv=sys.argv[1:]))
    except AcceptanceError as error:
        print(json.dumps(
            {
                "ok": False,
                "error": {"code": str(error), "message": str(error)},
            },
            ensure_ascii=False,
        ))
        sys.exit(1)
