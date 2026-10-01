"""Where each saved annual report prints its financial statements, relative to Item 8.

Usage: python3 appended_statements.py <restored source root> <out.json>

For every saved annual report (as page_foot_headings.py enumerates them): the
located Item 8 range, the note headings the frozen note scan's pattern finds
inside it and after it, and - where Item 8 holds none and the notes come after
it - the first note heading after Item 8 and the keyword blocks from there to the
end of the document that no located item range holds. A report whose Item 8 is a
pointer page has its statements printed after the form's items; the keyword
proxy reads Item 8 only, so it reads none of them. Zero calls.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_foot_headings import annual_reports  # noqa: E402
from vnext.text_business_candidates import _LEGAL, _NOTE_HEADING, _PATTERNS  # noqa: E402


def note_headings(blocks):
    """The frozen note scan's heading test, one block at a time."""
    return [i for i, b in enumerate(blocks)
            if not b["linked"] and b.get("emphasized") and len(b["text"]) <= 300
            and _NOTE_HEADING.match(b["text"]) and not _PATTERNS["continued_heading"].search(b["text"])]


def describe(document):
    blocks = document["blocks"]
    item_8 = document["sections"]["ITEM_8"]["candidates"]
    if len(item_8) != 1:
        return {"item_8": None}
    start, stop = item_8[0]["start_block"], item_8[0]["end_block_exclusive"]
    headings = note_headings(blocks)
    inside = [i for i in headings if start <= i < stop]
    after = [i for i in headings if i >= stop]
    row = {"item_8": [start, stop], "note_headings_inside": len(inside),
           "note_headings_after": len(after), "blocks": len(blocks)}
    if not inside and after:
        located = [(c["start_block"], c["end_block_exclusive"])
                   for value in document["sections"].values() for c in value["candidates"]]
        first = after[0]
        row["first_note_heading_after"] = {"i": first, "text": blocks[first]["text"][:100]}
        row["keyword_blocks_after"] = [
            {"i": i, "text": blocks[i]["text"][:160]} for i in range(first, len(blocks))
            if _LEGAL.search(blocks[i]["text"]) and not any(a <= i < b for a, b in located)]
    return row


def main(root, out_path):
    rows = []
    for name, document, problem in annual_reports(root):
        row = {"file": name, "error": problem} if document is None else {"file": name, **describe(document)}
        rows.append(row)
        print(name, row.get("error") or (row.get("note_headings_inside"), row.get("note_headings_after"),
              row.get("first_note_heading_after"), len(row.get("keyword_blocks_after", []))), flush=True)
    Path(out_path).write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
