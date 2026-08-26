"""Load and verify the immutable AI-first Requirement Snapshot.

The loader binds exact FSD, Issue Contract, Decision Register, legacy
inventory, and baseline bytes. Runtime callers receive explicit hashes and the
single effective decision for each decision ID; comments or live issue state
are never consulted.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from .canonical import CanonicalError, SEMANTIC_VERSIONS, content_hash
from .canonical import parse_utc_timestamp
from .canonical import sha256_file, strict_json_file


FSD_SHA256 = "1cf091812629648095119692c1742d12015e1012ccabf2173820e585e1d42b2b"
PARENT_REQUIREMENT_ID = "ai_first_v3_3_1"
ISSUE_15_REQUIREMENT_ID = "issue_15_v1"
ISSUE_15_CONTRACT_SHA256 = (
    "9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec"
)
ISSUE_15_FOUNDATION_SOURCE_COMMIT = "f1cc44342e6814522ec2688cf3674f7ec442be8d"
ISSUE_15_FOUNDATION_MERGE_COMMIT = "4d02db6a474f93eec9e058d780e206b4504ab24d"
ISSUE_15_FOUNDATION_TAG = "issue-15-foundation-v1"
SNAPSHOT_FILES = {
    "baseline": "baseline_manifest.json",
    "decisions": "decision_register.json",
    "fsd": "FSD.md",
    "issue": "ISSUE_CONTRACT.md",
    "r3_addendum": "ISSUE_CONTRACT_R3_ADDENDUM.md",
    "legacy_inventory": "legacy_path_inventory.json",
}
ISSUE_15_SNAPSHOT_FILES = {
    "baseline": "baseline_manifest.json",
    "contract": "CONTRACT.md",
    "decisions": "decision_register.json",
    "foundation_verification": "foundation_verification_receipt.json",
    "legacy_inventory": "legacy_semantic_producer_inventory.json",
    "source_strategy": "source_strategy_baseline_receipt.json",
    "transfer": "transfer_manifest.json",
}
ISSUE_15_RUNTIME_AUTHORITY_FILES = {
    "catalog/deterministic_metrics.json",
    "catalog/event_routes.json",
    "catalog/zero_ai_public_projection.json",
    "config/provider_model_runtime.json",
    "config/source_strategy_registry.json",
}
ISSUE_15_EFFECTIVE_DECISION_IDS = {
    "D-01",
    "D-03",
    "D-04",
    "D-05",
    "D-06",
    "D-07",
    "D-08",
    "D-24",
    "D-26",
    "D-30",
    "D-31",
    "D-32",
    "D-33",
    "D-34",
    "D-35",
    "D-36",
    "D-37",
    "D-38",
}
ISSUE_15_D07_MEASUREMENT_EXCEPTION = {
    "purpose": "ACTUAL_PROMPT_TOKEN_USAGE_ONLY",
    "family_id": "lodging_kpi_table",
    "task_contract_id": "lodging_occupancy_table_v2",
    "source_company_id": "marriott_international",
    "source_sha256": (
        "c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547"
    ),
    "serializer_version": "2",
    "allowed_successful_provider_egress_count": 1,
    "automatic_retry_count": 0,
    "qualification_ordinal_credit": False,
    "publication_eligible": False,
    "qualification_evidence_eligible": False,
    "response_reuse_for_qualification": False,
    "consumes_authorization_after_any_egress_marker": True,
    "execution_requires_external_exact_head_authorization": True,
}
ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION = {
    "purpose": "ACTUAL_PROMPT_TOKEN_USAGE_ONLY",
    "family_id": "lodging_kpi_table",
    "task_contract_id": "lodging_revpar_table_v2",
    "source_company_id": "marriott_international",
    "source_sha256": (
        "c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547"
    ),
    "serializer_version": "2",
    "allowed_successful_provider_egress_count": 1,
    "automatic_retry_count": 0,
    "qualification_ordinal_credit": False,
    "publication_eligible": False,
    "qualification_evidence_eligible": False,
    "response_reuse_for_qualification": False,
    "consumes_authorization_after_any_egress_marker": True,
    "execution_requires_external_exact_head_authorization": True,
    "provider_reported_prompt_tokens_required": True,
    "usage_unavailable_status": "FAILED_USAGE_UNAVAILABLE",
    "context_budget_tokens": 200000,
}
ISSUE_15_D07_REVISED_LODGING_SYSTEM_PROMPT = (
    "Return raw claims and exact locators from one selected table only. For "
    "every primary candidate, emit exactly these schema keys: role, "
    "claimed_period, claimed_raw_value, claimed_reported_unit, claimed_scope, "
    "locator, scope_evidence_locators, and competing_candidates. Define every "
    "claimed_scope.evidence_locator_ids value in scope_evidence_locators with "
    "exact table geometry and raw_text copied from the supplied table. Always "
    "emit competing_candidates, using [] when none. Never emit "
    "rejection_reason_claim on a primary candidate; emit it only on each "
    "competing candidate, which must include every competing-candidate schema "
    "key."
)
ISSUE_15_D07_SCOPE_BOUND_LODGING_SYSTEM_PROMPT = (
    ISSUE_15_D07_REVISED_LODGING_SYSTEM_PROMPT
    + " For scope_evidence_locators, use location_type caption only when the "
    "selected target table supplies a non-empty caption_raw_text, and copy "
    "that exact caption_raw_text into raw_text. Otherwise use location_type "
    "cell, header, row, or label with all eight locator fields copied from "
    "one supplied cell in the same selected target table, and copy that "
    "cell exact raw_text. Never use text from another table or nearby prose."
)
ISSUE_15_D07_REVISED_PROMPT_MEASUREMENT_GRANT_POLICY = {
    "policy_status": "PROMPT_REVISION_APPROVED_EXACT_GRANTS_PENDING",
    "family_id": "lodging_kpi_table",
    "task_contract_ids": [
        "lodging_occupancy_table_v2",
        "lodging_revpar_table_v2",
    ],
    "revised_system_prompt": ISSUE_15_D07_REVISED_LODGING_SYSTEM_PROMPT,
    "prompt_revision_scope": "SYSTEM_PROMPT_ONLY",
    "output_schema_change_authorized": False,
    "metric_meaning_change_authorized": False,
    "task_role_change_authorized": False,
    "source_change_authorized": False,
    "serializer_change_authorized": False,
    "provider_model_api_change_authorized": False,
    "table_selection_change_authorized": False,
    "historical_attestations_status": (
        "HISTORICAL_NOT_CURRENT_FOR_REVISED_REQUESTS"
    ),
    "old_no_remeasurement_rule_overridden_for_revised_requests": True,
    "maximum_measurements_per_task": 1,
    "automatic_retry_count": 0,
    "provider_reported_prompt_tokens_required": True,
    "usage_unavailable_status": "FAILED_USAGE_UNAVAILABLE",
    "context_budget_tokens": 200000,
    "qualification_ordinal_credit": False,
    "qualification_evidence_eligible": False,
    "response_reuse_for_qualification": False,
    "publication_eligible": False,
    "consumes_authorization_after_any_egress_marker": True,
    "concrete_grant_requires_independent_exact_head_review": True,
    "qualification_requires_both_revised_context_attestations": True,
}
ISSUE_15_D07_REVISED_PROMPT_MEASUREMENT_POLICY = {
    **ISSUE_15_D07_REVISED_PROMPT_MEASUREMENT_GRANT_POLICY,
    "policy_status": "MEASUREMENTS_CONSUMED_ATTESTATIONS_ACCEPTED",
}
ISSUE_15_D07_SCHEMA_REVISED_MEASUREMENT_GRANT_POLICY = {
    "policy_status": "LOCATOR_SCHEMA_REVISION_APPROVED_EXACT_GRANTS_PENDING",
    "family_id": "lodging_kpi_table",
    "task_contract_ids": [
        "lodging_occupancy_table_v2",
        "lodging_revpar_table_v2",
    ],
    "output_schema_version": "3",
    "schema_revision_scope": "SHARED_READER_OUTPUT_LOCATOR_CONTRACT",
    "scope_evidence_locator_contract": {
        "caption": ["derived_asset_id", "table_id"],
        "cell_header_row_label": [
            "derived_asset_id",
            "table_id",
            "row_index",
            "column_index",
            "origin_row_index",
            "origin_column_index",
            "rowspan",
            "colspan",
        ],
    },
    "revised_system_prompt": ISSUE_15_D07_REVISED_LODGING_SYSTEM_PROMPT,
    "system_prompt_change_authorized": False,
    "output_schema_change_authorized": True,
    "metric_meaning_change_authorized": False,
    "task_role_change_authorized": False,
    "source_change_authorized": False,
    "serializer_change_authorized": False,
    "provider_model_api_change_authorized": False,
    "table_selection_change_authorized": False,
    "historical_attestations_status": (
        "HISTORICAL_NOT_CURRENT_FOR_SCHEMA_REVISED_REQUESTS"
    ),
    "failed_qualification_terminal_id": (
        "sha256:5c5c5997194396485cb4f00d684f0280"
        "6049f50625708b754bf6a60a428a7cd9"
    ),
    "old_no_additional_measurement_rule_overridden": True,
    "maximum_measurements_per_task": 1,
    "automatic_retry_count": 0,
    "provider_reported_prompt_tokens_required": True,
    "usage_unavailable_status": "FAILED_USAGE_UNAVAILABLE",
    "context_budget_tokens": 200000,
    "qualification_ordinal_credit": False,
    "qualification_evidence_eligible": False,
    "response_reuse_for_qualification": False,
    "publication_eligible": False,
    "consumes_authorization_after_any_egress_marker": True,
    "concrete_grant_requires_independent_exact_head_review": True,
    "qualification_requires_both_schema_revised_attestations": True,
}
ISSUE_15_D07_SCHEMA_REVISED_MEASUREMENT_POLICY = {
    **ISSUE_15_D07_SCHEMA_REVISED_MEASUREMENT_GRANT_POLICY,
    "policy_status": (
        "SCHEMA_REVISED_MEASUREMENTS_CONSUMED_ATTESTATIONS_ACCEPTED"
    ),
}
ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY = {
    "policy_status": "SCOPE_BINDING_PROMPT_REVISION_APPROVED_EXACT_GRANTS_PENDING",
    "family_id": "lodging_kpi_table",
    "task_contract_ids": [
        "lodging_occupancy_table_v2",
        "lodging_revpar_table_v2",
    ],
    "output_schema_version": "3",
    "prompt_revision_scope": "SYSTEM_PROMPT_SCOPE_EVIDENCE_BINDING_ONLY",
    "scope_evidence_binding_contract": {
        "caption": {
            "selected_target_table_caption_raw_text_non_empty_required": True,
            "locator_fields": ["derived_asset_id", "table_id"],
            "raw_text_source": "SELECTED_TARGET_TABLE_CAPTION_RAW_TEXT_EXACT",
        },
        "cell_header_row_label": {
            "locator_fields": [
                "derived_asset_id",
                "table_id",
                "row_index",
                "column_index",
                "origin_row_index",
                "origin_column_index",
                "rowspan",
                "colspan",
            ],
            "locator_source": "ONE_SUPPLIED_CELL_IN_SELECTED_TARGET_TABLE",
            "raw_text_source": "SUPPLIED_CELL_RAW_TEXT_EXACT",
        },
        "forbidden_text_sources": ["ANOTHER_TABLE", "NEARBY_PROSE"],
    },
    "revised_system_prompt": ISSUE_15_D07_SCOPE_BOUND_LODGING_SYSTEM_PROMPT,
    "system_prompt_change_authorized": True,
    "output_schema_change_authorized": False,
    "metric_meaning_change_authorized": False,
    "task_role_change_authorized": False,
    "source_change_authorized": False,
    "serializer_change_authorized": False,
    "provider_model_api_change_authorized": False,
    "table_selection_change_authorized": False,
    "historical_attestations_status": (
        "HISTORICAL_NOT_CURRENT_FOR_SCOPE_BOUND_PROMPT_REQUESTS"
    ),
    "failed_qualification_terminal_id": (
        "sha256:4fb8d565a674a917aa099d953690af8c"
        "8b6d99d329d340d00b8967ebcb3d2828"
    ),
    "old_no_additional_measurement_rule_overridden": True,
    "maximum_measurements_per_task": 1,
    "automatic_retry_count": 0,
    "provider_reported_prompt_tokens_required": True,
    "usage_unavailable_status": "FAILED_USAGE_UNAVAILABLE",
    "context_budget_tokens": 200000,
    "qualification_ordinal_credit": False,
    "qualification_evidence_eligible": False,
    "response_reuse_for_qualification": False,
    "publication_eligible": False,
    "consumes_authorization_after_any_egress_marker": True,
    "concrete_grant_requires_independent_exact_head_review": True,
    "qualification_requires_both_scope_bound_context_attestations": True,
}
ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_POLICY = {
    **ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY,
    "policy_status": (
        "SCOPE_BOUND_MEASUREMENTS_CONSUMED_ATTESTATIONS_ACCEPTED"
    ),
}
ISSUE_15_D07_HISTORICAL_CONTEXT_ATTESTATIONS = [
    {
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_occupancy_table_v2",
        "attestation_id": (
            "sha256:dc8cb1d152cc42b5b438e4db33fe0360"
            "6766b8d7ec1b4bc11bd92273cbbd9e60"
        ),
        "measurement_evidence_id": (
            "sha256:bd5c4e1e1fb302ce539c2ae7aa88b67c"
            "2b366c419436253b9ebb56f56dbf9795"
        ),
        "actual_prompt_tokens": 160937,
        "context_budget_tokens": 200000,
    },
    {
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_revpar_table_v2",
        "attestation_id": (
            "sha256:d3824ed29716596cbb4b997462d3974c8"
            "c36f429555dd35d84f62b8b137a9c42"
        ),
        "measurement_evidence_id": (
            "sha256:9a3d6072a7ce640d510ad8a9451e075f8"
            "659c078715a5eaae97b2ef51ffff2cd"
        ),
        "actual_prompt_tokens": 160928,
        "context_budget_tokens": 200000,
    },
]
ISSUE_15_D07_SCHEMA_V2_CONTEXT_ATTESTATIONS = [
    {
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_occupancy_table_v2",
        "attestation_id": (
            "sha256:9acc0d3ea50509eb9a41fbac0cadae8e"
            "2b5c956bba0af0c2c66514a8f667fcd5"
        ),
        "measurement_evidence_id": (
            "sha256:b4bc0aaa3f1dbad06f5a29018c00e9b9"
            "01d47ad2fae66acbc6c5076c8e7d3eec"
        ),
        "actual_prompt_tokens": 161181,
        "context_budget_tokens": 200000,
    },
    {
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_revpar_table_v2",
        "attestation_id": (
            "sha256:3504b836a787865c8b7e874275ee7974"
            "ccad7e2342086c5b8b0922653a71cfb1"
        ),
        "measurement_evidence_id": (
            "sha256:0d453606d154eec76bb93cbcf69747af6"
            "58cc8e9f704e8794ad944446b96d950"
        ),
        "actual_prompt_tokens": 161167,
        "context_budget_tokens": 200000,
    },
]
ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS = [
    {
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_occupancy_table_v2",
        "attestation_id": (
            "sha256:ae0a2bee7bbccae2007566413688a9b3f"
            "605e6eeabe63cf32891a76229c08715"
        ),
        "measurement_evidence_id": (
            "sha256:0399b5034d4920a31d9391f36870eb640"
            "7a39e943454147f0e6b7f33c9813825"
        ),
        "actual_prompt_tokens": 161282,
        "context_budget_tokens": 200000,
    },
    {
        "family_id": "lodging_kpi_table",
        "task_contract_id": "lodging_revpar_table_v2",
        "attestation_id": (
            "sha256:52d243db14cdfb95507393451cd2a23f9"
            "c278853cc24e15ed0bce5100799daee"
        ),
        "measurement_evidence_id": (
            "sha256:7679c5d712f4635b5b31ba2f4e666108"
            "5dc09a8498b9b40929f308a964dfaa42"
        ),
        "actual_prompt_tokens": 161263,
        "context_budget_tokens": 200000,
    },
]
ISSUE_15_D07_LIVE_QUALIFICATION_SCOPE = {
    "authorized_family_ids": ["lodging_kpi_table"],
    "authorized_task_contract_ids": [
        "lodging_occupancy_table_v2",
        "lodging_revpar_table_v2",
    ],
    "second_layout_fixture_id": "hilton-2024-sec-layout-v7",
    "post_freeze_holdout_fixture_id": "hyatt-2025-sec-holdout-v2",
    "fresh_samples_required": 3,
    "sample_sequence": [
        "SECOND_LAYOUT",
        "PRODUCTION_SEMANTIC_FREEZE",
        "POST_FREEZE_HOLDOUT",
        "FRESH_STABILITY_1",
        "FRESH_STABILITY_2",
        "FRESH_STABILITY_3",
    ],
    "current_content_addressed_freeze_required": True,
    "current_stage_a_snapshot_required": True,
    "new_provider_execution_per_sample_required": True,
    "measurement_response_reuse_for_qualification": False,
    "provider_usage_required": True,
    "actual_prompt_tokens_max": 200000,
    "authorized_context_evidence_bases": [
        "ESTIMATED_BOUND",
        "PROVIDER_REPORTED_EXACT_BINDING",
        "EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE",
    ],
    "unattested_over_estimated_bound_phase": "POST_FREEZE_HOLDOUT",
    "unattested_over_estimated_bound_requires_exact_review": True,
    "missing_or_excess_usage_terminal_no_retry": True,
    "independent_exact_head_review_required_before_first_egress": True,
    "financial_qualification_authorized": False,
}
ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY = {
    "attestation_record_type": "TABLE_CONTEXT_FEASIBILITY_ATTESTATION",
    "accepted_measurement_evidence_id": (
        "sha256:0399b5034d4920a31d9391f36870eb640"
        "7a39e943454147f0e6b7f33c9813825"
    ),
    "accepted_provider": "deepseek",
    "accepted_model": "deepseek-v4-flash",
    "accepted_api": "chat_completions",
    "accepted_actual_prompt_tokens": 161282,
    "context_budget_tokens": 200000,
    "context_headroom_tokens": 38718,
    "default_path": {
        "condition": "estimated_input_tokens <= 200000",
        "result": "PASS",
        "evidence_basis": "ESTIMATED_BOUND",
    },
    "exact_attestation_path": {
        "estimated_condition": "estimated_input_tokens > 200000",
        "actual_condition": "attested_actual_prompt_tokens <= 200000",
        "required_exact_equalities": [
            "provider_request_body_sha256",
            "family_id",
            "task_contract_id",
            "source_identity",
            "source_repo_relative_path",
            "source_sha256",
            "serializer_identity",
            "serializer_hash",
            "task_contract_hash",
            "prompt_hash",
            "output_schema_hash",
            "provider",
            "model",
            "api",
            "requirement_closure_hash",
            "protected_closure_hash",
        ],
        "result": "PASS",
        "evidence_basis": "PROVIDER_REPORTED_EXACT_BINDING",
    },
    "non_exact_equivalence_forbidden": [
        "APPROXIMATE_RATIO",
        "SIMILAR_BYTE_LENGTH",
        "SAME_FAMILY",
        "SAME_SOURCE",
        "SAME_SERIALIZER_VERSION",
        "SHARED_TABLE_PAYLOAD",
    ],
    "attestation_scope": "ONE_EXACT_TASK_REQUEST",
    "attestation_semantics": "CONTEXT_FEASIBILITY_ONLY",
    "measurement_authorization_permanently_consumed": True,
    "additional_measurement_authorized": False,
    "measurement_response_qualification_credit": False,
    "measurement_response_reuse_for_qualification": False,
    "qualification_requires_separate_authorization": True,
    "qualification_requires_new_provider_execution": True,
    "future_qualification_usage_required": True,
    "future_qualification_actual_prompt_tokens_max": 200000,
    "future_qualification_usage_failure_policy": (
        "TERMINAL_NO_RETRY_STOP_LATER_ORDINALS"
    ),
}
ISSUE_15_D07_EFFECTIVE_CHOICE = {
    "reader_table_set": "ALL_DOCUMENT_TABLE_GRIDS_IN_DOCUMENT_ORDER",
    "semantic_prefilter": False,
    "selector_authorized": False,
    "estimator_id": "utf8_byte_upper_bound",
    "estimator_version": "1",
    "max_estimated_input_tokens": 200000,
    "threshold_comparison": {
        "passes": "estimated_input_tokens <= 200000",
        "blocks": "estimated_input_tokens > 200000",
    },
    "threshold_scope": "PER_FAMILY_PER_REQUEST",
    "oversized_payload_policy": (
        "BLOCK_LIVE_QUALIFICATION_FOR_AFFECTED_FAMILY"
    ),
    "shared_dependency_drift_policy": (
        "INVALIDATE_ALL_DEPENDENT_FAMILIES"
    ),
    "family_local_drift_policy": "INVALIDATE_OWNER_FAMILY_ONLY",
    "lossless_context_minimization_precedes_semantic_selection": True,
    "actual_prompt_tokens_authority": (
        "PROVIDER_USAGE_WHEN_A_LATER_LIVE_CALL_IS_SEPARATELY_AUTHORIZED"
    ),
    "live_measurement_authorized": False,
    "live_qualification_authorized": False,
    "measurement_exception": ISSUE_15_D07_MEASUREMENT_EXCEPTION,
    "context_feasibility_policy": ISSUE_15_D07_CONTEXT_FEASIBILITY_POLICY,
    "revpar_measurement_exception": (
        ISSUE_15_D07_REVPAR_MEASUREMENT_EXCEPTION
    ),
    "accepted_context_attestations": (
        ISSUE_15_D07_ACCEPTED_CONTEXT_ATTESTATIONS
    ),
    "revpar_measurement_authorization_permanently_consumed": True,
    "live_qualification_scope": ISSUE_15_D07_LIVE_QUALIFICATION_SCOPE,
    "revised_prompt_measurement_policy": (
        ISSUE_15_D07_REVISED_PROMPT_MEASUREMENT_POLICY
    ),
    "schema_revised_measurement_policy": (
        ISSUE_15_D07_SCOPE_BOUND_MEASUREMENT_GRANT_POLICY
    ),
}
ISSUE_15_POST_FREEZE_DECISION_EVIDENCE_BY_ID = {
    "D-07": (
        "https://github.com/wlvh/SEC_metrics/pull/22"
        "#issuecomment-5422296601"
    ),
    "D-26": (
        "https://github.com/wlvh/SEC_metrics/issues/15"
        "#issuecomment-5340538535"
    ),
    "D-35": (
        "https://github.com/wlvh/SEC_metrics/issues/15"
        "#issuecomment-5340538535"
    ),
    "D-36": (
        "https://github.com/wlvh/SEC_metrics/issues/15"
        "#issuecomment-5340538535"
    ),
}
ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES = {
    "D-07": (
        "sha256:fc307fe113e94f1111ccc5b2a1bc8a6c"
        "62a8bb955e20c078e36edec1e15a3571"
    ),
    "D-26": (
        "sha256:f7186286693e9c9b2ec4bb9084060468ef1629d3ad3b06e53510efbf2d74b938"
    ),
    "D-35": (
        "sha256:6e966a51833c5f1d4fd25e5b8520dfb46414a64e4b868ce4d8181f2b8ac1de04"
    ),
    "D-36": (
        "sha256:468b7ef6528f4d76de56a71bcba4c913e47e858eefdba55129554ddaf845af1e"
    ),
}
ISSUE_15_BASE_PIPELINE_SHA256 = (
    "f62bd3dba3a140002d0d4e74912876ff5972d785a4a029f80d5a75dfbb89b438"
)
ISSUE_15_EXPECTED_PRODUCER_EXACT_SET_HASH = (
    "sha256:ce657cb8cc25fd4d665b04ed2c66e027b765d9a36f1090d3eb8e4f9e07f3710a"
)
ISSUE_15_EXPECTED_SHARED_EXACT_SET_HASH = (
    "sha256:e148bac50da7d86389ac3181d65f8420f77f0db06e0aeb59c898260883d2eb96"
)
ISSUE_15_EXPECTED_PRODUCER_RECORD_SET_HASH = (
    "sha256:878b250692dca379557103ff2bed213aeefb256c7c9ce35c6b2be3e991c9afbe"
)
ISSUE_15_EXPECTED_SEMANTIC_RECORD_SET_HASH = (
    "sha256:c2bca333c4dd470f153a1aeb6fb231acb92af14d9f917666e72431fe66b6cc75"
)
ISSUE_15_EXPECTED_SEMANTIC_PRODUCER_COUNT = 116
ISSUE_15_EXPECTED_SHARED_PLUMBING_COUNT = 20
ISSUE_15_EXPECTED_SCOPE_EVIDENCE_HASH = (
    "sha256:cdbfa3e6466dd44a1d1ce59f5a3a22c4a343daa795125214b3c65d759acfb3d0"
)


class RequirementError(ValueError):
    """Report missing, changed, ambiguous, or malformed requirement bytes."""


def load_run_requirement_snapshot(
    *, repo_root: Path, task_contract_bindings: object,
) -> Dict[str, object]:
    """Load the Requirement authority mechanically selected by one Run type.

    Args:
        repo_root: Repository owning both supported immutable snapshots.
        task_contract_bindings: Run manifest's explicit catalog-task bindings.

    Returns:
        Issue #15 authority for catalog table-task Runs; otherwise the retained
        parent authority for historical disclosure Runs.

    Raises:
        RequirementError: When the Run binding shape is invalid or its selected
        snapshot cannot be loaded from the repository.

    Why:
        A catalog task is governed by Issue #15's effective decisions, while a
        historical disclosure Run remains replayable under its inherited
        parent.  Choosing from the persisted task-binding shape avoids letting
        a later caller select a policy at creation, review, or replay time.
    """
    if type(task_contract_bindings) is not list:
        raise RequirementError("Run task contract bindings are invalid")
    requirement_id = (
        ISSUE_15_REQUIREMENT_ID
        if task_contract_bindings
        else PARENT_REQUIREMENT_ID
    )
    snapshot_dir = repo_root / "requirements" / requirement_id
    requirement = load_requirement_snapshot(snapshot_dir=snapshot_dir)
    if requirement["requirement_id"] != requirement_id:
        raise RequirementError("Run Requirement authority identity differs")
    return requirement


def _read_object(*, path: Path) -> Dict[str, object]:
    """Read a strict JSON object from one Requirement file.

    Args:
        path: Existing regular JSON file.

    Returns:
        Isolated root mapping.
    """
    parsed = strict_json_file(path=path)
    if not isinstance(parsed, dict):
        raise RequirementError("Requirement JSON root must be an object")
    return dict(parsed)


def _decision_record_hash(*, decision: Mapping[str, object]) -> str:
    """Return the audit identity used by a later superseding decision.

    Args:
        decision: Exact immutable decision record.

    Returns:
        Canonical content hash.
    """
    return content_hash(value=dict(decision))


def _validate_decision(*, decision: Mapping[str, object]) -> Dict[str, object]:
    """Validate one historical pending or terminal decision-chain record.

    Args:
        decision: Candidate decision mapping.

    Returns:
        Isolated record.

    Raises:
        RequirementError: On schema, state, identity, or UTC drift.
    """
    pending = {
        "decision_id",
        "effect",
        "evidence",
        "required_choice_fields",
        "status",
    }
    if set(decision) == pending:
        if decision["status"] != "PENDING_EXTERNAL_APPROVAL":
            raise RequirementError("Pending Decision status is invalid")
        for key in ("decision_id", "effect", "evidence"):
            if not isinstance(decision[key], str) or not decision[key]:
                raise RequirementError(
                    "Pending Decision field is empty: {}".format(key)
                )
        fields = decision["required_choice_fields"]
        if (
            not isinstance(fields, list)
            or not fields
            or any(not isinstance(item, str) or not item for item in fields)
            or len(fields) != len(set(fields))
        ):
            raise RequirementError("Pending Decision required fields are invalid")
        return dict(decision)
    required = {
        "approved_at_utc",
        "approved_by",
        "choice",
        "decision_id",
        "evidence",
        "status",
        "supersedes_decision_id",
    }
    if set(decision) != required:
        raise RequirementError("Decision fields are not exact")
    for key in ("approved_at_utc", "approved_by", "decision_id", "evidence"):
        if not isinstance(decision[key], str) or not decision[key]:
            raise RequirementError("Decision field is empty: {}".format(key))
    try:
        parse_utc_timestamp(value=str(decision["approved_at_utc"]))
    except CanonicalError as error:
        raise RequirementError("Decision timestamp must be UTC") from error
    if decision["status"] not in {"APPROVED", "REJECTED", "SUPERSEDED"}:
        raise RequirementError("Decision status is invalid")
    if not isinstance(decision["choice"], dict):
        raise RequirementError("Decision choice must be an object")
    parent = decision["supersedes_decision_id"]
    if parent is not None and (not isinstance(parent, str) or not parent):
        raise RequirementError("Decision supersedes identity is invalid")
    return dict(decision)


def _decision_parent(*, decision: Mapping[str, object]) -> Optional[str]:
    """Return the predecessor hash for either supported history record.

    Args:
        decision: Validated pending or terminal record.

    Returns:
        ``None`` for the historical pending root, otherwise the named parent.
    """
    if decision["status"] == "PENDING_EXTERNAL_APPROVAL":
        return None
    return decision["supersedes_decision_id"]


def _resolve_decisions(
    *, decisions: Sequence[Mapping[str, object]]
) -> tuple[Dict[str, Dict[str, object]], Dict[str, List[Dict[str, object]]]]:
    """Resolve unique effective tips and preserve every ordered chain.

    Args:
        decisions: Historical pending roots plus terminal records.

    Returns:
        Effective tips and root-to-tip audit chains by Decision ID.
    """
    groups: Dict[str, List[Dict[str, object]]] = {}
    for candidate in decisions:
        decision = _validate_decision(decision=candidate)
        groups.setdefault(str(decision["decision_id"]), []).append(decision)
    effective: Dict[str, Dict[str, object]] = {}
    chains: Dict[str, List[Dict[str, object]]] = {}
    for decision_id, records in groups.items():
        by_hash = {_decision_record_hash(decision=record): record for record in records}
        if len(by_hash) != len(records):
            raise RequirementError("Decision chain contains duplicate bytes")
        children: Dict[Optional[str], List[str]] = {}
        for record_hash, record in by_hash.items():
            parent = _decision_parent(decision=record)
            if parent is not None and parent not in by_hash:
                raise RequirementError("Decision chain has a detached parent")
            children.setdefault(parent, []).append(record_hash)
        roots = children[None] if None in children else []
        if len(roots) != 1:
            raise RequirementError("Decision chain must have one root")
        current = roots[0]
        visited = set()
        ordered = []
        while True:
            if current in visited:
                raise RequirementError("Decision chain contains a cycle")
            visited.add(current)
            ordered.append(by_hash[current])
            next_records = children[current] if current in children else []
            if len(next_records) > 1:
                raise RequirementError("Parallel effective decisions fail closed")
            if not next_records:
                break
            current = next_records[0]
        if len(visited) != len(records):
            raise RequirementError("Decision chain is disconnected")
        tip = by_hash[current]
        if tip["status"] == "SUPERSEDED":
            raise RequirementError("Effective decision cannot be SUPERSEDED")
        effective[decision_id] = tip
        chains[decision_id] = ordered
    return effective, chains


def effective_decisions(
    *, decisions: Sequence[Mapping[str, object]]
) -> Dict[str, Dict[str, object]]:
    """Resolve one effective tip for every Decision Register decision ID.

    Args:
        decisions: Immutable records in register order. A superseding record
            names the canonical hash of the exact previous record.

    Returns:
        Decision ID to unique effective non-superseded record.

    Raises:
        RequirementError: On detached, cyclic, duplicate, or parallel chains.
    """
    effective, _chains = _resolve_decisions(decisions=decisions)
    return effective


def _load_ai_first_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Verify the immutable parent AI-first Requirement Snapshot.

    Args:
        snapshot_dir: ``requirements/ai_first_v3_3_1`` directory.

    Returns:
        Hashes, baseline, effective decisions, pending D-01 state, and one
        requirement closure hash.

    Raises:
        RequirementError: On unsafe files, changed bytes, or invalid register.
    """
    paths = {key: snapshot_dir / relative for key, relative in SNAPSHOT_FILES.items()}
    for key in paths:
        if paths[key].is_symlink() or not paths[key].is_file():
            raise RequirementError("Requirement file is unsafe: {}".format(key))
    baseline = _read_object(path=paths["baseline"])
    register = _read_object(path=paths["decisions"])
    if baseline["fsd_sha256"] != sha256_file(path=paths["fsd"]):
        raise RequirementError("FSD bytes differ from baseline")
    if baseline["fsd_sha256"] != FSD_SHA256:
        raise RequirementError("FSD bytes differ from approved v3.3.1")
    if baseline["issue_body_sha256"] != sha256_file(path=paths["issue"]):
        raise RequirementError("Issue Contract bytes differ from baseline")
    if baseline["r3_addendum_sha256"] != sha256_file(path=paths["r3_addendum"]):
        raise RequirementError("R3 Addendum bytes differ from baseline")
    if baseline["decision_register_sha256"] != sha256_file(path=paths["decisions"]):
        raise RequirementError("Decision Register bytes differ from baseline")
    if baseline["legacy_path_inventory_sha256"] != sha256_file(
        path=paths["legacy_inventory"]
    ):
        raise RequirementError("Legacy inventory bytes differ from baseline")
    required_register = {
        "decisions",
        "issue_contract_revision",
        "pending_decisions",
        "requirement_id",
        "schema_version",
    }
    if set(register) != required_register:
        raise RequirementError("Decision Register fields are not exact")
    if not isinstance(register["decisions"], list):
        raise RequirementError("Decision Register decisions must be an array")
    if not isinstance(register["pending_decisions"], list):
        raise RequirementError("Pending decisions must be an array")
    all_decisions = list(register["decisions"])
    all_decisions.extend(register["pending_decisions"])
    decisions, chains = _resolve_decisions(decisions=all_decisions)
    pending_ids = sorted(
        decision_id
        for decision_id, decision in decisions.items()
        if decision["status"] == "PENDING_EXTERNAL_APPROVAL"
    )
    repo_root = snapshot_dir.parents[1]
    release_plan_path = repo_root / "config" / "vnext_release_plan.json"
    if not release_plan_path.is_file():
        release_plan_path = Path(__file__).resolve().parents[2] / (
            "config/vnext_release_plan.json"
        )
    if (
        release_plan_path.is_symlink()
        or not release_plan_path.is_file()
        or baseline["release_plan_sha256"] != sha256_file(path=release_plan_path)
    ):
        raise RequirementError("Release plan bytes differ from baseline")
    if baseline["semantic_runtime_versions"] != SEMANTIC_VERSIONS:
        raise RequirementError("Semantic runtime versions differ")
    semantic_versions_hash = content_hash(value=SEMANTIC_VERSIONS)
    if baseline["semantic_runtime_versions_hash"] != semantic_versions_hash:
        raise RequirementError("Semantic runtime version hash differs")
    hashes = {
        "baseline_sha256": sha256_file(path=paths["baseline"]),
        "decision_register_sha256": sha256_file(path=paths["decisions"]),
        "fsd_sha256": sha256_file(path=paths["fsd"]),
        "issue_body_sha256": sha256_file(path=paths["issue"]),
        "r3_addendum_sha256": sha256_file(path=paths["r3_addendum"]),
        "legacy_path_inventory_sha256": sha256_file(path=paths["legacy_inventory"]),
        "release_plan_sha256": sha256_file(path=release_plan_path),
        "semantic_runtime_versions_hash": semantic_versions_hash,
    }
    return {
        "requirement_id": register["requirement_id"],
        "issue_contract_revision": register["issue_contract_revision"],
        "hashes": hashes,
        "requirement_closure_hash": content_hash(value=hashes),
        "baseline": baseline,
        "effective_decisions": decisions,
        "decision_chains": chains,
        "pending_decision_ids": pending_ids,
    }


