#!/usr/bin/env python3
"""Fault injections for the item reader's reference check: any case, visible text, the heading's own block.

Each injection edits one file in place, runs the class aimed at it, restores
the file byte for byte in a ``finally`` and checks the restore. It counts as
caught only when the run fails and the named case is among the failures or
errors; an edit that does not apply exactly once, or does not compile, stops
the script before anything runs. Bytecode goes to a fresh directory per run
(see visibility_injections._isolated_env).

The edits are made in place, so run this in a worktree of its own, never in a
checkout another job is reading. Zero SEC or provider calls:
    python3 docs/evidence/issue47_history/e01-item-text/reference_injections.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from visibility_injections import _failed_cases, _isolated_env  # noqa: E402

CLASS = "tests.vnext.test_historical_event_items.HeadingsAndReferences"
ITEMS = "scripts/vnext/historical_event_items.py"
TESTS = "tests/vnext/test_historical_event_items.py"
ANY_CASE = "test_a_reference_word_is_read_in_any_case"
HIDDEN = "test_a_hidden_line_break_or_long_hidden_text_does_not_end_the_reference"
BLOCK = "test_the_previous_block_does_not_make_a_heading_a_reference"
UNSEEN = "test_an_unseen_block_still_breaks_the_line"

INJECTIONS = [
    {"id": "A_REFERENCE_WORD_IS_LOWERCASE_ONLY",
     "old": "    r\"pursuant|such|also)|[\\u201c\\u2018\\\"'])\\s*$\", re.IGNORECASE)\n",
     "new": "    r\"pursuant|such|also)|[\\u201c\\u2018\\\"'])\\s*$\")\n",
     "expect": ANY_CASE,
     "why": "#28's control: 'SEE Item 2.01 Completion of ...' is a reference, not a heading"},
    {"id": "THE_FLAT_WINDOW_RETURNS",
     "old": "        if _REFERENCE_BEFORE.search(_visible_before(text=text, nodes=nodes, position=match.start())):\n",
     "new": "        if _REFERENCE_BEFORE.search(text[max(0, match.start() - _REFERENCE_WINDOW):match.start()]):\n",
     "expect": BLOCK,
     "why": "a word ending the previous paragraph would erase the next paragraph's heading"},
    {"id": "THE_WINDOW_CROSSES_BLOCKS",
     "old": "              if block == own[4] and hidden is None and start < position]\n",
     "new": "              if hidden is None and start < position]\n",
     "expect": BLOCK,
     "why": "the previous block's text is not this heading's sentence"},
    {"id": "THE_WINDOW_READS_HIDDEN_TEXT",
     "old": "              if block == own[4] and hidden is None and start < position]\n",
     "new": "              if block == own[4] and start < position]\n",
     "expect": HIDDEN,
     "why": "text a reader cannot see neither makes nor hides a reference"},
    {"id": "A_REMOVED_BLOCK_BREAKS_THE_LINE",
     "old": "        if tag in _BLOCK and not removed:\n",
     "new": "        if tag in _BLOCK:\n",
     "expect": HIDDEN,
     "why": "a display:none block has no box; the text on its two sides runs on"},
    {"id": "AN_UNSEEN_BLOCK_IS_REMOVED",
     "old": "        removed = (self.removed[-1] if self.removed else False) or _removed(tag, attributes, style)\n",
     "new": ("        removed = ((self.removed[-1] if self.removed else False) or _removed(tag, attributes, style)\n"
             "                   or _hidden_by_style(style) is not None\n"
             "                   or (attributes.get(\"aria-hidden\") or \"\").lower() == \"true\")\n"),
     "expect": UNSEEN,
     "why": "visibility:hidden or opacity:0 keeps a block's box and its line break"},
    {"id": "A_REMOVED_PARENT_DOES_NOT_CARRY",
     "old": "        removed = (self.removed[-1] if self.removed else False) or _removed(tag, attributes, style)\n",
     "new": "        removed = _removed(tag, attributes, style)\n",
     "expect": HIDDEN,
     "why": "a block inside a display:none element has no box either"},
    {"id": "IMPORTANT_HIDES_DISPLAY_NONE",
     "old": "            or any(name == \"display\" and value.replace(\"!important\", \"\") == \"none\"\n",
     "new": "            or any(name == \"display\" and value == \"none\"\n",
     "expect": HIDDEN,
     "why": "'display: none !important' removes the element as 'display:none' does"},
]


def _sha256(path):
    return "sha256:" + hashlib.sha256((REPO / path).read_bytes()).hexdigest()


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
    files = {path: _sha256(path) for path in (ITEMS, TESTS)}
    control = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=REPO, env=_isolated_env(),
                             capture_output=True, text=True, timeout=1800)
    if control.returncode != 0:
        print("CONTROL_FAILED", (control.stdout + control.stderr)[-2000:])
        return 2
    results = []
    path = REPO / ITEMS
    for injection in INJECTIONS:
        original = path.read_bytes()
        try:
            path.write_text(original.decode("utf-8").replace(injection["old"], injection["new"]),
                            encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=REPO, env=_isolated_env(),
                                 capture_output=True, text=True, timeout=1800)
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        failed = sorted(_failed_cases(run.stdout + run.stderr))
        caught = run.returncode != 0 and injection["expect"] in failed
        results.append({"id": injection["id"], "file": ITEMS, "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    if {path: _sha256(path) for path in files} != files:
        print("FILES_UNDER_TEST_CHANGED")
        return 2
    HERE.joinpath("reference-injections.json").write_text(json.dumps(
        {"record_type": "ISSUE_47_E01_REFERENCE_FAULT_INJECTIONS", "class": CLASS, "files_under_test": files,
         "control": "passed", "results": results, "calls": [0, 0, 0]}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
