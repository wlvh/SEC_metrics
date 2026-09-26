"""Compare the targeted E01 Runs with the twelve-period batch, position by position.

The targeted Runs were made by ../targeted-round-30a7934b/targeted_runs.py in a
runtime tree synced to this change; the batch is ../native-run-batch-12-periods/.
Both are read from their Run records (records.jsonl), not from a driver's
summary, and the result identity is compared as well as the value: a route the
change must not touch has to give the same result_id, not merely the same number.

Usage:
    python3 docs/evidence/issue47_history/e01-item-text/compare_runs.py \
        <targeted runs root> <batch runs root with <label>/run-<label>-<metric>>
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _result(run_dir, metric):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for line in (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "METRIC_RESULT" and record.get("metric_id") == metric:
            return {"run_id": manifest["run_id"], "status": manifest["status"],
                    "requirement_closure_hash": manifest["requirement_closure_hash"],
                    "result_id": record["result_id"], "value": record["value"],
                    "publication": record["publication"], "reason_code": record["reason_code"]}
    raise SystemExit("NO_RESULT:" + str(run_dir))


def main():
    targeted, batch = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for matrix in sorted(targeted.glob("matrix-*.json")):
        for position in json.loads(matrix.read_text(encoding="utf-8"))["positions"]:
            label, metric = position["case"], position["metric_id"]
            now = _result(targeted / ("run-" + label + "-" + metric), metric)
            before = _result(batch / label / ("run-" + label + "-" + metric), metric)
            rows.append({"position": label, "metric_id": metric, "before": before, "now": now,
                         "public_row": position["stage"] == "PUBLIC_ROW",
                         "separate_process_cold_read": position["separate_process_replay"],
                         "cold_read_same_result": position["separate_process_replay"].get(
                             "result_id") == now["result_id"],
                         "same_result_id": before["result_id"] == now["result_id"],
                         "same_answer": (before["value"], before["publication"])
                         == (now["value"], now["publication"])})
    closures = sorted({row["now"]["requirement_closure_hash"] for row in rows})
    report = {"record_type": "ISSUE_47_E01_ITEM_TEXT_TARGETED_RUNS",
              "closure": closures, "batch_closure": sorted(
                  {row["before"]["requirement_closure_hash"] for row in rows}),
              "positions": rows,
              "summary": {
                  "runs": len(rows),
                  "all_frozen_with_public_row_and_cold_read": all(
                      row["now"]["status"] == "FROZEN" and row["public_row"]
                      and row["cold_read_same_result"] for row in rows),
                  "untouched_routes_same_result_id": sorted(
                      row["position"] + ":" + row["metric_id"] for row in rows
                      if row["metric_id"] != "E01" and row["same_result_id"]),
                  "e01_same_answer": sorted(row["position"] for row in rows
                                            if row["metric_id"] == "E01" and row["same_answer"]),
                  "e01_now_withheld": sorted(row["position"] for row in rows
                                             if row["metric_id"] == "E01"
                                             and row["now"]["publication"] == "WITHHELD"),
              },
              "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "targeted-runs.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n",
                                             encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
