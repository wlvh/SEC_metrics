"""Name a repaired defect's release for a result that a committed reading read MATCH.

A coordinate-level defect stops withdrawing only where its ``released`` block
names the repaired result by result_id and the Requirement closure it was
produced under (``known_result_defects.json``'s release rule).
``native-run-batch-2026-09-27/name_version_releases.py`` names a release for a
later version that reproduced the same result_id. A later version can also
produce the repaired content under another result_id - D01's Spec moved from v1
to v2, which only raised the item bound from 64 to 192, and the result's
identity moved with it while its lines did not. Such a result is released only
by a reading of it, and only where every condition holds:

- the defect is coordinate-level and already released for some result, so its
  repair has been made and read once (an open defect is not decided here);
- a committed reading's row for the coordinate reads MATCH and records, in its
  ``checked_identity.bound_from``, that it checked this result_id, run_id and
  closure;
- the Run directory's manifest and its row receipt name the same run_id,
  result_id and closure.

Nothing else is released: a coordinate whose reading is not MATCH stays
withdrawn, and so does every other result at a released coordinate.

Usage:
    python3 release_on_reading.py <runs root> <reading> [<reading> ...] [--write]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"


def _run_for(runs_root, bound):
    """The Run directory whose manifest carries this run_id, and its row receipt."""
    for manifest_path in sorted(runs_root.glob("run-*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["run_id"] != bound["run_id"]:
            continue
        receipt = json.loads(manifest_path.parent.with_name(
            manifest_path.parent.name + ".row_receipt.json").read_text(encoding="utf-8"))["receipt"]
        if not (manifest["requirement_closure_hash"] == bound["requirement_closure_hash"]
                and receipt["run_id"] == bound["run_id"]
                and receipt["result_id"] == bound["result_id"]):
            raise SystemExit("THE_RUN_ITS_RECEIPT_AND_THE_READING_DISAGREE:"
                             + manifest_path.parent.name)
        return manifest_path.parent.name, receipt
    raise SystemExit("NO_RUN_CARRIES:" + bound["run_id"])


def main(argv):
    write = "--write" in argv
    arguments = [argument for argument in argv if argument != "--write"]
    runs_root, readings = Path(arguments[0]), arguments[1:]
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    by_coordinate = {}
    for defect in register["defects"]:
        if defect.get("result_id") is None and "metric_id" in defect:
            key = (defect["company_id"], defect["metric_id"], defect["period_end"])
            by_coordinate.setdefault(key, []).append(defect)
    named, not_released = [], []
    for reading in readings:
        body = json.loads((REPO / reading).read_text(encoding="utf-8"))
        for label, row in sorted(body["per_position"].items()):
            metric = row["checked_identity"].get("metric_id", "D01")
            for defect in by_coordinate.get((row["company_id"], metric, row["period_end"]), []):
                released = defect.get("released") or []
                bound = row["checked_identity"]["bound_from"]
                if not released or row["verdict"] != "MATCH":
                    not_released.append({"defect_id": defect["defect_id"], "label": label,
                                         "why": ("OPEN_DEFECT" if not released
                                                 else "READING_IS_NOT_MATCH")})
                    continue
                if any(entry["result_id"] == bound["result_id"] and entry[
                        "requirement_closure_hash"] == bound["requirement_closure_hash"]
                       for entry in released):
                    continue
                run_name, receipt = _run_for(runs_root, bound)
                released.append({
                    "result_id": bound["result_id"],
                    "requirement_closure_hash": bound["requirement_closure_hash"],
                    "run_id": bound["run_id"], "public_row_hash": receipt["row_hash"],
                    "read_by": reading,
                    "what_this_releases": (
                        "This result: the reading reads its lines off the filing, one by one "
                        "under the recorded judgements, and they are the published lines in "
                        "order. Its result_id differs from the results released before because "
                        "D01's Spec moved from v1 to v2 (the item bound only), not its lines."),
                    "what_it_does_not_assert": (
                        "anything about another result at this coordinate, or that any other "
                        "position ran under this version.")})
                named.append({"defect_id": defect["defect_id"], "label": label,
                              "run": run_name, "result_id": bound["result_id"],
                              "closure": bound["requirement_closure_hash"]})
    print(json.dumps({"named": named, "not_released": not_released}, indent=1))
    if write and named:
        REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
