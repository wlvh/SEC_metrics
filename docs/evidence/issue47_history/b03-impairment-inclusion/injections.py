#!/usr/bin/env python3
"""Fault injections for B03's two scope withholds: each must be caught by the case written for it.

The historical route asks a kept or retaken direct D&A total whether the filing
itself says it includes impairment-related depreciation
(``historical_zero_ai_results.impairment_included``). Each injection undoes
one part of that; the case named for it must fail. An edit that does not apply
exactly once or does not compile stops the script, the file is restored byte
for byte and checked, and every run reads and writes bytecode only in a fresh
directory. The control run must pass first.

Zero SEC or provider calls. Run from the repository root:
    python3 docs/evidence/issue47_history/b03-impairment-inclusion/injections.py
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
MODULE = "tests.vnext.test_historical_da_scope_route"
ROUTE = "scripts/vnext/historical_zero_ai_results.py"
FORD = MODULE + ".AKeptTotalTheFilingSaysIncludesImpairment"
MARRIOTT = MODULE + ".AComposedTotalBesideAContractCostAmortization"
INJECTIONS = [
    {"id": "THE_KEPT_TOTAL_IS_NOT_ASKED", "file": ROUTE,
     "old": "    included = impairment_included(raw_bytes=raw_bytes, period=period, observation=direct[0])\n",
     "new": "    included = None\n",
     "expect": FORD + ".test_it_is_withheld_by_name_and_still_carries_b01",
     "edit": "depreciation_scope() never asks a kept direct total about impairment",
     "why": "the total the filing says includes impairment-related depreciation would be published"},
    {"id": "EVERY_KEPT_TOTAL_IS_WITHHELD", "file": ROUTE,
     "old": ("    if included is not None:\n"
             "        return {**body, \"status\": \"WITHHOLD\", \"impairment_inclusion\": included,\n"),
     "new": ("    if True:\n"
             "        return {**body, \"status\": \"WITHHOLD\", \"impairment_inclusion\": included,\n"),
     "expect": MODULE + ".OnSavedFilings.test_where_the_filing_proves_the_input_the_result_is_the_chain_s",
     "edit": "depreciation_scope() withholds every kept direct total, footnoted or not",
     "why": "a total the filing does not footnote would be lost for nothing"},
    {"id": "THE_RETAKEN_TOTAL_IS_NOT_ASKED", "file": ROUTE,
     "old": ("                if included is not None:\n"
             "                    raise _DepreciationScopeUnproven({\n"),
     "new": ("                if False:\n"
             "                    raise _DepreciationScopeUnproven({\n"),
     "expect": FORD + ".test_a_retaken_total_is_asked_too",
     "edit": "the route publishes a retaken total without asking it about impairment",
     "why": "the same footnoted total would pass through the retake branch"},
    {"id": "ANOTHER_PERIOD_S_FACT_IS_ASKED", "file": ROUTE,
     "old": ("        if (context[\"period_start\"] != period[\"period_start\"]\n"
             "                or context[\"period_end\"] != period[\"period_end\"]\n"
             "                or context[\"typed_dimension_count\"] or context[\"dimensions\"]\n"
             "                or str(int(context[\"entity_identifier\"])) != str(int(binding[\"entity\"]))):\n"),
     "new": ("        if (context[\"typed_dimension_count\"] or context[\"dimensions\"]\n"
             "                or str(int(context[\"entity_identifier\"])) != str(int(binding[\"entity\"]))):\n"),
     "expect": FORD + ".test_the_proof_is_the_measured_period_s_fact",
     "edit": "impairment_included() takes a fact of any period that carries the value",
     "why": "a year's total would be withheld for a footnote written about another year"},
    # #28's contract-cost amortization question, asked of a kept composition.
    {"id": "THE_COMPOSITION_IS_NOT_ASKED", "file": ROUTE,
     "old": ("            if da_scope[\"status\"] == \"KEEP\":\n"
             "                unreconciled = contract_amortization_unreconciled(\n"),
     "new": ("            if False:\n"
             "                unreconciled = contract_amortization_unreconciled(\n"),
     "expect": MARRIOTT + ".test_it_is_withheld_by_name_and_still_carries_b01",
     "edit": "the route publishes a kept composition without asking #28's question",
     "why": "a D&A the filing shows is not the whole of it would be published"},
    {"id": "EVERY_KEPT_RESULT_IS_WITHHELD", "file": ROUTE,
     "old": ("                if unreconciled is not None:\n"
             "                    raise _DepreciationScopeUnproven({\n"),
     "new": ("                if True:\n"
             "                    raise _DepreciationScopeUnproven({\n"),
     "expect": MARRIOTT + ".test_a_direct_total_is_not_its_question",
     "edit": "the route withholds every kept B03, whatever #28's check answers",
     "why": "a direct total the question does not concern would be lost for nothing"},
    {"id": "THE_ANSWER_IS_NOT_CARRIED", "file": ROUTE,
     "old": "\"status\": \"WITHHOLD\", \"contract_amortization\": unreconciled,",
     "new": "\"status\": \"WITHHOLD\",",
     "expect": MARRIOTT + ".test_it_is_the_answer_of_28_s_own_check",
     "edit": "the withheld result drops #28's answer",
     "why": "the reader could not see which amortization, amount and fact withheld it"},
]


def _isolated_env():
    """Bytecode read and written only in a fresh directory."""
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
                        "expected_case": injection["expect"], "failed_cases": failed,
                        "suite_result": " ".join(summary), "seconds": seconds})
        print(injection["id"], results[-1]["outcome"], failed, seconds, "s", flush=True)
    out = Path(__file__).with_name("injections.json")
    out.write_text(json.dumps({"record_type": "ISSUE_47_B03_IMPAIRMENT_INCLUSION_FAULT_INJECTIONS",
                               "results": results, "calls": [0, 0, 0]},
                              indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(item["outcome"] == "CAUGHT" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
