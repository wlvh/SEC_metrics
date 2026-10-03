#!/usr/bin/env python3
"""Fault injections for resuming a lost SEC ledger: each must be caught by the case written for it.

The container that held the ledger was restored from an older snapshot while an
acquisition was running (2026-09-29). ``historical_sec_resume`` rebuilds the
ledger from the branch's export and charges what the lost host may have spent;
each injection below undoes one part of that, and the case named for it must
fail. Same rules as ``rule_input_injections.py``: an edit that does not apply
exactly once or does not compile stops the script, the file is restored byte
for byte and checked, and every run reads and writes bytecode only in a fresh
directory. The control run must pass first.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/acquisition-wiring/resume_injections.py
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
CLASS = "tests.vnext.test_historical_sec_session.ALostHostResumesFromTheExportAndPaysForWhatItMayHaveSpent"
SESSION = "scripts/vnext/historical_sec_session.py"
RESUME = "scripts/vnext/historical_sec_resume.py"
EXPORT = "scripts/vnext/historical_source_export.py"
MAIN = "test_a_lost_host_resumes_the_exported_ledger_and_its_count_carries_the_reserve"
PINNED = "test_the_resume_charge_cannot_shrink_while_a_session_holds_the_ledger"
FIRST_HOST = "test_a_host_that_still_holds_its_start_may_not_spend_after_a_resume"
BRANCH = "test_a_resume_is_from_the_export_the_branch_carries_now"
GIT = "tests.vnext.test_historical_sec_session.TheResumeIsHandedTheBranchTipThroughGit"
RUNNING = "test_a_running_session_stops_when_a_resume_is_published_elsewhere"
GUARDS = "test_the_resume_guards_the_review_found_untested"
LEFT_OVER = "test_a_resume_already_running_or_left_over_is_not_disturbed"
START = "tests.vnext.test_historical_sec_session.AStartMustBePublishedBeforeAnyRequest"
TOOL = "tools/vnext_historical_sec.py"
INJECTIONS = [
    {"id": "THE_RESERVE_IS_NOT_COUNTED", "file": SESSION,
     "old": "        counts[2] += reserve\n", "new": "        counts[2] += 0\n", "expect": MAIN,
     "edit": "HistoricalCallLedger.snapshot() leaves the resume's reserve out of the count",
     "why": "the cap would bound only what the restored slots recorded, not what the lost "
            "host may have sent"},
    {"id": "A_RESUME_NEEDS_NO_MARKER", "file": RESUME,
     "old": ("    _need(len(shown) >= len(views), \"RESUME_NOT_PUBLISHED:post the resume marker on issue \"\n"
             "          + str(kind.issue_number))\n"
             "    _need(shown == views, \"RESUMED_ELSEWHERE:the issue's resume markers are not this \"\n"
             "          \"host's chain\")\n"),
     "new": "", "expect": MAIN,
     "edit": "require_published_resume() accepts a local chain the issue does not show",
     "why": "a resume nobody can see on the issue would be a second, unaudited spending of "
            "the same approval"},
    {"id": "A_CHEAPER_CHAIN_PASSES", "file": RESUME,
     "old": "    _need(shown == views, \"RESUMED_ELSEWHERE",
     "new": "    _need(len(shown) == len(views), \"RESUMED_ELSEWHERE", "expect": MAIN,
     "edit": "require_published_resume() compares how many resumes, not what they say",
     "why": "a chain whose reserve was lowered locally would pass beside the true marker"},
    {"id": "THE_EXPORT_DROPS_THE_CHAIN", "file": EXPORT,
     "old": "    if resume_chain_path(ledger_root).exists() or resume_chain_path(ledger_root).is_symlink():\n",
     "new": "    if False:\n", "expect": MAIN,
     "edit": "export_acquisition() leaves the resume chain out of the export",
     "why": "a later restore would count from the slots alone and forget the lost segment"},
    {"id": "AN_EXPORT_MAY_DROP_A_RESUME", "file": EXPORT,
     "old": ("    _need(old_chain is None or (type(old_chain) is dict and type(old_chain.get(\"size\")) is int\n"
             "                                and len(chain) >= old_chain[\"size\"]\n"
             "                                and sha256_bytes(content=chain[:old_chain[\"size\"]])\n"
             "                                == old_chain.get(\"sha256\")),\n"
             "          \"ISSUE_47_EXPORT_WOULD_DROP_A_RESUME:\" + str(previous))"),
     "new": "    pass", "expect": MAIN,
     "edit": "_only_forward() lets an export without the chain replace one that carries it",
     "why": "the branch would stop recording the charge for a lost segment"},
    {"id": "THE_NONCE_IS_EXPORTED", "file": EXPORT,
     "old": ("            canonical_json_bytes(value=resume_view(record) if \"instance_nonce\" in record\n"
             "                                 else record).rstrip(b\"\\n\") + b\"\\n\"\n"),
     "new": "            canonical_json_bytes(value=record).rstrip(b\"\\n\") + b\"\\n\"\n",
     "expect": MAIN,
     "edit": "export_acquisition() exports the resume record with its random number",
     "why": "anyone reading the public branch could write a matching chain beside an empty root"},
    {"id": "A_RESUME_SINCE_THE_EXPORT_IS_IGNORED", "file": RESUME,
     "old": ("    _need([item[\"record\"] for item in published] == exported_chain,\n"
             "          \"RESUMED_SINCE_THE_EXPORT"),
     "new": ("    _need(True,\n"
             "          \"RESUMED_SINCE_THE_EXPORT"), "expect": MAIN,
     "edit": "resume_ledger() ignores resume markers the export does not carry",
     "why": "what a resumed-then-lost host spent after its resume would be charged nowhere"},
    {"id": "THE_RESERVE_COUNTS_NOTHING", "file": RESUME,
     "old": "            admitted.append(row)\n", "new": "            pass\n",
     "expect": "test_the_reserve_is_the_due_rows_and_refuses_where_a_capture_could_open_more",
     "edit": "lost_segment_reserve() charges nothing for the due rows",
     "why": "the resume would count from the export as if the lost host had sent nothing"},
    {"id": "AN_OPENING_ROW_IS_TREATED_AS_BOUNDED", "file": RESUME,
     "old": ("        _need(not opening, \"RESUME_RESERVE_UNBOUNDED:\""),
     "new": ("        _need(True, \"RESUME_RESERVE_UNBOUNDED:\""),
     "expect": "test_the_reserve_is_the_due_rows_and_refuses_where_a_capture_could_open_more",
     "edit": "lost_segment_reserve() counts rows whose capture can declare more rows",
     "why": "a later pass could have claimed rows the reserve does not see"},
    {"id": "A_RESUME_OVER_A_KEPT_START", "file": RESUME,
     "old": ("    _need(not start_path.exists() and not start_path.is_symlink(),\n"
             "          \"RESUME_BESIDE_A_START_RECORD:this host kept its start; it did not lose its ledger\")\n"),
     "new": "", "expect": "test_a_host_that_kept_its_start_or_its_root_does_not_resume",
     "edit": "resume_ledger() rebuilds a ledger beside a start record the host kept",
     "why": "a host that did not lose its ledger could reset it to an older export"},
    {"id": "ANOTHER_APPROVAL_S_EXPORT_IS_RESUMED", "file": RESUME,
     "old": ("    _need(index.get(\"execution_mode\") == \"LIVE\"\n"
             "          and index.get(\"approval\") == _expected_approval(allowance),\n"),
     "new": ("    _need(index.get(\"execution_mode\") == \"LIVE\",\n"),
     "expect": "test_a_resume_needs_this_approval_s_export",
     "edit": "resume_ledger() rebuilds from an export whose approval block differs",
     "why": "another approval's ledger would be counted against this one"},
    {"id": "AN_EDITED_START_MARKER_IS_ACCEPTED", "file": RESUME,
     "old": ("    _need(_unedited(markers[0][\"comment\"]),\n"
             "          \"START_MARKER_EDITED:\" + str(markers[0][\"comment\"].get(\"html_url\")))\n"
             "    start_sha = markers[0][\"record\"].get(\"start_record_sha256\")\n"
             "    _need(type(start_sha) is str and bool(start_sha), \"RESUME_START_MARKER_HAS_NO_DIGEST\")\n"),
     "new": ("    start_sha = markers[0][\"record\"].get(\"start_record_sha256\")\n"
             "    _need(type(start_sha) is str and bool(start_sha), \"RESUME_START_MARKER_HAS_NO_DIGEST\")\n"),
     "expect": "test_a_resume_needs_the_approval_s_earliest_start_marker_unedited",
     "edit": "resume_ledger() resumes from an edited start marker",
     "why": "an edited marker is no longer the start that was published"},
    # What the independent review of 2026-09-29 found, each fix undone.
    {"id": "A_SNAPSHOT_DOES_NOT_HOLD_THE_PINNED_CHARGE", "file": SESSION,
     "old": ("        _need(self._pinned_reserve is None or reserve == self._pinned_reserve,\n"),
     "new": ("        _need(True or reserve == self._pinned_reserve,\n"), "expect": PINNED,
     "edit": "HistoricalCallLedger.snapshot() reads the chain afresh and ignores the pinned charge",
     "why": "a chain deleted mid-session lowered the count and captures ran past the cap"},
    {"id": "THE_LIVE_LEDGER_IS_NOT_PINNED", "file": SESSION,
     "old": "    ledger.pin_resume_reserve(published[\"reserve_sec_calls\"])\n",
     "new": "", "expect": PINNED,
     "edit": "live_ledger() builds the ledger without holding it to the verified charge",
     "why": "the snapshot check would have nothing to compare with"},
    {"id": "A_LIVE_LEDGER_WITHOUT_A_BEGINNING_IS_EXPORTED", "file": EXPORT,
     "old": ("    _need(mode != \"LIVE\" or any(path.is_file() and not path.is_symlink() for path in\n"),
     "new": ("    _need(True or any(path.is_file() and not path.is_symlink() for path in\n"),
     "expect": MAIN,
     "edit": "export_acquisition() exports a LIVE ledger with neither a start nor a resume beside it",
     "why": "an export after the chain was deleted would leave the lost segment's charge out"},
    {"id": "THE_FIRST_HOST_IS_NOT_FENCED", "file": SESSION,
     "old": "    _need(not resumed, \"ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE:\"\n",
     "new": "    _need(True, \"ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE:\"\n", "expect": FIRST_HOST,
     "edit": "require_published_start() lets a host holding its start spend after a published resume",
     "why": "a host that was only unreachable would spend the same allowance a second time"},
    {"id": "THE_RESUME_TRUSTS_THE_CHECKOUT", "file": RESUME,
     "old": ("    _need(type(branch_export_index) is bytes\n"
             "          and (export_dir / INDEX_NAME).read_bytes() == branch_export_index\n"
             "          and type(branch_tip_commit) is str and len(branch_tip_commit) == 40,\n"),
     "new": ("    _need(True,\n"), "expect": BRANCH,
     "edit": "resume_ledger() restores whatever export the checkout holds",
     "why": "a checkout the loss took back would restore an older export and charge from it"},
    {"id": "THE_TIP_IS_NOT_FETCHED", "file": TOOL, "class": GIT,
     "old": "    git(\"fetch\", remote, branch)\n", "new": "",
     "expect": "test_a_checkout_behind_the_branch_is_handed_the_branch_s_newer_export",
     "edit": "the resume command reads the upstream ref without fetching it",
     "why": "the stale checkout's own remote ref is the export the loss took it back to"},
    {"id": "A_RUNNING_SESSION_IS_NOT_RECHECKED", "file": SESSION,
     "old": ("            refused = self._published_still()\n"
             "            if refused is not None:\n"),
     "new": ("            refused = None\n"
             "            if refused is not None:\n"), "expect": RUNNING,
     "edit": "capture_pending() plans a pass without running the live path's check again",
     "why": "a session already running would keep claiming after a resume elsewhere"},
    {"id": "THE_LIVE_SESSION_KEEPS_NO_CHECK", "file": SESSION,
     "old": "    session.published_check = published\n", "new": "", "class": START,
     "expect": "test_the_live_path_checks_the_start_before_any_transport",
     "edit": "live_historical_session() builds a session with no check to run per pass",
     "why": "the per-pass check would be skipped in production while every test of it passed"},
    {"id": "THE_LIVE_PATH_TRUSTS_THE_CHECKOUT", "file": SESSION,
     "old": ("    _need((local.read_bytes() if local.is_file() and not local.is_symlink() else None)\n"
             "          == branch_export_index,\n"),
     "new": ("    _need(True,\n"), "expect": MAIN,
     "edit": "require_published_start() compares the ledger with the checkout's export only",
     "why": "a snapshot that took the ledger and the checkout back together would pass"},
    {"id": "A_RESUME_IS_CLAIMED_BEFORE_IT_IS_EXPORTED", "file": RESUME,
     "old": ("    _need(exported is not None and _prefix(own, exported) and exported[\"size\"] == len(own),\n"),
     "new": ("    _need(True,\n"), "expect": MAIN,
     "edit": "require_published_resume() lets a session claim before the branch carries the resume",
     "why": "a second loss before that export would find the resume only on the issue"},
    {"id": "A_QUOTED_MARKER_IS_ANOTHER_RESUME", "file": RESUME,
     "old": ("        if not str(item[\"comment\"].get(\"body\") or \"\").startswith(MARKER_TITLE):\n"
             "            continue\n"),
     "new": "", "expect": GUARDS,
     "edit": "resume_markers() counts any owner comment carrying a resume record",
     "why": "a status comment quoting the marker would stop every live start"},
    {"id": "A_DUPLICATE_MARKER_IS_ANOTHER_RESUME", "file": RESUME,
     "old": ("        if digest in seen:\n"
             "            continue\n"),
     "new": "", "expect": GUARDS,
     "edit": "resume_markers() counts the same record posted twice as two resumes",
     "why": "a retried POST GitHub had accepted would stop every live start"},
    {"id": "A_RESUME_IN_PROGRESS_IS_DISTURBED", "file": RESUME,
     "old": "        _need(False, \"RESUME_IN_PROGRESS_OR_LEFT_OVER:\"",
     "new": "        _need(True, \"RESUME_IN_PROGRESS_OR_LEFT_OVER:\"", "expect": LEFT_OVER,
     "edit": "resume_ledger() goes on beside another resume's sentinel",
     "why": "a refused resume would delete the staging directory of the one in progress"},
    {"id": "THE_PREFIX_IS_ALWAYS_TRUE", "file": RESUME,
     "old": "def _prefix(data, binding):\n    return (",
     "new": "def _prefix(data, binding):\n    return True or (", "expect": GUARDS,
     "edit": "_prefix() accepts any bytes (the review's mutation)",
     "why": "a ledger that is not what was restored would pass the live path"},
    {"id": "THE_LINKS_ARE_NOT_CHECKED", "file": RESUME,
     "old": "def _check_links(views, *, start_sha):\n",
     "new": "def _check_links(views, *, start_sha):\n    return None\n", "expect": GUARDS,
     "edit": "_check_links() checks nothing (the review's mutation)",
     "why": "a chain resuming another start, or with a broken link, would pass"},
    {"id": "A_HEAD_BEHIND_THE_TIP_IS_ACCEPTED", "file": TOOL, "class": GIT,
     "old": "    if contained != 0:\n", "new": "    if False:\n",
     "expect": "test_a_checkout_behind_the_branch_is_handed_the_branch_s_newer_export",
     "edit": "the resume command accepts a HEAD that does not contain the fetched tip",
     "why": "the code and export the command acts on would be older than the branch's"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory; see batch_injections.py."""
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
    control, seconds = _run(CLASS)
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
        try:
            compile(edited, str(path), "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
        try:
            path.write_text(edited, encoding="utf-8")
            run, seconds = _run(injection.get("class", CLASS) + "." + injection["expect"])
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        caught = run.returncode != 0 and injection["expect"] in failed
        summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
        results.append({"id": injection["id"], "file": injection["file"],
                        "edit": injection["edit"], "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s", flush=True)
    out = Path(__file__).with_name("resume-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_SEC_RESUME_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
