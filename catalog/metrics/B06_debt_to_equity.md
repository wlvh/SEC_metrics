---
{
  "metric_id": "B06",
  "name": "Debt-to-equity",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "ratio",
  "source_mode": "structured_first_ai_fallback",
  "disclosure_group": "financial_statement",
  "applicability": {"all": [], "none": []},
  "required_claims": {"entity_scope": "consolidated"},
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["entity_scope"],
    "allowed_dimensions": ["entity_scope"],
    "exact_enum_aliases": {
      "entity_scope": {"consolidated": ["Consolidated"]}
    },
    "selection_preference": {
      "dimension_order": ["entity_scope"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["Ford Credit", "captive finance"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Debt-to-equity

This table task is available only after a structured ambiguity trigger and
requires an exact consolidated-scope proof.
