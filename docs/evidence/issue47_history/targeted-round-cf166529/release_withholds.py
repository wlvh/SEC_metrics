"""Name this round's version on releases already given to the same withheld results.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/targeted-round-cf166529/release_withholds.py [--write]

A release names a result and the closure it was produced under. This round
re-ran two coordinates whose defects were released on their withheld results
under closure 004c5771 (A05 JPMorgan FY2021, B02 Pfizer FY2021: the target
filing recasts the prior year under the same concept). The round produced the
same result ids, withheld for the same reason, under closure cf166529. For each
withheld position of this round whose coordinate-level defect already releases
the same result id, one release is added for this closure, with this round's
run and row - nothing else. A published position releases nothing here. Dry run
unless --write.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"
ROUND = HERE / "rerun-results.json"


def main(*flags):
    record = json.loads(ROUND.read_text(encoding="utf-8"))
    (closure,) = record["requirement_closure_hashes"]
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    added = []
    for position in record["positions"]:
        if position.get("stage") != "PUBLIC_ROW" or position.get("publication") == "PUBLISHED":
            continue
        if not position.get("separate_process_read_back_same_run_and_result"):
            raise SystemExit("WITHHELD_POSITION_NOT_READ_BACK:" + position["metric_id"])
        for entry in register["defects"]:
            if ((entry["metric_id"], entry["company_id"], entry["period_end"])
                    != (position["metric_id"], position["company_id"], position["report_end"])
                    or entry.get("result_id") is not None):
                continue
            released = entry.setdefault("released", [])
            earlier = [item for item in released if item["result_id"] == position["result_id"]]
            if not earlier or any(item["requirement_closure_hash"] == closure for item in earlier):
                continue
            released.append({
                "result_id": position["result_id"], "requirement_closure_hash": closure,
                "run_id": position["run_id"], "public_row_hash": position["row_hash"],
                "read_by": str(ROUND.relative_to(REPO)),
                "what_this_releases": (
                    "This withheld result under this version, as the release under "
                    + earlier[0]["requirement_closure_hash"][:15] + "... did under that one: "
                    + position["reason_code"] + ", frozen, public row written, read back by a "
                    "separate process. Any published value at this coordinate stays withdrawn."),
                "what_it_does_not_assert": earlier[0]["what_it_does_not_assert"]})
            added.append((position["metric_id"], position["company_id"], position["report_end"],
                          entry["defect_id"]))
    for item in added:
        print(*item)
    if "--write" in flags:
        REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(added), "releases", "written" if "--write" in flags else "(dry run)")


if __name__ == "__main__":
    main(*sys.argv[1:])
