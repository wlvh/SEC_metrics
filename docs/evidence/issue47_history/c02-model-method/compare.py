"""Compare development C02 extractions with #47's two-direction readings of the same filings.

A development context answered prepare_inputs.py's input with #28's task. The
answer is held to #28's own mechanical checks (its postprocess.preview: shape,
kinds, block references in range, no exact duplicate, quotation grouping) and
then compared with the reading #47's independent readers made of the same
document (c02-older-years/ or c02-composition-facts/ judgements, with the
recorded adjudication), by the same comparison tools/read_c02_composition.py
applies to the selector: the blocks the answer's facts cite are its "selection".
So "wrongly taken" is a cited block the reading judged states no composition
fact, "missed" is a block the reading judged a fact that no fact cites (nor a
block the reading names as stating the same fact), and "unread" is a cited block
no reader was given. The selector's own comparison on the same document is
reported beside it. Block-level agreement is a proxy: a fact can cite a context
block, and every listed problem is read by hand before any conclusion (README).

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-model-method/compare.py \
        --source-root <root> --inputs <dir> --answers <dir> --out <json>
Zero calls.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))
PILOT = REPO / "docs/evidence/issue28_continuous/c02-model-input-pilot-20261003"
READINGS = (REPO / "docs/evidence/issue47_history/c02-older-years/judgements",
            REPO / "docs/evidence/issue47_history/c02-composition-facts/judgements")


def _reading(position_dir):
    for root in READINGS:
        path = root / (position_dir + ".json")
        if path.exists():
            return path
    raise SystemExit("C02_DEV_COMPARE_NO_READING:" + position_dir)


def _raw(source_root, document, filing):
    digest = document["raw_asset_id"].split(":", 1)[1]
    path = (Path(source_root) / "evidence/request_attempts" / digest[:2] / digest
            / filing["primaryDocument"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise SystemExit("C02_DEV_COMPARE_RAW_CHANGED:" + str(path))
    return raw


def compare(*, source_root, inputs, answers, position_dir, tokenizer):
    from read_c02_composition import load_adjudications, read_position, route_selection
    sys.path.insert(0, str(PILOT))
    from postprocess import preview
    metadata = json.loads((inputs / position_dir / "metadata.json").read_text())
    document, chosen, _candidate = route_selection(
        repo_root=REPO, company_id=metadata["company_id"], report_end=metadata["report_end"],
        source_root=source_root)
    if document["text_document_id"] != metadata["document_id"]:
        raise SystemExit("C02_DEV_COMPARE_DOCUMENT_CHANGED:" + position_dir)
    reading_path = _reading(position_dir)
    reading = json.loads(reading_path.read_text())
    # The reading binds each block it judged by the block's text hash, which is
    # what read_position checks (text_changed). Its packet's document id can
    # differ for reasons that leave every block's text alone - the document
    # record also carries the filing's submissions row, and the acquisition
    # refreshed some submissions blocks after the readings - so the ids are
    # recorded side by side and any changed block text stops the comparison.
    raw_answer = (answers / (position_dir + ".json")).read_text(encoding="utf-8")
    row = {"position": metadata["company_id"] + ":" + metadata["report_end"],
           "reading": str(reading_path.relative_to(REPO)),
           "document_id": document["text_document_id"],
           "reading_packet_document_id": reading["packet_document_id"],
           "answer_sha256": hashlib.sha256(raw_answer.encode("utf-8")).hexdigest(),
           "answer_tokens": len(tokenizer.encode(raw_answer, add_special_tokens=False).ids),
           "input_tokens": json.loads((inputs / position_dir / "context-measurement.json")
                                      .read_text()).get("input_tokens")}
    try:
        answer = json.loads(raw_answer)
        quoted = preview(response=answer, document=document,
                         raw=_raw(source_root, document, metadata["filing"]))
    except (ValueError, KeyError, TypeError) as refusal:
        row["contract_check"] = "REFUSED: %s: %s" % (type(refusal).__name__, str(refusal)[:300])
        return row
    row["contract_check"] = "PASSED"
    row["quotation_preview"] = {"unique_cited_blocks": quoted["unique_cited_blocks"],
                                "quote_groups": len(quoted["quote_groups"]),
                                "quote_characters": quoted["quote_characters"]}
    facts, unresolved = answer["facts"], answer["unresolved"]
    cited = sorted({i for fact in facts for i in fact["source_blocks"]})
    adjudications = load_adjudications()
    model = read_position(document=document, chosen=cited, reading=reading, adjudications=adjudications)
    rules = read_position(document=document, chosen=chosen, reading=reading, adjudications=adjudications)
    by_block = {}
    for number, fact in enumerate(facts):
        for i in fact["source_blocks"]:
            by_block.setdefault(i, []).append(number)
    blocks = document["blocks"]

    def show(i):
        return {"i": i, "text": blocks[i]["text"][:400],
                "facts_citing": [{"kind": facts[n]["kind"], "statement": facts[n]["statement"]}
                                 for n in by_block.get(i, [])]}
    problems = model["problems"]
    if problems["text_changed"] or rules["problems"]["text_changed"]:
        raise SystemExit("C02_DEV_COMPARE_READING_BLOCK_TEXT_CHANGED:" + position_dir + ":"
                         + str(sorted(set(problems["text_changed"]) | set(rules["problems"]["text_changed"]))[:20]))
    row.update({
        "facts": len(facts), "unresolved": len(unresolved),
        "kinds": dict(Counter(fact["kind"] for fact in facts)),
        "cited_blocks": len(cited), "selector_blocks": len(chosen),
        "model_vs_reading": {"verdict": model["verdict"], "counts": model["counts"],
                             "wrongly_taken": [{**show(p["i"]), "reading_why": p["why"]}
                                               for p in problems["wrongly_taken"]],
                             "missed": [{**show(p["i"]), "reading_why": p["why"],
                                         "redundant_with": p.get("redundant_with")}
                                        for p in problems["missed"]],
                             "unread": [show(i) for i in problems["unread"]],
                             "other": {k: v for k, v in problems.items()
                                       if k not in ("wrongly_taken", "missed", "unread") and v}},
        "selector_vs_reading": {"verdict": rules["verdict"],
                                "missed": [p["i"] for p in rules["problems"]["missed"]],
                                "wrongly_taken": [p["i"] for p in rules["problems"]["wrongly_taken"]],
                                "unread": rules["problems"]["unread"]},
        "unresolved_items": unresolved})
    return row


def main():
    from vnext.continuous_request_context import _load_tokenizer
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    tokenizer, _ = _load_tokenizer()
    rows = [compare(source_root=arguments.source_root, inputs=arguments.inputs,
                    answers=arguments.answers, position_dir=path.stem, tokenizer=tokenizer)
            for path in sorted(arguments.answers.glob("*.json"))]
    arguments.out.write_text(json.dumps({
        "record_type": "ISSUE_47_C02_DEV_EXTRACTION_COMPARISON",
        "what_this_is": ("development-context extractions on #28's C02 task, checked by #28's "
                         "mechanical checks and compared block by block with #47's readings; "
                         "not DeepSeek, no call, no result credit"),
        "rows": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        ensure_ascii=False, indent=1) + "\n")
    for row in rows:
        print(row["position"], row.get("contract_check"), row.get("facts"), "facts",
              (row.get("model_vs_reading") or {}).get("verdict"), flush=True)


if __name__ == "__main__":
    main()
