---
{
  "metric_id": "A03",
  "name": "Liquidity coverage ratio",
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
    "entity_scope": "firm",
    "aggregation": "average"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": [
      "entity_scope",
      "aggregation"
    ],
    "allowed_dimensions": [
      "entity_scope",
      "aggregation"
    ],
    "exact_enum_aliases": {
      "entity_scope": {
        "firm": [
          "Firm",
          "Citigroup’s consolidated LCR"
        ]
      },
      "aggregation": {
        "average": [
          "average"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": [
        "entity_scope",
        "aggregation"
      ],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": [
    "bank subsidiary",
    "period-end"
  ],
  "review_policy": "none",
  "legacy_projection": {},
  "dependencies": [],
  "quality_rule": {
    "resolver": "ordinary_financial_source_v1",
    "semantic_role": "lcr_disclosed_average",
    "measurement_period": "source_disclosed_average_ending_at_filing_end",
    "filing_period_role": "separate_annual_reporting_group",
    "source_admission": "trusted_saved_normal_source_set",
    "scope_gate": "complete_source_semantic_fact_with_no_unresolved_competitors",
    "selection": "recompute_from_original_bytes",
    "ai_calls": 0,
    "fixture_answer_or_receipt_input": false
  }
}
---

# Liquidity coverage ratio — ordinary source result

Actual averaging interval is taken from the source; the filing year is only its reporting group. A quarterly average is never labelled or calculated as an annual average. The historic Citi fixture exception is not reused.

This additive structured route retains the approved metric name, scope and units.
It grants no old AI qualification credit, source acquisition allowance, Run
activation, formal adoption, publication or active-state change. Unsupported
source interpretation is an implementation gap and must not be relabelled as
issuer disclosure absence.
