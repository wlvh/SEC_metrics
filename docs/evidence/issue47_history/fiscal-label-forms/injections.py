#!/usr/bin/env python3
"""Fault injections for the widened fiscal-year definition forms: each must be caught by its case.

Same rules as ``../acquisition-wiring/resume_injections.py``: an edit that does
not apply exactly once or does not compile stops the script, the file is
restored byte for byte and checked, every run reads and writes bytecode only
in a fresh directory, and the control run must pass first.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/fiscal-label-forms/injections.py
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
MODULE = "tests.vnext.test_historical_fiscal_labels"
SUCCESSOR = "scripts/vnext/historical_fiscal_labels.py"
ANNUAL = "scripts/vnext/historical_annual_input.py"
REAL = MODULE + ".OlderAnnualReportsDefineTheirYearsInTwoMoreForms"
ONLY = MODULE + ".OnlyAnUnresolvedPeriodIsReadAgain"
NARROW = MODULE + ".TheWidenedFormsAreNarrow"
INJECTIONS = [
    {"id": "EVERY_PERIOD_IS_READ_AGAIN", "file": SUCCESSOR,
     "old": ("    if inspected[\"status\"] != UNRESOLVED:\n        return inspected\n"
             "    _need(sha256_bytes("),
     "new": "    _need(sha256_bytes(",
     "expect": ONLY + ".test_a_resolved_period_is_the_frozen_inspection_itself",
     "edit": "widen_inspection() reads a period the frozen scan resolved",
     "why": "a resolved period's inspection, and so its input identity, would move"},
    {"id": "ANY_CLAUSE_AFTER_RESPECTIVELY", "file": SUCCESSOR,
     "old": "_WEEKS_END = r\"respectively(?:,\\s+and\\s+included\\s+5[23]\\s+weeks)?\\.\"",
     "new": "_WEEKS_END = r\"respectively(?:,[^.]*)?\\.\"",
     "expect": NARROW + ".test_another_clause_after_respectively_still_stops_the_period",
     "edit": "the ordered form accepts any clause after 'respectively'",
     "why": "a clause that changes the mapping would be read as if it were the week count"},
    {"id": "ANY_ALIAS_IS_THE_REGISTRANT", "file": SUCCESSOR,
     "old": ("    if _frozen_labels._issuer_alias_prefix(prefix, names):\n        return True\n"),
     "new": "    return True\n",
     "expect": NARROW + ".test_an_alias_naming_another_entity_still_stops_the_period",
     "edit": "the reference form's alias proof accepts any name",
     "why": "another entity's fiscal years would label the registrant's"},
    {"id": "LEGAL_FORMS_DROPPED_ANYWHERE", "file": SUCCESSOR,
     "old": ("        while len(tokens) > 1 and tokens[-1] in _LEGAL_FORMS:\n"
             "            tokens.pop()\n"
             "            forms.add(\" \".join(tokens))\n"),
     "new": "        forms.add(\" \".join(t for t in tokens if t not in _LEGAL_FORMS))\n",
     "expect": NARROW + ".test_a_legal_form_is_dropped_only_from_the_end_of_the_name",
     "edit": "legal-form words are removed from anywhere in the name",
     "why": "'Company Stores' would become 'stores', a different name"},
    {"id": "AN_OPEN_CURRENT_LEAD_IS_IGNORED", "file": SUCCESSOR,
     "old": "    if len(labels) > 1 or current:\n",
     "new": "    if len(labels) > 1:\n",
     "expect": REAL + ".test_the_frozen_rule_is_what_decides",
     "edit": "the rule ignores a definition-like sentence it could not read",
     "why": "a period whose definition is unread would take a label anyway"},
    {"id": "A_FROZEN_DEFINITION_MAY_CHANGE", "file": SUCCESSOR,
     "old": ("    _need(all(item in definitions for item in frozen_definitions),\n"
             "          \"HISTORICAL_FISCAL_WIDENED_SCAN_CHANGED_A_FROZEN_DEFINITION\")\n"),
     "new": "",
     "expect": NARROW + ".test_a_widened_scan_that_changes_a_frozen_definition_is_refused",
     "edit": "widen_inspection() accepts a widened scan that lost a frozen definition",
     "why": "the widened reading would replace what the frozen scan read instead of adding to it"},
    {"id": "A_NEW_LEAD_MAY_APPEAR", "file": SUCCESSOR,
     "old": ("    _need(all(lead in inspected[\"unsupported_definition_leads\"] for lead in unparsed),\n"
             "          \"HISTORICAL_FISCAL_WIDENED_SCAN_LEFT_A_NEW_LEAD\")\n"),
     "new": "",
     "expect": NARROW + ".test_a_widened_scan_that_leaves_a_new_lead_is_refused",
     "edit": "widen_inspection() accepts a widened scan that left a lead the frozen one did not",
     "why": "the widened recognizers would have misread a sentence the frozen scan read"},
    {"id": "OTHER_BYTES_ARE_READ", "file": SUCCESSOR,
     "old": ("    _need(sha256_bytes(content=primary_bytes) == inspected[\"primary_sha256\"],\n"
             "          \"HISTORICAL_FISCAL_PRIMARY_BYTES_ARE_NOT_THE_INSPECTED_ONES\")\n"),
     "new": "",
     "expect": REAL + ".test_the_bytes_must_be_the_inspected_ones",
     "edit": "widen_inspection() reads bytes other than the inspected document",
     "why": "a label could come from a document the inspection never bound"},
    {"id": "THE_FROZEN_FORM_IS_NOT_CHECKED", "file": SUCCESSOR,
     "old": ("    _need(frozen.pattern.count(_FROZEN_END) == 1 and frozen.pattern.endswith(_FROZEN_END),\n"
             "          \"HISTORICAL_FISCAL_FROZEN_ORDERED_FORM_CHANGED\")\n"),
     "new": "",
     "expect": NARROW + ".test_the_frozen_ordered_form_must_still_end_where_it_did",
     "edit": "_ordered_pattern() widens whatever the frozen pattern is",
     "why": "a changed frozen pattern would be cut at the wrong place and still used"},
    {"id": "THE_ROUTE_KEEPS_THE_FROZEN_INSPECTION", "file": ANNUAL,
     "old": ("from .historical_dei import annual_period\n"
             "from .historical_fiscal_labels import inspect_prepared_fiscal_year_labels\n"),
     "new": "from .historical_dei import annual_period, inspect_prepared_fiscal_year_labels\n",
     "expect": ONLY + ".test_the_pinned_input_reads_its_label_here",
     "edit": "the pinned annual input keeps the DEI view's inspection",
     "why": "the repair would exist and no Run would use it"},
]


def _isolated_env():
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPATH": str(REPO / "scripts"), "PYTHONPYCACHEPREFIX": cache}


def _failed_cases(output):
    return set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", output, re.M))


def _run(selector):
    started = time.time()
    run = subprocess.run([sys.executable, "-m", "unittest", selector], cwd=REPO,
                         env=_isolated_env(), capture_output=True, text=True, timeout=3600)
    return run, int(time.time() - started)


def main():
    control, seconds = _run(MODULE)
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
        results.append({"id": injection["id"], "file": injection["file"],
                        "edit": injection["edit"], "why_it_matters": injection["why"],
                        "outcome": "CAUGHT" if caught else "NOT_CAUGHT",
                        "expected_case": expected, "failed_cases": failed,
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s", flush=True)
    out = Path(__file__).with_name("injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_FISCAL_LABEL_FORM_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
