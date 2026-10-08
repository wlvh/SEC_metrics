"""Version 2 against version 3 of the D02 Item 8 category-mention rule, on everything measured.

Usage: python3 compare.py <restored source root> <out.json>

Version 2 is the module as committed in 54eb39d4 with its terms file
(catalog/r6/D02_item_8_category_mention_v2.json, still in the tree); version 3
is the module in this tree. Both are asked the same question of:

* every Item 8 keyword block a reading judged: the thirty older-year readings
  (d02-older-years/judgements) and the four fresh readings of round 1e1ef948
  (targeted-round-1e1ef948/judgements), taken and skipped blocks alike;
* #28's sentence and the sentences written beside version 3 (below);
* version 2's constructed sentences and the first independent battery;
* the second independent battery, held out for version 3 as drafted;
* every Item 8 keyword admission in every saved annual report under the given
  root, as version 2's comparison counted them.

Version 3 only adds conditions to version 2's evidence, so a block version 2
keeps cannot leave under version 3; the census checks that rather than
assuming it. Zero calls.
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
sys.path.insert(0, str(HERE.parent / "v2"))

import compare as v2_compare  # noqa: E402  version 2's constructed sentences
from vnext import d02_item_8_category_mentions as v3  # noqa: E402
from vnext.text_business_candidates import _LEGAL  # noqa: E402

V2_COMMIT = "54eb39d47718dea25812ea05ceb5a085078ff611"
MODULE = "scripts/vnext/d02_item_8_category_mentions.py"
ITEM_8 = ("ITEM_8", "ITEM_8_STATEMENTS_PRINTED_AFTER_THE_ITEMS")
# #28's sentence (Issue #28 evidence collab-d02-versioned-20261002/v2/
# independent-review-79677ed/conclusion.md) and its two controls.
REVIEWED = [
    "During 2025, our company faced litigation, regulatory proceedings and fines.",
    "During 2025, the Company faced litigation, regulatory proceedings and fines.",
    "During 2025, we faced litigation, regulatory proceedings and fines.",
]
# Written by the executor beside version 3: the same matter in other shapes,
# and adviser lists that name the registrant. Design material, not a measure.
CONSTRUCTED_STAY = [
    "During 2025, our company faced regulatory proceedings, litigation and fines.",
    "During 2025 our company faced regulatory proceedings, litigation and fines.",
    "In 2025, our Company became the target of regulatory proceedings, litigation and fines.",
    "Our company faced litigation, regulatory proceedings and fines in 2025.",
    "Throughout the year, our firm defended litigation, regulatory proceedings and arbitrations.",
    "In 2025, our company was hit with regulatory proceedings, litigation and fines.",
    "Kestrel faced litigation, regulatory proceedings and fines.",
    "Kestrel faced regulatory proceedings, litigation and fines.",
    "During 2025, our company has matters such as litigation, fines and penalties.",
    "Our company has matters such as litigation, fines and penalties.",
    "During 2025, the Group defended litigation, regulatory proceedings and fines.",
]
CONSTRUCTED_LEAVE = [
    "We engage outside counsel to advise us on finance, regulatory, litigation and other matters.",
    "In the normal course of business we retain counsel to advise us on regulatory, litigation and "
    "other matters.",
    "Our outside counsel advise us on finance, regulatory, litigation and other matters.",
]


def version_two():
    """The committed version 2 module, reading its own terms file."""
    source = subprocess.run(["git", "show", V2_COMMIT + ":" + MODULE], cwd=REPO, check=True,
                            capture_output=True, text=True).stdout
    spec = importlib.util.spec_from_loader("vnext.d02_item_8_category_mentions_v2", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(REPO / MODULE)
    module.__package__ = "vnext"
    exec(compile(source, MODULE + "@" + V2_COMMIT, "exec"), module.__dict__)
    return module


def both(v2, text):
    return (v2.left_out_as_category_mention(text=text, keyword=_LEGAL),
            v3.left_out_as_category_mention(text=text, keyword=_LEGAL))


def judged(v2):
    blocks = {}
    for folder in ("d02-older-years/judgements", "targeted-round-1e1ef948/judgements"):
        for path in sorted((EVIDENCE / folder).glob("*.json")):
            body = json.loads(path.read_text(encoding="utf-8"))
            for row in body["judgements"]:
                if (row["kind"] in ("TAKEN", "SKIPPED") and row.get("scope") in ITEM_8
                        and _LEGAL.search(row["text"])):
                    blocks[(folder, body["position"], row["i"])] = (row["verdict"], row["text"])
    counts, moves = {}, []
    for (folder, position, index), (verdict, text) in sorted(blocks.items()):
        old, new = both(v2, text)
        key = "%s|v2_%s|v3_%s" % (verdict, "out" if old else "kept", "out" if new else "kept")
        counts[key] = counts.get(key, 0) + 1
        if old != new:
            moves.append({"readings": folder, "position": position, "i": index, "verdict": verdict})
    return {"blocks": len(blocks), "counts": dict(sorted(counts.items())), "moves": moves}


def battery(v2, stay, leave):
    return {"stay": len(stay), "leave": len(leave),
            "stay_left_out": {"v2": sum(both(v2, t)[0] for t in stay),
                              "v3": sum(both(v2, t)[1] for t in stay)},
            "leave_left_out": {"v2": sum(both(v2, t)[0] for t in leave),
                               "v3": sum(both(v2, t)[1] for t in leave)},
            "stay_left_out_by_v3": [t for t in stay if both(v2, t)[1]],
            "leave_kept_by_v3_where_v2_left_out": [t for t in leave if both(v2, t)[0]
                                                   and not both(v2, t)[1]]}


def census(v2, root):
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
        row = {"file": name, "keyword_admitted": len(admitted), "v2_left_out": [], "v3_left_out": [],
               "moved": []}
        for index in admitted:
            old, new = both(v2, blocks[index]["text"])
            if old:
                row["v2_left_out"].append(index)
            if new:
                row["v3_left_out"].append(index)
            if old != new:
                row["moved"].append({"i": index, "v2": old, "v3": new,
                                     "why_v3": [o["why"] for o in v3.classify(
                                         text=blocks[index]["text"], keyword=_LEGAL)["occurrences"]],
                                     "text": blocks[index]["text"]})
        rows.append(row)
        print(name, row["keyword_admitted"], len(row["v2_left_out"]), len(row["v3_left_out"]),
              len(row["moved"]), flush=True)
    return rows


def main(root, out):
    v2 = version_two()
    first = json.loads((HERE.parent / "v2/independent-battery-1.json").read_text(encoding="utf-8"))
    second = json.loads((HERE / "independent-battery-2.json").read_text(encoding="utf-8"))
    reports = census(v2, root)
    body = {
        "record_type": "ISSUE_47_D02_CATEGORY_RULE_V2_V3_COMPARISON",
        "v2": {"module_commit": V2_COMMIT, "terms": "catalog/r6/D02_item_8_category_mention_v2.json",
               "terms_hash": v2.TERMS_HASH},
        "v3": {"terms": "catalog/r6/D02_item_8_category_mention_v3.json", "terms_hash": v3.TERMS_HASH},
        "judged_blocks": judged(v2),
        "reviewed_sentences": battery(v2, REVIEWED, []),
        "constructed_v3": battery(v2, CONSTRUCTED_STAY, CONSTRUCTED_LEAVE),
        "constructed_v2": battery(v2, v2_compare.CONSTRUCTED_STAY, v2_compare.CONSTRUCTED_LEAVE),
        "independent_battery_1": battery(v2, first["stay"], first["leave"]),
        "independent_battery_2_held_out": battery(v2, second["stay"], second["leave"]),
        "census": {"reports": len(reports),
                   "errors": [r for r in reports if "error" in r],
                   "keyword_admitted": sum(r.get("keyword_admitted", 0) for r in reports),
                   "v2_left_out": sum(len(r.get("v2_left_out", ())) for r in reports),
                   "v3_left_out": sum(len(r.get("v3_left_out", ())) for r in reports),
                   "v3_out_where_v2_kept": [(r["file"], m["i"]) for r in reports
                                            for m in r.get("moved", ()) if m["v3"]],
                   "moved": [{"file": r["file"], **m} for r in reports for m in r.get("moved", ())],
                   "per_report": reports},
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    Path(out).write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                         encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
