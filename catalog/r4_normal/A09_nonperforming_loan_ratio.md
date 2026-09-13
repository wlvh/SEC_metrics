---
{
  "metric_id": "A09",
  "name": "Non-performing loan ratio",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "ratio",
  "source_mode": "structured",
  "disclosure_group": "financial_statement",
  "applicability": {
    "all": [
      "financial"
    ],
    "none": []
  },
  "required_claims": {
    "loan_population": "firmwide"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "loan_population"
    ],
    "allowed_dimensions": [
      "loan_population"
    ],
    "exact_enum_aliases": {
      "loan_population": {
        "firmwide": [
          "Firmwide"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "loan_population"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "nonperforming assets",
    "credit card"
  ],
  "review_policy": "none",
  "legacy_projection": {},
  "dependencies": [],
  "quality_rule": {
    "resolver": "ordinary_financial_source_v1",
    "semantic_role": "firmwide_nonperforming_loan_ratio",
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

# Non-performing loan ratio — ordinary source result

Recompute the complete native structured route first. A source-bound deterministic HTML relation is allowed only after actual structured ambiguity, with the disclosed firmwide loan ratio and denominator scope preserved.

This additive structured route retains the approved metric name, scope and units.
It grants no old AI qualification credit, source acquisition allowance, Run
activation, formal adoption, publication or active-state change. Unsupported
source interpretation is an implementation gap and must not be relabelled as
issuer disclosure absence.
