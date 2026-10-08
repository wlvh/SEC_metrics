#!/usr/bin/env python3
"""#28's controls for its port of the item reader (4711a488), run on this Issue's reader before and after.

Each case is a constructed 8-K body; ``reader_sees`` is what a reader of the
rendered page takes as item headings, written down here, not computed by
either reader. The reader before the repair is the committed
``scripts/vnext/historical_event_items.py`` at ``--before`` (default
f25d3373); the reader after is the checkout's. Zero SEC or provider calls:
    python3 docs/evidence/issue47_history/e01-item-text/reference_controls.py
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import vnext  # noqa: E402,F401
from vnext import historical_event_items as after  # noqa: E402
from vnext.deterministic_router import _visible_text  # noqa: E402

ITEMS = "scripts/vnext/historical_event_items.py"
H = "Item 2.01 Completion of Acquisition or Disposition of Assets"
FIRST = "Item 8.01 Other Events."


def _html(*paragraphs):
    return ("<html><body>" + "".join("<p>" + p + "</p>" for p in paragraphs) + "</body></html>")


# (name, body, what a reader of the page takes as headings, #28's control or this reader's own)
CASES = [
    ("a lowercase reference", _html(FIRST, "see " + H + "."), ["8.01"], "control"),
    ("a capitalised reference", _html(FIRST, "See " + H + "."), ["8.01"], "control"),
    ("an uppercase reference", _html(FIRST, "SEE " + H + "."), ["8.01"], "control"),
    ("an uncaptioned reference", _html(FIRST, "See Item 2.01."), ["8.01"], "how 'does not reproduce' was measured"),
    ("the previous paragraph ends in a state code", _html(FIRST, "Location: Portland, OR", H, "The sale closed."),
     ["8.01", "2.01"], "control"),
    ("the previous paragraph ends in 'see'", _html(FIRST, "The details are set out below; see", H,
                                                   "The sale closed."), ["8.01", "2.01"], "control"),
    ("the previous paragraph ends in 'and'", _html(FIRST, "Text continues and", H, "The sale closed."),
     ["8.01", "2.01"], "control"),
    ("hidden 'see' before a heading", _html(FIRST, "<span hidden>see</span>" + H), ["8.01", "2.01"], "control"),
    ("hidden 'SEE' before a heading", _html(FIRST, "<span hidden>SEE</span>" + H), ["8.01", "2.01"], "control"),
    ("long hidden text after 'SEE'", _html(FIRST, 'SEE <span style="display:none">' + "x" * 200 + "</span>" + H
                                       + "."), ["8.01"], "control"),
    ("a hidden line break after 'SEE'", _html(FIRST, "SEE <br hidden>" + H + "."), ["8.01"], "control"),
    ("a block out of the layout after 'SEE'", _html(FIRST, 'SEE <div style="display:none">x</div>' + H + "."),
     ["8.01"], "this reader's block rule"),
    ("an unseen block after 'SEE'", _html(FIRST, 'SEE <div style="visibility:hidden">x</div>' + H + "."),
     ["8.01", "2.01"], "this reader's block rule"),
]


def _reader_before(commit):
    source = subprocess.run(["git", "show", commit + ":" + ITEMS], cwd=REPO, check=True,
                            capture_output=True).stdout
    spec = importlib.util.spec_from_loader("vnext._reader_before", loader=None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(source, ITEMS + "@" + commit, "exec"), module.__dict__)
    return module


def _headings_before(module, raw):
    text = _visible_text(raw_bytes=raw)
    return [code for *_, code in module.item_headings(text)]


def _headings_after(raw):
    text = _visible_text(raw_bytes=raw)
    return [code for *_, code in after.item_headings(text, after._text_nodes(raw_bytes=raw, text=text))]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="f25d3373")
    args = parser.parse_args(argv)
    before = _reader_before(args.before)
    rows = []
    for name, body, sees, origin in CASES:
        raw = body.encode("utf-8")
        rows.append({"case": name, "origin": origin, "body": body, "reader_sees": sees,
                     "before": _headings_before(before, raw), "after": _headings_after(raw)})
        rows[-1]["before_right"] = rows[-1]["before"] == sees
        rows[-1]["after_right"] = rows[-1]["after"] == sees
        print(f"{name:42s} before={rows[-1]['before']} after={rows[-1]['after']} reader={sees}")
    HERE.joinpath("reference-controls.json").write_text(json.dumps(
        {"record_type": "ISSUE_47_E01_REFERENCE_CONTROLS", "before_commit": args.before,
         "cases": rows, "before_wrong": sum(not row["before_right"] for row in rows),
         "after_wrong": sum(not row["after_right"] for row in rows), "calls": [0, 0, 0]},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(row["after_right"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
