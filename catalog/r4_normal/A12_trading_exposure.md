---
{
  "metric_id": "A12",
  "name": "Trading exposure",
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
    "confidence_level": "ninety_five_percent",
    "holding_period": "one_day"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "confidence_level",
      "holding_period"
    ],
    "allowed_dimensions": [
      "confidence_level",
      "holding_period"
    ],
    "exact_enum_aliases": {
      "confidence_level": {
        "ninety_five_percent": [
          "95%",
          "95 percent"
        ],
        "ninety_nine_percent": [
          "99%",
          "99 percent"
        ]
      },
      "holding_period": {
        "one_day": [
          "one day",
          "one-day"
        ],
        "ten_days": [
          "10 days",
          "ten days",
          "10-day"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "confidence_level",
        "holding_period"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "regulatory VaR",
    "regulatory capital calculations",
    "maximum"
  ],
  "review_policy": "none",
  "legacy_projection": {},
  "dependencies": [],
  "quality_rule": {
    "resolver": "ordinary_financial_source_v1",
    "semantic_role": "firmwide_annual_average_var",
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

# Trading exposure — ordinary source result

The statistical window is the full filing year and the statistic is average. Its risk holding period is separately one day with 95 percent confidence. A trading component, regulatory VaR or hypothetical change is not the total measure.

This additive structured route retains the approved metric name, scope and units.
It grants no old AI qualification credit, source acquisition allowance, Run
activation, formal adoption, publication or active-state change. Unsupported
source interpretation is an implementation gap and must not be relabelled as
issuer disclosure absence.
