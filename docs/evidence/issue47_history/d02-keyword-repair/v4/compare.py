"""Version 3 against version 4 of the D02 Item 8 category-mention rule, on everything measured.

Usage: python3 compare.py <restored source root> <out.json>

Version 3 is the module as committed in 1672097b with its terms file
(catalog/r6/D02_item_8_category_mention_v3.json, still in the tree); version 4
is the module in this tree. Both are asked the same question of:

* every Item 8 keyword block a reading judged: the thirty older-year readings
  (d02-older-years/judgements) and the four fresh readings of round 1e1ef948
  (targeted-round-1e1ef948/judgements), taken and skipped blocks alike;
* #28's four sentences on its copy of version 3 (Issue #47 comment
  5956052190) and its three P2 sentences on version 2;
* the constructed sentences written beside versions 2, 3 and 4, and both
  independent batteries;
* every Item 8 keyword admission in every saved annual report under the given
  root, as the earlier comparisons counted them.

Version 4 only adds a condition to version 3's category reading, so a block
version 3 keeps cannot leave under version 4; the census checks that rather
than assuming it. Zero calls.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
EVIDENCE = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(EVIDENCE / "d02-navigation-repairs"))

from vnext import d02_item_8_category_mentions as v4  # noqa: E402
from vnext.text_business_candidates import _LEGAL  # noqa: E402

V3_COMMIT = "1672097b"
MODULE = "scripts/vnext/d02_item_8_category_mentions.py"
ITEM_8 = ("ITEM_8", "ITEM_8_STATEMENTS_PRINTED_AFTER_THE_ITEMS")
JUDGED = ("d02-older-years/judgements", "targeted-round-1e1ef948/judgements")
# #28's four sentences on its copy of version 3 (Issue #28 evidence
# collab-d02-versioned-20261002/v2/read-peer-v3-known-limits.py on
# task/b06-new-source); the first and the last are its controls.
PEER_V3 = {
    "stay": ["During 2025, our company faced litigation, regulatory proceedings and fines.",
             "Kestrel defended regulatory proceedings, litigation and fines.",
             "In 2025, litigation, fines and penalties increased."],
    "leave": ["We engage outside counsel to advise us on finance, regulatory, litigation and other matters."],
}
# Written by the executor beside version 4: series no closed-class word
# governs, and governed category lists it must still leave out. Design
# material, not a measure.
CONSTRUCTED_STAY = [
    "Last year, regulatory proceedings, litigation and fines rose sharply.",
    "Throughout 2025, investigations, litigation and fines continued.",
    "Acme defended regulatory proceedings, litigation and fines in several states.",
    "In Europe, consumer claims, litigation and penalties grew.",
]
CONSTRUCTED_LEAVE = [
    "Results may vary because of competition, litigation, legislation and other factors.",
    "Expenses include fees for audit, tax, litigation and other services.",
    "Counsel advise the board on governance, litigation and other matters.",
]


def _sentences(name, path):
    """An earlier comparison loaded under its own name, only for its sentence lists."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Loaded under its own name: as "compare" its own "import compare" (version 2's
# sentences) would return itself.
v3_compare = _sentences("d02_rule_v3_compare", HERE.parent / "v3/compare.py")


