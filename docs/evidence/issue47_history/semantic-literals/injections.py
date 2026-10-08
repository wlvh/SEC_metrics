#!/usr/bin/env python3
"""Fault injections for the guards added when #47's family-owned phrases left its code.

Each injection edits one file in place, runs the named case, restores the file
byte for byte in a ``finally`` and checks the restore. It counts as caught only
when the run fails and the named case is among the failures. An edit that does
not apply exactly once, or does not compile, stops the script before anything
runs. Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/semantic-literals/injections.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path
import atexit
import os
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[4]
READER = "scripts/vnext/historical_board_composition.py"
LITERALS = "tests.vnext.test_historical_business_literals.Issue47SpellsNoFamilyOwnedPhrase"
CATALOG = "tests.vnext.test_historical_board_composition.TheLeadRoleIsReadFromTheCatalog"
INJECTIONS = [
    {"id": "THE_PHRASE_COMES_BACK_INTO_THE_CODE", "file": READER,
     "old": '_DESIGNATION_WORDS = frozenset("""director directors independent nominee',
     "new": '_DESIGNATION_WORDS = frozenset("""independent director directors nominee',
     "class": LITERALS, "expect": "test_no_file_spells_a_family_owned_phrase",
     "why": "the set is the same, and the source spells the phrase the audit forbids again"},
    {"id": "ANY_CATALOG_PHRASE_IS_COMPILED", "file": READER,
     "old": '            or type(role) is not str or not re.fullmatch(r"[a-z]+(?: [a-z]+)*", role)):\n',
     "new": '            or type(role) is not str):\n',
     "class": CATALOG, "expect": "test_terms_that_could_reshape_a_pattern_are_refused",
     "why": "the phrase goes into four patterns unescaped; a group or an alternation reshapes them"},
    {"id": "A_PATTERN_STOPS_READING_THE_CATALOG", "file": READER,
     "old": '    r"|vice[- ]chair(?:man|person|woman)?|" + _LEAD_ROLE + r")',
     "new": '    r"|vice[- ]chair(?:man|person|woman)?|lead director" + r")',
     "class": CATALOG, "expect": "test_the_four_patterns_carry_the_catalog_s_phrase",
     "why": "a pattern that no longer carries the catalog's phrase is no longer bound by it"},
    {"id": "THE_FILE_SET_COMES_BACK_EMPTY", "file": "tests/vnext/test_historical_business_literals.py",
     "old": "    return sorted(path for path in named\n",
     "new": "    return sorted(path for path in named if False\n",
     "class": LITERALS, "expect": "test_the_files_are_found_before_they_are_judged",
     "why": "an empty set passes the audit case by finding nothing"},
]


def _isolated_env():
    """The environment for one injected run: bytecode read and written only in a fresh directory.

    Restoring a file's bytes does not restore what runs. The interpreter trusts
    a cached compile whose recorded source size and whole-second modification
    time match the file, so an edit of the same size, restored within the same
    second, leaves the injected bytecode in the checkout's __pycache__ to run
    in place of the restored source. Measured 2026-09-29: a restored C02
    reader ran an injection's pattern in the next ordinary test run. No
    injected run here reads or writes the checkout's __pycache__.
    """
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def main():
    for item in INJECTIONS:
        text = (REPO / item["file"]).read_text(encoding="utf-8")
        if text.count(item["old"]) != 1:
            print("INJECTION_DID_NOT_APPLY", item["id"], text.count(item["old"]))
            return 2
        compile(text.replace(item["old"], item["new"]), item["file"], "exec")
    results = []
    for item in INJECTIONS:
        path = REPO / item["file"]
        original = path.read_bytes()
        try:
            path.write_text(original.decode("utf-8").replace(item["old"], item["new"]), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", item["class"]], cwd=REPO, env=_isolated_env(),
                                 capture_output=True, text=True, timeout=600)
        finally:
            path.write_bytes(original)
        if path.read_bytes() != original:
            print("RESTORE_FAILED", item["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M)))
        caught = run.returncode != 0 and item["expect"] in failed
        results.append({"id": item["id"], "file": item["file"], "why_it_matters": item["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT", "expected_case": item["expect"],
                        "failed_cases": failed})
        print(item["id"], results[-1]["outcome"], failed, flush=True)
    Path(__file__).with_name("injections.json").write_text(
        json.dumps({"record_type": "ISSUE_47_SEMANTIC_LITERAL_GUARD_INJECTIONS", "results": results,
                    "calls": [0, 0, 0]}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
