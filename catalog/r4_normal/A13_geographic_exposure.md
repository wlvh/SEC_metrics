---
{
  "metric_id": "A13",
  "name": "International net revenue",
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
    "geography_scope": "international"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "geography_scope"
    ],
    "allowed_dimensions": [
      "geography_scope"
    ],
    "exact_enum_aliases": {
      "geography_scope": {
        "international": [
          "International",
          "Total international"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "geography_scope"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "net income",
    "assets",
    "loans",
    "deposits",
    "maturity schedules",
    "segment-only totals",
    "global total"
  ],
  "review_policy": "none",
  "legacy_projection": {},
  "dependencies": [],
  "quality_rule": {
    "resolver": "ordinary_financial_source_v1",
    "semantic_role": "international_net_revenue",
    "measurement_period": "exact_annual_filing_period",
    "filing_period_role": "separate_annual_reporting_group",
    "source_admission": "trusted_saved_normal_source_set",
    "scope_gate": "complete_source_semantic_fact_with_no_unresolved_competitors",
    "selection": "recompute_from_original_bytes",
    "ai_calls": 0,
    "fixture_answer_or_receipt_input": false
  }
}
---

# International net revenue — ordinary source result

Use full-year international net revenue from native facts whose geography and net-revenue meaning are proved by the actual SourceSet, dimensions, table labels and linked notes. No source-specific member list or regional sum supplies an answer.

This additive structured route retains the approved metric name, scope and units.
It grants no old AI qualification credit, source acquisition allowance, Run
activation, formal adoption, publication or active-state change. Unsupported
source interpretation is an implementation gap and must not be relabelled as
issuer disclosure absence.
