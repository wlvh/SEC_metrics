#!/usr/bin/env python3
"""Fault injections for the US GAAP release widening: each must be caught by the case written for it.

Each injection undoes one part of the change - the view's table entry, the
pattern it widens to, one of the two frozen spellings, or one of the four call
sites that now go through a view - and the case named for it must fail. An
edit that does not apply exactly once or does not compile stops the script,
the file is restored byte for byte and checked, and every run reads and writes
bytecode only in a fresh directory. The control run must pass first. Run it in
a worktree or clone: it edits the files in place while it runs.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/us-gaap-release/injections.py
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
MODULE = "tests.vnext.test_historical_dei"
RELEASE = MODULE + ".AUsGaapReleaseIsRead"
COMPLETE = MODULE + ".EveryHistoricalReferenceGoesThroughAView"
DEI = "scripts/vnext/historical_dei.py"
INJECTIONS = [
    {"id": "US_GAAP_IS_NOT_IN_THE_VIEW",
     "file": DEI,
     "old": "            **{p: US_GAAP_NAMESPACE_PATTERN for p in FROZEN_US_GAAP_NAMESPACE_PATTERNS}}\n",
     "new": "            }\n",
     "expect": RELEASE + ".test_a_fy2021_report_s_equity_is_read_through_the_view",
     "edit": "the view's table carries no US GAAP entry",
     "why": "every FY2021 B06 stops at B06_GUARD_EQUITY_NAMESPACE_CONFLICT again"},
    {"id": "ANY_SUFFIX_IS_A_US_GAAP_RELEASE",
     "file": DEI,
     "old": "US_GAAP_NAMESPACE_PATTERN = r\"https?://fasb\\.org/us-gaap/[0-9]{4}(?:-\\d{2}-\\d{2})?\"\n",
     "new": "US_GAAP_NAMESPACE_PATTERN = r\"https?://fasb\\.org/us-gaap/[0-9]{4}.*\"\n",
     "expect": RELEASE + ".test_anything_else_is_refused",
     "edit": "the widened pattern accepts any text after the year",
     "why": "a quarter form or a malformed date would read as a US GAAP release"},
    {"id": "ONE_FROZEN_SPELLING_IS_LEFT_OUT",
     "file": DEI,
     "old": "FROZEN_US_GAAP_NAMESPACE_PATTERNS = (r\"https?://fasb\\.org/us-gaap/[0-9]{4}\",\n                                     r\"https?://fasb\\.org/us-gaap/\\d{4}\")\n",
     "new": "FROZEN_US_GAAP_NAMESPACE_PATTERNS = (r\"https?://fasb\\.org/us-gaap/[0-9]{4}\",)\n",
     "expect": RELEASE + ".test_the_frozen_readers_spell_the_pattern_these_ways",
     "edit": "the \\d{4} spelling of the capacity and text readers is not widened",
     "why": "the D04 request reconstruction and D02/D03 fact candidates would keep the frozen answer"},
    {"id": "THE_CONTRACT_AMORTIZATION_CHECK_IS_NOT_VIEWED",
     "file": "scripts/vnext/historical_zero_ai_results.py",
     "old": "_UNRECONCILED_CONTRACT_AMORTIZATION = release_aware(\n    _contract_scope._unreconciled_contract_amortization)\n",
     "new": "_UNRECONCILED_CONTRACT_AMORTIZATION = _contract_scope._unreconciled_contract_amortization\n",
     "expect": COMPLETE + ".test_no_historical_function_reaches_the_question_without_a_view",
     "edit": "B03's contract-amortization check is called directly",
     "why": "a FY2021 report's contract amortization would not be seen as US GAAP"},
    {"id": "THE_REQUEST_RECONSTRUCTION_IS_NOT_VIEWED",
     "file": "scripts/vnext/historical_semantic_results.py",
     "old": "_RECONSTRUCT_REQUESTS = release_aware(reconstruct_requests)\n",
     "new": "_RECONSTRUCT_REQUESTS = reconstruct_requests\n",
     "expect": COMPLETE + ".test_no_historical_function_reaches_the_question_without_a_view",
     "edit": "D04's request reconstruction is called directly",
     "why": "a FY2021 report's monetary facts would not be seen as US GAAP in the requests"},
    {"id": "THE_CAPACITY_SOURCE_IS_NOT_VIEWED",
     "file": "scripts/vnext/historical_semantic_source.py",
     "old": "_CAPACITY_SOURCE_FROM_COMPLETE_ANNUAL = release_aware(\n    frozen_capacity.capacity_source_from_complete_annual)\n",
     "new": "_CAPACITY_SOURCE_FROM_COMPLETE_ANNUAL = frozen_capacity.capacity_source_from_complete_annual\n",
     "expect": COMPLETE + ".test_no_historical_function_reaches_the_question_without_a_view",
     "edit": "B13's capacity source is built directly",
     "why": "a FY2021 report's monetary capacity facts would not be seen as US GAAP"},
    {"id": "THE_DEFINED_ABSENCE_ROW_IS_NOT_VIEWED",
     "file": "scripts/vnext/historical_projection.py",
     "old": "        row, evidence = release_aware(capacity_run).project_defined_absence(\n",
     "new": "        row, evidence = capacity_run.project_defined_absence(\n",
     "expect": COMPLETE + ".test_no_historical_function_reaches_the_question_without_a_view",
     "edit": "the D04 defined-absence row re-derives its candidate directly",
     "why": "a FY2021 D04 row would re-derive a different candidate from the one its Run holds"},
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
        results.append({"id": injection["id"], "file": injection["file"], "edit": injection["edit"],
                        "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "expected_case_failure": _reason(output, expected),
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s",
              results[-1]["expected_case_failure"], flush=True)
    out = Path(__file__).with_name("injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_US_GAAP_RELEASE_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
