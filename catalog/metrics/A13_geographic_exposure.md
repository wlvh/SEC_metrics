---
{
  "metric_id": "A13",
  "name": "Geographic exposure",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "structured_first_ai_fallback",
  "disclosure_group": "financial_statement",
  "applicability": {"all": ["financial"], "none": []},
  "required_claims": {"geography_scope": "international"},
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["geography_scope"],
    "allowed_dimensions": ["geography_scope"],
    "exact_enum_aliases": {
      "geography_scope": {
        "international": ["International"],
        "united_states": ["United States", "U.S."]
      }
    },
    "selection_preference": {
      "dimension_order": ["geography_scope"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["global total", "segment total"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Geographic exposure

This is the table fallback after SourceStrategy's structured-first route; an
undeclared geography literal requires HUMAN review.
