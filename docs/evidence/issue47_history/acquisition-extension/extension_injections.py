#!/usr/bin/env python3
"""Fault injections for the extension of the SEC approval: each must be caught by the case written for it.

The owner decided on one further approval after the first was spent to its
cap. ``historical_sec_extension`` verifies it; the ledger raises its cap by
exactly what it adds, only for the claim log it names; an already-requested
URL is requested again only as a refresh or replacement of a class the owner
named, once, and marked in the request; the live path pins it; the resume
counts what it allows; the export records it beside its approval. Each
injection below undoes one of those, and the case named for it must fail.
Same rules as ``resume_injections.py``: an edit that does not apply exactly
once or does not compile stops the script, the file is restored byte for byte
and checked, and every run reads and writes bytecode only in a fresh
directory. The control run must pass first. Run it in a clone, not in a tree
another job reads.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/acquisition-extension/extension_injections.py
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
T = "tests.vnext.test_historical_sec_session."
CAP = T + "AnExtensionRaisesTheCapOnlyForTheLedgerItNames"
AGAIN = T + "AnExtensionMayRequestARefreshOrReplacementOnceMore"
GATE = T + "AnExtensionIsVerifiedLikeTheApprovalItExtends"
CHAIN = T + "AReplacementUnderTheExtensionReplaysThroughTheFrozenValidator"
EXPORTED = T + "AnExportSaysWhichExtensionItWasSpentUnder"
LIVE = T + "TheLivePathHoldsTheLedgerToTheExtensionItRead"
BRANCH = T + "AnExtensionIsSpentOnlyOnceTheBranchCarriesIt"
START = T + "AStartMustBePublishedBeforeAnyRequest"
LOST = T + "ALostHostResumesFromTheExportAndPaysForWhatItMayHaveSpent"
STATE = T + "TheStatedSpendingIsTheLedgerAtThatState"
CONTROL = [CAP, AGAIN, GATE, CHAIN, EXPORTED, LIVE, BRANCH, START, LOST, STATE]
SESSION = "scripts/vnext/historical_sec_session.py"
EXTENSION = "scripts/vnext/historical_sec_extension.py"
RESUME = "scripts/vnext/historical_sec_resume.py"
EXPORT = "scripts/vnext/historical_source_export.py"
INJECTIONS = [
    {"id": "ANY_CLAIM_LOG_IS_EXTENDED", "file": SESSION, "class": CAP,
     "old": ("        _need(len(held) >= size and sha256_bytes(content=held[:size]) == state[\"claims\"][\"sha256\"]\n"
             "              and held[:size].count(b\"\\n\") == state[\"claim_count\"],\n"),
     "new": "        _need(True,\n",
     "expect": "test_an_extension_of_another_ledger_or_state_is_refused",
     "edit": "pin_extension() raises the cap whatever the ledger's claim log holds",
     "why": "an extension approved for one ledger would raise the cap of any ledger at the root"},
    {"id": "THE_CAP_IS_NOT_RAISED", "file": SESSION, "class": CAP,
     "old": "            limits = [a + b for a, b in zip(limits, self._extension[\"limits\"])]\n",
     "new": "            limits = limits\n",
     "expect": "test_the_cap_rises_by_exactly_what_the_extension_adds",
     "edit": "_limits() ignores the pinned extension",
     "why": "the approval would be read and pinned and still grant nothing"},
    {"id": "THE_CAP_IS_RAISED_TWICE", "file": SESSION, "class": CAP,
     "old": "            limits = [a + b for a, b in zip(limits, self._extension[\"limits\"])]\n",
     "new": "            limits = [a + 2 * b for a, b in zip(limits, self._extension[\"limits\"])]\n",
     "expect": "test_the_cap_rises_by_exactly_what_the_extension_adds",
     "edit": "_limits() adds the extension's limits twice",
     "why": "more requests than the owner approved"},
    {"id": "A_URL_IS_REQUESTED_AGAIN_AND_AGAIN", "file": EXTENSION, "class": AGAIN,
     "old": ("    if max(claimed_ordinals) > extension[\"ledger_state\"][\"claim_count\"]:\n"
             "        return None\n"),
     "new": "",
     "expect": "test_a_refresh_is_requested_once_more_under_the_extension_and_not_again",
     "edit": "reclaim_ordinal() allows a URL requested under the extension to be requested again",
     "why": "zero automatic retries would become one retry per pass"},
    {"id": "ANY_KIND_IS_REQUESTED_AGAIN", "file": EXTENSION, "class": AGAIN,
     "old": ("        if (dependency.get(\"acquisition_kind\") == entry[\"acquisition_kind\"]\n"
             "                and dependency[\"dependency_class\"] in entry[\"dependency_classes\"]):\n"),
     "new": "        if dependency[\"dependency_class\"] in entry[\"dependency_classes\"]:\n",
     "expect": "test_only_the_kinds_and_classes_the_owner_named",
     "edit": "reclaim_ordinal() ignores why the planner asks again",
     "why": "a failed first request of a named class would be retried without being a replacement"},
    {"id": "ANY_CLASS_IS_REQUESTED_AGAIN", "file": EXTENSION, "class": AGAIN,
     "old": ("        if (dependency.get(\"acquisition_kind\") == entry[\"acquisition_kind\"]\n"
             "                and dependency[\"dependency_class\"] in entry[\"dependency_classes\"]):\n"),
     "new": "        if dependency.get(\"acquisition_kind\") == entry[\"acquisition_kind\"]:\n",
     "expect": "test_only_the_kinds_and_classes_the_owner_named",
     "edit": "reclaim_ordinal() ignores which classes the owner named",
     "why": "a refresh of a class the owner did not name would be requested again"},
    {"id": "A_MARKER_WITHOUT_AN_EXTENSION", "file": SESSION, "class": AGAIN,
     "old": ("        _need(reclaim is None\n"
             "              or (type(reclaim) is int and reclaim > 0\n"
             "                  and (self.allowance.get(\"extension\") or {}).get(\"extension_ordinal\")\n"
             "                  == reclaim), \"ISSUE_47_RECLAIM_WITHOUT_ITS_EXTENSION\")\n"),
     "new": "",
     "expect": "test_a_re_request_marker_needs_the_extension_that_makes_it",
     "edit": "_capture_one() takes a re-request marker from a caller with no extension",
     "why": "a claimed URL could be requested again by anything that passes the marker"},
    {"id": "THE_REQUEST_IS_NOT_MARKED", "file": SESSION, "class": CHAIN,
     "old": ("        if reclaim is not None:\n"
             "            request[\"reclaimed_under_extension\"] = reclaim\n"),
     "new": "",
     "expect": "test_the_replacement_is_saved_and_the_plan_stops_asking",
     "edit": "_capture_one() requests again with the first request's exact bytes",
     "why": "the same digest twice is the redraw the ledger forbids; the replacement could never be made"},
    {"id": "THE_FIRST_APPROVAL_S_GRANTS_STAY", "file": EXTENSION, "class": AGAIN,
     "old": "    return {**allowance, \"scope\": extension[\"scope\"], \"first_approval_scope\": allowance[\"scope\"],\n",
     "new": "    return {**allowance, \"scope\": allowance[\"scope\"], \"first_approval_scope\": allowance[\"scope\"],\n",
     "expect": "test_after_the_extension_requests_are_held_to_its_grants",
     "edit": "extended_allowance() keeps the first approval's grants",
     "why": "requests after the extension would be held to grants the owner did not approve for them"},
    {"id": "THE_COMMENT_NEED_NOT_RESTATE_THE_POLICY", "file": EXTENSION, "class": GATE,
     "old": ("        _need(approved.get(field) == policy[field],\n"
             "              \"ISSUE_47_EXTENSION_WIDENS_THE_APPROVED_GRANT:\" + field)\n"),
     "new": "        pass\n",
     "expect": "test_each_tie_and_each_field_refuses_by_name",
     "edit": "_approved_body() does not compare the comment with the policy",
     "why": "a policy file could grant more than the owner's comment says"},
    {"id": "ANY_APPROVAL_MAY_BE_EXTENDED", "file": EXTENSION, "class": GATE,
     "old": ("    _need(extends[\"delegation_url\"] == allowance[\"delegation_url\"]\n"
             "          and extends[\"delegation_body_sha256\"] == allowance[\"delegation_body_sha256\"],\n"
             "          \"ISSUE_47_EXTENSION_EXTENDS_ANOTHER_APPROVAL\")\n"),
     "new": "",
     "expect": "test_each_tie_and_each_field_refuses_by_name",
     "edit": "_typed() does not tie the extension to the approval it names",
     "why": "an extension of another approval would raise this one's cap"},
    {"id": "GITHUB_IS_NOT_COMPARED", "file": EXTENSION, "class": GATE,
     "old": ("        _need(fetched.get(\"body\") == comment[\"body\"],\n"
             "              \"ISSUE_47_SAVED_EXTENSION_DIFFERS_FROM_THE_ONE_ON_GITHUB\")\n"),
     "new": "",
     "expect": "test_the_saved_record_must_be_what_github_returns",
     "edit": "_approved_body() fetches the comment and does not compare it with the saved record",
     "why": "a locally written record would stand for an approval nobody posted"},
    {"id": "THE_LOST_HOST_S_RE_REQUESTS_ARE_FREE", "file": RESUME, "class": AGAIN,
     "old": ("            if row[\"source_url\"] in claimed and (\n"
             "                    claimed[row[\"source_url\"]] is None\n"
             "                    or reclaim_ordinal(allowance=allowance, dependency=row,\n"
             "                                       claimed_ordinals=claimed[row[\"source_url\"]]) is None):\n"),
     "new": "            if row[\"source_url\"] in claimed:\n",
     "expect": "test_a_lost_host_s_reserve_counts_what_the_extension_let_it_request_again",
     "edit": "lost_segment_reserve() counts every claimed URL as done",
     "why": "a lost host may have requested it again under the extension; the charge would miss it"},
    {"id": "THE_EXPORT_RECORDS_ANY_EXTENSION", "file": EXPORT, "class": EXPORTED,
     "old": ("    _need(policy[\"extends\"][\"delegation_url\"] == approval[\"delegation_url\"]\n"
             "          and policy[\"extends\"][\"delegation_body_sha256\"] == approval[\"delegation_body_sha256\"]\n"
             "          and Path(policy[\"budget_root\"]) == Path(approval[\"budget_root\"]),\n"),
     "new": "    _need(True,\n",
     "expect": "test_an_extension_of_another_approval_or_root_is_refused",
     "edit": "_extension() records an extension beside an approval it does not extend",
     "why": "the branch would say a ledger was spent under an extension of another approval"},
    {"id": "THE_LIVE_PATH_DOES_NOT_PIN", "file": SESSION, "class": LIVE,
     "old": ("        ledger.pin_extension(allowance[\"extension\"])\n"
             "    return ledger\n"),
     "new": "        pass\n    return ledger\n",
     "expect": "test_the_live_ledger_is_raised_only_for_the_log_it_continues",
     "edit": "live_ledger() reads the extension and does not pin it",
     "why": "production would stop at the first cap while every recorded case passed"},
    # The independent review's findings (2026-09-30), one injection per fix.
    {"id": "A_REPLACEMENT_FOR_ANY_UNREADABLE_COPY", "file": EXTENSION, "class": AGAIN,
     "old": ("    if (dependency.get(\"acquisition_kind\") == \"REPLACEMENT_ACQUISITION\"\n"
             "            and not str(dependency.get(\"reason\") or \"\").startswith(FAILED_REQUEST_REASON)):\n"
             "        return None\n"),
     "new": "",
     "expect": "test_a_replacement_is_only_for_a_copy_whose_last_request_failed",
     "edit": "reclaim_ordinal() requests again any copy the planner cannot read",
     "why": "a changed hash or a conflicting attempt is not the failed request the owner named (review L2)"},
    {"id": "THE_CALLER_S_MARKER_IS_TRUSTED", "file": SESSION, "class": CHAIN,
     "old": ("        _need(self._reclaim(dependency, self.ledger.claimed_url_ordinals()) == reclaim,\n"
             "              \"ISSUE_47_RECLAIM_IS_NOT_WHAT_THE_LEDGER_ALLOWS:\" + url)\n"),
     "new": "",
     "expect": "test_the_replacement_is_saved_and_the_plan_stops_asking",
     "edit": "_capture_one() takes the marker it is handed without reading the slots",
     "why": "a URL already requested under the extension could be requested a third time (review L3)"},
    {"id": "THE_STATED_SPENDING_IS_NOT_CHECKED", "file": SESSION, "class": LIVE,
     "old": ("        _need(spent == list(state[\"cumulative\"]),\n"),
     "new": "        _need(True,\n",
     "expect": "test_the_live_ledger_is_raised_only_for_the_log_it_continues",
     "edit": "pin_extension() does not compare the stated spending with the claim log",
     "why": "the owner could approve an increment against a spending that was not the ledger's (review L4)"},
    {"id": "ANY_EXTENSION_MAY_FOLLOW_ANOTHER", "file": SESSION, "class": LIVE,
     "old": ("        _need(anchor.is_file() and not anchor.is_symlink() and anchor.read_bytes() == pinned,\n"),
     "new": "        _need(True,\n",
     "expect": "test_the_live_ledger_is_raised_only_for_the_log_it_continues",
     "edit": "pin_extension() accepts an extension other than the one first pinned at the root",
     "why": "an unverified dict could raise the cap after the real extension was pinned (review L1)"},
    {"id": "A_LIVE_EXTENSION_NEED_NOT_BE_READ_BACK", "file": SESSION, "class": LIVE,
     "old": ("        _need(allowance[\"extension\"].get(\"provenance_verified_against_github\") is True,\n"),
     "new": "        _need(True,\n",
     "expect": "test_the_live_ledger_is_raised_only_for_the_log_it_continues",
     "edit": "live_ledger() pins an extension that was not read back from GitHub",
     "why": "a locally written extension would raise the live cap (review L1)"},
    {"id": "THE_SESSION_AND_ITS_LEDGER_MAY_DISAGREE", "file": SESSION, "class": AGAIN,
     "old": ("              \"ISSUE_47_LEDGER_AND_SESSION_DISAGREE_ON_THE_EXTENSION\")\n"),
     "new": "              \"ISSUE_47_LEDGER_AND_SESSION_DISAGREE_ON_THE_EXTENSION\") if False else None\n",
     "expect": "test_a_session_holding_other_grants_than_its_ledger_s_extension_is_refused",
     "edit": "_check() lets a session hold other grants than its ledger's extension",
     "why": "requests would be counted against one approval and admitted by another (review L1, the uncaught injection)"},
    {"id": "THE_LIVE_PATH_IGNORES_THE_BRANCH", "file": SESSION, "class": START,
     "old": ("    require_extension_on_branch(repo_root=ROOT, branch_files=tip.get(\"extension_files\"))\n"),
     "new": "",
     "expect": "test_the_live_path_needs_the_branch_to_say_which_extension",
     "edit": "live_historical_session() does not compare the extension with the branch tip",
     "why": "an extension never pushed could be spent, and a resume reading the branch could not charge for it (review M1)"},
    {"id": "ANY_BRANCH_CARRIES_THE_EXTENSION", "file": EXTENSION, "class": BRANCH,
     "old": ("        _need(held == branch_files[relative],\n"),
     "new": "        _need(True,\n",
     "expect": "test_the_checkout_and_the_tip_must_carry_the_same_extension",
     "edit": "require_extension_on_branch() accepts files the branch does not carry",
     "why": "the same as above, inside the check itself (review M1)"},
    {"id": "A_RESUME_UNDER_ANY_EXTENSION", "file": RESUME, "class": LOST,
     "old": ("    _need(index.get(\"extension\") is None\n"
             "          or _same_extension(index[\"extension\"], allowance.get(\"extension\")),\n"),
     "new": "    _need(True,\n",
     "expect": "test_a_resume_charges_under_the_extension_the_export_was_spent_under",
     "edit": "resume_ledger() charges an export spent under an extension without it",
     "why": "the lost segment's charge would leave out the rows only the extension admits (review M1)"},
    {"id": "A_RESUME_CHARGED_UNDER_ANOTHER_EXTENSION_HOLDS", "file": RESUME, "class": LOST,
     "old": ("              \"RESUME_WAS_CHARGED_UNDER_ANOTHER_EXTENSION\")\n"),
     "new": "              \"RESUME_WAS_CHARGED_UNDER_ANOTHER_EXTENSION\") if False else None\n",
     "expect": "test_a_resume_charged_under_an_extension_holds_only_under_it",
     "edit": "require_published_resume() keeps a resume charged under another extension",
     "why": "its reserve was not computed against the grants now spent (review M1)"},
    # The re-review's N1: the state binds the resume chain as the export carried it.
    {"id": "A_RESUME_AFTER_THE_STATE_IS_COUNTED", "file": SESSION, "class": STATE,
     "old": ("        if offset < stated:\n"),
     "new": "        if True:\n",
     "expect": "test_a_resume_before_the_state_is_in_it_and_one_after_is_not",
     "edit": "resume_reserve_at_state() counts every resume in the chain as spent at the state",
     "why": "a resume after the state, restoring the stated export, would refuse every later pin (the re-review's N1)"},
    {"id": "THE_STATE_MAY_LEAVE_OUT_AN_EARLIER_RESUME", "file": SESSION, "class": STATE,
     "old": ("            _need(restored >= claims_size,\n"),
     "new": "            _need(True,\n",
     "expect": "test_a_state_that_leaves_out_an_earlier_resume_is_refused",
     "edit": "resume_reserve_at_state() lets a resume that restored an earlier log sit outside the stated chain",
     "why": "the stated spending would understate a charge made before the state"},
    {"id": "THE_STATED_CHAIN_IS_NOT_BOUND", "file": SESSION, "class": STATE,
     "old": ("    _need(len(chain) >= stated and sha256_bytes(content=chain[:stated]) == resumes[\"sha256\"],\n"),
     "new": "    _need(True,\n",
     "expect": "test_a_chain_that_does_not_begin_with_the_stated_one_is_refused",
     "edit": "resume_reserve_at_state() does not compare the chain with the stated bytes",
     "why": "a chain whose charges were changed after the state would be read as the stated one"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory; see batch_injections.py."""
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def _run(*selectors):
    started = time.time()
    run = subprocess.run([sys.executable, "-m", "unittest", *selectors], cwd=REPO,
                         env=_isolated_env(), capture_output=True, text=True, timeout=3600)
    return run, int(time.time() - started)


def main():
    control, seconds = _run(*CONTROL)
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
            run, seconds = _run(injection["class"] + "." + injection["expect"])
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
    out = Path(__file__).with_name("extension-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_SEC_EXTENSION_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
