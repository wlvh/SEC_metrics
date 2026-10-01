"""Record one C02 selector repair's measured effect on the defects it touches.

``measure.py`` holds the selector before and after a repair to every judged
position. This writes what it found into ``known_result_defects.json`` for the
C02 coordinates the register keeps a selection record for (older years read in
c02-older-years, latest years withdrawn by the uniform adjudication):

* ``selection_problems`` - today's problems, block for block, which the filings
  test holds each latest position to;
* ``partial_repair[<key>]`` - for a position the repair moved, how many blocks
  it took or dropped, and where the repair is described;
* ``partial_repair.still_open`` and ``repair_state``.

It refuses a repair that takes a block nobody judged a fact, or drops one
somebody did (the reading's own verdict, or the adjudication where it decides):
such a repair is not one bounded problem. A position whose selection now agrees
stays withdrawn - its published result was computed by an earlier version - and
is marked so; it is released only by naming a recomputed, read result.

Usage:
    python3 docs/evidence/issue47_history/c02-selector-repairs/register.py \
        --measured <measured.json> --key <partial_repair key> --section <README section> \
        --text "<what moved, with %(added)d and %(removed)d>"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from tools import read_c02_composition as reading  # noqa: E402

REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"
KEPT = ("_OLDER_YEAR_READING_DISAGREES", "_UNIFIED_ADJUDICATION_DISAGREES")


def _fact(position, index, verdict, adjudications):
    decided = adjudications.get((position, index))
    if decided is not None:
        return decided["decision"] == "FACT"
    return verdict in ("FACT", "MIXED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--measured", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--text", required=True)
    args = parser.parse_args(argv)
    measured = json.loads(args.measured.read_text(encoding="utf-8"))
    evidence = str(args.measured.resolve().relative_to(REPO))
    adjudications = reading.load_adjudications()
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    touched = 0
    for entry in register["defects"]:
        if entry.get("metric_id") != "C02" or not entry["defect_id"].endswith(KEPT):
            continue
        position = entry["company_id"] + ":" + entry["period_end"]
        row = measured["positions"].get(position)
        if row is None:
            raise SystemExit("C02_REPAIR_POSITION_NOT_MEASURED:" + position)
        moved = row["moved"]
        added = sorted(int(i) for i, v in moved.items() if v["moved"] == "ADDED")
        dropped = sorted(int(i) for i, v in moved.items() if v["moved"] == "REMOVED")
        verdicts = {int(i): v["reading"] for i, v in moved.items()}
        wrong = [i for i in added if not _fact(position, i, verdicts[i], adjudications)]
        wrong += [i for i in dropped if _fact(position, i, verdicts[i], adjudications)]
        if wrong:
            raise SystemExit("C02_REPAIR_MOVES_A_BLOCK_AGAINST_THE_READING:" + position + ":" + str(wrong))
        problems = {kind: sorted(blocks) for kind, blocks in row["problems_working"].items() if blocks}
        entry["selection_problems"] = problems
        part = entry.setdefault("partial_repair", {})
        if moved:
            part[args.key] = (args.text % {"added": len(added), "removed": len(dropped)}
                              + " (docs/evidence/issue47_history/c02-selector-repairs/README.md section "
                              + args.section + " [shared-with-#28]).")
            if evidence not in entry["evidence"]:
                entry["evidence"].append(evidence)
            touched += 1
        missed, taken = problems.get("missed", []), problems.get("wrongly_taken", [])
        if not problems:
            entry["repair_state"] = "SELECTION_AGREES_RESULT_NOT_RECOMPUTED"
            part["still_open"] = ("Today's selection agrees with the reading. The withdrawn result was computed by an "
                                  "earlier version; it stays withdrawn until a result is recomputed, read against this "
                                  "reading and released by result_id.")
        else:
            if moved:
                entry["repair_state"] = "PARTLY_REPAIRED_SELECTION_STILL_DISAGREES"
            part["still_open"] = (
                "%d fact block(s) missed (%s) and %d block(s) taken that state no composition fact (%s); the "
                "selection still disagrees with the reading, so the coordinate stays withdrawn."
                % (len(missed), ", ".join(map(str, missed)) or "none", len(taken), ", ".join(map(str, taken)) or "none"))
        print(entry["defect_id"], "moved" if moved else "-", problems)
    REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("entries moved by this repair:", touched)


if __name__ == "__main__":
    main()
