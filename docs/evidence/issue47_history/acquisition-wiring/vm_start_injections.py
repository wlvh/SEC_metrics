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

REPO = Path(__file__).resolve().parents[4]
SUITE = "tests.vnext.test_historical_sec_session"
START = SUITE + ".AStartMustBePublishedBeforeAnyRequest"
TRANSPORT = SUITE + ".AReceiptSaysWhichWayItsBytesCame"
READER = "tests.vnext.test_historical_source_acquisition.TheRestReaderReadsOnlyThisIssuesComments"
REGISTER = SUITE + ".AnApprovalIsRegisteredOnlyFromTheApprovedBytes"
GRANT = SUITE + ".AGrantMustComeFromAnApprovalNotFromTwoLocalFiles"
SESSION = "scripts/vnext/historical_sec_session.py"
GATE = "scripts/vnext/historical_source_acquisition.py"

INJECTIONS = [
    {"id": "THE_LIVE_PATH_SKIPS_THE_START", "file": SESSION,
     "old": "    require_published_start(allowance=allowance, reader=reader)\n",
     "new": "",
     "classes": [START],
     "expect": "test_the_live_path_checks_the_start_before_any_transport"},
    {"id": "ANY_MARKER_WILL_DO", "file": SESSION,
     "old": '    _need(first["record"] == record,\n',
     "new": '    _need(any(item["record"] == record for item in markers),\n',
     "classes": [START],
     "expect": "test_the_earliest_marker_decides_not_the_latest"},
    {"id": "THE_LATEST_MARKER_DECIDES", "file": SESSION,
     "old": '                                             int(item["comment"].get("id") or 0)))\n',
     "new": '                                             int(item["comment"].get("id") or 0)),\n'
            '                  reverse=True)\n',
     "classes": [START],
     "expect": "test_the_earliest_marker_decides_not_the_latest"},
    {"id": "AN_EDITED_MARKER_COUNTS", "file": SESSION,
     "old": '          and comment.get("created_at") == comment.get("updated_at"),\n'
            '          "ISSUE_47_SEC_LEDGER_START_MARKER_EDITED:"',
     "new": '          and True,\n'
            '          "ISSUE_47_SEC_LEDGER_START_MARKER_EDITED:"',
     "classes": [START],
     "expect": "test_an_edited_marker_does_not_count"},
    {"id": "A_STRANGER_S_MARKER_COUNTS", "file": SESSION,
     "old": '            if (record is not None and comment.get("author_association") == "OWNER"\n',
     "new": '            if (record is not None\n',
     "classes": [START],
     "expect": "test_a_stranger_s_marker_neither_blocks_nor_stands_in"},
    {"id": "ANOTHER_APPROVAL_S_MARKER_COUNTS", "file": SESSION,
     "old": '                    and record.get("delegation_body_sha256")\n'
            '                    == allowance["delegation_body_sha256"]):\n',
     "new": '                    ):\n',
     "classes": [START],
     "expect": "test_another_approval_s_marker_is_not_this_one_s"},
    {"id": "A_LOST_LEDGER_STARTS_AGAIN", "file": SESSION,
     "old": '    _need(not start_markers(allowance=allowance, reader=reader),\n',
     "new": '    _need(True,\n',
     "classes": [START],
     "expect": "test_a_host_that_lost_its_ledger_cannot_start_the_allowance_again"},
    {"id": "ONLY_THE_FIRST_PAGE_IS_READ", "file": SESSION,
     "old": "        if len(comments) < 100:\n            break\n",
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
    {"id": "A_DELETED_MARKER_LETS_A_NEW_START", "file": SESSION,
     "old": '    _need(not _exported_here(allowance=allowance, checkout=ROOT if checkout is None else checkout),\n',
     "new": '    _need(True,\n',
     "classes": [START],
     "expect": "test_an_export_on_the_branch_blocks_a_start_the_issue_would_allow"},
    {"id": "AN_UNREADABLE_EXPORT_READS_AS_NONE", "file": SESSION,
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
    {"id": "THE_DIGEST_IS_OVER_THE_RAW_BODY", "file": GATE,
     "old": '    _need(sha256_bytes(content=posted_text(comment["body"]).encode("utf-8"))\n'
            '          == policy["delegation_body_sha256"],\n',
     "new": '    _need(sha256_bytes(content=comment["body"].encode("utf-8"))\n'
            '          == policy["delegation_body_sha256"],\n',
     "classes": [REGISTER],
     "expect": "test_a_body_pasted_into_the_web_page_registers_as_the_same_approval"},
]


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def main():
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
            run = subprocess.run([sys.executable, "-m", "unittest", *injection["classes"]],
                                 cwd=REPO, capture_output=True, text=True, timeout=1800)
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
