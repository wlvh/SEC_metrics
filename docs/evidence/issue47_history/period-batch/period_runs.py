"""One period's native Runs: install, create, freeze, public row, and a separate-process cold read.

The body of targeted_runs.py (targeted-round-30a7934b/), with two choices a
batch over an acquisition's root needs, each switchable so that it can be
compared against the way it replaces:

* ``--layout shared`` installs every metric of the period into one data root
  and creates the Runs after all installs; ``per-position`` gives each metric
  its own data root, as targeted_runs.py does. Every install copies every
  captured attempt (checkpoint_installation), so per-position roots also cost
  one full copy each.
* ``--block on`` runs the whole period, and the cold read's process, inside
  historical_run_replay.run_checks_replay_once(); ``off`` runs the frozen path.
* ``--memo on`` also opens historical_derivation_memo.derived_once_per_state()
  in both processes, so the Requirement snapshot and the two input
  preparations are derived once per state of the trees they read; ``off``
  derives them every time, as the frozen path does.

Each position records the run and result it produced, its public row hash and
a separate process's read-back. That process opens the same blocks, so it
catches anything that changed since creation but does not test the
derivation memo's own assumptions; ``--memo-off-read-back N`` reads N of the
period's Runs back once more with the memo off (the replay block stays on: a
replay on an acquisition's root takes minutes), chosen by the label's hash so
a frame's periods sample different metrics. The period records seconds, the
number of
frozen checkpoint replays and the memo's outcomes per phase. Besides
``period-<label>.json`` it writes ``matrix-<label>.json`` in the shape
targeted_runs.py writes, one row per position with the read-back under
``separate_process_replay``, so the full-frame report reads either driver's
output. Zero calls: the network is patched off.

Run from the root of a runtime tree carrying the registration patch, with
SOURCE_ROOT set to a root that tree's trust journal registers.

Usage:
    SOURCE_ROOT=<root> python3 docs/evidence/issue47_history/period-batch/period_runs.py \
        <out dir> <label> <company_id> <report_end> <metric,metric,...> \
        --layout shared|per-position --block on|off --memo on|off [--memo-off-read-back N]
"""
import argparse
import contextlib
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

RUNTIME = Path(os.environ.get("RUNTIME") or Path.cwd())
sys.path.insert(0, str(RUNTIME / "scripts"))

from vnext.historical_projection import render_historical_run  # noqa: E402
from vnext.historical_derivation_memo import derived_once_per_state  # noqa: E402
from vnext.historical_run import create_historical_run, install_historical_run_inputs  # noqa: E402
from vnext.historical_run_replay import run_checks_replay_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

READ_BACK = r"""
import hashlib, json, socket, sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, %(scripts)r)
from vnext.historical_derivation_memo import derived_once_per_state
from vnext.historical_run_replay import run_checks_replay_once
from vnext.run_store import load_frozen_run
import contextlib
replays, memo = [], []
block = run_checks_replay_once(replays=replays) if %(block)r else contextlib.nullcontext()
derived = derived_once_per_state(report=memo) if %(memo)r else contextlib.nullcontext()
rows, started = {}, time.time()
with patch.object(socket.socket, 'connect', side_effect=AssertionError('no net')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('no dns')), block, derived:
    for metric, run_dir, data_root in %(runs)r:
        try:
            manifest, records, _ = load_frozen_run(run_dir=Path(run_dir), repo_root=Path(data_root))
            found = [x for x in records if x['record_type'] == 'METRIC_RESULT'
                     and x.get('metric_id') == metric]
            assert len(found) == 1
            rows[metric] = {'run_id': manifest['run_id'], 'status': manifest['status'],
                            'result_id': found[0]['result_id'],
                            'quality': found[0]['quality'],
                            'publication': found[0]['publication'],
                            'value_sha256': hashlib.sha256(str(found[0]['value']).encode()).hexdigest()}
        except Exception as error:
            rows[metric] = {'error': type(error).__name__ + ': ' + str(error)[:300]}
outcomes = {}
for item in memo:
    outcomes[item['outcome']] = outcomes.get(item['outcome'], 0) + 1
print(json.dumps({'rows': rows, 'seconds': round(time.time() - started, 1),
                  'frozen_replays': len(replays), 'memo': outcomes,
                  'not_remembered': [x for x in memo if x['outcome'] != 'ANSWERED'
                                     and x['outcome'] != 'COMPUTED']}))
"""


