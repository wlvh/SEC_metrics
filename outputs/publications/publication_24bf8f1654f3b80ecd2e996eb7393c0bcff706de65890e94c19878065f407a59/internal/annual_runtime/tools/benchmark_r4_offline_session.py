#!/usr/bin/env python3
"""Measure actual R4 offline work or guarded production materialization.

The complete benchmark requires the certified mixed-route fixture set and
charges one fresh disk replay to both alternatives. Materialization-only
measurements remain a distinct evidence tier, never an aggregate >=10x PASS.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.canonical import atomic_write_json, canonical_json_bytes, content_hash, sha256_bytes  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402
from vnext.r4_materialization import materialize_full_source  # noqa: E402
from vnext.records import validate_record  # noqa: E402
from vnext.sources import resolve_repository_file  # noqa: E402


ARTIFACT_ROOT = Path("docs/r4_offline/qualified_cases")
BASE_COMMIT = "c45338567700e3048f4cf32d251369e4521e9444"
NETWORK_DENY_PROFILE = "(version 1) (allow default) (deny network*)"


def _file_binding(relative):
    path = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative)
    data = path.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(content=data), "size": len(data)}


def _assert_bindings(bindings):
    for expected in bindings:
        if _file_binding(expected["path"]) != expected:
            raise RuntimeError("Benchmark input changed: " + expected["path"])


def _workload(*, requirement_id, closure):
    """Pin committed prior history and the actual mixed-route artifact set."""
    from git_workspace import sanitized_git_environment
    from vnext.r4_offline_qualification import load_case_definitions

    cases = load_case_definitions(repo_root=ROOT)
    if type(cases) is not list or not cases or len({c["fixture_id"] for c in cases}) != len(cases):
        raise RuntimeError("Benchmark fixture set is empty or duplicated")
    if {c["metric_id"] for c in cases} != {"A03", "A04", "A09", "A11", "A12", "A13"}:
        raise RuntimeError("Benchmark must represent the exact six R4 metrics")
    paths = set()
    for root in (ROOT / "scripts", ROOT / "requirements", ROOT / "catalog", ROOT / "config"):
        for path in root.rglob("*"):
            if path.is_symlink():
                raise RuntimeError("Benchmark authority contains a symlink")
            if path.is_file() and "__pycache__" not in path.parts:
                paths.add(path.relative_to(ROOT).as_posix())
    paths.add(Path(__file__).resolve().relative_to(ROOT).as_posix())
    paths.update({"docs/r4_offline/fixture_acquisition_receipt.json", "evidence/requests_log.csv",
                  "evidence/requests_log_manifest.json"})
    def include_immutable_sources(value):
        if type(value) is dict:
            for nested in value.values():
                include_immutable_sources(nested)
        elif type(value) is list:
            for nested in value:
                include_immutable_sources(nested)
        elif type(value) is str and value.startswith("evidence/request_attempts/"):
            paths.add(value)

    for case in cases:
        directory = ROOT / ARTIFACT_ROOT / case["fixture_id"]
        if not directory.is_dir() or directory.is_symlink():
            raise RuntimeError("Qualified fixture directory is unavailable: " + case["fixture_id"])
        artifact_files = sorted(p for p in directory.iterdir() if p.is_file())
        if not artifact_files:
            raise RuntimeError("Qualified fixture has no persisted artifacts")
        paths.update(p.relative_to(ROOT).as_posix() for p in artifact_files)
        for path in artifact_files:
            _file_binding(path.relative_to(ROOT).as_posix())
            if path.suffix == ".json":
                include_immutable_sources(strict_json_file(path=path))
        if case.get("recipe_path"):
            paths.add(case["recipe_path"])
            include_immutable_sources(strict_json_file(path=ROOT / case["recipe_path"]))
    paths.add((ARTIFACT_ROOT / "index.json").as_posix())
    include_immutable_sources(strict_json_file(path=ROOT / ARTIFACT_ROOT / "index.json"))
    previous = prior_terminal_inventory(repo_root=ROOT)
    for row in previous["selected_runs"]:
        original = subprocess.run(["git", "cat-file", "blob", BASE_COMMIT + ":" + row["manifest_path"]],
            cwd=ROOT, env=sanitized_git_environment(), capture_output=True, check=True).stdout
        if sha256_bytes(content=original) != row["manifest_sha256"] or len(original) != row["manifest_size"]:
            raise RuntimeError("Prior Run is not the exact main baseline input")
    body = {"schema_version": 1, "requirement_id": requirement_id,
            "requirement_closure_hash": closure, "cases": cases, "prior_history": previous,
            "base_commit": BASE_COMMIT, "input_bindings": [_file_binding(p) for p in sorted(paths)]}
    return {**body, "workload_id": content_hash(value=body)}


def _replay_case(*, case, requirement, source_bundle, evidence_context=None, scoped_context=None):
    from vnext.r4_offline_qualification import replay_case_artifacts

    result = replay_case_artifacts(repo_root=ROOT, requirement=requirement, fixture=case,
        source_bundle=source_bundle, evidence_context=evidence_context, scoped_context=scoped_context)
    if type(result) is not dict:
        raise RuntimeError("Native fixture replay must return a JSON semantic result")
    # No timing, mode flag, or omitted evidence is used to force equivalence.
    canonical = canonical_json_bytes(value=result)
    return {"fixture_id": case["fixture_id"], "artifact_kind": case["artifact_kind"],
            "semantic_result": result, "semantic_result_sha256": sha256_bytes(content=canonical)}


def _scope_file_bindings(cases):
    result = {}
    for case in cases:
        path = ARTIFACT_ROOT / case["fixture_id"] / "source_scope.json"
        if (ROOT / path).is_file():
            value = strict_json_file(path=ROOT / path)
            identity = value["source_scope_manifest_id"]
            if identity in result:
                raise RuntimeError("Duplicate scoped fixture identity")
            result[identity] = _file_binding(path.as_posix())
    return result


def _source_contexts(*, source_id, declaration, derived_asset_bytes, requirement, cases):
    from vnext.evidence import prepare_offline_evidence_context_from_asset_bytes
    from vnext.scoped_reader import prepare_offline_scoped_context
    from vnext.r4_task_contracts import resolve_r4_task_contract
    from vnext.r4_source_audit import source_authority
    from vnext.r4_offline_qualification import prepare_source_bundle, prepare_source_bundle_from_context

    scope_files = _scope_file_bindings(cases)
    if not scope_files and not any(c["fixture_class"] in {"NEGATIVE_EXPECTED", "AMBIGUOUS_EXCLUDED"} for c in cases):
        bundle = prepare_source_bundle(repo_root=ROOT, source_id=source_id,
                                       full_derived_asset=json.loads(derived_asset_bytes))
        return bundle, None, None
    task_ids = sorted({case["task_contract_id"] for case in cases})
    tasks = [resolve_r4_task_contract(repo_root=ROOT, requirement=requirement, task_contract_id=t) for t in task_ids]
    source = source_authority(repo_root=ROOT, declaration=declaration)
    # One canonical-byte ownership deserialize, with no temporary full graph
    # merely to create a manifest/transport. The factory derives both from
    # its private graph and performs the same full native verification.
    context = prepare_offline_evidence_context_from_asset_bytes(repo_root=ROOT,
        requirement=requirement, source_bytes=source["source_bytes"], raw_blob=source["raw_blob"],
        source_reference=source["source_reference"], derived_asset_bytes=derived_asset_bytes,
        task_contracts=tasks, task_generation="R4_V2")
    bundle = prepare_source_bundle_from_context(repo_root=ROOT, source_id=source_id,
        evidence_context=context, task_contract_id=task_ids[0])
    scope_context = prepare_offline_scoped_context(evidence_context=context, scope_files=scope_files) if scope_files else None
    return bundle, context, scope_context


def _worker_body(*, mode, workload_path):
    """Execute one fresh process; every duration includes cold input checks."""
    from vnext.offline_execution_session import FileBinding, OfflineExecutionSession, OfflineOperationObserver
    from vnext.offline_execution_session import OfflinePriorRunSet
    from vnext.requirements import load_requirement_snapshot
    from vnext.ratchet_release import load_portable_qualification_run
    from vnext.r4_offline_qualification import prepare_source_bundle, _structured_context
    from vnext.r4_fixture_authority import load_r4_fixture_authority

    # A second enforcement layer in addition to the process-tree OS sandbox.
    forbidden_network_attempts = []
    def deny_network(event, arguments):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.bind"}:
            forbidden_network_attempts.append(event)
            raise RuntimeError("Offline benchmark attempted network: " + event)
    sys.addaudithook(deny_network)
    started = time.perf_counter()
    workload = strict_json_file(path=workload_path)
    body = {k: v for k, v in workload.items() if k != "workload_id"}
    if content_hash(value=body) != workload["workload_id"]:
        raise RuntimeError("Benchmark workload identity differs")
    if workload != _workload(requirement_id=workload["requirement_id"],
                             closure=workload["requirement_closure_hash"]):
        raise RuntimeError("Benchmark workload is not the current repository-derived exact set")
    _assert_bindings(workload["input_bindings"])
    qid, closure = workload["requirement_id"], workload["requirement_closure_hash"]
    prior_rows = workload["prior_history"]["selected_runs"]
    results, sessions, baseline_children, counts = [], [], [], defaultdict(int)

    def authority():
        q = load_requirement_snapshot(snapshot_dir=ROOT / "requirements" / qid)
        if q["requirement_closure_hash"] != closure:
            raise RuntimeError("Benchmark Requirement closure changed")
        return q

    if mode == "baseline":
        with OfflineOperationObserver() as observed:
            for case in workload["cases"]:
                child_started = time.perf_counter()
                child_before = dict(OfflineOperationObserver._active_observer.counts)
                print(json.dumps({"mode": mode, "starting_fixture": case["fixture_id"]}), flush=True)
                # The pre-session model revalidates prior terminals at each
                # actual child boundary, like the existing qualification phase
                # gate. It never runs extra/fake children to increase timings.
                for row in prior_rows:
                    load_portable_qualification_run((ROOT / row["manifest_path"]).parent, ROOT)
                requirement = authority()
                bundle = prepare_source_bundle(repo_root=ROOT, source_id=case["source_id"])
                result = _replay_case(case=case, requirement=requirement, source_bundle=bundle)
                results.append(result)
                baseline_children.append({"fixture_id": case["fixture_id"],
                    "wall_seconds": format(time.perf_counter() - child_started, ".6f"),
                    "operation_counts": {key: value - child_before[key]
                        for key, value in OfflineOperationObserver._active_observer.counts.items()}})
                print(json.dumps({"mode": mode, "completed_fixture": case["fixture_id"],
                    "fixture_wall_seconds": baseline_children[-1]["wall_seconds"]}), flush=True)
                del bundle
        counts.update(observed.counts)
    else:
        prior = OfflinePriorRunSet(repo_root=ROOT, manifests=[
            FileBinding(row["manifest_path"], row["manifest_sha256"], row["manifest_size"]) for row in prior_rows
        ])
        prior.prepare()
        counts.update(prior.observed_operation_counts)
        grouped = defaultdict(list)
        for case in workload["cases"]:
            grouped[case["source_id"]].append(case)
        for source_id, cases in grouped.items():
            source_started = time.perf_counter()
            print(json.dumps({"mode": mode, "preparing_source": source_id}), flush=True)
            # The source factory is the sole source/asset constructor. The
            # context owns one native XBRL parse and exact immutable tables.
            with OfflineOperationObserver() as prep_observed:
                declaration = load_r4_fixture_authority(repo_root=ROOT)["sources"][source_id]
                session = OfflineExecutionSession(repo_root=ROOT,
                    source=FileBinding(declaration["source_repo_relative_path"], declaration["source_sha256"], declaration["source_size"]),
                    requirement_id=qid, requirement_closure_hash=closure)
                prepared_inputs = session.prepare()
                requirement = json.loads(prepared_inputs.requirement_bytes)
                bundle, evidence_context, scoped_context = _source_contexts(
                    source_id=source_id, declaration=declaration,
                    derived_asset_bytes=prepared_inputs.derived_asset_bytes,
                    requirement=requirement, cases=cases)
                recipes = load_r4_fixture_authority(repo_root=ROOT)["recipes"]
                if any(recipes[c["fixture_id"]].get("structured_route_input") is not None for c in cases):
                    _structured_context(repo_root=ROOT, bundle=bundle)
            preparation_seconds = format(time.perf_counter() - source_started, ".6f")
            source_counts = dict(prep_observed.counts)
            print(json.dumps({"mode": mode, "prepared_source": source_id,
                              "preparation_wall_seconds": preparation_seconds}), flush=True)
            if source_counts["source_materializations"] != 1 or source_counts["derived_asset_builds"] != 1:
                raise RuntimeError("Optimized source preparation must build the full source/asset exactly once")
            if source_counts["derived_asset_json_decodes"] != 1:
                raise RuntimeError("Optimized preparation repeated the full asset ownership deserialize")
            if any(source_counts[key] > 1 for key in (
                    "parent_authority_builds", "requirement_builds", "revision_requirement_builds")):
                raise RuntimeError("Optimized source preparation repeated full Requirement authority")
            child_rows = []
            for case in cases:
                child_started = time.perf_counter()
                prior.assert_unchanged()
                with OfflineOperationObserver() as child_observed:
                    encoded = session.run_child(child_id=case["fixture_id"], operation=lambda _:
                        {"status": "PASSED", "case": _replay_case(case=case, requirement=requirement, source_bundle=bundle,
                                          evidence_context=evidence_context, scoped_context=scoped_context)})
                    result = json.loads(encoded)["case"]
                for key in ("source_materializations", "derived_asset_builds", "requirement_load_calls",
                            "requirement_builds", "revision_requirement_builds",
                            "parent_authority_builds", "legacy_parent_authority_builds",
                            "native_prior_run_loads", "portable_prior_run_loads",
                            "xbrl_fact_parses", "xbrl_context_parses", "derived_asset_json_decodes"):
                    if child_observed.counts[key]:
                        raise RuntimeError("Optimized child repeated full work: " + case["fixture_id"] + ":" + key)
                child_rows.append({"fixture_id": case["fixture_id"],
                    "wall_seconds": format(time.perf_counter() - child_started, ".6f"),
                    "operation_counts": dict(child_observed.counts)})
                for key, value in child_observed.counts.items():
                    counts[key] += value
                results.append(result)
                prior.assert_unchanged()
                print(json.dumps({"mode": mode, "completed_fixture": case["fixture_id"],
                    "fixture_wall_seconds": child_rows[-1]["wall_seconds"]}), flush=True)
            for key, value in source_counts.items():
                counts[key] += value
            sessions.append({"source_id": source_id, "source_sha256": bundle["raw_blob"]["raw_asset_id"][7:],
                             "preparation_wall_seconds": preparation_seconds,
                             "preparation_counts": source_counts, "children": child_rows,
                             "session_guard_state": session.state})
            del bundle, evidence_context, scoped_context, session, prepared_inputs
    results.sort(key=lambda row: row["fixture_id"])
    _assert_bindings(workload["input_bindings"])
    if forbidden_network_attempts or any(counts[key] for key in ("provider_calls", "paid_model_calls", "sec_calls")):
        raise RuntimeError("Offline benchmark observed a forbidden egress attempt")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {"status": "PASSED", "mode": mode, "workload_id": workload["workload_id"],
              "worker_pid": os.getpid(), "interpreter": {"executable": sys.executable,
                  "executable_sha256": sha256_bytes(content=Path(sys.executable).resolve().read_bytes()),
                  "version": platform.python_version(), "implementation": platform.python_implementation(),
                  "platform": platform.platform()},
              "wall_seconds": format(time.perf_counter() - started, ".6f"),
              "peak_rss_bytes": peak if platform.system() == "Darwin" else peak * 1024,
              "operation_counts": dict(counts), "source_sessions": sessions,
              "baseline_children": baseline_children, "results": results,
              "semantic_result_set_id": content_hash(value=results), "provider_paid_sec_calls": [0, 0, 0],
              "qualification_credit": "NONE_OFFLINE_BENCHMARK"}
    return report


def _worker(*, mode, workload_path, output):
    from vnext.offline_execution_session import OfflineOperationObserver
    with OfflineOperationObserver() as observed:
        report = _worker_body(mode=mode, workload_path=workload_path)
    report["operation_counts"] = dict(observed.counts)
    report["counter_scope"] = "ALL_NATIVE_WORK_THROUGH_RESULT_SEAL_EXCLUDING_REPORT_SERIALIZATION"
    if any(observed.counts[key] for key in ("provider_calls", "paid_model_calls", "sec_calls")):
        raise RuntimeError("Offline worker attempted forbidden egress")
    atomic_write_json(path=output, value=report)


def run_full_benchmark(*, requirement_id, closure, output):
    """Run two alternatives and exactly one fresh independent disk replay.

    The single final replay verifies both identical semantic result sets. Its
    measured duration is charged equally to both alternatives, not omitted
    from optimized time. Workload preparation and source pins are identical.
    """
    from decimal import Decimal

    if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise RuntimeError("Full benchmark requires the available process-tree network-deny sandbox")
    workload = _workload(requirement_id=requirement_id, closure=closure)
    environment = {k: v for k, v in os.environ.items()
                   if not any(token in k.upper() for token in ("API_KEY", "SECRET", "TOKEN", "SEC_CONTACT"))}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(ROOT / "scripts")
    reports = {}
    with tempfile.TemporaryDirectory(prefix="r4-offline-benchmark-") as temporary:
        directory = Path(temporary)
        workload_path = directory / "workload.json"
        atomic_write_json(path=workload_path, value=workload)
        for mode in ("baseline", "optimized", "independent-replay"):
            destination = directory / (mode + ".json")
            command = ["/usr/bin/sandbox-exec", "-p", NETWORK_DENY_PROFILE, sys.executable,
                       str(Path(__file__).resolve()), "--worker-mode", mode,
                       "--workload", str(workload_path), "--output", str(destination)]
            started = time.perf_counter()
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, start_new_session=True)
            expired = []
            def stop_expired_worker(target=process, expiration=expired):
                if target.poll() is None:
                    expiration.append(True)
                    try:
                        os.killpg(target.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            timer = threading.Timer(3600, stop_expired_worker)
            timer.start()
            tail = []
            try:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    tail.append(line)
                    tail = tail[-120:]
                return_code = process.wait()
            except BaseException:
                # An interrupted local benchmark must not orphan a long
                # uncached replay after its orchestrator has stopped.
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                raise
            finally:
                timer.cancel()
            elapsed = time.perf_counter() - started
            if return_code or expired:
                raise RuntimeError(mode + " failed rc=" + str(return_code) + "\n" + "".join(tail)[-12000:])
            report = strict_json_file(path=destination)
            report["process_wall_seconds"] = format(elapsed, ".6f")
            report["command"] = [argument.replace(str(directory), "$BENCHMARK_TEMP") for argument in command]
            reports[mode] = report
            _assert_bindings(workload["input_bindings"])
    semantic_ids = {r["semantic_result_set_id"] for r in reports.values()}
    interpreter_ids = {content_hash(value=r["interpreter"]) for r in reports.values()}
    if (len(semantic_ids) != 1 or len(interpreter_ids) != 1
            or len({r["worker_pid"] for r in reports.values()}) != 3):
        raise RuntimeError("Alternatives/fresh disk replay did not produce one identical result set")
    final = Decimal(reports["independent-replay"]["process_wall_seconds"])
    baseline = Decimal(reports["baseline"]["process_wall_seconds"]) + final
    optimized = Decimal(reports["optimized"]["process_wall_seconds"]) + final
    factor = baseline / optimized
    body = {"record_type": "R4_OFFLINE_SESSION_BENCHMARK", "schema_version": 1,
            "status": "PASSED" if factor >= 10 else "BELOW_REQUIRED_10X", "workload": workload,
            "reports": reports, "final_independent_disk_replay_executions": 1,
            "final_replay_cost_accounting": "ONE_SHARED_FRESH_REPLAY_CHARGED_EQUALLY_TO_BOTH_ALTERNATIVES",
            "baseline_aggregate_seconds": str(baseline), "optimized_aggregate_seconds": str(optimized),
            "aggregate_improvement_factor": str(factor), "required_minimum_improvement": 10,
            "provider_paid_sec_calls": [0, 0, 0], "qualification_credit": "NONE_OFFLINE_BENCHMARK"}
    atomic_write_json(path=output, value={**body, "benchmark_receipt_id": content_hash(value=body)})
    print(json.dumps({"status": body["status"], "factor": str(factor), "output": str(output)}), flush=True)
    if factor < 10:
        raise RuntimeError("Actual aggregate improvement did not reach 10x; no result was hidden")


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
    parser.add_argument("--source")
    parser.add_argument("--sha256")
    parser.add_argument("--size", type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--requirement-id")
    parser.add_argument("--requirement-closure")
    parser.add_argument("--worker-mode", choices=("baseline", "optimized", "independent-replay"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--workload", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve(strict=False)
    try:
        relative = output.relative_to(ROOT)
    except ValueError:
        relative = None
    if relative is not None and not relative.as_posix().startswith("docs/r4_offline/performance"):
        raise RuntimeError("Benchmark output must not overwrite runtime or authority paths")
    if args.worker_mode:
        if args.workload is None or any(value is not None for value in
                                        (args.source, args.sha256, args.size, args.requirement_id,
                                         args.requirement_closure)) or args.benchmark:
            raise RuntimeError("Internal worker arguments are not exact")
        _worker(mode=args.worker_mode, workload_path=args.workload, output=output)
        return 0
    if args.benchmark:
        if any(value is not None for value in (args.source, args.sha256, args.size)):
            raise RuntimeError("Full benchmark cannot mix materialization arguments")
        if args.requirement_id is None or args.requirement_closure is None:
            raise RuntimeError("Full benchmark requires exact Requirement identity")
        run_full_benchmark(requirement_id=args.requirement_id,
                           closure=args.requirement_closure, output=output)
        return 0
    if any(value is None for value in (args.source, args.sha256, args.size)):
        raise RuntimeError("Materialization requires exact source path/SHA/size")
    if args.requirement_id is not None or args.requirement_closure is not None:
        raise RuntimeError("Materialization does not accept Requirement overrides")
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
        "qualification_credit": "NONE", "runtime_limit_override": False,
        "production_max_total_cells": report["production_max_total_cells"],
        "production_resource_policy_modified_by_this_command": False,
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
