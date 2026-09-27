#!/usr/bin/env python3
"""Fault injections for the batch acquisition, export and approval registration.

Each injection edits one source file in place, runs the test classes aimed at
it, restores the file byte for byte in a ``finally`` and checks the restore.
An injection counts as caught only when the run fails AND the named case is
among the failures or errors - a run that fails for another reason, such as
an edit that does not import, is reported as not caught. An edit that does not
apply exactly once stops the script before anything runs.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/acquisition-wiring/batch_injections.py
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SUITE = "tests.vnext.test_historical_sec_session"
SCRIPTED = SUITE + ".APassTakesOneTierAndNeverClaimsAUrlTwice"
REGISTER = SUITE + ".AnApprovalIsRegisteredOnlyFromTheApprovedBytes"
EXPORT = SUITE + ".AnExportCarriesExactlyWhatTheReplayAccepts"
SESSION = "scripts/vnext/historical_sec_session.py"
GATE = "scripts/vnext/historical_source_acquisition.py"
CARRY = "scripts/vnext/historical_source_export.py"

RESET = SUITE + ".ALedgerCannotBeResetByDeletingIt"

INJECTIONS = [
    {"id": "RETRY_A_URL_THIS_LEDGER_CLAIMED", "file": SESSION,
     "old": '                if row["source_url"] in claimed:\n',
     "new": '                if False:\n',
     "classes": [SCRIPTED],
     "expect": "test_a_failed_url_is_reported_and_not_claimed_again"},
    {"id": "TAKE_EVERY_TIER_IN_ONE_PASS", "file": SESSION,
     "old": '                result["frame_may_have_changed"] = tier != OTHER_TIER\n                break\n',
     "new": '                result["frame_may_have_changed"] = tier != OTHER_TIER\n',
     "classes": [SCRIPTED],
     "expect": "test_the_index_then_the_shards_then_the_rest_each_in_its_own_pass"},
    {"id": "KEEP_SENDING_AFTER_A_429", "file": SESSION,
     "old": '                    if status_code in SEC_ACCESS_REFUSED:\n',
     "new": '                    if False:\n',
     "classes": [SCRIPTED],
     "expect": "test_an_sec_access_refusal_stops_everything_by_name"},
    {"id": "ACCEPT_A_BODY_THAT_ONLY_STARTS_WITH_THE_APPROVAL", "file": GATE,
     "old": '    _need(fetched["body"].encode("utf-8") == approved,\n',
     "new": '    _need(fetched["body"].encode("utf-8").startswith(approved),\n',
     "classes": [REGISTER],
     "expect": "test_a_footer_appended_to_the_body_registers_nothing"},
    {"id": "EXPORT_A_LEDGER_NOBODY_REGISTERED", "file": CARRY,
     "old": '    checkpoint = _journal_checkpoint(ledger_sha256=ledger_sha)\n'
            '    validate_acquisition_checkpoint(data_root, checkpoint, baseline)\n'
            '    mode = checkpoint["execution_mode"]\n',
     "new": '    try:\n'
            '        checkpoint = _journal_checkpoint(ledger_sha256=ledger_sha)\n'
            '    except HistoricalExportError:\n'
            '        from .continuous_sec_acquisition import _journal\n'
            '        checkpoint = strict_json_file(path=sorted(_journal().iterdir())[-1])\n'
            '    mode = checkpoint["execution_mode"]\n',
     "classes": [EXPORT],
     "expect": "test_an_unregistered_ledger_is_not_exported"},
    {"id": "RESTORE_WITHOUT_CHECKING_THE_ARCHIVE_DIGEST", "file": CARRY,
     "old": '    _need(_binding(data) == {k: binding[k] for k in ("sha256", "size")},\n'
            '          "ISSUE_47_EXPORT_ARCHIVE_CHANGED:" + path.name)\n',
     "new": '',
     "classes": [EXPORT],
     "expect": "test_a_changed_archive_byte_is_refused"},
    {"id": "PLAN_BEFORE_REGISTERING_WHAT_A_DEAD_PROCESS_LEFT", "file": SESSION,
     "old": '            if register:\n'
            '                result["registered_before_planning"] = self._register_if_unregistered()\n',
     "new": '',
     "classes": [EXPORT],
     "expect": "test_an_unregistered_ledger_is_not_exported"},
    # The ledger protections ported from Issue #28 after the independent review.
    {"id": "COUNT_WHATEVER_SLOTS_EXIST", "file": SESSION,
     "old": '        _need(len(slots) == len(claims), "ISSUE_47_LEDGER_CLAIM_SET_CHANGED:"\n',
     "new": '        claims = claims[:len(slots)]\n        _need(True, "ISSUE_47_LEDGER_CLAIM_SET_CHANGED:"\n',
     "classes": [RESET],
     "expect": "test_a_deleted_slot_is_a_refusal_not_a_smaller_count"},
    {"id": "RESTART_A_LEDGER_WHOSE_ROOT_WAS_DELETED", "file": SESSION,
     "old": '            _need(not anchor.exists() and set(present) <= {"source-inputs"},\n',
     "new": '            anchor.unlink(missing_ok=True)\n            _need(set(present) <= {"source-inputs"},\n',
     "classes": [RESET],
     "expect": "test_a_deleted_root_is_a_refusal_not_a_fresh_start"},
    {"id": "TRUST_THE_SLOT_S_OWN_RECORDS", "file": SESSION,
     "old": '    if rows is not None:\n        index = receipt.get("ledger_row_index")\n',
     "new": '    if False:\n        index = receipt.get("ledger_row_index")\n',
     "classes": [RESET],
     "expect": "test_a_stop_hidden_by_rewriting_the_slot_s_own_records_is_found"},
    {"id": "ALLOW_A_SAME_REQUEST_REDRAW", "file": SESSION,
     "old": '        _need(request_digest not in state["request_digests"],\n',
     "new": '        _need(True,\n',
     "classes": [RESET],
     "expect": "test_a_same_request_claimed_again_is_a_redraw"},
    {"id": "LOCK_A_ROOT_THROUGH_A_SYMLINK", "file": SESSION,
     "old": '              and not any(path.is_symlink() for path in [self.root, *self.root.parents]),\n',
     "new": '              and True,\n',
     "classes": [RESET],
     "expect": "test_a_root_reached_through_a_symlink_is_refused"},
    {"id": "PARSE_THE_APPROVAL_LEAVING_THE_LAST_DUPLICATE_KEY", "file": GATE,
     "old": '        approved = strict_json_loads(text=comment["body"])\n',
     "new": '        approved = json.loads(comment["body"])\n',
     "classes": [SUITE + ".AnApprovalMustBeReadAsWrittenAndUnedited"],
     "expect": "test_a_duplicate_key_is_a_refusal_not_the_last_value"},
    {"id": "ACCEPT_AN_EDITED_APPROVAL", "file": GATE,
     "old": '    _need(type(comment.get("created_at")) is str and comment.get("created_at")\n'
            '          and comment.get("created_at") == comment.get("updated_at"),\n',
     "new": '    _need(True,\n',
     "classes": [SUITE + ".AnApprovalMustBeReadAsWrittenAndUnedited"],
     "expect": "test_an_edited_comment_is_not_the_approval"},
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
    out = Path(__file__).with_name("batch-injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_BATCH_ACQUISITION_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