def _no_network():
    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(socket.socket, "connect",
                                     side_effect=AssertionError("Network forbidden")))
    stack.enter_context(patch.object(socket, "getaddrinfo",
                                     side_effect=AssertionError("DNS forbidden")))
    return stack


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("label")
    parser.add_argument("company_id")
    parser.add_argument("report_end")
    parser.add_argument("metrics")
    parser.add_argument("--layout", choices=("shared", "per-position"), required=True)
    parser.add_argument("--block", choices=("on", "off"), required=True)
    parser.add_argument("--memo", choices=("on", "off"), required=True)
    parser.add_argument("--memo-off-read-back", type=int, default=0)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_root = Path(os.environ["SOURCE_ROOT"]) if os.environ.get("SOURCE_ROOT") else None
    metrics = args.metrics.split(",")
    replays, memo, phases, positions = [], [], {}, {}
    block = run_checks_replay_once(replays=replays) if args.block == "on" else contextlib.nullcontext()
    derived = (derived_once_per_state(report=memo) if args.memo == "on"
               else contextlib.nullcontext())

    def data_root(metric):
        return out / ("data-" + args.label + ("" if args.layout == "shared" else "-" + metric))

    def mark(phase, started, before):
        outcomes = {}
        for item in memo[before[1]:]:
            outcomes[item["outcome"]] = outcomes.get(item["outcome"], 0) + 1
        phases[phase] = {"seconds": round(time.time() - started, 1),
                         "frozen_replays": len(replays) - before[0], "memo": outcomes}

    started_all = time.time()
    with _no_network(), block, derived:
        started, before = time.time(), (len(replays), len(memo))
        selection = resolve_period_selection(repo_root=source_root or RUNTIME,
                                             company_id=args.company_id,
                                             report_end=args.report_end)
        mark("select", started, before)
        installed = {}
        started, before = time.time(), (len(replays), len(memo))
        for metric in metrics:
            try:
                installed[metric] = install_historical_run_inputs(
                    data_root=data_root(metric), company_id=args.company_id, metric_id=metric,
                    period_selection=selection,
                    **({"source_root": source_root} if source_root else {}))
            except Exception as error:  # noqa: BLE001 - per position
                positions[metric] = {"stage": "INSTALL_FAILED", "error_type": type(error).__name__,
                                     "error": str(error)[:300],
                                     "category": getattr(error, "category", None)}
        mark("install", started, before)
        started, before = time.time(), (len(replays), len(memo))
        for metric in metrics:
            if metric not in installed:
                continue
            run_dir = out / ("run-" + args.label + "-" + metric)
            try:
                run = create_historical_run(
                    data_root=data_root(metric), run_dir=run_dir, company_id=args.company_id,
                    metric_id=metric, binding_id=installed[metric]["binding"]["binding_id"],
                    freeze=True)
                rendered = render_historical_run(data_root=data_root(metric), run_dir=run_dir,
                                                 frozen=True, persist=True)
                positions[metric] = {
                    "stage": "PUBLIC_ROW", "run_dir": str(run_dir),
                    "data_root": str(data_root(metric)),
                    "binding_id": installed[metric]["binding"]["binding_id"],
                    "run_id": run["manifest"]["run_id"],
                    "requirement_closure_hash": run["manifest"]["requirement_closure_hash"],
                    "result_id": run["result"]["result_id"], "value": run["result"]["value"],
                    "quality": run["result"]["quality"],
                    "publication": run["result"]["publication"],
                    "reason_code": run["result"]["reason_code"], "new_calls": run["new_calls"],
                    "row_hash": rendered["receipt"]["row_hash"],
                    "evidence_count": len(rendered["evidence"])}
            except Exception as error:  # noqa: BLE001 - per position
                positions[metric] = {"stage": "FAILED", "error_type": type(error).__name__,
                                     "error": str(error)[:300],
                                     "category": getattr(error, "category", None)}
            print(args.label, metric, positions[metric]["stage"],
                  str(positions[metric].get("value") or positions[metric].get("error") or "")[:100],
                  flush=True)
        mark("create", started, before)
    runs = sorted((metric, row["run_dir"], row["data_root"]) for metric, row in positions.items()
                  if row["stage"] == "PUBLIC_ROW")

    def read_back(chosen, block, memo_on):
        started = time.time()
        completed = subprocess.run(
            [sys.executable, "-c", READ_BACK % {"scripts": str(RUNTIME / "scripts"),
                                                "runs": chosen, "block": block,
                                                "memo": memo_on}],
            capture_output=True, text=True, cwd=str(out))
        found = (json.loads(completed.stdout.strip().splitlines()[-1])
                 if completed.returncode == 0 else {"error": completed.stderr[-600:]})
        return found, {"seconds": round(time.time() - started, 1),
                       "frozen_replays": found.get("frozen_replays"), "memo": found.get("memo"),
                       "memo_not_remembered": found.get("not_remembered"),
                       **({"error": found["error"]} if "error" in found else {})}

    found, phases["read_back"] = read_back(runs, args.block == "on", args.memo == "on")
    for metric, row in found.get("rows", {}).items():
        positions[metric]["separate_process_read_back"] = row
    if args.memo_off_read_back and runs:
        start = int(hashlib.sha256(args.label.encode()).hexdigest()[:8], 16) % len(runs)
        step = max(1, len(runs) // args.memo_off_read_back)
        chosen = sorted({runs[(start + index * step) % len(runs)]
                         for index in range(min(args.memo_off_read_back, len(runs)))})
        found, phases["memo_off_read_back"] = read_back(chosen, args.block == "on", False)
        phases["memo_off_read_back"]["metrics"] = [metric for metric, _, _ in chosen]
        for metric, row in found.get("rows", {}).items():
            positions[metric]["memo_off_read_back"] = row
    body = {"label": args.label, "company_id": args.company_id, "report_end": args.report_end,
            "layout": args.layout, "block": args.block, "memo": args.memo, "metrics": metrics,
            "memo_not_remembered": [item for item in memo
                                    if item["outcome"] not in ("ANSWERED", "COMPUTED")],
            "selection_id": selection["selection_id"], "positions": positions, "phases": phases,
            "seconds": round(time.time() - started_all, 1),
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    matrix = []
    for metric in metrics:
        row = {"case": args.label, "company_id": args.company_id,
               "report_end": args.report_end, "metric_id": metric,
               "selection_id": selection["selection_id"],
               **{key: value for key, value in positions[metric].items()
                  if key not in ("separate_process_read_back", "memo_off_read_back", "run_dir",
                                 "data_root", "binding_id")}}
        if row["stage"] == "INSTALL_FAILED":
            row["stage"] = "FAILED"
        if "separate_process_read_back" in positions[metric]:
            row["separate_process_replay"] = positions[metric]["separate_process_read_back"]
        matrix.append(row)
    (out / ("matrix-" + args.label + ".json")).write_text(
        json.dumps({"positions": matrix, "duration_seconds": body["seconds"],
                    "calls": body["calls"]}, indent=1, sort_keys=True, default=str) + "\n",
        encoding="utf-8")
    # Written last: a batch treats this file's presence as "the period finished".
    (out / ("period-" + args.label + ".json")).write_text(
        json.dumps(body, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"phases": phases, "seconds": body["seconds"]}), flush=True)


if __name__ == "__main__":
    main()
