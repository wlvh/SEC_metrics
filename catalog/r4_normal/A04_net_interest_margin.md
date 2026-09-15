---
{
  "metric_id": "A04",
  "name": "Net interest margin",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "percent",
  "source_mode": "structured",
  "disclosure_group": "financial_statement",
  "applicability": {
    "all": [
      "financial"
    ],
    "none": []
  },
  "required_claims": {
    "basis": "managed_basis"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "basis"
    ],
    "allowed_dimensions": [
      "basis"
    ],
    "exact_enum_aliases": {
      "basis": {
        "managed_basis": [
          "managed basis",
          "taxable equivalent basis"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "basis"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "average total assets",
    "proxy"
  ],
  "review_policy": "none",
  "legacy_projection": {},
  "dependencies": [],
  "quality_rule": {
    "resolver": "ordinary_financial_source_v1",
    "semantic_role": "managed_net_interest_margin",
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

# Net interest margin — ordinary source result

Retain the disclosed managed or taxable-equivalent NIM. The complete earning-asset denominator and named tax-basis relationship validate the rate; arithmetic does not replace it.

This additive structured route retains the approved metric name, scope and units.
It grants no old AI qualification credit, source acquisition allowance, Run
activation, formal adoption, publication or active-state change. Unsupported
source interpretation is an implementation gap and must not be relabelled as
issuer disclosure absence.
