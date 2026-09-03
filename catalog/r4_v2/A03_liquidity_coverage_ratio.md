---
{
  "metric_id": "A03",
  "name": "Liquidity coverage ratio",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "percent",
  "source_mode": "ai_table",
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
          "Firm"
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
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Liquidity coverage ratio

The task owns a firm-average table claim only; a bank-subsidiary or
period-end disclosure remains a competing claim for review.
