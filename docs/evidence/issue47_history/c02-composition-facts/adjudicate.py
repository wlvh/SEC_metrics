"""Write the executor's C02 adjudications where independent readers split.

Two classes of block were judged one way by some readers and the other way by
others. Each is decided by one rule, applied to every block of the class in
every reading, not to the blocks that happen to disagree with the route:

CARD_TENURE_FIELD (decision NOT)
    A director card's "Director since: 2017" / "Joined the Board: 2025" field.
    Three readers judged these facts, six left them out. The owner's meaning
    lists board size, independence, committee setup, members, chairs and the
    related independence and qualification determinations; how long a sitting
    director has served is none of these. A dated change in who sits on the
    board is a different statement and is read where the filing states it.

CARD_SUBJECT_NAME (decision FACT)
    The name on a director card whose committee or designation fields the
    route takes. A card field ("NCG (Chair)", "Independent") says nothing
    without whose card it is. Three readers judged such names facts; three
    left the name out and judged the field, naming the person in their own
    reason. Only a name whose surname the same reader wrote in the reason for
    another block the route takes is decided here; any other is left to the
    readings.

Older years' filings are read from a root restored from the acquisition's
export by this checkout (``--source-root``); the latest years' filings are in
that root too, because a restored root starts as a copy of this checkout's
saved sources.

Usage:
    python3 docs/evidence/issue47_history/c02-composition-facts/adjudicate.py [--source-root <root>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from tools import read_c02_composition as reading  # noqa: E402
from vnext.historical_board_composition import board_composition_facts, _strip_name  # noqa: E402

HERE = Path(__file__).resolve().parent
TENURE = re.compile(r"^\s*(?:director since|joined the board)\s*:?", re.I)
RULES = {
    "CARD_TENURE_FIELD": ("NOT", "Tenure of a sitting director is not in the owner's meaning (size, independence, "
                                 "committee setup, members, chairs, related determinations); readers split 3 FACT, "
                                 "6 left out."),
    "CARD_SUBJECT_NAME": ("FACT", "A card field states nothing without whose card it is; the same reader named this "
                                  "person in the reason for a card field the route takes."),
}


def decisions_for(position, document, record, chosen_labels):
    blocks = document["blocks"]
    judged = [*record["selected"], *record["pool_facts"], *record.get("outside_pool_facts", []),
              *record.get("supplementary", [])]
    out = []
    for row in judged:
        text = blocks[row["i"]]["text"]
        if row["verdict"] in ("FACT", "MIXED") and TENURE.match(text):
            out.append({"position": position, "i": row["i"], "text_sha256": reading.text_sha256(text),
                        "rule": "CARD_TENURE_FIELD", "decision": "NOT",
                        "reader_verdict": row["verdict"], "reader_why": row.get("why", "")[:200]})
    known = {row["i"] for row in judged}
    fields = [row for row in judged if row["verdict"] in ("FACT", "MIXED") and row["i"] in chosen_labels]
    for index, labels in sorted(chosen_labels.items()):
        if "DIRECTOR_NAME" not in labels or index in known:
            continue
        tokens = _strip_name(blocks[index]["text"]).replace(",", " ").split()
        surname = tokens[-1] if tokens else ""
        # A name broken over two blocks ("James D." / "Farley, Jr."): the
        # second block carries the surname.
        if index + 1 < len(blocks) and "DIRECTOR_NAME" in chosen_labels.get(index + 1, []):
            surname = _strip_name(blocks[index + 1]["text"]).replace(",", " ").split()[-1]
        if len(surname) < 3:
            continue
        cited = [row["i"] for row in fields
                 if abs(row["i"] - index) <= 12 and re.search(r"\b" + re.escape(surname) + r"\b", row.get("why", ""),
                                                              re.I)]
        if cited:
            out.append({"position": position, "i": index, "text_sha256": reading.text_sha256(blocks[index]["text"]),
                        "rule": "CARD_SUBJECT_NAME", "decision": "FACT", "surname": surname,
                        "fields_whose_reason_names_it": cited})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", type=Path, default=REPO)
    args = parser.parse_args(argv)
    decisions = []
    for path in sorted(reading.READING_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = record["position"].rsplit(":", 1)
        document, _chosen, _candidate = reading.route_selection(repo_root=REPO, company_id=company_id,
                                                                 report_end=report_end,
                                                                 source_root=args.source_root.resolve())
        proposal = board_composition_facts(document=document)
        chosen_labels = {c["block_index"]: c["labels"] for c in proposal["candidates"]}
        decisions.extend(decisions_for(record["position"], document, record, chosen_labels))
    out = {"record_type": "C02_COMPOSITION_ADJUDICATION",
           "decided_by": "executor, applying each rule to every block of its class",
           "rules": {name: {"decision": decision, "reason": reason} for name, (decision, reason) in RULES.items()},
           "decisions": decisions}
    (HERE / "adjudication.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts = {}
    for row in decisions:
        counts[row["rule"]] = counts.get(row["rule"], 0) + 1
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
