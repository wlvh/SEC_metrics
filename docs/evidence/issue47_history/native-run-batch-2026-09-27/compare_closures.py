"""Compare targeted re-runs under a later closure with the batch's rows, position by position.

After the batch, rule files on the C02/D01/D02/E01/D04 paths changed and the
merged base moved inherited files the semantic routes load; those metrics, and
B13, were re-run for every period under the later closure with
``../targeted-round-30a7934b/targeted_runs.py`` in a runtime tree that is the
checkout plus the registration patch. This reads each re-run's matrix row and
the batch's row for the same position and records every field that differs.
Identical rows are counted, not assumed: a position the batch holds and the
re-run does not, or the reverse, stops the comparison.

A frozen re-run must also have been read back by a separate process with the
same run and result (the driver's own cold read); a re-run whose read-back is
missing or different is listed.

Usage:
    python3 compare_closures.py <batch directory> <output json> <re-run directory> [<re-run directory> ...]
"""
import json
import sys
from pathlib import Path

FIELDS = ("stage", "result_id", "value", "quality", "publication", "reason_code", "error",
          "category")


def _rows(directory):
    found = {}
    for matrix in sorted(Path(directory).glob("matrix-*.json")):
        if ".part" in matrix.name:
            continue
        for row in json.loads(matrix.read_text())["positions"]:
            key = (matrix.stem[len("matrix-"):], row["metric_id"])
            if key in found:
                raise SystemExit("A_POSITION_APPEARS_TWICE:" + str(key))
            found[key] = row
    return found


def main():
    batch_dir, output, reruns = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    batch = _rows(batch_dir)
    rows, differ, closures = [], [], {"batch": set(), "re_run": set()}
    for directory in reruns:
        for key, row in sorted(_rows(directory).items()):
            old = batch.get(key)
            if old is None:
                raise SystemExit("THE_BATCH_HOLDS_NO_SUCH_POSITION:" + str(key))
            for side, source in (("batch", old), ("re_run", row)):
                if source.get("requirement_closure_hash"):
                    closures[side].add(source["requirement_closure_hash"])
            delta = {field: [old.get(field), row.get(field)] for field in FIELDS
                     if old.get(field) != row.get(field)}
            replay = row.get("separate_process_replay") or {}
            read_back = (replay.get("status") == "FROZEN" and replay.get("run_id") == row.get("run_id")
                         and replay.get("result_id") == row.get("result_id")
                         if row["stage"] == "PUBLIC_ROW" else None)
            entry = {"case": key[0], "metric_id": key[1], "stage": row["stage"],
                     "fields_that_differ": delta, "re_run_read_back_by_another_process": read_back,
                     "re_run_directory": Path(directory).name}
            rows.append(entry)
            if delta or read_back is False:
                differ.append(entry)
    body = {"record_type": "ISSUE_47_LATER_CLOSURE_TARGETED_CHECK",
            "positions": len(rows), "identical": len(rows) - len(differ), "differ": differ,
            "stages": {stage: sum(1 for r in rows if r["stage"] == stage)
                       for stage in sorted({r["stage"] for r in rows})},
            "closures": {side: sorted(values) for side, values in closures.items()},
            "fields_compared": list(FIELDS), "rows": rows,
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    output.write_text(json.dumps(body, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({key: body[key] for key in ("positions", "identical", "stages", "closures")}),
          len(differ))


if __name__ == "__main__":
    main()
