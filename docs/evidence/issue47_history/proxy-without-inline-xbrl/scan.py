"""Which saved proxy statements carry inline XBRL.

Usage: python3 scan.py <restored source root> <out.json>

Every saved HTML document whose first 60 KB of text names a Schedule 14A is
listed once (by name and size) with whether it holds any inline XBRL element.
Zero calls.
"""
import glob
import html
import json
import os
import re
import sys
from pathlib import Path


def main(root, out):
    evidence = Path(root) / "evidence"
    rows, seen = [], set()
    for path in sorted(glob.glob(str(evidence / "request_attempts/*/*/*.htm"))
                       + glob.glob(str(evidence / "accession_materials/*/*.htm"))):
        raw = open(path, "rb").read()
        head = re.sub(r"<[^>]+>", " ", html.unescape(raw[:60000].decode("utf-8", "replace")))
        if not re.search(r"SCHEDULE\s*14A", head, re.I):
            continue
        key = (os.path.basename(path), len(raw))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"document": key[0], "bytes": key[1], "inline_xbrl": b"<ix:" in raw.lower()})
    record = {"documents": rows, "without_inline_xbrl": sorted(r["document"] for r in rows if not r["inline_xbrl"])}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
