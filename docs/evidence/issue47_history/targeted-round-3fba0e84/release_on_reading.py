"""Release JPMorgan's D01 running-header entries on the results a reading accepted.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/targeted-round-3fba0e84/release_on_reading.py <reading> [--write]

For each MATCH position of the D01 reading, every coordinate-level D01 entry at
that coordinate (``result_id`` null) whose defect is the running header gets one
release naming the result the reading checked - its ``result_id``, the closure
it was produced under and its run - with the reading and its hash. A MATCH means
every published line was read as a heading off the filing's own bytes, in order,
under the recorded judgements, and no marked block was left unjudged. Entries
naming a result_id are never released, a release already present is not added
twice, and a position that does not match releases nothing. The batch results
that carry the running header stay withdrawn: the release names only the new
result. Dry run unless --write.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"
DEFECT_SUFFIX = "_RUNNING_HEADER_PARTS_I_AND_II_TAKEN_AS_A_HEADING"


def main(*arguments):
    flags = [a for a in arguments if a.startswith("--")]
    readings = [a for a in arguments if not a.startswith("--")]
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    added, open_left = [], []
    for reading in readings:
        raw = (REPO / reading).read_bytes()
        body = json.loads(raw.decode("utf-8"))
        if body["record_type"] != "ISSUE_47_D01_HEADINGS_READ_FROM_BYTES":
            raise SystemExit("NOT_A_D01_READING:" + reading)
        for label, row in sorted(body["per_position"].items()):
            entries = [entry for entry in register["defects"]
                       if (entry["metric_id"], entry["company_id"], entry["period_end"])
                       == ("D01", row["company_id"], row["period_end"])
                       and entry.get("result_id") is None
                       and entry["defect_id"].endswith(DEFECT_SUFFIX)]
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
                    "accepted_by": reading + " (" + label + ": READING_AGREES, MATCH)",
                    "reading_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "judgements_file": row["judgements_file"],
                    "what_this_releases": (
                        "this entry, for this result under this version only: the targeted round's "
                        "result after the running-header successor (e14d3ca9), whose lines the "
                        "reading read as the filing's headings in order. The batch result that "
                        "carries the running header stays withdrawn by it.")})
                state = str(entry.get("repair_state"))
                if state == "ROOT_CAUSE_MEASURED_NOT_REPAIRED":
                    entry["repair_state"] = "RULE_FIXED_RESULT_RECOMPUTED_AND_READ"
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
