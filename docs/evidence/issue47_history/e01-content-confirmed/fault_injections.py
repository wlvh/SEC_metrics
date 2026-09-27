"""Break one E01 content-confirmation rule at a time; its case must fail.

Each injection edits one module in memory and runs the E01 suites in a child
process whose ``vnext`` package searches a temporary directory holding only the
edited module before the checkout's own package, so the checkout is never
written. The control run - every module unedited through the same path - must
pass and run the whole suite; a child that loads nothing reports no failures,
which would make every injection read as missed for no reason about the rules.

The second group breaks the confirmation contract the owner's decision needs
before any window can be counted: the request, the answer's form, the count,
and how a registered answer is found, checked again and installed.

Usage:
    python3 docs/evidence/issue47_history/e01-content-confirmed/fault_injections.py
"""
from __future__ import annotations

import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SUITES = ("tests.vnext.test_historical_event_items", "tests.vnext.test_historical_ma_confirmation")
ITEMS = REPO / "scripts/vnext/historical_event_items.py"
ROUTE = REPO / "scripts/vnext/historical_zero_ai_results.py"
CONFIRM = REPO / "scripts/vnext/historical_ma_confirmation.py"
RESULTS = REPO / "scripts/vnext/historical_results.py"
MODULES = (ITEMS, ROUTE, CONFIRM, RESULTS)

INJECTIONS = [
    ("COUNT_EVERY_CANDIDATE_UNCONFIRMED", ROUTE,
     "                if confirmation[\"candidates\"]:\n                    request = confirmation_request(",
     "                if False:\n                    request = confirmation_request(",
     "test_a_window_with_a_candidate_is_withheld_by_name"),
    ("KEEP_THE_APPROVED_ROUTE", ROUTE,
     "        if metric_id in SUCCESSOR_EVENT_ROUTES:\n            # The owner's",
     "        if False:\n            # The owner's", "test_the_spec_is_the_successor_route_s"),
    ("ACCEPT_A_SUCCESSOR_OF_ANOTHER_ROUTE", ITEMS,
     "    _need(record[\"predecessor\"][\"route_hash\"] == content_hash(value=dict(frozen_route)),",
     "    _need(True or record[\"predecessor\"][\"route_hash\"] == content_hash(value=dict(frozen_route)),",
     "test_a_successor_written_against_another_route_is_refused"),
    ("READ_ONLY_THE_8_01_ITEMS", ITEMS,
     "    codes = [str(code) for code in route[\"candidate_item_codes\"]]",
     "    codes = [\"8.01\"]", "test_every_candidate_item_is_read_from_its_own_text"),
    ("A_ZERO_WINDOW_NOT_BOUND_TO_ITS_READING", ROUTE,
     "                binding[\"content_confirmation\"] = compact_confirmation(confirmation)",
     "                pass", "test_a_window_with_no_candidate_is_answered_zero_by_the_route_s_matcher"),
    # The confirmation contract.
    ("A_DECLINED_CANDIDATE_STILL_COUNTS", ROUTE,
     "                    claims = [claim for claim in claims\n"
     "                              if claim[\"verified_claim_id\"] not in candidate_ids\n"
     "                              or claim[\"verified_claim_id\"] in confirmed]\n",
     "", "test_a_window_whose_candidates_are_all_declined_is_zero"),
    ("AN_UNSETTLED_WINDOW_COUNTS_WHAT_IS_SETTLED", CONFIRM,
     "    if unsettled:\n        return None, WITHHELD_REASON, unsettled\n", "",
     "test_an_item_its_text_does_not_settle_withholds_the_window_by_name"),
    ("THE_REGISTERED_ANSWER_IS_NOT_INSTALLED", ROUTE,
     "                    confirmation[\"registered_record\"] = registered\n", "",
     "test_the_count_is_the_items_the_answer_confirms"),
    ("A_BATCH_CONSUMES_A_RECORDED_ANSWER", CONFIRM,
     "        mode = installed[\"mode\"] if installed is not None else \"LIVE\"",
     "        mode = installed[\"mode\"] if installed is not None else \"RECORDED_TEST_ONLY\"",
     "test_a_batch_never_consumes_a_recorded_answer"),
    ("AN_ANSWER_TO_ANOTHER_QUESTION_IS_TAKEN", CONFIRM,
     "                    if strict_json_file(path=path).get(\"request_id\") == request[\"request_id\"]]",
     "                    if True]",
     "test_an_answer_to_another_question_is_not_this_window_s"),
    ("A_CAPTION_ONLY_ITEM_KEEPS_ONLY_ITS_CAPTION", ITEMS,
     "    return caption is not None and _LETTERS.sub(",
     "    return False and _LETTERS.sub(",
     "test_a_caption_only_item_carries_the_body_it_shares"),
    ("A_QUOTE_NEED_NOT_BE_THE_ITEM_S_WORDS", CONFIRM,
     "        _need(quote in texts[identity], \"E01_CONFIRMATION_QUOTE_NOT_IN_THE_ITEM:\" + identity)",
     "        _need(True or quote in texts[identity], \"E01_CONFIRMATION_QUOTE_NOT_IN_THE_ITEM:\" + identity)",
     "test_a_quote_not_in_the_item_is_refused"),
    ("A_RESEALED_COUNT_IS_ACCEPTED", CONFIRM,
     "    _need(again == record, \"E01_CONFIRMATION_DOES_NOT_RE_DERIVE\")",
     "    _need(True or again == record, \"E01_CONFIRMATION_DOES_NOT_RE_DERIVE\")",
     "test_an_edited_count_is_refused_even_when_resealed"),
    ("THE_SPEC_DOCUMENT_IS_NOT_HELD_TO_THE_ROUTE", RESULTS,
     "    _need(document.read_text(encoding=\"utf-8\") == _spec_document(compiled)\n",
     "    _need(True or document.read_text(encoding=\"utf-8\") == _spec_document(compiled)\n",
     "test_the_successor_spec_is_a_document_the_route_generates"),
    ("AN_ITEM_MAY_GO_UNANSWERED", CONFIRM,
     "    _need(set(decisions) == set(texts), ",
     "    _need(True or set(decisions) == set(texts), ",
     "test_every_item_is_answered_exactly_once"),
]


