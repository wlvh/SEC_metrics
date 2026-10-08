"""Compare the Paramount FY2024 targeted Runs with the 12-period batch, position by position.

Usage:
    python3 docs/evidence/issue47_history/part-iii-statement-review/compare_runs.py \
        <targeted runs root> <batch runs root> <output json>

Reads each Run's own records (results and the route's selection detail), never
a summary; both sides are read the same way.
"""
import json
import sys
from pathlib import Path

LABEL = "paramount-2024"
METRICS = ("C01", "E01", "E02", "E03", "E04", "E05", "B01", "B02")


def read(root, metric):
    run = Path(root) / ("run-" + LABEL + "-" + metric)
    if not run.is_dir():
        run = Path(root) / LABEL / ("run-" + LABEL + "-" + metric)
    result, detail = None, None
    for line in (run / "records.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "METRIC_RESULT" and record.get("metric_id") == metric:
            result = record
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    return {"publication": result["publication"], "value": result.get("value"),
            "reason_code": result["reason_code"], "result_id": result["result_id"],
            "run_id": manifest.get("run_id"),
            "requirement_closure_hash": manifest.get("requirement_closure_hash")
            or manifest.get("requirement", {}).get("requirement_closure_hash")}


def main():
    targeted, batch, output = sys.argv[1:4]
    matrix = json.loads((Path(targeted) / ("matrix-" + LABEL + ".json")).read_text())
    replay = {p["metric_id"]: p.get("separate_process_replay") for p in matrix["positions"]}
    rows = []
    for metric in METRICS:
        before, after = read(batch, metric), read(targeted, metric)
        rows.append({"metric_id": metric, "batch": before, "targeted": after,
                     "cold_read": replay.get(metric),
                     "moved": (before["publication"], before["value"], before["reason_code"])
                     != (after["publication"], after["value"], after["reason_code"])})
    body = {"record_type": "ISSUE_47_PART_III_TARGETED_RUNS", "position": LABEL,
            "batch_closure": rows[0]["batch"]["requirement_closure_hash"],
            "targeted_closure": rows[0]["targeted"]["requirement_closure_hash"],
            "rows": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    Path(output).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in rows:
        print(row["metric_id"], row["batch"]["reason_code"], "->",
              row["targeted"]["publication"], row["targeted"]["value"],
              row["targeted"]["reason_code"])


if __name__ == "__main__":
    main()
