#!/usr/bin/env python3
"""Fault injections for D01's bound revision: each must be caught by the case written for it.

D01's pinned route compiles ``catalog/r6/D01_risk_factor_headings_v2.md``, which
``historical_spec_revision`` proves is the ordinary Spec with only
``max_items`` raised. Each injection undoes one part of that; the case named
for it must fail. An edit that does not apply exactly once or does not compile
stops the script, the file is restored byte for byte and checked, and every
run reads and writes bytecode only in a fresh directory. The control run must
pass first.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/d01-item-bound/injections.py
"""
import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CASE = ("tests.vnext.test_historical_risk_headings.PinnedRiskHeadingsTest."
        "test_the_pinned_route_s_spec_is_the_ordinary_one_with_only_the_bound_raised")
INJECTIONS = [
    {"id": "D01_KEEPS_THE_FROZEN_SPEC", "file": "scripts/vnext/historical_results.py",
     "old": '                   "D01": "catalog/r6/D01_risk_factor_headings_v2.md",\n',
     "new": '                   "D01": "catalog/r6/D01_risk_factor_headings.md",\n',
     "expect": CASE,
     "edit": "the pinned route compiles the ordinary D01 Spec",
     "why": "a year whose Item 1A has more than 64 emphasized headings has no D01 result"},
    {"id": "THE_REVISION_IS_NOT_REGISTERED", "file": "scripts/vnext/historical_spec_revision.py",
     "old": ('    "catalog/r6/D01_risk_factor_headings_v2.md": '
             '"catalog/r6/D01_risk_factor_headings.md",\n'),
     "new": "",
     "expect": CASE,
     "edit": "historical_spec_revision does not name D01's successor",
     "why": "the successor would take the frozen compiler's path, which refuses its bound, "
            "and the text protocol would not render more than 64 headings"},
    {"id": "THE_SUCCESSOR_MOVES_ANOTHER_FIELD", "file": "catalog/r6/D01_risk_factor_headings_v2.md",
     "old": '    "max_text_chars": 64000,\n',
     "new": '    "max_text_chars": 32000,\n',
     "expect": CASE,
     "edit": "D01's successor also halves the character bound",
     "why": "a revision that changes more than the bound is a different Spec, not this one",
     "text": True},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory."""
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def _run(selector):
    started = time.time()
    run = subprocess.run([sys.executable, "-m", "unittest", selector], cwd=REPO,
                         env=_isolated_env(), capture_output=True, text=True, timeout=3600)
    return run, int(time.time() - started)


def main():
    control, seconds = _run(CASE)
    if control.returncode != 0:
        print("CONTROL_RUN_FAILED", control.stderr[-1500:])
        return 2
    print("control passed in", seconds, "s", flush=True)
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
        if not injection.get("text"):
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
        results.append({"id": injection["id"], "file": injection["file"],
                        "edit": injection["edit"], "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s", flush=True)
    out = Path(__file__).with_name("injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_D01_BOUND_REVISION_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
