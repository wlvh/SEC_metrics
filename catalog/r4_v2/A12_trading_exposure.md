---
{
  "metric_id": "A12",
  "name": "Trading exposure",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "ai_table",
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
        ]
      },
      "holding_period": {
        "one_day": [
          "one day",
          "one-day"
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
    "maximum"
  ],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Trading exposure: source-bound successor scope

The numeric value remains an exact cell in the selected table; its scale
remains an exact header in that table. Owner policy comment 5524085182
allows only confidence level 95 percent and holding period one day to be
proved by exact same-source, same-section text spans with a deterministic
target-table association and complete competing-span dispositions.
No prose is copied into a table, caption or provider payload.