def _require_exact_fields(
    *, value: Mapping[str, object], fields: set[str], label: str,
) -> None:
    """Require one mapping to expose an exact field set.

    Args:
        value: Mapping whose schema is frozen by the Requirement contract.
        fields: Exact allowed and required keys.
        label: Stable diagnostic name for the mapping.

    Raises:
        RequirementError: When a required field is missing or extra.
    """
    if set(value) != fields:
        raise RequirementError("{} fields are not exact".format(label))


def _issue_15_paths(*, snapshot_dir: Path) -> Dict[str, Path]:
    """Return and validate every Issue #15 snapshot file locator.

    Args:
        snapshot_dir: Candidate ``requirements/issue_15_v1`` directory.

    Returns:
        Stable role-to-path mapping for the seven frozen WB-1 files.
    """
    paths = {
        key: snapshot_dir / relative
        for key, relative in ISSUE_15_SNAPSHOT_FILES.items()
    }
    for key in paths:
        if paths[key].is_symlink() or not paths[key].is_file():
            raise RequirementError(
                "Issue #15 Requirement file is unsafe: {}".format(key)
            )
    return paths


def _bound_repository_file(*, repository_root: Path, relative: str) -> Path:
    """Return one safe regular repository file without following symlinks.

    Args:
        repository_root: Root containing the ``requirements`` and ``outputs``
            directories for the snapshot under verification.
        relative: POSIX-style repository-relative receipt path.

    Returns:
        Existing regular file named by the binding.

    Raises:
        RequirementError: When the locator escapes the repository, traverses
            a symlink, or does not end at a regular file.
    """
    locator = Path(relative)
    if (
        not relative
        or locator.is_absolute()
        or ".." in locator.parts
        or "." in locator.parts
    ):
        raise RequirementError("Foundation receipt path is unsafe")
    candidate = repository_root
    for part in locator.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise RequirementError(
                "Foundation receipt path traverses a symlink: {}".format(relative)
            )
    if not candidate.exists() or not stat.S_ISREG(candidate.stat().st_mode):
        raise RequirementError(
            "Foundation receipt path is not a regular file: {}".format(relative)
        )
    return candidate


