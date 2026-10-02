"""What pairing page numbers across facing pages moves, on every saved annual report.

Usage: python3 effect.py <restored source root> <out.json>

Each saved annual report (DEI DocumentType 10-K) is built as a text document
with the release-aware builder and narrowed as the route narrows it. The page
numbers (``page_number_blocks``), the furniture found by its place on the page
(``page_structure_furniture``), the note references and the D02 and D03
candidate sets are computed twice: with a page number paired only with the
number one lower or higher beside the same footer on the same side (as
before), and also on the other side (facing pages). Every difference is recorded
per report, with the text beside each newly found page number, so the repair
is held to moving only page furniture. Zero calls.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE.parent / "d02-navigation-repairs"))

from effect import BUILD, _documents  # noqa: E402  (the census's own report builder)
from vnext import historical_text_results as route  # noqa: E402

FACING = route._FACING_PAGES


def _run(document, raw, facing):
    route._FACING_PAGES = facing
    try:
        blocks = document["blocks"]
        pages = route.page_number_blocks(blocks)
        furniture = route.page_structure_furniture(blocks)
        proposal = route.referenced_note_candidates(document=document, raw_bytes=raw)
    finally:
        route._FACING_PAGES = FACING
    return {
        "pages": sorted(pages), "furniture": sorted(furniture),
        "D02": sorted(c["block_index"] for c in proposal["D02"]["candidates"]),
        "D03": sorted(c["block_index"] for c in proposal["D03"]["candidates"]),
        "notes": [(r["reference"], r["status"],
                   [(c["start_block"], c["end_block_exclusive"], c["scope_relation"])
                    for c in r["range_candidates"]]) for r in proposal.get("note_references", [])],
        "reasons": proposal.get("coverage_reasons", []),
    }


def main(root, out):
    rows = []
    for name, raw, blob, reference, cik, period_end in _documents(str(Path(root) / "evidence")):
        try:
            document = BUILD(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                             expected_company_id="company", expected_cik=cik,
                             expected_period_end=period_end)
            document = route.narrow_document_sections(document=document)
            before, after = _run(document, raw, False), _run(document, raw, True)
        except Exception as error:  # recorded, not hidden
            rows.append({"file": name, "error": type(error).__name__ + ":" + str(error)[:200]})
            print(name, "ERROR", str(error)[:120], flush=True)
            continue
        blocks = document["blocks"]
        new_pages = sorted(set(after["pages"]) - set(before["pages"]))
        row = {"file": name, "pages_before": len(before["pages"]), "pages_after": len(after["pages"]),
               "pages_lost": sorted(set(before["pages"]) - set(after["pages"])),
               "new_page_neighbours": dict(Counter(
                   " | ".join(" ".join(blocks[j]["text"].split())[:60] for j in (i - 1, i + 1)
                              if 0 <= j < len(blocks))
                   for i in new_pages).most_common(6)),
               "new_furniture": [[i, blocks[i]["text"][:80]] for i in
                                 sorted(set(after["furniture"]) - set(before["furniture"]))][:40],
               "new_furniture_count": len(set(after["furniture"]) - set(before["furniture"]))}
        for key in ("D02", "D03"):
            gained = sorted(set(after[key]) - set(before[key]))
            lost = sorted(set(before[key]) - set(after[key]))
            if gained or lost:
                row[key] = {"gained": gained, "lost": lost,
                            "lost_text": [blocks[i]["text"][:80] for i in lost][:40]}
        for key in ("notes", "reasons"):
            if before[key] != after[key]:
                row[key] = {"before": before[key], "after": after[key]}
        rows.append(row)
        print(name, row["pages_before"], "->", row["pages_after"], {k: (len(v["gained"]), len(v["lost"]))
              for k, v in row.items() if k in ("D02", "D03")}, "notes" in row, flush=True)
    Path(out).write_text(json.dumps(rows, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                         encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