def run_one(edits):
    """Run the suite with ``edits`` ({module path: text}); return (failed, tests run, return code)."""
    with tempfile.TemporaryDirectory() as tmp:
        for module, text in edits.items():
            target = Path(tmp) / module.name
            target.write_text(text, encoding="utf-8")
            py_compile.compile(str(target), doraise=True)
        code = ("import sys; sys.path.insert(0, %r); import vnext; vnext.__path__.insert(0, %r); "
                "sys.argv=['x', *%r]; import unittest; unittest.main(module=None)"
                ) % (str(REPO / "scripts"), tmp, list(SUITES))
        run = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=1800)
        failed = sorted({line.split(" ")[1] for line in run.stderr.splitlines()
                         if line.startswith(("FAIL: ", "ERROR: "))})
        ran = [int(line.split()[1]) for line in run.stderr.splitlines() if line.startswith("Ran ")]
        return failed, (ran[-1] if ran else 0), run.returncode


def main():
    originals = {module: module.read_text(encoding="utf-8") for module in MODULES}
    control, control_ran, control_code = run_one({})
    if control or control_code != 0 or control_ran == 0:
        raise SystemExit("E01_INJECTION_CONTROL_DID_NOT_RUN_CLEAN: failed=%s ran=%s rc=%s"
                         % (control, control_ran, control_code))
    results = []
    for name, module, old, new, expected in INJECTIONS:
        text = originals[module]
        if text.count(old) != 1:
            results.append({"injection": name, "result": "EDIT_DOES_NOT_APPLY", "count": text.count(old)})
            continue
        # A module edited alone: the others are the checkout's.
        edits = {module: text.replace(old, new)}
        failed, ran, _code = run_one(edits)
        if ran != control_ran:
            results.append({"injection": name, "expected": expected, "result": "SUITE_DID_NOT_RUN", "ran": ran})
            continue
        results.append({"injection": name, "module": module.name, "expected": expected,
                        "result": "CAUGHT" if expected in failed else ("CAUGHT_ELSEWHERE" if failed else "MISSED"),
                        "failed": failed})
    out = {"record_type": "E01_CONTENT_CONFIRMED_FAULT_INJECTIONS", "suites": list(SUITES),
           "control_failures": control, "control_tests_run": control_ran,
           "caught": sum(r["result"] == "CAUGHT" for r in results), "total": len(results), "results": results}
    (HERE / "fault-injections.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("control_failures", "control_tests_run", "caught", "total")}))
    for row in results:
        if row["result"] != "CAUGHT":
            print(json.dumps(row))
    for module, text in originals.items():
        assert module.read_text(encoding="utf-8") == text
    return 0 if out["caught"] == out["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
