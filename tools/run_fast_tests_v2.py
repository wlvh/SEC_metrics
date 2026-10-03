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
# The successor mechanism and its forms on constructed documents; under a second.
FAST_TESTS += ("tests.vnext.test_historical_financial_wording",)
# D02's Item 8 category-mention rule against the thirty older-year readings'
# judged texts and constructed paragraphs; well under a second.
FAST_TESTS += ("tests.vnext.test_d02_item_8_category_mentions",)
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
# Issue #47 historical period selection and its catalog resolution read real
# saved originals, so they belong to the saved-source tier, not the 30s tier.
SOURCE_TESTS += ("tests.vnext.test_normal_history_catalog",)
SOURCE_TESTS += ("tests.vnext.test_historical_period_results",)
SOURCE_TESTS += ("tests.vnext.test_historical_coverage",)
SOURCE_TESTS += ("tests.vnext.test_historical_governance_text",)
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
# B06's disclosure resolver on older layouts: the two forms the frozen inventory
# leaves unresolved, on Southwest's FY2022 report (answered) and on reports the
# frozen resolver answers (identical), read from the checkout and the export.
# 48 seconds measured beside a batch.
SOURCE_TESTS += ("tests.vnext.test_historical_debt_fallback_forms",)
# B10 and B11 through the pinned route. Two cases carry it: one answers the
# current period and requires seventeen observation-binding fields to match the
# ordinary route's, and one answers Marriott for three years and requires three
# different values in each metric - a route that read the newest filing would
# satisfy everything else in that file.
SOURCE_TESTS += ("tests.vnext.test_historical_lodging_results",)
# D01 through the pinned route. Two cases carry it: one compares the whole
# candidate record - each heading's exact text and raw byte span - against the
# ordinary chain's for two companies at opposite ends of the heading range, and
# one answers Marriott for three years and requires three different candidates,
# so a route reading the newest filing satisfies everything else in the file
# and fails there. Two further classes hold the underline successor to the
# frozen parser it restates - identical blocks with underline switched off,
# and never a cleared emphasis with it on. 187 seconds measured, which is why
# it carries an override rather than the 240 default.
SOURCE_TESTS += ("tests.vnext.test_historical_risk_headings",)
# The D01 reading that grants acceptances, run on the filings each of its steps
# exists for, plus the reader's own lines reproducing every accepted published
# value's digest from the filing alone. It reads seven full 10-Ks; 5 seconds
# measured.
SOURCE_TESTS += ("tests.vnext.test_d01_byte_reading",)
SOURCE_TESTS += ("tests.vnext.test_historical_page_split_headings",)
# D01's running header naming two parts (JPMorgan's "Parts I and II"): both
# selectors on the same rebuilt document of three saved reports - one line
# apart where the page closes Item 1A, none where it does not - and the
# constructed edges of the added form. 67 seconds measured beside a batch.
SOURCE_TESTS += ("tests.vnext.test_historical_running_header",)
# Three D02 marks the frozen parse cannot see - Enphase's page-numbered footer,
# Lumen's underlined case label and Paramount's italic matter labels - each on
# its filing against a control with the rule off, with D03 required not to
# move, plus the constructed edges the filings do not reach. It reads four
# full 10-Ks; 162 seconds measured under a running batch.
SOURCE_TESTS += ("tests.vnext.test_historical_d02_marks",)
# B13 where the approved definition leaves the company out. Its load-bearing
# case holds this route's answer to the ordinary route's, field for field and
# down to the result identifier, for three companies of three shapes - the two
# read the scope from different places, and this is where they would disagree.
# It prepares five periods' annual inputs; 24 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_capacity_results",)
# Registered predecessor years (Issue #47 section 7.3): the window crossing to
# the predecessor only where the successor filed nothing, each year read from
# its own registrant's filing, and every submissions block the re-derivation
# reads admitted as an input. It reads both registrants' catalogs and two
# years of annual reports; 75 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_predecessor_periods",)
# E01's item 8.01 reading, which the route's constant brief never reaches:
# each step checked on the filing it exists for, the verdict held to every
# reading of the confirmation, and every committed item re-derived from the
# saved bytes. It reads 22 small 8-K documents; 1.5 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_e01_eight_o_one_reading",)
# B03's D&A census: the chain's first concept found where Salesforce tags it on
# fixed-asset depreciation only, and the nine filings' direct candidates
# disagreeing at that one filing and no other. Reads nine 10-K documents.
# (Renamed from test_b03_depreciation_scope when the base added a file of that name
# for the ordinary route's current-credit guard; both now run.)
SOURCE_TESTS += ("tests.vnext.test_historical_b03_depreciation_scope",)
# The statement reading behind 75 acceptances, committed in place of one that
# was not and that skipped every value int() could not parse. Each rule on
# the filing that needs it, and the committed reading re-derived from the
# ten saved 10-Ks. Parses about 30 MB; under a second measured.
SOURCE_TESTS += ("tests.vnext.test_statement_fact_reading",)
# The event-count reading behind C01 and E02-E05: every window's filings and
# counts re-derived from the saved index and headers, the index being the
# ledger's latest successful copy, and an 8-K/A counted as its own entry.
SOURCE_TESTS += ("tests.vnext.test_event_count_reading",)
# The governance reading behind C03 and C04: the pay table's placeholder dash
# for a year a person was not PEO, read from the table itself, and every
# position re-derived from the saved proxies and annual reports.
SOURCE_TESTS += ("tests.vnext.test_governance_reading",)
# The lodging, RPO and compensation readings re-derived from the saved
# filings: the scope section's Worldwide row rather than the first one, the
# two RPO facts not taken, and a compensation row that must sum to its total.
SOURCE_TESTS += ("tests.vnext.test_single_readings",)
# The B06 reading behind four acceptances: each position re-derived from its
# filing's balance sheet and lease note, each finance-lease branch on the filing
# it exists for, and a lease note rewritten to classify leases under debt shown
# not to add them twice. Reads four 10-Ks; under a second measured.
SOURCE_TESTS += ("tests.vnext.test_debt_to_equity_reading",)
# D04 at a pinned period: the pinned complete source held byte for byte to the
# frozen builders with the same inputs (an earlier year, a predecessor year
# with its Part III amendment, B13 in scope), a recorded registration carried
# through the loader and the case to the frozen text builders, and the live
# session refused by name. Builds five complete semantic sources; 204 seconds
# measured under a running batch.
SOURCE_TESTS += ("tests.vnext.test_historical_semantic_routes",)
# The C02 judgements held to the route's own selection from the saved proxies:
# the committed reading re-derived for ten values, and a judgement file that
# no longer describes the selection refused. Prepares ten text inputs; 70
# seconds measured under a running batch.
SOURCE_TESTS += ("tests.vnext.test_c02_board_reading",)
# E01 under the content-confirmed definition: the one answer the reading can
# grant (a window with no candidate item) recomputed from saved headers, and a
# window with candidates must show them. About 10 seconds.
SOURCE_TESTS += ("tests.vnext.test_e01_candidate_reading",)
# The six financial metrics' open side: the ordinary resolver and the restated
# one handed the same preparation, every returned field equal on the bank's
# real latest filing; an earlier year's and an amended period's pinned
# preparations through the restated reader; and the gate answered once. Parses
# the bank's 10-K once per metric; 130 seconds measured under a running batch.
SOURCE_TESTS += ("tests.vnext.test_historical_financial_results",)
# A pinned period whose selection reads history blocks: every loaded block's
# proof carried with the input, a main-document period's proofs unchanged, and
# the installer reading the runtime's Requirement rather than the source root's.
# Builds the recorded root with the re-derived bank index (480 MB copied);
# 42 seconds measured under a running batch.
SOURCE_TESTS += ("tests.vnext.test_historical_block_inputs",)
# A pinned filing whose submissions row sits in a history block: the lookup that
# answers with the main index when recent lists the row and with the loaded block
# otherwise, and the four routes that prove their target against it answering
# exactly as on the repository root. Builds a recorded root with Marriott's rows
# up to 2024-06-30 moved into a new block; 52 seconds measured beside a sweep.
SOURCE_TESTS += ("tests.vnext.test_historical_filing_inventory",)
# E01's 8.01 items read from their own text: every saved 8.01 located once and
# compared with the independent reading, and the route resolving the seven value
# windows; 84 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_event_items",)
# The accession route reading reports whose FASB namespaces carry the release
# date: JPMorgan FY2021 and Salesforce FY2022 from the export, two year-only
# reports from the checkout; 131 seconds measured beside a running batch.
SOURCE_TESTS += ("tests.vnext.test_historical_accession_releases",)
# D02's route leaving Item 8 category mentions out on three saved latest-year
# reports, with the rule stubbed out for the before side; 47 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_d02_category_route",)
# The candidate B03 D&A rule on the nine filings the cross-source reading opened,
# with the frozen fact parser's output compared fact by fact; 10 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_da_scope_candidate",)
# A Part III amendment's note read whole: the three saved amendments and seven
# counterexamples built from the predecessor's own bytes; 94 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_amendment_note",)
# B03 through the pinned route with the D&A scope rule wired in: Salesforce
# withheld by name with its B01 carried, two filings whose result equals the
# result with the check off, and four constructed shapes; 44 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_da_scope_route",)
# The DEI reader with the taxonomy releases before 2022 accepted: it parses ten
# saved annual reports and constructed older-release copies, about 30 seconds.
SOURCE_TESTS += ("tests.vnext.test_historical_dei",)
SOURCE_TESTS += ("tests.vnext.test_historical_proxy_identity",)
SOURCE_TESTS += ("tests.vnext.test_historical_note_navigation",)
SOURCE_TESTS += ("tests.vnext.test_historical_proxy_compensation",)
# D04's single-object bound widened only where the frozen grouping refuses:
# Pfizer FY2022 from the export and an Enphase report from the checkout, with
# the request bound's own refusal of a unit twice the size; 27 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_semantic_bound",)
# The lodging table introduction in its older printed forms, read only where the
# frozen inspector refuses it: Marriott FY2021/FY2022 from the export and FY2025
# from the checkout; 26 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_lodging_introduction",)
# C03 on the proxies that declare the first ECD taxonomy release (ecd/2022q4),
# each set against the next proxy read by the frozen resolver: eleven proxies
# from the export, 29 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_ecd_release",)
# The financial witnesses' older-wording successors on the bank's FY2021 annual
# report from the export: one run of each of the five metrics' successors.
SOURCE_TESTS += ("tests.vnext.test_historical_financial_wording_filings",)
# The older-year C03 reading across every saved proxy of the registrant,
# including the export's: 5 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_c03_across_proxies_reading",)
# The bank-measures reading re-derived from the five saved annual reports
# (checkout and export) and its guards on constructed tables: 20 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_bank_measures_reading",)
# The bank statement-facts reading (A01, A02, A05-A08, A10 off the inline XBRL)
# re-derived from the five annual reports and their prior reports, and its
# guards on constructed documents: 6 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_bank_statement_facts_reading",)
# The XBRL instances an annual accession's index lists, declared for C04 and
# B06 and checked against the frozen reader run for real: 52 seconds measured.
SOURCE_TESTS += ("tests.vnext.test_historical_instance_sources",)
# Four modules the tier did not run although their records said it did or would:
# the approved amendment policy asked of two saved 10-K/A filings (38 seconds
# alone), the two Part III filings' statement-input admission re-verified from
# saved bytes (244 seconds beside four busy processes), the fiscal-year
# definition forms older annual reports use (18 seconds), and the checkpoint
# replayed once per ledger state over a recorded root (127 seconds).
SOURCE_TESTS += ("tests.vnext.test_historical_amendment_admission",)
SOURCE_TESTS += ("tests.vnext.test_historical_part_iii_admission",)
SOURCE_TESTS += ("tests.vnext.test_historical_fiscal_labels",)
SOURCE_TESTS += ("tests.vnext.test_historical_plan_replay",)
# The batch's two blocks: the checkpoint replay once per ledger state over two
# recorded roots, and the derivation memo, whose last class calls the five real
# functions on this repository's saved sources.
SOURCE_TESTS += ("tests.vnext.test_historical_run_replay",)
SOURCE_TESTS += ("tests.vnext.test_historical_derivation_memo",)
# Whether a saved history block is the block its index declares: made-up
# blocks, then every saved and acquired block, read from the checkout and the
# acquisition's export.
SOURCE_TESTS += ("tests.vnext.test_history_block_coherence",)
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
# What an acceptance binds and where it gets it. The generator reads no Run -
# asserted by replacing every binding of the receipt readers - and an unchanged
# reading regenerated beside a batch whose result moved unit, scope, filing or
# meaning must build the committed register byte for byte. It reads the
# committed readings and a few saved attempt headers; 2 seconds measured with
# 600 acceptances, most of it one pass over each export archive.
FAST_TESTS += ("tests.vnext.test_acceptance_identity",)
# #47's model-call allowance, ledger and request binding, in the tree where the
# egress patch is not applied: nothing here can reach a provider, which is
# asserted rather than assumed. It reads no source material; about 3 seconds.
FAST_TESTS += ("tests.vnext.test_historical_model_calls",)
# A LIVE registration only with the counted calls that answered it (the
# re-review's N1), held where CI runs: the fix is in the repository while the
# suite making real counted calls needs the egress patch. No filing; milliseconds.
FAST_TESTS += ("tests.vnext.test_historical_counted_calls",)
# E01's content-confirmation contract on synthetic candidates: the request, the
# answer's form and the count. Reads no filing; well under a second.
FAST_TESTS += ("tests.vnext.test_historical_ma_confirmation",)
# What a pinned row says about where its values come from, chosen by its own
# evidence: a pure function over accessions; no filing is read.
FAST_TESTS += ("tests.vnext.test_historical_row_notes",)
FAST_TESTS += ("tests.vnext.test_c02_core_fact_reach",)
# The saved-source tier's split across its CI jobs: every case in exactly one
# shard, every weight naming a real case. Imports the runner; no material.
FAST_TESTS += ("tests.vnext.test_source_tier_split",)
# C02 composition facts: synthetic structures, one rule per case.
FAST_TESTS += ("tests.vnext.test_historical_board_composition",)
# #47's own files against the family-owned phrase list; CI runs no
# repository-wide semantic audit, and nine phrases had crept in unseen.
FAST_TESTS += ("tests.vnext.test_historical_business_literals",)
# C02 composition facts on the ten saved governance filings, both directions.
SOURCE_TESTS += ("tests.vnext.test_historical_board_composition_filings",)
# D02's Item 8 review: the contract on synthetic documents (no filing, well
# under a second), then what a registered answer changes on Lumen's 10-K.
FAST_TESTS += ("tests.vnext.test_historical_legal_review.TheRequestIsTheBlocksAndWhichMustBeDecided",
               "tests.vnext.test_historical_legal_review.TheAnswerIsHeldToItsForm",
               "tests.vnext.test_historical_legal_review.WhatACheckedAnswerCounts",
               "tests.vnext.test_historical_legal_review.ARegistrationIsCheckedAgainUnderTheCurrentCode")