def _validate_foundation_receipt_bindings(
    *, foundation: Mapping[str, object], repository_root: Path,
) -> None:
    """Verify every foundation receipt binding against committed bytes.

    Args:
        foundation: Frozen ``foundation_verification_receipt.json`` object.
        repository_root: Repository root used by the Requirement snapshot.

    Expected output:
        Each declared receipt is a non-symlink regular file with exact size
        and SHA-256, and every command receipt locator belongs to that set.

    Raises:
        RequirementError: On malformed, missing, unsafe, unbound, or changed
            evidence bytes.
    """
    bindings = foundation["receipt_bindings"]
    commands = foundation["verification_commands"]
    if not isinstance(bindings, list) or not isinstance(commands, list):
        raise RequirementError("Foundation receipt bindings are invalid")
    bound_paths = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            raise RequirementError("Foundation receipt binding is invalid")
        _require_exact_fields(
            value=binding,
            fields={"path", "receipt_id", "sha256", "size"},
            label="Foundation receipt binding",
        )
        relative = binding["path"]
        if (
            not isinstance(relative, str)
            or relative in bound_paths
            or not isinstance(binding["receipt_id"], str)
            or not binding["receipt_id"]
            or not isinstance(binding["sha256"], str)
            or not isinstance(binding["size"], int)
            or binding["size"] < 0
        ):
            raise RequirementError("Foundation receipt binding value is invalid")
        path = _bound_repository_file(
            repository_root=repository_root, relative=relative,
        )
        if binding["size"] != path.stat().st_size or binding["sha256"] != sha256_file(
            path=path
        ):
            raise RequirementError(
                "Foundation receipt bytes differ: {}".format(relative)
            )
        bound_paths.add(relative)
    for command in commands:
        if not isinstance(command, dict):
            raise RequirementError("Foundation verification command is invalid")
        receipt_paths = command["receipt_paths"]
        if (
            not isinstance(receipt_paths, list)
            or not receipt_paths
            or any(not isinstance(path, str) for path in receipt_paths)
            or not set(receipt_paths).issubset(bound_paths)
        ):
            raise RequirementError(
                "Foundation command receipt paths are not binding-closed"
            )


