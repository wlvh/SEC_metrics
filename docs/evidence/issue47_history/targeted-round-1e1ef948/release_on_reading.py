"""Release this round's open D02 coordinate defects on the results a reading accepted.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/targeted-round-1e1ef948/release_on_reading.py <acceptance> [--write]

For each MATCH position of the acceptance reading, every coordinate-level D02
entry at that coordinate (``result_id`` null) gets one release naming the
result the reading checked - its ``result_id``, the closure it was produced
under and its run - with the reading and its hash. A MATCH means the reading
judged every taken, skipped, context and heading block of that result and
found none wrong or missing, so no listed block of any of these entries is in
it. Entries naming a result_id are never released, a release already present
is not added twice, and a position that does not match releases nothing.
Dry run unless --write.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"


def main(acceptance, *flags):
    body = json.loads((REPO / acceptance).read_text(encoding="utf-8"))
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    added = []
    for label, row in sorted(body["per_position"].items()):
        if row["verdict"] != "MATCH":
            continue
        bound = row["checked_identity"]["bound_from"]
        if bound["requirement_closure_hash"] != body["requirement_closure_hash"]:
            raise SystemExit("RELEASE_CLOSURE_DIFFERS:" + label)
        for entry in register["defects"]:
            if (entry["metric_id"], entry["company_id"], entry["period_end"]) != (
                    "D02", row["company_id"], row["period_end"]) or entry.get("result_id") is not None:
                continue
            released = entry.setdefault("released", [])
            if any((item["result_id"], item["requirement_closure_hash"])
                   == (bound["result_id"], bound["requirement_closure_hash"]) for item in released):
                continue
            released.append({
                "result_id": bound["result_id"],
                "requirement_closure_hash": bound["requirement_closure_hash"],
                "run_id": bound["run_id"],
                "accepted_by": acceptance + " (" + label + ": READING_AGREES, MATCH)",
                "reading": row["reading"], "reading_sha256": row["reading_sha256"],
                "what_this_releases": (
                    "this entry, for this result under this version only: the targeted round's "
                    "recomputed result, whose excerpts the reading judged in both directions with "
                    "nothing wrong or missing. Any other result at this coordinate stays withdrawn by it.")})
            if "NOT_YET_RECOMPUTED" in str(entry.get("repair_state")):
                entry["repair_state"] = entry["repair_state"].replace("NOT_YET_RECOMPUTED", "RECOMPUTED_AND_READ")
            added.append((label, entry["defect_id"]))
    for label, defect_id in added:
        print(label, defect_id)
    if "--write" in flags:
        REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(added), "releases", "written" if "--write" in flags else "(dry run)")


if __name__ == "__main__":
    main(*sys.argv[1:])
