"""Apply each injection in place, run the named tests, restore; record what caught it.

Usage (from the repository root, clean tree):
    python3 docs/evidence/issue47_history/e01-item-text/fault_injections.py \
        docs/evidence/issue47_history/e01-item-text/fault-injections.json

Each file is restored from its own bytes in a ``finally`` block, so an
interrupted run leaves no injection behind.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
T = "tests.vnext.test_historical_event_items"
ITEMS = "scripts/vnext/historical_event_items.py"
ROUTE = "scripts/vnext/historical_zero_ai_results.py"
INJECTIONS = [
    ("READ_THE_BRIEF_NOT_THE_ITEM", ITEMS,
     '        normalised, occurrences = alias_occurrences(text=body["text"], aliases=keyword[code])',
     '        normalised, occurrences = alias_occurrences(text=attributes["brief"], aliases=keyword[code])',
     [T]),
    ("READ_ONLY_THE_FROZEN_BRIEF_WINDOW", ITEMS,
     '        normalised, occurrences = alias_occurrences(text=body["text"], aliases=keyword[code])',
     '        normalised, occurrences = alias_occurrences(text=body["text"][:300], aliases=keyword[code])',
     [T]),
    ("READ_TO_THE_END_OF_THE_DOCUMENT", ITEMS,
     '    if later and (signatures is None or later[0] < signatures.start()):',
     '    if False:',
     [T]),
    ("PUBLISH_THE_DIRECT_COUNT_WHEN_AN_ALIAS_IS_THERE", ROUTE,
     '                if keyword["status"] == "MEANING_PENDING":',
     '                if False:',
     [T]),
    ("ANY_LOWERCASE_WORD_MAKES_A_REFERENCE", ITEMS,
     '    r"(?:\\b(?:this|that|these|those|in|into|under|and|or|of|to|see|with|from|by|per|"',
     '    r"(?:\\b(?:[a-z][A-Za-z]*|this|that|these|those|in|into|under|and|or|of|to|see|with|from|by|per|"',
     [T]),
    ("A_QUOTE_DOES_NOT_MAKE_A_REFERENCE", ITEMS,
     '    r"pursuant|such|also)|[\\u201c\\u2018\\"\'])\\s*$")',
     '    r"pursuant|such|also))\\s*$")',
     [T]),
    ("EACH_SUB_ITEM_HEADING_IS_ITS_OWN_ITEM", ITEMS,
     '        if runs and runs[-1][-1][2] == heading[2]:',
     '        if False:',
     [T]),
    ("TAKE_THE_FIRST_OF_TWO_HEADINGS", ITEMS,
     '    _need(len(own) == 1, "EVENT_ITEM_HEADED_MORE_THAN_ONCE:" + item_code)',
     '    pass',
     [T]),
    ("DIRECT_ONLY_ROUTES_ARE_READ_TOO", ROUTE,
     '            if route["keyword_item_rules"]:',
     '            if True:',
     [T]),
]


def main():
    out = []
    for name, path, old, new, tests in INJECTIONS:
        target = REPO / path
        original = target.read_bytes()
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        try:
            target.write_text(text.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", *tests], cwd=REPO,
                                 capture_output=True, text=True, timeout=2400)
            tail = run.stderr.strip().splitlines()
            failed = sorted({line.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
                             for line in tail if line.startswith(("FAIL:", "ERROR:"))})
            out.append({"id": name, "file": path,
                        "outcome": "CAUGHT" if run.returncode else "NOT_CAUGHT",
                        "caught_by": failed, "suite_result": tail[-1] if tail else ""})
        finally:
            target.write_bytes(original)
        print(json.dumps(out[-1]), flush=True)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
