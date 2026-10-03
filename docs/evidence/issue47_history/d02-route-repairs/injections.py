#!/usr/bin/env python3
"""Fault injections for the four D02 route repairs: each must be caught by the case written for it.

Each injection undoes one part of a repair in
``scripts/vnext/historical_text_results.py``; the case named for it must fail.
An edit that does not apply exactly once or does not compile stops the script,
the file is restored byte for byte and checked, and every run reads and writes
bytecode only in a fresh directory. The control run must pass first. Run it in a
clone: it edits the route file in place while it runs.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/d02-route-repairs/injections.py
"""
import atexit
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MODULE = "tests.vnext.test_historical_d02_route_repairs"
ROUTE = "scripts/vnext/historical_text_results.py"
FOOT = MODULE + ".AHeadingAtThePageFootTest"
FURNITURE = MODULE + ".FurnitureByItsPlaceOnThePageTest"
CAPTIONS = MODULE + ".CaptionsTheNoteDoesNotCarryTest"
POINTER = MODULE + ".StatementsPrintedAfterAPointerPageTest"
INJECTIONS = [
    {"id": "PAGE_FOOT_HEADINGS_ARE_NOT_ADDED",
     "old": "    return headings, [h for h in headings if h not in frozen_headings]\n",
     "new": "    return frozen_headings, []\n",
     "expect": FOOT + ".test_item_three_closes_at_item_four_printed_above_the_page_number",
     "edit": "page_bottom_item_headings() adds nothing",
     "why": "Item 3 runs past a heading printed at the page foot again"},
    {"id": "A_HEADING_THAT_MOVES_NOTHING_IS_RECORDED",
     "old": "    if base == document[\"sections\"]:\n        added = []\n",
     "new": "",
     "expect": FOOT + ".test_a_page_foot_heading_that_moves_no_section_leaves_the_document_as_it_was",
     "edit": "a page-foot heading that moves no section still rewrites the document",
     "why": "a report whose ranges did not change would get a new document identity"},
    {"id": "THE_SECTION_DERIVATION_DRIFTS",
     "old": "                               \"closing_heading\": following})\n",
     "new": "                               \"closing_heading\": dict(following, drifted=True)})\n",
     "expect": FOOT + ".test_the_section_derivation_is_the_frozen_one",
     "edit": "_sections_from() no longer rebuilds the frozen sections exactly",
     "why": "the successor's derivation would stop being the frozen one"},
    {"id": "NO_FURNITURE_BY_PLACE",
     "old": "    on_the_page = page_structure_furniture(document[\"blocks\"])\n",
     "new": "    on_the_page = set()\n",
     "expect": FURNITURE + ".test_the_item_three_footer_leaves_and_the_sentence_stays",
     "edit": "page-position furniture is not applied",
     "why": "Pfizer's footers become excerpts again"},
    {"id": "THE_WALK_DOES_NOT_STOP_AT_A_BLOCK_THAT_DOES_NOT_RECUR",
     "old": "                   and seen[(offset, texts[index])] >= 3):\n",
     "new": "                   ):\n",
     "expect": FURNITURE + ".test_the_item_three_footer_leaves_and_the_sentence_stays",
     "edit": "every block within reach of a page number is furniture",
     "why": "the Item 3 sentence three blocks above the page number would be dropped"},
    {"id": "FURNITURE_BY_PLACE_IS_SKIPPED_FOR_D03_TOO",
     "old": "        furniture = set(scope.get(\"repeated_furniture_blocks\", ()))\n        running_header = d02_furniture.get(id(scope), frozenset()) | on_the_page\n",
     "new": "        furniture = set(scope.get(\"repeated_furniture_blocks\", ())) | on_the_page\n        running_header = d02_furniture.get(id(scope), frozenset()) | on_the_page\n",
     "expect": FURNITURE + ".test_d03_keeps_what_the_repair_takes_out_of_d02",
     "edit": "page-position furniture is skipped for D03's candidates as well",
     "why": "D03's measured ranges would move under a D02 repair; no saved filing prints D03's words in a footer, so only the constructed case can tell"},
    {"id": "UNCARRIED_CAPTIONS_ARE_IGNORED",
     "old": "    return sorted({caption for caption in quoted\n                   if caption not in carried and not _QUOTED_FORM_ITEM.match(caption)})\n",
     "new": "    return []\n",
     "expect": CAPTIONS + ".test_the_whole_note_is_not_taken_in_their_place",
     "edit": "unincorporable_captions() never reports a caption",
     "why": "Lumen FY2021's whole note, commitments included, is taken again"},
    {"id": "THE_NOTE_S_NUMBERED_TITLE_IS_NOT_ITS_TITLE",
     "old": "            carried |= {title, _NOTE_NUMBER_PREFIX.sub(\"\", title, count=1)}\n",
     "new": "            carried |= {title}\n",
     "expect": CAPTIONS + ".test_a_quoted_note_title_is_not_a_missing_caption",
     "edit": "the note heading is compared with its number",
     "why": "Salesforce's quoted note title would read as a missing caption and stop its D02"},
    {"id": "A_QUOTED_FORM_ITEM_IS_A_CAPTION",
     "old": "                   if caption not in carried and not _QUOTED_FORM_ITEM.match(caption)})\n",
     "new": "                   if caption not in carried})\n",
     "expect": CAPTIONS + ".test_a_quoted_form_item_says_where_the_note_is_not_which_part",
     "edit": "a quoted Form 10-K item is read as a caption the note must carry",
     "why": "every Paramount year stops as navigation incomplete"},
    {"id": "ONE_FOUND_CAPTION_IS_ENOUGH",
     "old": "    return sorted({caption for caption in quoted\n                   if caption not in carried and not _QUOTED_FORM_ITEM.match(caption)})\n",
     "new": "    missing = sorted({caption for caption in quoted\n                      if caption not in carried and not _QUOTED_FORM_ITEM.match(caption)})\n    return missing if len(missing) == len(set(quoted)) else []\n",
     "expect": CAPTIONS + ".test_one_missing_caption_of_two_is_enough",
     "edit": "a note is stopped only when none of its quoted captions is found",
     "why": "one found caption would silently stand for two"},
    {"id": "THE_APPENDED_STATEMENTS_ARE_NOT_READ",
     "old": "    if appended is not None:\n        ranges.append(appended)\n",
     "new": "",
     "expect": POINTER + ".test_the_statements_are_read_through_the_keyword_and_nothing_else_moves",
     "edit": "the statements after a pointer-page Item 8 are not added",
     "why": "Macy's FY2021 claims accrual is missing again"},
    {"id": "THE_APPENDED_STATEMENTS_ARE_READ_WHOLE",
     "old": "                or section in (ITEM_8, APPENDED_STATEMENTS) and _LEGAL.search(text))\n",
     "new": "                or section == APPENDED_STATEMENTS or section == ITEM_8 and _LEGAL.search(text))\n",
     "expect": POINTER + ".test_the_statements_are_read_through_the_keyword_and_nothing_else_moves",
     "edit": "every block of the appended statements is an excerpt",
     "why": "whole statements would be taken as litigation disclosure"},
    {"id": "THE_APPENDED_STATEMENTS_FEED_D03",
     "old": "            if section != APPENDED_STATEMENTS and (_ACTION.search(text) or _AUTHORITY.search(text)):\n",
     "new": "            if (_ACTION.search(text) or _AUTHORITY.search(text)):\n",
     "expect": POINTER + ".test_the_statements_are_read_through_the_keyword_and_nothing_else_moves",
     "edit": "the appended statements add D03 candidates",
     "why": "D03's measured candidates would move under a D02 repair"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory."""
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def _reason(output, case):
    """The exception line of the named case's traceback: what actually failed.

    A case can fail for a reason that has nothing to do with the injection - an
    import error, a missing file - and still be listed as failed. The reason is
    recorded beside the verdict so a reader can see the catch is the one the
    case was written for.
    """
    found = re.search(r"^(?:FAIL|ERROR): " + re.escape(case) + r" .*?\n-{20,}\n(.*?)(?=\n={20,}|\n-{20,}|\Z)",
                      output, re.M | re.S)
    if not found:
        return None
    lines = [line for line in found.group(1).splitlines() if line.strip()]
    raised = [line for line in lines if re.match(r"^[A-Za-z_][\w.]*(?:Error|Exception|Exit)\b", line)]
    return (raised[0] if raised else lines[-1])[:400] if lines else None


def _run(selector):
    started = time.time()
    run = subprocess.run([sys.executable, "-m", "unittest", selector], cwd=REPO,
                         env=_isolated_env(), capture_output=True, text=True, timeout=3600)
    return run, int(time.time() - started)


def _stop(signum, _frame):
    """A stop by signal unwinds through the restore, instead of leaving an edit in place."""
    raise SystemExit("INJECTIONS_INTERRUPTED_BY_SIGNAL_" + str(signum))


def main():
    for stop in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(stop, _stop)
    control, seconds = _run(MODULE)
    if control.returncode != 0:
        print("CONTROL_RUN_FAILED", (control.stdout + control.stderr)[-2500:])
        return 2
    print("control passed in", seconds, "s", flush=True)
    results = []
    path = REPO / ROUTE
    for injection in INJECTIONS:
        original = path.read_bytes()
        text = original.decode("utf-8")
        found = text.count(injection["old"])
        if found != 1:
            print("INJECTION_DID_NOT_APPLY", injection["id"], found)
            return 2
        edited = text.replace(injection["old"], injection["new"])
        try:
            compile(edited, str(path), "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
        try:
            path.write_text(edited, encoding="utf-8")
            run, seconds = _run(injection["expect"])
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        expected = injection["expect"].rsplit(".", 1)[-1]
        caught = run.returncode != 0 and expected in failed
        summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        results.append({"id": injection["id"], "file": ROUTE, "edit": injection["edit"],
                        "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "expected_case_failure": _reason(output, expected),
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s",
              results[-1]["expected_case_failure"], flush=True)
    out = Path(__file__).with_name("injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_D02_ROUTE_REPAIR_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
