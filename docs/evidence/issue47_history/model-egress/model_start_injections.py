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
    # Retargeted after the model exports moved into one directory per approval:
    # pointing the model directory at the SEC one no longer collides, so this
    # points the model start at the SEC index instead.
    {"id": "THE_MODEL_START_READS_THE_SEC_EXPORT",
     "old": ('                      export_index=lambda allowance: (model_export_directory(allowance) + "/"\n'
             '                                                      + MODEL_EXPORT_INDEX),\n'),
     "new": '                      export_index=lambda allowance: "evidence/issue47_acquired/export.json",\n',
     "class": START,
     "expect": "test_only_the_model_export_blocks_a_model_start",
     "why": "one ledger's export would block the other ledger's start, and its own would not"},
    # The VM-delta review (independent-review-2026-09-29-vm/).
    {"id": "THE_MARKER_CARRIES_THE_WHOLE_RECORD", "file": "scripts/vnext/historical_ledger_start.py",
     "old": '            + json.dumps(marker_view(record), indent=1, sort_keys=True) + "\\n```\\n")',
     "new": '            + json.dumps(record, indent=1, sort_keys=True) + "\\n```\\n")',
     "also": [('    _need(kind, first["record"] == marker_view(record),\n',
               '    _need(kind, first["record"] == record,\n')],
     "class": START,
     "expect": "test_the_marker_does_not_carry_what_the_local_record_needs",
     "why": "a marker that carries the record can be copied back beside an empty root and be the start (F2)"},
    {"id": "A_LEDGER_MAY_BE_BEHIND_ITS_EXPORT", "file": "scripts/vnext/historical_ledger_start.py",
     "old": "    require_not_behind_export(kind, allowance=allowance, checkout=checkout)\n",
     "new": "",
     "class": START,
     "expect": "test_a_ledger_behind_its_export_is_refused",
     "why": "a host that lost or reset its ledger would count from less than was spent (F2)"},
    {"id": "A_MARKER_FROM_ANYWHERE_COUNTS", "file": "scripts/vnext/historical_ledger_start.py",
     "old": ('                    and comment.get("issue_url") == issue_api and type(user) is dict\n'
             '                    and user.get("id") == kind.owner_id and user.get("type") == "User"\n'),
     "new": "",
     "class": START,
     "expect": "test_a_marker_not_from_this_issue_or_account_does_not_count",
     "why": "a comment from another issue or account would stand in for the start (F9)"},
    {"id": "A_RE_APPROVAL_REDRAWS_CLAIMED_REQUESTS",
     "old": '    _need(not again, "ISSUE_47_MODEL_LEDGER_GRANTS_REQUESTS_ANOTHER_APPROVAL_CLAIMED:"\n',
     "new": '    _need(True, "ISSUE_47_MODEL_LEDGER_GRANTS_REQUESTS_ANOTHER_APPROVAL_CLAIMED:"\n',
     "class": START,
     "expect": "test_a_re_approval_cannot_start_over_requests_another_approval_claimed",
     "why": "a re-approval would send again the requests an earlier approval already paid for (F5)"},
    {"id": "ALL_APPROVALS_SHARE_ONE_EXPORT",
     "old": '    return MODEL_EXPORT_DIRECTORY + "/" + digest[:16]\n',
     "new": "    return MODEL_EXPORT_DIRECTORY\n",
     "class": START,
     "expect": "test_each_approval_exports_into_its_own_directory",
     "why": "a second approval's export would overwrite the first one's record (F5)"},
    {"id": "AN_EXPORT_BEGINS_A_LEDGER", "file": EXPORT,
     "old": '    _need(_started(ledger), "ISSUE_47_MODEL_EXPORT_OF_A_LEDGER_NEVER_STARTED_HERE:" + str(ledger.root))\n',
     "new": "",
     "class": TRAVEL,
     "expect": "test_an_export_of_a_ledger_never_started_here_is_refused",
     "why": "exporting on a host whose ledger is gone would begin an empty one and record nothing (F3)"},
    {"id": "AN_EXPORT_MAY_GO_BACKWARDS", "file": EXPORT,
     "old": '        _need(same and type(old_log) is dict and type(old_log.get("size")) is int\n',
     "new": '        _need(True or same and type(old_log) is dict and type(old_log.get("size")) is int\n',
     "class": TRAVEL,
     "expect": "test_an_export_only_moves_forward",
     "why": "a shorter ledger's export would be written over the record of what was spent (F3)"},
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
     "old": "        # the snapshot is what checks the slots, the claim log and its copy.\n"
            "        state = ledger.snapshot()\n",
     "new": "        # the snapshot is what checks the slots, the claim log and its copy.\n"
            '        state = {"counts": index["counts"], "stopped": index["stopped"],\n'
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
        for old, new in [(injection["old"], injection["new"])] + injection.get("also", []):
            found = text.count(old)
            if found != 1:
                print("INJECTION_DID_NOT_APPLY", injection["id"], found)
                return 2
            text = text.replace(old, new)
        try:
            compile(text, injection.get("file", MODULE), "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
    results = []
    for injection in INJECTIONS:
        path = REPO / injection.get("file", MODULE)
        original = path.read_bytes()
        edited = original.decode("utf-8")
        for old, new in [(injection["old"], injection["new"])] + injection.get("also", []):
            edited = edited.replace(old, new)
        try:
            path.write_text(edited, encoding="utf-8")
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
