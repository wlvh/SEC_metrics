---
{
  "metric_id": "A04",
  "name": "Net interest margin",
  "kind": "direct_numeric",
  "canonical_unit": "ratio",
  "reported_unit": "percent",
  "source_mode": "ai_table",
  "disclosure_group": "financial_statement",
  "applicability": {"all": ["financial"], "none": []},
  "required_claims": {"basis": "managed_basis"},
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["basis"],
    "allowed_dimensions": ["basis"],
    "exact_enum_aliases": {
      "basis": {"managed_basis": ["managed basis"]}
    },
    "selection_preference": {
      "dimension_order": ["basis"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["average total assets", "proxy"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Net interest margin

The table task binds the reported managed-basis literal.  Any proxy or other
basis is a separately reviewed claim rather than an automatic substitution.
