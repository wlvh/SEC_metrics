"""Hold development answers to D02's Item 8 review contract and to the older-year readings.

Each answer is checked first by the contract itself (``validate_answer`` and
``reviewed_blocks``), as a paid answer would be. It is then compared with the
two-direction reading of the same filing (``../d02-older-years/judgements/``):
every Item 8 block the reading judged (``kind`` TAKEN or OUTSIDE with scope
ITEM_8, and every heading in the request it judged) must get the reading's
answer - DISCLOSURE in scope, NOT_DISCLOSURE or a NOT_D02 heading out of scope;
a REACHED heading (its content is in the value) agrees either way. A reading's block is matched by its index and its text hash, so a
reading of other text is not counted as agreeing. Blocks the answer puts in
scope that the reading never judged are listed for a hand reading (the
reading judged the route's selection and the headings around it, not every
Item 8 block). The route's own Item 8 selection today (rule v4) is reported
beside it, judged by the same reading.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/d02-model-method/compare.py \
        --inputs <dir> --answers <dir> --out <json>
Zero calls.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
READINGS = REPO / "docs/evidence/issue47_history/d02-older-years/judgements"


def _sha(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def compare(*, inputs, answers, name, tokenizer):
    from vnext.historical_legal_review import (LegalReviewContractError, reviewed_blocks,
                                               validate_answer)
    request = json.loads((inputs / name / "request.json").read_text(encoding="utf-8"))
    raw = (answers / (name + ".json")).read_text(encoding="utf-8")
    texts = {block["block_id"]: block["text"] for block in request["blocks"]}
    row = {"position": request["company_id"] + ":" + request["period_end"],
           "answer_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
           "answer_tokens": len(tokenizer.encode(raw, add_special_tokens=False).ids),
           "blocks": len(request["blocks"]), "must_decide": len(request["must_decide"])}
    try:
        decisions, added = validate_answer(request=request, raw_output=raw)
        counted, withheld, unsettled = reviewed_blocks(request=request, decisions=decisions, added=added)
    except LegalReviewContractError as refusal:
        row["contract_check"] = "REFUSED: " + str(refusal)[:300]
        return row
    row["contract_check"] = "PASSED"
    row["withheld"] = withheld
    row["unsettled"] = unsettled
    in_scope = set(counted or []) | {i for i, d in decisions.items() if d["decision"] == "IN_SCOPE"} | set(added)
    reading = json.loads((READINGS / (name + ".json")).read_text(encoding="utf-8"))
    judged, agree, disagree, absent = {}, [], [], []
    for entry in reading["judgements"]:
        # Item 8 blocks the reading judged, and every heading it judged: a
        # heading the reading found REACHED heads a disclosure the value
        # takes, which the definition counts with it; NOT_D02 is not one.
        # Headings outside the request (Item 3, MD&A, incorporated notes) are
        # not this request's to decide and are skipped below.
        if not ((entry.get("scope") == "ITEM_8" and entry["kind"] in ("TAKEN", "OUTSIDE"))
                or entry["kind"] == "HEADING"):
            continue
        if entry["kind"] == "HEADING" and "b" + str(entry["i"]) not in texts:
            continue
        identity = "b" + str(entry["i"])
        judged[identity] = entry
        if identity not in texts:
            absent.append({"block_id": identity, "reading": entry["verdict"], "why": entry.get("why", "")})
            continue
        if _sha(texts[identity]) != entry["text_sha256"]:
            raise SystemExit("D02_DEV_COMPARE_READING_BLOCK_TEXT_CHANGED:" + name + ":" + identity)
        got = identity in in_scope
        answer = decisions.get(identity, {}).get("decision") or ("IN_SCOPE" if identity in added else "NOT_LISTED")
        line = {"block_id": identity, "reading": entry["verdict"], "answer": answer,
                "reading_why": entry.get("why", ""), "text": texts[identity][:300]}
        if entry["verdict"] == "REACHED":
            # The reading says the value reached this heading's content, not
            # that the heading itself must be taken; either answer agrees.
            agree.append(line)
            continue
        wanted = entry["verdict"] in ("DISCLOSURE", "WRONGLY_SKIPPED")
        (agree if wanted == got else disagree).append(line)
    unjudged = [{"block_id": i, "how": decisions[i]["decision"] if i in decisions else "ALSO_IN_SCOPE",
                 "quote": (decisions.get(i) or added.get(i))["quote"], "text": texts[i][:400]}
                for i in sorted(in_scope, key=lambda x: int(x[1:])) if i not in judged]
    metadata = json.loads((inputs / name / "metadata.json").read_text(encoding="utf-8"))
    route = set(metadata["route_item_8_selection"])
    route_disagree = [{"block_id": i, "reading": e["verdict"], "route": "TAKEN" if i in route else "NOT_TAKEN"}
                      for i, e in sorted(judged.items(), key=lambda x: int(x[0][1:]))
                      if e["verdict"] != "REACHED"
                      and (e["verdict"] in ("DISCLOSURE", "WRONGLY_SKIPPED")) != (i in route)]
    row.update({"route_item_8_selection": sorted(route, key=lambda x: int(x[1:])),
                "route_disagrees_with_the_reading": route_disagree,
                "route_selection_not_judged_by_the_reading": sorted(
                    (i for i in route if i not in judged), key=lambda x: int(x[1:])),
                "decided": len(decisions), "in_scope": sorted(in_scope, key=lambda x: int(x[1:])),
                "added": sorted(added, key=lambda x: int(x[1:])),
                "reading_item_8_blocks": len(judged), "agree": agree, "disagree": disagree,
                "reading_blocks_not_in_request": absent, "in_scope_not_judged_by_the_reading": unjudged})
    return row


def main():
    from vnext.continuous_request_context import _load_tokenizer
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    tokenizer, _ = _load_tokenizer()
    rows = [compare(inputs=arguments.inputs, answers=arguments.answers, name=path.stem, tokenizer=tokenizer)
            for path in sorted(arguments.answers.glob("*.json"))]
    arguments.out.write_text(json.dumps({
        "record_type": "ISSUE_47_D02_DEV_REVIEW_COMPARISON",
        "what_this_is": ("development-context answers to D02's Item 8 review contract on older positions, "
                         "checked by the contract and compared with #47's two-direction readings; "
                         "not DeepSeek, no call, no result credit"),
        "rows": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}}, ensure_ascii=False, indent=1) + "\n")
    for row in rows:
        print(row["position"], row["contract_check"], "agree", len(row.get("agree", [])),
              "disagree", len(row.get("disagree", [])), "unjudged in scope",
              len(row.get("in_scope_not_judged_by_the_reading", [])), flush=True)


if __name__ == "__main__":
    main()
