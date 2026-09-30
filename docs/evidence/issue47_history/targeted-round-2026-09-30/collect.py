"""Collect the two targeted rounds of 2026-09-30 and compare them position by position.

Usage: python3 collect.py <round-2 directory> <round-3 directory> <out.json>

The frame driver writes one directory per period; every matrix-*.json under a
round is read, each frozen position's separate-process read-back must name the
same run and result, and the positions both rounds ran are compared by value
and result id. Nothing is re-run and nothing is called.
"""
import json
import sys
from pathlib import Path

KEEP = ("case", "company_id", "metric_id", "report_end", "stage", "quality", "publication",
        "reason_code", "result_id", "run_id", "requirement_closure_hash", "evidence_count",
        "error", "error_type", "category")


def collect(directory):
    positions, problems, calls = [], [], {"provider": 0, "paid": 0, "sec": 0}
    for path in sorted(Path(directory).glob("*/matrix-*.json")):
        matrix = json.loads(path.read_text(encoding="utf-8"))
        for name in calls:
            calls[name] += matrix["calls"][name]
        for position in matrix["positions"]:
            row = {key: position[key] for key in KEEP if key in position}
            value = position.get("value")
            if isinstance(value, str) and len(value) > 60:
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
                    problems.append(row)
            positions.append(row)
    return {"positions": positions, "position_count": len(positions),
            "public_rows": sum(row.get("stage") == "PUBLIC_ROW" for row in positions),
            "requirement_closure_hashes": sorted({row["requirement_closure_hash"] for row in positions
                                                  if row.get("requirement_closure_hash")}),
            "calls": calls, "read_back_problems": problems}


def main(second, third, out):
    rounds = {"round_2": collect(second), "round_3": collect(third)}
    key = lambda row: (row["case"], row["metric_id"])
    earlier = {key(row): row for row in rounds["round_2"]["positions"]}
    compared = []
    for row in rounds["round_3"]["positions"]:
        before = earlier.get(key(row))
        if before is None:
            continue
        compared.append({"case": row["case"], "metric_id": row["metric_id"],
                         "same_result_id": before.get("result_id") == row.get("result_id"),
                         "same_value": (before.get("value"), before.get("value_characters"))
                         == (row.get("value"), row.get("value_characters")),
                         "same_reason_code": before.get("reason_code") == row.get("reason_code")})
    record = {"record_type": "ISSUE_47_TARGETED_ROUNDS", **rounds,
              "positions_in_both_rounds": compared,
              "differing_between_rounds": [item for item in compared
                                           if not (item["same_result_id"] and item["same_value"])]}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(json.dumps({name: {k: v for k, v in body.items() if k != "positions"}
                      for name, body in rounds.items()}, indent=1))
    print("in both:", len(compared), "differing:", record["differing_between_rounds"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
