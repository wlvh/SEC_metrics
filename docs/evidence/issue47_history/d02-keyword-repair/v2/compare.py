"""Version 1 against version 2 of the D02 Item 8 category-mention rule, on everything measured.

Usage: python3 compare.py <restored source root> <out.json>

Version 1 is the module as committed in 104876d6 with its terms file
(catalog/r6/D02_item_8_category_mention_v1.json, still in the tree); version 2
is the module in this tree. Both are asked the same question of:

* every Item 8 keyword admission the older-year readings judged
  (d02-older-years/judgements): design, held-out and Pfizer FY2021 (seen);
* the constructed sentences written beside version 2 (below);
* the independent battery (independent-battery-1.json);
* every Item 8 keyword admission in every saved annual report under the given
  root: the blocks the route admits through the keyword before the category
  rule, which is the route's Item 8 excerpts plus the blocks it left out.

Version 2 only adds conditions to version 1's evidence, so a block version 1
keeps cannot leave under version 2; the census checks that rather than
assuming it. Zero calls.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE.parents[1] / "d02-navigation-repairs"))

from vnext import d02_item_8_category_mentions as v2  # noqa: E402
from vnext.text_business_candidates import _LEGAL  # noqa: E402

V1_COMMIT = "104876d6cfae7812d93fd5b8a4bb0e0f97959fff"
MODULE = "scripts/vnext/d02_item_8_category_mentions.py"
ITEM_8 = ("ITEM_8", "ITEM_8_STATEMENTS_PRINTED_AFTER_THE_ITEMS")
# Written by the executor beside version 2: disclosures that must stay, and
# category mentions that should leave. Design material, not a measure.
CONSTRUCTED_STAY = [
    "We face litigation, which could result in a significant loss.",
    "Litigation, brought by a customer against us in 2025, remains unresolved.",
    "Litigation, brought by customers and suppliers, remains unresolved.",
    "Irrespective of its merits, litigation may be both lengthy and disruptive to our operations.",
    "Since 2019, litigation against us has increased.",
    "We operate globally and litigation is a constant cost of doing so.",
    "A customer sued us, and litigation, brought against us in 2025, remains unresolved.",
    "Several matters remain open, including litigation brought by a customer against us in 2025.",
    "We face litigation, regulatory actions and fines.",
    "We face regulatory actions, litigation and fines.",
    "We face regulatory actions, litigation and other claims.",
    "The Company faces regulatory actions, litigation and other claims.",
    "We are exposed to regulatory actions, litigation and other claims.",
    "The Company has been named in lawsuits, investigations and other claims.",
    "Litigation and other claims remain unresolved.",
    "Litigation, fines and penalties remain unresolved.",
    "The litigation, which a customer brought in 2025, continues.",
    "In 2025, litigation, fines and penalties increased.",
    "Matters include litigation brought against the Company by a former supplier.",
    "During 2025, the Company faced litigation, fines and penalties.",
    "In 2025, the Company faced regulatory actions, litigation and fines.",
    "As of year end, litigation, fines and penalties remained open.",
    "Matters include regulatory actions, litigation and claims against the Company.",
    "The Company and its subsidiaries face regulatory actions, litigation and other claims.",
    "The Company has been named in investigations, lawsuits and other claims.",
    "We could face regulatory actions and litigation.",
]
CONSTRUCTED_LEAVE = [
    "In the normal course of our business, we incur costs to retain external counsel to advise us on "
    "finance, regulatory, litigation, and other matters. We expense these costs as the related services "
    "are received.",
    "Trade accounts receivable are written off after all reasonable means to collect the full amount "
    "(including litigation, where appropriate) have been exhausted.",
    "Our estimates are often based on complex judgments. We are subject to risks that may cause results "
    "to differ, such as competition, litigation, legislation and regulations.",
    "Finalizing audits with the relevant taxing authorities can include formal administrative and legal "
    "proceedings, and, as a result, it is difficult to estimate the timing.",
    "These events could result in financial losses, litigation and regulatory fines, as well as other "
    "harm to the Firm.",
    "Rating agencies continue to evaluate economic and geopolitical trends, regulatory developments, "
    "future profitability, risk management practices, and litigation matters, as well as their broader "
    "ratings methodologies.",
]


def version_one():
    """The committed version 1 module, reading its own terms file."""
    source = subprocess.run(["git", "show", V1_COMMIT + ":" + MODULE], cwd=REPO, check=True,
                            capture_output=True, text=True).stdout
    spec = importlib.util.spec_from_loader("vnext.d02_item_8_category_mentions_v1", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(REPO / MODULE)
    module.__package__ = "vnext"
    exec(compile(source, MODULE + "@" + V1_COMMIT, "exec"), module.__dict__)
    return module


def both(v1, text):
    return (v1.left_out_as_category_mention(text=text, keyword=_LEGAL),
            v2.left_out_as_category_mention(text=text, keyword=_LEGAL))


def judged(v1):
    counts, moves = {}, []
    for path in sorted((HERE.parents[1] / "d02-older-years/judgements").glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        group = ("pfizer_2021_seen" if body["position"].startswith("pfizer:2021")
                 else "held_out" if "held-out round" in body["reader"] else "design")
        for row in body["judgements"]:
            if row["kind"] != "TAKEN" or row.get("scope") not in ITEM_8:
                continue
            old, new = both(v1, row["text"])
            key = "%s|%s|v1_%s|v2_%s" % (group, row["verdict"], "out" if old else "kept",
                                        "out" if new else "kept")
            counts[key] = counts.get(key, 0) + 1
            if old != new:
                moves.append({"position": body["position"], "i": row["i"], "verdict": row["verdict"]})
    return {"counts": dict(sorted(counts.items())), "moves": moves}


def battery(v1, stay, leave):
    return {"stay": len(stay), "leave": len(leave),
            "stay_left_out": {"v1": sum(both(v1, t)[0] for t in stay),
                              "v2": sum(both(v1, t)[1] for t in stay)},
            "leave_left_out": {"v1": sum(both(v1, t)[0] for t in leave),
                               "v2": sum(both(v1, t)[1] for t in leave)},
            "stay_left_out_by_v2": [t for t in stay if both(v1, t)[1]]}


def census(v1, root):
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
        row = {"file": name, "keyword_admitted": len(admitted), "v1_left_out": [], "v2_left_out": [],
               "moved": []}
        for index in admitted:
            old, new = both(v1, blocks[index]["text"])
            if old:
                row["v1_left_out"].append(index)
            if new:
                row["v2_left_out"].append(index)
            if old != new:
                row["moved"].append({"i": index, "v1": old, "v2": new,
                                     "why_v2": [o["why"] for o in v2.classify(
                                         text=blocks[index]["text"], keyword=_LEGAL)["occurrences"]],
                                     "text": blocks[index]["text"]})
        rows.append(row)
        print(name, row["keyword_admitted"], len(row["v1_left_out"]), len(row["v2_left_out"]),
              len(row["moved"]), flush=True)
    return rows


def main(root, out):
    v1 = version_one()
    independent = json.loads((HERE / "independent-battery-1.json").read_text(encoding="utf-8"))
    reports = census(v1, root)
    body = {
        "record_type": "ISSUE_47_D02_CATEGORY_RULE_V1_V2_COMPARISON",
        "v1": {"module_commit": V1_COMMIT, "terms": "catalog/r6/D02_item_8_category_mention_v1.json",
               "terms_hash": v1.TERMS_HASH},
        "v2": {"terms": "catalog/r6/D02_item_8_category_mention_v2.json", "terms_hash": v2.TERMS_HASH},
        "judged_admissions": judged(v1),
        "constructed_battery": battery(v1, CONSTRUCTED_STAY, CONSTRUCTED_LEAVE),
        "independent_battery": battery(v1, independent["stay"], independent["leave"]),
        "census": {"reports": len(reports),
                   "errors": [r for r in reports if "error" in r],
                   "keyword_admitted": sum(r.get("keyword_admitted", 0) for r in reports),
                   "v1_left_out": sum(len(r.get("v1_left_out", ())) for r in reports),
                   "v2_left_out": sum(len(r.get("v2_left_out", ())) for r in reports),
                   "v2_out_where_v1_kept": [(r["file"], m["i"]) for r in reports
                                            for m in r.get("moved", ()) if m["v2"]],
                   "moved": [{"file": r["file"], **m} for r in reports for m in r.get("moved", ())],
                   "per_report": reports},
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    Path(out).write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                         encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
