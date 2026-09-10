---
{
  "metric_id": "A12",
  "name": "Trading exposure",
  "kind": "direct_numeric",
  "canonical_unit": "USD",
  "reported_unit": "USD",
  "source_mode": "ai_table",
  "disclosure_group": "financial_statement",
  "applicability": {"all": ["financial"], "none": []},
  "required_claims": {
    "confidence_level": "ninety_five_percent",
    "holding_period": "one_day"
  },
  "scope_contract": {
    "scope_contract_version": "2",
    "required_dimensions": ["confidence_level", "holding_period"],
    "allowed_dimensions": ["confidence_level", "holding_period"],
    "exact_enum_aliases": {
      "confidence_level": {
        "ninety_five_percent": ["95%", "95 percent"],
        "ninety_nine_percent": ["99%", "99 percent"]
      },
      "holding_period": {
        "one_day": ["one day", "one-day"],
        "ten_days": ["10 days", "ten days", "10-day"]
      }
    },
    "selection_preference": {
      "dimension_order": ["confidence_level", "holding_period"],
      "prefer_complete_required_dimensions": true
    },
    "cross_dimension_constraints": []
  },
  "forbidden_confusions": ["regulatory VaR", "maximum"],
  "review_policy": "human_optional_system_audited_r5",
  "legacy_projection": {},
  "dependencies": []
}
---

# Trading exposure

The contract accepts each declared confidence/holding-period enum combination
after exact raw-locator proof; the required claims provide only the legacy
default, not an automatic rejection of another declared enum combination.