def _parent_inventory_identity(*, group: str, symbol: str) -> str:
    """Return the historical file::symbol identity for one parent member.

    Args:
        group: Parent inventory migration-rule group.
        symbol: Exact member stored in that group.

    Returns:
        Repository-relative file::symbol identity used by child dispositions.
    """
    if group == "legacy_configuration_keys":
        return "config/metric_applicability.yaml::{}".format(symbol)
    return "scripts/sec_pipeline.py::{}".format(symbol)


def _validate_issue_15_scope_evidence(
    *,
    inventory: Mapping[str, object],
    producer_by_id: Mapping[str, Mapping[str, object]],
    semantic_id_set: set[str],
    metric_id_set: set[str],
) -> None:
    """Match reusable producer scopes to frozen call-graph evidence groups.

    Args:
        inventory: Child producer inventory containing scope evidence.
        producer_by_id: Validated producer records keyed by ``file::symbol``.
        semantic_id_set: Externally closed semantic producer identity set.
        metric_id_set: Exact 39-metric authority set.

    Expected output:
        Every evidence-marked producer scope equals the union of its referenced
        code-audited groups, and every group is used by at least one producer.

    Raises:
        RequirementError: On malformed evidence, dangling groups, or producer
            scope that differs from the code-level derivation receipt.
    """
    groups = inventory["scope_evidence_groups"]
    evidence_by_producer = inventory["scope_evidence_by_producer"]
    if not isinstance(groups, list) or not isinstance(evidence_by_producer, dict):
        raise RequirementError("Issue #15 producer scope evidence is invalid")
    group_fields = {
        "active_metric_ids",
        "callee_id",
        "call_sites",
        "caller_id",
        "evidence_id",
        "evidence_type",
        "period_kind",
        "retired_metric_ids",
    }
    group_by_id: Dict[str, Dict[str, object]] = {}
    for group in groups:
        if not isinstance(group, dict):
            raise RequirementError("Issue #15 scope evidence group is invalid")
        _require_exact_fields(
            value=group, fields=group_fields, label="Issue #15 scope evidence group",
        )
        evidence_id = group["evidence_id"]
        active = group["active_metric_ids"]
        retired = group["retired_metric_ids"]
        call_sites = group["call_sites"]
        if (
            not isinstance(evidence_id, str)
            or not evidence_id
            or evidence_id in group_by_id
            or group["evidence_type"]
            not in {
                "DIRECT_METRIC_ARGUMENT",
                "DIRECT_PREDICATE_CALLSITES",
                "METRIC_SET_CONSTANT",
                "SELECTION_CALLSITES",
            }
            or group["period_kind"] not in {"duration", "instant", "NOT_APPLICABLE"}
            or not isinstance(group["caller_id"], str)
            or not group["caller_id"]
            or not isinstance(group["callee_id"], str)
            or not group["callee_id"]
            or not isinstance(call_sites, list)
            or not call_sites
            or call_sites != sorted(set(call_sites))
            or any(not isinstance(site, str) or ":" not in site for site in call_sites)
            or not isinstance(active, list)
            or not isinstance(retired, list)
            or active != sorted(set(active))
            or retired != sorted(set(retired))
            or set(active) & set(retired)
            or not (set(active) | set(retired)).issubset(metric_id_set)
        ):
            raise RequirementError("Issue #15 scope evidence group differs")
        group_by_id[evidence_id] = group
    if [row["evidence_id"] for row in groups] != sorted(group_by_id):
        raise RequirementError("Issue #15 scope evidence groups are not ordered")

    evidence_fields = {
        "active_metric_ids",
        "derivation",
        "evidence_group_ids",
        "retired_metric_ids",
    }
    referenced_groups = set()
    for producer_id, evidence in evidence_by_producer.items():
        if producer_id not in semantic_id_set or not isinstance(evidence, dict):
            raise RequirementError("Issue #15 scoped producer is invalid")
        _require_exact_fields(
            value=evidence,
            fields=evidence_fields,
            label="Issue #15 producer scope evidence",
        )
        evidence_group_ids = evidence["evidence_group_ids"]
        if (
            evidence["derivation"] != "UNION_OF_SCOPE_EVIDENCE_GROUPS"
            or not isinstance(evidence_group_ids, list)
            or not evidence_group_ids
            or evidence_group_ids != sorted(set(evidence_group_ids))
            or not set(evidence_group_ids).issubset(group_by_id)
        ):
            raise RequirementError("Issue #15 producer scope derivation differs")
        selected_groups = [group_by_id[group_id] for group_id in evidence_group_ids]
        derived_active = sorted(
            {
                metric_id
                for group in selected_groups
                for metric_id in group["active_metric_ids"]
            }
        )
        derived_retired = sorted(
            {
                metric_id
                for group in selected_groups
                for metric_id in group["retired_metric_ids"]
            }
        )
        producer = producer_by_id[producer_id]
        if (
            evidence["active_metric_ids"] != derived_active
            or evidence["retired_metric_ids"] != derived_retired
            or producer["active_metric_ids"] != derived_active
            or producer["retired_metric_ids"] != derived_retired
        ):
            raise RequirementError(
                "Issue #15 code-derived producer scope differs: {}".format(producer_id)
            )
        referenced_groups.update(evidence_group_ids)
    if referenced_groups != set(group_by_id):
        raise RequirementError("Issue #15 scope evidence group is unreferenced")

    edges = inventory["scope_transitive_edges"]
    excluded_callers = inventory["scope_excluded_callers"]
    if not isinstance(edges, list) or not isinstance(excluded_callers, dict):
        raise RequirementError("Issue #15 scope call-graph closure is invalid")
    edge_fields = {"callee_id", "caller_id", "call_site", "period_kind_flow"}
    edge_identities = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise RequirementError("Issue #15 scope edge is invalid")
        _require_exact_fields(
            value=edge, fields=edge_fields, label="Issue #15 scope edge",
        )
        identity = (edge["caller_id"], edge["callee_id"], edge["call_site"])
        if identity in edge_identities or edge["period_kind_flow"] not in {
            "GUARD::duration",
            "GUARD::instant",
            "PASSTHROUGH",
        }:
            raise RequirementError("Issue #15 scope edge differs")
        edge_identities.add(identity)
    if any(
        not isinstance(caller_id, str)
        or reason not in {"TRANSITIVE_WRAPPER", "VALIDATION_ONLY"}
        for caller_id, reason in excluded_callers.items()
    ):
        raise RequirementError("Issue #15 excluded scope caller differs")


