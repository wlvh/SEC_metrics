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
    # Measured at 29.9 seconds standalone against the 30-second fast cap, so it
    # fails under --jobs contention and passes alone. The fast tier's timeout
    # comes from the frozen inherited entry and cannot be raised for one case;
    # this selector reads complete saved qualification material, which is what
    # the source tier is for.
    "tests.vnext.test_table_context_qualification_guard.",
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
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_changed_debt_or_equity_outside_the_purpose_note_is_rejected",
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_changed_declared_amendment_purpose_and_new_native_debt_cannot_pass",
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_current_run_input_retains_the_actual_amendment_without_creating_debt",
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_real_effect_is_separate_from_debt_completeness_and_the_old_balance_policy",
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_source_relationship_failure_remains_a_withheld_result",
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_unproven_amendment_does_not_enter_even_the_equity_guard",
    "tests.vnext.test_lodging_table_source",
    "tests.vnext.test_normal_source_requirements",
    "tests.vnext.test_instant_balance_amendment",
    "tests.vnext.test_r6_semantic_review",
)
FAST_TESTS = tuple(s for s in FAST_TESTS if s not in SOURCE_TESTS)
FAST_TESTS += ("tests.vnext.test_ordinary_source_session",)
FAST_TESTS += ("tests.vnext.test_ordinary_source_authority",)
FAST_TESTS += ("tests.vnext.test_continuous_call_ledger",)
FAST_TESTS += ("tests.vnext.test_continuous_call_policy",)
FAST_TESTS += ("tests.vnext.test_capacity_utilization_source.CapacityComparisonTest",)
FAST_TESTS += ("tests.vnext.test_ordinary_storage_identity",)
FAST_TESTS += ("tests.vnext.test_r6_semantic_scope",)
FAST_TESTS += ("tests.vnext.test_regulatory_statement_facts.RegulatoryStatementFactsTest",)
FAST_TESTS += ("tests.vnext.test_capacity_semantic_source.CapacitySemanticSourceTest",)
FAST_TESTS += ("tests.vnext.test_capacity_semantic_review.CapacitySemanticReviewTest",)
FAST_TESTS += ("tests.vnext.test_capacity_applicability.CapacityApplicabilityTest",)
FAST_TESTS += ("tests.vnext.test_d04_native_assessment",)
FAST_TESTS += ("tests.vnext.test_native_request_variants",)
FAST_TESTS += ("tests.vnext.test_native_unit_index",)
FAST_TESTS += ("tests.vnext.test_source_input_rule_roles",)
FAST_TESTS += ("tests.vnext.test_prior_html_dependency",)
FAST_TESTS += ("tests.vnext.test_registration_event_discovery",)
FAST_TESTS += ("tests.vnext.test_registered_native_update.RegisteredNativeUpdateTest",)
FAST_TESTS += ("tests.vnext.test_native_source_runtime_policy",)
FAST_TESTS += ("tests.vnext.test_native_refresh_execution",)
FAST_TESTS += ("tests.vnext.test_native_request_construction",)
FAST_TESTS += ("tests.vnext.test_ordinary_isolated_publication.OrdinaryIsolatedPublicationBoundaryTest",)
FAST_TESTS += ("tests.vnext.test_continuous_request_context",)
FAST_TESTS += ("tests.vnext.test_capacity_quantity_scope",)
FAST_TESTS += ("tests.vnext.test_capacity_quantity_roles",)
FAST_TESTS += ("tests.vnext.test_capacity_program_roles",)
FAST_TESTS += ("tests.vnext.test_semantic_source_grouping.SemanticSourceGroupingTest",)
SOURCE_TESTS += ("tests.vnext.test_continuous_semantic_calls",)
SOURCE_TESTS += ("tests.vnext.test_r6_regulatory_semantics",)
SOURCE_TESTS += ("tests.vnext.test_r6_semantic_verification",)
SOURCE_TESTS += ("tests.vnext.test_r6_historical_controls",)
SOURCE_TESTS += ("tests.vnext.test_capacity_utilization_source.CapacitySourceMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_capacity_semantic_source.CapacityCompleteSourceMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_regulatory_statement_facts.RegulatoryStatementSourceMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_continuous_sec_acquisition",)
SOURCE_TESTS += ("tests.vnext.test_ordinary_special_debt_scope",)
SOURCE_TESTS += ("tests.vnext.test_ordinary_income_input",)
SOURCE_TESTS += ("tests.vnext.test_capacity_semantic_review.CapacitySemanticReviewMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_semantic_source_grouping.SemanticSourceGroupingMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_capacity_native_assessment",)
SOURCE_TESTS += ("tests.vnext.test_capacity_text_results",)
SOURCE_TESTS += ("tests.vnext.test_capacity_applicability.CapacityApplicabilityMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_d04_native_wiring",)
SOURCE_TESTS += ("tests.vnext.test_native_assessment_replay",)
# Issue #47 historical period selection and its catalog resolution read real
# saved originals, so they belong to the saved-source tier, not the 30s tier.
SOURCE_TESTS += ("tests.vnext.test_normal_history_catalog",)
SOURCE_TESTS += ("tests.vnext.test_historical_period_results",)
SOURCE_TESTS += ("tests.vnext.test_historical_coverage",)
# Issue #47's acquisition chain installs the saved corpus and drives real
# attempt and checkpoint primitives over recorded responses, so it reads
# saved sources; it opens no socket, asserted by counting connects.
SOURCE_TESTS += ("tests.vnext.test_historical_sec_session",)
# A D02 Result held another item's text, passed every check and was published as
# EXACT. This is the boundary that ends it and the control cases that stop the
# boundary from cutting an item's own body, so it reads two filings in full.
SOURCE_TESTS += ("tests.vnext.test_historical_text_boundary",)
# Identity isolation, object isolation and scope leakage for the shared parse.
# It reads two filings in full; 43 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_shared_sources",)
# Which submissions blocks a pinned period may be read from. It reads six
# companies' saved submissions indexes and shards and no filing bodies; 10
# seconds measured. Registered because its positive cases and its negative
# cases are the same comparison run against two implementations, so a change
# that quietly re-narrows the view fails here rather than in a batch.
SOURCE_TESTS += ("tests.vnext.test_historical_metadata_context",)
# The event window a successor registrant measures, and the Run coordinate it
# is not. It reads two companies' saved submissions and resolves C01 through
# both the historical and the ordinary route so they can be compared; 62
# seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_event_window",)
# Structural non-applicability: it prepares two companies' annual inputs from
# saved originals; 38 seconds measured. Its load-bearing case is a refusal -
# a route that answered "not applicable" whenever asked would pass every
# positive case here and be wrong about Marriott's occupancy.
SOURCE_TESTS += ("tests.vnext.test_historical_structural_results",)
# Issue #47's own dependency gate. It reads saved submissions metadata for two
# companies and makes no request; 19 seconds measured. Registered because the
# load-bearing case asks the old gate and the new one the same question, so a
# gate that accepted everything fails here rather than in a fetch.
SOURCE_TESTS += ("tests.vnext.test_historical_source_acquisition",)
# The pinned governance selection C04 will read. It asks the frozen selector
# and the successor the same question about the same period with the same
# blocks, so a successor that merely returned something fails there; 26 seconds
# measured. Registered before the route is wired, because the selection is what
# the route will rest on.
SOURCE_TESTS += ("tests.vnext.test_historical_governance_input",)
# C04 through the pinned route. Its load-bearing case answers one company for
# two periods and requires two different answers, so a route that ignored the
# period fails there rather than in a batch.
SOURCE_TESTS += ("tests.vnext.test_historical_governance_results",)
# B06 through the pinned cascade. Its load-bearing case runs both chains - the
# ordinary one and this copy - for four companies and requires them to agree
# field for field; a copy checked against itself could not find a
# transcription error, so this is the only place one shows up.
SOURCE_TESTS += ("tests.vnext.test_historical_debt_results",)
# This one reads no source material at all - it hashes the nineteen rule files the
# issue_47_v1 snapshot records - so it belongs in the 30s tier. It is registered
# because the snapshot has already drifted twice behind a rule-file change, and
# a README asking the author to run --check did not stop either one.
FAST_TESTS += ("tests.vnext.test_historical_requirement_snapshot",)
# Parses three files and compares conditions; it reads no source material.
# It exists because an unreachable dispatch branch changes no behaviour, so
# no Run can fail on it - one shipped and a complete end-to-end Run passed.
FAST_TESTS += ("tests.vnext.test_requirement_dispatch_map",)
# The D02 Spec revision compiles above the frozen compiler's declared ceiling,
# which fourteen Requirement generations bind by bytes. It reads two Spec files
# and no source material; 0.02 seconds measured. Registered because the guard
# that matters is a comparison, and a comparison that silently stops comparing
# looks exactly like one that passes.
FAST_TESTS += ("tests.vnext.test_historical_spec_revision",)
# The successor text protocol, checked differentially against the frozen one:
# 26 mutations inside the old bound must give the same value or the same error
# message, and every item-level mutation runs again at index 80. No source
# material; 0.9 seconds measured.
FAST_TESTS += ("tests.vnext.test_historical_text_protocol",)
# The same capacity through the production entry points. It skips without the
# registration patch, which is not a pass - it is registered so that a run
# declaring the patch applied shows the skip rather than hiding it.
FAST_TESTS += ("tests.vnext.test_historical_protocol_wiring",)
# Splitting the saved-source tier must be a partition. A split that dropped a
# case or ran one twice would still look green, so the exactness, the balance
# and the determinism are checked here. No source material; 0.004 seconds.
FAST_TESTS += ("tests.vnext.test_source_tier_shard",)
SOURCE_TIMEOUT_SECONDS = 240
SOURCE_TIMEOUT_OVERRIDES = {
    # This single case includes acquisition, native installation and cold replay.
    "tests.vnext.test_continuous_sec_acquisition": 480,
    # Nine cases over six filings' full 10-K bytes; measured at 192 seconds,
    # which is close enough to the 240 default to fail on a slower runner.
    "tests.vnext.test_historical_text_boundary": 480,
    # Ten cases over the ordinary zero-AI routes, including the registered
    # event union across two CIKs. Measured at 258 seconds alone - over the
    # default, not near it - so it was timing out rather than flaking, and a
    # timeout reads as a failure with no diagnosis at all.
    "tests.vnext.test_normal_zero_ai_results": 600,
    # Six cases, two of which run both B06 chains over four companies' full
    # 10-K bytes - eight complete resolutions, plus a fifth company's Run
    # input. Measured alone before registering it.
    "tests.vnext.test_historical_debt_results": 900,
    # 42 cases at 144 seconds measured together. The earlier 900 was sized for
    # five cases that asked the routes themselves - 343 seconds of route
    # preparation per position - and those are gone: the report no longer runs
    # a route, so the cases now assert that it does not. 144 against the 240
    # default is the same margin that was judged too thin above, so this keeps
    # an override, at the size the current cases actually need.
    "tests.vnext.test_historical_coverage": 480,
    # 91 cases at 379 seconds measured together. The refresh chain runs a whole acquisition - install, capture,
    # checkpoint, installation, and three plans of a company with sixty-nine
    # declared shards - once for its class and once more for the case that
    # re-captures unchanged bytes, which is the case that makes the rest mean
    # anything. Each company's declaration is still built once per process and
    # deep-copied to the cases that read it. This module is the one whose
    # timeout would read as "the acquisition chain broke".
    "tests.vnext.test_historical_sec_session": 900,
}


