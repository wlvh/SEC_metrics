#!/usr/bin/env python3
"""Fault injections for the model ledger's VM changes in the repository's own module.

The owner decided the model calls run in the executor's cloud container. The
repository side of that - the start that outlives the container, the reader a
host without gh uses, and forgiving the line breaks a web page adds to the
approval - lives in scripts/vnext/historical_model_calls.py, and carrying the
ledger to the branch and back in scripts/vnext/historical_model_export.py.
Each injection edits one of them in place, runs the class aimed at it,
restores it byte for byte in a
``finally`` and checks the restore; it counts as caught only when the run fails
AND the named case is among the failures. An edit that does not apply exactly
once, or does not compile, stops the script before anything runs. The sealed
offline verification of the call path (verify.py) re-runs the path's own cases
when it is next sealed; this records what the repository's cases catch now.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/model-egress/model_start_injections.py
"""
import hashlib
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
MODULE = "scripts/vnext/historical_model_calls.py"
EXPORT = "scripts/vnext/historical_model_export.py"
TRAVEL = "tests.vnext.test_historical_model_calls.TheModelLedgerTravelsToTheBranchAndBack"
START = "tests.vnext.test_historical_model_calls.TheModelLedgerStartsOnceAndOnlyItsOwnMarkerCounts"
REGISTER = "tests.vnext.test_historical_model_calls.TheApprovalIsRegisteredFromWhatWasPosted"

INJECTIONS = [
    {"id": "THE_MODEL_LIVE_PATH_SKIPS_THE_START",
     "old": "    require_published_model_start(allowance=allowance, reader=reader)\n",
     "new": "",
     "class": START,
     "expect": "test_the_live_ledger_reads_the_host_s_reader_and_checks_the_start_last",
     "why": "without it a new container with an empty model ledger spends the allowance again"},
    {"id": "THE_MODEL_LIVE_PATH_READS_ONLY_WITH_GH",
     "old": "    reader = live_github_reader()\n",
     "new": "    from .historical_source_acquisition import github_comment_reader as reader\n",
     "class": START,
     "expect": "test_the_live_ledger_reads_the_host_s_reader_and_checks_the_start_last",
     "why": "the container has no gh; the live path must read GitHub the way the host can"},
    {"id": "THE_MODEL_START_IS_THE_SEC_START",
     "old": '    return LedgerKind(record_type="ISSUE_47_MODEL_LEDGER_START", prefix="ISSUE_47_MODEL_LEDGER",\n',
     "new": '    return LedgerKind(record_type="ISSUE_47_SEC_LEDGER_START", prefix="ISSUE_47_MODEL_LEDGER",\n',
     "class": START,
     "expect": "test_an_sec_marker_neither_starts_nor_blocks_the_model_ledger",
     "why": "an SEC marker for the same approval digest would stand in for the model ledger's start"},
    {"id": "THE_MODEL_EXPORT_IS_THE_SEC_EXPORT",
     "old": 'MODEL_EXPORT_DIRECTORY = "evidence/issue47_model_calls"\n',
     "new": 'MODEL_EXPORT_DIRECTORY = "evidence/issue47_acquired"\n',
     "class": START,
     "expect": "test_only_the_model_export_blocks_a_model_start",
     "why": "one ledger's export would block the other ledger's start"},
    {"id": "MODEL_REGISTRATION_COMPARES_THE_RAW_BODY",
     "old": '    _need(posted_text(fetched["body"]).encode("utf-8") == proposed,\n',
     "new": '    _need(fetched["body"].encode("utf-8") == proposed,\n',
     "class": REGISTER,
     "expect": "test_a_proposal_pasted_into_the_web_page_registers",
     "why": "an approval pasted into github.com may come back with CRLF line breaks"},
    {"id": "MODEL_ALLOWANCE_HASHES_THE_RAW_BODY",
     "old": '          and sha256_bytes(content=posted_text(comment["body"]).encode("utf-8"))\n',
     "new": '          and sha256_bytes(content=comment["body"].encode("utf-8"))\n',
     "class": REGISTER,
     "expect": "test_a_proposal_pasted_into_the_web_page_registers",
     "why": "registration would accept a pasted approval the gate then refuses"},
    {"id": "VERIFY_TRUSTS_THE_INDEX", "file": EXPORT,
     "old": '    _need([state["counts"], state["stopped"], state["requests"]]\n'
            '          == [index["counts"], index["stopped"], index["requests"]],\n',
     "new": '    _need(True,\n',
     "class": TRAVEL,
     "expect": "test_an_index_resealed_with_other_counts_is_refused",
     "why": "an index sealed by whoever wrote the archive would say how much was spent"},
    {"id": "VERIFY_SKIPS_THE_LEDGER_S_OWN_SNAPSHOT", "file": EXPORT,
     "old": "        state = ledger.snapshot()\n",
     "new": '        state = {"counts": index["counts"], "stopped": index["stopped"],\n'
            '                 "requests": index["requests"]}\n',
     "class": TRAVEL,
     "expect": "test_a_resealed_archive_of_a_truncated_ledger_is_refused_by_the_ledger",
     "why": "hashes that agree with each other are not a ledger"},
    {"id": "A_RECORDED_LEDGER_IS_RESTORED", "file": EXPORT,
     "old": '    _need(index["execution_mode"] == "LIVE", "ISSUE_47_MODEL_RESTORE_ONLY_A_LIVE_LEDGER")\n',
     "new": "",
     "class": TRAVEL,
     "expect": "test_only_a_live_ledger_is_restored",
     "why": "only the granted ledger's record belongs at the granted root"},
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


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def main():
    for injection in INJECTIONS:
        text = (REPO / injection.get("file", MODULE)).read_text(encoding="utf-8")
        found = text.count(injection["old"])
        if found != 1:
            print("INJECTION_DID_NOT_APPLY", injection["id"], found)
            return 2
        try:
            compile(text.replace(injection["old"], injection["new"]),
                    injection.get("file", MODULE), "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
    results = []
    for injection in INJECTIONS:
        path = REPO / injection.get("file", MODULE)
        original = path.read_bytes()
        try:
            path.write_text(original.decode("utf-8").replace(injection["old"], injection["new"]),
                            encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", injection["class"]], cwd=REPO, env=_isolated_env(),
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
        results.append({"id": injection["id"], "file": injection.get("file", MODULE),
                        "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary)})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    out = Path(__file__).with_name("model-start-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_MODEL_LEDGER_VM_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
