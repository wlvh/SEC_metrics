#!/usr/bin/env python3
"""Fault injections for the VM run: start marker, REST reader, transport record, approval provenance.

On 2026-09-29 the owner decided Issue #47's acquisition runs in the executor's
cloud container. Three things were added for that and each is injected here:
the start that must be published on issue 47 before any request, the reader
for a host without gh, and the transport each LIVE receipt records. A fourth
came from measuring that container: its GitHub API calls are made as the
owner's account through a GitHub App, so the approval gate now refuses a
comment an app posted, and - because the owner may paste the approval into
github.com - forgives the CRLF line breaks a browser sends and nothing else.
The same measurement means the executor could delete a start marker, so a
new start is also refused once the checkout carries this approval's export.

Same method as batch_injections.py: each injection edits one source file in
place, runs the test classes aimed at it, restores the file byte for byte in
a ``finally`` and checks the restore. An injection counts as caught only when
the run fails AND the named case is among the failures or errors; an edit
that does not apply exactly once, or does not compile, stops the script
before anything runs.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/acquisition-wiring/vm_start_injections.py
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
SUITE = "tests.vnext.test_historical_sec_session"
START = SUITE + ".AStartMustBePublishedBeforeAnyRequest"
TRANSPORT = SUITE + ".AReceiptSaysWhichWayItsBytesCame"
READER = "tests.vnext.test_historical_source_acquisition.TheRestReaderReadsOnlyThisIssuesComments"
REGISTER = SUITE + ".AnApprovalIsRegisteredOnlyFromTheApprovedBytes"
EXPORTS = SUITE + ".AnExportCarriesExactlyWhatTheReplayAccepts"
GRANT = SUITE + ".AGrantMustComeFromAnApprovalNotFromTwoLocalFiles"
SESSION = "scripts/vnext/historical_sec_session.py"
GATE = "scripts/vnext/historical_source_acquisition.py"
# The start's logic moved into a module the model ledger shares; the SEC
# ledger's cases still run it through the SEC session's names.
START_MODULE = "scripts/vnext/historical_ledger_start.py"
EXPORT_MODULE = "scripts/vnext/historical_source_export.py"

INJECTIONS = [
    {"id": "THE_LIVE_PATH_SKIPS_THE_START", "file": SESSION,
     "old": "    require_published_start(allowance=allowance, reader=reader)\n",
     "new": "",
     "classes": [START],
     "expect": "test_the_live_path_checks_the_start_before_any_transport"},
    {"id": "ANY_MARKER_WILL_DO", "file": START_MODULE,
     "old": '    _need(kind, first["record"] == marker_view(record),\n',
     "new": '    _need(kind, any(item["record"] == marker_view(record) for item in markers),\n',
     "classes": [START],
     "expect": "test_the_earliest_marker_decides_not_the_latest"},
    {"id": "THE_LATEST_MARKER_DECIDES", "file": START_MODULE,
     "old": '                                             int(item["comment"].get("id") or 0)))\n',
     "new": '                                             int(item["comment"].get("id") or 0)),\n'
            '                  reverse=True)\n',
     "classes": [START],
     "expect": "test_the_earliest_marker_decides_not_the_latest"},
    {"id": "AN_EDITED_MARKER_COUNTS", "file": START_MODULE,
     "old": '          and comment.get("created_at") == comment.get("updated_at"),\n'
            '          "START_MARKER_EDITED:"',
     "new": '          and True,\n'
            '          "START_MARKER_EDITED:"',
     "classes": [START],
     "expect": "test_an_edited_marker_does_not_count"},
    {"id": "A_STRANGER_S_MARKER_COUNTS", "file": START_MODULE,
     "old": '            if (record is not None and comment.get("author_association") == "OWNER"\n',
     "new": '            if (record is not None\n',
     "classes": [START],
     "expect": "test_a_stranger_s_marker_neither_blocks_nor_stands_in"},
    {"id": "ANOTHER_APPROVAL_S_MARKER_COUNTS", "file": START_MODULE,
     "old": '                    and record.get("delegation_body_sha256")\n'
            '                    == allowance["delegation_body_sha256"]):\n',
     "new": '                    ):\n',
     "classes": [START],
     "expect": "test_another_approval_s_marker_is_not_this_one_s"},
    {"id": "A_LOST_LEDGER_STARTS_AGAIN", "file": START_MODULE,
     "old": '    _need(kind, not start_markers(kind, allowance=allowance, reader=reader),\n',
     "new": '    _need(kind, True,\n',
     "classes": [START],
     "expect": "test_a_host_that_lost_its_ledger_cannot_start_the_allowance_again"},
    {"id": "ONLY_THE_FIRST_PAGE_IS_READ", "file": START_MODULE,
     "old": "        if len(comments) < _PAGE_SIZE:\n            break\n",
     "new": "        if True:\n            break\n",
     "classes": [START],
     "expect": "test_markers_are_read_past_the_first_page"},
    {"id": "THE_READER_TAKES_ANY_PATH", "file": GATE,
     "old": "    _need(_GITHUB_READABLE.match(str(path)) is not None,\n",
     "new": "    _need(True,\n",
     "classes": [READER],
     "expect": "test_only_this_issue_s_comment_resources_are_readable"},
    {"id": "THE_PROXY_S_CREDENTIALS_ARE_RECORDED", "file": SESSION,
     "old": '                proxy = (parts.scheme + "://" + (parts.hostname or "")\n'
            '                         + (":" + str(parts.port) if parts.port else ""))\n',
     "new": '                proxy = proxy\n',
     "classes": [TRANSPORT],
     "expect": "test_the_live_receipt_names_the_proxy_without_credentials_and_the_bundle"},
    {"id": "THE_TRANSPORT_IS_NOT_RECORDED", "file": SESSION,
     "old": '"wire": wire, "transport": self._transport(), "company_id": company_id,',
     "new": '"wire": wire, "company_id": company_id,',
     "classes": [TRANSPORT],
     "expect": "test_the_live_receipt_names_the_proxy_without_credentials_and_the_bundle"},
    {"id": "A_DELETED_MARKER_LETS_A_NEW_START", "file": START_MODULE,
     "old": '    _need(kind, not exported_here(kind, allowance=allowance, checkout=checkout),\n',
     "new": '    _need(kind, True,\n',
     "classes": [START],
     "expect": "test_an_export_on_the_branch_blocks_a_start_the_issue_would_allow"},
    {"id": "AN_UNREADABLE_EXPORT_READS_AS_NONE", "file": START_MODULE,
     "old": "    except (OSError, ValueError):\n        return True\n    if type(index) is not dict:\n",
     "new": "    except (OSError, ValueError):\n        return False\n    if type(index) is not dict:\n",
     "classes": [START],
     "expect": "test_an_export_on_the_branch_blocks_a_start_the_issue_would_allow"},
    {"id": "AN_APP_S_POST_COUNTS_AS_THE_OWNER_S", "file": GATE,
     "old": '    _need("performed_via_github_app" in comment and comment["performed_via_github_app"] is None,\n'
            '          "ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP:" + where)\n',
     "new": '    _need(True,\n'
            '          "ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP:" + where)\n',
     "classes": [REGISTER, GRANT],
     "expect": "test_an_approval_posted_through_an_app_registers_nothing"},
    {"id": "A_DROPPED_FIELD_READS_AS_NO_APP", "file": GATE,
     "old": '    _need("performed_via_github_app" in comment and comment["performed_via_github_app"] is None,\n'
            '          "ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP:" + where)\n',
     "new": '    _need(comment.get("performed_via_github_app") is None,\n'
            '          "ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP:" + where)\n',
     "classes": [REGISTER, GRANT],
     "expect": "test_an_app_s_mark_on_either_copy_is_a_refusal"},
    {"id": "THE_SAVED_RECORD_IS_NOT_READ_FOR_THE_MARK", "file": GATE,
     "old": '    _posted_by_the_approver_directly(comment, where="saved_record")\n',
     "new": '',
     "classes": [GRANT],
     "expect": "test_an_app_s_mark_on_either_copy_is_a_refusal"},
    {"id": "THE_FETCHED_COMMENT_IS_NOT_READ_FOR_THE_MARK", "file": GATE,
     "old": '        _provenance(comment=fetched, policy=policy, where="fetched")\n'
            '        _posted_by_the_approver_directly(fetched, where="fetched")\n',
     "new": '        _provenance(comment=fetched, policy=policy, where="fetched")\n',
     "classes": [GRANT],
     "expect": "test_an_app_s_mark_on_either_copy_is_a_refusal"},
    {"id": "REGISTRATION_DOES_NOT_READ_THE_MARK", "file": GATE,
     "old": '    _provenance(comment=fetched, policy=policy, where="fetched")\n'
            '    _posted_by_the_approver_directly(fetched, where="fetched")\n'
            '    record = {',
     "new": '    _provenance(comment=fetched, policy=policy, where="fetched")\n'
            '    record = {',
     "classes": [REGISTER],
     "expect": "test_an_approval_posted_through_an_app_registers_nothing"},
    {"id": "MORE_THAN_LINE_BREAKS_IS_FORGIVEN", "file": GATE,
     "old": '    return body.replace("\\r\\n", "\\n").rstrip(" \\t\\r\\n")\n',
     "new": '    return body.replace("\\r\\n", "\\n").replace("\\r", "\\n").strip()\n',
     "classes": [REGISTER],
     "expect": "test_only_line_breaks_are_forgiven"},
    {"id": "LINE_BREAKS_ARE_NOT_FORGIVEN", "file": GATE,
     "old": '    return body.replace("\\r\\n", "\\n").rstrip(" \\t\\r\\n")\n',
     "new": '    return body\n',
     "classes": [REGISTER],
     "expect": "test_a_body_pasted_into_the_web_page_registers_as_the_same_approval"},
    # The VM-delta review (model-egress/independent-review-2026-09-29-vm/): the
    # marker carried the whole start record, so a copy of it beside an empty
    # root was the start; nothing asked whether the branch's export was ahead
    # of the ledger; a marker's own issue and account were not checked; the
    # export could go backwards; and a redirected read was trusted.
    {"id": "THE_MARKER_CARRIES_THE_WHOLE_RECORD", "file": START_MODULE,
     "old": '            + json.dumps(marker_view(record), indent=1, sort_keys=True) + "\\n```\\n")',
     "new": '            + json.dumps(record, indent=1, sort_keys=True) + "\\n```\\n")',
     "also": [('    _need(kind, first["record"] == marker_view(record),\n',
               '    _need(kind, first["record"] == record,\n')],
     "classes": [START],
     "expect": "test_a_marker_copied_beside_an_empty_root_is_not_the_start"},
    {"id": "A_LEDGER_MAY_BE_BEHIND_ITS_EXPORT", "file": START_MODULE,
     "old": "    require_not_behind_export(kind, allowance=allowance, checkout=checkout)\n",
     "new": "",
     "classes": [START],
     "expect": "test_a_ledger_behind_its_export_on_the_branch_is_refused"},
    {"id": "A_MARKER_FROM_ANYWHERE_COUNTS", "file": START_MODULE,
     "old": ('                    and comment.get("issue_url") == issue_api and type(user) is dict\n'
             '                    and user.get("id") == kind.owner_id and user.get("type") == "User"\n'),
     "new": "",
     "classes": [START],
     "expect": "test_a_marker_not_from_this_issue_or_account_does_not_count"},
    {"id": "AN_EXPORT_MAY_GO_BACKWARDS", "file": EXPORT_MODULE,
     "old": '    _need(same and type(old_log) is dict and type(old_log.get("size")) is int\n',
     "new": '    _need(True or same and type(old_log) is dict and type(old_log.get("size")) is int\n',
     "classes": [EXPORTS],
     "expect": "test_an_export_replaces_only_its_own_shorter_self"},
    {"id": "A_REDIRECTED_READ_IS_TRUSTED", "file": GATE,
     "old": '    _need(final == url, "ISSUE_47_GITHUB_READ_WAS_REDIRECTED:" + str(final)[:160])\n',
     "new": "",
     "classes": [READER],
     "expect": "test_a_redirected_read_is_refused"},
    {"id": "THE_DIGEST_IS_OVER_THE_RAW_BODY", "file": GATE,
     "old": '    _need(sha256_bytes(content=posted_text(comment["body"]).encode("utf-8"))\n'
            '          == policy["delegation_body_sha256"],\n',
     "new": '    _need(sha256_bytes(content=comment["body"].encode("utf-8"))\n'
            '          == policy["delegation_body_sha256"],\n',
     "classes": [REGISTER],
     "expect": "test_a_body_pasted_into_the_web_page_registers_as_the_same_approval"},
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
    results = []
    for injection in INJECTIONS:
        path = REPO / injection["file"]
        original = path.read_bytes()
        text = original.decode("utf-8")
        # An injection may need more than one edit to stay one coherent change
        # (the whole-record marker is written and compared in two places).
        edited = text
        for old, new in [(injection["old"], injection["new"])] + injection.get("also", []):
            found = edited.count(old)
            if found != 1:
                print("INJECTION_DID_NOT_APPLY", injection["id"], found)
                return 2
            edited = edited.replace(old, new)
        try:
            compile(edited, str(path), "exec")
        except SyntaxError as error:
            print("INJECTED_SOURCE_DOES_NOT_COMPILE", injection["id"], error)
            return 2
        try:
            path.write_text(edited, encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", *injection["classes"]],
                                 cwd=REPO, env=_isolated_env(), capture_output=True, text=True, timeout=1800)
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            print("RESTORE_FAILED", injection["id"])
            return 2
        output = run.stdout + run.stderr
        failed = sorted(_failed_cases(output))
        caught = run.returncode != 0 and injection["expect"] in failed
        summary = [line for line in output.splitlines()
                   if line.startswith(("Ran ", "OK", "FAILED"))]
        results.append({"id": injection["id"], "file": injection["file"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary)})
        print(injection["id"], results[-1]["outcome"], failed, flush=True)
    out = Path(__file__).with_name("vm-start-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_VM_ACQUISITION_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
