#!/usr/bin/env python3
"""Run one guarded, offline full JPM expanded-grid materialization benchmark."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path = [str(SCRIPTS_DIR), *sys.path]

from vnext.canonical import atomic_write_json  # noqa: E402
from vnext.canonical import canonical_json_bytes, content_hash  # noqa: E402
from vnext.canonical import sha256_bytes, sha256_file  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402


SOURCE_RELATIVE = Path(
    "evidence/request_attempts/4d/"
    "4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/"
    "jpm-20251231.htm"
)
SOURCE_SHA256 = (
    "4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23"
)
STAGE_B_CENSUS_RECEIPT_ID = (
    "sha256:ea3d796f256a43ac5a6079de753d7d5456fc6d7485bb794ef4c9e27276ca6f2c"
)
STAGE_B_CENSUS_RELATIVE = Path(
    "artifacts/vnext/table_stage_b_investigation/financial_grid_census/"
    "ea3d796f256a43ac5a6079de753d7d5456fc6d7485bb794ef4c9e27276ca6f2c.json"
)
OUTPUT_ROOT = Path(
    "artifacts/vnext/table_stage_c_evidence/"
    "financial_materialization_benchmark"
)
SEMANTIC_ROOT = OUTPUT_ROOT / "semantic_receipts"
RUN_ROOT = OUTPUT_ROOT / "run_receipts"
CURRENT_POINTER = OUTPUT_ROOT / "current.json"
TOOL_RELATIVE = Path("tools/benchmark_jpm_full_materialization.py")
TABLE_GRID_RELATIVE = Path("scripts/vnext/table_grid.py")
RESOURCE_LIMITS_RELATIVE = Path("scripts/vnext/resource_limits.py")
CANONICAL_RELATIVE = Path("scripts/vnext/canonical.py")
TEST_ONLY_MAX_TOTAL_CELLS = 187142
EXPECTED_RECTANGULAR_CELLS = 124761
EXPECTED_TABLE_COUNT = 679
PRODUCTION_MAX_TOTAL_CELLS = 100000
RSS_CEILING_BYTES = 512 * 1024 * 1024
WALL_TIME_CEILING_SECONDS = 120
RSS_POLL_INTERVAL_SECONDS = 0.02
NETWORK_DENY_PROFILE = "(version 1) (allow default) (deny network*)"
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
DOCKER_LINUX_IMAGE = (
    "python:3.12.11-slim-bookworm@"
    "sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
)
DOCKER_WORKDIR = "/workspace"
LINUX_CGROUP_MEMORY_MAX = Path("/sys/fs/cgroup/memory.max")
LINUX_CGROUP_MEMORY_PEAK = Path("/sys/fs/cgroup/memory.peak")
LINUX_NETWORK_CLASS = Path("/sys/class/net")
LINUX_IPV4_ROUTES = Path("/proc/net/route")
LINUX_IPV6_ROUTES = Path("/proc/net/ipv6_route")


class FinancialMaterializationBenchmarkError(RuntimeError):
    """Report an unavailable guard or invalid benchmark receipt."""


def _root_state(*, repo_root: Path) -> Dict[str, object]:
    """Hash the protected active pointer and three public business artifacts."""
    paths = (
        Path("outputs/active_publication.json"),
        Path("outputs/metrics_matrix.csv"),
        Path("outputs/metric_evidence.csv"),
        Path("REPORT_十公司财务指标.md"),
    )
    return {
        path.as_posix(): {
            "sha256": sha256_file(path=repo_root / path),
            "size": (repo_root / path).stat().st_size,
        }
        for path in paths
    }


def _normalize_peak_rss(*, raw_value: int) -> int:
    """Normalize ru_maxrss to bytes on Darwin and Linux."""
    if raw_value < 0:
        raise FinancialMaterializationBenchmarkError(
            "Peak RSS observation is invalid"
        )
    return raw_value if platform.system() == "Darwin" else raw_value * 1024


def _runtime_identity() -> Dict[str, object]:
    """Return portable interpreter/platform fields for semantic evidence."""
    return {
        "python_executable_name": Path(sys.executable).name,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
    }


def _linux_container_guard_observations() -> Dict[str, object]:
    """Verify the benchmark child is inside the required Linux cgroup/netns."""
    if platform.system() != "Linux":
        raise FinancialMaterializationBenchmarkError(
            "Linux container guard is unavailable"
        )
    try:
        memory_max_text = LINUX_CGROUP_MEMORY_MAX.read_text(
            encoding="utf-8"
        ).strip()
        memory_max = int(memory_max_text)
        memory_peak = int(LINUX_CGROUP_MEMORY_PEAK.read_text(
            encoding="utf-8"
        ).strip())
        interfaces = sorted(path.name for path in LINUX_NETWORK_CLASS.iterdir())
        ipv4_text = LINUX_IPV4_ROUTES.read_text(encoding="utf-8")
        ipv6_text = LINUX_IPV6_ROUTES.read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        raise FinancialMaterializationBenchmarkError(
            "Linux cgroup or network namespace evidence is unavailable"
        ) from error
    if memory_max != RSS_CEILING_BYTES:
        raise FinancialMaterializationBenchmarkError(
            "Linux cgroup memory ceiling differs"
        )
    ipv4_routes = [
        line for line in ipv4_text.splitlines()[1:] if line.strip()
    ]
    ipv6_non_loopback_routes = [
        line for line in ipv6_text.splitlines()
        if line.strip() and line.split()[-1] != "lo"
    ]
    if ipv4_routes or ipv6_non_loopback_routes:
        raise FinancialMaterializationBenchmarkError(
            "Linux benchmark network namespace has a non-loopback route"
        )
    return {
        "cgroup_version": 2,
        "memory_max_bytes": memory_max,
        "memory_peak_bytes": memory_peak,
        "network_interface_names": interfaces,
        "ipv4_route_count": len(ipv4_routes),
        "ipv6_non_loopback_route_count": len(ipv6_non_loopback_routes),
        "ipv4_route_table_sha256": "sha256:" + sha256_bytes(
            content=ipv4_text.encode("utf-8"),
        ),
        "ipv6_route_table_sha256": "sha256:" + sha256_bytes(
            content=ipv6_text.encode("utf-8"),
        ),
        "network_policy": "DOCKER_NETWORK_NONE",
    }


def _production_source_hashes(*, repo_root: Path) -> Dict[str, str]:
    """Bind exact parser, limits, canonicalizer, and benchmark tool bytes."""
    return {
        relative.as_posix(): sha256_file(path=repo_root / relative)
        for relative in (
            TABLE_GRID_RELATIVE,
            RESOURCE_LIMITS_RELATIVE,
            CANONICAL_RELATIVE,
            TOOL_RELATIVE,
        )
    }


def _stage_b_census(*, repo_root: Path) -> Dict[str, object]:
    """Load and recompute the exact Stage-B census identity."""
    receipt = strict_json_file(path=repo_root / STAGE_B_CENSUS_RELATIVE)
    if type(receipt) is not dict or receipt.get("receipt_id") != (
        STAGE_B_CENSUS_RECEIPT_ID
    ):
        raise FinancialMaterializationBenchmarkError(
            "Stage-B census identity differs"
        )
    body = {key: receipt[key] for key in receipt if key != "receipt_id"}
    if content_hash(value=body) != STAGE_B_CENSUS_RECEIPT_ID:
        raise FinancialMaterializationBenchmarkError(
            "Stage-B census bytes differ"
        )
    census = receipt.get("census")
    if (
        type(census) is not dict
        or census.get("exact_table_count") != EXPECTED_TABLE_COUNT
        or census.get("exact_total_rectangular_expanded_cell_count")
        != EXPECTED_RECTANGULAR_CELLS
    ):
        raise FinancialMaterializationBenchmarkError(
            "Stage-B census counts differ"
        )
    return dict(receipt)


def _child_result() -> Dict[str, object]:
    """Materialize and canonically serialize the exact full DerivedAsset."""
    from vnext import resource_limits as production_limits
    from vnext import table_grid
    from vnext.records import validate_record

    linux_guard = (
        _linux_container_guard_observations()
        if platform.system() == "Linux" else None
    )
    source_path = REPO_ROOT / SOURCE_RELATIVE
    source_bytes = source_path.read_bytes()
    if sha256_bytes(content=source_bytes) != SOURCE_SHA256:
        raise FinancialMaterializationBenchmarkError(
            "JPM source bytes differ"
        )
    if production_limits.RESOURCE_LIMITS.max_total_cells != (
        PRODUCTION_MAX_TOTAL_CELLS
    ):
        raise FinancialMaterializationBenchmarkError(
            "Production max_total_cells differs"
        )
    table_grid.RESOURCE_LIMITS = dataclasses.replace(
        production_limits.RESOURCE_LIMITS,
        max_total_cells=TEST_ONLY_MAX_TOTAL_CELLS,
    )
    asset = table_grid.build_table_grid(
        html_bytes=source_bytes,
        parent_raw_asset_ids=["sha256:" + SOURCE_SHA256],
        storage_uri=(
            "artifacts/vnext/table_stage_c_evidence/"
            "financial_materialization_benchmark/derived_asset.json"
        ),
    )
    validate_record(record=asset)
    tables = asset["tables"]
    table_hashes = []
    rectangular_cells = 0
    for order, table in enumerate(tables):
        table_body = {
            key: table[key] for key in table if key != "grid_sha256"
        }
        if (
            table["order"] != order
            or table["grid_sha256"] != content_hash(value=table_body)
        ):
            raise FinancialMaterializationBenchmarkError(
                "Materialized table identity differs"
            )
        rectangular_cells += int(table["row_count"]) * int(
            table["column_count"]
        )
        table_hashes.append({
            "order": order,
            "table_id": table["table_id"],
            "grid_sha256": table["grid_sha256"],
        })
    identity = {
        "parent_raw_asset_ids": asset["parent_raw_asset_ids"],
        "transform_id": asset["transform_id"],
        "transform_semantic_version": asset["transform_semantic_version"],
        "content_type": asset["content_type"],
        "tables": tables,
    }
    if (
        len(tables) != EXPECTED_TABLE_COUNT
        or rectangular_cells != EXPECTED_RECTANGULAR_CELLS
        or asset["derived_asset_id"] != content_hash(value=identity)
    ):
        raise FinancialMaterializationBenchmarkError(
            "Complete materialization counts or DerivedAsset identity differ"
        )
    canonical = canonical_json_bytes(value=asset)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    completed_guard = (
        _linux_container_guard_observations()
        if linux_guard is not None else None
    )
    return {
        "status": "COMPLETED",
        "final_expanded_cells": rectangular_cells,
        "table_count": len(tables),
        "canonical_json_bytes": len(canonical),
        "canonical_json_sha256": "sha256:" + sha256_bytes(content=canonical),
        "derived_asset_id": asset["derived_asset_id"],
        "canonical_serialization_completed": True,
        "table_grid_hashes": table_hashes,
        "table_grid_hash_exact_set_hash": content_hash(value=table_hashes),
        "child_peak_rss_bytes": _normalize_peak_rss(
            raw_value=int(usage.ru_maxrss),
        ),
        "child_user_cpu_seconds": format(Decimal(str(usage.ru_utime)), "f"),
        "child_system_cpu_seconds": format(Decimal(str(usage.ru_stime)), "f"),
        "runtime_identity": _runtime_identity(),
        "linux_guard_observations": completed_guard,
    }


def _set_address_space_limit(*, limit_bytes: int) -> None:
    """Apply a hard child address-space ceiling before exec."""
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _guarded_argv(*, python_arguments: Sequence[str]) -> Sequence[str]:
    """Wrap one child in the OS process-tree network-deny sandbox."""
    return [
        str(SANDBOX_EXECUTABLE),
        "-p",
        NETWORK_DENY_PROFILE,
        sys.executable,
        *python_arguments,
    ]


def _guard_probe() -> Tuple[bool, str]:
    """Prove sandbox and RLIMIT_AS block a sub-512-MiB overflow probe."""
    if (
        platform.system() != "Darwin"
        or not hasattr(resource, "RLIMIT_AS")
        or SANDBOX_EXECUTABLE.is_symlink()
        or not SANDBOX_EXECUTABLE.is_file()
    ):
        return False, "RSS_OR_NETWORK_GUARD_UNAVAILABLE"
    try:
        baseline = subprocess.run(
            _guarded_argv(
                python_arguments=["-c", "print('GUARD_BASELINE_OK')"],
            ),
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            start_new_session=True,
            preexec_fn=lambda: _set_address_space_limit(
                limit_bytes=RSS_CEILING_BYTES,
            ),
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired,
            ValueError):
        return False, "RSS_HARD_LIMIT_SETUP_FAILED"
    if baseline.returncode != 0 or "GUARD_BASELINE_OK" not in baseline.stdout:
        return False, "RSS_GUARD_BASELINE_FAILED"
    probe_limit = 128 * 1024 * 1024
    try:
        probe = subprocess.run(
            _guarded_argv(python_arguments=[
                "-c",
                (
                    "import sys\n"
                    "try:\n"
                    "    bytearray(192 * 1024 * 1024)\n"
                    "except MemoryError:\n"
                    "    sys.exit(0)\n"
                    "sys.exit(9)\n"
                ),
            ]),
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            start_new_session=True,
            preexec_fn=lambda: _set_address_space_limit(
                limit_bytes=probe_limit,
            ),
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired,
            ValueError):
        return False, "RSS_HARD_LIMIT_PROBE_UNAVAILABLE"
    if probe.returncode != 0:
        return False, "RSS_HARD_LIMIT_PROBE_FAILED"
    return True, "RLIMIT_AS_PROBE_AND_SANDBOX_PASS"


def _process_group_rss_bytes(*, process_group_id: int) -> Optional[int]:
    """Return current total RSS for the guarded process group, when observable."""
    completed = subprocess.run(
        ["ps", "-axo", "pgid=,rss="],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    total_kib = 0
    matched = False
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            pgid, rss_kib = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if pgid == process_group_id:
            matched = True
            total_kib += rss_kib
    return total_kib * 1024 if matched else None


def _run_child() -> Dict[str, object]:
    """Run the protected child and return normalized terminal observations."""
    available, guard_status = _guard_probe()
    if not available:
        return {
            "status": "NOT_RUN_RSS_GUARD_UNAVAILABLE",
            "guard_status": guard_status,
            "guard_mechanism": "DARWIN_RLIMIT_AS_SANDBOX_EXEC",
            "container_image_reference": None,
            "exit_code": None,
            "wall_time_seconds": None,
            "user_cpu_seconds": None,
            "system_cpu_seconds": None,
            "peak_rss_bytes": None,
            "cgroup_memory_peak_bytes": None,
            "stdout_sha256": None,
            "stdout_size": 0,
            "stderr_sha256": None,
            "stderr_size": 0,
            "child_result": None,
        }
    started = time.monotonic()
    process = subprocess.Popen(
        _guarded_argv(
            python_arguments=[str(Path(__file__).resolve()), "--child"],
        ),
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        start_new_session=True,
        preexec_fn=lambda: _set_address_space_limit(
            limit_bytes=RSS_CEILING_BYTES,
        ),
    )
    observed_peak = 0
    terminal_override: Optional[str] = None
    deadline = started + WALL_TIME_CEILING_SECONDS
    while process.poll() is None:
        observed = _process_group_rss_bytes(process_group_id=process.pid)
        if observed is not None:
            observed_peak = max(observed_peak, observed)
            if observed > RSS_CEILING_BYTES:
                terminal_override = "KILLED_RSS_LIMIT"
                os.killpg(process.pid, signal.SIGKILL)
                break
        if time.monotonic() >= deadline:
            terminal_override = "KILLED_WALL_TIME_LIMIT"
            os.killpg(process.pid, signal.SIGKILL)
            break
        time.sleep(RSS_POLL_INTERVAL_SECONDS)
    stdout, stderr = process.communicate()
    wall_time = time.monotonic() - started
    stdout_hash = "sha256:" + sha256_bytes(content=stdout)
    stderr_hash = "sha256:" + sha256_bytes(content=stderr)
    child_result = None
    if terminal_override is None and process.returncode == 0:
        try:
            child_result = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            terminal_override = "FAILED_CHILD_OUTPUT"
    if terminal_override is None and process.returncode != 0:
        terminal_override = "FAILED_CHILD"
    status = terminal_override or str(child_result.get("status"))
    child_peak = (
        int(child_result["child_peak_rss_bytes"])
        if type(child_result) is dict
        and type(child_result.get("child_peak_rss_bytes")) is int
        else 0
    )
    peak = max(observed_peak, child_peak)
    if peak > RSS_CEILING_BYTES and status == "COMPLETED":
        status = "FAILED_RSS_OBSERVATION_EXCEEDED"
    return {
        "status": status,
        "guard_status": guard_status,
        "guard_mechanism": "DARWIN_RLIMIT_AS_SANDBOX_EXEC",
        "container_image_reference": None,
        "exit_code": process.returncode,
        "wall_time_seconds": format(Decimal(str(round(wall_time, 6))), "f"),
        "user_cpu_seconds": (
            child_result.get("child_user_cpu_seconds")
            if type(child_result) is dict else None
        ),
        "system_cpu_seconds": (
            child_result.get("child_system_cpu_seconds")
            if type(child_result) is dict else None
        ),
        "peak_rss_bytes": peak,
        "cgroup_memory_peak_bytes": None,
        "stdout_sha256": stdout_hash,
        "stdout_size": len(stdout),
        "stderr_sha256": stderr_hash,
        "stderr_size": len(stderr),
        "child_result": child_result,
    }


def _docker_executable() -> str:
    """Return the installed Docker CLI without permitting an override."""
    executable = shutil.which("docker")
    if executable is None:
        raise FinancialMaterializationBenchmarkError(
            "Docker CLI is unavailable"
        )
    return executable


def _verify_docker_linux_runtime(*, executable: str) -> None:
    """Require one local Linux daemon and the already-pulled pinned image."""
    version = subprocess.run(
        [
            executable,
            "version",
            "--format",
            "{{.Server.Os}}|{{.Server.Arch}}|{{.Server.Version}}",
        ],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    fields = version.stdout.strip().split("|")
    if version.returncode != 0 or len(fields) != 3 or fields[0] != "linux":
        raise FinancialMaterializationBenchmarkError(
            "Docker Linux daemon is unavailable"
        )
    image = subprocess.run(
        [executable, "image", "inspect", DOCKER_LINUX_IMAGE],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if image.returncode != 0:
        raise FinancialMaterializationBenchmarkError(
            "Pinned Docker Linux image is unavailable"
        )


def _docker_container_state(
    *, executable: str, container_name: str,
) -> Tuple[bool, Optional[int]]:
    """Read OOM and exit observations before removing the exact container."""
    state = subprocess.run(
        [
            executable,
            "inspect",
            "--format",
            "{{.State.OOMKilled}}|{{.State.ExitCode}}",
            container_name,
        ],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if state.returncode != 0:
        return False, None
    fields = state.stdout.strip().split("|")
    if len(fields) != 2:
        return False, None
    try:
        return fields[0].lower() == "true", int(fields[1])
    except ValueError:
        return False, None


def _docker_argv(
    *, executable: str, container_name: str,
) -> Sequence[str]:
    """Build the fixed read-only, networkless, hard-memory Linux command."""
    return [
        executable,
        "run",
        "--name",
        container_name,
        "--network=none",
        "--memory={}".format(RSS_CEILING_BYTES),
        "--memory-swap={}".format(RSS_CEILING_BYTES),
        "--pids-limit=64",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--read-only",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=16777216",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--mount=type=bind,src={},dst={},readonly".format(
            REPO_ROOT, DOCKER_WORKDIR,
        ),
        "--workdir={}".format(DOCKER_WORKDIR),
        DOCKER_LINUX_IMAGE,
        "python3",
        str(Path(DOCKER_WORKDIR) / TOOL_RELATIVE),
        "--child",
    ]


def _run_docker_linux_child() -> Dict[str, object]:
    """Run the exact child in a networkless 512-MiB Linux cgroup."""
    executable = _docker_executable()
    _verify_docker_linux_runtime(executable=executable)
    container_name = "secmetrics-jpm-benchmark-{}-{}".format(
        os.getpid(), time.monotonic_ns(),
    )
    argv = _docker_argv(
        executable=executable, container_name=container_name,
    )
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        start_new_session=True,
    )
    terminal_override: Optional[str] = None
    try:
        stdout, stderr = process.communicate(
            timeout=WALL_TIME_CEILING_SECONDS,
        )
    except subprocess.TimeoutExpired:
        terminal_override = "KILLED_WALL_TIME_LIMIT"
        subprocess.run(
            [executable, "kill", container_name],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            timeout=15,
        )
        stdout, stderr = process.communicate(timeout=15)
    wall_time = time.monotonic() - started
    oom_killed, container_exit = _docker_container_state(
        executable=executable,
        container_name=container_name,
    )
    subprocess.run(
        [executable, "rm", "-f", container_name],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        timeout=15,
    )
    child_result = None
    if terminal_override is None and process.returncode == 0:
        try:
            child_result = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            terminal_override = "FAILED_CHILD_OUTPUT"
    if terminal_override is None and oom_killed:
        terminal_override = "KILLED_RSS_LIMIT"
    if terminal_override is None and process.returncode != 0:
        terminal_override = "FAILED_CHILD"
    if (
        terminal_override is None
        and type(child_result) is dict
        and child_result.get("status") == "COMPLETED"
    ):
        guard = child_result.get("linux_guard_observations")
        if (
            type(guard) is not dict
            or guard.get("memory_max_bytes") != RSS_CEILING_BYTES
            or guard.get("network_policy") != "DOCKER_NETWORK_NONE"
            or guard.get("ipv4_route_count") != 0
            or guard.get("ipv6_non_loopback_route_count") != 0
        ):
            terminal_override = "FAILED_LINUX_GUARD_OBSERVATION"
    status = terminal_override or (
        str(child_result.get("status"))
        if type(child_result) is dict else "FAILED_CHILD"
    )
    child_peak = (
        int(child_result["child_peak_rss_bytes"])
        if type(child_result) is dict
        and type(child_result.get("child_peak_rss_bytes")) is int
        else 0
    )
    guard = (
        child_result.get("linux_guard_observations", {})
        if type(child_result) is dict else {}
    )
    cgroup_peak = (
        int(guard["memory_peak_bytes"])
        if type(guard) is dict
        and type(guard.get("memory_peak_bytes")) is int
        else None
    )
    return {
        "status": status,
        "guard_status": "LINUX_CGROUP_V2_AND_NETWORK_NONE_PASS",
        "guard_mechanism": "DOCKER_CGROUP_V2_NETWORK_NONE",
        "container_image_reference": DOCKER_LINUX_IMAGE,
        "exit_code": (
            container_exit if container_exit is not None else process.returncode
        ),
        "wall_time_seconds": format(
            Decimal(str(round(wall_time, 6))), "f",
        ),
        "user_cpu_seconds": (
            child_result.get("child_user_cpu_seconds")
            if type(child_result) is dict else None
        ),
        "system_cpu_seconds": (
            child_result.get("child_system_cpu_seconds")
            if type(child_result) is dict else None
        ),
        "peak_rss_bytes": child_peak,
        "cgroup_memory_peak_bytes": cgroup_peak,
        "stdout_sha256": "sha256:" + sha256_bytes(content=stdout),
        "stdout_size": len(stdout),
        "stderr_sha256": "sha256:" + sha256_bytes(content=stderr),
        "stderr_size": len(stderr),
        "child_result": child_result,
    }


def _semantic_receipt(
    *,
    repo_root: Path,
    terminal: Mapping[str, object],
    root_before: Mapping[str, object],
    root_after: Mapping[str, object],
    sources_before: Mapping[str, str],
    sources_after: Mapping[str, str],
) -> Dict[str, object]:
    """Build the stable result identity without timing, PID, or temp locators."""
    census = _stage_b_census(repo_root=repo_root)
    child = terminal.get("child_result")
    materialized = child if type(child) is dict else {}
    body = {
        "schema_version": 1,
        "record_type": "TABLE_STAGE_C_FINANCIAL_MATERIALIZATION_BENCHMARK",
        "status": terminal["status"],
        "source": {
            "repo_relative_path": SOURCE_RELATIVE.as_posix(),
            "sha256": SOURCE_SHA256,
            "size": (repo_root / SOURCE_RELATIVE).stat().st_size,
        },
        "stage_b_census_binding": {
            "receipt_id": STAGE_B_CENSUS_RECEIPT_ID,
            "exact_table_count": census["census"]["exact_table_count"],
            "exact_total_rectangular_expanded_cell_count": census[
                "census"
            ]["exact_total_rectangular_expanded_cell_count"],
        },
        "runtime_identity": materialized.get(
            "runtime_identity", _runtime_identity(),
        ),
        "production_source_code_hashes": dict(sources_after),
        "test_only_override": {
            "field": "max_total_cells",
            "value": TEST_ONLY_MAX_TOTAL_CELLS,
            "scope": "BENCHMARK_CHILD_PROCESS_ONLY",
        },
        "production_resource_policy": {
            "max_total_cells": PRODUCTION_MAX_TOTAL_CELLS,
            "resource_limits_sha256_before": sources_before[
                RESOURCE_LIMITS_RELATIVE.as_posix()
            ],
            "resource_limits_sha256_after": sources_after[
                RESOURCE_LIMITS_RELATIVE.as_posix()
            ],
            "unchanged": sources_before == sources_after,
        },
        "safety_ceilings": {
            "hard_address_space_and_peak_rss_ceiling_bytes": RSS_CEILING_BYTES,
            "hard_memory_ceiling_bytes": RSS_CEILING_BYTES,
            "hard_wall_time_ceiling_seconds": WALL_TIME_CEILING_SECONDS,
            "guard_status": terminal["guard_status"],
            "guard_mechanism": terminal["guard_mechanism"],
            "cgroup_memory_peak_bytes": terminal[
                "cgroup_memory_peak_bytes"
            ],
        },
        "no_network_proof": {
            "sandbox_executable": (
                "docker"
                if terminal["guard_mechanism"]
                == "DOCKER_CGROUP_V2_NETWORK_NONE"
                else SANDBOX_EXECUTABLE.as_posix()
            ),
            "profile_sha256": "sha256:" + sha256_bytes(
                content=(
                    "--network=none"
                    if terminal["guard_mechanism"]
                    == "DOCKER_CGROUP_V2_NETWORK_NONE"
                    else NETWORK_DENY_PROFILE
                ).encode("utf-8"),
            ),
            "policy": (
                "DOCKER_NETWORK_NONE"
                if terminal["guard_mechanism"]
                == "DOCKER_CGROUP_V2_NETWORK_NONE"
                else "DENY_NETWORK_STAR_PROCESS_TREE"
            ),
            "container_image_reference": terminal[
                "container_image_reference"
            ],
            "network_interface_names": (
                materialized.get("linux_guard_observations", {}).get(
                    "network_interface_names"
                )
                if type(materialized.get("linux_guard_observations")) is dict
                else None
            ),
            "ipv4_route_count": (
                materialized.get("linux_guard_observations", {}).get(
                    "ipv4_route_count"
                )
                if type(materialized.get("linux_guard_observations")) is dict
                else None
            ),
            "ipv6_non_loopback_route_count": (
                materialized.get("linux_guard_observations", {}).get(
                    "ipv6_non_loopback_route_count"
                )
                if type(materialized.get("linux_guard_observations")) is dict
                else None
            ),
            "benchmark_child_started": terminal["status"]
            != "NOT_RUN_RSS_GUARD_UNAVAILABLE",
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_SEC_egress_count": 0,
        },
        "materialization": {
            "completed": terminal["status"] == "COMPLETED",
            "final_expanded_cells": materialized.get("final_expanded_cells"),
            "table_count": materialized.get("table_count"),
            "canonical_json_bytes": materialized.get("canonical_json_bytes"),
            "canonical_json_sha256": materialized.get("canonical_json_sha256"),
            "derived_asset_id": materialized.get("derived_asset_id"),
            "canonical_serialization_completed": materialized.get(
                "canonical_serialization_completed", False,
            ),
            "table_grid_hashes": materialized.get("table_grid_hashes", []),
            "table_grid_hash_exact_set_hash": materialized.get(
                "table_grid_hash_exact_set_hash"
            ),
        },
        "root_business_artifacts_before": dict(root_before),
        "root_business_artifacts_after": dict(root_after),
        "root_business_artifacts_byte_equal": root_before == root_after,
    }
    if (
        sources_before != sources_after
        or root_before != root_after
        or body["production_resource_policy"]["unchanged"] is not True
    ):
        raise FinancialMaterializationBenchmarkError(
            "Benchmark changed production or root authority bytes"
        )
    if terminal["status"] == "COMPLETED" and (
        materialized.get("final_expanded_cells") != EXPECTED_RECTANGULAR_CELLS
        or materialized.get("table_count") != EXPECTED_TABLE_COUNT
        or materialized.get("canonical_serialization_completed") is not True
        or len(materialized.get("table_grid_hashes", []))
        != EXPECTED_TABLE_COUNT
        or (
            terminal["guard_mechanism"]
            == "DOCKER_CGROUP_V2_NETWORK_NONE"
            and (
                materialized.get("runtime_identity", {}).get(
                    "platform_system"
                ) != "Linux"
                or terminal["cgroup_memory_peak_bytes"] is None
                or terminal["cgroup_memory_peak_bytes"]
                > RSS_CEILING_BYTES
                or body["no_network_proof"]["ipv4_route_count"] != 0
                or body["no_network_proof"][
                    "ipv6_non_loopback_route_count"
                ] != 0
            )
        )
    ):
        raise FinancialMaterializationBenchmarkError(
            "Completed benchmark result differs from the exact census"
        )
    return {**body, "benchmark_receipt_id": content_hash(value=body)}


def _run_receipt(
    *, semantic: Mapping[str, object], terminal: Mapping[str, object],
) -> Dict[str, object]:
    """Build a separate observation identity for time, CPU, RSS, and rc."""
    body = {
        "schema_version": 1,
        "record_type": "TABLE_STAGE_C_FINANCIAL_MATERIALIZATION_RUN",
        "benchmark_receipt_id": semantic["benchmark_receipt_id"],
        "status": terminal["status"],
        "exit_code": terminal["exit_code"],
        "wall_time_seconds": terminal["wall_time_seconds"],
        "user_cpu_seconds": terminal["user_cpu_seconds"],
        "system_cpu_seconds": terminal["system_cpu_seconds"],
        "peak_rss_bytes": terminal["peak_rss_bytes"],
        "cgroup_memory_peak_bytes": terminal["cgroup_memory_peak_bytes"],
        "rss_ceiling_bytes": RSS_CEILING_BYTES,
        "wall_time_ceiling_seconds": WALL_TIME_CEILING_SECONDS,
        "stdout_sha256": terminal["stdout_sha256"],
        "stdout_size": terminal["stdout_size"],
        "stderr_sha256": terminal["stderr_sha256"],
        "stderr_size": terminal["stderr_size"],
    }
    return {**body, "run_receipt_id": content_hash(value=body)}


def _write_receipts(
    *, repo_root: Path, semantic: Mapping[str, object], run: Mapping[str, object],
) -> Dict[str, object]:
    """Persist semantic/run receipts and a content-bound current pointer."""
    semantic_digest = str(semantic["benchmark_receipt_id"]).split(
        ":", maxsplit=1,
    )[1]
    run_digest = str(run["run_receipt_id"]).split(":", maxsplit=1)[1]
    semantic_relative = SEMANTIC_ROOT / (semantic_digest + ".json")
    run_relative = RUN_ROOT / (run_digest + ".json")
    atomic_write_json(path=repo_root / semantic_relative, value=semantic)
    atomic_write_json(path=repo_root / run_relative, value=run)
    pointer_body = {
        "schema_version": 1,
        "record_type": "TABLE_STAGE_C_FINANCIAL_MATERIALIZATION_POINTER",
        "benchmark_receipt_id": semantic["benchmark_receipt_id"],
        "benchmark_receipt_path": semantic_relative.as_posix(),
        "run_receipt_id": run["run_receipt_id"],
        "run_receipt_path": run_relative.as_posix(),
    }
    pointer = {**pointer_body, "pointer_id": content_hash(value=pointer_body)}
    atomic_write_json(path=repo_root / CURRENT_POINTER, value=pointer)
    return pointer


def run_benchmark(
    *, repo_root: Path, docker_linux: bool = False,
) -> Dict[str, object]:
    """Run once under hard guards and persist honest terminal evidence."""
    source = repo_root / SOURCE_RELATIVE
    if source.is_symlink() or not source.is_file():
        raise FinancialMaterializationBenchmarkError("JPM source is unavailable")
    if sha256_file(path=source) != SOURCE_SHA256:
        raise FinancialMaterializationBenchmarkError("JPM source hash differs")
    _stage_b_census(repo_root=repo_root)
    root_before = _root_state(repo_root=repo_root)
    sources_before = _production_source_hashes(repo_root=repo_root)
    terminal = (
        _run_docker_linux_child() if docker_linux else _run_child()
    )
    sources_after = _production_source_hashes(repo_root=repo_root)
    root_after = _root_state(repo_root=repo_root)
    semantic = _semantic_receipt(
        repo_root=repo_root,
        terminal=terminal,
        root_before=root_before,
        root_after=root_after,
        sources_before=sources_before,
        sources_after=sources_after,
    )
    run = _run_receipt(semantic=semantic, terminal=terminal)
    pointer = _write_receipts(repo_root=repo_root, semantic=semantic, run=run)
    return {
        "status": semantic["status"],
        "benchmark_receipt_id": semantic["benchmark_receipt_id"],
        "run_receipt_id": run["run_receipt_id"],
        "pointer_id": pointer["pointer_id"],
        "peak_rss_bytes": run["peak_rss_bytes"],
        "cgroup_memory_peak_bytes": run["cgroup_memory_peak_bytes"],
        "wall_time_seconds": run["wall_time_seconds"],
        "canonical_json_bytes": semantic["materialization"][
            "canonical_json_bytes"
        ],
        "derived_asset_id": semantic["materialization"]["derived_asset_id"],
    }


def validate_current_receipts(*, repo_root: Path) -> Dict[str, object]:
    """Recompute current pointer, semantic receipt, and run receipt identities."""
    pointer = strict_json_file(path=repo_root / CURRENT_POINTER)
    if type(pointer) is not dict:
        raise FinancialMaterializationBenchmarkError(
            "Benchmark pointer is invalid"
        )
    pointer_body = {key: pointer[key] for key in pointer if key != "pointer_id"}
    if pointer.get("pointer_id") != content_hash(value=pointer_body):
        raise FinancialMaterializationBenchmarkError(
            "Benchmark pointer identity differs"
        )
    semantic = strict_json_file(
        path=repo_root / Path(str(pointer["benchmark_receipt_path"])),
    )
    run = strict_json_file(
        path=repo_root / Path(str(pointer["run_receipt_path"])),
    )
    if type(semantic) is not dict or type(run) is not dict:
        raise FinancialMaterializationBenchmarkError(
            "Benchmark receipt root is invalid"
        )
    semantic_body = {
        key: semantic[key] for key in semantic if key != "benchmark_receipt_id"
    }
    run_body = {key: run[key] for key in run if key != "run_receipt_id"}
    current_sources = _production_source_hashes(repo_root=repo_root)
    recorded_sources = semantic["production_source_code_hashes"]
    if type(recorded_sources) is not dict:
        raise FinancialMaterializationBenchmarkError(
            "Benchmark source binding is invalid"
        )
    source_binding_valid = current_sources == recorded_sources
    if not source_binding_valid:
        from vnext.requirements import load_requirement_snapshot
        from vnext.resource_limits import RESOURCE_LIMITS

        requirement = load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements/issue_15_v1",
        )
        policy = requirement["effective_decisions"]["D-35"]["choice"].get(
            "financial_materialization_resource_policy"
        )
        layout_policy = requirement["effective_decisions"]["D-35"][
            "choice"
        ].get("financial_layout_source_materialization_policy")
        if type(policy) is dict and type(layout_policy) is dict:
            benchmark_commit = str(policy.get("benchmark_source_commit", ""))
            tree = subprocess.run(
                ["git", "rev-parse", benchmark_commit + "^{tree}"],
                cwd=str(repo_root),
                check=False,
                capture_output=True,
                text=True,
            )
            git_hashes = {}
            for relative in recorded_sources:
                blob = subprocess.run(
                    ["git", "show", benchmark_commit + ":" + relative],
                    cwd=str(repo_root),
                    check=False,
                    capture_output=True,
                )
                if blob.returncode == 0:
                    git_hashes[relative] = sha256_bytes(content=blob.stdout)
            changed = {
                relative for relative in recorded_sources
                if current_sources.get(relative) != recorded_sources[relative]
            }
            source_binding_valid = (
                tree.returncode == 0
                and tree.stdout.strip() == policy.get("benchmark_source_tree")
                and git_hashes == recorded_sources
                and changed == {
                    RESOURCE_LIMITS_RELATIVE.as_posix(),
                    TOOL_RELATIVE.as_posix(),
                }
                and policy.get("benchmark_receipt_id")
                == semantic.get("benchmark_receipt_id")
                and policy.get("run_receipt_id") == run.get("run_receipt_id")
                and policy.get("production_max_total_cells_before")
                == semantic["production_resource_policy"]["max_total_cells"]
                and policy.get("production_max_total_cells_after")
                == layout_policy.get("production_max_total_cells_before")
                and layout_policy.get("production_max_total_cells_after")
                == RESOURCE_LIMITS.max_total_cells
                and layout_policy.get(
                    "maximum_current_source_expanded_cell_count"
                ) == RESOURCE_LIMITS.max_total_cells
                and layout_policy.get("local_materialization_shards_selected")
                is False
                and layout_policy.get(
                    "provider_request_shard_policy_unchanged"
                ) is True
            )
    if (
        semantic.get("benchmark_receipt_id") != content_hash(value=semantic_body)
        or run.get("run_receipt_id") != content_hash(value=run_body)
        or pointer["benchmark_receipt_id"] != semantic["benchmark_receipt_id"]
        or pointer["run_receipt_id"] != run["run_receipt_id"]
        or semantic["stage_b_census_binding"]["receipt_id"]
        != STAGE_B_CENSUS_RECEIPT_ID
        or not source_binding_valid
        or semantic["root_business_artifacts_before"]
        != semantic["root_business_artifacts_after"]
        or semantic["root_business_artifacts_after"]
        != _root_state(repo_root=repo_root)
    ):
        raise FinancialMaterializationBenchmarkError(
            "Benchmark receipt binding differs"
        )
    return {
        "status": semantic["status"],
        "benchmark_receipt_id": semantic["benchmark_receipt_id"],
        "run_receipt_id": run["run_receipt_id"],
        "peak_rss_bytes": run["peak_rss_bytes"],
        "cgroup_memory_peak_bytes": run.get("cgroup_memory_peak_bytes"),
        "wall_time_seconds": run["wall_time_seconds"],
        "canonical_json_bytes": semantic["materialization"][
            "canonical_json_bytes"
        ],
        "derived_asset_id": semantic["materialization"]["derived_asset_id"],
    }


def main(*, argv: Sequence[str]) -> int:
    """Run parent benchmark, validate receipts, or execute the guarded child."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--docker-linux", action="store_true")
    parser.add_argument("--validate", action="store_true")
    arguments = parser.parse_args(list(argv))
    if sum((arguments.child, arguments.docker_linux, arguments.validate)) > 1:
        parser.error(
            "--child, --docker-linux, and --validate are mutually exclusive"
        )
    try:
        if arguments.child:
            print(json.dumps(
                _child_result(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ))
            return 0
        result = (
            validate_current_receipts(repo_root=REPO_ROOT)
            if arguments.validate
            else run_benchmark(
                repo_root=REPO_ROOT,
                docker_linux=arguments.docker_linux,
            )
        )
    except (FinancialMaterializationBenchmarkError, OSError, ValueError) as error:
        print(json.dumps(
            {"status": "FAILED", "error": str(error)},
            ensure_ascii=False,
            sort_keys=True,
        ))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if arguments.validate:
        return 0
    return 0 if result["status"] == "COMPLETED" else 3


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
