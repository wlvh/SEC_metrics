#!/usr/bin/env python3
"""Fault injections for the linear page-number footer and the XBRL parse block.

Each injection undoes one part of the change - in the page-number reading
(``scripts/vnext/historical_text_results.py``) or in the parse block
(``scripts/vnext/historical_xbrl_parse.py``) - and the case named for it must
fail. An edit that does not apply exactly once or does not compile stops the
script; the file is restored byte for byte and checked after every run, and
every run reads and writes bytecode only in a fresh directory. The control
runs must pass first. Run it in a clone: it edits the files in place.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/saved-source-time/injections.py
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
ROUTE = "scripts/vnext/historical_text_results.py"
BLOCK = "scripts/vnext/historical_xbrl_parse.py"
PAGES = "tests.vnext.test_historical_page_numbered"
PARSE = "tests.vnext.test_historical_xbrl_parse"
READING = PAGES + ".ThePageNumberReadingIsTheOldPatternsTest"
FOOTERS = PAGES + ".TheFooterSetIsTheOldOnesTest"
LINEAR = PAGES + ".TheReadingIsLinearTest"
ONCE = PARSE + ".OneParsePerDocumentTest"
BINDINGS = PARSE + ".TheBindingsAreSwappedOnlyInsideTest"
INJECTIONS = [
    {"id": "NO_LOOKBEHIND", "file": ROUTE,
     "old": '_PAGE_SUFFIX = re.compile(r"(?<![\\s|\\-\\u2013\\u2014])[\\s|\\-\\u2013\\u2014]+(\\d{1,4})$")\n',
     "new": '_PAGE_SUFFIX = re.compile(r"[\\s|\\-\\u2013\\u2014]+(\\d{1,4})$")\n',
     "expect": LINEAR + ".test_a_long_separator_run",
     "why": "a run of separators is walked again from each of its positions"},
    {"id": "THE_OLD_PATTERN_IS_BACK", "file": ROUTE,
     "old": ('    suffix = _PAGE_SUFFIX.search(text)\n    if suffix is None:\n        return None\n'
             '    stem = text[:suffix.start()]\n'),
     "new": ('    found = re.match(r"^(?P<stem>.*?[A-Za-z].*?)[\\s|\\-\\u2013\\u2014]+(?P<page>\\d{1,4})$",'
             ' text)\n    return None if found is None else (found["stem"], found["page"])\n'
             '    stem = text\n'),
     "expect": LINEAR + ".test_a_long_paragraph",
     "why": "the backtracking pattern returns, and a paragraph costs the square of its length"},
    {"id": "A_STEM_MAY_SPAN_LINES", "file": ROUTE,
     "old": '    if "\\n" in stem or _ASCII_LETTER.search(stem) is None:\n',
     "new": '    if _ASCII_LETTER.search(stem) is None:\n',
     "expect": READING + ".test_every_crafted_string_gets_the_same_answer",
     "why": "the old pattern's stem never crossed a line break"},
    {"id": "A_STEM_NEEDS_NO_LETTER", "file": ROUTE,
     "old": '    if "\\n" in stem or _ASCII_LETTER.search(stem) is None:\n',
     "new": '    if "\\n" in stem:\n',
     "expect": READING + ".test_every_crafted_string_gets_the_same_answer",
     "why": "a bare number would become a footer stem"},
    {"id": "FIVE_DIGIT_PAGES", "file": ROUTE,
     "old": '[\\s|\\-\\u2013\\u2014]+(\\d{1,4})$")\n',
     "new": '[\\s|\\-\\u2013\\u2014]+(\\d{1,5})$")\n',
     "expect": READING + ".test_every_crafted_string_gets_the_same_answer",
     "why": "a five-digit number would be read as a page"},
    {"id": "ANY_LETTER_COUNTS", "file": ROUTE,
     "old": '_ASCII_LETTER = re.compile(r"[A-Za-z]")\n',
     "new": '_ASCII_LETTER = re.compile(r"[^\\W\\d_]")\n',
     "expect": READING + ".test_every_crafted_string_gets_the_same_answer",
     "why": "the old pattern counted only ASCII letters"},
    {"id": "A_NUMBERED_NEIGHBOUR_DOES_NOT_RECUR", "file": ROUTE,
     "old": ('        return ((stem_of[index] is not None and len(stems[stem_of[index]]) >= 3)\n'
             '                or texts[normalized[index]] >= 3)\n'),
     "new": '        return texts[normalized[index]] >= 3\n',
     "expect": FOOTERS + ".test_generated_documents_and_ranges",
     "why": "two footers that only recur as numbered stems would stop counting each other"},
    {"id": "A_REPEATED_NEIGHBOUR_DOES_NOT_RECUR", "file": ROUTE,
     "old": ('        return ((stem_of[index] is not None and len(stems[stem_of[index]]) >= 3)\n'
             '                or texts[normalized[index]] >= 3)\n'),
     "new": '        return stem_of[index] is not None and len(stems[stem_of[index]]) >= 3\n',
     "expect": FOOTERS + ".test_generated_documents_and_ranges",
     "why": "a footer beside a repeated running head would stop being one"},
    {"id": "THE_STEM_IS_NOT_NORMALIZED", "file": ROUTE,
     "old": '        stem_of.append(None if found is None else _normalized(found[0]))\n',
     "new": '        stem_of.append(None if found is None else found[0])\n',
     "expect": FOOTERS + ".test_generated_documents_and_ranges",
     "why": "one footer printed in two cases would count as two stems"},
    {"id": "KEYED_BY_LENGTH", "file": BLOCK,
     "old": '        key = (hashlib.sha256(raw_bytes).hexdigest(), len(raw_bytes))\n',
     "new": '        key = len(raw_bytes)\n',
     "expect": ONCE + ".test_different_bytes_of_one_length_are_different_documents",
     "why": "another document of the same length would get this one's facts"},
    {"id": "A_BYTEARRAY_IS_PARSED", "file": BLOCK,
     "old": '        if type(raw_bytes) is not bytes:\n            return frozen(raw_bytes=raw_bytes)\n',
     "new": '        if type(raw_bytes) is not bytes:\n            raw_bytes = bytes(raw_bytes)\n',
     "expect": ONCE + ".test_what_the_parser_refuses_is_refused_as_before_and_not_kept",
     "why": "an argument the frozen parser refuses would be answered"},
    {"id": "NOTHING_IS_DROPPED", "file": BLOCK,
     "old": '            while len(held) > MAX_DOCUMENTS:\n                held.pop(next(iter(held)))\n',
     "new": '',
     "expect": ONCE + ".test_a_dropped_document_is_parsed_again_not_answered_differently",
     "why": "the block would hold every document it ever parsed"},
    {"id": "NOT_PUT_BACK_WHEN_THE_BLOCK_RAISES", "file": BLOCK,
     "old": '        yield\n    finally:\n',
     "new": '        yield\n    except BaseException:\n        raise\n    else:\n',
     "expect": BINDINGS + ".test_the_bindings_are_put_back_when_the_block_raises",
     "why": "a failing case would leave every later one on the remembered parser"},
    {"id": "A_MODULE_IMPORTED_INSIDE_KEEPS_THE_MEMO", "file": BLOCK,
     "old": ('        # A module first imported inside the block bound the remembered parser.\n'
             '        for namespace, attribute in _bindings(memo):\n'
             '            namespace[attribute] = current\n'),
     "new": '',
     "expect": BINDINGS + ".test_a_module_first_imported_inside_the_block_is_put_back",
     "why": "a module first imported inside the block would keep the memo after it"},
    {"id": "THE_ROUTER_IS_NOT_SWAPPED", "file": BLOCK,
     "old": "        if not isinstance(name, str) or not (name == PACKAGE or name.startswith(PACKAGE + \".\")):\n",
     "new": ("        if (not isinstance(name, str) or not (name == PACKAGE or name.startswith(PACKAGE + \".\"))\n"
             "                or name == deterministic_router.__name__):\n"),
     "expect": BINDINGS + ".test_every_binding_inside_and_none_outside",
     "why": "a module imported inside the block would take the frozen parser"},
    {"id": "ANOTHER_THREAD_SHARES_THE_BLOCK", "file": BLOCK,
     "old": ('        _need(current.thread == threading.get_ident(),\n'
             '              "HISTORICAL_XBRL_PARSE_BLOCK_OPEN_IN_ANOTHER_THREAD")\n'),
     "new": '',
     "expect": BINDINGS + ".test_a_block_open_in_another_thread_is_refused",
     "why": "a second thread would share one thread's memo"},
    {"id": "A_REPLACED_PARSER_IS_WRAPPED", "file": BLOCK,
     "old": ('    _need(getattr(current, "__module__", None) == deterministic_router.__name__,\n'
             '          "HISTORICAL_XBRL_PARSER_ALREADY_REPLACED")\n'),
     "new": '',
     "expect": BINDINGS + ".test_a_parser_someone_else_replaced_is_refused",
     "why": "a patched parser would be remembered as if it were the frozen one"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory."""
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def _reason(output, case):
    """The exception line of the named case's traceback: what actually failed."""
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
    for module in (PAGES, PARSE):
        control, seconds = _run(module)
        if control.returncode != 0:
            print("CONTROL_RUN_FAILED", module, (control.stdout + control.stderr)[-2500:])
            return 2
        print("control passed", module, seconds, "s", flush=True)
    results = []
    for injection in INJECTIONS:
        path = REPO / injection["file"]
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
            run, seconds = _run(injection["expect"].rsplit(".", 1)[0])
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
        results.append({"id": injection["id"], "file": injection["file"],
                        "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "expected_case_failure": _reason(output, expected),
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s",
              results[-1]["expected_case_failure"], flush=True)
    out = Path(__file__).with_name("injections.json")
    out.write_text(json.dumps({"injections": results,
                               "caught": sum(r["outcome"] == "CAUGHT" for r in results),
                               "total": len(results),
                               "calls": {"provider": 0, "paid": 0, "sec": 0}},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("caught", sum(r["outcome"] == "CAUGHT" for r in results), "of", len(results))
    return 0 if all(r["outcome"] == "CAUGHT" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
