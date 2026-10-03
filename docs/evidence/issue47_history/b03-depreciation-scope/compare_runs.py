"""Compare the B03 targeted Runs with the 12-period batch, position by position.

Usage:
    python3 docs/evidence/issue47_history/b03-depreciation-scope/compare_runs.py \
        <targeted runs root> <batch runs root> <output json>

Each side is read from its own Run records - every METRIC_RESULT the Run
holds, so the B01 a B03 Run carries is compared too - never from a summary.
"""
import json
import sys
from pathlib import Path

POSITIONS = (("salesforce-2026", "B03"), ("enphase-2025", "B03"), ("marriott-2025", "B03"))


def _run_dir(root, label, metric):
    run = Path(root) / ("run-" + label + "-" + metric)
    return run if run.is_dir() else Path(root) / label / ("run-" + label + "-" + metric)


def read(root, label, metric):
    run = _run_dir(root, label, metric)
    results = {}
    for line in (run / "records.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "METRIC_RESULT":
            results[record["metric_id"]] = {
                "publication": record["publication"], "value": record.get("value"),
                "reason_code": record["reason_code"], "result_id": record["result_id"]}
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    return {"results": results, "run_id": manifest.get("run_id"),
            "requirement_closure_hash": manifest.get("requirement_closure_hash")
            or manifest.get("requirement", {}).get("requirement_closure_hash")}


def main():
    targeted, batch, output = sys.argv[1:4]
    rows = []
    for label, metric in POSITIONS:
        matrix = json.loads((Path(targeted) / ("matrix-" + label + ".json")).read_text(
            encoding="utf-8"))
        replay = {p["metric_id"]: p.get("separate_process_replay") for p in matrix["positions"]}
        before, after = read(batch, label, metric), read(targeted, label, metric)
        rows.append({
            "position": label, "metric_id": metric, "batch": before, "targeted": after,
            "cold_read": replay.get(metric),
            "result_ids_unchanged": {m: before["results"].get(m, {}).get("result_id")
                                     == after["results"][m]["result_id"]
                                     for m in sorted(after["results"])}})
    body = {"record_type": "ISSUE_47_B03_TARGETED_RUNS",
            "batch_closure": rows[0]["batch"]["requirement_closure_hash"],
            "targeted_closure": rows[0]["targeted"]["requirement_closure_hash"],
            "rows": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    Path(output).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    for row in rows:
        new = row["targeted"]["results"][row["metric_id"]]
        print(row["position"], row["metric_id"], new["publication"], new["value"],
              new["reason_code"], row["result_ids_unchanged"])


if __name__ == "__main__":
    main()
