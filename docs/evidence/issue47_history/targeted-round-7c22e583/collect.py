"""Collect one targeted round's matrices into a record, checking what each claims.

Usage: python3 collect.py <targeted directory> <runtime tree> <out.json>

Reads every matrix-*.json the round's driver wrote, requires each frozen
position's separate-process read-back to name the same run and result, and
records the runtime tree's commit and the files it carries beyond that commit
(the registration patch). Nothing is re-run and nothing is called.
"""
import json
import subprocess
import sys
from pathlib import Path

ROUND, RUNTIME, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
KEEP = ("company_id", "metric_id", "report_end", "stage", "quality", "publication",
        "reason_code", "result_id", "run_id", "requirement_closure_hash", "evidence_count",
        "selection_id", "error", "error_type")


def _git(*arguments):
    return subprocess.run(["git", "-C", str(RUNTIME), *arguments], check=True,
                          capture_output=True, text=True).stdout.strip()


positions, problems, calls, seconds = [], [], [0, 0, 0], 0
for matrix_path in sorted(ROUND.glob("matrix-*.json")):
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
          "runtime_tree": {"commit": _git("rev-parse", "HEAD"),
                           "files_beyond_the_commit": _git("diff", "--name-only").splitlines()}}
OUT.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: record[k] for k in ("position_count", "public_rows",
                                         "requirement_closure_hashes", "calls",
                                         "read_back_problems")}, sort_keys=True))
