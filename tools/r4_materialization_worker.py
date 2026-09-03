#!/usr/bin/env python3
"""One hard-guarded offline parser process; stdout is the entire native asset."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
import platform
import resource
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.canonical import canonical_json_bytes, sha256_bytes  # noqa: E402
from vnext.r4_materialization import MEMORY_CEILING_BYTES, OFFLINE_MAX_TOTAL_CELLS  # noqa: E402
from vnext.r4_materialization import MATERIALIZATION_CODE_PATHS  # noqa: E402
from vnext.r4_materialization import offline_asset_summary  # noqa: E402
from vnext.offline_execution_session import OfflineOperationObserver  # noqa: E402
from vnext.sources import resolve_repository_file  # noqa: E402


def _guard() -> dict:
    if platform.system() != "Linux":
        raise RuntimeError("Offline research cell ceiling requires guarded Linux worker")
    root_flags = [row.split()[3].split(",") for row in Path("/proc/mounts").read_text().splitlines() if row.split()[1] == "/"]
    interfaces = [path for path in Path("/sys/class/net").iterdir() if (path / "operstate").is_file()]
    guard = {
        "memory_max_bytes": int(Path("/sys/fs/cgroup/memory.max").read_text()),
        "memory_swap_max_bytes": int(Path("/sys/fs/cgroup/memory.swap.max").read_text()),
        "network_interfaces": sorted(path.name for path in interfaces),
        "non_loopback_active_interfaces": sorted(
            path.name for path in interfaces
            if path.name != "lo" and (path / "operstate").read_text().strip() != "down"
        ),
        "ipv4_routes": Path("/proc/net/route").read_text().splitlines()[1:],
        "root_mount_read_only": len(root_flags) == 1 and "ro" in root_flags[0],
    }
    if (
        guard["memory_max_bytes"] != MEMORY_CEILING_BYTES
        or guard["memory_swap_max_bytes"] != 0
        or guard["non_loopback_active_interfaces"] != []
        or guard["ipv4_routes"] != []
        or "lo" not in guard["network_interfaces"]
        or guard["root_mount_read_only"] is not True
    ):
        raise RuntimeError("Required cgroup/read-only/network-none guards are absent")
    return guard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--size", required=True, type=int)
    args = parser.parse_args()
    guard = _guard()
    source = resolve_repository_file(repo_root=ROOT, repo_relative_path=args.source)
    raw = source.read_bytes()
    if len(raw) != args.size or sha256_bytes(content=raw) != args.sha256:
        raise RuntimeError("Exact immutable source identity differs")
    from vnext import table_grid
    from vnext.resource_limits import RESOURCE_LIMITS
    # This assignment exists only inside the guarded one-shot process. The
    # production object is immutable and no caller may choose a larger cap.
    table_grid.RESOURCE_LIMITS = dataclasses.replace(RESOURCE_LIMITS, max_total_cells=OFFLINE_MAX_TOTAL_CELLS)
    started = time.perf_counter()
    with OfflineOperationObserver() as observed:
        asset = table_grid.build_table_grid(
            html_bytes=raw, parent_raw_asset_ids=["sha256:" + args.sha256],
            storage_uri="offline://full-derived-asset/" + args.sha256,
        )
        data = canonical_json_bytes(value=asset)
    report = {
        "status": "PASSED_OFFLINE_ONLY", "source_sha256": args.sha256, "source_size": args.size,
        **offline_asset_summary(asset=asset),
        "canonical_asset_sha256": sha256_bytes(content=data), "canonical_asset_size": len(data),
        "guard": guard, "cgroup_memory_peak_bytes": int(Path("/sys/fs/cgroup/memory.peak").read_text()),
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "wall_seconds": format(time.perf_counter() - started, ".6f"),
        "interpreter": {"implementation": platform.python_implementation(), "version": platform.python_version()},
        "production_max_total_cells": RESOURCE_LIMITS.max_total_cells,
        "offline_worker_max_total_cells": OFFLINE_MAX_TOTAL_CELLS,
        "source_materializations": 1, "derived_asset_builds": 1,
        "observed_operation_counts": dict(observed.counts),
        "instrumentation_backend": observed.instrumentation_backend,
        "provider_paid_sec_calls": [0, 0, 0], "qualification_credit": "NONE",
        "code_sha256": {
            relative: sha256_bytes(content=resolve_repository_file(
                repo_root=ROOT, repo_relative_path=relative,
            ).read_bytes()) for relative in MATERIALIZATION_CODE_PATHS
        },
    }
    sys.stdout.buffer.write(data)
    sys.stderr.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
