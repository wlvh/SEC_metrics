"""Current CI selectors, retaining the frozen V13 runner byte for byte.

The inherited selector is kept in its original module for historical replay;
this successor runs all its variants separately with the same subprocess
runner, timeout and evidence tier. It never changes the inherited globals.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys
import time

import run_fast_tests as inherited


REPLACED = "tests.vnext.test_financial_balance_scope.FinancialBalanceScopeTest.test_var_reported_estimate_is_distinct_from_an_illustrative_table"
VAR_SELECTORS = tuple("tests.vnext.test_financial_balance_scope.VarReportingFastTest." + name for name in (
    "test_hypothetical_table_is_rejected", "test_illustrative_table_is_rejected",
    "test_unrelated_hypothetical_example_preserves_reported_var"))
FAST_TESTS = tuple(selector for original in inherited.FAST_TESTS
                   for selector in (VAR_SELECTORS if original == REPLACED else (original,))) + (
    "tests.vnext.test_regulatory_investigation_candidates",
    "tests.vnext.test_going_concern_source",
    "tests.vnext.test_fiscal_year_labels",
)
ALL_PREVIOUS_SELECTORS = FAST_TESTS
# These selectors parse complete saved filings, often with several independent
# source variants. They are source-material checks, not 30-second unit checks.
SOURCE_PREFIXES = (
    "tests.vnext.test_financial_candidates.LcrEntityFastTest.",
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.",
    "tests.vnext.test_financial_balance_scope.VarReportingFastTest.",
    "tests.vnext.test_financial_structured.FinancialStructuredTest.",
    "tests.vnext.test_financial_duration",
    "tests.vnext.test_b06_disclosure_v2.",
    "tests.vnext.test_risk_signals",
    "tests.vnext.test_text_results",
    "tests.vnext.test_going_concern_source",
    "tests.vnext.test_fiscal_year_labels",
)
SOURCE_TESTS = tuple(s for s in FAST_TESTS if any(s == p or s.startswith(p) for p in SOURCE_PREFIXES)) + (
    "tests.vnext.test_normal_companyfacts_results",
    "tests.vnext.test_normal_zero_ai_results",
    "tests.vnext.test_normal_accession_results",
    "tests.vnext.test_normal_annual_input_v2",
    "tests.vnext.test_normal_run_inputs",
    "tests.vnext.test_annual_amendment_scope",
    "tests.vnext.test_b06_combined_borrowings",
    "tests.vnext.test_b06_financing_inventory",
    "tests.vnext.test_b06_note_carrying",
    "tests.vnext.test_b06_bond_leases",
    "tests.vnext.test_b06_inclusive_table",
    "tests.vnext.test_b06_current_input",
    "tests.vnext.test_lodging_table_source",
    "tests.vnext.test_normal_source_requirements",
    "tests.vnext.test_instant_balance_amendment",
    "tests.vnext.test_r6_semantic_review",
)
FAST_TESTS = tuple(s for s in FAST_TESTS if s not in SOURCE_TESTS)
FAST_TESTS += ("tests.vnext.test_ordinary_source_session",)
FAST_TESTS += ("tests.vnext.test_ordinary_source_authority",)
SOURCE_TIMEOUT_SECONDS = 240


def _run_source_case(name):
    start = time.monotonic()
    environment = {**os.environ,"PYTHONDONTWRITEBYTECODE":"1"}
    try:
        done = subprocess.run([sys.executable,"-m","unittest","-q",name],cwd=str(inherited.REPO_ROOT),
            env=environment,capture_output=True,encoding="utf-8",timeout=SOURCE_TIMEOUT_SECONDS)
        code,stdout,stderr = done.returncode,done.stdout,done.stderr
    except subprocess.TimeoutExpired as error:
        code,stdout,stderr = 124,error.stdout or "",error.stderr or ""
        stdout = stdout.decode("utf-8",errors="replace") if isinstance(stdout,bytes) else stdout
        stderr = stderr.decode("utf-8",errors="replace") if isinstance(stderr,bytes) else stderr
        stderr += "\nSOURCE_MATERIAL_TIMEOUT_SECONDS="+str(SOURCE_TIMEOUT_SECONDS)
    return {"test":name,"return_code":code,"duration_seconds":round(time.monotonic()-start,3),
            "stdout_tail":stdout[-2000:],"stderr_tail":stderr[-2000:]}


def run_fast_tests(*, jobs, suite="fast"):
    selectors = FAST_TESTS if suite == "fast" else SOURCE_TESTS
    all_selectors = (*FAST_TESTS,*SOURCE_TESTS)
    if jobs < 1 or jobs > len(selectors):
        raise inherited.FastTestError("FAST_TEST_JOBS_INVALID")
    if (inherited.FAST_TESTS.count(REPLACED) != 1 or len(set(all_selectors)) != len(all_selectors)
            or not set(ALL_PREVIOUS_SELECTORS) <= set(all_selectors)):
        raise inherited.FastTestError("FAST_TEST_SUCCESSOR_SELECTOR_CONFLICT")
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [executor.submit(inherited._run_case, test_name=name) if suite == "fast"
                   else executor.submit(_run_source_case,name) for name in selectors]
        rows = sorted((f.result() for f in futures), key=lambda r:r["test"])
    return {"evidence_tier":"FAST_LOCAL_ONLY" if suite == "fast" else "SOURCE_MATERIAL_LOCAL_ONLY",
        "selector_generation":2, "suite":suite, "jobs":jobs,
        "per_case_timeout_seconds":inherited.FAST_TEST_TIMEOUT_SECONDS if suite == "fast" else SOURCE_TIMEOUT_SECONDS,
        "duration_seconds":round(time.monotonic()-start, 3), "tests":rows,
        "status":"PASSED" if all(r["return_code"] == 0 for r in rows) else "FAILED"}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--suite",choices=("fast","source-material"),default="fast")
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps({"suite":args.suite,"tests":FAST_TESTS if args.suite == "fast" else SOURCE_TESTS}, sort_keys=True))
        return 0
    try:
        result = run_fast_tests(jobs=args.jobs,suite=args.suite)
    except inherited.FastTestError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
