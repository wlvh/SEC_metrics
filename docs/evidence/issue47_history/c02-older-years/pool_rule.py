"""Which pool rule reaches every composition fact the latest-year C02 readers found.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-older-years/pool_rule.py <out.json>

The latest-year readings (``../c02-composition-facts/judgements/``) record the
pool each reader was given (block index and text digest) and every block the
reader said states a composition fact: the selected blocks judged FACT or
MIXED, the pool facts and the facts outside the pool. The script that built
those pools was never committed, so a packet for the older years needs a rule
of its own. A rule is a candidate only if its pool, with the selection, holds
every fact block a latest-year reader found; among those, the smaller pool is
the better one, because every pool block is a block a reader must read.

The rule is written from the owner's decision - board size, independent
directors, committees, members, chairs, and the related independence and
qualification determinations - not from the selector's signals: a pool built
from the selector's own tests could not show what the selector misses. Each
candidate is a vocabulary V and a reach k: every block V matches, and every
block within k of one - or, in the second family, every short block (at most
``short`` characters, with a letter) within k of one. The second family exists
because of what the first misses: the facts far from the owner's words are
short blocks - a director's name in a roster or on a card, a committee's name
in a card field or a matrix header ("Audit", "Finance", "Governance"), a card
label ("Financial Expert") - while the long blocks far from those words are
not facts. The text volume a reader must read is reported beside the block
count, because a name costs a reader less than a paragraph. Zero calls.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from read_c02_composition import READING_DIR, route_selection, text_sha256  # noqa: E402

# The owner's decision, in the words a proxy uses for it.
VOCABULARY = re.compile(
    r"\b(?:directors?|board|committees?|independen(?:t|ce)|chair(?:man|woman|person|s)?|vice[- ]chair"
    r"|lead(?:ing)?\s+director|presiding\s+director|members?(?:hip)?|nominees?|nominat(?:ed|ing|ion))\b",
    re.I)
REACHES = (0, 1, 2, 3, 4, 6, 8)
SHORT_RULES = ((10, 60), (16, 60), (16, 80), (20, 100))
LETTER = re.compile(r"[A-Za-z]")


def fact_blocks(reading):
    facts = {row["i"] for row in reading["selected"] if row["verdict"] in ("FACT", "MIXED")}
    facts |= {row["i"] for row in reading.get("supplementary", []) if row["verdict"] in ("FACT", "MIXED")}
    facts |= {row["i"] for row in reading["pool_facts"]}
    facts |= {row["i"] for row in reading.get("outside_pool_facts", [])}
    return facts


def pool_for(blocks, reach):
    matched = [i for i, block in enumerate(blocks) if VOCABULARY.search(block["text"])]
    pool = set()
    for i in matched:
        pool.update(range(max(0, i - reach), min(len(blocks), i + reach + 1)))
    return pool


def short_pool_for(blocks, reach, short):
    matched = [i for i, block in enumerate(blocks) if VOCABULARY.search(block["text"])]
    pool = set(matched)
    for i in matched:
        for j in range(max(0, i - reach), min(len(blocks), i + reach + 1)):
            text = blocks[j]["text"].strip()
            if len(text) <= short and LETTER.search(text):
                pool.add(j)
    return pool


def _measure(blocks, pool, chosen, facts):
    reached = pool | set(chosen)
    outside = pool - set(chosen)
    return {"pool": len(pool), "pool_outside_selection": len(outside),
            "pool_characters": sum(len(blocks[i]["text"]) for i in outside),
            "facts_missed": sorted(facts - reached)}


def main(out_path):
    rows = {}
    for path in sorted(READING_DIR.glob("*.json")):
        reading = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = reading["position"].rsplit(":", 1)
        document, chosen, _ = route_selection(repo_root=REPO, company_id=company_id,
                                              report_end=report_end)
        blocks = document["blocks"]
        recorded = {row["i"] for row in reading["pool"]
                    if row["i"] < len(blocks) and row["text_sha256"] == text_sha256(blocks[row["i"]]["text"])}
        facts = fact_blocks(reading)
        row = {"blocks": len(blocks), "selected": len(chosen), "recorded_pool": len(reading["pool"]),
               "recorded_pool_text_unchanged": len(recorded), "facts_found_by_the_reader": len(facts),
               "facts_outside_recorded_pool_and_selection": len(facts - recorded - set(chosen)),
               "candidates": {}}
        row["recorded"] = _measure(blocks, recorded, chosen, facts)
        for reach in REACHES:
            row["candidates"][str(reach)] = _measure(blocks, pool_for(blocks, reach), chosen, facts)
        for reach, short in SHORT_RULES:
            row["candidates"]["short%d_reach%d" % (short, reach)] = _measure(
                blocks, short_pool_for(blocks, reach, short), chosen, facts)
        rows[reading["position"]] = row
        print(reading["position"], {k: (v["pool"], len(v["facts_missed"])) for k, v in row["candidates"].items()},
              flush=True)
    summary = {"recorded": {key: sum(len(r["recorded"][key]) if key == "facts_missed" else r["recorded"][key]
                                     for r in rows.values())
                            for key in ("pool_outside_selection", "pool_characters", "facts_missed")}}
    for key in rows[next(iter(rows))]["candidates"]:
        summary[key] = {name: sum(len(r["candidates"][key][name]) if name == "facts_missed"
                                  else r["candidates"][key][name] for r in rows.values())
                        for name in ("pool_outside_selection", "pool_characters", "facts_missed")}
    Path(out_path).write_text(json.dumps({"record_type": "ISSUE_47_C02_POOL_RULE_MEASUREMENT",
                                          "vocabulary": VOCABULARY.pattern, "positions": rows,
                                          "summary": summary, "calls": {"provider": 0, "paid": 0, "sec": 0}},
                                         indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
