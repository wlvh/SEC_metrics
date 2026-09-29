#!/usr/bin/env python3
"""Fault injections for E01's item-text visibility and end checks.

Each injection edits scripts/vnext/historical_event_items.py in place, runs the
class aimed at it, restores the file byte for byte in a ``finally`` and checks
the restore. An injection counts as caught only when the run fails AND the
named case is among the failures or errors; an edit that does not apply
exactly once, or does not compile, stops the script before anything runs.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/e01-item-text/visibility_injections.py
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CLASS = "tests.vnext.test_historical_event_items.TextAReaderCannotSeeNeverEntersTheItem"
ITEMS = "scripts/vnext/historical_event_items.py"

INJECTIONS = [
    {"id": "VISIBILITY_IS_NOT_CHECKED",
     "old": '    _need(hidden is None, "EVENT_ITEM_TEXT_A_READER_CANNOT_SEE:" + item_code + ":" + str(hidden))\n',
     "new": "",
     "expect": "test_hidden_text_inside_the_item_is_refused",
     "why": "the frozen view keeps hidden text; without the check it goes to the model as the item's text"},
    {"id": "IX_HIDDEN_IS_DISPLAYED",
     "old": '                         "ix:hidden"))\n',
     "new": '                         ))\n',
     "expect": "test_hidden_text_inside_the_item_is_refused",
     "why": "every saved 8-K carries its inline-XBRL header in ix:hidden"},
    {"id": "ONLY_AN_EXACT_ZERO_OPACITY_HIDES",
     "old": '        if name == "opacity" and (number is None or number[0] * (0.01 if number[1] == "%" else 1)\n'
            '                                  < 0.1):\n',
     "new": '        if name == "opacity" and number is not None and number[0] == 0:\n',
     "expect": "test_text_styled_so_it_cannot_be_seen_is_refused",
     "why": "a percentage, a near-zero value or an unreadable value hides text as well as 0 does"},
    {"id": "TRANSPARENT_COLOUR_IS_VISIBLE",
     "old": '                or (name == "color" and (value == "transparent"\n'
            '                                         or re.fullmatch(r"rgba\\([^)]*,0*\\.?0*\\)", value)))):\n',
     "new": '                ):\n',
     "expect": "test_text_styled_so_it_cannot_be_seen_is_refused",
     "why": "an independent review of #28's component found color:transparent accepted"},
    {"id": "ANY_INLINE_COLOUR_OR_POSITION_IS_UNCERTAIN",
     "old": '    for declaration in style.split(";"):\n',
     "new": '    if re.search(r"(?:^|;)(?:color|position|background|background-color):", style):\n'
            '        return "broad"\n'
            '    for declaration in style.split(";"):\n',
     "expect": "test_ordinary_formatting_is_not_hiding",
     "why": "measured: a broad rule refuses 36 of the 56 saved candidate items"},
    {"id": "THE_END_HEADING_IS_COUNTED_BY_RUNS",
     "old": '        _need(sum(1 for position, _, code in headings if code == end_code and position > start) == 1,\n',
     "new": '        _need(sum(1 for run in runs if run[0][2] == end_code) == 1,\n',
     "expect": "test_a_cross_reference_that_looks_like_the_next_heading_is_refused",
     "why": "adjacent headings of one code merge into one run, so a reference and the real heading count once"},
    {"id": "THE_SIGNATURES_ARE_NOT_CHECKED",
     "old": '        _need(len(_SIGNATURES.findall(text, start)) == 1,\n',
     "new": '        _need(True,\n',
     "expect": "test_a_second_signatures_word_is_refused_rather_than_cut_at",
     "why": "an upper-case SIGNATURE word inside the item would end it there silently"},
    {"id": "THE_REBUILT_VIEW_IS_TRUSTED",
     "old": '    _need(" ".join(node for node, _ in parser.nodes) == text, "EVENT_ITEM_TEXT_VIEW_NOT_REBUILT")\n',
     "new": "",
     "expect": "test_a_view_the_check_cannot_rebuild_is_refused_not_trusted",
     "why": "offsets from a rebuild that differs from the frozen view point at the wrong nodes"},
    {"id": "HIDDEN_TEXT_OUTSIDE_THE_SPAN_REFUSES",
     "old": '        if hidden is not None and offset < end and offset + len(node) > start:\n',
     "new": '        if hidden is not None:\n',
     "expect": "test_hidden_text_outside_the_item_is_not_this_item_s",
     "why": "every saved 8-K has hidden text above its first item; refusing on it refuses every item"},
]


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def main():
    for injection in INJECTIONS:
        text = (REPO / ITEMS).read_text(encoding="utf-8")
        found = text.count(injection["old"])
        if found != 1:
            print("INJECTION_DID_NOT_APPLY", injection["id"], found)
            return 2
        try:
            compile(text.replace(injection["old"], injection["new"]), ITEMS, "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
    results = []
    path = REPO / ITEMS
    for injection in INJECTIONS:
        original = path.read_bytes()
        try:
            path.write_text(original.decode("utf-8").replace(injection["old"], injection["new"]),
                            encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=REPO,
                                 capture_output=True, text=True, timeout=1800)
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        caught = run.returncode != 0 and injection["expect"] in failed
        summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        results.append({"id": injection["id"], "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary)})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    out = Path(__file__).with_name("visibility-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_E01_ITEM_VISIBILITY_FAULT_INJECTIONS",
                               "file": ITEMS, "class": CLASS, "results": results,
                               "calls": [0, 0, 0]}, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