def version_three():
    """The committed version 3 module, reading its own terms file."""
    source = subprocess.run(["git", "show", V3_COMMIT + ":" + MODULE], cwd=REPO, check=True,
                            capture_output=True, text=True).stdout
    spec = importlib.util.spec_from_loader("vnext.d02_item_8_category_mentions_v3", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(REPO / MODULE)
    module.__package__ = "vnext"
    exec(compile(source, MODULE + "@" + V3_COMMIT, "exec"), module.__dict__)
    return module


def both(v3, text):
    return (v3.left_out_as_category_mention(text=text, keyword=_LEGAL),
            v4.left_out_as_category_mention(text=text, keyword=_LEGAL))


def judged(v3):
    blocks = {}
    for folder in JUDGED:
        for path in sorted((EVIDENCE / folder).glob("*.json")):
            body = json.loads(path.read_text(encoding="utf-8"))
            for row in body["judgements"]:
                if (row["kind"] in ("TAKEN", "SKIPPED") and row.get("scope") in ITEM_8
                        and _LEGAL.search(row["text"])):
                    blocks[(folder, body["position"], row["i"])] = (row["verdict"], row["text"])
    counts, moves = {}, []
    for (folder, position, index), (verdict, text) in sorted(blocks.items()):
        old, new = both(v3, text)
        key = "%s|v3_%s|v4_%s" % (verdict, "out" if old else "kept", "out" if new else "kept")
        counts[key] = counts.get(key, 0) + 1
        if old != new:
            moves.append({"readings": folder, "position": position, "i": index, "verdict": verdict,
                          "why_v4": [o["why"] for o in v4.classify(text=text, keyword=_LEGAL)["occurrences"]],
                          "text": text})
    return {"blocks": len(blocks), "counts": dict(sorted(counts.items())), "moves": moves}


def battery(v3, stay, leave):
    return {"stay": len(stay), "leave": len(leave),
            "stay_left_out": {"v3": sum(both(v3, t)[0] for t in stay),
                              "v4": sum(both(v3, t)[1] for t in stay)},
            "leave_left_out": {"v3": sum(both(v3, t)[0] for t in leave),
                               "v4": sum(both(v3, t)[1] for t in leave)},
            "stay_left_out_by_v4": [t for t in stay if both(v3, t)[1]],
            "leave_kept_by_v4_where_v3_left_out": [t for t in leave if both(v3, t)[0]
                                                   and not both(v3, t)[1]]}


def census(v3, root):
    from effect import BUILD, _documents  # the navigation census's own report builder
    from vnext import historical_text_results as route
    rows = []
    for name, raw, blob, reference, cik, period_end in _documents(str(Path(root) / "evidence")):
        try:
            document = BUILD(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                             expected_company_id="company", expected_cik=cik,
                             expected_period_end=period_end)
            document = route.narrow_document_sections(document=document)
            proposal = route.referenced_note_candidates(document=document, raw_bytes=raw)
        except Exception as error:  # recorded, not hidden
            rows.append({"file": name, "error": type(error).__name__ + ":" + str(error)[:160]})
            continue
        blocks = document["blocks"]
        admitted = sorted({c["block_index"] for c in proposal["D02"]["candidates"]
                           if c["section_id"] in ITEM_8 and _LEGAL.search(blocks[c["block_index"]]["text"])}
                          | {item["block_index"] for item in
                             (proposal.get("item_8_category_mentions_left_out") or {}).get("blocks", [])})
        row = {"file": name, "keyword_admitted": len(admitted), "v3_left_out": [], "v4_left_out": [],
               "moved": []}
        for index in admitted:
            old, new = both(v3, blocks[index]["text"])
            if old:
                row["v3_left_out"].append(index)
            if new:
                row["v4_left_out"].append(index)
            if old != new:
                row["moved"].append({"i": index, "v3": old, "v4": new,
                                     "why_v4": [o["why"] for o in v4.classify(
                                         text=blocks[index]["text"], keyword=_LEGAL)["occurrences"]],
                                     "text": blocks[index]["text"]})
        rows.append(row)
        print(name, row["keyword_admitted"], len(row["v3_left_out"]), len(row["v4_left_out"]),
              len(row["moved"]), flush=True)
    return rows


def main(root, out):
    v3 = version_three()
    first = json.loads((HERE.parent / "v2/independent-battery-1.json").read_text(encoding="utf-8"))
    second = json.loads((HERE.parent / "v3/independent-battery-2.json").read_text(encoding="utf-8"))
    v2_sentences = v3_compare.v2_compare
    reports = census(v3, root)
    body = {
        "record_type": "ISSUE_47_D02_CATEGORY_RULE_V3_V4_COMPARISON",
        "v3": {"module_commit": V3_COMMIT, "terms": "catalog/r6/D02_item_8_category_mention_v3.json",
               "terms_hash": v3.TERMS_HASH},
        "v4": {"terms": "catalog/r6/D02_item_8_category_mention_v4.json", "terms_hash": v4.TERMS_HASH},
        "judged_blocks": judged(v3),
        "peer_v3_sentences": battery(v3, PEER_V3["stay"], PEER_V3["leave"]),
        "reviewed_sentences_v2": battery(v3, v3_compare.REVIEWED, []),
        "constructed_v4": battery(v3, CONSTRUCTED_STAY, CONSTRUCTED_LEAVE),
        "constructed_v3": battery(v3, v3_compare.CONSTRUCTED_STAY, v3_compare.CONSTRUCTED_LEAVE),
        "constructed_v2": battery(v3, v2_sentences.CONSTRUCTED_STAY, v2_sentences.CONSTRUCTED_LEAVE),
        "independent_battery_1": battery(v3, first["stay"], first["leave"]),
        "independent_battery_2": battery(v3, second["stay"], second["leave"]),
        "census": {"reports": len(reports),
                   "errors": [r for r in reports if "error" in r],
                   "keyword_admitted": sum(r.get("keyword_admitted", 0) for r in reports),
                   "v3_left_out": sum(len(r.get("v3_left_out", ())) for r in reports),
                   "v4_left_out": sum(len(r.get("v4_left_out", ())) for r in reports),
                   "v4_out_where_v3_kept": [(r["file"], m["i"]) for r in reports
                                            for m in r.get("moved", ()) if m["v4"]],
                   "moved": [{"file": r["file"], **m} for r in reports for m in r.get("moved", ())],
                   "per_report": reports},
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    Path(out).write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                         encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