def _validate_issue_15_producer_inventory(
    *,
    inventory: Mapping[str, object],
    parent_inventory: Mapping[str, object],
    source_strategy: Mapping[str, object],
) -> None:
    """Verify the externally closed Issue #15 producer authority.

    Args:
        inventory: Child ``legacy_semantic_producer_inventory.json`` object.
        parent_inventory: Exact parent legacy inventory object.
        source_strategy: Mechanically generated 39-metric baseline receipt.

    Expected output:
        The audited base source, semantic/shared exact sets, active/retired
        scopes, parent groups, per-parent-symbol dispositions, and metric
        coverage all match independently maintained loader authority.

    Raises:
        RequirementError: On source drift, self-only closure, missing parent
            accounting, scope drift, or malformed producer records.
    """
    inventory_fields = {
        "audit_basis",
        "audit_granularity",
        "baseline_source_commit",
        "baseline_source_tree",
        "coverage_by_metric",
        "covered_metric_ids",
        "created_at_utc",
        "disposition_definitions",
        "metric_id_set",
        "metric_id_set_hash",
        "mutable_legacy_retirement_config_ledger",
        "parent_inventory_groups",
        "parent_legacy_inventory_path",
        "parent_legacy_inventory_sha256",
        "parent_symbol_dispositions",
        "producer_exact_set_hash",
        "producer_kinds",
        "producer_record_set_hash",
        "producer_source_files",
        "producers",
        "reachability_proof",
        "record_type",
        "requirement_id",
        "retirement_evidence_chain",
        "schema_version",
        "scope_evidence_by_producer",
        "scope_evidence_groups",
        "scope_excluded_callers",
        "scope_transitive_edges",
        "semantic_producer_count",
        "semantic_producer_record_set_hash",
        "shared_plumbing_count",
        "shared_plumbing_exact_set_hash",
    }
    _require_exact_fields(
        value=inventory, fields=inventory_fields, label="Issue #15 producer inventory",
    )
    if (
        inventory["schema_version"] != 2
        or inventory["record_type"] != "ISSUE_15_LEGACY_SEMANTIC_PRODUCER_INVENTORY"
        or inventory["requirement_id"] != ISSUE_15_REQUIREMENT_ID
        or inventory["audit_granularity"] != "FILE_SYMBOL_SEMANTIC_DECISION"
        or inventory["baseline_source_commit"] != ISSUE_15_FOUNDATION_MERGE_COMMIT
        or inventory["baseline_source_tree"]
        != "46e47a219f077f5561e373bc3cb69bdfe23ee065"
        or inventory["parent_legacy_inventory_path"]
        != "requirements/ai_first_v3_3_1/legacy_path_inventory.json"
        or inventory["producer_kinds"] != ["SEMANTIC_PRODUCER", "SHARED_PLUMBING"]
        or inventory["mutable_legacy_retirement_config_ledger"] is not False
    ):
        raise RequirementError("Issue #15 producer authority differs")
    audit_basis = inventory["audit_basis"]
    if not isinstance(audit_basis, dict):
        raise RequirementError("Issue #15 producer audit basis is invalid")
    _require_exact_fields(
        value=audit_basis,
        fields={
            "exact_base_commit",
            "exact_base_tree",
            "semantic_inclusion_rule",
            "shared_plumbing_rule",
        },
        label="Issue #15 producer audit basis",
    )
    if (
        audit_basis["exact_base_commit"] != ISSUE_15_FOUNDATION_MERGE_COMMIT
        or audit_basis["exact_base_tree"] != "46e47a219f077f5561e373bc3cb69bdfe23ee065"
        or not audit_basis["semantic_inclusion_rule"]
        or not audit_basis["shared_plumbing_rule"]
    ):
        raise RequirementError("Issue #15 producer audit basis differs")
    reachability = inventory["reachability_proof"]
    if not isinstance(reachability, dict):
        raise RequirementError("Issue #15 reachability proof is invalid")
    _require_exact_fields(
        value=reachability,
        fields={"matrix_write_guard", "role", "statement"},
        label="Issue #15 reachability proof",
    )
    if (
        reachability["role"] != "SUPPLEMENTAL_DOMINATOR_ONLY"
        or reachability["matrix_write_guard"]
        != "scripts/sec_pipeline.py::assert_legacy_candidate_rows"
        or not reachability["statement"]
    ):
        raise RequirementError("Issue #15 reachability proof differs")
    scope_closure = {
        "scope_evidence_by_producer": inventory["scope_evidence_by_producer"],
        "scope_evidence_groups": inventory["scope_evidence_groups"],
        "scope_excluded_callers": inventory["scope_excluded_callers"],
        "scope_transitive_edges": inventory["scope_transitive_edges"],
    }
    if content_hash(value=scope_closure) != ISSUE_15_EXPECTED_SCOPE_EVIDENCE_HASH:
        raise RequirementError("Issue #15 producer scope evidence differs")

    source_files = inventory["producer_source_files"]
    if not isinstance(source_files, dict):
        raise RequirementError("Issue #15 producer source bindings are invalid")
    runtime_root = Path(__file__).parents[2]
    for relative, binding in source_files.items():
        if not isinstance(relative, str) or not isinstance(binding, dict):
            raise RequirementError("Issue #15 producer source binding is invalid")
        _require_exact_fields(
            value=binding,
            fields={"sha256", "size"},
            label="Issue #15 producer source binding",
        )
        path = _bound_repository_file(repository_root=runtime_root, relative=relative,)
        if binding["size"] != path.stat().st_size or binding["sha256"] != sha256_file(
            path=path
        ):
            raise RequirementError(
                "Issue #15 audited producer source differs: {}".format(relative)
            )
    if "scripts/sec_pipeline.py" not in source_files:
        raise RequirementError("Issue #15 exact-base pipeline binding is missing")
    pipeline_binding = source_files["scripts/sec_pipeline.py"]
    if pipeline_binding["sha256"] != ISSUE_15_BASE_PIPELINE_SHA256:
        raise RequirementError("Issue #15 exact-base pipeline binding differs")

    producers = inventory["producers"]
    if not isinstance(producers, list) or not producers:
        raise RequirementError("Issue #15 producer records are invalid")
    producer_fields = {
        "active_metric_ids",
        "covered_metric_ids",
        "kind",
        "lifecycle",
        "parent_inventory_groups",
        "producer_id",
        "purpose",
        "retired_metric_ids",
    }
    producer_by_id: Dict[str, Dict[str, object]] = {}
    metric_ids = source_strategy["metric_id_set"]
    if not isinstance(metric_ids, list):
        raise RequirementError("Issue #15 metric identity set is invalid")
    metric_id_set = set(metric_ids)
    for producer in producers:
        if not isinstance(producer, dict):
            raise RequirementError("Issue #15 producer record is invalid")
        _require_exact_fields(
            value=producer, fields=producer_fields, label="Issue #15 producer record",
        )
        producer_id = producer["producer_id"]
        if (
            not isinstance(producer_id, str)
            or producer_id in producer_by_id
            or "::" not in producer_id
        ):
            raise RequirementError("Issue #15 producer identity is invalid")
        active = producer["active_metric_ids"]
        retired = producer["retired_metric_ids"]
        covered = producer["covered_metric_ids"]
        parent_groups = producer["parent_inventory_groups"]
        if (
            not isinstance(active, list)
            or not isinstance(retired, list)
            or not isinstance(covered, list)
            or not isinstance(parent_groups, list)
            or parent_groups != sorted(set(parent_groups))
            or not isinstance(producer["purpose"], str)
            or not producer["purpose"]
            or active != sorted(set(active))
            or retired != sorted(set(retired))
            or set(active) & set(retired)
            or covered != sorted(set(active) | set(retired))
            or not set(covered).issubset(metric_id_set)
        ):
            raise RequirementError("Issue #15 producer metric scope is invalid")
        source_relative = producer_id.split("::", 1)[0]
        if source_relative not in source_files:
            raise RequirementError("Issue #15 producer source is unbound")
        producer_by_id[producer_id] = producer
    if [row["producer_id"] for row in producers] != sorted(producer_by_id):
        raise RequirementError("Issue #15 producer records are not ordered")
    expected_source_files = {
        producer_id.split("::", 1)[0] for producer_id in producer_by_id
    }
    if set(source_files) != expected_source_files:
        raise RequirementError("Issue #15 producer source set differs")

    semantic = [row for row in producers if row["kind"] == "SEMANTIC_PRODUCER"]
    shared = [row for row in producers if row["kind"] == "SHARED_PLUMBING"]
    if len(semantic) + len(shared) != len(producers):
        raise RequirementError("Issue #15 producer kind is invalid")
    semantic_ids = [row["producer_id"] for row in semantic]
    shared_id_list = [row["producer_id"] for row in shared]
    semantic_id_set = set(semantic_ids)
    shared_ids = set(shared_id_list)
    if (
        len(semantic) != ISSUE_15_EXPECTED_SEMANTIC_PRODUCER_COUNT
        or len(shared) != ISSUE_15_EXPECTED_SHARED_PLUMBING_COUNT
        or content_hash(value=semantic_ids) != ISSUE_15_EXPECTED_PRODUCER_EXACT_SET_HASH
        or content_hash(value=shared_id_list) != ISSUE_15_EXPECTED_SHARED_EXACT_SET_HASH
        or any(
            row["active_metric_ids"]
            or row["retired_metric_ids"]
            or row["covered_metric_ids"]
            or row["lifecycle"] != "RETAINABLE_SHARED_PLUMBING"
            for row in shared
        )
        or any(
            row["lifecycle"]
            != (
                "ACTIVE_WITH_RETIRED_SCOPE"
                if row["active_metric_ids"] and row["retired_metric_ids"]
                else "ACTIVE_CURRENT_RUNTIME"
                if row["active_metric_ids"]
                else "RETIRED_TOMBSTONE"
            )
            for row in semantic
        )
    ):
        raise RequirementError(
            "Issue #15 producer exact set or active/retired scope differs"
        )
    _validate_issue_15_scope_evidence(
        inventory=inventory,
        producer_by_id=producer_by_id,
        semantic_id_set=semantic_id_set,
        metric_id_set=metric_id_set,
    )
    if (
        content_hash(value=producers) != ISSUE_15_EXPECTED_PRODUCER_RECORD_SET_HASH
        or content_hash(value=semantic) != ISSUE_15_EXPECTED_SEMANTIC_RECORD_SET_HASH
    ):
        raise RequirementError("Issue #15 complete producer record authority differs")

    migration_rules = parent_inventory["migration_rules"]
    if not isinstance(migration_rules, dict):
        raise RequirementError("Parent inventory migration rules are invalid")
    expected_groups = {}
    for group in sorted(migration_rules):
        members = parent_inventory[group]
        if (
            not isinstance(members, list)
            or any(not isinstance(symbol, str) for symbol in members)
            or len(members) != len(set(members))
        ):
            raise RequirementError("Parent inventory group is invalid")
        expected_groups[group] = members
    if inventory["parent_inventory_groups"] != expected_groups:
        raise RequirementError("Issue #15 parent inventory groups differ")
    dispositions = inventory["parent_symbol_dispositions"]
    if not isinstance(dispositions, dict) or set(dispositions) != set(expected_groups):
        raise RequirementError("Issue #15 parent dispositions are incomplete")
    derived_groups: Dict[str, set[str]] = {}
    for group, members in expected_groups.items():
        group_dispositions = dispositions[group]
        if not isinstance(group_dispositions, dict) or set(group_dispositions) != set(
            members
        ):
            raise RequirementError(
                "Issue #15 parent symbol disposition set differs: {}".format(group)
            )
        migration_rule = migration_rules[group]
        if not isinstance(migration_rule, dict):
            raise RequirementError("Parent inventory migration rule is invalid")
        kind = migration_rule["kind"]
        for symbol in members:
            disposition = group_dispositions[symbol]
            identity = _parent_inventory_identity(group=group, symbol=symbol,)
            target = None
            if kind == "INVARIANT":
                if disposition != "INVARIANT_NOT_PRODUCER":
                    raise RequirementError("Parent invariant disposition differs")
            elif kind == "CONFIGURATION":
                if disposition != "OBSOLETE_WITH_PROOF":
                    raise RequirementError("Parent config disposition differs")
            elif disposition == "INCLUDED_AS_SEMANTIC_PRODUCER":
                if identity not in semantic_id_set:
                    raise RequirementError("Parent producer inclusion is invalid")
                target = identity
            elif disposition == "RECLASSIFIED_AS_SHARED_PLUMBING":
                if identity not in shared_ids:
                    raise RequirementError("Parent shared reclassification is invalid")
                target = identity
            elif isinstance(disposition, str) and disposition.startswith(
                "ALIASED_TO::"
            ):
                target = disposition.removeprefix("ALIASED_TO::")
                if target not in semantic_id_set:
                    raise RequirementError("Parent producer alias is invalid")
            else:
                raise RequirementError("Parent production disposition is invalid")
            if target is not None:
                derived_groups.setdefault(target, set()).add(group)
    for producer_id, producer in producer_by_id.items():
        if producer["parent_inventory_groups"] != sorted(
            derived_groups.get(producer_id, set())
        ):
            raise RequirementError("Issue #15 producer parent-group derivation differs")

    coverage = {
        metric_id: [
            row["producer_id"]
            for row in semantic
            if metric_id in row["covered_metric_ids"]
        ]
        for metric_id in metric_ids
    }
    if (
        inventory["semantic_producer_count"] != len(semantic)
        or inventory["shared_plumbing_count"] != len(shared)
        or inventory["producer_exact_set_hash"] != content_hash(value=semantic_ids)
        or inventory["shared_plumbing_exact_set_hash"]
        != content_hash(value=shared_id_list)
        or inventory["producer_record_set_hash"] != content_hash(value=producers)
        or inventory["semantic_producer_record_set_hash"]
        != content_hash(value=semantic)
        or inventory["metric_id_set"] != metric_ids
        or inventory["metric_id_set_hash"] != content_hash(value=metric_ids)
        or inventory["covered_metric_ids"] != metric_ids
        or inventory["coverage_by_metric"] != coverage
        or any(not rows for rows in coverage.values())
    ):
        raise RequirementError("Issue #15 producer closure differs")


