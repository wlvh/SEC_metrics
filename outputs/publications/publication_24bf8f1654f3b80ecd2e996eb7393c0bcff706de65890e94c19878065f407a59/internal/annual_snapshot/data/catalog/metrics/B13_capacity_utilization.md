---
{
  "metric_id": "B13",
  "name": "Capacity utilization",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "percent",
  "source_mode": "ai_table",
  "disclosure_group": "financial_statement",
  "applicability": {"all": [], "none": []},
  "required_claims": {"capacity_basis": "production"},
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["capacity_basis"],
    "allowed_dimensions": ["capacity_basis"],
    "exact_enum_aliases": {
      "capacity_basis": {"production": ["production"]}
    },
    "selection_preference": {
      "dimension_order": ["capacity_basis"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["manufacturing capacity", "qualitative"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Capacity utilization

Only a numeric production-capacity table claim can enter this task; a
qualitative statement remains outside the numeric Reader contract.
