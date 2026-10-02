"""Release this round's open C02 coordinate defects on the results a reading accepted.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/targeted-round-cf166529/release_on_reading.py <acceptance>... [--write]

For each MATCH position of each C02 acceptance reading, every coordinate-level
C02 entry at that coordinate (``result_id`` null) gets one release naming the
result the reading checked - its ``result_id``, the closure it was produced
under and its run - with the reading and its hash. A MATCH means no selected
block is judged outside the meaning and no fact the reader found is missed,
under the recorded adjudication, and that the Run's candidate is the selection
recomputed from the filing. Entries naming a result_id are never released, a
release already present is not added twice, and a position that does not match
releases nothing: its entry stays open with its state. Dry run unless --write.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"


def main(*arguments):
    flags = [a for a in arguments if a.startswith("--")]
    readings = [a for a in arguments if not a.startswith("--")]
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    added, open_left = [], []
    for acceptance in readings:
        body = json.loads((REPO / acceptance).read_text(encoding="utf-8"))
        if body["record_type"] != "ISSUE_47_C02_COMPOSITION_READ":
            raise SystemExit("NOT_A_C02_COMPOSITION_READING:" + acceptance)
        for label, row in sorted(body["per_position"].items()):
            entries = [entry for entry in register["defects"]
                       if (entry["metric_id"], entry["company_id"], entry["period_end"])
                       == ("C02", row["company_id"], row["period_end"])
                       and entry.get("result_id") is None]
            if row["verdict"] != "MATCH":
                open_left.extend((label, entry["defect_id"]) for entry in entries)
                continue
            bound = row["checked_identity"]["bound_from"]
            if bound["requirement_closure_hash"] != body["requirement_closure_hash"]:
                raise SystemExit("RELEASE_CLOSURE_DIFFERS:" + label)
            for entry in entries:
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
                    "adjudication_sha256": body["adjudication_sha256"],
                    "what_this_releases": (
                        "this entry, for this result under this version only: the targeted round's "
                        "result, whose excerpts the reading found within the meaning with no fact "
                        "missed under the recorded adjudication. Any other result at this coordinate "
                        "stays withdrawn by it.")})
                state = str(entry.get("repair_state"))
                if state.endswith("RESULT_NOT_RECOMPUTED"):
                    entry["repair_state"] = state[:-len("RESULT_NOT_RECOMPUTED")] + "RESULT_RECOMPUTED_AND_READ"
                elif "STILL_DISAGREES" in state:
                    raise SystemExit("A_MATCH_ON_AN_ENTRY_RECORDED_AS_STILL_DISAGREEING:" + entry["defect_id"])
                added.append((label, entry["defect_id"]))
    for label, defect_id in added:
        print("released", label, defect_id)
    for label, defect_id in open_left:
        print("left open", label, defect_id)
    if "--write" in flags:
        REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(added), "releases", len(open_left), "left open",
          "written" if "--write" in flags else "(dry run)")


if __name__ == "__main__":
    main(*sys.argv[1:])
