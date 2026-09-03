"""Guarded, offline-only complete table materialization for R4 research.

The historical parser and production resource policy are not modified. A
separate network-none, read-only Linux worker uses the *same* parser with an
explicit bounded research ceiling; that ceiling is not live readiness or a
production resource grant. No asset is persisted or shared between sessions.
"""

from __future__ import annotations

import json
from pathlib import Path
import platform
import re
import resource
import subprocess
import time
from typing import Dict, Mapping
import uuid

from .canonical import sha256_bytes, strict_json_loads
from .records import validate_record
from .sources import resolve_repository_file


PINNED_IMAGE_ID = "sha256:6bb4a52297019add65df37d3abcd37819ea4e247adeaff276d03343b05b94b17"
OFFLINE_MAX_TOTAL_CELLS = 250000
MEMORY_CEILING_BYTES = 512 * 1024 * 1024
WALL_CEILING_SECONDS = 120
WORKER_PATH = "tools/r4_materialization_worker.py"
MATERIALIZATION_CODE_PATHS = (
    "scripts/vnext/table_grid.py", "scripts/vnext/resource_limits.py",
    "scripts/vnext/records.py", "scripts/vnext/canonical.py",
    "scripts/vnext/offline_execution_session.py", "scripts/vnext/r4_materialization.py",
    WORKER_PATH,
)


class OfflineMaterializationError(RuntimeError):
    """A resource, identity or process-isolation boundary did not pass."""


def materialize_full_source(
    *, repo_root: Path, source_path: str, source_sha256: str, source_size: int,
) -> Dict[str, object]:
    """Return a complete native DerivedAsset and actual bounded-worker data.

    Only a local, already-present pinned image can be used. There is no pull,
    provider transport, source acquisition, fallback, caller cell cap, or
    persistent cache. Source bytes are rechecked after the worker completes.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256) or type(source_size) is not int or source_size < 1:
        raise OfflineMaterializationError("Exact source SHA and size are required")
    root = repo_root.resolve(strict=True)
    source = resolve_repository_file(repo_root=root, repo_relative_path=source_path)
    raw = source.read_bytes()
    if len(raw) != source_size or sha256_bytes(content=raw) != source_sha256:
        raise OfflineMaterializationError("Offline source path/hash/size differs")
    worker = resolve_repository_file(repo_root=root, repo_relative_path=WORKER_PATH)
    code_hashes = {
        relative: sha256_bytes(content=resolve_repository_file(
            repo_root=root, repo_relative_path=relative,
        ).read_bytes())
        for relative in MATERIALIZATION_CODE_PATHS
    }
    inspected = subprocess.run(
        ["docker", "image", "inspect", PINNED_IMAGE_ID, "--format", "{{.Id}}"],
        capture_output=True, text=True, check=False, timeout=15,
    )
    if inspected.returncode or inspected.stdout.strip() != PINNED_IMAGE_ID:
        raise OfflineMaterializationError("Pinned local offline worker image is unavailable; no pull is allowed")
    name = "secmetrics-r4-materialize-" + uuid.uuid4().hex
    argv = [
        "docker", "run", "--pull=never", "--rm", "--name", name,
        "--network", "none", "--memory", str(MEMORY_CEILING_BYTES),
        "--memory-swap", str(MEMORY_CEILING_BYTES), "--pids-limit", "32",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--mount", "type=bind,source=" + str(root) + ",target=/repo,readonly",
        "--workdir", "/repo", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONPATH=/repo/scripts", PINNED_IMAGE_ID,
        "python3", WORKER_PATH, "--source", source_path,
        "--sha256", source_sha256, "--size", str(source_size),
    ]
    started = time.perf_counter()
    try:
        child = subprocess.run(argv, capture_output=True, timeout=WALL_CEILING_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=False, timeout=15)
        raise OfflineMaterializationError("Offline materializer wall/process guard failed") from error
    if child.returncode:
        raise OfflineMaterializationError(
            "Offline materializer failed (rc=" + str(child.returncode) + "): "
            + child.stderr.decode("utf-8", errors="replace")[-4000:]
        )
    try:
        report = json.loads(child.stderr.decode("utf-8"))
        asset = strict_json_loads(text=child.stdout.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise OfflineMaterializationError("Offline worker output is not exact JSON") from error
    if not isinstance(asset, dict) or not isinstance(report, dict):
        raise OfflineMaterializationError("Offline worker roots are not objects")
    validate_record(record=asset)
    if (
        report.get("status") != "PASSED_OFFLINE_ONLY"
        or report.get("source_sha256") != source_sha256
        or report.get("source_size") != source_size
        or report.get("derived_asset_id") != asset["derived_asset_id"]
        or report.get("canonical_asset_sha256") != sha256_bytes(content=child.stdout)
        or report.get("canonical_asset_size") != len(child.stdout)
        or report.get("provider_paid_sec_calls") != [0, 0, 0]
        or report.get("code_sha256") != code_hashes
        or report.get("guard", {}).get("memory_max_bytes") != MEMORY_CEILING_BYTES
        or report.get("guard", {}).get("non_loopback_active_interfaces") != []
        or report.get("guard", {}).get("ipv4_routes") != []
        or report.get("guard", {}).get("memory_swap_max_bytes") != 0
        or report.get("guard", {}).get("root_mount_read_only") is not True
    ):
        raise OfflineMaterializationError("Offline worker identity/guard differs")
    if resolve_repository_file(repo_root=root, repo_relative_path=source_path).read_bytes() != raw:
        raise OfflineMaterializationError("Source changed during offline materialization")
    if any(
        sha256_bytes(content=resolve_repository_file(repo_root=root, repo_relative_path=path).read_bytes()) != digest
        for path, digest in code_hashes.items()
    ):
        raise OfflineMaterializationError("Parser/worker source changed during offline materialization")
    report["host_wall_seconds"] = format(time.perf_counter() - started, ".6f")
    host_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["host_process_peak_rss_bytes"] = host_peak if platform.system() == "Darwin" else host_peak * 1024
    report["image_id"] = PINNED_IMAGE_ID
    report["worker_sha256"] = sha256_bytes(content=worker.read_bytes())
    return {"asset": asset, "asset_bytes": child.stdout, "report": report}


def offline_asset_summary(*, asset: Mapping[str, object]) -> Dict[str, object]:
    """Small reproducible identity/census summary, never a filtered asset."""
    tables = asset["tables"]
    return {
        "derived_asset_id": asset["derived_asset_id"],
        "table_count": len(tables),
        "expanded_cells": sum(int(t["row_count"]) * int(t["column_count"]) for t in tables),
        "ordered_tables": [
            {"order": t["order"], "table_id": t["table_id"], "grid_sha256": t["grid_sha256"]}
            for t in tables
        ],
    }
