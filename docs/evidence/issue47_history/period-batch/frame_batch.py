"""Run every planned period through period_runs.py, a few periods at a time.

Usage (from the runtime tree, SOURCE_ROOT set as for period_runs.py):
    python3 frame_batch.py <plan.tsv> <out dir> --workers 3

Each line of the plan (label, company, report end, metrics) runs as its own
process - ``period_runs.py <out>/<label> ...  --layout shared --block on
--memo on --memo-off-read-back 1`` - with its own bytecode prefix, so no
process writes the runtime tree. A period whose ``period-<label>.json`` already
exists is skipped, so a restarted batch picks up where it stopped. A period's
data root is deleted only when every Run it created was read back by the
separate process - and the sampled one again with the derivation memo off -
with the same run and result, and every position that produced no public row
failed with a named refusal - an error of the route's own type carrying a
category or a reason code, not a Python fault: a data root holds a copy of
every captured attempt (about 0.8 GB), and the Runs, their row receipts and
the read-backs stay. A named refusal is an answer about the inputs, which the
source root still holds, and every period has some (D04 until an assessment
is registered), so keeping those roots would fill the disk. A program fault or
any read-back that differs keeps it.

Progress, one line per event, goes to ``<out>/progress.log``. Zero calls.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(out, line):
    with open(out / "progress.log", "a", encoding="utf-8") as handle:
        handle.write(_now() + " " + line + "\n")


_FAULTS = {"AssertionError", "AttributeError", "FileNotFoundError", "IndexError", "KeyError",
           "NameError", "OSError", "RecursionError", "RuntimeError", "TypeError",
           "UnboundLocalError", "ValueError", "ZeroDivisionError"}
_REASON_CODE = re.compile(r"[A-Z][A-Z0-9_]{3,}(:|$)")


def _named_refusal(position):
    return position.get("error_type") not in _FAULTS and (
        bool(position.get("category")) or bool(_REASON_CODE.match(position.get("error") or "")))


def _same(position, key):
    found = position.get(key, {})
    return found.get("run_id") == position.get("run_id") and found.get(
        "result_id") == position.get("result_id")


def _deletable(period):
    """Every Run read back the same, the sample too, and every failure named."""
    positions = period["positions"]
    created = {m: p for m, p in positions.items() if p.get("stage") == "PUBLIC_ROW"}
    sampled = period["phases"].get("memo_off_read_back", {}).get("metrics", [])
    return (all(_same(p, "separate_process_read_back") for p in created.values())
            and (not created or bool(sampled))
            and all(_same(positions[m], "memo_off_read_back") for m in sampled)
            and all(_named_refusal(p) for m, p in positions.items() if m not in created))


def run_period(line, out):
    label, company, report_end, metrics = line
    target = out / label
    record = target / ("period-" + label + ".json")
    if record.exists():
        _log(out, label + " SKIPPED_ALREADY_RECORDED")
        return label, "SKIPPED"
    if target.exists():
        # A period cut short by a restart: its Runs cannot be resumed one by
        # one inside the same shared data root, so the period starts over.
        shutil.rmtree(target)
    target.mkdir(parents=True)
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp(prefix="frame-batch-pyc-")}
    started = time.time()
    _log(out, label + " START " + company + " " + report_end + " " + str(len(metrics.split(","))))
    with open(target / "period.log", "w", encoding="utf-8") as handle:
        done = subprocess.run(
            [sys.executable, "-u", str(HERE / "period_runs.py"), str(target), label, company,
             report_end, metrics, "--layout", "shared", "--block", "on", "--memo", "on",
             "--memo-off-read-back", "1"],
            stdout=handle, stderr=subprocess.STDOUT, env=env)
    shutil.rmtree(env["PYTHONPYCACHEPREFIX"], ignore_errors=True)
    seconds = int(time.time() - started)
    if done.returncode != 0 or not record.exists():
        _log(out, label + " FAILED_EXIT " + str(done.returncode) + " " + str(seconds) + "s")
        return label, "FAILED"
    period = json.loads(record.read_text(encoding="utf-8"))
    stages = {}
    for position in period["positions"].values():
        stages[position["stage"]] = stages.get(position["stage"], 0) + 1
    if _deletable(period):
        data_root = target / ("data-" + label)
        if data_root.is_dir():
            shutil.rmtree(data_root)
        kept = "DATA_ROOT_DELETED"
    else:
        kept = "DATA_ROOT_KEPT"
    _log(out, label + " DONE " + json.dumps(stages, sort_keys=True) + " " + kept + " "
         + str(seconds) + "s")
    return label, "DONE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lines = [line.rstrip("\n").split("\t") for line in args.plan.read_text().splitlines()
             if line.strip()]
    _log(out, "BATCH_START " + str(len(lines)) + " periods, " + str(args.workers) + " workers")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda line: run_period(line, out), lines))
    _log(out, "BATCH_END " + json.dumps({status: sum(1 for _, s in results if s == status)
                                         for status in ("DONE", "SKIPPED", "FAILED")}))


if __name__ == "__main__":
    main()