SOURCE_TESTS += ("tests.vnext.test_historical_legal_review.OnARealFilingOnlyItem8Changes",)
# Issue #47: a current and a prior claim of one quantity must read one quantity
# (Pfizer's B02 divided product revenue by total revenue); saved Company Facts only.
FAST_TESTS += ("tests.vnext.test_historical_paired_measure",)
# D02's numbered page footer: the linear reading against the backtracking
# pattern it replaced, on crafted and generated strings; no filing.
FAST_TESTS += ("tests.vnext.test_historical_page_numbered",)
# The XBRL parse block: one parse per document while it is open, each binding
# put back after; synthetic documents and one saved 10-K. A few seconds.
FAST_TESTS += ("tests.vnext.test_historical_xbrl_parse",)
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
# D02 excerpt readings: exact coverage of the packet, a covered-elsewhere
# verdict that must cite an excerpt, Pfizer FY2025's packet built from the saved
# filing with the two registered keyword errors in front of the reader, and each
# committed reading's excerpts rendering the value it accepted. About 80 seconds.
SOURCE_TESTS += ("tests.vnext.test_d02_excerpt_reading",)
# The four D02 route repairs the older-year readings found (page-foot item
# headings, page-position furniture, captions a note does not carry, statements
# after a pointer-page Item 8), each on the saved filing that showed it, with
# what must not move asserted beside what must. Builds thirteen annual reports.
SOURCE_TESTS += ("tests.vnext.test_historical_d02_route_repairs",)
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
FAST_TESTS += ("tests.vnext.test_historical_note_carrying.HistoricalNoteCarryingTest",)
FAST_TESTS += ("tests.vnext.test_paid_e01_reading.PaidE01ReadingTest",)
SOURCE_TESTS += ("tests.vnext.test_historical_note_carrying.HistoricalNoteRateMaterialTest",)
SOURCE_TIMEOUT_SECONDS = 240
SOURCE_TIMEOUT_OVERRIDES = {
    # The unchanged full original-source module passed on head 698b9a45 in
    # 226.062s, then alone reached 240.117s/rc124 on c3cda0b1. Both original
    # test classes pass separately without assertion changes; keep the same
    # selector and job deadline while allowing a measured 60-second margin.
    "tests.vnext.test_normal_zero_ai_results": 300,
    # This single case includes acquisition, native installation and cold replay.
    "tests.vnext.test_continuous_sec_acquisition": 480,
    # 25 cases over nine filings' full 10-K bytes. The 480 here was sized for
    # nine cases at 192 seconds; the cases added since - page furniture, the
    # italic and underlined note labels, the audit-report spans - were never
    # re-measured, and the saved-source tier timed the module out at 480.
    # Measured at 1029 seconds alone on a 4-core runner beside one other
    # single-process job.
    "tests.vnext.test_historical_text_boundary": 1500,
    # Sixteen cases over thirteen annual reports' full bytes; the injection
    # script's control run took 619 seconds on a 4-core machine running four
    # other jobs. Most of it is the route's proposals, not the builds.
    "tests.vnext.test_historical_d02_route_repairs": 1200,
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
    # Seven cases that recompute ten positions through the historical route;
    # measured at 202 seconds alone.
    "tests.vnext.test_historical_board_composition_filings": 600,
    # Lumen's 10-K prepared once and reviewed eight ways; 179 seconds with the
    # synthetic classes beside a batch.
    "tests.vnext.test_historical_legal_review.OnARealFilingOnlyItem8Changes": 480,
    # Fourteen cases over nine filings' full 10-K bytes, three of which parse
    # the same document twice to hold the successor parser to the frozen one.
    # Measured at 187 seconds, too close to the 240 default to survive a
    # slower runner.
    "tests.vnext.test_historical_risk_headings": 600,
    # 91 cases at 379 seconds measured together. The refresh chain runs a whole acquisition - install, capture,
    # checkpoint, installation, and three plans of a company with sixty-nine
    # declared shards - once for its class and once more for the case that
    # re-captures unchanged bytes, which is the case that makes the rest mean
    # anything. Each company's declaration is still built once per process and
    # deep-copied to the cases that read it. This module is the one whose
    # timeout would read as "the acquisition chain broke". The extension of
    # the SEC approval added 26 cases, three of them real chains or resumes;
    # the whole module took 930 seconds here while a batch held three of four
    # cores, so the budget moved from 900 before a runner could hit it.
    "tests.vnext.test_historical_sec_session": 1500,
    # 21 cases, five complete semantic sources; 204 seconds measured while a
    # batch held three of four cores, which is too close to the default.
    "tests.vnext.test_historical_semantic_routes": 600,
    # Seven cases over four filings' full 10-K bytes; 162 seconds measured while
    # a batch held three of four cores.
    "tests.vnext.test_historical_d02_marks": 480,
    # Nine cases, six parses of the bank's full 10-K; 130 seconds measured
    # while a batch held three of four cores.
    "tests.vnext.test_historical_financial_results": 480,
    # 24 cases; 204 seconds in CI, and 226 seconds alone on 2026-09-28 while
    # the egress verification and two source shards held the other cores - it
    # timed out at the 240 default in the shard it shared with them.
    "tests.vnext.test_historical_period_results": 480,
    # Copies a 480 MB recorded root before its first case; 42 seconds measured
    # with a warm page cache, which a fresh runner will not have.
    "tests.vnext.test_historical_block_inputs": 480,
    # 244 seconds measured beside four busy processes: past the 240 default.
    "tests.vnext.test_historical_part_iii_admission": 600,
    # Installs the baseline corpus into a recorded root and plans a company
    # twice, once with the frozen replay on every check; 127 seconds alone.
    "tests.vnext.test_historical_plan_replay": 480,
    # Two recorded roots from the baseline corpus, sixteen cases; about two
    # minutes alone.
    "tests.vnext.test_historical_run_replay": 480,
    # The real-function class loads the Requirement snapshot and prepares one
    # period's inputs, each twice frozen and once memoized; about a minute alone.
    "tests.vnext.test_historical_derivation_memo": 300,
    # Reads every saved and acquired submissions block out of the export's
    # archives; 140 seconds alone.
    "tests.vnext.test_history_block_coherence": 480,
    # Copies the baseline corpus into a recorded root, then resolves three route
    # families on both roots; 52 seconds measured beside a running sweep.
    "tests.vnext.test_historical_filing_inventory": 480,
    # Resolves E01 for seven windows through the route; 84 seconds measured.
    "tests.vnext.test_historical_event_items": 480,
    # Resolves the latest accession metrics for two companies, then four saved
    # reports; 131 seconds measured beside a running batch.
    "tests.vnext.test_historical_accession_releases": 480,
    "tests.vnext.test_historical_d02_category_route": 480,
    # Parses the two Paramount amendments and their originals for each case.
    "tests.vnext.test_historical_amendment_note": 480,
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
    # One line when a case starts and one when it ends, on stderr. The result
    # JSON is printed only once every case is done, so a job cancelled at its
    # time limit printed nothing at all: two consecutive shard runs were
    # cancelled at 35 minutes with no way to tell which case was running.
    print(json.dumps({"started": name, "timeout_seconds": timeout}), file=sys.stderr, flush=True)
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
    seconds = round(time.monotonic()-start,3)
    print(json.dumps({"finished": name, "return_code": code, "seconds": seconds}),
          file=sys.stderr, flush=True)
    return {"test":name,"return_code":code,"duration_seconds":seconds,
            "timeout_seconds":timeout,
            "stdout_tail":stdout[-2000:],"stderr_tail":stderr[-2000:]}


# How long each saved-source case takes on CI, in seconds: the mean of the
# per-case progress lines of two runs on 2026-10-03 - 37115109925 (141587e3)
# and 37116301601 (8eaf1b63). Every case finished in at least one of them
# (132 in both). The table this replaces (three 10-01 runs and local estimates)
# held 11 cases at the 30-second default and still carried the #47 modules at
# their weight from before the 10-01 cuts, so in 37116301601 shard 0 finished
# in 19 minutes while shard 2 was cancelled at 35 with every case it reached
# passing. Runners differ (earlier runs measured the same shard at 0.69 to 1.31
# times), so a mean carries less of one runner's speed than one run does. These
# are weights for splitting the tier across its CI jobs, not limits - a wrong
# weight unbalances the split and fails nothing. Balanced on these figures,
# three shards carry about 30.3 minutes a lane; the fourth shard
# (docs/evidence/issue47_history/ci-job-patch/0005) is a workflow change this
# branch cannot push.
SOURCE_CI_SECONDS = {
    "tests.vnext.test_historical_sec_session": 445,
    "tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_mixed_old_root_resumes_current_rule_metric_and_c04": 395,
    "tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_failed_processing_copy_preserves_recorded_capture_for_resume": 349,
    "tests.vnext.test_d03_recorded_response_set.D03RecordedResponseSetTest": 252,
    "tests.vnext.test_historical_debt_results": 239,
    "tests.vnext.test_continuous_sec_acquisition": 236,
    "tests.vnext.test_normal_zero_ai_results": 201,
    "tests.vnext.test_d03_recorded_response_store.D03RecordedResponseStoreTest": 193,
    "tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest": 189,
    "tests.vnext.test_normal_companyfacts_results": 179,
    "tests.vnext.test_historical_coverage": 171,
    "tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest": 161,
    "tests.vnext.test_historical_board_composition_filings": 157,
    "tests.vnext.test_d02_item8_current_material": 155,
    "tests.vnext.test_normal_c02_composition.C02CompositionMaterialTest": 155,
    "tests.vnext.test_historical_da_scope_route": 154,
    "tests.vnext.test_c04_refresh_cycle.C04RefreshCycleMaterialTest": 151,
    "tests.vnext.test_historical_semantic_routes": 148,
    "tests.vnext.test_b03_depreciation_scope_update.B03FordUpdateMaterialTest": 146,
    "tests.vnext.test_regulatory_fact_review": 146,
    "tests.vnext.test_historical_period_results": 142,
    "tests.vnext.test_d03_native_assessment.D03NativeCollectionMaterialTest": 138,
    "tests.vnext.test_c04_update_cycle.C04UpdateCycleMaterialTest": 131,
    "tests.vnext.test_c02_auditor_successor.C02AuditorScopeMaterialTest": 129,
    "tests.vnext.test_b06_bond_leases": 126,
    "tests.vnext.test_b03_depreciation_scope_update.B03LegacyRecoveryMaterialTest": 120,
    "tests.vnext.test_normal_accession_results": 120,
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_current_run_input_retains_the_actual_amendment_without_creating_debt": 118,
    "tests.vnext.test_historical_financial_results": 118,
    "tests.vnext.test_b06_inclusive_table": 117,
    "tests.vnext.test_c02_member_successor.C02MemberScopeMaterialTest": 116,
    "tests.vnext.test_capacity_two_stage_material.CapacityTwoStageMaterialTest.test_scoped_interpretation_stops_after_saved_scan": 114,
    "tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest.test_saved_source_recorded_candidate_replays_but_is_not_company_result": 110,
    "tests.vnext.test_historical_d02_route_repairs": 108,
    "tests.vnext.test_historical_plan_replay": 107,
    "tests.vnext.test_d03_current_source_replay.D03CurrentSourceReplayTest": 105,
    "tests.vnext.test_instant_balance_amendment": 102,
    "tests.vnext.test_historical_event_items": 101,
    "tests.vnext.test_historical_event_window": 100,
    "tests.vnext.test_historical_financial_wording_filings": 99,
    "tests.vnext.test_c02_board_reading": 96,
    "tests.vnext.test_historical_text_boundary": 91,
    "tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest.test_unresolved_recorded_group_is_retained_without_company_credit": 88,
    "tests.vnext.test_historical_governance_results": 85,
    "tests.vnext.test_historical_accession_releases": 82,
    "tests.vnext.test_historical_run_replay": 82,
    "tests.vnext.test_annual_amendment_scope": 79,
    "tests.vnext.test_historical_dei": 79,
    "tests.vnext.test_historical_amendment_note": 76,
    "tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest": 75,
    "tests.vnext.test_ordinary_processing_source.OrdinaryProcessingSourceTest": 75,
    "tests.vnext.test_historical_part_iii_admission": 73,
    "tests.vnext.test_historical_risk_headings": 72,
    "tests.vnext.test_historical_filing_inventory": 67,
    "tests.vnext.test_b06_combined_borrowings": 66,
    "tests.vnext.test_historical_predecessor_periods": 66,
    "tests.vnext.test_historical_running_header": 64,
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_source_relationship_failure_remains_a_withheld_result": 61,
    "tests.vnext.test_ordinary_e01_item_text_input": 59,
    "tests.vnext.test_regulatory_statement_facts.RegulatoryStatementSourceMaterialTest": 58,
    "tests.vnext.test_b03_depreciation_scope.B03DepreciationScopeMaterialTest": 57,
    "tests.vnext.test_historical_amendment_admission": 57,
    "tests.vnext.test_d01_byte_reading": 56,
    "tests.vnext.test_historical_governance_text": 56,
    "tests.vnext.test_historical_legal_review.OnARealFilingOnlyItem8Changes": 56,
    "tests.vnext.test_historical_source_acquisition": 56,
    "tests.vnext.test_historical_lodging_results": 55,
    "tests.vnext.test_normal_source_requirements": 55,
    "tests.vnext.test_r6_historical_controls": 54,
    "tests.vnext.test_b06_financing_inventory": 53,
    "tests.vnext.test_historical_block_inputs": 49,
    "tests.vnext.test_capacity_applicability.CapacityApplicabilityMaterialTest": 48,
    "tests.vnext.test_capacity_text_results": 47,
    "tests.vnext.test_ordinary_income_input": 44,
    "tests.vnext.test_ordinary_special_debt_scope": 44,
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_real_effect_is_separate_from_debt_completeness_and_the_old_balance_policy": 43,
    "tests.vnext.test_b06_note_carrying": 42,
    "tests.vnext.test_normal_annual_input_v2": 42,
    "tests.vnext.test_a05_formula_material": 41,
    "tests.vnext.test_b03_contract_amortization_scope.B03ContractAmortizationScopeTest": 41,
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_changed_debt_or_equity_outside_the_purpose_note_is_rejected": 41,
    "tests.vnext.test_financial_structured.FinancialStructuredTest.test_native_tags_do_not_override_an_explicit_non_reported_table_declaration": 41,
    "tests.vnext.test_capacity_native_assessment": 40,
    "tests.vnext.test_e01_header_document_guard.E01HeaderDocumentGuardMaterialTest": 40,
    "tests.vnext.test_historical_d02_category_route": 40,
    "tests.vnext.test_normal_run_inputs": 40,
    "tests.vnext.test_financial_candidates.LcrEntityFastTest.test_unidentified_named_holding_is_rejected": 39,
    "tests.vnext.test_historical_shared_sources": 39,
    "tests.vnext.test_r6_regulatory_semantics": 39,
    "tests.vnext.test_d03_complete_interpretation.D03CompleteInterpretationTest.test_saved_marriott_context_only_stays_unapproved_without_fake_unresolved": 37,
    "tests.vnext.test_historical_instance_sources": 37,
    "tests.vnext.test_semantic_source_grouping.SemanticSourceGroupingMaterialTest": 37,
    "tests.vnext.test_historical_proxy_compensation": 36,
    "tests.vnext.test_financial_candidates.LcrEntityFastTest.test_explicit_subsidiaries_keep_their_original_definition": 35,
    "tests.vnext.test_historical_structural_results": 35,
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_unproven_amendment_does_not_enter_even_the_equity_guard": 34,
    "tests.vnext.test_continuous_semantic_calls": 34,
    "tests.vnext.test_b06_current_input.CurrentDebtInputTest.test_changed_declared_amendment_purpose_and_new_native_debt_cannot_pass": 33,
    "tests.vnext.test_historical_debt_fallback_forms": 33,
    "tests.vnext.test_historical_metadata_context": 31,
    "tests.vnext.test_historical_proxy_identity": 31,
    "tests.vnext.test_lodging_table_source": 31,
    "tests.vnext.test_e01_layout_successor.E01LayoutSuccessorMaterialTest": 30,
    "tests.vnext.test_historical_capacity_results": 30,
    "tests.vnext.test_bank_measures_reading": 29,
    "tests.vnext.test_fiscal_year_labels": 28,
    "tests.vnext.test_ordinary_scalability_audit.OrdinaryScalabilityAuditTest.test_current_exact_reviewed_sources_only_have_no_business_literals": 28,
    "tests.vnext.test_d04_native_wiring": 27,
    "tests.vnext.test_native_assessment_replay": 27,
    "tests.vnext.test_c04_source_only_install.C04SourceOnlyInstallTest": 26,
    "tests.vnext.test_event_count_reading": 26,
    "tests.vnext.test_historical_lodging_introduction": 26,
    "tests.vnext.test_capacity_semantic_source.CapacityCompleteSourceMaterialTest": 25,
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.test_only_private_clients": 25,
    "tests.vnext.test_financial_candidates.LcrEntityFastTest.test_unidentified_consolidated_group_is_rejected": 25,
    "tests.vnext.test_d01_emphasis_material": 24,
    "tests.vnext.test_d02_excerpt_reading": 24,
    "tests.vnext.test_historical_d02_marks": 24,
    "tests.vnext.test_b03_exact_impairment_relation.B03ExactImpairmentRelationTest": 23,
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.test_selected_clients": 22,
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.test_unrelated_exclusion_does_not_change_aum_scope": 22,
    "tests.vnext.test_financial_balance_scope.VarReportingFastTest.test_illustrative_table_is_rejected": 22,
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.test_but_not_clients": 21,
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.test_only_institutional_and_retail_clients": 21,
    "tests.vnext.test_historical_ecd_release": 20,
    "tests.vnext.test_historical_governance_input": 20,
    "tests.vnext.test_historical_note_navigation": 20,
    "tests.vnext.test_r6_semantic_review": 19,
    "tests.vnext.test_b03_depreciation_scope.B03ImpairmentSourceMaterialTest": 18,
    "tests.vnext.test_historical_semantic_bound": 18,
    "tests.vnext.test_history_block_coherence": 18,
    "tests.vnext.test_risk_signals": 18,
    "tests.vnext.test_going_concern_source": 17,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_explicit_additional_current_borrowing_blocks_both_modes": 16,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_same_xml_and_primary_alternate_total_still_needs_its_own_arithmetic": 16,
    "tests.vnext.test_financial_balance_scope.AumClientFastTest.test_excluding_clients": 16,
    "tests.vnext.test_financial_balance_scope.VarReportingFastTest.test_hypothetical_table_is_rejected": 16,
    "tests.vnext.test_financial_balance_scope.VarReportingFastTest.test_unrelated_hypothetical_example_preserves_reported_var": 16,
    "tests.vnext.test_financial_duration": 16,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_current_named_carrying_total_is_reconciled_but_unknown_balance_is_not": 15,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_original_two_modes_keep_amounts_and_explain_different_measurements": 15,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_primary_equity_amount_sign_scale_and_unit_conflicts_reject": 14,
    "tests.vnext.test_governance_reading": 14,
    "tests.vnext.test_normal_history_catalog": 14,
    "tests.vnext.test_r6_semantic_verification": 14,
    "tests.vnext.test_text_results": 14,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_borrowing_keyword_and_explicit_past_issuance_do_not_block": 13,
    "tests.vnext.test_table_context_qualification_guard.TableContextQualificationGuardTest.test_missing_or_excess_usage_is_terminal_and_skips_ordinal_two": 13,
    "tests.vnext.test_c04_registration_successor": 12,
    "tests.vnext.test_e01_candidate_reading": 12,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_newer_disclosed_credit_group_is_derived_from_table_members": 11,
    "tests.vnext.test_historical_page_split_headings": 11,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_zero_clause_cannot_hide_a_positive_balance_or_unsupported_amount": 10,
    "tests.vnext.test_capacity_utilization_source.CapacitySourceMaterialTest": 9,
    "tests.vnext.test_historical_da_scope_candidate": 9,
    "tests.vnext.test_historical_fiscal_labels": 8,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_unconsumed_known_concept_must_agree_with_primary": 6,
    "tests.vnext.test_capacity_semantic_review.CapacitySemanticReviewMaterialTest": 6,
    "tests.vnext.test_statement_fact_reading": 6,
    "tests.vnext.test_b06_disclosure_v2.B06DisclosureV2Test.test_current_balance_cannot_inherit_an_unspecified_date": 5,
    "tests.vnext.test_bank_statement_facts_reading": 4,
    "tests.vnext.test_c03_across_proxies_reading": 4,
    "tests.vnext.test_e01_eight_o_one_reading": 2,
    "tests.vnext.test_historical_derivation_memo": 2,
    "tests.vnext.test_single_readings": 2,
    "tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest.test_anchor_candidate_changes_business_digest": 1,
    "tests.vnext.test_debt_to_equity_reading": 1,
    "tests.vnext.test_historical_b03_depreciation_scope": 1,
    "tests.vnext.test_text_results_v2": 1,
}
SOURCE_DEFAULT_CI_SECONDS = 30


def _heaviest_first(names):
    return sorted(names, key=lambda name: (-SOURCE_CI_SECONDS.get(name, SOURCE_DEFAULT_CI_SECONDS),
                                           name))


def _selected_tests(suite, shard_index, shard_count):
    if (shard_count < 1 or shard_index < 0 or shard_index >= shard_count
            or (suite != "source-material" and (shard_index, shard_count) != (0, 1))):
        raise inherited.FastTestError("FAST_TEST_SHARD_INVALID")
    if suite == "fast":
        return FAST_TESTS
    # Each case goes, heaviest first, to the shard with less measured work so
    # far, and each shard runs its heaviest cases first. Assigning by list
    # position put 4,840 measured seconds in one shard and 4,155 in the other
    # (run 36321956779) and both were cancelled at 35 minutes with every case
    # they reached passing; with two jobs a shard, it is the total and a long
    # case started late that decide when a shard ends. Ties go by name, so
    # every job computes the same split and each case lands in exactly one.
    loads, shards = [0] * shard_count, [[] for _ in range(shard_count)]
    for name in _heaviest_first(SOURCE_TESTS):
        lightest = min(range(shard_count), key=lambda index: (loads[index], index))
        loads[lightest] += SOURCE_CI_SECONDS.get(name, SOURCE_DEFAULT_CI_SECONDS)
        shards[lightest].append(name)
    return tuple(shards[shard_index])


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
