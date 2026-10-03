"""Name a released repair for a run's own version when the run reproduced the repaired result.

A coordinate-level defect stops withdrawing only where its ``released`` block
names the repaired result by result_id and the Requirement closure it was
produced under (``known_result_defects.json``'s release rule). A later run
under another closure that produces the same result_id - the same value and
identity - carries a result the release already covers in substance but not
by version, so the frame withdraws it. This names the release for that
version, the way ``26017bed`` did for the earlier twelve-period batch, and
only where every condition holds:

- the defect is coordinate-level (an entry naming a result_id withdraws exactly
  that result and is never released);
- some existing release names this exact result_id;
- the run's Run directory, row receipt and matrix row all agree on the
  result_id, the run_id and the closure, and the row receipt's row hash is the
  one recorded here.

Nothing else is released: an open defect (no release) stays open, and a
different result_id at a released coordinate stays withdrawn. The reading a
new entry points to is the one the existing release for that result_id names.

The fifty-period batch (2026-10-01, closure 500ddf5f) writes one matrix per
period directory, so the matrices are read from every subdirectory; and an
existing release names who read the result either as ``read_by`` or as
``accepted_by`` with its ``reading``, so either is carried. A coordinate where
another entry still withdraws the batch's result (Southwest FY2022 and
FY2023 D01, whose merged headings a later entry withdraws for their span
records) is left as it is: naming a release there would describe a result
the register still holds to be wrong.

Usage:
    python3 name_version_releases.py <runs root> <matrix directory> <evidence path> [--write]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"
RUNS, MATRICES, EVIDENCE = (Path(argument) for argument in sys.argv[1:4])
WRITE = "--write" in sys.argv[4:]


def rows():
    """(company, metric, end) -> matrix row, for every frozen public row the matrices record."""
    found = {}
    for matrix in sorted(MATRICES.glob("*/matrix-*.json")):
        if ".part" in matrix.name:
            continue
        for row in json.loads(matrix.read_text())["positions"]:
            if row["stage"] == "PUBLIC_ROW":
                key = (row["company_id"], row["metric_id"], row["report_end"])
                if key in found:
                    raise SystemExit("A_POSITION_APPEARS_TWICE:" + str(key))
                found[key] = row
    return found


def receipt_for(row):
    """The row receipt beside the Run, checked against the matrix row it must describe."""
    name = "run-" + row["case"] + "-" + row["metric_id"]
    receipt = json.loads((RUNS / (name + ".row_receipt.json")).read_text())["receipt"]
    manifest = json.loads((RUNS / name / "manifest.json").read_text())
    if not (receipt["result_id"] == row["result_id"] and receipt["run_id"] == row["run_id"]
            == manifest["run_id"] and row["requirement_closure_hash"]
            == manifest["requirement_closure_hash"]):
        raise SystemExit("THE_RUN_ITS_RECEIPT_AND_ITS_ROW_DISAGREE:" + name)
    return receipt


def withdraws(defect, key, row):
    """Does this entry withdraw the batch's result at ``key``, by the register's rule?"""
    if defect.get("result_id") is not None:
        return defect["result_id"] == row["result_id"]
    if (defect.get("company_id"), defect.get("metric_id"), defect.get("period_end")) != key:
        return False
    released = defect.get("released") or []
    released = [released] if isinstance(released, dict) else released
    return not any(entry.get("result_id") == row["result_id"]
                   and entry.get("requirement_closure_hash") == row["requirement_closure_hash"]
                   for entry in released)


def main():
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    found = rows()
    named, kept_open, different, withdrawn_elsewhere = [], [], [], []
    for defect in register["defects"]:
        # The register's coordinate is (company_id, metric_id, period_end), and a
        # coordinate-level entry carries result_id as null
        # (historical_coverage._matching_defect).
        if defect.get("result_id") is not None or "metric_id" not in defect:
            continue
        key = (defect["company_id"], defect["metric_id"], defect["period_end"])
        row = found.get(key)
        if row is None:
            continue
        released = defect.get("released") or []
        if not released:
            kept_open.append(defect["defect_id"])
            continue
        same = [entry for entry in released if entry["result_id"] == row["result_id"]]
        if not same:
            different.append(defect["defect_id"])
            continue
        closure = row["requirement_closure_hash"]
        if any(entry["requirement_closure_hash"] == closure for entry in same):
            continue
        others = [other["defect_id"] for other in register["defects"]
                  if other is not defect and withdraws(other, key, row)]
        if others:
            withdrawn_elsewhere.append({"defect_id": defect["defect_id"], "also_withdrawn_by": others})
            continue
        receipt = receipt_for(row)
        read = ({"read_by": same[-1]["read_by"]} if "read_by" in same[-1] else
                {name: same[-1][name] for name in ("accepted_by", "reading", "reading_sha256") if name in same[-1]})
        entry = {"result_id": row["result_id"], "requirement_closure_hash": closure,
                 "run_id": row["run_id"], "public_row_hash": receipt["row_hash"], **read,
                 "what_this_releases": ("The same result - the same result_id, so the same value "
                                        "and identity - produced again under this version; named "
                                        "for that version on its own."),
                 "what_it_does_not_assert": ("that any position outside " + EVIDENCE.as_posix()
                                             + " ran under this version, or anything about results "
                                             "with another result_id.")}
        released.append(entry)
        named.append({"defect_id": defect["defect_id"], "result_id": row["result_id"],
                      "closure": closure})
    print(json.dumps({"named": named, "open_defects_left_withdrawing": kept_open,
                      "released_coordinates_with_another_result": different,
                      "left_as_withdrawn_by_another_entry": withdrawn_elsewhere}, indent=1))
    if WRITE and named:
        REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")


if __name__ == "__main__":
    main()
