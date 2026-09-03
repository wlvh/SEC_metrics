#!/usr/bin/env python3
"""Reproduce guarded R4 materialization data and prior-terminal inventory.

Materialization is not the aggregate session benchmark. Until all six tasks
have auto-certified positives, this tool deliberately records the >=10x and
final independent R4 replay gates as NOT_RUN rather than benchmarking a
different/synthetic workload and claiming R4 performance acceptance.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.canonical import atomic_write_json, content_hash, sha256_bytes  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402
from vnext.r4_materialization import materialize_full_source  # noqa: E402
from vnext.records import validate_record  # noqa: E402
from vnext.sources import resolve_repository_file  # noqa: E402


def prior_terminal_inventory(*, repo_root: Path) -> dict:
    """Inventory existing base Runs; do not promote inventory to replay PASS."""
    cycles = defaultdict(list)
    root = repo_root / "artifacts/vnext/qualification/cycles"
    for path in sorted(root.glob("*/runs/*/manifest.json")):
        relative = path.relative_to(repo_root).as_posix()
        regular = resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)
        manifest = strict_json_file(path=regular)
        validate_record(record=manifest)
        if manifest["status"] == "FROZEN":
            body = regular.read_bytes()
            cycles[path.parents[2].name].append({
                "run_id": manifest["run_id"], "manifest_path": relative,
                "manifest_sha256": sha256_bytes(content=body), "manifest_size": len(body),
                "content_manifest_hash": manifest["content_manifest_hash"],
                "audit_manifest_hash": manifest["audit_manifest_hash"],
                "status": "FROZEN", "replay_status": "NOT_RUN_INVENTORY_ONLY",
            })
    if not cycles:
        raise RuntimeError("No FROZEN prior Runs are available for the baseline inventory")
    selected_cycle, selected = sorted(cycles.items(), key=lambda pair: (-len(pair[1]), pair[0]))[0]
    if len(selected) < 6:
        raise RuntimeError("At least six distinct terminal Runs are required for the baseline")
    return {
        "frozen_run_count": sum(len(rows) for rows in cycles.values()),
        "selected_cycle_id": "sha256:" + selected_cycle,
        "selected_run_count": 6, "selected_runs": selected[:6],
        "purpose": "PERFORMANCE_INPUT_ONLY; no current or successor qualification credit",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve(strict=False)
    try:
        relative = output.relative_to(ROOT)
    except ValueError:
        relative = None
    if relative is not None and not relative.as_posix().startswith("docs/r4_offline/performance"):
        raise RuntimeError("Benchmark output must not overwrite runtime or authority paths")
    result = materialize_full_source(
        repo_root=ROOT, source_path=args.source,
        source_sha256=args.sha256, source_size=args.size,
    )
    report = dict(result["report"])
    ordered = report.pop("ordered_tables")
    report["ordered_table_grid_exact_set_hash"] = content_hash(value=ordered)
    body = {
        "record_type": "R4_OFFLINE_MATERIALIZATION_EXPLORATION", "schema_version": 1,
        "generator_sha256": sha256_bytes(content=Path(__file__).read_bytes()),
        "source_path": args.source, "materialization": report,
        "prior_terminal_inventory": prior_terminal_inventory(repo_root=ROOT),
        "aggregate_performance_benchmark": "NOT_RUN_PENDING_AUTO_CERTIFIED_SIX_TASK_WORKLOAD",
        "minimum_10x_gate": "NOT_RUN", "final_independent_r4_disk_replay": "NOT_RUN",
        "qualification_credit": "NONE", "production_resource_policy_changed": False,
        "provider_paid_sec_calls": [0, 0, 0],
    }
    receipt = {**body, "receipt_id": content_hash(value=body)}
    atomic_write_json(path=output, value=receipt)
    print(json.dumps({
        "receipt_id": receipt["receipt_id"], "path": str(output),
        "materialization_status": report["status"],
        "full_benchmark_status": body["aggregate_performance_benchmark"],
        "derived_asset_id": report["derived_asset_id"],
        "table_count": report["table_count"], "expanded_cells": report["expanded_cells"],
        "worker_wall_seconds": report["wall_seconds"], "host_wall_seconds": report["host_wall_seconds"],
        "cgroup_peak_bytes": report["cgroup_memory_peak_bytes"],
        "observed_operation_counts": report["observed_operation_counts"],
        "provider_paid_sec_calls": [0, 0, 0],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
