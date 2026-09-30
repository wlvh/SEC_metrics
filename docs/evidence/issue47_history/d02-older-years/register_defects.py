"""Register a coordinate-level defect for each older-year D02 position its reading found wrong.

Usage: python3 register_defects.py <acceptance reading> [<acceptance reading> ...] [--write]

For each DIFFERS position of the given acceptance readings, every wrong block
of its reading (NOT_DISCLOSURE, WRONGLY_SKIPPED, MISSED) is assigned a cause by
causes.json - by the block's scope for a taken or skipped block, by its kind
for an outside block - and one entry is written to known_result_defects.json,
naming the blocks, their causes and the result identity the reading compared.
A wrong block without a cause stops the run: a defect whose cause nobody named
is not registered as if it had one. Existing entries are never rewritten.
Dry run unless --write.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
REGISTER = REPO / "docs/evidence/issue47_history/known_result_defects.json"
WRONG = ("NOT_DISCLOSURE", "WRONGLY_SKIPPED", "MISSED")


def entries(readings):
    causes = json.loads((HERE / "causes.json").read_text(encoding="utf-8"))
    found = []
    for path in readings:
        body = json.loads((REPO / path).read_text(encoding="utf-8"))
        for label, row in sorted(body["per_position"].items()):
            if row["verdict"] == "MATCH":
                continue
            reading = json.loads((REPO / row["reading"]).read_text(encoding="utf-8"))
            position = reading["position"]
            table = causes["positions"].get(position)
            if table is None:
                raise SystemExit("NO_CAUSES_FOR_POSITION:" + position)
            blocks, used = [], []
            for judgement in reading["judgements"]:
                if judgement["verdict"] not in WRONG:
                    continue
                key = judgement.get("scope") or judgement["kind"]
                cause = table.get(key)
                if cause is None:
                    raise SystemExit("NO_CAUSE_FOR_BLOCK:" + position + ":" + str(judgement["i"]) + ":" + key)
                used.append(cause)
                blocks.append({"kind": judgement["kind"], "block_index": judgement["i"],
                               "scope": judgement.get("scope"), "text": judgement["text"],
                               "verdict": judgement["verdict"], "why": judgement["why"],
                               "cause": cause,
                               **({"reader_verdict": judgement["reader_verdict"],
                                   "adjudication_rule": judgement["adjudication_rule"]}
                                  if judgement.get("adjudication_rule") else {})})
            named = sorted(set(used))
            company, end = position.rsplit(":", 1)
            found.append({
                "company_id": company, "metric_id": "D02", "period_end": end, "result_id": None,
                "defect_id": "D02_" + company.split("_")[0].upper() + "_" + end[:4] + "_" + "_AND_".join(named),
                "same_cause_as": sorted({d for cause in named for d in causes["causes"][cause].get("same_cause_as", [])}),
                "summary": ("The older-year reading in both directions found " + str(len(blocks))
                            + " wrong block(s): " + "; ".join(causes["causes"][c]["text"] for c in named)
                            + " A set with a wrong member is not the right set, so the coordinate is withdrawn."),
                "the_blocks": blocks,
                "causes": {cause: causes["causes"][cause] for cause in named},
                "confirmed_in": {"acceptance_reading": path, "reading": row["reading"],
                                 "reading_sha256": row["reading_sha256"],
                                 "result_identity": row["checked_identity"]["bound_from"]},
                "repair_state": " + ".join(causes["causes"][c]["repair_state"] for c in named),
                "evidence": ["docs/evidence/issue47_history/d02-older-years/README.md", row["reading"],
                             "docs/evidence/issue47_history/d02-older-years/causes.json"]})
    return found


def main(argv):
    write = "--write" in argv
    readings = [a for a in argv if a != "--write"]
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    existing = {d["defect_id"] for d in register["defects"]}
    new = [e for e in entries(readings) if e["defect_id"] not in existing]
    for entry in new:
        print(entry["defect_id"], [(b["kind"], b["block_index"], b["cause"]) for b in entry["the_blocks"]])
    if write and new:
        register["defects"].extend(new)
        REGISTER.write_text(json.dumps(register, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", len(new))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
