"""Break one D02 Item 8 review rule at a time; its case must fail.

Each injection edits one module in memory and runs the D02 review suite in a
child process whose ``vnext`` package searches a temporary directory holding
only the edited module before the checkout's own package, so the checkout is
never written. The control run - every module unedited through the same path -
must pass and run the whole suite; a child that loads nothing reports no
failures, which would make every injection read as missed for no reason about
the rules. An edit that does not hit exactly once, or does not compile, is
reported as such rather than run.

Usage:
    python3 docs/evidence/issue47_history/d02-item-8-review/fault_injections.py
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
SUITES = ("tests.vnext.test_historical_legal_review",)
REVIEW = REPO / "scripts/vnext/historical_legal_review.py"
TEXT = REPO / "scripts/vnext/historical_text_results.py"
INPUT = REPO / "scripts/vnext/historical_text_input.py"
MODULES = (REVIEW, TEXT, INPUT)

INJECTIONS = [
    # The request.
    ("MUST_DECIDE_IS_ONLY_THE_VOCABULARY", REVIEW,
     "            if index in set(keyword_admitted)\n            or MUST_DECIDE_TERMS",
     "            if MUST_DECIDE_TERMS",
     "test_a_keyword_admission_is_decided_even_without_the_vocabulary"),
    ("THE_POOL_TAKES_WHAT_A_NOTE_OWNS", TEXT,
     "        if (owner[index] is not scope or index in furniture or index in running_header",
     "        if (index in furniture or index in running_header",
     "test_the_pool_is_item_8_s_own_blocks"),
    ("THE_POOL_AND_THE_PROPOSAL_MAY_DISAGREE", TEXT,
     "    _need(admitted == keyword, \"HISTORICAL_D02_REVIEW_POOL_DISAGREES_WITH_THE_PROPOSAL\")",
     "    _need(True or admitted == keyword, \"HISTORICAL_D02_REVIEW_POOL_DISAGREES_WITH_THE_PROPOSAL\")",
     "test_a_pool_that_disagrees_with_the_proposal_is_refused"),
    # The answer's form.
    ("A_BLOCK_MAY_GO_UNDECIDED", REVIEW,
     "    _need(set(decisions) == must, ",
     "    _need(True or set(decisions) == must, ",
     "test_every_must_decide_block_is_decided_exactly_once"),
    ("AN_OUT_OF_SCOPE_MAY_CARRY_A_QUOTE", REVIEW,
     "            _need(entry[\"quote\"] is None, ",
     "            _need(True or entry[\"quote\"] is None, ",
     "test_decisions_and_quotes"),
    ("A_QUOTE_NEED_NOT_BE_THE_BLOCK_S_WORDS", REVIEW,
     "    return type(quote) is str and lower <= len(quote) <= QUOTE_CHARACTERS[1] and quote in text",
     "    return type(quote) is str and lower <= len(quote) <= QUOTE_CHARACTERS[1]",
     "test_decisions_and_quotes"),
    ("AN_ADDITION_MAY_NAME_ANY_BLOCK", REVIEW,
     "        _need(identity in texts, \"D02_REVIEW_ADDS_A_BLOCK_NOT_IN_THE_REQUEST:\"",
     "        _need(True or identity in texts, \"D02_REVIEW_ADDS_A_BLOCK_NOT_IN_THE_REQUEST:\"",
     "test_additions"),
    # What an answer counts, and how a registration is found.
    ("AN_UNSETTLED_FILING_PUBLISHES_THE_SETTLED_PART", REVIEW,
     "    if unsettled:\n        return None, WITHHELD_REASON, unsettled\n", "",
     "test_an_unsettled_block_withholds_the_filing"),
    ("AN_ADDITION_IS_NOT_COUNTED", REVIEW,
     "               if entry[\"decision\"] == \"IN_SCOPE\"} | set(added)",
     "               if entry[\"decision\"] == \"IN_SCOPE\"}",
     "test_in_scope_and_additions_in_document_order"),
    ("A_STALE_REVIEW_READS_AS_UNREVIEWED", REVIEW,
     "    _need(bool(matching), \"D02_REVIEW_REGISTERED_FOR_ANOTHER_REQUEST\")",
     "    if not matching:\n        return None",
     "test_a_record_for_another_request_is_refused_not_read_as_unreviewed"),
    ("A_RESEALED_REVIEW_IS_ACCEPTED", REVIEW,
     "    _need(again == record, \"D02_REVIEW_DOES_NOT_RE_DERIVE\")",
     "    _need(True or again == record, \"D02_REVIEW_DOES_NOT_RE_DERIVE\")",
     "test_an_edited_count_is_refused_even_when_resealed"),
    ("A_BATCH_CONSUMES_A_RECORDED_REVIEW", REVIEW,
     "        mode = installed[\"mode\"] if installed is not None else \"LIVE\"",
     "        mode = installed[\"mode\"] if installed is not None else \"RECORDED_TEST_ONLY\"",
     "test_the_input_carries_a_registered_review_only_in_its_mode"),
    ("AN_INSTALLED_REVIEW_OF_ANOTHER_POSITION_IS_READ", REVIEW,
     "        _need(installed.get(\"review_key\") == key, ",
     "        _need(True or installed.get(\"review_key\") == key, ",
     "test_an_installed_recorded_copy_is_read_only_for_its_own_position"),
    # The route.
    ("THE_KEYWORD_ADMISSIONS_STAY", TEXT,
     "        if scope[\"section_id\"] == \"ITEM_8\":\n            candidates.extend(_excerpt(",
     "        if False:\n            candidates.extend(_excerpt(",
     "test_a_review_replaces_only_the_item_8_excerpts"),
    ("AN_UNSETTLED_REVIEW_IS_APPLIED", TEXT,
     "    if reviewed[\"withheld_reason\"] is not None:\n        raise LegalReviewUnsettled(",
     "    if False:\n        raise LegalReviewUnsettled(",
     "test_an_unsettled_review_withholds_the_filing_by_name"),
    ("A_REVIEW_MAY_REACH_C02", TEXT,
     "    _need(legal_review is None or metric_id == \"D02\",",
     "    _need(True or legal_review is None or metric_id == \"D02\",",
     "test_c02_takes_no_review"),
    ("THE_INPUT_IGNORES_REGISTERED_REVIEWS", INPUT,
     "    if metric_id == \"D02\" and text_args is not None and not _without_reviews:",
     "    if False:",
     "test_the_input_carries_a_registered_review_only_in_its_mode"),
    ("THE_INPUT_NEVER_CHECKS_WHICH_REVIEW_ANSWERS", INPUT,
     "            review = select_registered_review(records=reviews, request=legal_review_request(",
     "            review = reviews[0] if True else select_registered_review(records=reviews, request=legal_review_request(",
     "test_a_position_whose_only_review_is_stale_is_refused_at_input"),
]


def run_one(edits):
    """Run the suite with ``edits`` ({module path: text}); return (failed, fixtures, tests run, rc)."""
    with tempfile.TemporaryDirectory() as tmp:
        for module, text in edits.items():
            target = Path(tmp) / module.name
            target.write_text(text, encoding="utf-8")
            py_compile.compile(str(target), doraise=True)
        code = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r); import vnext; "
                "vnext.__path__.insert(0, %r); sys.argv=['x', *%r]; import unittest; "
                "unittest.main(module=None)") % (str(REPO / "scripts"), str(REPO), tmp, list(SUITES))
        run = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True,
                             timeout=1800)
        lines = [line for line in run.stderr.splitlines() if line.startswith(("FAIL: ", "ERROR: "))]
        fixtures = sorted({line.split("(", 1)[1].rstrip(")") for line in lines
                           if line.split(" ")[1] == "setUpClass"})
        failed = sorted({line.split(" ")[1] for line in lines} - {"setUpClass"})
        ran = [int(line.split()[1]) for line in run.stderr.splitlines() if line.startswith("Ran ")]
        return failed, fixtures, (ran[-1] if ran else 0), run.returncode


def main():
    originals = {module: module.read_text(encoding="utf-8") for module in MODULES}
    control, control_fixtures, control_ran, control_code = run_one({})
    if control or control_fixtures or control_code != 0 or control_ran == 0:
        raise SystemExit("D02_INJECTION_CONTROL_DID_NOT_RUN_CLEAN: failed=%s fixtures=%s ran=%s rc=%s"
                         % (control, control_fixtures, control_ran, control_code))
    results = []
    for name, module, old, new, expected in INJECTIONS:
        text = originals[module]
        if text.count(old) != 1:
            results.append({"injection": name, "result": "EDIT_DOES_NOT_APPLY", "count": text.count(old)})
            continue
        edited = text.replace(old, new)
        try:
            compile(edited, str(module), "exec")
        except SyntaxError as error:
            results.append({"injection": name, "result": "EDIT_DOES_NOT_COMPILE", "error": str(error)})
            continue
        failed, fixtures, ran, _code = run_one({module: edited})
        row = {"injection": name, "module": module.name, "expected": expected, "failed": failed}
        if fixtures:
            row.update(fixtures_failed=fixtures, ran=ran)
        if expected in failed:
            row["result"] = "CAUGHT"
        elif ran != control_ran and not fixtures:
            row["result"] = "SUITE_DID_NOT_RUN"
        elif fixtures:
            row["result"] = "CAUGHT_AT_FIXTURE_ONLY"
        else:
            row["result"] = "CAUGHT_ELSEWHERE" if failed else "MISSED"
        results.append(row)
        print(json.dumps({"injection": name, "result": row["result"]}), flush=True)
    out = {"record_type": "D02_ITEM_8_REVIEW_FAULT_INJECTIONS", "suites": list(SUITES),
           "control_failures": control, "control_tests_run": control_ran,
           "caught": sum(r["result"] == "CAUGHT" for r in results), "total": len(results),
           "results": results, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "fault-injections.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("control_failures", "control_tests_run", "caught", "total")}))
    for module, text in originals.items():
        assert module.read_text(encoding="utf-8") == text
    return 0 if out["caught"] == out["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
