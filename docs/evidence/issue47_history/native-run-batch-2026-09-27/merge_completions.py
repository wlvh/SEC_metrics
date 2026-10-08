"""Merge the completion invocations of an interrupted batch period back into its matrix.

The batch hit its 10-hour timeout with Paramount FY2024 at E05 and Enphase
FY2025 at A07. The interrupted positions' partial directories were removed and
re-run in their own output directories under the same label and runtime tree;
this puts their Run directories and row receipts back beside the others and
writes each period's matrix as the union of its invocations' rows, in plan
order, each plan position exactly once. The rows are the driver's own records,
unedited; the matrix records which invocation wrote each row.

Usage: python3 merge_completions.py <batch directory>
"""
import json
import shutil
import sys
from pathlib import Path

BATCH = Path(sys.argv[1])
PARTS = {"paramount-2024": ["complete-p24"], "enphase-2025": ["complete-e1", "complete-e2"]}


def main():
    plan = {line.split("\t")[0]: line.split("\t")[3].split(",")
            for line in (BATCH / "plan.tsv").read_text().splitlines()}
    for label, parts in PARTS.items():
        first = json.loads((BATCH / ("matrix-" + label + ".part1.json")).read_text())
        invocations = [{"output_directory": ".", "rows": len(first["positions"]),
                        "duration_seconds": first["duration_seconds"],
                        "ended": "BATCH_TIMEOUT_10_HOURS"}]
        rows = {row["metric_id"]: dict(row, invocation=0) for row in first["positions"]}
        for index, part in enumerate(parts, start=1):
            directory = BATCH / part
            matrix = json.loads((directory / ("matrix-" + label + ".json")).read_text())
            invocations.append({"output_directory": part, "rows": len(matrix["positions"]),
                                "duration_seconds": matrix["duration_seconds"], "ended": "COMPLETED"})
            for row in matrix["positions"]:
                if row["metric_id"] in rows:
                    raise SystemExit("A_POSITION_RAN_TWICE:" + label + ":" + row["metric_id"])
                rows[row["metric_id"]] = dict(row, invocation=index)
                for name in ("run-" + label + "-" + row["metric_id"],
                             "run-" + label + "-" + row["metric_id"] + ".row_receipt.json"):
                    source = directory / name
                    if source.exists():
                        if (BATCH / name).exists():
                            raise SystemExit("A_RUN_DIRECTORY_EXISTS_ALREADY:" + name)
                        shutil.move(str(source), str(BATCH / name))
        missing = [metric for metric in plan[label] if metric not in rows]
        extra = sorted(set(rows) - set(plan[label]))
        if missing or extra:
            raise SystemExit("THE_PERIOD_IS_NOT_ITS_PLAN:" + label + ":" + str(missing) + str(extra))
        merged = {"positions": [rows[metric] for metric in plan[label]],
                  "duration_seconds": round(sum(i["duration_seconds"] for i in invocations), 1),
                  "invocations": invocations, "calls": {"provider": 0, "paid": 0, "sec": 0}}
        (BATCH / ("matrix-" + label + ".json")).write_text(
            json.dumps(merged, indent=1, sort_keys=True, default=str) + "\n")
        print(label, len(merged["positions"]), [i["rows"] for i in invocations])


if __name__ == "__main__":
    main()