def _run_source_case(name):
    start = time.monotonic()
    timeout = SOURCE_TIMEOUT_OVERRIDES.get(name, SOURCE_TIMEOUT_SECONDS)
    environment = {**os.environ,"PYTHONDONTWRITEBYTECODE":"1"}
    try:
        done = subprocess.run([sys.executable,"-m","unittest","-q",name],cwd=str(inherited.REPO_ROOT),
            env=environment,capture_output=True,encoding="utf-8",timeout=timeout)
        code,stdout,stderr = done.returncode,done.stdout,done.stderr
    except subprocess.TimeoutExpired as error:
        code,stdout,stderr = 124,error.stdout or "",error.stderr or ""
        stdout = stdout.decode("utf-8",errors="replace") if isinstance(stdout,bytes) else stdout
        stderr = stderr.decode("utf-8",errors="replace") if isinstance(stderr,bytes) else stderr
        stderr += "\nSOURCE_MATERIAL_TIMEOUT_SECONDS="+str(timeout)
    return {"test":name,"return_code":code,"duration_seconds":round(time.monotonic()-start,3),
            "timeout_seconds":timeout,
            "stdout_tail":stdout[-2000:],"stderr_tail":stderr[-2000:]}


def source_shard(*, shard, shards):
    """One part of the source tier, balanced by each case's own time budget.

    The saved-source job reached its thirty-five minute cap and was cancelled
    mid-step, which reads as "cancelled" rather than as a failing assertion.
    Splitting it needs a partition that is exact and does not depend on how the
    list happens to be ordered, and dealing the cases round-robin would put the
    three long ones together whenever their positions line up.

    So the weight is each case's own timeout - the number this file already
    keeps for how long a case may take - and the heaviest case goes to the
    lightest shard. The result is a partition: every case in exactly one shard,
    and the same shard every time.
    """
    if shards < 1 or not 1 <= shard <= shards:
        raise inherited.FastTestError("SOURCE_SHARD_INVALID")
    weighed = sorted(SOURCE_TESTS,
                     key=lambda name: (-SOURCE_TIMEOUT_OVERRIDES.get(name,
                                                                     SOURCE_TIMEOUT_SECONDS),
                                       name))
    buckets = [[] for _ in range(shards)]
    budgets = [0] * shards
    for name in weighed:
        lightest = min(range(shards), key=lambda index: (budgets[index], index))
        buckets[lightest].append(name)
        budgets[lightest] += SOURCE_TIMEOUT_OVERRIDES.get(name, SOURCE_TIMEOUT_SECONDS)
    return tuple(sorted(buckets[shard - 1]))


