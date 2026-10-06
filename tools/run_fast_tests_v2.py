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
FAST_TESTS += ("tests.vnext.test_capacity_reference_contract",)
FAST_TESTS += ("tests.vnext.test_continuous_recovery_110",)
FAST_TESTS += ("tests.vnext.test_continuous_source_unit_bytes",)
FAST_TESTS += ("tests.vnext.test_capacity_visible_source_roles",)
FAST_TESTS += ("tests.vnext.test_continuous_batch33",)
FAST_TESTS += ("tests.vnext.test_capacity_two_stage",)
FAST_TESTS += ("tests.vnext.test_c04_update_cycle.C04UpdateCreditBoundaryTest",)
FAST_TESTS += ("tests.vnext.test_c04_source_only_install.C04MixedSourceScopeFastTest",)
FAST_TESTS += ("tests.vnext.test_c04_source_only_install.C04MissingAnnualBootstrapFastTest",)
FAST_TESTS += ("tests.vnext.test_c04_refresh_resume.C04ResumeBudgetBoundaryTest",)
FAST_TESTS += ("tests.vnext.test_d03_native_preparation.D03NativePreparationTest.test_successor_cannot_drop_original_units_or_required_items",)
FAST_TESTS += ("tests.vnext.test_d03_complete_interpretation.D03CompleteInterpretationTest.test_complete_empty_proposal_never_becomes_negative_result",)
FAST_TESTS += ("tests.vnext.test_d03_complete_interpretation.D03CompleteInterpretationTest.test_recorded_bridge_maps_original_to_effective_ids_without_credit",)
FAST_TESTS += ("tests.vnext.test_ordinary_scalability_audit.OrdinaryScalabilityAuditTest.test_actual_company_and_period_literals_remain_rejected",)
FAST_TESTS += ("tests.vnext.test_ordinary_scalability_audit.OrdinaryScalabilityAuditTest.test_same_line_exemption_does_not_hide_another_literal",)
FAST_TESTS += ("tests.vnext.test_ordinary_scalability_audit.OrdinaryScalabilityAuditTest.test_review_counterexamples_are_reported_without_exact_approval",)
FAST_TESTS += ("tests.vnext.test_ordinary_scalability_audit.OrdinaryScalabilityAuditTest.test_exact_policy_rejects_a_changed_approved_source",)
FAST_TESTS += ("tests.vnext.test_b03_depreciation_scope.B03DepreciationScopeTest",)
FAST_TESTS += ("tests.vnext.test_b03_depreciation_scope_update.B03HistoricalRecoveryVerifierTest",)
FAST_TESTS += ("tests.vnext.test_e01_item_source.E01ItemSourceTest",)
FAST_TESTS += ("tests.vnext.test_normal_b02_paired_measure",)
FAST_TESTS += ("tests.vnext.test_normal_c02_composition.C02CompositionFastTest",)
FAST_TESTS += ("tests.vnext.test_d01_emphasis_successor",)
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
SOURCE_TESTS += ("tests.vnext.test_regulatory_fact_review",)
SOURCE_TESTS += ("tests.vnext.test_c04_registration_successor",)
SOURCE_TESTS += ("tests.vnext.test_capacity_two_stage_material.CapacityTwoStageMaterialTest.test_scoped_interpretation_stops_after_saved_scan",)
SOURCE_TESTS += ("tests.vnext.test_c04_update_cycle.C04UpdateCycleMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_c04_refresh_cycle.C04RefreshCycleMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_c04_source_only_install.C04SourceOnlyInstallTest",)
SOURCE_TESTS += ("tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_d03_recorded_response_store.D03RecordedResponseStoreTest",)
SOURCE_TESTS += ("tests.vnext.test_d03_recorded_response_set.D03RecordedResponseSetTest",)
SOURCE_TESTS += ("tests.vnext.test_ordinary_processing_source.OrdinaryProcessingSourceTest",)
SOURCE_TESTS += ("tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_mixed_old_root_resumes_current_rule_metric_and_c04",)
SOURCE_TESTS += ("tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_failed_processing_copy_preserves_recorded_capture_for_resume",)
# The full class exceeded the 240-second material case limit on 9a6dea27.
# Keep every original test/guard and the same limit, but schedule its three
# independent methods as separate material units. No runner body changes.
SOURCE_TESTS += ("tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest.test_saved_source_recorded_candidate_replays_but_is_not_company_result",)
SOURCE_TESTS += ("tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest.test_unresolved_recorded_group_is_retained_without_company_credit",)
SOURCE_TESTS += ("tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest.test_anchor_candidate_changes_business_digest",)
SOURCE_TESTS += ("tests.vnext.test_d03_native_assessment.D03NativeCollectionMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_ordinary_scalability_audit.OrdinaryScalabilityAuditTest.test_current_exact_reviewed_sources_only_have_no_business_literals",)
SOURCE_TESTS += ("tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_depreciation_scope.B03DepreciationScopeMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_depreciation_scope.B03ImpairmentSourceMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_depreciation_scope_update.B03FordUpdateMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_depreciation_scope_update.B03LegacyRecoveryMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_d03_current_source_replay.D03CurrentSourceReplayTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_exact_impairment_relation.B03ExactImpairmentRelationTest",)
SOURCE_TESTS += ("tests.vnext.test_b03_contract_amortization_scope.B03ContractAmortizationScopeTest",)
SOURCE_TESTS += ("tests.vnext.test_d03_complete_interpretation.D03CompleteInterpretationTest.test_saved_marriott_context_only_stays_unapproved_without_fake_unresolved",)
SOURCE_TESTS += ("tests.vnext.test_normal_c02_composition.C02CompositionMaterialTest",)
SOURCE_TESTS += ("tests.vnext.test_d01_emphasis_material",)
FAST_TESTS += ("tests.vnext.test_a05_formula_successor",)
SOURCE_TESTS += ("tests.vnext.test_a05_formula_material",)
SOURCE_TESTS += ("tests.vnext.test_d02_item8_current_material",)
SOURCE_TESTS += ("tests.vnext.test_ordinary_e01_item_text_input",)
FAST_TESTS += ("tests.vnext.test_c02_auditor_successor.C02AuditorScopeFastTest",)
SOURCE_TESTS += ("tests.vnext.test_c02_auditor_successor.C02AuditorScopeMaterialTest",)
FAST_TESTS += ("tests.vnext.test_e01_header_document_guard.E01HeaderDocumentGuardFastTest",)
SOURCE_TESTS += ("tests.vnext.test_e01_header_document_guard.E01HeaderDocumentGuardMaterialTest",)
FAST_TESTS += ("tests.vnext.test_c02_member_successor.C02MemberScopeFastTest",)
SOURCE_TESTS += ("tests.vnext.test_c02_member_successor.C02MemberScopeMaterialTest",)
FAST_TESTS += ("tests.vnext.test_e01_layout_successor.E01LayoutSuccessorFastTest",)
SOURCE_TESTS += ("tests.vnext.test_e01_layout_successor.E01LayoutSuccessorMaterialTest",)
FAST_TESTS += ("tests.vnext.test_d01_running_header",)
FAST_TESTS += ("tests.vnext.test_c02_model_processing",)
FAST_TESTS += ("tests.vnext.test_c02_model_review_view",)
FAST_TESTS += ("tests.vnext.test_d03_model_processing",)
FAST_TESTS += ("tests.vnext.test_d03_model_review_cli",)
FAST_TESTS += ("tests.vnext.test_d03_context_requests",)
FAST_TESTS += ("tests.vnext.test_c02_table_development_input",)
FAST_TESTS += ("tests.vnext.test_c02_table_model_processing",)
FAST_TESTS += ("tests.vnext.test_c02_image_model_processing",)
FAST_TESTS += ("tests.vnext.test_company_c02_development",)
SOURCE_TIMEOUT_SECONDS = 240
SOURCE_TIMEOUT_OVERRIDES = {
    # The unchanged full original-source module passed on head 698b9a45 in
    # 226.062s, then alone reached 240.117s/rc124 on c3cda0b1. Both original
    # test classes pass separately without assertion changes; keep the same
    # selector and job deadline while allowing a measured 60-second margin.
    "tests.vnext.test_normal_zero_ai_results": 300,
    # This single case includes acquisition, native installation and cold replay.
    "tests.vnext.test_continuous_sec_acquisition": 480,
    # One complete C04 source refresh passed locally in 227.794s; the prior
    # two-version CI case hit 240s. Keep the job deadline unchanged.
    "tests.vnext.test_c04_refresh_cycle.C04RefreshCycleMaterialTest": 300,
    # The saved JPM D03 packet passed on the prior runner in 227.163s but
    # reached the 240s per-case bound while two complete CI shards ran.
    "tests.vnext.test_d03_recorded_response_store.D03RecordedResponseStoreTest": 300,
    # One C04 test runs an initial source capture and a separately authenticated
    # continuation plus three rejection branches. The same unchanged entry
    # passed locally in 119.135s and CI at 163.194s, then twice hit 240s under
    # concurrent source-shard load without a business assertion failure.
    "tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest": 360,
    # D03 full-set storage passed prior head b686 shard1 in 216.596s, then
    # hit this head's 240.107s limit under a new concurrent source shard.
    "tests.vnext.test_d03_recorded_response_set.D03RecordedResponseSetTest": 300,
    # Head 5e2a5ca9 shard1 ended the normal two-capture mixed-source case at
    # its 240.106s limit; the local two-case run passed in 377.591s.
    "tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_mixed_old_root_resumes_current_rule_metric_and_c04": 480,
    # Head 5e2a5ca9 shard0 ended this exact two-capture recovery case at the
    # 240.105s per-case limit (rc124); the local two-case run passed in
    # 377.591s. Keep the rest of the source suite and job deadline unchanged.
    "tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_failed_processing_copy_preserves_recorded_capture_for_resume": 480,
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


def _selected_tests(suite, shard_index, shard_count):
    if (shard_count < 1 or shard_index < 0 or shard_index >= shard_count
            or (suite != "source-material" and (shard_index, shard_count) != (0, 1))):
        raise inherited.FastTestError("FAST_TEST_SHARD_INVALID")
    complete = FAST_TESTS if suite == "fast" else SOURCE_TESTS
    return tuple(name for index, name in enumerate(complete) if index % shard_count == shard_index)


def run_fast_tests(*, jobs, suite="fast", shard_index=0, shard_count=1):
    selectors = _selected_tests(suite, shard_index, shard_count)
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
        **({"shard_index":shard_index,"shard_count":shard_count} if shard_count > 1 else {}),
        "per_case_timeout_seconds":inherited.FAST_TEST_TIMEOUT_SECONDS if suite == "fast" else SOURCE_TIMEOUT_SECONDS,
        **({"per_case_timeout_overrides":SOURCE_TIMEOUT_OVERRIDES} if suite != "fast" else {}),
        "duration_seconds":round(time.monotonic()-start, 3), "tests":rows,
        "status":"PASSED" if all(r["return_code"] == 0 for r in rows) else "FAILED"}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--suite",choices=("fast","source-material"),default="fast")
    parser.add_argument("--shard-index",type=int,default=0)
    parser.add_argument("--shard-count",type=int,default=1)
    args = parser.parse_args(argv)
    try:
        if args.list:
            selectors = _selected_tests(args.suite,args.shard_index,args.shard_count)
            print(json.dumps({"suite":args.suite,"tests":selectors}, sort_keys=True))
            return 0
        result = run_fast_tests(jobs=args.jobs,suite=args.suite,
                                shard_index=args.shard_index,shard_count=args.shard_count)
    except inherited.FastTestError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
