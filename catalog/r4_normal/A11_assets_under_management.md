---
{
  "metric_id": "A11",
  "name": "Assets under management",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "structured",
  "disclosure_group": "financial_statement",
  "applicability": {
    "all": [
      "financial"
    ],
    "none": []
  },
  "required_claims": {
    "asset_scope": "total_assets_under_management"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "asset_scope"
    ],
    "allowed_dimensions": [
      "asset_scope"
    ],
    "exact_enum_aliases": {
      "asset_scope": {
        "total_assets_under_management": [
          "Total assets under management"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "asset_scope"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "client assets",
    "custody"
  ],
  "review_policy": "none",
  "legacy_projection": {},
  "dependencies": [],
  "quality_rule": {
    "resolver": "ordinary_financial_source_v1",
    "semantic_role": "complete_assets_under_management",
    "measurement_period": "filing_end_instant",
    "filing_period_role": "separate_annual_reporting_group",
    "source_admission": "trusted_saved_normal_source_set",
    "scope_gate": "complete_source_semantic_fact_with_no_unresolved_competitors",
    "selection": "recompute_from_original_bytes",
    "ai_calls": 0,
    "fixture_answer_or_receipt_input": false
  }
}
---

# Assets under management — ordinary source result

Use the complete source-defined AUM balance, including its reported inclusion policy, client scope, manager scope, currency and amount scale. Equal repeated values alone do not prove completeness.

This additive structured route retains the approved metric name, scope and units.
It grants no old AI qualification credit, source acquisition allowance, Run
activation, formal adoption, publication or active-state change. Unsupported
source interpretation is an implementation gap and must not be relabelled as
issuer disclosure absence.