def _load_issue_15_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Verify the exact Issue #15 WB-1 authority snapshot.

    Args:
        snapshot_dir: ``requirements/issue_15_v1`` or an exact test copy.

    Returns:
        Child closure, parent binding, effective Decisions, frozen baseline,
        and the complete decision chains.

    Raises:
        RequirementError: On parent drift, byte drift, detached Decisions,
        incomplete producer coverage, or overstated foundation evidence.
    """
    paths = _issue_15_paths(snapshot_dir=snapshot_dir)
    baseline = _read_object(path=paths["baseline"])
    register = _read_object(path=paths["decisions"])
    transfer = _read_object(path=paths["transfer"])
    inventory = _read_object(path=paths["legacy_inventory"])
    source_strategy = _read_object(path=paths["source_strategy"])
    foundation = _read_object(path=paths["foundation_verification"])

    baseline_fields = {
        "contract_sha256",
        "created_at_utc",
        "effective_decision_ids",
        "foundation_merge_commit",
        "foundation_merge_tree",
        "foundation_source_commit",
        "foundation_source_tree",
        "foundation_tag",
        "foundation_tag_object",
        "foundation_tag_peeled_commit",
        "issue_body_sha256",
        "issue_contract_revision",
        "issue_number",
        "issue_url",
        "metrics_matrix_sha256",
        "parent_requirement_closure_hash",
        "parent_requirement_hashes",
        "parent_requirement_id",
        "pending_decision_ids",
        "record_type",
        "repository_commit",
        "repository_identity",
        "repository_tree",
        "requirement_id",
        "root_business_artifacts",
        "runtime_authority_files",
        "schema_version",
        "semantic_runtime_versions",
        "semantic_runtime_versions_hash",
        "snapshot_files",
        "source_input_role",
    }
    _require_exact_fields(
        value=baseline, fields=baseline_fields, label="Issue #15 baseline",
    )
    if baseline["requirement_id"] != ISSUE_15_REQUIREMENT_ID:
        raise RequirementError("Issue #15 baseline identity differs")
    if baseline["issue_number"] != 15:
        raise RequirementError("Issue #15 number differs")
    contract_sha256 = sha256_file(path=paths["contract"])
    if (
        contract_sha256 != ISSUE_15_CONTRACT_SHA256
        or baseline["contract_sha256"] != contract_sha256
        or baseline["issue_body_sha256"] != contract_sha256
    ):
        raise RequirementError("Issue #15 Contract bytes differ")

    bound_files = baseline["snapshot_files"]
    if not isinstance(bound_files, dict):
        raise RequirementError("Issue #15 snapshot file bindings are invalid")
    expected_bound = {
        relative
        for key, relative in ISSUE_15_SNAPSHOT_FILES.items()
        if key != "baseline"
    }
    if set(bound_files) != expected_bound:
        raise RequirementError("Issue #15 snapshot file set differs")
    for relative in sorted(expected_bound):
        binding = bound_files[relative]
        if not isinstance(binding, dict):
            raise RequirementError("Issue #15 file binding is invalid")
        _require_exact_fields(
            value=binding, fields={"sha256", "size"}, label="Issue #15 file binding",
        )
        path = snapshot_dir / relative
        if (
            binding["sha256"] != sha256_file(path=path)
            or binding["size"] != path.stat().st_size
        ):
            raise RequirementError(
                "Issue #15 snapshot file bytes differ: {}".format(relative)
            )

    repository_root = snapshot_dir.parents[1]
    runtime_bindings = baseline["runtime_authority_files"]
    if (
        not isinstance(runtime_bindings, dict)
        or set(runtime_bindings) != ISSUE_15_RUNTIME_AUTHORITY_FILES
    ):
        raise RequirementError("Issue #15 runtime authority file set differs")
    for relative in sorted(ISSUE_15_RUNTIME_AUTHORITY_FILES):
        binding = runtime_bindings[relative]
        if not isinstance(binding, dict):
            raise RequirementError("Issue #15 runtime authority binding is invalid")
        _require_exact_fields(
            value=binding,
            fields={"sha256", "size"},
            label="Issue #15 runtime authority binding",
        )
        path = _bound_repository_file(
            repository_root=repository_root, relative=relative,
        )
        if (
            binding["sha256"] != sha256_file(path=path)
            or binding["size"] != path.stat().st_size
        ):
            raise RequirementError(
                "Issue #15 runtime authority bytes differ: {}".format(relative)
            )

    parent_dir = snapshot_dir.parent / PARENT_REQUIREMENT_ID
    parent = _load_ai_first_snapshot(snapshot_dir=parent_dir)
    if (
        baseline["parent_requirement_id"] != PARENT_REQUIREMENT_ID
        or baseline["parent_requirement_closure_hash"]
        != parent["requirement_closure_hash"]
        or baseline["parent_requirement_hashes"] != parent["hashes"]
    ):
        raise RequirementError("Issue #15 parent Requirement binding differs")
    if baseline["semantic_runtime_versions"] != SEMANTIC_VERSIONS:
        raise RequirementError("Issue #15 semantic runtime versions differ")
    if baseline["semantic_runtime_versions_hash"] != content_hash(
        value=SEMANTIC_VERSIONS
    ):
        raise RequirementError("Issue #15 semantic runtime hash differs")

    required_register = {
        "decisions",
        "issue_contract_revision",
        "pending_decisions",
        "requirement_id",
        "schema_version",
    }
    _require_exact_fields(
        value=register, fields=required_register, label="Issue #15 Decision Register",
    )
    if register["requirement_id"] != ISSUE_15_REQUIREMENT_ID:
        raise RequirementError("Issue #15 Decision Register identity differs")
    if not isinstance(register["decisions"], list):
        raise RequirementError("Issue #15 decisions must be an array")
    if not isinstance(register["pending_decisions"], list):
        raise RequirementError("Issue #15 pending decisions must be an array")
    parent_register = _read_object(path=parent_dir / "decision_register.json")
    parent_decisions = parent_register["decisions"]
    parent_pending = parent_register["pending_decisions"]
    if not isinstance(parent_decisions, list) or not isinstance(parent_pending, list,):
        raise RequirementError("Parent Decision history is invalid")
    if (
        register["decisions"][: len(parent_decisions)] != parent_decisions
        or register["pending_decisions"] != parent_pending
    ):
        raise RequirementError("Issue #15 historical Decision bytes differ")
    all_decisions = list(register["decisions"])
    all_decisions.extend(register["pending_decisions"])
    decisions, chains = _resolve_decisions(decisions=all_decisions)
    pending_ids = sorted(
        decision_id
        for decision_id, decision in decisions.items()
        if decision["status"] == "PENDING_EXTERNAL_APPROVAL"
    )
    if set(decisions) != ISSUE_15_EFFECTIVE_DECISION_IDS:
        raise RequirementError("Issue #15 effective Decision set differs")
    if pending_ids or baseline["pending_decision_ids"] != []:
        raise RequirementError("Issue #15 has an effective pending Decision")
    if sorted(baseline["effective_decision_ids"]) != sorted(decisions):
        raise RequirementError("Issue #15 baseline Decision set differs")
    if (
        len(chains["D-01"]) != 4
        or len(chains["D-07"]) != 11
        or len(chains["D-26"]) != 3
        or len(chains["D-35"]) != 2
        or len(chains["D-36"]) != 2
        or decisions["D-01"]["supersedes_decision_id"]
        != _decision_record_hash(decision=parent["effective_decisions"]["D-01"])
        or decisions["D-07"]["supersedes_decision_id"]
        != _decision_record_hash(decision=chains["D-07"][9])
        or chains["D-26"][1]["supersedes_decision_id"]
        != _decision_record_hash(decision=parent["effective_decisions"]["D-26"])
        or decisions["D-26"]["supersedes_decision_id"]
        != _decision_record_hash(decision=chains["D-26"][1])
        or decisions["D-35"]["supersedes_decision_id"]
        != _decision_record_hash(decision=chains["D-35"][0])
        or decisions["D-36"]["supersedes_decision_id"]
        != _decision_record_hash(decision=chains["D-36"][0])
    ):
        raise RequirementError("Issue #15 Decision tip binding differs")
    expected_d01_choice = dict(parent["effective_decisions"]["D-01"]["choice"])
    expected_d01_choice["retry_count"] = 0
    d07_choice = decisions["D-07"]["choice"]
    d26_choice = decisions["D-26"]["choice"]
    d35_choice = decisions["D-35"]["choice"]
    d36_choice = decisions["D-36"]["choice"]
    effective_tip_hashes = {
        decision_id: _decision_record_hash(decision=decisions[decision_id])
        for decision_id in ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES
    }
    if (
        decisions["D-01"]["choice"] != expected_d01_choice
        or d07_choice != ISSUE_15_D07_EFFECTIVE_CHOICE
        or "freeze_replay" in d26_choice["prohibited_required_test_classes"]
        or not d26_choice["required_short_deterministic_invariants"]
        or "budget_preflight_provider_calls_zero"
        in d26_choice["required_short_deterministic_invariants"]
        or effective_tip_hashes != ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES
        or any(
            decisions[decision_id]["evidence"]
            != ISSUE_15_POST_FREEZE_DECISION_EVIDENCE_BY_ID[decision_id]
            for decision_id in ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES
        )
        or "BUDGET_EXCEEDED" in d35_choice["terminal_classes"]
        or d35_choice["http_402_automatic_retries"] != 0
        or not d35_choice["http_402_stops_execution"]
        or not d35_choice["http_402_stops_batch"]
        or d35_choice["monetary_budget_terminal_classes"] != []
        or d35_choice["non_monetary_safety_terminal_classes"]
        != ["PAYLOAD_LIMIT", "CONTEXT_LIMIT", "RESOURCE_LIMIT"]
        or d35_choice["resource_limit_is_monetary_budget_gate"]
        or d36_choice["repository_monetary_budget_enforcement"] != "DISABLED"
        or d36_choice["spending_authority"] != "EXTERNAL_API_ACCOUNT_BALANCE"
        or d36_choice["per_call_monetary_hard_cap_exists"]
        or d36_choice["batch_monetary_hard_cap_exists"]
        or d36_choice["monetary_budget_preflight"]
        or d36_choice["provider_usage_observability_blocking"]
        or d36_choice["estimated_or_actual_cost_may_block_provider_call"]
        or d36_choice["forbidden_monetary_budget_fields"]
        != [
            "owner_absolute_total_cap",
            "owner_absolute_per_request_cap",
            "remaining_owner_cap",
            "maximum_authorized_cost",
        ]
    ):
        raise RequirementError("Issue #15 superseding Decision content differs")

    if (
        transfer["parent_requirement_closure_hash"]
        != parent["requirement_closure_hash"]
        or transfer["contract_sha256"] != contract_sha256
        or transfer["requirement_id"] != ISSUE_15_REQUIREMENT_ID
    ):
        raise RequirementError("Issue #15 authority transfer differs")
    if (
        inventory["parent_legacy_inventory_sha256"]
        != parent["hashes"]["legacy_path_inventory_sha256"]
        or inventory["baseline_source_commit"] != baseline["repository_commit"]
    ):
        raise RequirementError("Issue #15 producer inventory parent differs")
    parent_inventory = _read_object(path=parent_dir / "legacy_path_inventory.json")
    _validate_issue_15_producer_inventory(
        inventory=inventory,
        parent_inventory=parent_inventory,
        source_strategy=source_strategy,
    )
    mode_metrics = sorted(
        metric_id
        for mode in source_strategy["metrics_by_target_source_mode"].values()
        for metric_id in mode
    )
    if (
        source_strategy["row_count"] != 230
        or source_strategy["metric_id_count"] != 39
        or mode_metrics != source_strategy["metric_id_set"]
        or source_strategy["matrix_sha256"] != baseline["metrics_matrix_sha256"]
    ):
        raise RequirementError("Issue #15 source baseline differs")
    if (
        foundation["foundation_source_commit"] != ISSUE_15_FOUNDATION_SOURCE_COMMIT
        or baseline["foundation_source_commit"] != ISSUE_15_FOUNDATION_SOURCE_COMMIT
        or foundation["foundation_merge_commit"] != ISSUE_15_FOUNDATION_MERGE_COMMIT
        or baseline["foundation_merge_commit"] != ISSUE_15_FOUNDATION_MERGE_COMMIT
        or foundation["foundation_tag"] != ISSUE_15_FOUNDATION_TAG
        or baseline["foundation_tag"] != ISSUE_15_FOUNDATION_TAG
        or foundation["highest_evidence_level"] != "FAST_LOCAL_ONLY"
        or foundation["real_external_provider_egress_count"] != 0
        or foundation["paid_provider_call_count"] != 0
        or len(foundation["verification_commands"]) != 4
        or any(
            command["return_code"] != 0
            for command in foundation["verification_commands"]
        )
    ):
        raise RequirementError("Issue #15 foundation evidence differs")
    _validate_foundation_receipt_bindings(
        foundation=foundation, repository_root=repository_root,
    )

    hashes = {
        "baseline_sha256": sha256_file(path=paths["baseline"]),
        "contract_sha256": contract_sha256,
        "decision_register_sha256": sha256_file(path=paths["decisions"]),
        "event_route_catalog_sha256": sha256_file(
            path=repository_root / "catalog" / "event_routes.json"
        ),
        "provider_model_runtime_sha256": sha256_file(
            path=repository_root / "config" / "provider_model_runtime.json"
        ),
        "public_projection_catalog_sha256": sha256_file(
            path=(
                repository_root
                / "catalog"
                / "zero_ai_public_projection.json"
            )
        ),
        "foundation_verification_receipt_sha256": sha256_file(
            path=paths["foundation_verification"]
        ),
        "issue_body_sha256": contract_sha256,
        "legacy_semantic_producer_inventory_sha256": sha256_file(
            path=paths["legacy_inventory"]
        ),
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "semantic_runtime_versions_hash": content_hash(value=SEMANTIC_VERSIONS),
        "source_strategy_registry_sha256": sha256_file(
            path=repository_root / "config" / "source_strategy_registry.json"
        ),
        "source_strategy_baseline_receipt_sha256": sha256_file(
            path=paths["source_strategy"]
        ),
        "transfer_manifest_sha256": sha256_file(path=paths["transfer"]),
    }
    return {
        "requirement_id": register["requirement_id"],
        "issue_contract_revision": register["issue_contract_revision"],
        "hashes": hashes,
        "requirement_closure_hash": content_hash(value=hashes),
        "parent_requirement_id": PARENT_REQUIREMENT_ID,
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "baseline": baseline,
        "effective_decisions": decisions,
        "decision_chains": chains,
        "pending_decision_ids": pending_ids,
    }


def load_requirement_snapshot(*, snapshot_dir: Path) -> Dict[str, object]:
    """Load one of the two explicit supported Requirement snapshots.

    Args:
        snapshot_dir: Exact parent ``ai_first_v3_3_1`` or child
            ``issue_15_v1`` snapshot directory. Test copies may use another
            directory name because dispatch is by the bound requirement ID.

    Returns:
        Verified Requirement closure and effective Decision chains.

    Raises:
        RequirementError: On an unknown Requirement ID or invalid bytes.
    """
    baseline = _read_object(path=snapshot_dir / "baseline_manifest.json")
    if "requirement_id" not in baseline:
        raise RequirementError("Requirement baseline identity is missing")
    requirement_id = baseline["requirement_id"]
    if requirement_id == PARENT_REQUIREMENT_ID:
        return _load_ai_first_snapshot(snapshot_dir=snapshot_dir)
    if requirement_id == ISSUE_15_REQUIREMENT_ID:
        return _load_issue_15_snapshot(snapshot_dir=snapshot_dir)
    raise RequirementError(
        "Unsupported Requirement Snapshot: {}".format(requirement_id)
    )
