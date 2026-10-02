"""How far the "a director is qualified to serve because ..." reading would move C02.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-composition-facts/qualification_narratives.py \
        <restored source root> <out.json>

#28 asked (Issue #47 comment 5945743839) whether a sentence such as Paramount
FY2025 block 168, "We believe Mr. Thornton is qualified to serve as a member of
our Board because of his extensive investment and management experience ...",
is a qualification determination C02 takes. Before answering, this counts what
taking such sentences would do on the 37 positions both directions were read
for (the ten latest years and the 27 older ones): for each governance document
the historical route selects, every block that states a director's
qualification to serve on the registrant's board, whether the route already
selects it, whether the readers judged it a fact, and whether the same block
also lists another organisation's board seats (which the Spec keeps out of
C02). Zero calls; the documents are the route's own, read from the saved bytes.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from read_c02_composition import route_selection  # noqa: E402

JUDGEMENTS = ("docs/evidence/issue47_history/c02-composition-facts/judgements",
              "docs/evidence/issue47_history/c02-older-years/judgements")
# The registrant concluding that a person is qualified to serve on its board,
# in the forms Item 401(e) narratives take in these filings.
QUALIFIED = re.compile(
    r"\b(?:qualified|well[- ]qualified|well[- ]suited)\s+to\s+serve\b"
    r"|\bqualifications?\s+to\s+serve\b"
    r"|\bshould\s+serve\s+as\s+a\s+(?:director|member)\b"
    r"|\bexperience,\s+qualifications,\s+attributes,?\s+(?:and|or)\s+skills\b", re.I)
# Another organisation's board seats named in the same block.
OTHER_BOARDS = re.compile(
    r"\b(?:serves?|served|serving)\s+(?:as\s+a\s+(?:director|member)\s+)?on\s+the\s+boards?\s+of\b"
    r"|\bdirector\s+on\s+the\s+boards?\s+of\b|\bboards?\s+of\s+directors\s+of\b(?!\s+(?:our|the)\s+Company)",
    re.I)


def _judged_facts(path):
    body = json.loads(path.read_text(encoding="utf-8"))
    facts = set()
    for collection in ("selected", "pool_facts", "outside_pool_facts"):
        for row in body.get(collection, []):
            if row.get("verdict") in ("FACT", "MIXED"):
                facts.add(row["i"])
    return facts


def main(source_root, out):
    # Each position is written as it is read, and a rerun skips what an
    # earlier run wrote: a run cut off by a time limit loses one position, not
    # all of them.
    partial = Path(str(out) + ".partial.jsonl")
    done = {}
    if partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["position"]] = row
    rows = []
    for folder in JUDGEMENTS:
        for path in sorted((REPO / folder).glob("*.json")):
            company_id, report_end = path.stem.rsplit("-", 3)[0], "-".join(path.stem.rsplit("-", 3)[1:])
            if company_id + ":" + report_end in done:
                rows.append(done[company_id + ":" + report_end])
                continue
            document, chosen, _ = route_selection(repo_root=REPO, company_id=company_id,
                                                  report_end=report_end,
                                                  source_root=Path(source_root))
            facts = _judged_facts(path)
            found = []
            for index, block in enumerate(document["blocks"]):
                if QUALIFIED.search(block["text"]):
                    found.append({"i": index, "selected": index in chosen,
                                  "judged_fact": index in facts,
                                  "names_other_boards": bool(OTHER_BOARDS.search(block["text"])),
                                  "chars": len(block["text"]),
                                  "text_head": block["text"][:200]})
            rows.append({"position": company_id + ":" + report_end, "judgement": str(path.relative_to(REPO)),
                         "selected": len(chosen), "qualification_blocks": found})
            with partial.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(rows[-1], ensure_ascii=False, sort_keys=True) + "\n")
            print(company_id, report_end, len(chosen), len(found),
                  sum(1 for item in found if not item["selected"]), flush=True)
    blocks = [item for row in rows for item in row["qualification_blocks"]]
    Path(out).write_text(json.dumps({
        "record_type": "ISSUE_47_C02_QUALIFICATION_NARRATIVE_REACH",
        "question": "Issue #47 comment 5945743839 (Paramount FY2025 block 168)",
        "positions": len(rows),
        "positions_with_such_a_block": sum(1 for row in rows if row["qualification_blocks"]),
        "blocks": len(blocks),
        "blocks_already_selected": sum(1 for item in blocks if item["selected"]),
        "blocks_not_selected": sum(1 for item in blocks if not item["selected"]),
        "blocks_judged_fact_by_the_readers": sum(1 for item in blocks if item["judged_fact"]),
        "blocks_not_selected_that_name_other_boards": sum(
            1 for item in blocks if not item["selected"] and item["names_other_boards"]),
        "per_position": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
