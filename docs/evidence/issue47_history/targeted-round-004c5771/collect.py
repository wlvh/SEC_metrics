"""Collect a targeted round driven by period-batch/frame_batch.py into one record.

Usage: python3 collect.py <round directory> <commit the runtime tree carried> <out.json>

The driver writes one directory per period with its matrix-<label>.json. This
reads every one, requires each frozen position's separate-process read-back to
name the same run and result, and records the closure each Run reports. The
runtime tree is re-synced between rounds, so its current state does not say
what a past round ran; the commit is given by the caller and checked against
the closures: the caller states which commit, plus the registration patch,
mints the closure the Runs report. Nothing is re-run and nothing is called.
"""
import json
import sys
from pathlib import Path

ROUND, COMMIT, OUT = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
KEEP = ("company_id", "metric_id", "report_end", "stage", "quality", "publication",
        "reason_code", "result_id", "run_id", "requirement_closure_hash", "evidence_count",
        "selection_id", "row_hash", "error", "error_type")

positions, problems, calls, seconds = [], [], [0, 0, 0], 0
for matrix_path in sorted(ROUND.glob("*/matrix-*.json")):
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    seconds += matrix.get("duration_seconds", 0)
    for index, name in enumerate(("provider", "paid", "sec")):
        calls[index] += matrix["calls"][name]
    for position in matrix["positions"]:
        row = {key: position.get(key) for key in KEEP if key in position}
        value = position.get("value")
        if isinstance(value, str) and "\n" in value:
            row["value_lines"] = value.count("\n") + 1
            row["value_characters"] = len(value)
        else:
            row["value"] = value
        replay = position.get("separate_process_replay")
        if position.get("stage") == "PUBLIC_ROW":
            same = (replay is not None and replay.get("status") == "FROZEN"
                    and replay.get("run_id") == position["run_id"]
                    and replay.get("result_id") == position["result_id"])
            row["separate_process_read_back_same_run_and_result"] = same
            if not same:
                problems.append({"position": row, "read_back": replay})
        positions.append(row)
closures = sorted({row["requirement_closure_hash"] for row in positions
                   if row.get("requirement_closure_hash")})
record = {"record_type": "ISSUE_47_TARGETED_ROUND", "positions": positions,
          "position_count": len(positions),
          "public_rows": sum(1 for row in positions if row.get("stage") == "PUBLIC_ROW"),
          "requirement_closure_hashes": closures,
          "calls": {"provider": calls[0], "paid": calls[1], "sec": calls[2]},
          "driver_seconds": int(seconds),
          "read_back_problems": problems,
          "runtime_tree": {"commit": COMMIT,
                           "carries": "docs/evidence/issue47_history/native-run-2026-09-18/"
                                      "0001-register-issue47-v1.patch"}}
OUT.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: record[k] for k in ("position_count", "public_rows",
                                         "requirement_closure_hashes", "calls",
                                         "read_back_problems")}, sort_keys=True))
