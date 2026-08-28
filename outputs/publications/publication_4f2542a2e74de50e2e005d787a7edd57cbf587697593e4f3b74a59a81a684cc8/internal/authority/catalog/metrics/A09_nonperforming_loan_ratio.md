---
{
  "metric_id": "A09",
  "name": "Non-performing loan ratio",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "ratio",
  "source_mode": "structured_first_ai_fallback",
  "disclosure_group": "financial_statement",
  "applicability": {"all": ["financial"], "none": []},
  "required_claims": {"loan_population": "firmwide"},
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["loan_population"],
    "allowed_dimensions": ["loan_population"],
    "exact_enum_aliases": {
      "loan_population": {"firmwide": ["Firmwide"]}
    },
    "selection_preference": {
      "dimension_order": ["loan_population"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["nonperforming assets", "credit card"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Non-performing loan ratio

This table contract is only the structured-source ambiguity fallback declared
by SourceStrategy; it never bypasses the structured-first route.
