"""Compare the parallel receipt's injections with the sequential baseline, injection by injection.

The owner's contract change (Issue #47 comment 5870869079) accepts parallel
sealing when the same injections are caught by the same named cases as the
sequential run. The baseline is the 2026-09-28 sequential run's 66 rows
(``sequential-interrupted-2026-09-28.log``; the container restarted during the
67th) and the other 12 run one after another in one copy
(``sequential-completion-2026-09-28.json``). For every injection this compares
the outcome, the expected class's outcome, whether the whole suite had to run,
and the cases that caught it; the fields that only a parallel row has - which
copy ran it and how long it took - are not compared.

    python3 docs/evidence/issue47_history/model-egress/compare_with_sequential.py [<out.json>]

Exits 0 only if every injection has exactly one row on each side and every row
agrees.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPARED = ("outcome", "expected_class", "expected_class_outcome", "whole_suite_run", "first_caught_by")


def main():
    receipt = json.loads((HERE / "offline-verification.json").read_text(encoding="utf-8"))
    interrupted = [json.loads(line) for line in
                   (HERE / "sequential-interrupted-2026-09-28.log").read_text().splitlines()
                   if line.startswith("{")]
    completion = json.loads((HERE / "sequential-completion-2026-09-28.json").read_text(encoding="utf-8"))
    baseline = interrupted + completion["rows"]
    parallel = receipt["fault_injections"]
    names = [row["id"] for row in parallel]
    report = {"record_type": "ISSUE_47_EGRESS_PARALLEL_VERSUS_SEQUENTIAL",
              "receipt_id": receipt["receipt_id"],
              "baseline": {"sequential_interrupted_rows": len(interrupted),
                           "sequential_completion_rows": len(completion["rows"])},
              "compared_fields": list(COMPARED), "rows": [], "calls": {"provider": 0, "paid": 0, "sec": 0}}
    problems = []
    if sorted(names) != sorted(row["id"] for row in baseline) or len(set(names)) != len(names) \
            or len(baseline) != len({row["id"] for row in baseline}):
        problems.append("THE_TWO_SIDES_DO_NOT_HOLD_THE_SAME_INJECTIONS_ONCE_EACH")
    by_id = {row["id"]: row for row in baseline}
    for row in parallel:
        other = by_id.get(row["id"], {})
        differs = [field for field in COMPARED if row.get(field) != other.get(field)]
        report["rows"].append({"id": row["id"], "same": not differs, "differs_in": differs,
                               "parallel_copy": row.get("copy"), "parallel_seconds": row.get("seconds"),
                               "first_caught_by": row.get("first_caught_by")})
        if differs:
            problems.append(row["id"] + ":" + ",".join(differs))
    report["same"] = sum(1 for row in report["rows"] if row["same"])
    report["problems"] = problems
    report["accepted"] = not problems
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    print(json.dumps({"same": report["same"], "of": len(parallel), "problems": problems}))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