def run_fast_tests(*, jobs, suite="fast", shard=None, shards=None):
    if suite == "fast":
        selectors = FAST_TESTS
    elif shard is None:
        selectors = SOURCE_TESTS
    else:
        selectors = source_shard(shard=shard, shards=shards)
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
        # A sharded run covers part of the tier. Saying which part is the
        # difference between evidence about a shard and a claim about the tier.
        **({"shard":shard,"shards":shards,"tier_case_count":len(SOURCE_TESTS)}
           if shard is not None else {}),
        "per_case_timeout_seconds":inherited.FAST_TEST_TIMEOUT_SECONDS if suite == "fast" else SOURCE_TIMEOUT_SECONDS,
        **({"per_case_timeout_overrides":SOURCE_TIMEOUT_OVERRIDES} if suite != "fast" else {}),
        "duration_seconds":round(time.monotonic()-start, 3), "tests":rows,
        "status":"PASSED" if all(r["return_code"] == 0 for r in rows) else "FAILED"}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--suite",choices=("fast","source-material"),default="fast")
    parser.add_argument("--shard",help="i/n - run part i of n of the source tier")
    args = parser.parse_args(argv)
    shard = shards = None
    if args.shard is not None:
        if args.suite != "source-material" or args.shard.count("/") != 1:
            parser.error("--shard is i/n and belongs to --suite source-material")
        part, _, total = args.shard.partition("/")
        if not part.isdigit() or not total.isdigit():
            parser.error("--shard is i/n with whole numbers")
        shard, shards = int(part), int(total)
    if args.list:
        listed = (FAST_TESTS if args.suite == "fast"
                  else SOURCE_TESTS if shard is None
                  else source_shard(shard=shard, shards=shards))
        print(json.dumps({"suite":args.suite,"tests":listed}, sort_keys=True))
        return 0
    try:
        result = run_fast_tests(jobs=args.jobs,suite=args.suite,shard=shard,shards=shards)
    except inherited.FastTestError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
