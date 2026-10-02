#!/usr/bin/env python3
"""Fault injections for E01's check that a document heads no candidate item its header omits.

Each injection edits one file in place, runs the class aimed at it, restores
the file byte for byte in a ``finally`` and checks the restore. It counts as
caught only when the run fails and the named case is among the failures or
errors; an edit that does not apply exactly once, or does not compile, stops
the script before anything runs. Bytecode goes to a fresh directory per run
(see visibility_injections._isolated_env).

The edits are made in place, so run this in a worktree of its own, never in a
checkout another job is reading. Zero SEC or provider calls:
    python3 docs/evidence/issue47_history/e01-item-text/header_document_injections.py
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

CLASS = "tests.vnext.test_historical_event_items.ACandidateTheHeaderOmitsStopsTheWindow"
ITEMS = "scripts/vnext/historical_event_items.py"
RESULTS = "scripts/vnext/historical_zero_ai_results.py"

INJECTIONS = [
    {"id": "THE_UNLISTED_HEADING_IS_NOT_CHECKED", "file": ITEMS,
     "old": '        _need(not unlisted, HEADED_NOT_LISTED + ":" + accession + ":" + ",".join(unlisted))\n',
     "new": "",
     "expect": "test_the_saved_filing_whose_header_omits_its_item_2_01",
     "why": "the window would be confirmed and counted without the Seagen completion"},
    {"id": "A_LINKED_HEADING_IS_HEADED", "file": ITEMS,
     "old": "            if not _linked_in_span(nodes=nodes, start=start, end=end)}\n",
     "new": "            }\n",
     "expect": "test_a_contents_link_to_an_unlisted_candidate_is_not_a_heading",
     "why": "a contents entry names an item without heading it"},
    {"id": "EVERY_UNLISTED_CODE_STOPS", "file": ITEMS,
     "old": "        unlisted = sorted((headed_item_codes(raw_bytes=raw) & set(codes)) - items)\n",
     "new": "        unlisted = sorted(headed_item_codes(raw_bytes=raw) - items)\n",
     "expect": "test_an_unlisted_heading_of_a_code_the_route_does_not_count_is_not_its_business",
     "why": "nine saved 8-Ks head a 9.01 their header omits; E01 does not count 9.01"},
    {"id": "ONLY_THE_FIRST_FILING_IS_CHECKED", "file": ITEMS,
     "old": "    for accession, (references, items) in sorted(listed.items()):\n",
     "new": "    for accession, (references, items) in sorted(listed.items())[:1]:\n",
     "expect": "test_one_filing_s_omission_stops_the_window_whatever_the_others_list",
     "why": "a window holds many filings and any one of them can carry the omission"},
    {"id": "THE_STOP_READS_AS_AN_ITEM_NOT_FOUND", "file": RESULTS,
     "old": '            reason_code=(HEADED_NOT_LISTED_REASON if str(error).startswith(HEADED_NOT_LISTED + ":")\n'
            '                         else NOT_LOCATED_REASON if error.category == "IMPLEMENTATION_GAP"\n',
     "new": '            reason_code=(NOT_LOCATED_REASON if error.category == "IMPLEMENTATION_GAP"\n',
     "expect": "test_the_route_withholds_the_window_with_its_own_reason",
     "why": "an omitted header item and an item whose text was not found are different gaps"},
]


def main():
    for injection in INJECTIONS:
        text = (REPO / injection["file"]).read_text(encoding="utf-8")
        found = text.count(injection["old"])
        if found != 1:
            print("INJECTION_DID_NOT_APPLY", injection["id"], found)
            return 2
        try:
            compile(text.replace(injection["old"], injection["new"]), injection["file"], "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
    control = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=REPO, env=_isolated_env(),
                             capture_output=True, text=True, timeout=1800)
    if control.returncode != 0:
        print("CONTROL_FAILED", (control.stdout + control.stderr)[-2000:])
        return 2
    results = []
    for injection in INJECTIONS:
        path = REPO / injection["file"]
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
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        caught = run.returncode != 0 and injection["expect"] in failed
        results.append({"id": injection["id"], "file": injection["file"], "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    HERE.joinpath("header-document-injections.json").write_text(json.dumps(
        {"record_type": "ISSUE_47_E01_HEADER_DOCUMENT_FAULT_INJECTIONS", "class": CLASS,
         "control": "passed", "results": results, "calls": [0, 0, 0]}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
