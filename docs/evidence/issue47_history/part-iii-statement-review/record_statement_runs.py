"""Record the targeted native Runs for the Part III statement admissions.

Reads each targeted batch's matrix (one row per position, written by
``targeted-round-30a7934b/targeted_runs.py``) and each Run's own manifest, and
writes one row per position: the result as frozen, the closure it ran under,
the cold read by a process that did not create it, and the calls made. A
position whose run failed keeps its error; a later run of the same position is
listed separately, never merged into the failed one.

Usage:
    python3 docs/evidence/issue47_history/part-iii-statement-review/record_statement_runs.py \
        <matrix json> [<matrix json> ...]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEEP = ("metric_id", "report_end", "publication", "quality", "reason_code", "value", "result_id", "run_id",
        "requirement_closure_hash", "evidence_count", "row_hash", "separate_process_replay", "new_calls")


def main(paths):
    rows, calls = [], {"provider": 0, "paid": 0, "sec": 0}
    for path in paths:
        matrix = json.loads(Path(path).read_text(encoding="utf-8"))
        for key in calls:
            calls[key] += matrix["calls"][key]
        for position in matrix["positions"]:
            row = {"case": position["case"], **{key: position[key] for key in KEEP if key in position}}
            if "error" in position:
                row.update({"failed": True, "error": position["error"], "stage": position.get("stage")})
            else:
                replay = position["separate_process_replay"]
                row["cold_read_agrees"] = (replay["status"] == "FROZEN"
                                           and replay["result_id"] == position["result_id"]
                                           and replay["run_id"] == position["run_id"])
            rows.append(row)
    body = {"record_type": "ISSUE_47_PART_III_STATEMENT_VALUE_RUNS",
            "what_this_is": ("targeted native Runs of the positions the two per-filing Part III admissions "
                             "unblocked; each row is read from the batch matrix and the Run's own records"),
            "rows": rows, "calls": calls}
    (HERE / "statement-value-runs.json").write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n",
                                                    encoding="utf-8")
    for row in rows:
        print(row["case"], row["metric_id"], row.get("publication"), row.get("quality"), row.get("value"),
              row.get("reason_code") or row.get("error"))
    print(calls)


if __name__ == "__main__":
    main(sys.argv[1:])
