"""Apply each injection to the note reader, run its tests, restore; record what caught it.

Usage (from the repository root, clean tree):
    python3 docs/evidence/issue47_history/part-iii-statement-review/fault_injections.py \
        docs/evidence/issue47_history/part-iii-statement-review/fault-injections.json
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
T = "tests.vnext.test_historical_amendment_note"
NOTE = "scripts/vnext/historical_amendment_note.py"
INJECTIONS = [
    ("COUNT_BLOCKS_NOT_PARAGRAPHS", NOTE,
     '    _need(1 <= len(paragraphs) <= NOTE_PARAGRAPH_BOUND,',
     '    _need(1 <= end - start - 1 <= NOTE_PARAGRAPH_BOUND,'),
    ("ACCEPT_ANY_CONTINUATION", NOTE,
     '    + " to include the information required by such Items(?P<continuation>\\\\.|, rather than"',
     '    + " to include the information required by such Items(?P<continuation>[.,].*$|, rather than"'),
    ("THE_APPROVED_WIDE_MIDDLE", NOTE,
     '    "(?:solely )?to amend Part III, Items 10, 11, 12, 13 and 14 of the " + _FORM',
     '    "(?:solely )?to amend Part III, Items 10, 11, 12, 13 and 14 .+? of the " + _FORM'),
    ("READ_ONLY_THE_FIRST_SENTENCE_OF_A_PARAGRAPH", NOTE,
     '        for sentence in sentences(paragraph["text"]):',
     '        for sentence in sentences(paragraph["text"])[:1]:'),
    ("NO_POINTER_CHECK", NOTE,
     '        if (_date(intro["period"]), _date(intro["filed"])) != (period_end, original_filed):',
     '        if False:'),
    ("NO_CHANGE_STATEMENT_NOT_REQUIRED", NOTE,
     '    _need(kinds.count("PURPOSE") == 1 and kinds.count("NO_CHANGE") == 1,',
     '    _need(kinds.count("PURPOSE") == 1,'),
    ("ANY_REGISTRANT_IN_DEFINED_TERMS", NOTE,
     '    if defined and any(_words(defined["name"]) == _words(name) for name in names):',
     '    if defined:'),
    ("SKIP_THE_PART_III_STRUCTURE", NOTE,
     '    _need(parts == {"PART III", "PART IV"} and items == {"10", "11", "12", "13", "14", "15"}\n'
     '          and len(statements) == 1 and governance, "PART_III_ONLY_SOURCE_SCOPE_NOT_PROVEN")',
     '    pass'),
]


def main():
    out = []
    for name, path, old, new in INJECTIONS:
        target = REPO / path
        original = target.read_bytes()
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        try:
            target.write_text(text.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", T], cwd=REPO,
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
