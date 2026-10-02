"""JPMorgan's D02 defects against the round's recomputed results: which causes the repairs closed.

Usage (from the repository root): python3 jpm_d02_recheck.py <out.json> [--update-register]

Each JPMorgan D02 defect lists the blocks the held-out reading judged wrong and
the cause of each. The round recomputed the five results with the statement-range
and facing-page repairs, and the held-out readings were carried to the new
selections (tools/read_d02_excerpts.py --carry; d02-older-years/carried/). This
reads, for every registered block, what the carried reading now says of it,
and every problem the carried reading has that the defect does not list. A
cause is closed only when each of its blocks is no longer taken. The defects
stay registered: the result is not released while any block is still wrong.
With --update-register, each defect records the recomputed result, the carried
reading and the per-cause state; nothing else in the register changes. Zero calls.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"
CARRIED = REPO / "docs/evidence/issue47_history/d02-older-years/carried"
ROUND = HERE / "rerun-results.json"
WRONG = {"NOT_DISCLOSURE", "WRONGLY_SKIPPED", "MISSED"}


def main(out, update):
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    runs = {(row["company_id"], row["report_end"]): row
            for row in json.loads(ROUND.read_text(encoding="utf-8"))["positions"]
            if row["metric_id"] == "D02" and row.get("stage") == "PUBLIC_ROW"}
    report = {}
    for defect in register["defects"]:
        if not (defect.get("company_id") == "jpmorgan_chase" and defect.get("metric_id") == "D02"
                and defect.get("result_id") is None and "the_blocks" in defect):
            continue
        end = defect["period_end"]
        path = CARRIED / ("jpmorgan_chase-" + end + ".json")
        reading = json.loads(path.read_text(encoding="utf-8"))
        rows = {}
        for row in reading["judgements"]:
            if row["kind"] != "HEADING":
                rows.setdefault(row["i"], []).append(row)
        registered = {block["block_index"] for block in defect["the_blocks"]}
        per_cause = {}
        for block in defect["the_blocks"]:
            now = [(row["kind"], row["verdict"]) for row in rows.get(block["block_index"], [])]
            still = any(kind == "TAKEN" and verdict == "NOT_DISCLOSURE" for kind, verdict in now)
            cause = per_cause.setdefault(block["cause"], {"closed": [], "still_wrong": []})
            cause["closed" if not still else "still_wrong"].append(
                {"i": block["block_index"], "now": now or "NOT_IN_THE_PACKET"})
        unregistered = [{"i": row["i"], "kind": row["kind"], "verdict": row["verdict"]}
                        for row in reading["judgements"]
                        if row["verdict"] in WRONG and row["i"] not in registered]
        run = runs[("jpmorgan_chase", end)]
        report[end] = {
            "result_id": run["result_id"], "run_id": run["run_id"],
            "requirement_closure_hash": run["requirement_closure_hash"],
            "carried_reading": str(path.relative_to(REPO)),
            "carried_reading_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            "per_cause": per_cause, "problems_the_defect_does_not_list": unregistered}
        if update:
            for name, cause in per_cause.items():
                if not cause["still_wrong"]:
                    defect["causes"][name]["repair_state"] = "ROUTE_REPAIRED_RECOMPUTED_AND_READ"
            defect["repair_state"] = " + ".join(
                defect["causes"][name]["repair_state"] for name in sorted(defect["causes"]))
            defect["recomputed_and_read"] = {
                "result_id": run["result_id"], "run_id": run["run_id"],
                "requirement_closure_hash": run["requirement_closure_hash"],
                "carried_reading": report[end]["carried_reading"],
                "carried_reading_sha256": report[end]["carried_reading_sha256"],
                "still_wrong": sorted(b["i"] for c in per_cause.values() for b in c["still_wrong"]),
                "what_this_releases": "nothing: the recomputed result still takes the blocks listed in still_wrong"}
    Path(out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if update:
        REGISTER.write_text(json.dumps(register, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for end, row in sorted(report.items()):
        print(end, {name: (len(c["closed"]), len(c["still_wrong"])) for name, c in row["per_cause"].items()},
              "unregistered", len(row["problems_the_defect_does_not_list"]))


if __name__ == "__main__":
    main(sys.argv[1], "--update-register" in sys.argv[2:])
