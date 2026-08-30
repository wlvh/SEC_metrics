---
{
  "metric_id": "A11",
  "name": "Assets under management",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "ai_table",
  "disclosure_group": "financial_statement",
  "applicability": {"all": ["financial"], "none": []},
  "required_claims": {"asset_scope": "total_assets_under_management"},
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["asset_scope"],
    "allowed_dimensions": ["asset_scope"],
    "exact_enum_aliases": {
      "asset_scope": {
        "total_assets_under_management": [
          "Total assets under management",
          "Assets under management",
          "Total assets under management, end of year"
        ]
      }
    },
    "selection_preference": {
      "dimension_order": ["asset_scope"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["client assets", "custody"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Assets under management

The task requires an exact total-AUM literal and keeps client-assets/custody
figures as competing evidence rather than treating them as aliases.
